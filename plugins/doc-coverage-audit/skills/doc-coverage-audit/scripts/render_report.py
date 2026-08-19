#!/usr/bin/env python3
"""Render a coverage-audit mapping into the final markdown report.

    python3 render_report.py mapping.json > report.md

mapping.json shape:

    {
      "target":   "ZamConnect",
      "intro":    "optional sentence about how the sweep was done",
      "scope":    [["Root document library", "https://..."], ...],
      "items":    [
        {"name":    "1. System installation and deployment procedures",
         "links":   [["Install & admin guide.docx", "https://..."], ...],
         "comment": "Primary source is ...",
         "status":  "covered" | "partial" | "missing"},
        ...
      ],
      "empty_folders": ["C5 Infrastructure / 3. ...", ...],
      "followups":     ["Export defect history from Azure DevOps", ...],
      "exclusions":    ["*.pfx / *.jks certificates on the team site", ...]
    }

Status is used only for the summary; a row with no links renders as "none found"
regardless. Keeping "missing" rows in the table is the whole point of the audit.
"""
import json, sys

SYM = {'covered': '✅', 'partial': '⚠️', 'missing': '❌'}


def esc(s):
    return (s or '').replace('|', '\\|')


def main():
    m = json.load(open(sys.argv[1]))
    o = []

    o.append(f"# {m['target']} — Deliverables Checklist → Documents\n")
    if m.get('intro'):
        o.append(m['intro'] + "\n")

    if m.get('scope'):
        o.append("**Search scope**\n")
        o.append("| Location | Root |")
        o.append("|---|---|")
        for label, url in m['scope']:
            o.append(f"| {label} | [{label}]({url}) |")
        o.append("")

    o.append("---\n")
    o.append("| # Deliverable | Links & document names | Comments |")
    o.append("|---|---|---|")
    for it in m['items']:
        links = it.get('links') or []
        cell = "<br>".join(f"[🔗]({u}) — {esc(l)}" for l, u in links) if links else "— *none found* —"
        o.append(f"| **{esc(it['name'])}** | {cell} | {esc(it.get('comment',''))} |")

    o.append("\n---\n")
    o.append("## Summary\n")
    buckets = {'covered': [], 'partial': [], 'missing': []}
    for it in m['items']:
        st = it.get('status') or ('missing' if not it.get('links') else 'covered')
        num = it['name'].split('.')[0].strip()
        buckets.get(st, buckets['partial']).append(num)
    o.append("| Status | Items |")
    o.append("|---|---|")
    for k, label in (('covered', 'Well covered'),
                     ('partial', 'Partial — exists but embedded, a register, or platform-wide'),
                     ('missing', 'Nothing located')):
        if buckets[k]:
            o.append(f"| {SYM[k]} {label} | {', '.join(buckets[k])} |")
    o.append("")

    if m.get('empty_folders'):
        o.append("**Empty folders found** (structure promises content that is absent):\n")
        for f in m['empty_folders']:
            o.append(f"- `{f}`")
        o.append("")

    if m.get('followups'):
        o.append("**Recommended follow-up before hand-over**\n")
        for i, f in enumerate(m['followups'], 1):
            o.append(f"{i}. {f}")
        o.append("")

    if m.get('exclusions'):
        o.append("**Exclude from any client package**\n")
        for f in m['exclusions']:
            o.append(f"- {f}")
        o.append("")

    print("\n".join(o))


if __name__ == '__main__':
    main()
