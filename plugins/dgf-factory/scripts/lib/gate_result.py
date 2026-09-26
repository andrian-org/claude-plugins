"""gate_result.py — build, validate and render every `dgf-gate-result` block (ADR 0020).

One builder for every gate, so no gate hand-writes its verdict:

  - `blockers` holds only what blocks; `warnings` holds every non-blocking
    warning and every required check that did not run (§2). The status is
    computed, never passed in: `fail` if any blocker, else `warn` if any
    warning, else `pass`; `blocking` is `status == "fail"`.
  - An entry is {id, severity, file, line, schema_family, summary}, its summary
    cut to SUMMARY_MAX characters. `affected_files` is every file an entry
    names plus the gate's extra files, sorted and unique (§3).
  - `checks_run` is the ordered union of the checks that ran. A required check
    is in `checks_run` or has a `not-run-<check>` entry, never both (§4).
  - A field the gate did not compute is left out; `[]` means "none" (§7).
  - Each gate has its own allowlist of next commands (§8): `verify` allows
    /dgf-plan, /dgf-implement, /dgf-commit and null; `doctor` allows null.

build() raises GateContractError, naming the rule, rather than emit a
contradictory block. render() is `json.dumps(indent=2)` inside the fence, which
escapes control characters, so no summary can close it. last_block() is the
consumer's rule: the last fenced block wins.

Stdlib only, and it imports nothing from its own package: doctor.py loads this
file by path with importlib, where a relative import cannot resolve.
"""

import json
import os
import re
import sys

SCHEMA_VERSION = 1
GATES = {"verify": ("/dgf-plan", "/dgf-implement", "/dgf-commit", None), "doctor": (None,)}
FAMILIES = ("json", "xsd")
UNRESOLVED = "unresolved"
SEVERITIES = ("error", "warning")
SUMMARY_MAX = 240
NOT_RUN_PREFIX = "not-run-"
ENTRY_KEYS = ("id", "severity", "file", "line", "schema_family", "summary")
FENCE = "```dgf-gate-result"
_BLOCK = re.compile(r"^```dgf-gate-result\n(.*?)\n```$", re.MULTILINE | re.DOTALL)


class GateContractError(ValueError):
    """The block would contradict the contract; `rule` names the rule it broke."""

    def __init__(self, rule, detail):
        super().__init__(f"gate contract: {rule} — {detail}")
        self.rule = rule
        self.detail = detail


def _debug(module_fn, message, **kv):
    if not (os.environ.get("DEBUG") or os.environ.get("LOG_LEVEL") == "debug"):
        return
    pairs = " ".join(f"{k}={v}" for k, v in kv.items())
    print(f"DEBUG [{module_fn}] {message} {pairs}".rstrip(), file=sys.stderr)


def _refuse(rule, detail):
    _debug("gate_result.build", "refused", rule=rule)
    raise GateContractError(rule, detail)


def _capped(summary):
    text = str(summary)
    return text if len(text) <= SUMMARY_MAX else text[:SUMMARY_MAX - 1] + "…"


# --- entries ------------------------------------------------------------------------

def entry(id, severity, summary, file=None, line=None, schema_family=None):
    """One blocker or warning, keys in the contract's order and its summary capped."""
    return {"id": id, "severity": severity, "file": file, "line": line, "schema_family": schema_family,
            "summary": _capped(summary)}


def not_run(check, reason, file=None):
    """The warning a required check that did not run becomes: `not-run-<check>`, with the reason."""
    return entry(NOT_RUN_PREFIX + check, "warning", f"{check} did not run: {reason}", file=file)


def _checked_entry(item, list_name):
    """`item` as a contract entry, or GateContractError."""
    if not isinstance(item, dict) or set(item) - set(ENTRY_KEYS):
        _refuse("entry-shape", f"a {list_name} entry must be a dict with only {', '.join(ENTRY_KEYS)}")
    if not isinstance(item.get("id"), str) or not item["id"]:
        _refuse("entry-id", f"a {list_name} entry has no id")
    severity = item.get("severity")
    if severity not in SEVERITIES:
        _refuse("entry-severity", f"`{item['id']}` has severity {severity!r}; it is error or warning")
    if list_name == "warnings" and severity != "warning":
        _refuse("warning-severity", f"`{item['id']}` is in warnings but claims severity {severity!r}")
    if item.get("schema_family") not in FAMILIES + (None,):
        _refuse("entry-family", f"`{item['id']}` has schema_family {item.get('schema_family')!r}")
    line = item.get("line")
    if line is not None and (isinstance(line, bool) or not isinstance(line, int)):
        _refuse("entry-line", f"`{item['id']}` has line {line!r}; it is an integer or null")
    if item.get("file") is not None and not isinstance(item["file"], str):
        _refuse("entry-file", f"`{item['id']}` has file {item['file']!r}; it is a path or null")
    if not isinstance(item.get("summary"), str):
        _refuse("entry-summary", f"`{item['id']}` has no summary")
    return entry(item["id"], severity, item["summary"], item.get("file"), line, item.get("schema_family"))


# --- the block's rules ----------------------------------------------------------------

def _check_gate(gate, command, reason):
    if gate not in GATES:
        _refuse("gate", f"`{gate}` is not a gate; the gates are {', '.join(GATES)}")
    if command not in GATES[gate]:
        allowed = ", ".join("null" if c is None else c for c in GATES[gate])
        _refuse("command", f"`{command}` is not in the {gate} gate's allowlist ({allowed})")
    if not isinstance(reason, str) or not reason.strip():
        _refuse("reason", "suggested_next.reason is empty")


def _ordered_unique(items):
    return list(dict.fromkeys(items))


def _check_required(required, checks_run, entries):
    """Each required check ran or has a not-run entry; no check both ran and did not."""
    required = list(required)
    if required and checks_run is None:
        _refuse("required-without-checks", "required checks are named but checks_run is not given")
    ran = set(checks_run or [])
    not_run_ids = {e["id"][len(NOT_RUN_PREFIX):] for e in entries if e["id"].startswith(NOT_RUN_PREFIX)}
    for check in sorted(not_run_ids & ran):
        _refuse("ran-and-not-run", f"`{check}` is in checks_run and has a `{NOT_RUN_PREFIX}{check}` entry")
    for check in required:
        if check not in ran and check not in not_run_ids:
            _refuse("required-unaccounted", f"required check `{check}` neither ran nor has a "
                                            f"`{NOT_RUN_PREFIX}{check}` entry")


def _family_counts(counts):
    """{json, xsd[, unresolved]} as non-negative integers; `unresolved` only when there are any."""
    if not isinstance(counts, dict) or set(counts) - set(FAMILIES + (UNRESOLVED,)):
        _refuse("family-counts", f"schema_family counts are keyed by {', '.join(FAMILIES + (UNRESOLVED,))}")
    for key, value in counts.items():
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            _refuse("family-counts", f"schema_family `{key}` is {value!r}; it is a non-negative integer")
    shaped = {family: counts.get(family, 0) for family in FAMILIES}
    if counts.get(UNRESOLVED):
        shaped[UNRESOLVED] = counts[UNRESOLVED]
    return shaped


def _list_field(name, value):
    if not isinstance(value, list):
        _refuse("list-field", f"`{name}` must be a list")
    return value


def build(gate, blockers, warnings, command, reason, *, checks_run=None, required=(), extra_files=(),
          schema_family=None, affected_components=None, affected_processes=None):
    """The block as a dict, its status and `blocking` computed. Raises GateContractError."""
    _check_gate(gate, command, reason)
    blockers = [_checked_entry(item, "blockers") for item in blockers]
    warnings = [_checked_entry(item, "warnings") for item in warnings]
    if checks_run is not None:
        checks_run = _ordered_unique(_list_field("checks_run", list(checks_run)))
    _check_required(required, checks_run, blockers + warnings)
    status = "fail" if blockers else "warn" if warnings else "pass"
    files = {e["file"] for e in blockers + warnings if e["file"]} | {f for f in extra_files if f}
    payload = {"schema_version": SCHEMA_VERSION, "gate": gate, "status": status, "blocking": status == "fail",
               "blockers": blockers, "warnings": warnings, "affected_files": sorted(files)}
    if checks_run is not None:
        payload["checks_run"] = checks_run
    if schema_family is not None:
        payload["schema_family"] = _family_counts(schema_family)
    if affected_components is not None:
        payload["affected_components"] = _list_field("affected_components", affected_components)
    if affected_processes is not None:
        payload["affected_processes"] = _list_field("affected_processes", affected_processes)
    payload["suggested_next"] = {"command": command, "reason": reason}
    _debug("gate_result.build", "built", gate=gate, status=status, blockers=len(blockers), warnings=len(warnings),
           checks=len(checks_run or []))
    return payload


# --- the fence ------------------------------------------------------------------------

def render(payload):
    """The fenced block. json.dumps escapes every control character, so the fence cannot be closed early."""
    return f"{FENCE}\n{json.dumps(payload, indent=2)}\n```"


def last_block(text):
    """The payload of the last `dgf-gate-result` block in `text`, or None when there is none or it is not JSON."""
    blocks = _BLOCK.findall(text)
    if not blocks:
        return None
    try:
        payload = json.loads(blocks[-1])
    except ValueError:
        return None
    return payload if isinstance(payload, dict) else None
