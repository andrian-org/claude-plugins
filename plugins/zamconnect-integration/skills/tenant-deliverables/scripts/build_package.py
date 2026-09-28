#!/usr/bin/env python3
"""Build a tenant's whole delivery package in one command.

Collapses build -> swagger export -> gateway prefix -> folder layout -> archive -> one DOCX per
role -> Postman collection -> gates into a single call, and prints a report short enough to read.
Everything it does is step 4 through 9 of the skill; the judgement call the skill reserves for a
human - which endpoints are Consume - is an input here, never a guess.

    python build_package.py ZDD --route zdd --version 1.0 --roles tenant,consumer

The package lands in src/Tenants/<Tenant>/Deliverables/ itself, with the five role folders
directly inside it.

For a tenant that both consumes and provides, pass --provide-paths so the Tenant document gets
both sections and the (c)/(p) documents become projections of it:

    --provide-paths /t/wcf/employers
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

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


def run(cmd, cwd=None, env=None, label=""):
    result = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True)
    if result.returncode != 0:
        tail = (result.stderr or result.stdout).strip().splitlines()[-25:]
        sys.exit(f"!! {label or cmd[0]} failed ({result.returncode}):\n" + "\n".join(tail))
    return result.stdout


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
    ap.add_argument("--history-description", default="Originally drafted")
    ap.add_argument("--repo-root", default=None)
    ap.add_argument("--out", default=None, help="override the Deliverables directory")
    ap.add_argument("--skip-build", action="store_true",
                    help="reuse the swagger.json already in the tenant's bin folder")
    ap.add_argument("--no-working-collection", action="store_true",
                    help="do not refresh the repo's own postman collections/<Tenant>.json")
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
    bin_dir = tdir / "bin" / "Debug" / "net10.0"
    swagger = bin_dir / "swagger.json"
    log: list[str] = []

    # --- 1. build and export -----------------------------------------------------------------
    if not args.skip_build:
        run(["dotnet", "build", str(tdir / f"{tenant}.csproj"), "-c", "Debug", "-v", "q", "--nologo"],
            label="dotnet build")
        # Both of these matter and both fail confusingly: the content root comes from the working
        # directory, and the base appsettings ships unsubstituted __Token__ URLs that only the
        # Development layer replaces with something Uri can parse.
        env = {**os.environ, "ASPNETCORE_ENVIRONMENT": "Development"}
        doc = re.search(r'SwaggerDoc\(\s*"([^"]+)"', (tdir / "Program.cs").read_text(encoding="utf-8"))
        run(["dotnet", "tool", "run", "swagger", "tofile", "--output", "swagger.json",
             f"{tenant}.dll", doc.group(1) if doc else "v1"], cwd=bin_dir, env=env, label="swagger tofile")
        log.append("built and exported swagger.json")
    elif not swagger.exists():
        sys.exit(f"!! --skip-build but no {swagger}")

    run([sys.executable, str(scripts / "apply_gateway_route.py"), str(swagger), "--route", route,
         "--version", args.version], label="apply_gateway_route.py")

    spec = json.loads(swagger.read_text(encoding="utf-8"))
    paths = list(spec.get("paths", {}))
    log.append(f"{len(paths)} path(s) prefixed /t/{route}")

    # --- 2. the Consume/Provide split ---------------------------------------------------------
    provide = set(args.provide_paths)
    unknown = provide - set(paths)
    if unknown:
        sys.exit(f"!! --provide-paths names path(s) not in the document: {sorted(unknown)}")
    sections = {p: ("Provide" if p in provide else "Consume") for p in paths}
    if "provider" in roles and not provide:
        sys.exit("!! provider requested but --provide-paths is empty; a tenant with no client of "
                 "its own provides nothing and gets no Provider document")
    if "consumer" in roles and set(sections.values()) == {"Provide"}:
        sys.exit("!! consumer requested but every path is Provide")

    sections_file = bin_dir / "sections.json"
    sections_file.write_text(json.dumps(sections, indent=1), encoding="utf-8")

    # --- 3. layout, archiving superseded artifacts --------------------------------------------
    pkg = Path(args.out).resolve() if args.out else tdir / "Deliverables"
    for d in LAYOUT:
        (pkg / d).mkdir(parents=True, exist_ok=True)

    superseded = [p for d in ("Consumer", "Provider", "Tenant") for p in (pkg / d).iterdir()
                  if p.is_file()]
    if superseded:
        stamp = datetime.now().strftime("%Y-%m-%d %H%M")
        dest = pkg / "Archive" / stamp
        dest.mkdir(parents=True, exist_ok=True)
        for p in superseded:
            # Move, never overwrite: these are delivered artifacts other people already
            # reference, and replacing one in place destroys the record of what was sent.
            shutil.move(str(p), str(dest / p.name))
        log.append(f"archived {len(superseded)} superseded file(s) to Archive/{stamp}/")

    written: list[Path] = []
    spec_out = pkg / "Tenant" / f"{tenant} (t) API Swagger.json"
    shutil.copyfile(swagger, spec_out)
    written.append(spec_out)

    # --- 4. one DOCX per role ------------------------------------------------------------------
    warnings: list[str] = []
    for role in roles:
        marker, folder, role_word, only = ROLES[role]
        target = pkg / folder / f"{tenant} {marker} API Specification.docx"
        cmd = [sys.executable, str(scripts / "openapi_to_docx.py"), str(spec_out), str(target),
               "--tenant", tenant, "--role", role_word, "--version", args.version,
               "--author", args.author, "--route", route,
               "--history-description", args.history_description,
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
         "-Tenant", tenant, "-SwaggerJson", str(spec_out), "-OutputPath", str(target)],
        label="openapi_to_postman.ps1")
    written.append(target)

    # The repo keeps its own working copy of every tenant's collection next to the 43
    # hand-maintained ones; the deliverable's is the one that ships.
    working = root / "postman collections" / f"{tenant}.postman_collection.json"
    if working.parent.is_dir() and not args.no_working_collection:
        shutil.copyfile(target, working)
        log.append(f"refreshed {working.relative_to(root)}")

    # --- 6. gates -------------------------------------------------------------------------------
    verify = Path(__file__).with_name("verify_package.py")
    gates = subprocess.run([sys.executable, str(verify), str(pkg), "--route", route,
                            "--version", args.version], capture_output=True, text=True)

    print("\n".join(f"- {line}" for line in log))
    print("\nfiles written:")
    for p in written:
        print(f"  {p.relative_to(root)}  ({round(p.stat().st_size / 1024)} KB)")
    for w in warnings:
        print(f"\n!! {w}")
    print("\ngates:")
    print(gates.stdout.rstrip() or gates.stderr.rstrip())
    return gates.returncode


if __name__ == "__main__":
    sys.exit(main())
