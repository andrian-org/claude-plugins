#!/usr/bin/env python3
"""Run every gate in the skill against a built deliverable package.

Each check here is a defect found in an already-published package. The DOCX gates open the
package rather than extracting its text, because headers, footers, styles and metadata are
separate parts and are exactly where staleness hides.

    python verify_package.py "<.../Deliverables>" [--route zdd] [--version 1.0]

Exits non-zero if anything failed, so it can gate a commit.
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import os
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
MARKER = {"consumer": "(c)", "provider": "(p)", "tenant": "(t)"}
ROLE_OF = {"(c)": "Consumer", "(p)": "Provider", "(t)": "Tenant"}
# The chapter set openapi_to_docx.py renders. Executive Summary is optional: it exists only when
# the tenant's OpenApiInfo.Description does.
CHAPTERS = ("Executive Summary", "Glossary", "Endpoints", "Schemas", "API Environments",
            "Contacts and Signature")
REASON_PHRASES = {"OK", "Created", "No Content", "Bad Request", "Not Found",
                  "Conflict", "Internal Server Error", "Not Implemented"}
METHODS = ("get", "post", "put", "patch", "delete")
ENDPOINT_HEADING = re.compile(r"^(GET|POST|PUT|PATCH|DELETE) /")


def load_environments():
    """environments.py, the one source of the platform's Base URLs, loaded by path so the gate
    works under `python -I`, which keeps the script's own folder off sys.path."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("environments", Path(__file__).with_name("environments.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ENV = load_environments()


def style_of(p):
    s = p.find(W + "pPr/" + W + "pStyle")
    return s.get(W + "val") if s is not None else None


def cells(tbl):
    return [[
        "".join(x.text or "" for x in c.iter(W + "t")).strip()
        for c in tr.findall(W + "tc")
    ] for tr in tbl.iter(W + "tr")]


def check_openapi(path: Path, route: str | None, version: str | None) -> list[str]:
    fails: list[str] = []
    s = json.loads(path.read_text(encoding="utf-8"))
    info = s.get("info", {})
    title = info.get("title", "")

    if "Controller" in title or "Module" in title:
        fails.append(f"info.title is a class name: {title}")
    if not re.search(r"\(\w+\)\s*$", title):
        fails.append(f'info.title omits the "(<CODE>)" suffix: {title}')
    if version and info.get("version") != version:
        fails.append(f"info.version {info.get('version')} != {version}")
    servers = [(x.get("url"), x.get("description")) for x in s.get("servers", [])]
    expected = [(x["url"], x["description"]) for x in ENV.openapi_servers()]
    if servers != expected:
        fails.append(f"servers {servers} are not environments.py's {expected}")
    if not s.get("components", {}).get("securitySchemes"):
        fails.append("no securitySchemes (every tenant is Basic-authenticated)")

    for p in s.get("paths", {}):
        if p.count("/t/") != 1:
            fails.append(f"gateway prefix not exactly once: {p}")
        if route and not p.startswith(f"/t/{route}"):
            fails.append(f"path does not start with /t/{route}: {p}")

    for p, ops in s.get("paths", {}).items():
        for method, op in ops.items():
            where = f"{method.upper()} {p}"
            for tag in op.get("tags", []):
                if tag.endswith(("Module", "Controller")):
                    fails.append(f"{where}: tag is a C# class name: {tag} (no .WithTags)")
            for par in op.get("parameters", []):
                if "required" not in par:
                    fails.append(f"{where}: parameter {par.get('name')} has no required flag")
                if not par.get("description"):
                    fails.append(f"{where}: parameter {par.get('name')} has no description")
            for code, resp in op.get("responses", {}).items():
                if resp.get("description", "") in REASON_PHRASES:
                    fails.append(f"{where}: response {code} description is the bare reason phrase")
                if code.startswith(("4", "5")):
                    ref = json.dumps(resp.get("content", {}))
                    if ref and "ProblemDetails" not in ref:
                        fails.append(f"{where}: error response {code} is not ProblemDetails")
    return fails


def body_blocks(root) -> list[tuple]:
    """The body's top-level paragraphs and tables in document order: ("p", style, text) or
    ("tbl", rows)."""
    out = []
    for el in root.find(W + "body"):
        if el.tag == W + "p":
            out.append(("p", style_of(el), "".join(t.text or "" for t in el.iter(W + "t")).strip()))
        elif el.tag == W + "tbl":
            out.append(("tbl", [[c.strip("\xa0 ") for c in r] for r in cells(el)]))
    return out


def chapter(blocks, title: str) -> list[tuple]:
    """The blocks under one Heading 2, up to the next."""
    start = next((i for i, b in enumerate(blocks) if b[0] == "p" and b[1] == "Heading2" and b[2] == title), None)
    if start is None:
        return []
    end = next((i for i in range(start + 1, len(blocks))
                if blocks[i][0] == "p" and blocks[i][1] == "Heading2"), len(blocks))
    return blocks[start + 1:end]


def under_headings(blocks) -> list[tuple[str, list[tuple]]]:
    """A chapter's blocks grouped by Heading 3."""
    groups: list[tuple[str, list[tuple]]] = []
    for b in blocks:
        if b[0] == "p" and b[1] == "Heading3":
            groups.append((b[2], []))
        elif groups:
            groups[-1][1].append(b)
    return groups


def operation(spec: dict, heading: str) -> dict | None:
    method, _, p = heading.partition(" ")
    return spec.get("paths", {}).get(p, {}).get(method.lower())


def parameter_names(spec: dict, op: dict) -> list[str]:
    out = []
    for par in op.get("parameters", []):
        ref = par.get("$ref", "")
        if ref.startswith("#/components/parameters/"):
            par = spec.get("components", {}).get("parameters", {}).get(ref.rsplit("/", 1)[-1], {})
        out.append(par.get("name", ""))
    return out


def check_environments(blocks) -> list[str]:
    """The API Environments chapter against environments.py: one Heading 3 per environment in
    its order, the (DEV|STG|PRD) code in the prose under each naming that environment, and its
    Base URL."""
    fails: list[str] = []
    envs = {name: (code, url) for name, code, _, url in ENV.ENVIRONMENTS}
    groups = under_headings(chapter(blocks, "API Environments"))
    names = [h for h, _ in groups]
    if names != list(envs):
        fails.append(f"environment headings {names} are not environments.py's {list(envs)}")
    for h, body in groups:
        prose = [b[2] for b in body if b[0] == "p" and not b[2].startswith("Base URL:")]
        urls = [re.sub(r"^Base URL:\s*<?|>?$", "", b[2]) for b in body
                if b[0] == "p" and b[2].startswith("Base URL:")]
        codes = re.findall(r"\((DEV|STG|PRD)\)", " ".join(prose))
        code, url = envs.get(h, (None, None))
        if not codes:
            fails.append(f"no (DEV|STG|PRD) in the prose under the {h!r} environment heading")
        elif set(codes) != {code}:
            named = [n for n, (c, _) in envs.items() if c in codes]
            fails.append(f"environment heading {h!r} over prose naming {sorted(set(codes))} ({', '.join(named)})")
        if url and urls != [url]:
            fails.append(f"{h} Base URL {urls} is not environments.py's {url}")
    return fails


def check_operations(blocks, spec: dict) -> list[str]:
    """Every endpoint's parameter names (casing and order) and response codes against its
    OpenAPI operation."""
    fails: list[str] = []
    for h, body in under_headings(chapter(blocks, "Endpoints")):
        if not ENDPOINT_HEADING.match(h):
            continue
        op = operation(spec, h)
        if op is None:
            fails.append(f"{h}: not an operation in the OpenAPI document")
            continue
        tables = [b[1] for b in body if b[0] == "tbl" and b[1]]
        params = next((t for t in tables if t[0][:2] == ["In", "Name"]), None)
        names = [r[1] for r in (params or [])[1:] if len(r) > 1 and r[0] != "Body"]
        expected = parameter_names(spec, op)
        if names != expected:
            if [n.lower() for n in names] == [n.lower() for n in expected]:
                fails.append(f"{h}: parameter name casing {names} differs from OpenAPI {expected}")
            elif sorted(names) == sorted(expected):
                fails.append(f"{h}: parameter order {names} differs from OpenAPI {expected}")
            else:
                fails.append(f"{h}: parameters {names} are not OpenAPI's {expected}")
        resp = next((t for t in tables if t[0][:1] == ["Status"]), None)
        codes = {r[0] for r in (resp or [])[1:] if r}
        declared = set(op.get("responses", {}))
        if codes - declared:
            fails.append(f"{h}: response code(s) {sorted(codes - declared)} not in the OpenAPI operation")
        if declared - codes:
            fails.append(f"{h}: OpenAPI response code(s) {sorted(declared - codes)} missing from the table")
    return fails


def check_docx(path: Path, version: str | None, spec: dict | None = None) -> list[str]:
    fails: list[str] = []
    z = zipfile.ZipFile(path)
    doc_xml = z.read("word/document.xml").decode("utf8")
    root = ET.fromstring(doc_xml)
    blocks = body_blocks(root)
    name, folder = path.name, path.parent.name

    if re.match(r"^\d+\.\s", folder):
        fails.append(f"numbered folder {folder}; use the unnumbered name")
    if name.endswith("API Specifications.docx"):
        fails.append('legacy plural "Specifications" in the filename')
    marker = MARKER.get(re.sub(r"^\d+\.\s*", "", folder).lower())
    if marker and marker not in name:
        fails.append(f"filed in {folder} but named {name}")

    role = ROLE_OF.get(marker)
    hdr = " ".join(re.sub("<[^>]+>", "", z.read(n).decode("utf8"))
                   for n in z.namelist() if re.match(r"word/header\d+\.xml", n))
    if role and role not in hdr:
        fails.append(f"running header does not say {role}")
    if version and f"Version {version}" not in hdr:
        fails.append(f"running header does not say Version {version}")
    ftr = " ".join(re.sub("<[^>]+>", "", z.read(n).decode("utf8"))
                   for n in z.namelist() if re.match(r"word/footer\d+\.xml", n))
    if re.search(r"\{\{|__[A-Za-z.]+__|TODO", doc_xml + hdr + ftr):
        fails.append("placeholder survived (body, header or footer)")

    # The cover is everything before "Last edited:", which opens the disclaimer page.
    end = next((i for i, b in enumerate(blocks) if b[0] == "p" and b[2].startswith("Last edited:")), 0)
    cover = [b[2] for b in blocks[:end] if b[0] == "p"]
    name_marker = next((m for m in ROLE_OF if m in name), None)
    cover_roles = [t.strip("()") for t in cover if re.fullmatch(r"\((Consumer|Provider|Tenant|Both)\)", t)]
    if name_marker and cover_roles != [ROLE_OF[name_marker]]:
        fails.append(f"cover role word {cover_roles} is not {ROLE_OF[name_marker]}, as the {name_marker} filename says")
    cover_version = next((m.group(1) for t in cover for m in [re.match(r"Version\s+(\S+)", t)] if m), None)
    header_version = next(iter(re.findall(r"Version\s+(\d[\w.]*)", hdr)), None)
    if not cover_version:
        fails.append("cover carries no Version")
    elif version and cover_version != version:
        fails.append(f"cover says Version {cover_version}, not {version}")
    elif header_version and cover_version != header_version:
        fails.append(f"cover says Version {cover_version}, running header {header_version}")

    fails += check_environments(blocks)
    if spec is not None:
        fails += check_operations(blocks, spec)

    heads = ["".join(t.text or "" for t in p.iter(W + "t"))
             for p in root.iter(W + "p") if (style_of(p) or "").startswith("Heading")]
    if any(not h.strip() for h in heads):
        fails.append("empty heading")
    if any(h != h.strip() for h in heads):
        fails.append("untrimmed heading")
    dupes = [h for h, n in collections.Counter(h.strip() for h in heads).items() if n > 1 and h]
    if dupes:
        fails.append(f"duplicate headings {dupes[:4]}")

    styles = collections.Counter(style_of(p) for p in root.iter(W + "p"))
    if styles.get("Heading1"):
        fails.append("Heading 1 used; sections must be Heading 2")
    if styles.get("TOC3", 0) != styles.get("Heading3", 0):
        fails.append(f"TOC stale: {styles.get('TOC3', 0)} TOC3 vs {styles.get('Heading3', 0)} Heading3")
    unstyled = sum(1 for t in root.iter(W + "tbl") if t.find(W + "tblPr/" + W + "tblStyle") is None)
    if unstyled:
        fails.append(f"{unstyled} table(s) with no style instead of Table Grid")

    h2 = ["".join(t.text or "" for t in p.iter(W + "t")).strip()
          for p in root.iter(W + "p") if style_of(p) == "Heading2"]
    if h2 != [c for c in CHAPTERS if c in h2] or set(h2) - set(CHAPTERS):
        fails.append(f"chapters {h2} are not {list(CHAPTERS)}")
    missing = [c for c in CHAPTERS[1:] if c not in h2]
    if missing:
        fails.append(f"missing chapter(s) {missing}")

    blank = 0
    for t in root.iter(W + "tbl"):
        rows = cells(t)
        header = [x.strip("\xa0 ") for x in rows[0]] if rows else []
        if "Description" in header:
            i = header.index("Description")
            blank += sum(1 for r in rows[1:] if i < len(r) and not r[i])
        if "E-mail" in header and any(any(c for c in r) for r in rows[1:]):
            fails.append("Contacts and Signature table is populated; it is filled in at signing")
        if header[:4] == ["Description", "Author", "Version", "Date"]:
            versions = [r[2] for r in rows[1:] if len(r) > 2]
            if len(versions) != len(set(versions)):
                fails.append(f"two Document History rows share a version: {versions}")
            keys = [tuple(int(n) for n in re.findall(r"\d+", v)) for v in versions]
            if keys != sorted(keys):
                fails.append(f"Document History versions out of order: {versions}")
            if version and versions and versions[-1] != version:
                fails.append(f"last Document History row is {versions[-1]}, not Version {version}")
    # A couple of blank cells is a judgement call (a self-explanatory field); more is a source
    # without doc comments.
    if blank > 2:
        fails.append(f"{blank} blank Description cell(s); the source lacks doc comments")

    core = z.read("docProps/core.xml").decode("utf8")
    if "@" in core:
        fails.append("email address in docProps/core.xml")
    if re.search(r"<cp:lastModifiedBy>\s*\S", core):
        fails.append("cp:lastModifiedBy populated")
    if not re.search(r"<dc:creator>dotGov", core):
        fails.append("dc:creator is not dotGov Solutions LLC")
    if any(n.startswith("[trash]") for n in z.namelist()):
        fails.append("stray [trash] part")
    if any(n.startswith("customXml/") for n in z.namelist()):
        fails.append("customXml/ part carries SharePoint library metadata")
    if "docProps/custom.xml" in z.namelist() and re.search(
            r'name="(ContentTypeId|MediaServiceImageTags)"', z.read("docProps/custom.xml").decode("utf8")):
        fails.append("SharePoint ContentTypeId in docProps/custom.xml")
    if "<HLinks>" in z.read("docProps/app.xml").decode("utf8"):
        fails.append("cached HLinks list in docProps/app.xml")
    if "<cp:lastPrinted>" in core:
        fails.append("cp:lastPrinted populated")
    if "word/media/image1.png" not in z.namelist():
        fails.append("cover logo missing")

    pages = re.search(r"<Pages>(\d+)</Pages>", z.read("docProps/app.xml").decode("utf8"))
    cached = re.search(r"NUMPAGES.*?MERGEFORMAT\s*(\d+)", ftr)
    if pages and (not cached or cached.group(1) != pages.group(1)):
        fails.append(f"cached NUMPAGES {cached and cached.group(1)} != app.xml Pages {pages.group(1)}")
    return fails


def body_paragraphs(path: Path) -> list[tuple[str | None, str]]:
    root = ET.fromstring(zipfile.ZipFile(path).read("word/document.xml").decode("utf8"))
    return [(style_of(p), "".join(t.text or "" for t in p.iter(W + "t"))) for p in root.iter(W + "p")]


def endpoints(paras) -> list[str]:
    return [t.strip() for s, t in paras if s == "Heading3" and ENDPOINT_HEADING.match(t.strip())]


def front_matter(paras) -> list[str]:
    """Cover, disclaimer, history and Executive Summary. The TOC is left out: it lists the
    endpoints, which differ between the documents of a tenant that consumes and provides."""
    out = []
    for s, t in paras:
        if s == "Heading2" and t.strip() in ("Glossary", "Endpoints"):
            break
        if not (s or "").startswith("TOC"):
            out.append(t)
    return out


def signature(paras) -> list[str]:
    start = next((i for i, (s, t) in enumerate(paras)
                  if s == "Heading2" and t.strip() == "Contacts and Signature"), len(paras))
    return [t for _, t in paras[start:]]


def role_diff(a: list[str], b: list[str], what: str) -> list[str]:
    """Two paragraph lists that may differ only where each side is a role word."""
    roles = set(ROLE_OF.values())
    fails = [] if len(a) == len(b) else [f"{what}: paragraph counts differ: {len(a)} vs {len(b)}"]
    return fails + [f"{what}: {x!r} vs {y!r}" for x, y in zip(a, b)
                    if x != y and not (x.strip("()") in roles and y.strip("()") in roles)]


def check_split(t: Path, c: Path | None, p: Path | None) -> tuple[str, list[str]]:
    """A single-role tenant's role document is the (t) document with another role word. A tenant
    that consumes and provides gets (c) and (p) as projections of (t): every endpoint in exactly
    one of them, (t) listing the Consume ones first, and the same front matter and signature block."""
    tp = body_paragraphs(t)
    if not (c and p):
        one = c or p
        marker = "(c)" if c else "(p)"
        return f"PAIR     {marker} vs (t)", role_diff(
            [x for _, x in tp], [x for _, x in body_paragraphs(one)], "body")

    cp, pp = body_paragraphs(c), body_paragraphs(p)
    te, ce, pe = endpoints(tp), endpoints(cp), endpoints(pp)
    fails = [f"in both (c) and (p): {e}" for e in sorted(set(ce) & set(pe))]
    fails += [f"in (t) but in neither (c) nor (p): {e}" for e in te if e not in ce and e not in pe]
    fails += [f"in {m} but not in (t): {e}" for m, es in (("(c)", ce), ("(p)", pe)) for e in es if e not in te]
    if not fails and te != ce + pe:
        fails.append("(t) does not list the (c) endpoints first, then the (p) endpoints, in the same order")
    for m, other in (("(c)", cp), ("(p)", pp)):
        fails += role_diff(front_matter(tp), front_matter(other), f"front matter {m}")
        fails += role_diff(signature(tp), signature(other), f"Contacts and Signature {m}")
    return "SPLIT    (c) + (p) = (t)", fails


def check_completeness(t: Path, spec: dict) -> list[str]:
    """The (t) document is the whole surface: one Heading 3 per OpenAPI operation. An endpoint
    the OpenAPI lacks is reported by the DOCX gate."""
    have = set(endpoints(body_paragraphs(t)))
    return [f"OpenAPI operation with no Heading 3 in (t): {m.upper()} {p}"
            for p, ops in spec.get("paths", {}).items() for m in ops
            if m in METHODS and f"{m.upper()} {p}" not in have]


def check_postman(path: Path, spec_path: Path) -> list[str]:
    fails: list[str] = []
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    paths = set(spec.get("paths", {}))
    col = json.loads(path.read_text(encoding="utf-8"))

    def walk(items):
        for i in items:
            if "item" in i:
                yield from walk(i["item"])
            else:
                yield i

    auth = col.get("auth") or {}
    if auth.get("type") != "basic":
        fails.append(f"collection auth is {auth.get('type')}, must be basic")
    if re.search(r"\{\{(test|your_access_token)\}\}", json.dumps(auth)):
        fails.append("placeholder credential in the auth block")
    if not re.fullmatch(r"[A-Z0-9]+", col.get("info", {}).get("name", "")):
        fails.append(f"info.name is {col.get('info', {}).get('name')!r}, must be the tenant code alone")

    loose = [i for i in col.get("item", []) if "item" not in i]
    if loose and any("item" in i for i in col.get("item", [])):
        fails.append(f"{len(loose)} request(s) loose at the root alongside folders; fold by tag")

    for r in walk(col.get("item", [])):
        raw = r.get("request", {}).get("url", {}).get("raw", "")
        norm = re.sub(r":([A-Za-z]\w*)", r"{\1}", re.sub(r"\?.*$", "", raw.replace("{{zc_base_url}}", "")))
        if norm not in paths:
            fails.append(f"request URL absent from OpenAPI paths: {raw}")
        else:
            method = str(r.get("request", {}).get("method", "")).lower()
            op = spec["paths"][norm].get(method)
            if op is None:
                fails.append(f"{method.upper()} {norm} is not an operation in the OpenAPI document")
            else:
                allowed = {par.get("name") for par in op.get("parameters", []) if par.get("in") == "query"}
                keys = [q.get("key") for q in r["request"]["url"].get("query", [])]
                keys += re.findall(r"[?&]([^=&]+)=", raw)
                stray = list(dict.fromkeys(k for k in keys if k not in allowed))
                if stray:
                    fails.append(f"{r.get('name')}: query key(s) {stray} are not query parameters "
                                 f"of the operation {sorted(allowed)}")
        if not re.match(r"^(GET|POST|PUT|PATCH|DELETE)\s+/", r.get("name", "")):
            fails.append(f"request name is free text, not the operation: {r.get('name')!r}")
        values = [v for v in re.findall(r"=([^&]+)", raw)]
        values += [str(v.get("value", "")) for v in r["request"]["url"].get("variable", [])]
        for v in values:
            if re.fullmatch(r"[\d/]{8,}", v):
                fails.append(f"real-looking identifier {v!r} in {r.get('name')}")
    return fails


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("package", help="the tenant's Deliverables folder")
    ap.add_argument("--route", default=None)
    ap.add_argument("--version", default=None)
    args = ap.parse_args()
    # A failure quotes document text (the cover's "●"); a cp1252 console must not end the run.
    sys.stdout.reconfigure(errors="backslashreplace")

    pkg = Path(args.package).resolve()
    if not pkg.is_dir():
        sys.exit(f"!! not a directory: {pkg}")

    total = 0
    def report(label, fails):
        nonlocal total
        total += len(fails)
        print(f"{label}\n  " + ("\n  ".join(fails) if fails else "OK"))

    def current(pattern):
        """Everything but Archive/, which holds superseded versions by design."""
        return sorted(f for f in pkg.rglob(pattern) if "Archive" not in f.relative_to(pkg).parts)

    specs = current("*Swagger.json")
    for f in specs:
        report(f"OpenAPI  {f.relative_to(pkg)}", check_openapi(f, args.route, args.version))
    # The DOCX and Postman gates diff against the Tenant-level document, which is the whole surface.
    spec = json.loads(specs[0].read_text(encoding="utf-8")) if specs else None

    docs = current("*API Spec*.docx")
    for f in docs:
        pages = re.search(r"<Pages>(\d+)</Pages>",
                          zipfile.ZipFile(f).read("docProps/app.xml").decode("utf8"))
        report(f"DOCX     {f.relative_to(pkg)}  ({pages.group(1) if pages else '?'} pages, "
               f"{round(os.path.getsize(f) / 1024)} KB)", check_docx(f, args.version, spec))

    by_marker = {m: next((f for f in docs if m in f.name), None) for m in ("(c)", "(p)", "(t)")}
    if by_marker["(t)"] and (by_marker["(c)"] or by_marker["(p)"]):
        report(*check_split(by_marker["(t)"], by_marker["(c)"], by_marker["(p)"]))
    if by_marker["(t)"]:
        report("COMPLETE (t) vs OpenAPI", check_completeness(by_marker["(t)"], spec)
               if spec else ["no OpenAPI document to diff against"])

    for f in current("*.postman_collection.json"):
        if f.parent.name != "Tenant":
            report(f"POSTMAN  {f.relative_to(pkg)}",
                   [f"lives in {f.parent.name}; the collection is a Tenant-level artifact"])
        report(f"POSTMAN  {f.relative_to(pkg)}",
               check_postman(f, specs[0]) if specs else ["no OpenAPI document to diff against"])

    missing = [d for d in ("Consumer", "Provider", "Tenant", "Integration Requests", "Archive")
               if not (pkg / d).is_dir()]
    layout = [f"missing folder(s): {', '.join(missing)}"] if missing else []
    # The role folders sit directly in Deliverables/: a file one folder deeper means a folder
    # between them, which is where a consumer stops looking.
    for f in specs + docs + current("*.postman_collection.json"):
        rel = f.relative_to(pkg)
        if len(rel.parts) > 2:
            layout.append(f"{rel} is {len(rel.parts) - 1} folder levels below Deliverables/; at most one")
    report("LAYOUT", layout)

    print(f"\n{'ALL GATES PASS' if total == 0 else f'{total} FAILURE(S)'}")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
