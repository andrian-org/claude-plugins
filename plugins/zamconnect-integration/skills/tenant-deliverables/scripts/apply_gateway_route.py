"""
Rewrites an exported OpenAPI document so it describes the API as it is actually reachable
through the YARP gateway, rather than as the tenant service sees it internally.

A tenant registers its routes with the gateway under `/t/<route>`, and the gateway strips that
prefix before forwarding — so a Carter module that maps `/paxlst` is called by consumers at
`/t/apis/paxlst`. Swashbuckle only ever sees the internal path, which left every generated
deliverable one manual find-and-replace short of correct. Running this once, right after the
export, fixes the OpenAPI document itself, so the DOCX and the Postman collection both inherit
the correct paths instead of each re-deriving them.

Some tenants front more than one upstream system and use a two-level route, e.g.
`/t/mcti/zabs` and `/t/mcti/zma`, or `/t/mlgrd/lgms` — pass the whole thing as `--route
mcti/zabs`. Case is preserved (`/t/govzm/ZamPass` is a real route), so pass the route exactly
as it is registered in the gateway.

Usage:
    python apply_gateway_route.py <swagger.json> --route apis
    python apply_gateway_route.py <swagger.json> --route mcti/zabs --output prefixed.json

Idempotent: re-running against an already-prefixed document rewrites nothing, so a re-sync
that starts from a stale export cannot end up with `/t/apis/t/apis/paxlst`.
"""
import argparse
import json
import sys

from environments import openapi_servers

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GATEWAY_PREFIX = "/t"


def normalize_route(route):
    """Accepts `apis`, `/apis`, `/t/apis`, `mcti/zabs` — returns `apis` / `mcti/zabs`."""
    cleaned = route.strip().strip("/")
    if cleaned.startswith("t/"):
        cleaned = cleaned[2:]

    segments = [s for s in cleaned.split("/") if s]
    if not segments:
        raise SystemExit("--route is empty after normalization")
    if len(segments) > 2:
        raise SystemExit(
            f"--route '{route}' has {len(segments)} levels; the gateway uses one "
            f"(/t/apis) or two (/t/mcti/zabs)")
    for segment in segments:
        if not segment.replace("-", "").replace("_", "").isalnum():
            raise SystemExit(f"--route segment '{segment}' is not a valid URL path segment")

    return "/".join(segments)


def apply_route(openapi, route):
    prefix = f"{GATEWAY_PREFIX}/{route}"
    paths = openapi.get("paths") or {}

    already = [p for p in paths if p == prefix or p.startswith(prefix + "/")]
    if already and len(already) == len(paths):
        return prefix, []

    foreign = [p for p in paths if p.startswith(GATEWAY_PREFIX + "/") and p not in already]
    if foreign:
        raise SystemExit(
            f"Refusing to rewrite: {len(foreign)} path(s) already carry a different gateway "
            f"prefix (e.g. '{foreign[0]}'). Re-export the document, or pass the route it was "
            f"already prefixed with.")

    rewritten = {}
    changes = []
    for path, operations in paths.items():
        # A tenant that maps its root ("/") would otherwise become "/t/apis/".
        new_path = prefix if path in ("", "/") else f"{prefix}{path}"
        rewritten[new_path] = operations
        changes.append((path, new_path))

    openapi["paths"] = rewritten
    return prefix, changes


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("openapi_json")
    parser.add_argument("--route", required=True,
                        help="Gateway route as registered in YARP, e.g. 'apis' or 'mcti/zabs'")
    parser.add_argument("--output", default=None,
                        help="Write here instead of rewriting the input in place")
    parser.add_argument("--version", default=None,
                        help="Document version to write into info.version, e.g. '1.0'")
    args = parser.parse_args()

    route = normalize_route(args.route)

    with open(args.openapi_json, encoding="utf-8") as f:
        openapi = json.load(f)

    prefix, changes = apply_route(openapi, route)
    openapi["servers"] = openapi_servers()
    # The code's OpenApiInfo.Version is the API version ("v1"); the deliverable carries the document version.
    if args.version:
        openapi.setdefault("info", {})["version"] = args.version

    output = args.output or args.openapi_json
    with open(output, "w", encoding="utf-8") as f:
        json.dump(openapi, f, indent=2, ensure_ascii=False)
        f.write("\n")

    if changes:
        print(f"Applied gateway route {prefix} to {len(changes)} path(s):")
        for old, new in changes:
            print(f"  {old} -> {new}")
    else:
        print(f"Paths already carry {prefix}; refreshed servers only.")

    print(f"servers: {', '.join(s['url'] for s in openapi['servers'])}")
    print(f"Wrote: {output}")


if __name__ == "__main__":
    main()
