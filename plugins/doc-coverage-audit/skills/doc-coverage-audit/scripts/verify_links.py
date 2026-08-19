#!/usr/bin/env python3
"""Verify that every SharePoint URL in a markdown report actually resolves.

    python3 verify_links.py report.md drives.json

drives.json maps URL prefix -> driveId, e.g.

    {
      "https://tenant.sharepoint.com/Shared%20Documents/": "b!abc...",
      "https://tenant.sharepoint.com/sites/Team/Shared%20Documents/": "b!def..."
    }

Exits non-zero if any link is broken. RUN THIS BEFORE DELIVERING THE REPORT -
hand-reconstructed paths are the usual source of breakage.
"""
import re, json, sys, os, urllib.parse, urllib.request, urllib.error

DIR = os.environ.get('DCA_DIR', os.getcwd())
SKIP = ('_layouts', 'AllItems.aspx', 'DispForm.aspx')


def main():
    report, drives_file = sys.argv[1], sys.argv[2]
    token = open(os.path.join(DIR, 'gtok.txt')).read().strip()
    drives = json.load(open(drives_file))

    urls = sorted(set(re.findall(r'\]\((https://[^)\s]+)\)', open(report).read())))
    broken, checked, skipped = [], 0, 0

    for u in urls:
        if any(s in u for s in SKIP):
            skipped += 1
            continue
        base = next((b for b in drives if u.startswith(b)), None)
        if base is None:
            broken.append((u, 'no matching drive prefix'))
            continue
        rel = urllib.parse.unquote(u[len(base):])
        api = (f"https://graph.microsoft.com/v1.0/drives/{drives[base]}"
               f"/root:/{urllib.parse.quote(rel)}?$select=name")
        req = urllib.request.Request(api, headers={'Authorization': 'Bearer ' + token})
        try:
            urllib.request.urlopen(req)
            checked += 1
        except urllib.error.HTTPError as e:
            broken.append((rel, e.code))

    print(f"verified {checked} / {len(urls)} urls  (skipped {skipped} viewer/form urls)")
    if broken:
        print(f"\nBROKEN ({len(broken)}):")
        for b, why in broken:
            print(f"  [{why}] {b}")
        print("\nFix: take paths from the enumeration index, do not retype them.")
        sys.exit(1)
    print("all links OK")


if __name__ == '__main__':
    main()
