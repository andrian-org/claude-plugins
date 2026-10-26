#!/usr/bin/env python3
"""check_package.py — does the npm tarball hold the payload, and only the payload? (ADR 0030 §1)

A repo-maintenance check, not a runtime validator: contributors run it (via
tools/check-dual-schema-docs.sh section 6), skills do not. It runs
`npm pack --dry-run --json`, which reads package.json `files` exactly as a
publish would, and holds the file list to the shipped set:

  - every file is under bin/, cli/, skills/, scripts/ or knowledge/, or is one
    npm always adds (package.json, README.md, LICENSE);
  - no maintainer material (tests/, tools/, provenance/, docs/, .ai-factory/,
    .claude/), no environment or bytecode (.venv/, __pycache__/, *.pyc), and no
    IDE build output in the scaffold's templates (obj/, bin/ under templates/);
  - package.json names @andrian-org/dgf-factory, a semver version, the
    `dgf-factory` bin, `type: module`, `engines.node`, and the GitHub Packages
    registry; and declares no runtime dependencies (ADR 0029 §1).

Usage:  check_package.py [<package-root>]
        DEBUG=1 check_package.py     # every packed path

Exit codes (contract, see .ai-factory/rules/base.md):
  0  CLEAN    — the tarball is the payload
  1  BLOCKED  — a file outside the payload, maintainer material, or a package.json field is wrong
  3  usage error — npm is not installed, or its output cannot be read
"""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

if sys.stdout.isatty():
    RED, GREEN, BOLD, NC = "\033[0;31m", "\033[0;32m", "\033[1m", "\033[0m"
else:
    RED = GREEN = BOLD = NC = ""

PAYLOAD = ("bin/", "cli/", "skills/", "scripts/", "knowledge/")
ALWAYS_PACKED = ("package.json", "README.md")
FORBIDDEN_PARTS = ("tests", "tools", "provenance", "docs", ".ai-factory", ".claude", ".claude-plugin", ".venv",
                   "__pycache__", "node_modules")
IDE_OUTPUT = re.compile(r"(?:^|/)templates/.*?/(?:obj|bin)/")
SEMVER = re.compile(r"\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?\Z")
EXPECTED = {
    "name": "@andrian-org/dgf-factory",
    "type": "module",
    "bin": {"dgf-factory": "bin/dgf-factory.mjs"},
    "registry": "https://npm.pkg.github.com",
}

ERRORS = []


def fail(code, message):
    print(message, file=sys.stderr)
    raise SystemExit(code)


def trace(message):
    if os.environ.get("DEBUG") or os.environ.get("LOG_LEVEL") == "debug":
        print(f"  · {message}")


def error(message):
    ERRORS.append(message)
    print(f"{RED}ERROR{NC} {message}")


def packed_files(root):
    """The paths `npm pack` would put in the tarball. npm 7–11 print a list, npm 12 an object."""
    npm = shutil.which("npm")
    if npm is None:
        fail(3, "npm is not installed — the tarball cannot be listed")
    done = subprocess.run([npm, "pack", "--dry-run", "--json", "--ignore-scripts"], cwd=root,
                          capture_output=True, text=True)
    if done.returncode != 0:
        fail(3, f"npm pack --dry-run failed: {done.stderr.strip()[-400:]}")
    try:
        data = json.loads(done.stdout)
        entry = data[0] if isinstance(data, list) else next(iter(data.values()))
        files = [item["path"] for item in entry["files"]]
    except (ValueError, KeyError, IndexError, StopIteration, TypeError) as exc:
        fail(3, f"npm pack's output cannot be read: {exc!r}")
    print(f"Tarball: {len(files)} file(s), {entry.get('size', '?')} bytes packed, "
          f"{entry.get('unpackedSize', '?')} unpacked")
    return files


def check_files(files):
    print(f"\n{BOLD}1. Files{NC}")
    for rel in files:
        trace(rel)
        parts = rel.split("/")
        if rel not in ALWAYS_PACKED and not rel.startswith(PAYLOAD):
            error(f"{rel} is outside the payload ({', '.join(PAYLOAD)})")
        elif any(part in FORBIDDEN_PARTS for part in parts) or rel.endswith(".pyc") or ".DS_Store" in parts:
            error(f"{rel} is maintainer material, an environment or bytecode — exclude it in package.json `files`")
        elif IDE_OUTPUT.search(rel):
            error(f"{rel} is IDE build output in a template — exclude it in package.json `files`")
    for prefix in PAYLOAD:
        if not any(rel.startswith(prefix) for rel in files):
            error(f"nothing under {prefix} is packed")


def check_manifest(root):
    print(f"\n{BOLD}2. package.json{NC}")
    try:
        package = json.loads((root / "package.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        fail(3, f"package.json cannot be read: {exc}")
    for key in ("name", "type", "bin"):
        if package.get(key) != EXPECTED[key]:
            error(f"package.json `{key}` is {json.dumps(package.get(key))}, not {json.dumps(EXPECTED[key])}")
    if not SEMVER.match(str(package.get("version", ""))):
        error(f"package.json `version` {package.get('version')!r} is not semver")
    if not (package.get("engines") or {}).get("node"):
        error("package.json declares no `engines.node`")
    if (package.get("publishConfig") or {}).get("registry") != EXPECTED["registry"]:
        error(f"package.json `publishConfig.registry` is not {EXPECTED['registry']} — the content is internal")
    if package.get("dependencies"):
        error(f"package.json declares runtime dependencies ({', '.join(package['dependencies'])}); "
              "the CLI has none (ADR 0029 §1)")


def main(argv):
    if len(argv) > 2:
        fail(3, f"Usage: {Path(argv[0]).name} [<package-root>]")
    root = Path(argv[1]).resolve() if len(argv) == 2 else Path(__file__).resolve().parents[1]
    print(f"{BOLD}Package check{NC}\nRoot: {root}")
    check_files(packed_files(root))
    check_manifest(root)
    print(f"\n{BOLD}Summary{NC}\nErrors: {len(ERRORS)}")
    if ERRORS:
        print(f"\n{RED}BLOCKED{NC}")
        return 1
    print(f"\n{GREEN}CLEAN{NC}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
