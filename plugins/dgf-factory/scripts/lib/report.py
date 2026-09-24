"""report.py — findings, reports, exit codes and the rendered verdict.

Every validator under scripts/ builds a Report per file and hands the list to
render(). Library functions return Report objects, so tools and tests never parse
the text. The exit code is the worst finding across all reports, and 3 (usage or
unrunnable) beats everything:

  0  CLEAN     — no findings, or INFO only
  1  BLOCKED   — at least one error
  2  WARNINGS  — no errors, but something needs a human look
  3  usage error, or a check that could not run

Verbose tracing goes to stderr as `DEBUG [<module>.<function>] <message> k=v …`
and is on when --verbose is given (set_verbose) or DEBUG=1 / LOG_LEVEL=debug is
set. Report lines go to stdout. Stdlib only.
"""

import os
import sys
from dataclasses import dataclass, field

EXIT_CLEAN = 0
EXIT_BLOCKED = 1
EXIT_WARNINGS = 2
EXIT_USAGE = 3

# Worst first: a usage error hides nothing, but a pass must never hide an error.
_RANK = {EXIT_USAGE: 3, EXIT_BLOCKED: 2, EXIT_WARNINGS: 1, EXIT_CLEAN: 0}

# Finding codes and the exit code each one forces. The single source of truth:
# a validator names a code and never picks its own severity.
CODES = {
    "DEPENDENCY_MISSING": EXIT_USAGE,
    "KNOWLEDGE_TABLE": EXIT_USAGE,
    "FAMILY_UNRESOLVED": EXIT_USAGE,
    "SCHEMA_UNSELECTABLE": EXIT_USAGE,
    "ROUTE_NO_ROW": EXIT_USAGE,
    "XML_MALFORMED": EXIT_BLOCKED,
    "SCHEMA_INVALID": EXIT_BLOCKED,
    "UNKNOWN_DISCRIMINATOR": EXIT_BLOCKED,
    "UNKNOWN_COMPONENT": EXIT_BLOCKED,
    "XSD_INVALID": EXIT_BLOCKED,
    "DEAD_TRANSITION": EXIT_BLOCKED,
    "WORKFLOW_UNRESOLVED": EXIT_BLOCKED,
    "VALIDATION_FLOW_UNRESOLVED": EXIT_BLOCKED,
    "CHANGE_STATE_PROCESS_UNRESOLVED": EXIT_BLOCKED,
    "CHANGE_STATE_STATE_UNDECLARED": EXIT_BLOCKED,
    "COMPONENT_FILE_UNRESOLVED": EXIT_BLOCKED,
    "UNKNOWN_PROPERTY": EXIT_WARNINGS,
    "NO_SCHEMA": EXIT_WARNINGS,
    "TYPE_FOLDER_MISMATCH": EXIT_WARNINGS,
    "PARITY_NOT_RUNTIME": EXIT_WARNINGS,
    "PARITY_PARTIAL": EXIT_WARNINGS,
    "XSD_RUNTIME_DIVERGENCE": EXIT_WARNINGS,
    "XSD_LAGS_RUNTIME": EXIT_WARNINGS,
    "XSD_NOT_COMPILABLE": EXIT_WARNINGS,
    "NO_CONFIG_CLASS": EXIT_WARNINGS,
    "UNREACHABLE_STATE": EXIT_WARNINGS,
    "WORKFLOW_APP_DEPENDENT": EXIT_WARNINGS,
    "CASE_ONLY_MATCH": EXIT_WARNINGS,
    "NO_SERVICE": EXIT_CLEAN,
    "NO_PARITY_ROW": EXIT_CLEAN,
}

_LABELS = {EXIT_USAGE: "ERROR", EXIT_BLOCKED: "ERROR", EXIT_WARNINGS: "WARN", EXIT_CLEAN: "INFO"}

# --- colours (defined once, disabled when not a terminal) --------------------
if sys.stdout.isatty():
    RED = "\033[0;31m"
    YELLOW = "\033[0;33m"
    GREEN = "\033[0;32m"
    BOLD = "\033[1m"
    NC = "\033[0m"
else:
    RED = YELLOW = GREEN = BOLD = NC = ""

_COLOURS = {"ERROR": RED, "WARN": YELLOW, "INFO": ""}


@dataclass
class Finding:
    code: str
    severity: int
    file: str
    line: object  # int or None
    message: str

    @property
    def label(self):
        return _LABELS[self.severity]

    def render(self):
        where = self.file if self.line is None else f"{self.file}:{self.line}"
        return f"{_COLOURS[self.label]}{self.label}{NC} {self.code} {where} {self.message}"


@dataclass
class Report:
    file: str
    family: object = None  # "json", "xsd" or None when unresolved
    checks_run: list = field(default_factory=list)
    not_run: list = field(default_factory=list)  # (check id, reason) pairs
    findings: list = field(default_factory=list)

    def add(self, code, message, line=None, file=None):
        """Record a finding; its severity always comes from CODES."""
        if code not in CODES:
            raise KeyError(f"unknown finding code {code}")
        found = Finding(code, CODES[code], file or self.file, line, message)
        self.findings.append(found)
        debug("report.add", "finding", code=code, file=found.file, line=line)
        return found

    def ran(self, check_id):
        if check_id not in self.checks_run:
            self.checks_run.append(check_id)

    def skipped(self, check_id, reason):
        if (check_id, reason) not in self.not_run:
            self.not_run.append((check_id, reason))

    def exit_code(self):
        return worst(f.severity for f in self.findings)


def worst(codes):
    """The worst exit code in `codes`; 3 beats 1 beats 2 beats 0."""
    result = EXIT_CLEAN
    for code in codes:
        if _RANK[code] > _RANK[result]:
            result = code
    return result


def exit_code(reports):
    return worst(r.exit_code() for r in reports)


def _ordered_union(lists):
    seen = []
    for items in lists:
        for item in items:
            if item not in seen:
                seen.append(item)
    return seen


def render(reports, stream=None, header="Validation"):
    """Print the DD3 report: header, families, checks, findings, summary, verdict."""
    stream = stream or sys.stdout
    out = lambda text="": print(text, file=stream)

    out(f"{BOLD}{header}{NC}")
    for rep in reports:
        out(f"FAMILY: {rep.family or 'unresolved'} {rep.file}")
    checks = _ordered_union(r.checks_run for r in reports)
    out(f"CHECKS RUN: {', '.join(checks) if checks else '(none)'}")
    for check_id, reason in _ordered_union(r.not_run for r in reports):
        out(f"NOT RUN: {check_id} ({reason})")

    findings = [f for r in reports for f in r.findings]
    for found in findings:
        out(found.render())

    code = exit_code(reports)
    counts = {label: sum(1 for f in findings if f.label == label) for label in ("ERROR", "WARN", "INFO")}
    out()
    out(f"{BOLD}Summary{NC}")
    out(f"Files:    {len(reports)}")
    out(f"Errors:   {counts['ERROR']}")
    out(f"Warnings: {counts['WARN']}")
    out(f"Info:     {counts['INFO']}")
    out()
    out(verdict_line(code))
    return code


def verdict_line(code):
    if code in (EXIT_BLOCKED, EXIT_USAGE):
        return f"{RED}BLOCKED{NC}"
    if code == EXIT_WARNINGS:
        return f"{YELLOW}WARNINGS{NC}"
    return f"{GREEN}CLEAN{NC}"


# --- tracing and the single bail-out path ------------------------------------

def set_verbose():
    """--verbose is DEBUG=1, so every module — and knowledge.py — agrees."""
    os.environ["DEBUG"] = "1"


def verbose():
    return bool(os.environ.get("DEBUG")) or os.environ.get("LOG_LEVEL") == "debug"


def debug(module_fn, message, **kv):
    if not verbose():
        return
    pairs = " ".join(f"{k}={v}" for k, v in kv.items())
    print(f"DEBUG [{module_fn}] {message}{' ' + pairs if pairs else ''}", file=sys.stderr)


def fail(code, message):
    """The single bail-out path. Errors go to stderr, never to the report."""
    print(message, file=sys.stderr)
    raise SystemExit(code)
