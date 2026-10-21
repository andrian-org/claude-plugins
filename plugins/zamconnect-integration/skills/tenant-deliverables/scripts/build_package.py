#!/usr/bin/env python3
"""Build a tenant's whole delivery package in one command.

Collapses build -> swagger export -> gateway prefix -> folder layout -> archive -> one DOCX per
role -> Postman collection -> gates into a single call, and prints a report short enough to read.
Everything it does is step 4 through 9 of the skill; the judgement call the skill reserves for a
human - which endpoints are Consume - is an input here, never a guess.

    python build_package.py ZDD --route zdd --version 1.0 --roles tenant,consumer

The package lands in src/Tenants/<Tenant>/Deliverables/ itself, with the five role folders
directly inside it - or in src/VirtualTenants/<Tenant>/Deliverables/ for a virtual tenant, which
has no project to build, so its assembled document comes in through --from-swagger.

For a tenant that both consumes and provides, pass --provide-paths so the Tenant document gets
both sections and the (c)/(p) documents become projections of it:

    --provide-paths /t/wcf/employers

Every schema and property must have a description before anything is written (schema_descriptions.py):
from the code's /// comments, else src/Tenants/<Tenant>/Swagger/schema-descriptions.json. The run
stops with exit code 3 and a missing-descriptions.json when any is still missing; fill the catalogue
and re-run with --skip-build.

The Document History is carried forward from the current (t) document: a higher --version adds
one row and needs --history-description, the same version keeps the rows, a lower one is refused.
A tenant whose Program.cs declares several Swagger documents needs --swagger-doc <name>. The
repo's own postman collections/<Tenant>.postman_collection.json is replaced only with
--update-working-collection.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
HISTORY_HEADER = ["Description", "Author", "Version", "Date"]

ROLES = {
    "tenant":   ("(t)", "Tenant",   "Tenant",   None),
    "consumer": ("(c)", "Consumer", "Consumer", "Consume"),
    "provider": ("(p)", "Provider", "Provider", "Provide"),
}
LAYOUT = ("Consumer", "Provider", "Tenant", "Integration Requests", "Archive")


def find_repo_root(start: Path) -> Path:
    for d in [start, *start.parents]:
        if (d / "src" / "ZamConnect.sln").exists():
            return d
    sys.exit(f"!! no src/ZamConnect.sln at or above {start}")


def load_sibling(name: str):
    """A module next to this script, loaded by path so it works under `python -I`, which keeps
    the script's own folder off sys.path."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(f"{name}.py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def run(cmd, cwd=None, env=None, label=""):
    result = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True)
    if result.returncode != 0:
        tail = (result.stderr or result.stdout).strip().splitlines()[-25:]
        sys.exit(f"!! {label or cmd[0]} failed ({result.returncode}):\n" + "\n".join(tail))
    return result.stdout


def version_key(v: str) -> tuple[int, ...]:
    return tuple(int(n) for n in re.findall(r"\d+", v))


def read_history(path: Path) -> list[dict]:
    """The Document History rows of a rendered specification, read from the package itself."""
    root = ET.fromstring(zipfile.ZipFile(path).read("word/document.xml"))
    for tbl in root.iter(W + "tbl"):
        rows = [["".join(t.text or "" for t in tc.iter(W + "t")).strip("\xa0 ")
                 for tc in tr.findall(W + "tc")] for tr in tbl.iter(W + "tr")]
        if rows and rows[0][:4] == HISTORY_HEADER:
            return [dict(zip(("description", "author", "version", "date"), r[:4]))
                    for r in rows[1:] if len(r) >= 4 and any(r[:4])]
    return []


def decide_history(pkg: Path, tenant: str, version: str, description: str | None,
                   author: str, today: str, log: list[str]) -> list[dict]:
    """Carry the Document History forward from the current (t) document, before it is archived.

    No previous document: one row, "Originally drafted". A new version: the old rows plus one
    row with --history-description, which is then required. The same version: the rows as they
    are. A lower version: refused, because it would put the history out of order.
    """
    current = sorted((pkg / "Tenant").glob(f"{tenant} (t) API Spec*.docx"),
                     key=lambda p: p.stat().st_mtime)
    rows = read_history(current[-1]) if current else []
    if not rows:
        if current:
            log.append(f"history: {current[-1].name} has no Document History rows; starting over")
        if description:
            log.append("history: no previous document, so --history-description is ignored")
        log.append("history: one row, Originally drafted")
        return [{"description": "Originally drafted", "author": author, "version": version,
                 "date": today}]

    last = rows[-1]["version"]
    if version_key(version) < version_key(last):
        sys.exit(f"!! --version {version} is lower than {last}, the last Document History row of "
                 f"{current[-1].name}; a history never goes back")
    if version_key(version) == version_key(last):
        if description:
            log.append(f"history: version {version} unchanged, so --history-description is ignored")
        log.append(f"history: version {version} unchanged, {len(rows)} row(s) kept from "
                   f"{current[-1].name}")
        return rows
    if not description:
        sys.exit(f"!! --version {version} follows {last} in {current[-1].name}: pass "
                 f"--history-description with what changed in this revision")
    log.append(f"history: {len(rows)} row(s) carried forward from {current[-1].name}, "
               f"plus {version} \"{description}\"")
    return rows + [{"description": description, "author": author, "version": version,
                    "date": today}]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("tenant")
    ap.add_argument("--route", default=None, help="gateway route without /t/; default: tenant lowercased")
    ap.add_argument("--version", default="1.0")
    ap.add_argument("--roles", default="tenant,consumer")
    ap.add_argument("--provide-paths", nargs="*", default=[],
                    help="OpenAPI paths served by this tenant's own institution; every other "
                         "path is Consume. Read from the client each module injects")
    ap.add_argument("--author", default="dotGov Solutions LLC")
    ap.add_argument("--history-description", default=None,
                    help="what this revision changed; required when --version is higher than the "
                         "last Document History row of the current (t) document, ignored otherwise")
    ap.add_argument("--swagger-doc", default=None,
                    help="the SwaggerDoc(\"<name>\") to export; required when Program.cs declares "
                         "several. Default: the only one declared, else v1")
    ap.add_argument("--repo-root", default=None)
    ap.add_argument("--out", default=None, help="override the Deliverables directory")
    ap.add_argument("--skip-build", action="store_true",
                    help="reuse the swagger.json already in the tenant's bin folder")
    ap.add_argument("--from-swagger", default=None,
                    help="use this OpenAPI document instead of building the tenant - how a virtual "
                         "tenant's document, assembled from its host, comes in")
    ap.add_argument("--update-working-collection", action="store_true",
                    help="also overwrite the repo's own postman collections/<Tenant>.postman_"
                         "collection.json, which is tracked and may be hand-maintained. Off by "
                         "default: the collection is written to Tenant/ only")
    args = ap.parse_args()

    root = Path(args.repo_root).resolve() if args.repo_root else find_repo_root(Path.cwd())
    tenant = args.tenant
    route = (args.route or tenant.lower()).strip("/")
    # The renderers ship alongside this script, in the plugin. They began as the ZamConnect
    # repo's own `.claude/skills/api-spec-sync` and were copied out so a tenant's deliverables
    # can be rebuilt without the target repository carrying the tooling; that repo's copy is
    # unchanged and still serves `/api-spec-sync`.
    scripts = Path(__file__).parent
    if not (scripts / "openapi_to_docx.py").exists():
        sys.exit(f"!! renderers not found alongside this script at {scripts}")

    roles = [r.strip().lower() for r in args.roles.split(",") if r.strip()]
    bad = [r for r in roles if r not in ROLES]
    if bad:
        sys.exit(f"!! unknown role(s) {bad}; choose from {list(ROLES)}")
    if "tenant" not in roles:
        sys.exit("!! the Tenant document is the complete one and is always rendered")

    tdir = root / "src" / "Tenants" / tenant
    vdir = root / "src" / "VirtualTenants" / tenant
    # No project to build: a virtual tenant (conventions C11), whose package lives in src/VirtualTenants.
    virtual = not any(tdir.glob("*.csproj"))
    bin_dir = tdir / "bin" / "Debug" / "net10.0"
    swagger = bin_dir / "swagger.json"
    log: list[str] = []
    building = not args.from_swagger and not virtual and not args.skip_build

    # --- 0. checks that must stop the run before anything is built, moved or written ----------
    swagger_doc = None
    if building:
        # Every document, not the first: GOVZM declares 12, and the first (dataExchange) holds
        # none of the shared /eservices routes.
        program = tdir / "Program.cs"
        docs = re.findall(r'SwaggerDoc\(\s*"([^"]+)"', program.read_text(encoding="utf-8")) \
            if program.exists() else []
        docs = list(dict.fromkeys(docs))
        if not docs:
            docs = ["v1"]
        if args.swagger_doc:
            if args.swagger_doc not in docs:
                sys.exit(f"!! --swagger-doc {args.swagger_doc} is not declared in {tenant}/Program.cs; "
                         f"its SwaggerDoc names are: {', '.join(docs)}")
            swagger_doc = args.swagger_doc
        elif len(docs) > 1:
            sys.exit(f"!! {tenant}/Program.cs declares {len(docs)} Swagger documents; pass "
                     f"--swagger-doc with one of: {', '.join(docs)}")
        else:
            swagger_doc = docs[0]

    pkg = Path(args.out).resolve() if args.out else (vdir if virtual else tdir) / "Deliverables"
    today = datetime.now().strftime("%B %d, %Y").replace(" 0", " ")
    history = decide_history(pkg, tenant, args.version, args.history_description, args.author,
                             today, log)

    # --- 1. build and export -----------------------------------------------------------------
    if args.from_swagger:
        # Work on a copy: the gateway prefix is applied in place.
        bin_dir = Path(tempfile.mkdtemp(prefix=f"{tenant}-spec-"))
        swagger = bin_dir / "swagger.json"
        shutil.copyfile(args.from_swagger, swagger)
        log.append(f"took the OpenAPI document from {args.from_swagger}")
    elif virtual:
        sys.exit(f"!! {tenant} is a virtual tenant with no project to build - assemble its document "
                 f"from the host (skill step 4) and pass --from-swagger")
    elif not args.skip_build:
        run(["dotnet", "build", str(tdir / f"{tenant}.csproj"), "-c", "Debug", "-v", "q", "--nologo"],
            label="dotnet build")
        # Both of these matter and both fail confusingly: the content root comes from the working
        # directory, and the base appsettings ships unsubstituted __Token__ URLs that only the
        # Development layer replaces with something Uri can parse.
        env = {**os.environ, "ASPNETCORE_ENVIRONMENT": "Development"}
        run(["dotnet", "tool", "run", "swagger", "tofile", "--output", "swagger.json",
             f"{tenant}.dll", swagger_doc], cwd=bin_dir, env=env, label="swagger tofile")
        log.append(f"built and exported swagger.json from Swagger document \"{swagger_doc}\"")
    elif not swagger.exists():
        sys.exit(f"!! --skip-build but no {swagger}")
    else:
        log.append(f"reused {swagger.name} from the last export"
                   + (" (--swagger-doc is ignored with --skip-build)" if args.swagger_doc else ""))

    run([sys.executable, str(scripts / "apply_gateway_route.py"), str(swagger), "--route", route,
         "--version", args.version], label="apply_gateway_route.py")

    spec = json.loads(swagger.read_text(encoding="utf-8"))
    paths = list(spec.get("paths", {}))
    log.append(f"{len(paths)} path(s) prefixed /t/{route}")

    # --- 2. the Consume/Provide split ---------------------------------------------------------
    # Matched without regard to case: [controller] keeps the class casing in the export (/Hub/),
    # and routing ignores case, so /t/pqps/hub/pesticides names the same endpoint. Each one is
    # resolved to the exported path, which is what the sections and the documents carry.
    by_case: dict[str, list[str]] = {}
    for p in paths:
        by_case.setdefault(p.lower(), []).append(p)
    provide: set[str] = set()
    unknown, ambiguous = [], []
    for given in args.provide_paths:
        found = by_case.get(given.lower(), [])
        if not found:
            unknown.append(given)
        elif len(found) > 1:
            ambiguous.append(f"{given} -> {found}")
        else:
            provide.add(found[0])
            if found[0] != given:
                log.append(f"--provide-paths {given} resolved to {found[0]}")
    if unknown:
        sys.exit(f"!! --provide-paths names path(s) not in the document: {sorted(unknown)}")
    if ambiguous:
        sys.exit(f"!! --provide-paths matches paths that differ only by case: {ambiguous}; "
                 f"the document has to be fixed at the source")
    sections = {p: ("Provide" if p in provide else "Consume") for p in paths}
    if "provider" in roles and not provide:
        sys.exit("!! provider requested but --provide-paths is empty; a tenant with no client of "
                 "its own provides nothing and gets no Provider document")
    if "consumer" in roles and set(sections.values()) == {"Provide"}:
        sys.exit("!! consumer requested but every path is Provide")

    # --- 2b. schema descriptions, mandatory ----------------------------------------------------
    # Every schema and property gets a description before anything is moved or written: from the
    # code's /// comments, else the tenant's catalogue, else another tenant's identical model.
    # What is still missing stops the run with the context needed to describe it.
    describe = load_sibling("schema_descriptions")
    catalogue = describe.catalogue_path(root, tenant, virtual)
    described = describe.apply(spec, catalogue, root)
    shown = catalogue.relative_to(root).as_posix()
    for entry in described.reused:
        log.append(f"descriptions: reused {entry}, copied into {shown}")
    for key in described.stale:
        log.append(f"descriptions: {shown} has {key}, which the document no longer holds")
    if described.missing:
        missing_file = bin_dir / "missing-descriptions.json"
        describe.write_missing(missing_file, described, catalogue, root)
        print("\n".join(f"- {line}" for line in log))
        print(f"\n!! {len(described.missing)} schema/property description(s) missing. Nothing was "
              f"moved or written.\n   Write them into {shown} (context and style in "
              f"{missing_file}), then re-run the same command"
              + (" with --skip-build." if not args.from_swagger and not virtual else "."))
        return 3
    log.append(f"descriptions: {described.from_code} from the code, {described.from_catalogue} "
               f"from {shown}")
    # Beside the export, not over it: a --skip-build re-run must see only what the code exports,
    # or catalogue text would count as code and outlive its removal from the catalogue.
    described_spec = bin_dir / "swagger.described.json"
    described_spec.write_text(json.dumps(spec, indent=2, ensure_ascii=False), encoding="utf-8")

    sections_file = bin_dir / "sections.json"
    sections_file.write_text(json.dumps(sections, indent=1), encoding="utf-8")
    history_file = bin_dir / "history.json"
    history_file.write_text(json.dumps(history, indent=1), encoding="utf-8")

    # --- 3. layout, archiving superseded artifacts --------------------------------------------
    for d in LAYOUT:
        (pkg / d).mkdir(parents=True, exist_ok=True)

    superseded = [p for d in ("Consumer", "Provider", "Tenant") for p in (pkg / d).iterdir()
                  if p.is_file()]
    # A document open in Word (or held by a preview pane or a sync client) can't be moved. Check
    # them all first: a failure halfway would leave the archive split across two folders.
    locked = []
    for p in superseded:
        try:
            with open(p, "r+b"):
                pass
        except OSError:
            locked.append(str(p.relative_to(pkg)))
    if locked:
        sys.exit(f"!! close these files and re-run; nothing was moved or written: {locked}")
    if superseded:
        stamp = datetime.now().strftime("%Y-%m-%d %H%M")
        if (pkg / "Archive" / stamp).exists():
            # A second run in the same minute would overwrite the files archived by the first.
            stamp = datetime.now().strftime("%Y-%m-%d %H%M%S")
        dest = pkg / "Archive" / stamp
        dest.mkdir(parents=True, exist_ok=True)
        for p in superseded:
            # Move, never overwrite: these are delivered artifacts other people already
            # reference, and replacing one in place destroys the record of what was sent.
            shutil.move(str(p), str(dest / p.name))
        log.append(f"archived {len(superseded)} superseded file(s) to Archive/{stamp}/")

    written: list[Path] = []
    spec_out = pkg / "Tenant" / f"{tenant} (t) API Swagger.json"
    shutil.copyfile(described_spec, spec_out)
    written.append(spec_out)

    # --- 4. one DOCX per role ------------------------------------------------------------------
    warnings: list[str] = []
    for role in roles:
        marker, folder, role_word, only = ROLES[role]
        target = pkg / folder / f"{tenant} {marker} API Specification.docx"
        cmd = [sys.executable, str(scripts / "openapi_to_docx.py"), str(spec_out), str(target),
               "--tenant", tenant, "--role", role_word, "--version", args.version,
               "--author", args.author, "--route", route, "--date", today,
               "--history", str(history_file),
               "--sections", str(sections_file)]
        if only:
            cmd += ["--only-section", only]
        out = run(cmd, label=f"openapi_to_docx.py ({role})")
        if "estimated page numbers" in out:
            warnings.append(f"{target.name}: Word unavailable, page numbers are ESTIMATED - "
                            f"not shippable, re-run where Word is present")
        written.append(target)

    # --- 5. Postman, a Tenant-level artifact ---------------------------------------------------
    target = pkg / "Tenant" / f"{tenant}.postman_collection.json"
    run(["powershell", "-NoProfile", "-File", str(scripts / "openapi_to_postman.ps1"),
         "-Tenant", tenant, "-SwaggerJson", str(spec_out), "-Route", route, "-OutputPath", str(target)],
        label="openapi_to_postman.ps1")
    written.append(target)

    # The repo keeps a working copy of tenants' collections next to the hand-maintained ones, and
    # they are tracked. The deliverable's is the one that ships; the working copy is replaced
    # only on request, because it may hold a developer's own edits.
    working = root / "postman collections" / f"{tenant}.postman_collection.json"
    if args.update_working_collection:
        if working.parent.is_dir():
            shutil.copyfile(target, working)
            log.append(f"replaced the working collection {working.relative_to(root)}")
        else:
            log.append(f"--update-working-collection: no {working.parent.relative_to(root)}/ folder, "
                       f"nothing replaced")

    # --- 6. gates -------------------------------------------------------------------------------
    verify = Path(__file__).with_name("verify_package.py")
    gates = subprocess.run([sys.executable, str(verify), str(pkg), "--route", route,
                            "--version", args.version], capture_output=True, text=True)

    print("\n".join(f"- {line}" for line in log))
    print("\nfiles written:")
    for p in written:
        print(f"  {p.relative_to(pkg)}  ({round(p.stat().st_size / 1024)} KB)")
    for w in warnings:
        print(f"\n!! {w}")
    print("\ngates:")
    print(gates.stdout.rstrip() or gates.stderr.rstrip())
    return gates.returncode


if __name__ == "__main__":
    sys.exit(main())
