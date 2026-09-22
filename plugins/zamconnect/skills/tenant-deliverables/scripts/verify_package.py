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
REASON_PHRASES = {"OK", "Created", "No Content", "Bad Request", "Not Found",
                  "Conflict", "Internal Server Error", "Not Implemented"}


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
    if not s.get("servers"):
        fails.append("no servers")
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


def check_docx(path: Path, version: str | None) -> list[str]:
    fails: list[str] = []
    z = zipfile.ZipFile(path)
    doc_xml = z.read("word/document.xml").decode("utf8")
    root = ET.fromstring(doc_xml)
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
    if re.search(r"\{\{|__[A-Za-z.]+__|TODO", doc_xml + hdr):
        fails.append("placeholder survived")

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

    # Section scope: (c) must not carry Provide, (p) must not carry Consume, (t) needs what it has.
    h2 = [h.strip() for h in heads if h.strip() in ("Consume", "Provide", "Endpoints")]
    if marker == "(c)" and "Provide" in h2:
        fails.append("Consumer document carries a Provide section")
    if marker == "(p)" and "Consume" in h2:
        fails.append("Provider document carries a Consume section")
    if marker and not h2:
        fails.append("no Consume/Provide/Endpoints section")

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
    if blank:
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
    if "word/media/image1.png" not in z.namelist():
        fails.append("cover logo missing")

    pages = re.search(r"<Pages>(\d+)</Pages>", z.read("docProps/app.xml").decode("utf8"))
    ftr = " ".join(re.sub("<[^>]+>", "", z.read(n).decode("utf8"))
                   for n in z.namelist() if re.match(r"word/footer\d+\.xml", n))
    cached = re.search(r"NUMPAGES.*?MERGEFORMAT\s*(\d+)", ftr)
    if pages and (not cached or cached.group(1) != pages.group(1)):
        fails.append(f"cached NUMPAGES {cached and cached.group(1)} != app.xml Pages {pages.group(1)}")
    return fails


def body_paragraphs(path: Path) -> list[str]:
    root = ET.fromstring(zipfile.ZipFile(path).read("word/document.xml").decode("utf8"))
    return ["".join(t.text or "" for t in p.iter(W + "t")) for p in root.iter(W + "p")]


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

    for f in current("*Swagger.json"):
        report(f"OpenAPI  {f.relative_to(pkg)}", check_openapi(f, args.route, args.version))

    docs = current("*API Spec*.docx")
    for f in docs:
        pages = re.search(r"<Pages>(\d+)</Pages>",
                          zipfile.ZipFile(f).read("docProps/app.xml").decode("utf8"))
        report(f"DOCX     {f.relative_to(pkg)}  ({pages.group(1) if pages else '?'} pages, "
               f"{round(os.path.getsize(f) / 1024)} KB)", check_docx(f, args.version))

    # Pair equality: (c) and (t) may differ only in the role word.
    by_marker = {m: [f for f in docs if m in f.name] for m in ("(c)", "(p)", "(t)")}
    if by_marker["(c)"] and by_marker["(t)"]:
        a, b = body_paragraphs(by_marker["(t)"][0]), body_paragraphs(by_marker["(c)"][0])
        diff = [(x, y) for x, y in zip(a, b) if x != y]
        extra = [] if len(a) == len(b) else [f"paragraph counts differ: {len(a)} vs {len(b)}"]
        bad = extra + [f"{x!r} vs {y!r}" for x, y in diff if x.strip("()") not in ROLE_OF.values()]
        report("PAIR     (c) vs (t)", bad)

    specs = current("*Swagger.json")
    for f in current("*.postman_collection.json"):
        if f.parent.name != "Tenant":
            report(f"POSTMAN  {f.relative_to(pkg)}",
                   [f"lives in {f.parent.name}; the collection is a Tenant-level artifact"])
        report(f"POSTMAN  {f.relative_to(pkg)}",
               check_postman(f, specs[0]) if specs else ["no OpenAPI document to diff against"])

    missing = [d for d in ("Consumer", "Provider", "Tenant", "Integration Requests", "Archive")
               if not (pkg / d).is_dir()]
    report("LAYOUT", [f"missing folder(s): {', '.join(missing)}"] if missing else [])

    print(f"\n{'ALL GATES PASS' if total == 0 else f'{total} FAILURE(S)'}")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
