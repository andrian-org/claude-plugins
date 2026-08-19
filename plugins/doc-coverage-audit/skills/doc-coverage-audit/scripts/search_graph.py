#!/usr/bin/env python3
"""Tenant-wide Graph search for driveItems, with paging.

    python3 search_graph.py 'filename:zamconnect'            # print readable results
    python3 search_graph.py 'filename:"Test Plan"' out.json   # also save JSON
    python3 search_graph.py 'some full text' out.json 500     # raise the page cap

PREFER `filename:` KQL over bare terms. A bare term searches full text and returns
huge noisy result sets; `filename:` gives a usable candidate pool. Supports
AND / OR and `path:"..."`.

Search hits do not reliably carry parentReference.path, so location is derived
from webUrl here.
"""
import json, sys, os, time, urllib.request, urllib.parse, urllib.error

DIR = os.environ.get('DCA_DIR', os.getcwd())
PAGE = 100


def main():
    query = sys.argv[1]
    out_name = sys.argv[2] if len(sys.argv) > 2 else None
    cap = int(sys.argv[3]) if len(sys.argv) > 3 else 300

    token = open(os.path.join(DIR, 'gtok.txt')).read().strip()
    rows, frm = [], 0

    while frm < cap:
        body = {"requests": [{
            "entityTypes": ["driveItem"],
            "query": {"queryString": query},
            "from": frm, "size": PAGE,
            "fields": ["name", "webUrl", "lastModifiedDateTime", "size", "parentLink"]}]}
        req = urllib.request.Request(
            "https://graph.microsoft.com/v1.0/search/query",
            data=json.dumps(body).encode(),
            headers={'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json'})
        try:
            d = json.load(urllib.request.urlopen(req))
        except urllib.error.HTTPError as e:
            print("HTTP", e.code, e.read()[:400].decode(), file=sys.stderr)
            break

        hc = d['value'][0]['hitsContainers'][0]
        hits = hc.get('hits', [])
        for h in hits:
            r = h.get('resource', {})
            rows.append({'name': r.get('name'), 'webUrl': r.get('webUrl'),
                         'mod': r.get('lastModifiedDateTime'), 'size': r.get('size')})
        frm += len(hits)
        if not hits or not hc.get('moreResultsAvailable'):
            break
        time.sleep(0.3)

    if frm >= cap:
        print(f"NOTE: page cap {cap} reached - results truncated, narrow the query", file=sys.stderr)

    for r in rows:
        loc = urllib.parse.unquote(r['webUrl'] or '')
        kind = ''
        if '-my.sharepoint.com/personal/' in loc:
            kind = '  [ONEDRIVE-PERSONAL]'
        elif 'DispForm.aspx' in loc:
            kind = '  [LIST-ITEM FORM, not a path]'
        print(f"{r['name']}{kind}\n    {loc}")

    print(f"\n{len(rows)} hits for: {query}")
    if out_name:
        json.dump(rows, open(os.path.join(DIR, out_name), 'w'), indent=1)


if __name__ == '__main__':
    main()
