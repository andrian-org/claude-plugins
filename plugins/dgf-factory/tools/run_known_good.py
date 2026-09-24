#!/usr/bin/env python3
"""run_known_good.py — run every validator over DGF's own samples and hold each error to account (DD12).

A repo-maintenance tool, not a runtime validator: maintainers run it against a
DGF checkout, and it is not wired into tools/check-dual-schema-docs.sh because
that check runs without one. It imports scripts/lib and the validator modules
directly and runs, over `<dgf-root>/src/samples/workspaces`:

  1. validate_process.py --all — every process and every workflow;
  2. validate_config.py and resolve_components.py on every file a directory
     walk collects: component JSON and the legacy artifact files.

It passes only when all of these hold:
  - every error is excused by tools/known-good-exceptions.txt — an `EXCEPTION`
    line, or an unresolved CHANGE_STATE process listed as `EXPECTED_EXTERNAL`;
  - the unresolved CHANGE_STATE processes, computed by resolution, are exactly
    the `EXPECTED_EXTERNAL` names;
  - every `EXCEPTION` line still matches a finding — a stale one fails.

When the checkout's HEAD is not the `dgf_commit` the vendored schemas were read
at, the last two downgrade to warnings: the samples may have moved. Warnings are
counted per code, as the baseline.

Exceptions file, one entry per line (`#` starts a comment):
  EXCEPTION <CODE> <sample-relative path> <key> -- <reason, citing the runtime code path>
  EXPECTED_EXTERNAL <process name>
A key is `L<line>` (the finding's line), `*` (every finding of that code in that
file), or text the finding's message contains, with no spaces.

Usage:  run_known_good.py <dgf-root> [--verbose]

Exit codes (contract, see .ai-factory/rules/base.md):
  0  CLEAN     — every error excused, every expectation met
  1  BLOCKED   — an unexcused error, a stale exception, or an EXPECTED_EXTERNAL mismatch
  2  WARNINGS  — the expectation checks downgraded by checkout drift, and nothing blocking
  3  usage error, missing dependency, malformed exceptions file
"""

import argparse
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = PLUGIN_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from lib import deps, report  # noqa: E402 — after the path insert

EXCEPTIONS_FILE = PLUGIN_ROOT / "tools" / "known-good-exceptions.txt"
SCHEMA_LEDGER = PLUGIN_ROOT / "provenance" / "knowledge" / "schemas" / "MANIFEST.md"
SAMPLES = Path("src") / "samples" / "workspaces"
VERSION_SOURCE = Path("src") / "Directory.Build.props"
ERROR_EXITS = (report.EXIT_BLOCKED, report.EXIT_USAGE)
LINE_KEY = re.compile(r"L(\d+)\Z")


@dataclass
class Exception_:
    code: str
    path: str
    key: str
    reason: str
    source_line: int
    used: int = 0

    def matches(self, finding, path):
        if finding.code != self.code or path != self.path:
            return False
        line = LINE_KEY.match(self.key)
        if line:
            return finding.line == int(line.group(1))
        return self.key == "*" or self.key in finding.message


def fail(message):
    report.fail(report.EXIT_USAGE, message)


def parse_args(argv):
    parser = argparse.ArgumentParser(prog="run_known_good.py", description="Run the validators over DGF's samples.")
    parser.add_argument("dgf_root")
    parser.add_argument("--verbose", action="store_true", help="trace to stderr (same as DEBUG=1)")
    try:
        args = parser.parse_args(argv)
    except SystemExit:
        raise SystemExit(report.EXIT_USAGE)
    root = Path(args.dgf_root).expanduser().resolve()
    if not (root / VERSION_SOURCE).is_file():
        fail(f"Not a DGF repository root (no {VERSION_SOURCE.as_posix()}): {root}")
    if not (root / SAMPLES).is_dir():
        fail(f"No samples at {root / SAMPLES}")
    return root, args.verbose


def load_exceptions(path=EXCEPTIONS_FILE):
    """(EXCEPTION entries, EXPECTED_EXTERNAL names); a malformed line is exit 3."""
    exceptions, external = [], set()
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("EXPECTED_EXTERNAL "):
            name = line[len("EXPECTED_EXTERNAL "):].strip()
            if not name or " " in name:
                fail(f"{path.name}:{number}: EXPECTED_EXTERNAL takes one process name")
            external.add(name)
            continue
        head, separator, reason = line.partition(" -- ")
        tokens = head.split()
        if not line.startswith("EXCEPTION ") or not separator or len(tokens) < 4 or not reason.strip():
            fail(f"{path.name}:{number}: expected `EXCEPTION <CODE> <path> <key> -- <reason>` or "
                 f"`EXPECTED_EXTERNAL <name>`")
        code, key, sample_path = tokens[1], tokens[-1], " ".join(tokens[2:-1])
        if code not in report.CODES:
            fail(f"{path.name}:{number}: unknown finding code {code}")
        exceptions.append(Exception_(code, sample_path, key, reason.strip(), number))
    return exceptions, external


def git_head(root):
    try:
        return subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True,
                              check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def ledger_commit():
    for line in SCHEMA_LEDGER.read_text(encoding="utf-8").splitlines():
        if line.startswith("dgf_commit:"):
            return line.split(":", 1)[1].strip().strip('"')
    return None


# --- the runs ---------------------------------------------------------------------

def run_validators(samples):
    """{cli name: [Report]} for the three validators over `samples`."""
    import resolve_components
    import validate_config
    import validate_process
    from lib import cli, process_checks
    options = SimpleNamespace(component_type=None, view_kind=None)
    runs = {"validate_process.py": [], "validate_config.py": [], "resolve_components.py": []}
    unresolved = set()
    for path in process_checks.processes_under(samples):
        runs["validate_process.py"].append(validate_process.check_file(path, samples))
    for path in process_checks.workflows_under(samples):
        rep = report.Report(cli.display(path))
        tree = process_checks.parse(path)
        rep.family = "xsd"
        if tree is None:
            rep.add("XML_MALFORMED", "the workflow does not parse")
        else:
            unresolved |= set(process_checks.check_workflow(path, tree, rep, samples))
        runs["validate_process.py"].append(rep)
    for path in cli.collect([samples]):
        runs["validate_config.py"].append(validate_config.validate_file(path, options))
        runs["resolve_components.py"].append(resolve_components.check_file(path, options))
    for name, reports in runs.items():
        for rep in reports:
            report.debug("run_known_good.run_validators", "validated", cli=name, file=rep.file,
                         codes=",".join(sorted({f.code for f in rep.findings})) or "-")
    return runs, unresolved


def sample_path(finding_file, samples):
    try:
        return Path(os.path.abspath(finding_file)).relative_to(samples).as_posix()
    except ValueError:
        return finding_file


def settle(runs, samples, exceptions, external):
    """(unexcused [(cli, path, finding)], counts {cli: Counter}, excused Counter)."""
    unexcused, excused = [], Counter()
    counts = defaultdict(Counter)
    for name, reports in runs.items():
        for rep in reports:
            for finding in rep.findings:
                counts[name][(finding.label, finding.code)] += 1
                if finding.severity not in ERROR_EXITS:
                    continue
                path = sample_path(finding.file, samples)
                matched = [e for e in exceptions if e.matches(finding, path)]
                for entry in matched:
                    entry.used += 1
                if matched:
                    excused["EXCEPTION"] += 1
                elif finding.code == "CHANGE_STATE_PROCESS_UNRESOLVED" and any(
                        f"process `{name_}`" in finding.message for name_ in external):
                    excused["EXPECTED_EXTERNAL"] += 1
                else:
                    unexcused.append((name, path, finding))
    return unexcused, counts, excused


# --- output -----------------------------------------------------------------------

def print_summary(runs, counts):
    print(f"\n{report.BOLD}Findings per validator and code{report.NC}")
    for name, reports in runs.items():
        print(f"  {name} — {len(reports)} files")
        for (label, code), count in sorted(counts[name].items(), key=lambda item: (-item[1], item[0][1])):
            print(f"    {label:<5} {code:<32} {count:>5}")


def main(argv):
    root, verbose = parse_args(argv)
    if verbose:
        report.set_verbose()
    deps.require()
    from lxml import etree
    from lib import knowledge
    samples = root / SAMPLES
    exceptions, external = load_exceptions()
    head, recorded = git_head(root), ledger_commit()
    drift = not (head and recorded and (head.startswith(recorded) or recorded.startswith(head)))
    libxml = ".".join(map(str, etree.LIBXML_VERSION))

    print(f"{report.BOLD}Known-good run{report.NC}")
    print(f"DGF:      {root} @ {head or 'unknown'}")
    print(f"Ledger:   dgf_commit {recorded or 'unknown'} — {'DRIFT' if drift else 'match'}")
    print(f"libxml2:  {libxml} (lxml)")
    try:
        runs, unresolved = run_validators(samples)
    except knowledge.KnowledgeTableError as exc:
        fail(f"ERROR KNOWLEDGE_TABLE {exc}")
    unexcused, counts, excused = settle(runs, samples, exceptions, external)
    print_summary(runs, counts)

    blocking, warnings = 0, 0
    print(f"\n{report.BOLD}Settlement{report.NC}")
    print(f"  excused by EXCEPTION:         {excused['EXCEPTION']}")
    print(f"  excused by EXPECTED_EXTERNAL: {excused['EXPECTED_EXTERNAL']}")
    for name, path, finding in unexcused:
        where = path if finding.line is None else f"{path}:{finding.line}"
        print(f"{report.RED}ERROR{report.NC} UNEXCUSED {finding.code} {where} [{name}] {finding.message}")
        blocking += 1

    def expectation(message):
        nonlocal blocking, warnings
        if drift:
            print(f"{report.YELLOW}WARN{report.NC}  {message} (downgraded: checkout drift)")
            warnings += 1
        else:
            print(f"{report.RED}ERROR{report.NC} {message}")
            blocking += 1

    for entry in exceptions:
        if not entry.used:
            expectation(f"STALE_EXCEPTION {EXCEPTIONS_FILE.name}:{entry.source_line} {entry.code} {entry.path} "
                        f"{entry.key} matches no finding")
    if unresolved != external:
        expectation(f"EXPECTED_EXTERNAL mismatch — unresolved but not listed: {sorted(unresolved - external)}; "
                    f"listed but resolved or unused: {sorted(external - unresolved)}")

    code = report.EXIT_BLOCKED if blocking else report.EXIT_WARNINGS if warnings else report.EXIT_CLEAN
    print()
    print(report.verdict_line(code))
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
