#!/usr/bin/env python3
"""doctor.py — is dgf-factory installed correctly, and what can it see?

A structural check of dgf-factory itself, in one of two places:

- an installed project: the root is `.dgf-factory/runtime`, beside the receipt
  `dgf-factory setup` wrote (`.dgf-factory/install.json`, ADR 0029);
- this repository: the root is the package source, where `package.json` is.

It answers installability, not completeness: a correct-but-unfinished tree exits
0, and build progress is INFO that never touches the exit code.

It is a runtime validator — the /dgf-doctor skill calls it, and so does
tools/check-dual-schema-docs.sh. It reads and reports; it never edits.

Sections: 1 install (in a project: every file the receipt lists is there and
unedited, every chosen harness has every skill, and the receipt's version
against the `dgf-factory` CLI on PATH; in this repository: package.json),
2 skill slices (frontmatter YAML-safe), 3 portability (machine paths, DGF
repository paths, runtime paths that do not exist, and relative links that
leave the shipped set — ADR 0030), 4 line endings, 5 validator runtime (lxml
and jsonschema importable — in the project's .venv when it has one —,
scripts/requirements.txt pinned with hashes, every machine-read knowledge table
loads), 6 build progress (INFO only). It stays stdlib-only, so it runs before
the validators' dependencies are installed (ADR 0031 §9); it reports a missing
dependency, and installs nothing.

Sections 1–5 are checks, and all five are required: one that cannot run — no
skills/, no scripts/ — is `NOT RUN` with its reason, never a silent pass. (A
copy without scripts/ is reported so only by another copy's doctor: its own has
no builder, and exits 3.) The summary prints `CHECKS RUN:` and `NOT RUN:` lines.

The output ends with one `dgf-gate-result` block, built by scripts/lib/gate_result.py
(ADR 0022): gate `doctor`; errors in `blockers`; warnings, and a
`not-run-<section>` entry per section that did not run, in `warnings`;
`blocking` only on a fail; `checks_run` naming the sections that ran; and
`suggested_next.command` always null, since a broken install is fixed by
re-running `dgf-factory setup`, never by /dgf-fix (ADR 0022 §8).
There is no `schema_family`, `affected_components` or `affected_processes`: the
doctor reads no estate. The builder is loaded by path from this script's own
tree, never from the root it checks.

Usage:  doctor.py [<root>]
        DEBUG=1 doctor.py            # per-check trace

With no argument the root is resolved from this file's location, never from
the working directory.

Exit codes (contract, see .ai-factory/rules/base.md):
  0  CLEAN     — no findings
  1  BLOCKED   — an installed file is missing, a harness lacks a skill, a slice
                 will not register or has frontmatter YAML reads differently,
                 a shipped file names a DGF repository path, a runtime path
                 that does not exist or a link out of the shipped set, the
                 validator requirements are unpinned, or a knowledge table is
                 malformed
  2  WARNINGS  — it loads, but something needs a human look (an edited
                 installed file, a version that differs from the CLI's,
                 validator dependencies that are not installed), or a section
                 could not run
  3  usage error, or this tree's own scripts/lib/gate_result.py is missing or
     does not load — no block is printed, and a caller reads that as a gate
     that did not run
"""

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

# --- colours (defined once, disabled when not a terminal) --------------------
if sys.stdout.isatty():
    RED = "\033[0;31m"
    YELLOW = "\033[0;33m"
    GREEN = "\033[0;32m"
    BOLD = "\033[1m"
    NC = "\033[0m"
else:
    RED = YELLOW = GREEN = BOLD = NC = ""

# The npm package payload (ADR 0030 §1). `.claude/`, `tools/`, `provenance/`, `tests/`
# and `docs/` are maintainer material and never ship. An installed runtime holds the
# last three; bin/ and cli/ stay in the global package.
SHIPPED_DIRS = ("bin", "cli", "skills", "scripts", "knowledge")

# Where an installed runtime sits in a project, beside the receipt (ADR 0029 §2).
PIPELINE_DIR = ".dgf-factory"
RUNTIME_NAME = "runtime"
RECEIPT_NAME = "install.json"
CLI_NAME = "dgf-factory"

# Built in pieces so this file does not match its own portability check.
_SEP = "/"
ABSOLUTE_PATH_MARKERS = (_SEP + "Users" + _SEP, _SEP + "home" + _SEP, "~" + _SEP)

# A path into the DGF framework repository (ADR 0012). A developer's install has
# no DGF checkout, so a shipped file that names one points at nothing. The folder
# lists are DGF's top-level `src/` and `docs/` entries, read at commit aa1d5c4c2;
# `docs/adr` is left out because this plugin has a `docs/adr` of its own. Built in
# pieces, like the markers above. tools/vendor_schemas.py imports this pattern, so
# there is one definition.
_DGF_SRC = ("Components", "Core", "DGE.Office", "DGF.API", "DGF.Tests", "DGF.UI",
            "PlatformServices", "Plugins", "Tools", "samples", "tests")
_DGF_SRC_FILES = ("Directory.Build.props", "Directory.Packages.props", "global.json")
_DGF_DOCS = ("Components", "Presentations", "Release-notes", "Research", "analysis",
             "schemas", "wiki")
_DGF_MCP_SCHEMAS = ("Json", "XSD", "XmlReference")


def _alternatives(prefix, names, suffix=""):
    return prefix + _SEP + "(?:" + "|".join(re.escape(n) + suffix for n in names) + ")"


# The lookbehind admits a JSON string escape such as `\n` right before the path:
# vendored schemas write "…docs at\n<path>" inside one string.
DGF_PATH_PATTERN = re.compile(
    r"(?:(?<![\w.-])|(?<=\\[nrt]))(?:"
    + _alternatives("src", _DGF_SRC, _SEP) + "|"
    + _alternatives("src", _DGF_SRC_FILES) + "|"
    + _alternatives("docs", _DGF_DOCS, _SEP) + "|"
    + _alternatives("Schemas", _DGF_MCP_SCHEMAS, _SEP)
    + ")"
    + "|_?" + "DotGov" + "Framework" + _SEP
)

# The validators' third-party dependencies (ADR 0015): import name per package.
VALIDATOR_DEPENDENCIES = ("lxml", "jsonschema")
PINNED_REQUIREMENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*==[^\s;\\]+")
REQUIREMENT_HASH = re.compile(r"--hash=sha256:[0-9a-f]{64}")

PACKAGE_NAME = "@andrian-org/dgf-factory"
SEMVER_PATTERN = re.compile(r"\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?\Z")

# Slices the roadmap calls for, in roadmap order. Absent ones are progress, not faults.
EXPECTED_SLICES = ("dgf-doctor", "dgf", "dgf-plan", "dgf-implement", "dgf-verify", "dgf-commit",
                   "dgf-fix", "dgf-evolve", "dgf-component", "dgf-process", "dgf-audit", "dgf-model",
                   "dgf-scaffold")

# A path into the runtime in shipped Markdown: `{{dgf_runtime}}/<path>` in the source,
# `.dgf-factory/runtime/<path>` once setup has rendered it (ADR 0029 §3). The path ends
# at whitespace, a quote, a backtick, `)`, `]` or `§`; one with `<`, `*`, `{`, a `$` or
# an ellipsis is a template.
RUNTIME_TOKEN = "{{" + "dgf_runtime}}"
RENDERED_RUNTIME = PIPELINE_DIR + _SEP + RUNTIME_NAME
_PATH_TAIL = r"(/[^\s'\"`)\]\u00a7]*)?"
TOKEN_PATH = re.compile(re.escape(RUNTIME_TOKEN) + _PATH_TAIL)
RENDERED_PATH = re.compile(r"(?<![\w/.-])" + re.escape(RENDERED_RUNTIME) + _PATH_TAIL)
TEMPLATE_MARKERS = ("<", "*", "{", "$", "\u2026", "...")
# A relative Markdown link: [text](target), not a URL, a mail address or an anchor.
MARKDOWN_LINK = re.compile(r"\]\(([^)\s]+)\)")

# A frontmatter value the flat parser reads as one string, but YAML reads otherwise:
# an unquoted value starting with a flow, anchor, alias, tag, directive, reserved or
# block-scalar indicator, or holding `: ` or ` #`.
YAML_UNSAFE_START = tuple("[{*&!%@`|>")

# The five checks, all required (ADR 0022 §4). Build progress is INFO, not a check.
SECTIONS = ("install", "skill-slices", "portability", "line-endings", "validator-runtime")
GATE_ID = "doctor"
BUILDER_API = ("GateContractError", "build", "entry", "not_run", "render")

FINDINGS = []
INFOS = []
CHECKS_RUN = []
NOT_RUN = []  # (section id, reason) pairs


def fail(code, message):
    """The single bail-out path. Errors go to stderr, never to the report."""
    print(message, file=sys.stderr)
    raise SystemExit(code)


def error(finding_id, rel_path, summary):
    FINDINGS.append({"id": finding_id, "severity": "error", "file": rel_path, "summary": summary})
    print(f"{RED}ERROR{NC} {summary}")


def warn(finding_id, rel_path, summary):
    FINDINGS.append({"id": finding_id, "severity": "warning", "file": rel_path, "summary": summary})
    print(f"{YELLOW}WARN{NC}  {summary}")


def info(summary):
    INFOS.append(summary)
    print(f"INFO  {summary}")


def trace(message):
    if os.environ.get("DEBUG") or os.environ.get("LOG_LEVEL") == "debug":
        print(f"  · {message}")


def ran(section_id):
    if section_id not in CHECKS_RUN:
        CHECKS_RUN.append(section_id)


def not_run(section_id, reason):
    """A required section that could not run — reported, never passed silently."""
    NOT_RUN.append((section_id, reason))
    trace(f"NOT RUN: {section_id} ({reason})")


def section(title):
    print(f"\n{BOLD}{title}{NC}")


def relpath(root, path):
    try:
        return str(Path(path).relative_to(root))
    except ValueError:
        return str(path)


def json_type_name(value):
    """JSON's name for a decoded value — the report is about a JSON file, not Python."""
    names = {type(None): "null", bool: "boolean", int: "number",
             float: "number", str: "string", list: "array", dict: "object"}
    return names.get(type(value), type(value).__name__)


def read_text(path):
    """Decoded file contents, or None when the file is binary or unreadable."""
    try:
        return path.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def is_bytecode(path):
    """Python writes these next to scripts it runs; they are never shipped content."""
    return "__pycache__" in path.parts or path.suffix == ".pyc"


def is_ignored(path):
    """Never shipped: the project's .venv/, and IDE build output in the scaffold's templates."""
    return ".venv" in path.parts or ("templates" in path.parts and ("obj" in path.parts or "bin" in path.parts)
                                      and "solution" in path.parts)


def harness_files(root):
    """In a project: the rendered SKILL.md files the receipt lists outside the runtime, project-relative."""
    project = project_of(root)
    if project is None:
        return []
    module = load_lib_module(root, "install_receipt")
    try:
        data = module.load(project) if module else None
    except module.ReceiptError:
        return []
    files = (data or {}).get("files") or {}
    return sorted(rel for rel, entry in files.items()
                  if isinstance(entry, dict) and entry.get("owner") != RUNTIME_NAME and (project / rel).is_file())


def shipped_files(root):
    """(path, display path) for every shipped file, in a stable order (ADR 0030 §1).

    Bytecode is skipped: running a validator writes scripts/lib/__pycache__ on a
    contributor's tree and on an installed copy alike, and marshalled bytecode can
    hold the bytes of a CRLF or a path.
    """
    skipped = 0
    for name in SHIPPED_DIRS:
        base = root / name
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            if is_bytecode(path) or is_ignored(path):
                skipped += 1
                continue
            yield path, relpath(root, path)
    project = project_of(root)
    for rel in harness_files(root):
        yield project / rel, rel
    trace(f"skipped {skipped} bytecode or ignored file(s)")


def parse_frontmatter(text):
    """The flat key/value block between the leading `---` fences.

    Deliberately not a YAML parser: the SKILL.md contract is a handful of flat
    scalar keys, and depending on pyyaml would put a third-party import in a
    validator that must run anywhere.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    fields = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return fields
        key, sep, value = line.partition(":")
        if sep and not key.startswith((" ", "\t", "#")):
            fields[key.strip()] = value.strip()
    return None  # unterminated block


# --- 1. install --------------------------------------------------------------

def project_of(root):
    """The project an installed runtime belongs to, or None for the package source.

    An installed runtime is `<project>/.dgf-factory/runtime`, beside the receipt.
    """
    if root.name == RUNTIME_NAME and root.parent.name == PIPELINE_DIR and (root.parent / RECEIPT_NAME).is_file():
        return root.parent.parent
    return None


def check_install(root):
    section("1. Install")
    project = project_of(root)
    ran("install")
    if project is None:
        check_package(root)
    else:
        check_receipt(root, project)


def check_package(root):
    """The package source: package.json names the package, a semver version and the bin."""
    rel = "package.json"
    path = root / rel
    trace(f"package: {path}")
    if not path.is_file():
        error("PACKAGE_MISSING", rel, f"{rel} not found — neither an installed runtime nor the package source")
        return
    text = read_text(path)
    try:
        package = json.loads(text) if text is not None else None
    except json.JSONDecodeError as exc:
        error("PACKAGE_UNPARSEABLE", rel, f"{rel} is not valid JSON: {exc}")
        return
    if not isinstance(package, dict):
        error("PACKAGE_UNPARSEABLE", rel, f"{rel} must contain a JSON object, not {json_type_name(package)}")
        return
    if package.get("name") != PACKAGE_NAME:
        error("PACKAGE_NAME", rel, f"{rel} name is `{package.get('name')}`, not `{PACKAGE_NAME}`")
    if not SEMVER_PATTERN.match(str(package.get("version", ""))):
        error("PACKAGE_VERSION_INVALID", rel, f"{rel} version `{package.get('version')}` is not semver")
    bin_path = (package.get("bin") or {}).get(CLI_NAME) if isinstance(package.get("bin"), dict) else None
    if not bin_path or not (root / bin_path).is_file():
        error("PACKAGE_BIN_MISSING", rel, f"{rel} declares no `bin.{CLI_NAME}` that exists")
    info(f"package source — {package.get('name')} {package.get('version')}")


def load_receipt(root, project):
    module = load_lib_module(root, "install_receipt")
    if module is None:
        error("INSTALL_RECEIPT_UNREADABLE", f"scripts{_SEP}lib{_SEP}install_receipt.py",
              "scripts/lib/install_receipt.py is missing — re-run `dgf-factory setup`")
        return None, None
    try:
        data = module.load(project)
    except module.ReceiptError as exc:
        error("INSTALL_RECEIPT_UNREADABLE", f"{PIPELINE_DIR}{_SEP}{RECEIPT_NAME}", f"{exc} — re-run `dgf-factory setup`")
        return module, None
    return module, data


def check_receipt(root, project):
    """Every file setup recorded is there and unedited; every chosen harness has every skill."""
    module, data = load_receipt(root, project)
    if data is None:
        return
    files = data.get("files") if isinstance(data.get("files"), dict) else {}
    for rel, entry in sorted(files.items()):
        path = project / rel
        if not path.is_file():
            error("INSTALL_FILE_MISSING", rel, f"{rel} is in the receipt but not on disk — re-run `dgf-factory setup`")
            continue
        recorded = entry.get("installedHash") if isinstance(entry, dict) else None
        if module.hash_file(path) != recorded:
            warn("INSTALL_FILE_EDITED", rel, f"{rel} was edited since setup wrote it — setup keeps it and will not update it")
        trace(f"[install] {rel} checked")
    check_harness_skills(root, data, files)
    check_version(data)
    info(f"installed in {project} — {len(files)} file(s) recorded")


def check_harness_skills(root, data, files):
    skills = sorted(path.name for path in (root / "skills").iterdir() if (path / "SKILL.md").is_file()) \
        if (root / "skills").is_dir() else []
    for harness in data.get("harnesses") or []:
        if not isinstance(harness, dict) or not harness.get("selected"):
            continue
        hid = harness.get("id")
        have = {Path(rel).parent.name for rel, entry in files.items()
                if isinstance(entry, dict) and entry.get("owner") == hid and rel.endswith(_SEP + "SKILL.md")}
        absent = [name for name in skills if name not in have]
        if absent:
            error("INSTALL_HARNESS_INCOMPLETE", f"{PIPELINE_DIR}{_SEP}{RECEIPT_NAME}",
                  f"{hid} has no {', '.join(absent)} — re-run `dgf-factory setup --harness {hid}`")
        else:
            info(f"{hid} — all {len(skills)} skills installed")


def check_version(data):
    """The receipt's version against the CLI's. A teammate who cloned has no CLI, and needs none."""
    cli = shutil.which(CLI_NAME)
    if cli is None:
        info(f"`{CLI_NAME}` is not on PATH — the installed version ({data.get('version')}) is not compared")
        return
    try:
        done = subprocess.run([cli, "--version"], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError) as exc:
        info(f"`{CLI_NAME} --version` did not answer ({exc}) — the version is not compared")
        return
    current = done.stdout.strip()
    trace(f"[install] receipt version {data.get('version')}, CLI {current}")
    if done.returncode == 0 and current and current != data.get("version"):
        warn("INSTALL_VERSION_DRIFT", f"{PIPELINE_DIR}{_SEP}{RECEIPT_NAME}",
             f"installed by dgf-factory {data.get('version')}, and the CLI on PATH is {current} — "
             f"run `dgf-factory setup` to update")


# --- 2. skill slices ---------------------------------------------------------

def check_skill_slices(root):
    section("2. Skill slices")
    skills_dir = root / "skills"
    if not skills_dir.is_dir():
        not_run("skill-slices", f"no skills{_SEP} directory")
        return
    ran("skill-slices")

    slices = sorted(path for path in skills_dir.iterdir() if path.is_dir())
    if not slices:
        trace("skills/ is empty")
        return

    for slice_dir in slices:
        check_skill_slice(root, slice_dir)


def check_skill_slice(root, slice_dir):
    skill_file = slice_dir / "SKILL.md"
    rel = relpath(root, skill_file)
    trace(f"slice: {rel}")

    if not skill_file.is_file():
        error("SKILL_FILE_MISSING", relpath(root, slice_dir),
              f"{slice_dir.name}{_SEP} has no SKILL.md — the skill will not register")
        return

    text = read_text(skill_file)
    fields = parse_frontmatter(text) if text is not None else None
    if fields is None:
        error("SKILL_FRONTMATTER_MISSING", rel, f"{rel} has no closed YAML frontmatter block")
        return

    check_frontmatter_yaml(rel, fields)
    name = fields.get("name", "")
    if name != slice_dir.name:
        error("SKILL_NAME_MISMATCH", rel,
              f"{rel} name `{name}` does not match its directory `{slice_dir.name}`")
    if not fields.get("description"):
        error("SKILL_DESCRIPTION_MISSING", rel, f"{rel} has an empty `description`")
    if not fields.get("allowed-tools"):
        error("SKILL_TOOLS_MISSING", rel, f"{rel} declares no `allowed-tools`")


def yaml_unsafe(value):
    """Why YAML would not read `value` as the plain string the flat parser sees, or None."""
    if not value:
        return None
    if value[0] in "\"'":
        return None if len(value) > 1 and value.endswith(value[0]) else "opens a quote it never closes"
    if value.startswith("- "):
        return "starts with `- `, which YAML reads as a list item"
    if value.endswith(":"):
        return "ends with `:`, which YAML reads as a mapping key"
    if value.startswith(YAML_UNSAFE_START):
        return f"starts with `{value[0]}`"
    if ": " in value:
        return "contains `: `"
    if " #" in value:
        return "contains ` #`, which YAML reads as a comment"
    return None


def check_frontmatter_yaml(rel, fields):
    """Claude Code reads the block as YAML; the doctor reads it flat. They must agree."""
    for key, value in fields.items():
        why = yaml_unsafe(value)
        trace(f"{rel}: `{key}` yaml-safe={why is None}")
        if why:
            error("SKILL_FRONTMATTER_YAML", rel,
                  f"{rel} `{key}` {why} — YAML reads it differently or not at all, so the skill may not "
                  "load; quote the value")


# --- 3. portability ----------------------------------------------------------

def check_portability(root):
    section("3. Portability")
    ran("portability")
    project = project_of(root)
    for path, rel in shipped_files(root):
        text = read_text(path)
        if text is None:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            marker = next((m for m in ABSOLUTE_PATH_MARKERS if m in line), None)
            if marker:
                warn("ABSOLUTE_PATH", rel,
                     f"{rel}:{lineno} contains `{marker}` — breaks for other users")
            match = DGF_PATH_PATTERN.search(line)
            if match:
                error("DGF_PATH", rel,
                      f"{rel}:{lineno} names DGF repository path `{match.group(0)}…` — "
                      "a developer's install has no DGF checkout (ADR 0030)")
            if path.suffix == ".md":
                check_runtime_paths(root, project, rel, lineno, line)
                check_links(root, project, path, rel, lineno, line)
    trace("scanned shipped files for machine-specific, DGF repository and dangling runtime paths, and links")


def exists_exact(root, rel):
    """True when every segment of `rel` exists under `root` in exactly this case.

    Path.exists() matches regardless of case on APFS and NTFS; the tool runs on
    Linux too, where a wrong-case path does not resolve.
    """
    current = Path(root)
    for part in [p for p in rel.split(_SEP) if p]:
        try:
            names = os.listdir(current)
        except OSError:
            return False
        if part not in names:
            return False
        current = current / part
    return True


def check_runtime_paths(root, project, rel, lineno, line):
    """Every runtime path a shipped Markdown file cites must exist: `{{dgf_runtime}}/<path>`
    under the root, and — in a project — `.dgf-factory/runtime/<path>` under the project."""
    pairs = [(TOKEN_PATH, RUNTIME_TOKEN, root)]
    if project is not None:
        pairs.append((RENDERED_PATH, RENDERED_RUNTIME, root))
    for pattern, token, base in pairs:
        for match in pattern.finditer(line):
            target = (match.group(1) or "").rstrip(".,;:")
            if any(marker in target for marker in TEMPLATE_MARKERS):
                trace(f"{rel}:{lineno} template `{token}{target}` skipped")
                continue
            exists = exists_exact(base, target.lstrip(_SEP))
            trace(f"{rel}:{lineno} `{token}{target}` exists={exists}")
            if not exists:
                error("RUNTIME_PATH_DANGLING", rel,
                      f"{rel}:{lineno} cites `{token}{target}`, which does not exist in the runtime")


def shipped_roots(root, project):
    """The folders a link may land in: the shipped directories, and in a project the
    harness skill folders too."""
    roots = [(root / name).resolve() for name in SHIPPED_DIRS]
    return roots


def check_links(root, project, path, rel, lineno, line):
    """A relative Markdown link must resolve inside the shipped set (ADR 0030 §3)."""
    for match in MARKDOWN_LINK.finditer(line):
        target = match.group(1).split("#", 1)[0]
        if not target or re.match(r"[a-z][a-z0-9+.-]*:", target, re.I) or target.startswith(_SEP):
            continue
        resolved = (path.parent / target).resolve()
        inside = any(resolved == base or base in resolved.parents for base in shipped_roots(root, project))
        trace(f"{rel}:{lineno} link `{target}` inside={inside}")
        if not inside:
            error("LINK_LEAVES_SHIPPED", rel,
                  f"{rel}:{lineno} links `{target}`, outside what is installed — cite the knowledge file or "
                  "DGF docs MCP page instead, or name the document in plain text (ADR 0030 §3)")


# --- 4. line endings ---------------------------------------------------------

def check_line_endings(root):
    section("4. Line endings")
    ran("line-endings")
    for path, rel in shipped_files(root):
        try:
            if b"\r\n" in path.read_bytes():
                warn("CRLF", rel, f"{rel} has CRLF line endings — breaks shebangs and heredocs")
        except OSError:
            continue
    trace("scanned shipped files for CRLF")


# --- 5. validator runtime ----------------------------------------------------

def check_validator_runtime(root):
    section("5. Validator runtime")
    scripts_dir = root / "scripts"
    if not scripts_dir.is_dir():
        not_run("validator-runtime", f"no scripts{_SEP} directory — no validators to check")
        return
    ran("validator-runtime")
    check_validator_dependencies(root)
    check_requirement_pins(root)
    check_knowledge_tables(root)


def install_command(root):
    """lib/deps.py's command, restated: the doctor is stdlib-only and imports nothing from lib/."""
    requirements = root / "scripts" / "requirements.txt"
    if (root.parent / "install.json").is_file():
        venv = root / ".venv"
        python = venv / "Scripts" / "python.exe" if os.name == "nt" else venv / "bin" / "python"
        return (f'python3 -m venv "{venv}" && "{python}" -m pip install --require-hashes -r "{requirements}"'
                f" — or re-run `dgf-factory setup`")
    user = "" if sys.prefix != sys.base_prefix else " --user"
    return f'python3 -m pip install{user} --require-hashes -r "{requirements}"'


def venv_python(root):
    venv = root / ".venv"
    python = venv / "Scripts" / "python.exe" if os.name == "nt" else venv / "bin" / "python"
    return python if python.is_file() else None


def missing_dependencies(root):
    """The packages that do not import — in the project's .venv when it has one, since every
    script switches to it (ADR 0031 §7), else in this interpreter."""
    python = venv_python(root)
    if python is None:
        return [name for name in VALIDATOR_DEPENDENCIES if importlib.util.find_spec(name) is None], sys.executable
    absent = []
    for name in VALIDATOR_DEPENDENCIES:
        try:
            done = subprocess.run([str(python), "-c", f"import {name}"], capture_output=True, timeout=60)
        except (OSError, subprocess.SubprocessError):
            done = None
        if done is None or done.returncode != 0:
            absent.append(name)
    return absent, str(python)


def check_validator_dependencies(root):
    absent, python = missing_dependencies(root)
    trace(f"dependency probe: missing={','.join(absent) or 'none'} python={python}")
    if absent:
        warn("VALIDATOR_DEPS_MISSING", f"scripts{_SEP}requirements.txt",
             f"{', '.join(absent)} not installed — the validators exit 3 until they are. "
             f"Install with: {install_command(root)}")
        return
    info("validator dependencies — lxml and jsonschema import")


def requirement_entries(text):
    """Logical requirement lines: continuations joined, comments and blanks dropped."""
    entries, current = [], ""
    for line in text.splitlines():
        stripped = line.strip()
        if not current and (not stripped or stripped.startswith("#")):
            continue
        current += " " + stripped.rstrip("\\").strip()
        if not stripped.endswith("\\"):
            entries.append(current.strip())
            current = ""
    if current:
        entries.append(current.strip())
    return entries


def check_requirement_pins(root):
    rel = f"scripts{_SEP}requirements.txt"
    path = root / "scripts" / "requirements.txt"
    if not path.is_file():
        error("REQUIREMENTS_UNPINNED", rel, f"{rel} is missing — the validators' dependencies are unpinned")
        return
    text = read_text(path)
    if text is None:
        error("REQUIREMENTS_UNPINNED", rel, f"{rel} is not readable as UTF-8 text")
        return
    entries = requirement_entries(text)
    trace(f"{rel}: {len(entries)} requirement(s)")
    for entry in entries:
        name = entry.split()[0]
        if not PINNED_REQUIREMENT.match(entry):
            error("REQUIREMENTS_UNPINNED", rel, f"{rel}: `{name}` is not pinned as name==version")
        elif not REQUIREMENT_HASH.search(entry):
            error("REQUIREMENTS_UNPINNED", rel, f"{rel}: `{name}` has no --hash=sha256")


def load_lib_module(root, name):
    """scripts/lib/<name>.py under `root`, loaded by path — it imports nothing from its package.

    None when the file is absent. knowledge.py and gate_result.py are both
    stdlib-only for this reason: a relative import cannot resolve here.
    """
    path = root / "scripts" / "lib" / f"{name}.py"
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location(f"dgf_doctor_{name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_knowledge_tables(root):
    try:
        module = load_lib_module(root, "knowledge")
    except (OSError, SyntaxError, ImportError) as exc:
        error("KNOWLEDGE_TABLE", f"scripts{_SEP}lib{_SEP}knowledge.py",
              f"scripts{_SEP}lib{_SEP}knowledge.py cannot be loaded: {exc}")
        return
    if module is None:
        trace("no scripts/lib/knowledge.py — no machine-read tables to check")
        return
    for table_id in module.TABLES:
        try:
            rows = module.load(table_id, root / "knowledge")
        except module.KnowledgeTableError as exc:
            error("KNOWLEDGE_TABLE", f"knowledge{_SEP}{module.TABLES[table_id][0]}", str(exc))
            continue
        trace(f"table {table_id}: {len(rows)} row(s)")
    info(f"machine-read knowledge tables — {len(module.TABLES)} checked")


# --- 6. build progress (INFO only — never affects the exit code) -------------

def report_build_progress(root):
    section("6. Build progress")
    for name in ("knowledge", "scripts"):
        state = "present" if (root / name).is_dir() else "not yet built"
        info(f"{name}{_SEP} — {state}")

    skills_dir = root / "skills"
    for slice_name in EXPECTED_SLICES:
        state = "present" if (skills_dir / slice_name).is_dir() else "not yet built"
        info(f"skills{_SEP}{slice_name}{_SEP} — {state}")
    trace("build progress is informational; it does not affect the exit code")


# --- reporting ---------------------------------------------------------------

def load_gate_builder():
    """scripts/lib/gate_result.py from this script's own tree — never from the root it checks.

    The builder is the doctor's machinery, not the thing checked. When it is
    missing or does not load, exit 3 with no block: a caller reads a missing
    block as a gate that did not run.
    """
    own_root = Path(__file__).resolve().parents[3]
    path = own_root / "scripts" / "lib" / "gate_result.py"
    try:
        module = load_lib_module(own_root, "gate_result")
    except Exception as exc:  # whatever the file raises while it loads, the builder did not load
        fail(3, f"{path} cannot be loaded: {exc!r} — the gate block cannot be built; re-run `dgf-factory setup`")
    if module is None:
        fail(3, f"{path} is missing — the gate block cannot be built; re-run `dgf-factory setup`")
    absent = [name for name in BUILDER_API if not hasattr(module, name)]
    if absent:
        fail(3, f"{path} has no {', '.join(absent)} — the gate block cannot be built; re-run `dgf-factory setup`")
    trace(f"gate: loaded {path}")
    return module


def gate_block(gate, status, errors):
    """The machine-readable verdict, built by gate_result.py. Emitted last; nothing may follow it.

    `schema_family`, `affected_components` and `affected_processes` are left
    out: this gate reads no DGF configuration, and a field it never computed
    must not read as "none" (ADR 0022 §7).
    """
    blockers = [gate.entry(f["id"], f["severity"], f["summary"], file=f["file"])
                for f in FINDINGS if f["severity"] == "error"]
    warnings = [gate.entry(f["id"], f["severity"], f["summary"], file=f["file"])
                for f in FINDINGS if f["severity"] == "warning"]
    warnings += [gate.not_run(section_id, reason) for section_id, reason in NOT_RUN]
    if status == "fail":
        reason = f"{errors} blocking finding(s) — re-run `dgf-factory setup`, or fix them by hand, and re-run the doctor"
    elif status == "warn":
        reason = f"{len(warnings)} warning(s) — dgf-factory works but is not clean; read them, fix by hand, and re-run"
    else:
        reason = "no findings; nothing to fix"
    try:
        payload = gate.build(GATE_ID, blockers, warnings, None, reason, checks_run=CHECKS_RUN, required=SECTIONS)
    except gate.GateContractError as exc:
        fail(3, f"the doctor built a contradictory gate block: {exc}")
    print()
    print(gate.render(payload))


def report(root):
    gate = load_gate_builder()
    errors = sum(1 for f in FINDINGS if f["severity"] == "error")
    warnings = sum(1 for f in FINDINGS if f["severity"] == "warning")

    section("Summary")
    print(f"Root:     {root}")
    print(f"CHECKS RUN: {', '.join(CHECKS_RUN) if CHECKS_RUN else '(none)'}")
    for section_id, reason in NOT_RUN:
        print(f"NOT RUN: {section_id} ({reason})")
    print(f"Errors:   {errors}")
    print(f"Warnings: {warnings}")
    print(f"Info:     {len(INFOS)}")

    if errors:
        print(f"\n{RED}BLOCKED{NC}")
        code, status = 1, "fail"
    elif warnings or NOT_RUN:
        print(f"\n{YELLOW}WARNINGS{NC}")
        code, status = 2, "warn"
    else:
        print(f"\n{GREEN}CLEAN{NC}")
        code, status = 0, "pass"

    gate_block(gate, status, errors)
    return code


def resolve_root(argv):
    if len(argv) > 1:
        fail(3, f"Usage: {Path(argv[0]).name} [<root>]   (DEBUG=1 for a per-check trace)")
    if not argv:
        # skills/<slice>/scripts/doctor.py — never the working directory.
        return Path(__file__).resolve().parents[3]

    root = Path(argv[0]).expanduser().resolve()
    if not root.is_dir():
        fail(3, f"Not a directory: {root}")
    if not (root / "skills").is_dir():
        fail(3, f"Not a dgf-factory root (no skills{_SEP}): {root}")
    return root


def main(argv):
    root = resolve_root(argv[1:])

    print(f"{BOLD}dgf-factory install check{NC}")
    print(f"Root: {root}")

    check_install(root)
    check_skill_slices(root)
    check_portability(root)
    check_line_endings(root)
    check_validator_runtime(root)
    report_build_progress(root)

    return report(root)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
