#!/usr/bin/env python3
"""Recursively enumerate a SharePoint drive subtree into JSON.

    python3 walk_tree.py <driveId> "<relative/path or empty for root>" <out.json> [maxDepth]

Reads the access token from $DCA_DIR/gtok.txt (default: cwd).
Run in the background for anything large:

    nohup python3 walk_tree.py "$D" "$P" out.json > walk.log 2>&1 &

Output: [{path, name, type, webUrl, size, mod}, ...] with path relative to the start folder.
Writes partial results if interrupted, so a token expiry does not lose the whole walk.
"""
import json, sys, os, urllib.request, urllib.parse, urllib.error

DIR = os.environ.get('DCA_DIR', os.getcwd())
GRAPH = "https://graph.microsoft.com/v1.0"


def token():
    return open(os.path.join(DIR, 'gtok.txt')).read().strip()


def get(url, retries=3):
    for attempt in range(retries):
        req = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + token()})
        try:
            return json.load(urllib.request.urlopen(req))
        except urllib.error.HTTPError as e:
            # 401 -> token may have been refreshed on disk; re-read and retry
            if e.code in (401, 429, 503) and attempt < retries - 1:
                continue
            raise


def children(drive, item_id):
    out, url = [], (f"{GRAPH}/drives/{drive}/items/{item_id}/children"
                    f"?$top=200&$select=id,name,webUrl,folder,file,size,lastModifiedDateTime")
    while url:
        d = get(url)
        out += d.get('value', [])
        url = d.get('@odata.nextLink')
    return out


def main():
    drive, root_path, out_name = sys.argv[1], sys.argv[2], sys.argv[3]
    max_depth = int(sys.argv[4]) if len(sys.argv) > 4 else 14

    if root_path:
        root = get(f"{GRAPH}/drives/{drive}/root:/{urllib.parse.quote(root_path)}?$select=id,name")
    else:
        root = get(f"{GRAPH}/drives/{drive}/root?$select=id,name")

    rows = []

    def walk(item, prefix, depth):
        if depth > max_depth:
            print(f"depth cap hit at {prefix}", file=sys.stderr)
            return
        for c in sorted(children(drive, item['id']), key=lambda x: x['name'].lower()):
            path = prefix + '/' + c['name']
            is_folder = 'folder' in c
            rows.append({'path': path, 'name': c['name'],
                         'type': 'folder' if is_folder else 'file',
                         'webUrl': c['webUrl'], 'size': c.get('size'),
                         'mod': c.get('lastModifiedDateTime')})
            if is_folder:
                walk(c, path, depth + 1)

    try:
        walk(root, '', 0)
    finally:
        with open(os.path.join(DIR, out_name), 'w') as fh:
            json.dump(rows, fh, indent=1)
        files = sum(1 for r in rows if r['type'] == 'file')
        print(f"{out_name}: total {len(rows)} files {files}")


if __name__ == '__main__':
    main()
