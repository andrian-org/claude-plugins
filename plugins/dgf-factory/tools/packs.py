"""packs.py — where each DGF release line's knowledge pack and ledgers live (ADR 0036 §2).

A maintainer module, not shipped. Every maintainer tool learns a pack's directories
here, and nowhere else:

  packs/lines.json        shipped registry: line -> dir, dgf_version, read_date; `current`
  provenance/lines.json   maintainer registry: line -> tag, commit, support_branch

  pack_dir(line)          knowledge/ for the current line, else packs/<line>/
  ledger_dir(line)        provenance/knowledge/ for the current line, else provenance/packs/<line>/
  exceptions_file(line)   tools/known-good-exceptions.txt, else provenance/packs/<line>/known-good-exceptions.txt

Version parsing is scripts/lib/dgf_version.py's, loaded by path — one implementation.
A registry that does not parse, or the two registries disagreeing on the set of lines,
raises RegistryError, which a tool turns into exit 3. Stdlib only.
"""

import importlib.util
import json
import os
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SHIPPED_REGISTRY = Path("packs") / "lines.json"
MAINTAINER_REGISTRY = Path("provenance") / "lines.json"
CURRENT_PACK = Path("knowledge")
CURRENT_LEDGERS = Path("provenance") / "knowledge"
CURRENT_EXCEPTIONS = Path("tools") / "known-good-exceptions.txt"
EXCEPTIONS_NAME = "known-good-exceptions.txt"
FORMAT = 1

SHIPPED_KEYS = {"line", "dir", "dgf_version", "read_date", "legacy"}
MAINTAINER_KEYS = {"tag", "commit", "support_branch", "legacy"}


class RegistryError(Exception):
    """A registry is missing, malformed, or disagrees with the other one."""


def debug(event, **kv):
    if not (os.environ.get("DEBUG") or os.environ.get("LOG_LEVEL") == "debug"):
        return
    pairs = " ".join(f"{k}={v}" for k, v in kv.items())
    print(f"DEBUG [packs.{event}] {pairs}", file=sys.stderr)


def _load_dgf_version():
    path = PLUGIN_ROOT / "scripts" / "lib" / "dgf_version.py"
    spec = importlib.util.spec_from_file_location("dgf_version_for_tools", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


dgf_version = _load_dgf_version()
parse_version = dgf_version.parse
parse_line = dgf_version.parse_line
line_of = dgf_version.line_of
VersionError = dgf_version.VersionError


def _read_json(root, rel):
    path = Path(root) / rel
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise RegistryError(f"{rel.as_posix()} cannot be read: {exc.strerror}") from exc
    except json.JSONDecodeError as exc:
        raise RegistryError(f"{rel.as_posix()} is not JSON: {exc}") from exc
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        raise RegistryError(f"{rel.as_posix()} is not a format-{FORMAT} registry")
    return data


def _check_shipped_entry(entry, where):
    if not isinstance(entry, dict):
        raise RegistryError(f"{where} is not an object")
    unknown = set(entry) - SHIPPED_KEYS
    if unknown:
        raise RegistryError(f"{where} has unknown key(s): {', '.join(sorted(unknown))}")
    for key in ("line", "dir", "dgf_version", "read_date"):
        if not isinstance(entry.get(key), str) or not entry[key]:
            raise RegistryError(f"{where} needs a string `{key}`")
    try:
        parse_line(entry["line"])
        parse_version(entry["dgf_version"])
    except VersionError as exc:
        raise RegistryError(f"{where}: {exc}") from exc
    if not entry.get("legacy") and line_of(entry["dgf_version"]) != entry["line"]:
        raise RegistryError(f"{where}: dgf_version {entry['dgf_version']} is not on line {entry['line']}")


def load_shipped(root=PLUGIN_ROOT):
    """{line: entry} from packs/lines.json, plus the current line."""
    data = _read_json(root, SHIPPED_REGISTRY)
    lines = data.get("lines")
    if not isinstance(lines, list) or not lines:
        raise RegistryError(f"{SHIPPED_REGISTRY.as_posix()} lists no lines")
    found = {}
    for index, entry in enumerate(lines):
        where = f"{SHIPPED_REGISTRY.as_posix()} lines[{index}]"
        _check_shipped_entry(entry, where)
        if entry["line"] in found:
            raise RegistryError(f"{where}: line {entry['line']} is listed twice")
        found[entry["line"]] = entry
    current = data.get("current")
    if current not in found:
        raise RegistryError(f"{SHIPPED_REGISTRY.as_posix()} `current` {current!r} is not a listed line")
    if found[current]["dir"] != CURRENT_PACK.as_posix():
        raise RegistryError(f"{SHIPPED_REGISTRY.as_posix()}: the current line {current} must live in "
                            f"{CURRENT_PACK.as_posix()}/, not {found[current]['dir']}")
    for line, entry in found.items():
        if line != current and entry["dir"] != f"packs/{line}":
            raise RegistryError(f"{SHIPPED_REGISTRY.as_posix()}: line {line} must live in packs/{line}/, "
                                f"not {entry['dir']}")
    debug("registry", file=SHIPPED_REGISTRY.as_posix(), lines=",".join(sorted(found)), current=current)
    return found, current


def load_maintainer(root=PLUGIN_ROOT):
    """{line: entry} from provenance/lines.json."""
    data = _read_json(root, MAINTAINER_REGISTRY)
    lines = data.get("lines")
    if not isinstance(lines, dict) or not lines:
        raise RegistryError(f"{MAINTAINER_REGISTRY.as_posix()} lists no lines")
    for line, entry in lines.items():
        where = f"{MAINTAINER_REGISTRY.as_posix()} lines.{line}"
        try:
            parse_line(line)
        except VersionError as exc:
            raise RegistryError(f"{where}: {exc}") from exc
        if not isinstance(entry, dict):
            raise RegistryError(f"{where} is not an object")
        unknown = set(entry) - MAINTAINER_KEYS
        if unknown:
            raise RegistryError(f"{where} has unknown key(s): {', '.join(sorted(unknown))}")
        if not isinstance(entry.get("commit"), str) or len(entry["commit"]) != 40:
            raise RegistryError(f"{where} needs a full 40-character `commit`")
        tag = entry.get("tag")
        if tag is None and not entry.get("legacy"):
            raise RegistryError(f"{where} has no `tag`; only a legacy pin may")
        if tag is not None:
            try:
                if line_of(tag) != line:
                    raise RegistryError(f"{where}: tag {tag} is not on line {line}")
            except VersionError as exc:
                raise RegistryError(f"{where}: {exc}") from exc
    debug("registry", file=MAINTAINER_REGISTRY.as_posix(), lines=",".join(sorted(lines)))
    return lines


def load_registry(root=PLUGIN_ROOT):
    """(shipped {line: entry}, maintainer {line: entry}, current line); both must name the same lines."""
    shipped, current = load_shipped(root)
    maintainer = load_maintainer(root)
    if set(shipped) != set(maintainer):
        raise RegistryError(f"the registries disagree: {SHIPPED_REGISTRY.as_posix()} has "
                            f"{', '.join(sorted(shipped))}; {MAINTAINER_REGISTRY.as_posix()} has "
                            f"{', '.join(sorted(maintainer))}")
    for line in shipped:
        if bool(shipped[line].get("legacy")) != bool(maintainer[line].get("legacy")):
            raise RegistryError(f"the registries disagree on whether line {line} is legacy")
        tag = maintainer[line].get("tag")
        if tag is not None and tag != shipped[line]["dgf_version"]:
            raise RegistryError(f"line {line}: {MAINTAINER_REGISTRY.as_posix()} tag {tag} is not "
                                f"{SHIPPED_REGISTRY.as_posix()} dgf_version {shipped[line]['dgf_version']}")
    return shipped, maintainer, current


def lines(root=PLUGIN_ROOT):
    """Every registered line, oldest first."""
    shipped, _current = load_shipped(root)
    return sorted(shipped, key=parse_line)


def current(root=PLUGIN_ROOT):
    return load_shipped(root)[1]


def _resolve(line, root):
    shipped, cur = load_shipped(root)
    chosen = line or cur
    if chosen not in shipped:
        raise RegistryError(f"no knowledge pack for DGF line {chosen}; registered: "
                            f"{', '.join(sorted(shipped, key=parse_line))}")
    return chosen, chosen == cur


def pack_dir(line=None, root=PLUGIN_ROOT):
    """The pack's knowledge directory; the current line when `line` is None."""
    chosen, is_current = _resolve(line, root)
    path = Path(root) / (CURRENT_PACK if is_current else Path("packs") / chosen)
    debug("pack_dir", line=chosen, path=path)
    return path


def ledger_dir(line=None, root=PLUGIN_ROOT):
    """The pack's provenance directory: one ledger per knowledge file, same relative path."""
    chosen, is_current = _resolve(line, root)
    return Path(root) / (CURRENT_LEDGERS if is_current else Path("provenance") / "packs" / chosen)


def exceptions_file(line=None, root=PLUGIN_ROOT):
    """The known-good exceptions run_known_good.py settles this pack's sample errors with."""
    chosen, is_current = _resolve(line, root)
    if is_current:
        return Path(root) / CURRENT_EXCEPTIONS
    return Path(root) / "provenance" / "packs" / chosen / EXCEPTIONS_NAME


def write_json(root, rel, data):
    """Rewrite a registry: two-space indent, sorted nothing, one final newline."""
    path = Path(root) / rel
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    debug("write", file=Path(rel).as_posix())
