#!/usr/bin/env python3
"""Print everything about a tenant that step 1-3 of the skill needs, as one fact sheet.

Replaces reading the module files, Program.cs, both appsettings, the csproj, the gateway config
and docker-compose one at a time. What it cannot decide it says so rather than guessing: the
Consume/Provide split is reported per module with the client that decided it, so the split is
checkable rather than asserted, and anything ambiguous is flagged UNKNOWN for a human to settle.

    python inspect_tenant.py ZDD [--repo-root <dir>]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path


def find_repo_root(start: Path) -> Path:
    for d in [start, *start.parents]:
        if (d / "src" / "ZamConnect.sln").exists():
            return d
    sys.exit(f"!! no src/ZamConnect.sln at or above {start}")


def read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return ""


def module_classes(text: str):
    """(class name, constructor parameter list) for every type in the file."""
    return re.findall(r"class\s+(\w+)\s*\(([^)]*)\)", text)


def classify(params: str, tenant: str, config_clients: set[str]) -> tuple[str, str]:
    """Consume or Provide, and the injected client that decided it.

    Read from the client the module takes, never from the path - `/t/wcf/employers` is a Provide
    endpoint and `/t/wcf/napsa/members` a Consume one, so the URL cannot decide this. A trailing
    "?" marks an inference rather than a reading, for a human to confirm.
    """
    types = [p.strip().split()[0] for p in params.split(",") if p.strip()]
    for t in types:
        if t in ("ZamConnect", "Gateway"):
            return "Consume", t
    for t in types:
        # A shared service reaches back out through the gateway on the tenant's behalf.
        if t.endswith("Shared"):
            return "Consume", t
    for t in types:
        if t.lower().startswith(tenant.lower()):
            return "Provide", t
    # A client of its own, named after neither the gateway nor the tenant - APIS's `ZimsApi`,
    # say. The skill's rule is "the tenant's own institution's system", which the name alone
    # cannot settle, so this is offered as a reading to confirm rather than asserted.
    own = [t for t in types if t.lower() in config_clients]
    if len(own) == 1:
        return "Provide?", own[0]
    return "UNKNOWN", ", ".join(types) or "(none)"


ROUTE_RE = re.compile(r'"path"\s*:\s*"/t/([^/"]+(?:/[^/"{]+)*)/\{')
MAP_RE = re.compile(r'\.Map(Get|Post|Put|Patch|Delete)\(\s*"([^"]*)"')
GROUP_RE = re.compile(r'MapGroup\(\s*"([^"]*)"')
HTTP_ATTR_RE = re.compile(r'\[Http(Get|Post|Put|Patch|Delete)\(?"?([^")\]]*)"?\)?\]')
CTRL_ROUTE_RE = re.compile(r'\[Route\(\s*"([^"]+)"\s*\)\]')


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("tenant")
    ap.add_argument("--repo-root", default=None)
    args = ap.parse_args()

    root = Path(args.repo_root).resolve() if args.repo_root else find_repo_root(Path.cwd())
    tenant = args.tenant
    tdir = root / "src" / "Tenants" / tenant
    out: list[str] = [f"TENANT {tenant}   repo {root}"]

    compose = read(root / "src" / ".dockercompose" / "docker-compose.yml")
    has_container = f"core-{tenant.lower()}" in compose

    # --- shape -------------------------------------------------------------------------------
    modules = sorted((tdir / "Modules").glob("*.cs")) if (tdir / "Modules").is_dir() else []
    controllers = sorted((tdir / "Controllers").glob("*Controller.cs")) if (tdir / "Controllers").is_dir() else []
    if modules:
        shape = "carter"
    elif controllers:
        shape = "mvc"
    elif not tdir.is_dir() and not has_container:
        shape = "virtual"
    else:
        shape = "UNKNOWN"
    out.append(f"shape: {shape}   project: {tdir.is_dir()}   container: {has_container}")

    # --- route -------------------------------------------------------------------------------
    gateway_cfg = read(tdir / "GATEWAY-CONFIG.md")
    route_match = ROUTE_RE.search(gateway_cfg)
    route = route_match.group(1) if route_match else tenant.lower()
    out.append(f"route: /t/{route}" + ("" if route_match else "   (GUESSED from tenant code - confirm against gateway config)"))

    # --- configuration (first: the Endpoints:<Name> sections decide the Consume/Provide split) --
    config_lines: list[str] = []
    config_clients: set[str] = set()
    for name in ("appsettings.json", "appsettings.Development.json"):
        raw = read(tdir / name)
        if not raw:
            continue
        try:
            cfg = json.loads(raw)
        except json.JSONDecodeError:
            config_lines.append(f"{name}: UNPARSEABLE")
            continue
        sections = cfg.get("Endpoints", {})
        config_lines.append(f"{name}: Endpoints = {', '.join(sections) or '(none)'}")
        config_clients |= {k.lower() for k in sections if k not in ("ZamConnect", "Gateway")}
        for key, val in sections.items():
            for field in ("Username", "Password"):
                v = str(val.get(field, ""))
                if v and not (v.startswith("__") and v.endswith("__")):
                    config_lines.append(
                        f"  !! SECRET Endpoints:{key}:{field} is not a __Token__ placeholder "
                        f"- a finding to report, never a value to copy")

    # --- endpoints -----------------------------------------------------------------------------
    endpoints: list[tuple[str, str, str, str]] = []  # section, client, method, path
    unsummarised: list[str] = []
    untagged: list[str] = []

    for f in modules:
        text = read(f)
        classes = module_classes(text)
        section, client = ("UNKNOWN", "(none)")
        for cname, params in classes:
            if "Module" in cname:
                section, client = classify(params, tenant, config_clients)
                break
        group = GROUP_RE.search(text)
        prefix = group.group(1) if group else ""
        if ".WithTags(" not in text:
            untagged.append(f.name)
        for method, path in MAP_RE.findall(text):
            endpoints.append((section, client, method.upper(), prefix + path))
        if ".WithSummary(" not in text:
            unsummarised.append(f.name)

    for f in controllers:
        text = read(f)
        cls = re.search(r"class\s+(\w+)Controller", text)
        base = CTRL_ROUTE_RE.search(text)
        # [controller] expands to the class name minus its Controller suffix, lowercased -
        # HubController -> /hub. Action segments keep the casing written in the attribute.
        prefix = (base.group(1).replace("[controller]", cls.group(1).lower()) if base and cls else "")
        if prefix and not prefix.startswith("/"):
            prefix = "/" + prefix
        # Primary constructor, else the classic one.
        ctor = re.search(rf"class\s+\w+Controller\s*\(([^)]*)\)", text) \
            or re.search(rf"public\s+\w+Controller\s*\(([^)]*)\)", text)
        section, client = classify(ctor.group(1) if ctor else "", tenant, config_clients)
        for method, path in HTTP_ATTR_RE.findall(text):
            suffix = ("/" + path) if path else ""
            endpoints.append((section, client, method.upper(), prefix + suffix))

    if shape == "virtual":
        out.append("virtual tenant: surface comes from src/Core/Shared/Modules/*SharedModule.cs "
                   "- inspect those, this script does not attribute shared routes to a tenant")

    out.append(f"endpoints ({len(endpoints)}):")
    for section, client, method, path in endpoints:
        out.append(f"  [{section:<7}] {method:<6} /t/{route}{path}    <- {client}")

    consume = sum(1 for e in endpoints if e[0] == "Consume")
    provide = sum(1 for e in endpoints if e[0].startswith("Provide"))
    inferred = sum(1 for e in endpoints if e[0].endswith("?"))
    unknown = sum(1 for e in endpoints if e[0].startswith("UNKNOWN"))
    roles = ["tenant"] + (["consumer"] if consume else []) + (["provider"] if provide else [])
    out.append(f"split: consume={consume} provide={provide} unknown={unknown}")
    out.append(f"roles to render: {', '.join(roles)}"
               + ("   !! resolve the UNKNOWN endpoints first" if unknown else "")
               + ("   !! confirm the Provide? inferences against the client each module injects"
                  if inferred else ""))

    out.extend(config_lines)

    # --- swagger readiness ---------------------------------------------------------------------
    csproj = read(tdir / f"{tenant}.csproj")
    program = read(tdir / "Program.cs")
    shared_csproj = read(root / "src" / "Core" / "Shared" / "Shared.csproj")
    ready = {
        "GenerateDocumentationFile (tenant)": "<GenerateDocumentationFile>true" in csproj,
        "GenerateDocumentationFile (Shared)": "<GenerateDocumentationFile>true" in shared_csproj,
        "AddSwaggerGen with OpenApiInfo": "SwaggerDoc(" in program,
        "IncludeXmlComments": "IncludeXmlComments" in program,
        "securityDefinition": "AddSecurityDefinition" in program,
        "UseAllOfToExtendReferenceSchemas": "UseAllOfToExtendReferenceSchemas" in program,
    }
    out.append("swagger readiness:")
    for k, v in ready.items():
        out.append(f"  {'ok  ' if v else 'MISSING'} {k}")
    title = re.search(r'Title\s*=\s*"([^"]+)"', program)
    out.append(f"  info.title: {title.group(1) if title else 'NOT SET - must be \"<full name> (<CODE>)\"'}")

    if untagged:
        out.append(f"!! no .WithTags in: {', '.join(untagged)}   (tags default to the C# class name)")
    if unsummarised:
        out.append(f"!! no .WithSummary in: {', '.join(unsummarised)}   (endpoint tables come out thin)")

    # --- existing deliverables -------------------------------------------------------------------
    deliverables = tdir / "Deliverables"
    existing = sorted(p.name for p in deliverables.iterdir()) if deliverables.is_dir() else []
    out.append(f"Deliverables/: {', '.join(existing) or '(not created yet)'}")

    print("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
