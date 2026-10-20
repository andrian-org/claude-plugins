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


CLASS_RE = re.compile(r"((?:\b(?:public|internal|private|protected|abstract|sealed|partial|static|file)\s+)*)"
                      r"class\s+(\w+)\s*(?:<[^>]*>)?\s*(?=[(:{;]|where\b|$)", re.M)
CONSTRAINT_RE = re.compile(r"\{(\*{0,2}\w+)(?::[^}]*)?\??\}")
GATEWAY_BASE_URL = "__Endpoints.APIGATEWAY.BaseUrl__"


def balanced(text: str, i: int) -> tuple[str, int]:
    """The text inside the parenthesis opening at text[i], and the index just past its close."""
    depth, j = 0, i
    while j < len(text):
        c = text[j]
        if c == '"':
            j += 1
            while j < len(text) and text[j] != '"':
                j += 2 if text[j] == "\\" else 1
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return text[i + 1:j], j + 1
        j += 1
    return text[i + 1:], len(text)


def split_top(params: str) -> list[str]:
    """Split a parameter list on the commas outside <>, (), [] and {}."""
    parts, depth, cur = [], 0, ""
    for c in params:
        if c in "<([{":
            depth += 1
        elif c in ">)]}":
            depth -= 1
        if c == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += c
    return [p for p in parts + [cur] if p.strip()]


def param_types(params: str) -> list[str]:
    """The bare type name of every parameter - `[Required] Endpoints.Ifmis ifmis = null` -> `Ifmis`."""
    types = []
    for p in split_top(params):
        p = re.sub(r"^\s*(?:\[[^\]]*\]\s*)*", "", p).split("=")[0]
        words = [w for w in p.split() if w not in ("this", "ref", "out", "in", "params", "scoped")]
        if words:
            types.append(re.sub(r"<.*>", "", words[0]).split(".")[-1].rstrip("?"))
    return types


def join_path(*parts: str) -> str:
    """Route parts joined with exactly one slash between them, constraints stripped -
    `nbr` + `/entities/{id:guid}` -> `/nbr/entities/{id}`, as Swashbuckle exports it."""
    segments = [CONSTRAINT_RE.sub(r"{\1}", p).strip("/") for p in parts if p]
    segments = [s for s in segments if s]
    return "/" + "/".join(segments) if segments else ""


def parse_classes(text: str) -> list[dict]:
    """Every class in a file: name, abstract, constructor parameters (the primary constructor,
    else the classic `public X(...)`), base class and its arguments, and the class's own text."""
    found = list(CLASS_RE.finditer(text))
    classes = []
    for k, m in enumerate(found):
        body = text[m.start():found[k + 1].start() if k + 1 < len(found) else len(text)]
        name = m.group(2)
        head = m.end() - m.start()
        params = None
        if body[head:head + 1] == "(":
            params, head = balanced(body, head)
        header = body[head:re.search(r"[{;]|=>", body[head:] + "{").start() + head]
        base = re.match(r"\s*:\s*([\w.]+)\s*(?:<[^>]*>)?\s*(\()?", header)
        base_args = ""
        if base and base.group(2):
            base_args, _ = balanced(header, base.start(2))
        if params is None:
            ctor = re.search(rf"\b(?:public|protected|internal)\s+{name}\s*\(", body)
            params = balanced(body, ctor.end() - 1)[0] if ctor else ""
        classes.append({
            "name": name,
            "abstract": "abstract" in m.group(1),
            "params": params,
            "base": base.group(1).split(".")[-1] if base else None,
            "base_args": base_args,
            "body": body,
        })
    return classes


def receiver_start(text: str, i: int) -> int:
    """Start of the receiver expression of the member access whose `.` is at text[i] -
    `app.MapGroup("nbr").WithTags("x")` for `app.MapGroup("nbr").WithTags("x").MapGet(`."""
    j = i
    while True:
        k = j - 1
        while k >= 0 and text[k].isspace():
            k -= 1
        if k >= 0 and text[k] == ")":
            depth = 0
            while k >= 0:
                depth += {")": 1, "(": -1}.get(text[k], 0)
                if depth == 0:
                    break
                k -= 1
            k -= 1
        e = k + 1
        while k >= 0 and (text[k].isalnum() or text[k] == "_"):
            k -= 1
        if k + 1 == e:
            return j
        j = k + 1
        d = k
        while d >= 0 and text[d].isspace():
            d -= 1
        if d < 0 or text[d] != ".":
            return j
        j = d


def group_prefix(body: str, receiver: str, before: int, depth: int = 0) -> str:
    """The MapGroup prefix a receiver expression carries - its own MapGroup("...") calls, after
    those of the variable it starts from (`var group = app.MapGroup("zra")`)."""
    head = re.match(r"\s*(\w+)", receiver)
    prefix = ""
    if head and depth < 5:
        assigned = [a for a in re.finditer(rf"\b{head.group(1)}\s*=(?!=)\s*([^;]+);", body[:before])]
        if assigned:
            a = assigned[-1]
            prefix = group_prefix(body, a.group(1), a.start(), depth + 1)
    return join_path(prefix, *GROUP_RE.findall(receiver))


def class_routes(body: str) -> list[tuple[str, str, str]]:
    """(method, path, handler parameters) for every Map call in a class, its group prefix applied."""
    routes = []
    for m in MAP_RE.finditer(body):
        start = receiver_start(body, m.start())
        prefix = group_prefix(body, body[start:m.start()], start)
        handler = re.match(r"\s*,\s*(?:static\s+)?(?:async\s+)?(?:static\s+)?\(", body[m.end():])
        params = ""
        if handler:
            params, end = balanced(body, m.end() + handler.end() - 1)
            if not re.match(r"\s*=>", body[end:]):
                params = ""
        routes.append((m.group(1).upper(), join_path(prefix, m.group(2)), params))
    return routes


def find_class(dirs: list[Path], name: str) -> dict | None:
    """Class `name`, from `<name>.cs` or any file declaring it, in the first directory holding it."""
    if re.match(r"I[A-Z]", name):  # an interface - ICarterModule - has no routes
        return None
    for d in dirs:
        if not d.is_dir():
            continue
        files = [d / f"{name}.cs"] + sorted(d.glob("*.cs"))
        for f in files:
            for c in parse_classes(read(f)):
                if c["name"] == name:
                    return c
    return None


def module_routes(cls: dict, base_dirs: list[Path], depth: int = 0) -> list[tuple[str, str, str]]:
    """A module's routes, its base class's included. A base takes its path from the subclass's
    arguments: the three-argument shared-module form passes one, the two-argument form only tags."""
    routes = class_routes(cls["body"])
    if cls["base"] and depth < 3:
        base = find_class(base_dirs, cls["base"])
        if base:
            strings = re.findall(r'"([^"]*)"', cls["base_args"])
            base_path = strings[0] if len(strings) > 1 else ""
            routes += [(m, join_path(base_path, p), h) for m, p, h in module_routes(base, base_dirs, depth + 1)]
    return routes


def classify(params: str | list[str], tenant: str, config_clients: set[str],
             gateway_clients: set[str] = frozenset(), services: dict[str, str] | None = None,
             depth: int = 0) -> tuple[str, str]:
    """Consume or Provide, and the injected client that decided it.

    Read from the client the module takes, never from the path - `/t/wcf/employers` is a Provide
    endpoint and `/t/wcf/napsa/members` a Consume one, so the URL cannot decide this. A trailing
    "?" marks an inference rather than a reading, for a human to confirm.
    """
    types = param_types(params) if isinstance(params, str) else params
    for t in types:
        # A client bound to the gateway's own address reaches another tenant through it.
        if t in ("ZamConnect", "Gateway") or t.lower() in gateway_clients:
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
    # A service of the tenant's own is whatever the client it takes is - ZPS `Zra(Gateway)`.
    for t in types:
        if services and t in services and depth < 3:
            section, client = classify(services[t], tenant, config_clients, gateway_clients, services, depth + 1)
            if section != "UNKNOWN":
                return section, f"{t} -> {client}"
    return "UNKNOWN", ", ".join(types) or "(none)"


def handler_clients(params: str, config_clients: set[str], gateway_clients: set[str],
                    services: dict[str, str]) -> list[str]:
    """The handler parameters that are injected clients - not the request DTOs, whose names
    can start with the tenant code too."""
    return [t for t in param_types(params)
            if t in ("ZamConnect", "Gateway") or t.endswith("Shared") or t in services
            or t.lower() in config_clients or t.lower() in gateway_clients]


ROUTE_RE = re.compile(r'"path"\s*:\s*"/t/([^/"]+(?:/[^/"{]+)*)/\{')
PATH_RE = re.compile(r'^/t/([^/{]+(?:/[^/{]+)*)')
FENCE_RE = re.compile(r"```(?:json)?[ \t]*\r?\n(.*?)```", re.S)
MAP_RE = re.compile(r'\.Map(Get|Post|Put|Patch|Delete)\(\s*"([^"]*)"')
GROUP_RE = re.compile(r'MapGroup\(\s*"([^"]*)"')
CATCH_ALL_RE = re.compile(r'\{\*\*\w+\}$')
HTTP_ATTR_RE = re.compile(r'\[Http(Get|Post|Put|Patch|Delete)\(?"?([^")\]]*)"?\)?\]')
CTRL_ROUTE_RE = re.compile(r'\[Route\(\s*"([^"]+)"\s*\)\]')


def ci(d: dict, key: str):
    """Case-insensitive key lookup - an AdminAPI export is camelCase, hand-written files vary."""
    if not isinstance(d, dict):
        return None
    for k, v in d.items():
        if k.lower() == key.lower():
            return v
    return None


def gateway_route(text: str) -> tuple[str | None, list[str]]:
    """Route prefix (without /t/) from GATEWAY-CONFIG.md, and warnings about the route found.

    Current format: a RouteConfigurationPackageDto (`clusters[].configJson`, `routes[].configJson`),
    either as the whole file or in a fenced JSON block - the body of `POST /Import/routes`.
    Older scaffolds wrote separate Scope / Cluster / Route blocks; the regex fallback reads those.
    """
    candidates = [text] + FENCE_RE.findall(text)
    for chunk in candidates:
        try:
            doc = json.loads(chunk)
        except (json.JSONDecodeError, TypeError):
            continue
        routes = ci(doc, "routes")
        if not isinstance(routes, list):
            continue
        for r in routes:
            cfg = ci(r, "configJson") or {}
            path = str(ci(ci(cfg, "match") or {}, "path") or "")
            m = PATH_RE.match(path)
            if not m:
                continue
            warnings = []
            if not ci(cfg, "authorizationPolicy"):
                warnings.append("route has no authorizationPolicy - the gateway would not authenticate it")
            if not ci(ci(cfg, "metadata") or {}, "Scope"):
                warnings.append("route has no metadata.Scope - any authenticated user would pass")
            return m.group(1), warnings
    m = ROUTE_RE.search(text)
    if m:
        return m.group(1), ["GATEWAY-CONFIG.md is the pre-package format - regenerate it as an import package"]
    return None, []


def cross_cluster_routes(text: str) -> list[dict]:
    """routeId, clusterId, path, PathPattern and methods of every package route whose cluster the
    package doesn't define - the routes another tenant's cluster serves."""
    for chunk in [text] + FENCE_RE.findall(text):
        try:
            doc = json.loads(chunk)
        except (json.JSONDecodeError, TypeError):
            continue
        routes = ci(doc, "routes")
        if not isinstance(routes, list):
            continue
        own = {str(ci(ci(c, "configJson") or {}, "clusterId") or "").upper() for c in ci(doc, "clusters") or []}
        result = []
        for r in routes:
            cfg = ci(r, "configJson") or {}
            match = ci(cfg, "match") or {}
            pattern = next((ci(t, "PathPattern") for t in ci(cfg, "transforms") or [] if ci(t, "PathPattern")), None)
            cluster = str(ci(cfg, "clusterId") or "")
            if not cluster or cluster.upper() in own:
                continue
            result.append({
                "id": ci(cfg, "routeId"),
                "cluster": cluster,
                "path": str(ci(match, "path") or ""),
                "pattern": pattern,
                "methods": [str(m).upper() for m in ci(match, "methods") or []],
            })
        return result
    return []


def host_routes(root: Path, cluster: str) -> list[tuple[str, str]] | None:
    """(method, path) for every route the host tenant serves, shared-module bases included.

    The host is the tenant folder named like the cluster id. A shared module contributes its
    routes under the base path its three-argument constructor passes; the two-argument form has none.
    """
    tenants = root / "src" / "Tenants"
    host = next((d for d in tenants.iterdir() if d.is_dir() and d.name.lower() == cluster.lower()), None)
    if host is None or not (host / "Modules").is_dir():
        return None
    base_dirs = [host / "Modules", root / "src" / "Core" / "Shared" / "Modules"]
    routes: list[tuple[str, str]] = []
    for f in sorted((host / "Modules").glob("*.cs")):
        for cls in parse_classes(read(f)):
            if not cls["abstract"]:
                routes += [(m, p) for m, p, _ in module_routes(cls, base_dirs)]
    return routes


def reached(route: dict, host: list[tuple[str, str]]) -> list[tuple[str, str, str]]:
    """(method, consumer path, host path) for every host route a cross-cluster route forwards."""
    if not route["pattern"]:
        return []
    host_prefix = CATCH_ALL_RE.sub("", route["pattern"]).rstrip("/")
    consumer_prefix = CATCH_ALL_RE.sub("", route["path"]).rstrip("/")
    hits = []
    for method, path in host:
        if method not in route["methods"]:
            continue
        if path == host_prefix or path.startswith(host_prefix + "/"):
            hits.append((method, consumer_prefix + path[len(host_prefix):], path))
    return hits


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("tenant")
    ap.add_argument("--repo-root", default=None)
    args = ap.parse_args()

    root = Path(args.repo_root).resolve() if args.repo_root else find_repo_root(Path.cwd())
    tenant = args.tenant
    tdir = root / "src" / "Tenants" / tenant
    vdir = root / "src" / "VirtualTenants" / tenant
    out: list[str] = [f"TENANT {tenant}   repo {root}"]

    compose = read(root / "src" / ".dockercompose" / "docker-compose.yml")
    has_container = f"core-{tenant.lower()}" in compose
    # A Deliverables-only folder under src/Tenants is not a project.
    has_project = tdir.is_dir() and any(tdir.glob("*.csproj"))

    # --- shape -------------------------------------------------------------------------------
    modules = sorted((tdir / "Modules").glob("*.cs")) if (tdir / "Modules").is_dir() else []
    controllers = sorted((tdir / "Controllers").glob("*Controller.cs")) if (tdir / "Controllers").is_dir() else []
    if modules:
        shape = "carter"
    elif controllers:
        shape = "mvc"
    elif not has_project and not has_container:
        shape = "virtual"
    else:
        shape = "UNKNOWN"
    out.append(f"shape: {shape}   project: {has_project}   container: {has_container}")

    # --- route -------------------------------------------------------------------------------
    gateway_config = read(tdir / "GATEWAY-CONFIG.md") or read(vdir / "GATEWAY-CONFIG.md")
    found, route_warnings = gateway_route(gateway_config)
    if shape == "virtual" and found:
        # Per-path routes (/t/<slug>/nir/persons/{**url}) share one slug; the slug is the route.
        found = found.split("/")[0]
    route = found or tenant.lower()
    out.append(f"route: /t/{route}" + ("" if found else "   (GUESSED from tenant code - confirm against "
                                        "docs/zamconnect-test-routes.md)"))
    out.extend(f"  !! {w}" for w in route_warnings)

    # --- configuration (first: the Endpoints:<Name> sections decide the Consume/Provide split) --
    config_lines: list[str] = []
    config_clients: set[str] = set()
    gateway_clients: set[str] = set()  # clients whose BaseUrl is the gateway's - Consume
    for name in ("appsettings.json", "appsettings.Development.json"):
        raw = read(tdir / name)
        if not raw:
            continue
        try:
            cfg = json.loads(raw)
        except json.JSONDecodeError:
            config_lines.append(f"{name}: UNPARSEABLE")
            continue
        line = f"{name}: Endpoints = {', '.join(cfg.get('Endpoints', {})) or '(none)'}"
        if cfg.get("SoapEndpoints"):
            line += f"   SoapEndpoints = {', '.join(cfg['SoapEndpoints'])}"
        config_lines.append(line)
        for kind in ("Endpoints", "SoapEndpoints"):
            sections = cfg.get(kind, {})
            if not isinstance(sections, dict):
                continue
            config_clients |= {k.lower() for k in sections if k not in ("ZamConnect", "Gateway")}
            gateway_clients |= {k.lower() for k, v in sections.items()
                                if isinstance(v, dict) and v.get("BaseUrl") == GATEWAY_BASE_URL}
            for key, val in sections.items():
                for field in ("Username", "Password"):
                    v = str(val.get(field, "")) if isinstance(val, dict) else ""
                    if v and not (v.startswith("__") and v.endswith("__")):
                        config_lines.append(
                            f"  !! SECRET {kind}:{key}:{field} is not a __Token__ placeholder "
                            f"- a finding to report, never a value to copy")

    # The tenant's own classes and what each takes - a service is classified by its client.
    services: dict[str, str] = {}
    if tdir.is_dir():
        for f in tdir.rglob("*.cs"):
            if {"bin", "obj", "Modules", "Controllers"} & set(f.relative_to(tdir).parts[:-1]):
                continue
            for cls in parse_classes(read(f)):
                if cls["params"].strip():
                    services.setdefault(cls["name"], cls["params"])

    # --- endpoints -----------------------------------------------------------------------------
    endpoints: list[tuple[str, str, str, str]] = []  # section, client, method, path
    unsummarised: list[str] = []
    untagged: list[str] = []

    base_dirs = [tdir / "Modules", root / "src" / "Core" / "Shared" / "Modules"]
    for f in modules:
        text = read(f)
        # Class by class: each module's own constructor decides its routes, an abstract one
        # is listed only through the modules deriving from it.
        for cls in parse_classes(text):
            if cls["abstract"]:
                continue
            routes = module_routes(cls, base_dirs)
            if not routes:
                continue
            ctor = classify(cls["params"], tenant, config_clients, gateway_clients, services)
            for method, path, handler in routes:
                # A client injected in the handler wins over the one the constructor takes.
                own = handler_clients(handler, config_clients, gateway_clients, services)
                section, client = classify(own, tenant, config_clients, gateway_clients, services) \
                    if own else ("UNKNOWN", "")
                if section == "UNKNOWN":
                    section, client = ctor
                endpoints.append((section, client, method, path))
        if ".WithTags(" not in text:
            untagged.append(f.name)
        if ".WithSummary(" not in text:
            unsummarised.append(f.name)

    for f in controllers:
        text = read(f)
        cls = re.search(r"class\s+(\w+)Controller", text)
        base = CTRL_ROUTE_RE.search(text)
        # [controller] expands to the class name minus its Controller suffix, in the class's
        # casing - HubController -> /Hub, as Swashbuckle exports it. Action segments keep the
        # casing written in the attribute.
        prefix = (base.group(1).replace("[controller]", cls.group(1)) if base and cls else "")
        # Primary constructor, else the classic one.
        ctor = re.search(rf"class\s+\w+Controller\s*\(([^)]*)\)", text) \
            or re.search(rf"public\s+\w+Controller\s*\(([^)]*)\)", text)
        section, client = classify(ctor.group(1) if ctor else "", tenant, config_clients, gateway_clients, services)
        for method, path in HTTP_ATTR_RE.findall(text):
            endpoints.append((section, client, method.upper(), join_path(prefix, path)))

    # Cross-cluster routes (conventions C11): the host serves them, so their endpoints are the host
    # routes each one forwards, at the consumer's path. A real tenant can carry them too.
    cross = cross_cluster_routes(gateway_config)
    base = f"/t/{route}"
    if cross:
        out.append(f"cross-cluster routes ({len(cross)}):")
    seen: set[tuple[str, str]] = set()
    for r in cross:
        out.append(f"  {r['id']}: {','.join(r['methods'])} {r['path']} -> {r['cluster']} {r['pattern']}")
        host = host_routes(root, r["cluster"])
        if host is None:
            out.append(f"  !! host {r['cluster']} has no src/Tenants/<host>/Modules - its routes are not listed")
            continue
        hits = reached(r, host)
        if not hits:
            out.append(f"  !! {r['id']} reaches no route {r['cluster']} maps - check its PathPattern and methods")
        for method, consumer, host_path in hits:
            if (method, consumer) in seen:
                continue
            seen.add((method, consumer))
            if not consumer.startswith(base):
                out.append(f"  !! {r['id']} serves {consumer}, outside {base} - not listed")
                continue
            endpoints.append(("Consume", f"{r['cluster']} {host_path}", method, consumer[len(base):]))

    if shape == "virtual" and not cross:
        out.append("virtual tenant: surface comes from src/Core/Shared/Modules/*SharedModule.cs "
                   "- no src/VirtualTenants/<CODE>/GATEWAY-CONFIG.md, so its routes can't be attributed")

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
    deliverables = (vdir if shape == "virtual" else tdir) / "Deliverables"
    existing = sorted(p.name for p in deliverables.iterdir()) if deliverables.is_dir() else []
    out.append(f"Deliverables/: {', '.join(existing) or '(not created yet)'}")

    print("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
