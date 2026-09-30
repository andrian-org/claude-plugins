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
    "COMPONENT_FILE_APP_DEPENDENT": EXIT_WARNINGS,
    "CASE_ONLY_MATCH": EXIT_WARNINGS,
    "NO_SERVICE": EXIT_CLEAN,
    "NO_PARITY_ROW": EXIT_CLEAN,
    # the model (validate_model.py; ADR 0027 §3)
    "MODEL_REFERENCE_UNRESOLVED": EXIT_BLOCKED,
    "MODEL_ENTITY_UNLOADABLE": EXIT_BLOCKED,
    "MODEL_CELL_UNBOUND": EXIT_BLOCKED,
    "MODEL_REFERENCE_TEMPLATED": EXIT_WARNINGS,
    "MODEL_REFERENCE_APP_DEPENDENT": EXIT_WARNINGS,
    # the audit (audit_root.py; ADR 0027 §5)
    "AUDIT_REACH_NOT_ARTIFACT": EXIT_USAGE,
    "AUDIT_CHECK_FAILED": EXIT_USAGE,
    "AUDIT_REFERENCE_UNRESOLVED": EXIT_WARNINGS,
    "AUDIT_NARROWED": EXIT_WARNINGS,
    "AUDIT_WORKFLOW_UNREACHED": EXIT_CLEAN,
    "AUDIT_REFERENCE_DYNAMIC": EXIT_CLEAN,
    # the workspaces root and plan discovery (locate_plan.py, inventory_root.py; ADR 0017 §6)
    "ROOT_NO_WORKSPACE": EXIT_USAGE,
    "ROOT_NOT_SET_UP": EXIT_BLOCKED,
    "ROOT_AMBIGUOUS": EXIT_BLOCKED,
    "PLAN_NOT_FOUND": EXIT_BLOCKED,
    "PLAN_AMBIGUOUS": EXIT_BLOCKED,
    "PLAN_FALLBACK": EXIT_WARNINGS,
    "BASE_WORKSPACE_ABSENT": EXIT_WARNINGS,
    "VALIDATOR_DEPS_MISSING": EXIT_WARNINGS,
    # the plan file (check_plan.py; ADR 0017 §1–§5)
    "PLAN_UNREADABLE": EXIT_USAGE,
    "PLAN_FORMAT_UNSUPPORTED": EXIT_USAGE,
    "PLAN_FIELD_MISSING": EXIT_BLOCKED,
    "PLAN_FIELD_INVALID": EXIT_BLOCKED,
    "PLAN_UNKNOWN_WORKSPACE": EXIT_BLOCKED,
    "PLAN_BASE_REASON_MISSING": EXIT_BLOCKED,
    "PLAN_BRANCH_MISMATCH": EXIT_BLOCKED,
    "PLAN_NO_TASKS": EXIT_BLOCKED,
    "PLAN_TASK_INVALID": EXIT_BLOCKED,
    "PLAN_CODE_REASON_MISSING": EXIT_BLOCKED,
    "PLAN_ULTRA_BROKEN": EXIT_BLOCKED,
    "PLAN_PATH_INVALID": EXIT_BLOCKED,
    "PLAN_FILE_UNDECLARED_WORKSPACE": EXIT_BLOCKED,
    "PLAN_KIND_MISMATCH": EXIT_BLOCKED,
    "PLAN_OUT_OF_SCOPE": EXIT_BLOCKED,
    "PLAN_CODE_FILE_NEW": EXIT_BLOCKED,
    "PLAN_ROUTE_MISMATCH": EXIT_BLOCKED,
    "PLAN_ROUTE_UNKNOWN": EXIT_BLOCKED,
    "PLAN_COMMITS_INVALID": EXIT_BLOCKED,
    "PLAN_NOT_AUTHORED": EXIT_WARNINGS,
    "PLAN_COMMITS_MISSING": EXIT_WARNINGS,
    "PLAN_OVERLAP": EXIT_WARNINGS,
    "PLAN_OVERLAP_UNREADABLE": EXIT_CLEAN,
    # a branch's changes against its plan (check_change.py; ADR 0017 §6, ADR 0018)
    "CHANGE_UNDECLARED_WORKSPACE": EXIT_BLOCKED,
    "CHANGE_OUT_OF_SCOPE": EXIT_BLOCKED,
    "CHANGE_CODE_UNPLANNED": EXIT_BLOCKED,
    "CHANGE_CODE_FILE_NEW": EXIT_BLOCKED,
    "CHANGE_OUTSIDE_WORKSPACE": EXIT_WARNINGS,
    "CHANGE_UNPLANNED_FILE": EXIT_WARNINGS,
    "CHANGE_TASK_FILE_UNCHANGED": EXIT_WARNINGS,
    "CHANGE_NOT_AUTHORED": EXIT_WARNINGS,
    "PRE_EXISTING": EXIT_CLEAN,
    "FIXED": EXIT_CLEAN,
    "BASELINE_UNUSABLE": EXIT_USAGE,  # a writing skill's saved baseline (ADR 0025)
    # the verify gate (verify_gate.py; ADR 0022)
    "GATE_TASK_UNCHECKED": EXIT_BLOCKED,
    "GATE_STRICT_WARNING": EXIT_BLOCKED,
    "GATE_PLAN_UNCONFIRMED": EXIT_BLOCKED,
    "GATE_CHECK_NOT_RUN": EXIT_WARNINGS,
    # the learning loop (check_patches.py, check_override.py; ADR 0024)
    "PATCH_NAME_INVALID": EXIT_BLOCKED,
    "PATCH_UNREADABLE": EXIT_BLOCKED,
    "PATCH_FIELD_MISSING": EXIT_BLOCKED,
    "PATCH_FIELD_INVALID": EXIT_BLOCKED,
    "PATCH_SECTION_INVALID": EXIT_BLOCKED,
    "PATCH_CURSOR_UNREADABLE": EXIT_WARNINGS,
    "OVERRIDE_UNREADABLE": EXIT_BLOCKED,
    "OVERRIDE_SHAPE": EXIT_BLOCKED,
    "OVERRIDE_SOURCE_MISSING": EXIT_BLOCKED,
    "OVERRIDE_FORBIDDEN": EXIT_BLOCKED,
    "OVERRIDE_TOUCHES_LIMIT": EXIT_WARNINGS,
    # the scaffold's design check (design.py; ADR 0027 §7.3)
    "SCAFFOLD_DIR_NOT_EMPTY": EXIT_BLOCKED,
    "SCAFFOLD_NAME_INVALID": EXIT_BLOCKED,
    "SCAFFOLD_OPTION_INVALID": EXIT_BLOCKED,
    "SCAFFOLD_REFERENCE_INVALID": EXIT_BLOCKED,
    "SCAFFOLD_MODEL_INVALID": EXIT_BLOCKED,
    "SCAFFOLD_SQL_TYPE_UNKNOWN": EXIT_BLOCKED,
    "SCAFFOLD_ASK": EXIT_WARNINGS,
    "SCAFFOLD_DESIGN_UNREADABLE": EXIT_USAGE,
    # the scaffold's generator and its post-generation check (generate.py; ADR 0027 §7.10)
    "SCAFFOLD_TARGET_EXISTS": EXIT_BLOCKED,
    "SCAFFOLD_LITERAL_SECRET": EXIT_BLOCKED,
    "SCAFFOLD_VAR_UNDECLARED": EXIT_BLOCKED,
    "SCAFFOLD_STRUCTURE_INVALID": EXIT_BLOCKED,
    "SCAFFOLD_ROUTE_UNRESOLVED": EXIT_BLOCKED,
    "SCAFFOLD_VALIDATION_FAILED": EXIT_BLOCKED,
    "SCAFFOLD_DESIGN_INCOMPLETE": EXIT_USAGE,
    "SCAFFOLD_TEMPLATE_MISSING": EXIT_USAGE,
    "SCAFFOLD_WRITE_FAILED": EXIT_USAGE,
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
        where = one_line(self.file if self.line is None else f"{self.file}:{self.line}")
        return f"{_COLOURS[self.label]}{self.label}{NC} {self.code} {where} {one_line(self.message)}"


def one_line(text):
    """`text` with every control and line-separator character escaped, so it prints as one line.

    A finding's file or message can carry text the plugin did not write — a path
    from another branch, a JSON key, a name read from a workspace. Escaping C0
    controls, DEL, C1 controls and U+2028/U+2029 as `\\xNN`/`\\uNNNN` keeps one
    finding on one line, so such text can neither forge a line of this output
    nor move the terminal's cursor. Plain text is returned unchanged.
    """
    text = str(text)
    if not any(_breaks_a_line(ch) for ch in text):
        return text
    return "".join(_escaped(ch) if _breaks_a_line(ch) else ch for ch in text)


def _breaks_a_line(ch):
    code = ord(ch)
    return code < 0x20 or 0x7F <= code <= 0x9F or code in (0x2028, 0x2029)


def _escaped(ch):
    code = ord(ch)
    return f"\\x{code:02x}" if code <= 0xFF else f"\\u{code:04x}"


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


def render(reports, stream=None, header="Validation", lines=None, summary=None):
    """Print the DD3 report: header, families, checks, findings, summary, verdict.

    `lines`, when given, replace the `FAMILY:` lines — a script that reads no
    configuration (check_plan.py) prints its own `PLAN:`/`TASK:` lines there.
    `summary` lines are printed at the end of the Summary block.
    """
    stream = stream or sys.stdout
    out = lambda text="": print(text, file=stream)

    out(f"{BOLD}{header}{NC}")
    if lines is None:
        lines = [f"FAMILY: {rep.family or 'unresolved'} {rep.file}" for rep in reports]
    for line in lines:
        out(one_line(line))
    checks = _ordered_union(r.checks_run for r in reports)
    out(f"CHECKS RUN: {', '.join(checks) if checks else '(none)'}")
    for check_id, reason in _ordered_union(r.not_run for r in reports):
        out(f"NOT RUN: {check_id} ({one_line(reason)})")

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
    for line in summary or []:
        out(line)
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
