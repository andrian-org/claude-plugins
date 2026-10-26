"""install_receipt.py — what `dgf-factory setup` wrote into a project, read from its receipt.

The receipt is `.dgf-factory/install.json` (ADR 0029 §4). This module reads the part the
estate checks need: the install footprint — every managed file, and every MCP settings file
setup merged a `dgf-mcp` entry into (ADR 0029 §2). The change checks and the scaffold's
empty-folder rule ignore it, because none of it is the estate's configuration.

Stdlib only, and nothing from `lib/`, so the stdlib-only scripts (doctor.py, the scaffold's
design.py) can load it by path. A receipt that cannot be read raises ReceiptError; the
caller reports it as INSTALL_RECEIPT_UNREADABLE (exit 3).
"""

import json
import os
import sys
from pathlib import Path

PIPELINE_DIR = ".dgf-factory"
RECEIPT = Path(PIPELINE_DIR) / "install.json"


class ReceiptError(Exception):
    """The receipt exists but is not the shape setup writes."""


def _trace(message):
    if os.environ.get("DEBUG") or os.environ.get("LOG_LEVEL") == "debug":
        print(f"DEBUG [install_receipt.footprint] {message}", file=sys.stderr)


def receipt_path(root):
    return Path(root) / RECEIPT


def load(root):
    """The parsed receipt, or None when the project has none."""
    path = receipt_path(root)
    if not path.is_file():
        _trace(f"no receipt at {path}")
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReceiptError(f"{RECEIPT.as_posix()} cannot be read: {exc}") from exc
    if not isinstance(data, dict):
        raise ReceiptError(f"{RECEIPT.as_posix()} is not a JSON object")
    return data


def _paths(value, where):
    if not isinstance(value, str) or not value or value.startswith("/") or ".." in value.split("/"):
        raise ReceiptError(f"{RECEIPT.as_posix()} `{where}` holds `{value!r}`, which is not a project-relative path")
    return value


def footprint(root):
    """The root-relative POSIX paths setup manages: an empty set when there is no receipt."""
    data = load(root)
    if data is None:
        return frozenset()
    files = data.get("files", {})
    mcp = data.get("mcp", {})
    if not isinstance(files, dict) or not isinstance(mcp, dict):
        raise ReceiptError(f"{RECEIPT.as_posix()} `files` and `mcp` must be objects")
    found = {_paths(rel, "files") for rel in files}
    for harness, entry in mcp.items():
        if not isinstance(entry, dict):
            raise ReceiptError(f"{RECEIPT.as_posix()} `mcp.{harness}` is not an object")
        found.add(_paths(entry.get("file"), f"mcp.{harness}.file"))
    _trace(f"{len(found)} managed path(s) in {receipt_path(root)}")
    return frozenset(found)


# --- the receipt's hash: cli/hash.mjs restated, held to tests/fixtures/hash/expected.json ---------

TRAILING = " \t\r\n"


def is_text(data):
    """UTF-8 that holds no NUL byte."""
    if b"\x00" in data:
        return False
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        return False
    return True


def normalise(text):
    """CRLF becomes LF; the trailing run of spaces, tabs, CRs and LFs at the end is dropped."""
    return text.replace("\r\n", "\n").rstrip(TRAILING)


def hash_bytes(data):
    """SHA-256, lower-case hex, of normalised text or of the raw bytes (ADR 0029 §4)."""
    import hashlib
    payload = normalise(data.decode("utf-8")).encode("utf-8") if is_text(data) else data
    return hashlib.sha256(payload).hexdigest()


def hash_file(path):
    return hash_bytes(Path(path).read_bytes())


def is_pipeline(rel_path):
    """True for anything under `.dgf-factory/` — the pipeline's state and the installed runtime."""
    parts = [p for p in str(rel_path).replace("\\", "/").split("/") if p not in ("", ".")]
    return bool(parts) and parts[0] == PIPELINE_DIR
