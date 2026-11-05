"""dgf_version.py — DGF release versions, release lines, and which knowledge pack an estate reads (ADR 0036).

A DGF release is `X.Y.Z`, the exact release tag; its release line is `X.Y`. Each
line the package ships has one knowledge pack (`packs/lines.json`). This module
decides, from what setup was told and what the project records, which line to
install — the rules of ADR 0036 §3:

  1. `--dgf-line X.Y`        that line; an unregistered one is a usage error
  2. `--dgf-version X.Y.Z`   the line of that version (rule 5)
  3. the previous receipt's `dgfLine`, when still registered
  4. the estate's declared `dgf.version` (ADR 0019), when it is a version (rule 5)
  5. a version maps to its own line; between lines, to the nearest older one, and
     newer than every line, to the newest — both understate, which is safe; older
     than every line is refused, because an older estate would be told about
     capabilities its runtime lacks
  6. otherwise the current line

`tests/fixtures/unit/dgf-lines/selection.json` holds the vectors this module and
`cli/lines.mjs` must both pass. Stdlib only, and it imports nothing from its own
package: doctor.py loads it by path.
"""

import os
import re
import sys
from dataclasses import dataclass

VERSION = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
LINE = re.compile(r"^(\d+)\.(\d+)$")
UNKNOWN = "unknown"


class VersionError(ValueError):
    """A version or line that is not in the `X.Y.Z` / `X.Y` form."""


class SelectionError(Exception):
    """No line can be chosen. `kind` is `usage` (exit 3) or `blocked` (exit 1)."""

    def __init__(self, kind, message):
        super().__init__(message)
        self.kind = kind


@dataclass(frozen=True)
class Selection:
    line: str
    source: str   # flag-line | flag-version | receipt | config | current
    note: str = ""


def _debug(event, **kv):
    if not (os.environ.get("DEBUG") or os.environ.get("LOG_LEVEL") == "debug"):
        return
    pairs = " ".join(f"{k}={v}" for k, v in kv.items())
    print(f"DEBUG [dgf_version.{event}] {pairs}", file=sys.stderr)


def parse(version):
    """`X.Y.Z` as a tuple of three ints; anything else raises VersionError."""
    match = VERSION.match(str(version or "").strip())
    if not match:
        raise VersionError(f"`{version}` is not a DGF version such as 1.3.0")
    return tuple(int(part) for part in match.groups())


def parse_line(line):
    """`X.Y` as a tuple of two ints; anything else raises VersionError."""
    match = LINE.match(str(line or "").strip())
    if not match:
        raise VersionError(f"`{line}` is not a DGF release line such as 1.3")
    return tuple(int(part) for part in match.groups())


def is_version(text):
    return bool(VERSION.match(str(text or "").strip()))


def line_of(version):
    """The release line `X.Y` of a version `X.Y.Z`."""
    major, minor, _patch = parse(version)
    return f"{major}.{minor}"


def compare(left, right):
    """-1, 0 or 1, comparing two `X.Y.Z` versions numerically."""
    a, b = parse(left), parse(right)
    return (a > b) - (a < b)


def _sorted_lines(lines):
    return sorted(lines, key=parse_line)


def line_for_version(version, lines):
    """The pack line for a declared version, and a note when it is not the version's own line.

    Raises SelectionError("blocked") when the version is older than every line.
    """
    wanted = parse_line(line_of(version))
    ordered = _sorted_lines(lines)
    if not ordered:
        raise SelectionError("usage", "no DGF line is registered")
    own = f"{wanted[0]}.{wanted[1]}"
    if own in ordered:
        return own, ""
    older = [line for line in ordered if parse_line(line) < wanted]
    if not older:
        raise SelectionError(
            "blocked",
            f"DGF {version} is older than every knowledge pack ({', '.join(ordered)}); a newer pack would describe "
            f"capabilities its runtime lacks — pass --dgf-line {ordered[0]} to install it anyway")
    chosen = older[-1]
    if chosen == ordered[-1]:
        return chosen, f"DGF {version} is newer than every knowledge pack; using {chosen}, which may understate it"
    return chosen, f"no knowledge pack for DGF line {own}; using the nearest older one, {chosen}"


def select_line(lines, current, flag_line=None, flag_version=None, receipt_line=None, config_version=None):
    """Which line to install: a Selection, or SelectionError. The rules are in the module docstring."""
    _debug("select", lines=",".join(lines), current=current, flag_line=flag_line, flag_version=flag_version,
           receipt_line=receipt_line, config_version=config_version)
    if flag_line and flag_version:
        raise SelectionError("usage", "pass --dgf-line or --dgf-version, not both")
    if flag_line:
        try:
            parse_line(flag_line)
        except VersionError as exc:
            raise SelectionError("usage", str(exc)) from exc
        if flag_line not in lines:
            raise SelectionError("usage", f"no knowledge pack for DGF line {flag_line}; "
                                          f"available: {', '.join(_sorted_lines(lines))}")
        return _chosen(Selection(flag_line, "flag-line"))
    if flag_version:
        try:
            line, note = line_for_version(flag_version, lines)
        except VersionError as exc:
            raise SelectionError("usage", str(exc)) from exc
        return _chosen(Selection(line, "flag-version", note))
    if receipt_line and receipt_line in lines:
        return _chosen(Selection(receipt_line, "receipt"))
    if config_version and is_version(config_version):
        line, note = line_for_version(config_version, lines)
        return _chosen(Selection(line, "config", note))
    why = "the estate declares no DGF version" if not config_version or config_version == UNKNOWN \
        else f"`dgf.version` `{config_version}` is not a version"
    return _chosen(Selection(current, "current", f"{why}; installing the current line, {current}"))


def _chosen(selection):
    _debug("chosen", line=selection.line, source=selection.source, note=selection.note or "-")
    return selection
