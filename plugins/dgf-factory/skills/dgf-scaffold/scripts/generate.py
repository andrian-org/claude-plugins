#!/usr/bin/env python3
"""generate.py — render a new DGF application from its design and shipped templates (ADR 0027 §7.3).

Refuses unless design.py exits 0. Everything is rendered in memory first, so a template that
cannot render writes nothing; the result is then staged inside the folder and moved into place
file by file, and any failure removes what was moved and the staging directory, so the folder
is left as it was. It writes only into a folder design.py accepts as empty, and it never
overwrites: a target that exists is an error, matched by exact case.

  generate.py --folder <dir>             render and write the application
  generate.py --folder <dir> --dry-run   print every target, write nothing
  generate.py --folder <dir> --check     the post-generation check of what was written (check.py)

Usage:  generate.py --folder <dir> [--dry-run | --check] [--verbose]

Exit codes (contract, see .ai-factory/rules/base.md):
  0  written (or planned, or sound)
  1  a target exists, or --check found the application unsound
  3  the design is incomplete, a template is missing or wrong, a write failed, or a usage error
"""

import argparse
import importlib.util
import json
import os
import shutil
import sys
import types
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
TEMPLATES = SKILL / "templates"
MANIFEST = TEMPLATES / "manifest.json"
STAGING = ".dgf-scaffold-staging"
COPY_SKIP = {".git", ".DS_Store", "Thumbs.db"}


_SIBLINGS = {}


def _sibling(name):
    """A module of this folder, loaded by path once, so every caller shares the one instance."""
    if name not in _SIBLINGS:
        spec = importlib.util.spec_from_file_location(f"dgf_scaffold_{name}", HERE / f"{name}.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _SIBLINGS[name] = module
    return _SIBLINGS[name]


design = _sibling("design")
render = _sibling("render")
context = _sibling("context")
report = design.report
knowledge = design.knowledge

REPEATS = ("api", "deployment", "instance", "entity", "module", "workspace", "group", "membership")
MANIFEST_KEYS = ("template", "target", "format", "repeat", "when", "executable")


class Parser(argparse.ArgumentParser):
    def error(self, message):
        print(f"{self.prog}: {message}", file=sys.stderr)
        raise SystemExit(report.EXIT_USAGE)


class Bad(Exception):
    """A defect of the templates or the manifest: reported as SCAFFOLD_TEMPLATE_MISSING (exit 3)."""


class WriteFailed(Exception):
    pass


# --- the manifest --------------------------------------------------------------

def load_manifest(root=None):
    root = Path(root) if root is not None else TEMPLATES
    path = root / "manifest.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise Bad(f"{path.name}: {error}")
    if not isinstance(data, dict) or data.get("manifest_format") != 1 or not isinstance(data.get("entries"), list):
        raise Bad("manifest.json: not a manifest of format 1")
    for index, entry in enumerate(data["entries"]):
        if not isinstance(entry, dict) or set(entry) - set(MANIFEST_KEYS) or "template" not in entry \
                or "target" not in entry or "format" not in entry:
            raise Bad(f"manifest.json: entry {index} needs template, target and format, and no other key than "
                      f"{', '.join(MANIFEST_KEYS)}")
        for name in entry.get("repeat") or []:
            if name not in REPEATS:
                raise Bad(f"manifest.json: entry {index}: `{name}` is not a repeat — {', '.join(REPEATS)}")
        if entry["format"] not in render.FORMATS:
            raise Bad(f"manifest.json: entry {index}: `{entry['format']}` is not a format")
        if not (root / entry["template"]).is_file():
            raise Bad(f"manifest.json: entry {index}: template `{entry['template']}` does not exist")
    copies = data.get("copy") or []
    if not isinstance(copies, list):
        raise Bad("manifest.json: `copy` is not a list")
    return data


def frames(entry, ctx):
    """[(scope frame, description)] — the nested product of the entry's repeats, over the context."""
    scopes = entry.get("repeat") or []
    results = [({}, "")]
    for scope in scopes:
        expanded = []
        for frame, label in results:
            if scope == "api":
                items = ctx["apis"]
            elif scope == "deployment":
                items = frame["api"]["deployments"] if "api" in frame else ctx["deployments"]
            elif scope == "instance":
                items = ctx["instances"]
            elif scope == "entity":
                items = ctx["entities"]
            elif scope == "module":
                items = ctx["modules"]
            elif scope == "group":
                items = ctx["profile_groups"]
            elif scope == "membership":
                items = ctx["memberships"]
            else:
                items = ctx["workspaces"]
            for item in items:
                new = dict(frame)
                new[scope] = item
                if scope == "deployment":
                    new.setdefault("api", next(a for a in ctx["apis"] if a["name"] == item["api"]))
                expanded.append((new, f"{label}/{item['name'] if 'name' in item else item.get('dir')}"))
        results = expanded
    return results


PREDICATES = {
    "supply": lambda ctx, fr, arg: ctx["supply"] == arg,
    "model": lambda ctx, fr, arg: ctx["model"] == arg,
    "multi-instance": lambda ctx, fr, arg: ctx["multi"],
    "single-instance": lambda ctx, fr, arg: not ctx["multi"],
    "has-process": lambda ctx, fr, arg: ctx["has_process"],
    "has-entities": lambda ctx, fr, arg: ctx["has_entities"],
    "any-basic": lambda ctx, fr, arg: ctx["any_basic"],
    "first-workspace": lambda ctx, fr, arg: fr["workspace"]["first"],
    "pattern": lambda ctx, fr, arg: (fr["module"]["has_entity"] if arg == "entity"
                                     else fr["module"]["pattern"] == arg),
    "auth": lambda ctx, fr, arg: arg in fr["deployment"]["auth"],
    "shared-workspace": lambda ctx, fr, arg: ctx["shared"],
    "own-workspace": lambda ctx, fr, arg: not ctx["shared"],
}


def holds(entry, ctx, frame):
    for term in entry.get("when") or []:
        name, _, arg = term.partition(":")
        if name not in PREDICATES:
            raise Bad(f"manifest.json: `{term}` is not a condition — {', '.join(sorted(PREDICATES))}")
        try:
            if not PREDICATES[name](ctx, frame, arg):
                return False
        except KeyError:
            raise Bad(f"manifest.json: `{term}` needs a repeat that supplies its scope")
    return True


def safe_target(text):
    parts = text.split("/")
    if (not text or text.startswith("/") or "\\" in text or any(p in ("", ".", "..") for p in parts)
            or any(ord(c) < 0x20 for c in text) or parts[0] == STAGING):
        raise Bad(f"a target `{report.one_line(text)}` is not a relative path inside the application")
    return text


def plan(ctx, data, root=None):
    """[(target, template, format, frame, executable)] — every file, in target order; nothing is read yet."""
    jobs, seen = [], {}
    for entry in data["entries"]:
        for frame, label in frames(entry, ctx):
            if not holds(entry, ctx, frame):
                continue
            scope = {**ctx, **frame}
            try:
                target, _ = render.render(entry["target"], scope, "text", f"target of {entry['template']}")
            except render.TemplateError as error:
                raise Bad(str(error))
            target = safe_target(target)
            key = target.casefold()
            if key in seen:
                raise Bad(f"two entries render the target `{target}` (or one differing only in case)")
            seen[key] = target
            report.debug("generate.plan", "file", template=entry["template"], target=target)
            jobs.append((target, entry["template"], entry["format"], frame, bool(entry.get("executable"))))
    jobs.sort(key=lambda job: job[0])
    return jobs


def render_all(ctx, jobs, root=None):
    """{target: bytes} — every file rendered; a template error raises Bad before anything is written."""
    root = Path(root) if root is not None else TEMPLATES
    out = {}
    for target, template, fmt, frame, _ in jobs:
        try:
            source = (root / template).read_text(encoding="utf-8")
        except OSError as error:
            raise Bad(f"{template}: {error.strerror}")
        try:
            text, used = render.render(source, {**ctx, **frame}, fmt, template)
        except render.TemplateError as error:
            raise Bad(str(error))
        report.debug("generate.render", "escaped", format=fmt, values=len(used))
        if "\r" in text or "﻿" in text:
            raise Bad(f"{template}: renders a carriage return or a byte-order mark")
        out[target] = text.encode("utf-8")
    return out


# --- existing targets ------------------------------------------------------------

def exact_exists(folder, target):
    """Whether `folder/target` exists, matched by exact case at every step (os.scandir, never Path.exists)."""
    here = Path(folder)
    for part in target.split("/"):
        try:
            with os.scandir(here) as it:
                names = {entry.name for entry in it}
        except OSError:
            return False
        if part not in names:
            return False
        here = here / part
    return True


def any_case_exists(folder, target):
    """Whether a target exists in any case: on APFS and NTFS one differing only in case is the same file."""
    here = Path(folder)
    for part in target.split("/"):
        try:
            with os.scandir(here) as it:
                names = {entry.name.casefold(): entry.name for entry in it}
        except OSError:
            return False
        if part.casefold() not in names:
            return False
        here = here / names[part.casefold()]
    return True


# --- writing ---------------------------------------------------------------------

def base_files(source):
    """[(relative path, Path)] of the base workspace's regular files; links and junk are skipped."""
    found = []
    for directory, names, files in os.walk(source):
        names[:] = sorted(n for n in names if n not in COPY_SKIP and not os.path.islink(os.path.join(directory, n)))
        for name in sorted(files):
            path = Path(directory) / name
            if name in COPY_SKIP or path.is_symlink():
                report.debug("generate.plan", "skipped", path=path)
                continue
            found.append((path.relative_to(source).as_posix(), path))
    return found


def write(folder, files, base):
    """Stage `files` (and the base copy), then move them into place; on any failure undo it all."""
    folder = Path(folder)
    staging = folder / STAGING
    moved, created = [], []
    try:
        folder.mkdir(parents=True, exist_ok=True)
        staging.mkdir()
        for target, data in files.items():
            path = staging / target
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            if target.endswith(".sh"):
                path.chmod(0o755)
        copied = 0
        if base is not None:
            destination = staging / "workspaces" / "webasm"
            for relative, source in base_files(base):
                path = destination / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, path)
                copied += 1
            destination.mkdir(parents=True, exist_ok=True)
        _merge(staging, folder, moved)
        for line in sorted(files):
            print(f"WROTE: {report.one_line(line)}")
            report.debug("generate.write", "moved", path=line)
        if base is not None:
            print(f"WROTE: workspaces/webasm/ ({copied} files)")
        return len(files), copied
    except OSError as error:
        report.debug("generate.write", "failed", path=getattr(error, "filename", None), error=error.strerror)
        _undo(moved)
        raise WriteFailed(f"{getattr(error, 'filename', None) or folder}: {error.strerror or error}")
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def _merge(source, destination, moved):
    """Move what is under `source` into `destination`, joining directories that already exist."""
    with os.scandir(source) as it:
        entries = sorted(entry.name for entry in it)
    for name in entries:
        src, dst = source / name, destination / name
        if src.is_dir() and not src.is_symlink() and dst.is_dir() and not dst.is_symlink():
            _merge(src, dst, moved)
        elif dst.exists() or dst.is_symlink():
            raise OSError(17, "File exists", str(dst))
        else:
            os.replace(src, dst)
            moved.append(dst)


def _undo(moved):
    for path in reversed(moved):
        try:
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)
            else:
                path.unlink()
        except OSError:
            pass


# --- the command --------------------------------------------------------------------

def sql_rows():
    return {row["Dbtype"]: row for row in knowledge.load("field-sql-types")}


def prepare(folder, check_folder=True):
    """(design result, context) — or raises Incomplete with the design's report already printed."""
    result = design.check(folder)
    if result.exit_code != 0:
        design.show(result)
        raise Incomplete(f"design.py exits {result.exit_code} — {len(result.asks)} value(s) open, "
                         f"{result.conflicts} conflict(s)")
    return result, context.build(result.design, sql_rows())


class Incomplete(Exception):
    pass


def main(argv=None):
    parser = Parser(description="Render a new DGF application from its design and shipped templates.")
    parser.add_argument("--folder", required=True, help="the new application's folder")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="print every target, write nothing")
    mode.add_argument("--check", action="store_true", help="the post-generation check of a generated application")
    parser.add_argument("--verbose", action="store_true", help="trace each file to stderr")
    args = parser.parse_args(argv)
    if args.verbose:
        report.set_verbose()
    folder = Path(args.folder)
    rep = report.Report(str(folder))

    if args.check:
        check = _sibling("check")
        # what check.py needs of this module, by name — the module itself may have been loaded by path
        needs = ("design", "context", "render", "report", "knowledge", "sql_rows", "load_manifest", "plan", "Bad",
                 "exact_exists")
        return check.run(folder, types.SimpleNamespace(**{name: globals()[name] for name in needs}))

    try:
        result, ctx = prepare(folder)
    except Incomplete as error:
        rep.add("SCAFFOLD_DESIGN_INCOMPLETE", str(error))
        return report.render([rep], header="Scaffold generate")
    except ValueError as error:
        rep.add("SCAFFOLD_DESIGN_INCOMPLETE", str(error))
        return report.render([rep], header="Scaffold generate")
    rep.ran("design")

    try:
        data = load_manifest()
        jobs = plan(ctx, data)
        rep.ran("plan")
        files = render_all(ctx, jobs)
        rep.ran("render")
    except Bad as error:
        rep.add("SCAFFOLD_TEMPLATE_MISSING", str(error))
        return report.render([rep], header="Scaffold generate")
    base = Path(result.design["base"]["source"]) if ctx["supply_copy"] else None
    report.debug("generate.plan", "counted", files=len(files), copy=bool(base))

    clashes = [t for t in sorted(files) if any_case_exists(folder, t)]
    if base is not None and any_case_exists(folder, "workspaces/webasm"):
        clashes.append("workspaces/webasm")
    if clashes:
        for target in clashes[:20]:
            rep.add("SCAFFOLD_TARGET_EXISTS", f"{report.one_line(target)} exists; nothing was written")
        rep.ran("targets")
        return report.render([rep], header="Scaffold generate")
    rep.ran("targets")

    if args.dry_run:
        for target in sorted(files):
            print(f"TARGET: {report.one_line(target)}")
        if base is not None:
            print(f"TARGET: workspaces/webasm/ (a copy of the base, {len(base_files(base))} files)")
        return report.render([rep], header="Scaffold generate (dry run)",
                             lines=[f"FOLDER: {report.one_line(folder)}", f"TARGETS: {len(files)}"])

    try:
        count, copied = write(folder, files, base)
    except WriteFailed as error:
        rep.add("SCAFFOLD_WRITE_FAILED", str(error))
        rep.ran("write")
        return report.render([rep], header="Scaffold generate")
    rep.ran("write")
    return report.render([rep], header="Scaffold generate",
                         lines=[f"FOLDER: {report.one_line(folder)}", f"WROTE: {count} files, {copied} copied"])


if __name__ == "__main__":
    raise SystemExit(main())
