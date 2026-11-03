"""install_receipt.py — what `dgf-factory setup` wrote into a project, read from its receipt.

The receipt is `.dgf-factory/install.json` (ADR 0029 §4). This module reads the part the
estate checks need: the install footprint — every managed file, and every MCP settings file
setup merged a `dgf-mcp` entry into (ADR 0029 §2). The change checks and the scaffold's
empty-folder rule ignore it, because none of it is the estate's configuration.

Only what setup could have written counts: a `files` entry under `.dgf-factory/runtime/` owned
by `runtime`, or under its owning harness's skills or agents folder, never inside a `.git`
folder; an `mcp` entry naming its harness's own MCP file. A receipt is committed, so anyone can
edit it — an entry anywhere else would hide an estate file from the change checks. It is left
out of the footprint, and `ignored()` names it for the caller to report.

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
RUNTIME_OWNER = "runtime"
RUNTIME_PREFIX = f"{PIPELINE_DIR}/runtime/"

# Where setup installs for each harness: (skillsDir, agentsDir, mcp.file) from cli/harnesses.mjs,
# restated because this module is stdlib-only. tests/test_install_receipt.py holds the two in step.
HARNESS_PLACES = {
    "claude": (".claude/skills", ".claude/agents", ".mcp.json"),
    "cursor": (".cursor/skills", None, ".cursor/mcp.json"),
    "codex": (".codex/skills", ".codex/agents", ".codex/config.toml"),
    "codex-app": (".agents/skills", None, ".codex/config.toml"),
    "copilot": (".github/skills", None, ".vscode/mcp.json"),
    "gemini": (".gemini/skills", None, ".gemini/settings.json"),
    "junie": (".junie/skills", None, ".junie/mcp/mcp.json"),
    "qwen": (".qwen/skills", None, ".qwen/settings.json"),
    "windsurf": (".devin/skills", None, None),
    "warp": (".warp/skills", None, ".warp/.mcp.json"),
    "zencoder": (".zencoder/skills", None, None),
    "roocode": (".roo/skills", None, ".roo/mcp.json"),
    "kilocode": (".kilocode/skills", None, None),
    "antigravity": (".agents/skills", ".agents/agents", ".agents/mcp_config.json"),
    "opencode": (".opencode/skills", None, "opencode.json"),
    "universal": (".agents/skills", None, ".mcp.json"),
}

# Folders an earlier AI Factory registry installed into — cli/harnesses.mjs `formerDirs`. An older receipt may name
# them; their files still belong to the install until setup removes them.
FORMER_PLACES = {
    "windsurf": (".windsurf/skills",),
    "antigravity": (".agent/skills",),
}


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


def misplaced(rel, owner):
    """Why setup would never have installed `rel` for `owner`, or None when it could have —
    cli/receipt.mjs's misplaced(), restated."""
    if any(part.lower() == ".git" for part in rel.split("/")):
        return "is inside a `.git` folder"
    if owner == RUNTIME_OWNER:
        return None if rel.startswith(RUNTIME_PREFIX) else f"is not under {RUNTIME_PREFIX}"
    places = HARNESS_PLACES.get(owner) if isinstance(owner, str) else None
    if places is None:
        return f"has an unknown owner `{owner}`"
    folders = [folder for folder in places[:2] if folder] + list(FORMER_PLACES.get(owner, ()))
    if any(rel.startswith(folder + "/") for folder in folders):
        return None
    return f"is not under {owner}'s " + " or ".join(folder + "/" for folder in folders)


def _mcp_misplaced(harness, file):
    places = HARNESS_PLACES.get(harness)
    if places is None:
        return f"has an unknown harness `{harness}`"
    return None if places[2] == file else f"is not {harness}'s MCP file"


def _entries(root):
    """(managed paths, [(where, path, why)] ignored) — both empty when there is no receipt."""
    data = load(root)
    if data is None:
        return frozenset(), []
    files = data.get("files", {})
    mcp = data.get("mcp", {})
    if not isinstance(files, dict) or not isinstance(mcp, dict):
        raise ReceiptError(f"{RECEIPT.as_posix()} `files` and `mcp` must be objects")
    found, ignored = set(), []
    for rel, entry in files.items():
        _paths(rel, "files")
        why = misplaced(rel, entry.get("owner") if isinstance(entry, dict) else None)
        if why:
            ignored.append(("files", rel, why))
        else:
            found.add(rel)
    for harness, entry in mcp.items():
        if not isinstance(entry, dict):
            raise ReceiptError(f"{RECEIPT.as_posix()} `mcp.{harness}` is not an object")
        file = _paths(entry.get("file"), f"mcp.{harness}.file")
        why = _mcp_misplaced(harness, file)
        if why:
            ignored.append((f"mcp.{harness}.file", file, why))
        else:
            found.add(file)
    for where, rel, why in ignored:
        _trace(f"ignored {where} `{rel}`: {why}")
    _trace(f"{len(found)} managed path(s) in {receipt_path(root)}, {len(ignored)} ignored")
    return frozenset(found), ignored


def footprint(root):
    """The root-relative POSIX paths setup manages: an empty set when there is no receipt.
    An entry setup could not have written is left out (see `ignored`)."""
    return _entries(root)[0]


def ignored(root):
    """The receipt's entries left out of the footprint: [(where, path, why)], for the caller to report."""
    return _entries(root)[1]


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
