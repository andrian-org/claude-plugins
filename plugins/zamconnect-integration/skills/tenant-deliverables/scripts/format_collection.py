"""
Normalizes a generated Postman collection to the formatting the 43 hand-maintained collections
in "postman collections/" already use, so a generated file sits in the folder without looking
foreign and produces a readable diff.

Windows PowerShell 5.1's ConvertTo-Json — which is what writes the file before this runs —
indents by *column position* rather than by depth and pads every colon with two spaces:

    {
        "item":  [
                     {
                         "name":  "PAXLST",

Nesting a few levels deep pushes content off the right of the screen, and every edit reflows
unrelated lines. Postman's own export format, which the existing collections follow, is tab
indented with CRLF endings, no BOM, and no trailing newline.

Usage:
    python format_collection.py "postman collections/APIS.postman_collection.json"
"""
import argparse
import json
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Postman writes these first, in this order, and a reviewer looks for info.name at the top.
# Anything not listed keeps its existing relative order after these.
KEY_ORDER = ["info", "item", "event", "auth", "variable"]


def ordered(collection):
    ranked = sorted(collection.items(), key=lambda kv: (KEY_ORDER.index(kv[0])
                                                        if kv[0] in KEY_ORDER else len(KEY_ORDER)))
    return dict(ranked)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("collection_json")
    args = parser.parse_args()

    with open(args.collection_json, encoding="utf-8-sig") as f:
        collection = json.load(f)

    # ensure_ascii=False keeps prose readable: the file is UTF-8, and ConvertTo-Json would
    # otherwise escape every non-ASCII character in a description to \uXXXX.
    text = json.dumps(ordered(collection), indent="\t", ensure_ascii=False)
    data = text.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8")

    with open(args.collection_json, "wb") as f:
        f.write(data)

    print(f"Formatted: {args.collection_json} ({len(data):,} bytes, "
          f"{text.count(chr(10)) + 1} lines, tab-indented CRLF)")


if __name__ == "__main__":
    main()
