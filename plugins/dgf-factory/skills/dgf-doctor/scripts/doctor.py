#!/usr/bin/env python3
"""doctor.py — is this plugin installed correctly, and what can it see?

A structural check of the dgf-factory plugin itself. It answers installability,
not completeness: a correct-but-unfinished plugin exits 0. Milestones still to
come are reported as INFO lines that never touch the exit code, so this stays
green from milestone 6 through 15 and a red result keeps meaning something.

It is a runtime validator — the /dgf-doctor skill calls it, and so does
tools/check-dual-schema-docs.sh. It reads and reports; it never edits.

Sections: 1 manifest, 2 component paths, 3 skill slices (frontmatter YAML-safe),
4 portability (machine paths, DGF repository paths and dangling
${CLAUDE_PLUGIN_ROOT} paths in shipped files), 5 line endings, 6 validator
runtime (lxml and jsonschema importable, scripts/requirements.txt pinned with
hashes, every machine-read knowledge table loads), 7 build progress (INFO only).
It stays stdlib-only, so it runs before the validators' dependencies are
installed (ADR 0015 §8); it reports a missing dependency, and installs nothing.

Sections 1–6 are checks, and all six are required: one that cannot run — no
usable manifest, no skills/, no scripts/ — is `NOT RUN` with its reason, never
a silent pass. (A copy without scripts/ is reported so only by another copy's
doctor: its own has no builder, and exits 3.) The summary prints `CHECKS RUN:`
and `NOT RUN:` lines.

The output ends with one `dgf-gate-result` block, built by scripts/lib/gate_result.py
(ADR 0022): gate `doctor`; errors in `blockers`; warnings, and a
`not-run-<section>` entry per section that did not run, in `warnings`;
`blocking` only on a fail; `checks_run` naming the sections that ran; and
`suggested_next.command` always null, since a broken install is fixed by hand.
There is no `schema_family`, `affected_components` or `affected_processes`: the
doctor reads no estate. The builder is loaded by path from this script's own
plugin, never from the root it checks.

Usage:  doctor.py [<plugin-root>]
        DEBUG=1 doctor.py            # per-check trace

With no argument the plugin root is resolved from this file's location, never
from the working directory.

Exit codes (contract, see .ai-factory/rules/base.md):
  0  CLEAN     — no findings
  1  BLOCKED   — the plugin cannot load, a slice will not register or has
                 frontmatter YAML reads differently, a shipped file names a
                 DGF repository path or a plugin path that does not exist, the validator
                 requirements are unpinned, or a knowledge table is malformed
  2  WARNINGS  — it loads, but something needs a human look (including
                 validator dependencies that are not installed), or a section
                 could not run
  3  usage error, or this plugin's own scripts/lib/gate_result.py is missing or
     does not load — no block is printed, and a caller reads that as a gate
     that did not run
"""

import importlib.util
import json
import os
import re
import sys
from pathlib import Path

# --- colours (defined once, disabled when not a terminal) --------------------
if sys.stdout.isatty():
    RED = "\033[0;31m"
    YELLOW = "\033[0;33m"
    GREEN = "\033[0;32m"
    BOLD = "\033[1m"
    NC = "\033[0m"
else:
    RED = YELLOW = GREEN = BOLD = NC = ""

# Component keys with working defaults. Declaring one is optional; declaring one
# badly breaks the install, which is why they are validated when present.
COMPONENT_KEYS = ("skills", "agents", "commands", "hooks", "mcpServers")

# Directories shipped to whoever installs the plugin. `.claude/` is excluded on
# purpose: the aif-* corpus there is installer-managed and is not shipped. So are
# `tools/` and `provenance/`: maintainer checks and source ledgers (ADR 0012).
SHIPPED_DIRS = ("skills", "agents", "commands", "scripts", "knowledge", ".claude-plugin")

# Built in pieces so this file does not match its own portability check.
_SEP = "/"
ABSOLUTE_PATH_MARKERS = (_SEP + "Users" + _SEP, _SEP + "home" + _SEP, "~" + _SEP)

# A path into the DGF framework repository (ADR 0012). A developer's install has
# no DGF checkout, so a shipped file that names one points at nothing. The folder
# lists are DGF's top-level `src/` and `docs/` entries, read at commit aa1d5c4c2;
# `docs/adr` is left out because this plugin has a `docs/adr` of its own. Built in
# pieces, like the markers above. tools/vendor_schemas.py imports this pattern, so
# there is one definition.
_DGF_SRC = ("Components", "Core", "DGE.Office", "DGF.API", "DGF.Tests", "DGF.UI",
            "PlatformServices", "Plugins", "Tools", "samples", "tests")
_DGF_SRC_FILES = ("Directory.Build.props", "Directory.Packages.props", "global.json")
_DGF_DOCS = ("Components", "Presentations", "Release-notes", "Research", "analysis",
             "schemas", "wiki")
_DGF_MCP_SCHEMAS = ("Json", "XSD", "XmlReference")


def _alternatives(prefix, names, suffix=""):
    return prefix + _SEP + "(?:" + "|".join(re.escape(n) + suffix for n in names) + ")"


# The lookbehind admits a JSON string escape such as `\n` right before the path:
# vendored schemas write "…docs at\n<path>" inside one string.
DGF_PATH_PATTERN = re.compile(
    r"(?:(?<![\w.-])|(?<=\\[nrt]))(?:"
    + _alternatives("src", _DGF_SRC, _SEP) + "|"
    + _alternatives("src", _DGF_SRC_FILES) + "|"
    + _alternatives("docs", _DGF_DOCS, _SEP) + "|"
    + _alternatives("Schemas", _DGF_MCP_SCHEMAS, _SEP)
    + ")"
    + "|_?" + "DotGov" + "Framework" + _SEP
)

# The validators' third-party dependencies (ADR 0015): import name per package.
VALIDATOR_DEPENDENCIES = ("lxml", "jsonschema")
PINNED_REQUIREMENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*==[^\s;\\]+")
REQUIREMENT_HASH = re.compile(r"--hash=sha256:[0-9a-f]{64}")

NAME_PATTERN = re.compile(r"[a-z][a-z0-9]*(-[a-z0-9]+)*\Z")
SEMVER_PATTERN = re.compile(r"\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?\Z")

# Slices the roadmap calls for, in roadmap order. Absent ones are progress, not faults.
EXPECTED_SLICES = ("dgf-doctor", "dgf", "dgf-plan", "dgf-implement", "dgf-verify", "dgf-commit",
                   "dgf-fix", "dgf-evolve", "dgf-component", "dgf-process", "dgf-audit", "dgf-model")

# `${CLAUDE_PLUGIN_ROOT}/<path>` in shipped Markdown. The token ends at whitespace, a
# quote, a backtick, `)` or `]`; one with `<`, `*`, `{`, a second `$` or an ellipsis is
# a template.
PLUGIN_ROOT_TOKEN = "${" + "CLAUDE_PLUGIN_ROOT}"
PLUGIN_PATH = re.compile(re.escape(PLUGIN_ROOT_TOKEN) + r"(/[^\s'\"`)\]]*)?")
TEMPLATE_MARKERS = ("<", "*", "{", "$", "\u2026", "...")

# A frontmatter value the flat parser reads as one string, but YAML reads otherwise:
# an unquoted value starting with a flow, anchor, alias, tag, directive, reserved or
# block-scalar indicator, or holding `: ` or ` #`.
YAML_UNSAFE_START = tuple("[{*&!%@`|>")

# The six checks, all required (ADR 0022 §4). Build progress is INFO, not a check.
SECTIONS = ("manifest", "component-paths", "skill-slices", "portability", "line-endings", "validator-runtime")
GATE_ID = "doctor"
BUILDER_API = ("GateContractError", "build", "entry", "not_run", "render")

FINDINGS = []
INFOS = []
CHECKS_RUN = []
NOT_RUN = []  # (section id, reason) pairs


def fail(code, message):
    """The single bail-out path. Errors go to stderr, never to the report."""
    print(message, file=sys.stderr)
    raise SystemExit(code)


def error(finding_id, rel_path, summary):
    FINDINGS.append({"id": finding_id, "severity": "error", "file": rel_path, "summary": summary})
    print(f"{RED}ERROR{NC} {summary}")


def warn(finding_id, rel_path, summary):
    FINDINGS.append({"id": finding_id, "severity": "warning", "file": rel_path, "summary": summary})
    print(f"{YELLOW}WARN{NC}  {summary}")


def info(summary):
    INFOS.append(summary)
    print(f"INFO  {summary}")


def trace(message):
    if os.environ.get("DEBUG") or os.environ.get("LOG_LEVEL") == "debug":
        print(f"  · {message}")


def ran(section_id):
    if section_id not in CHECKS_RUN:
        CHECKS_RUN.append(section_id)


def not_run(section_id, reason):
    """A required section that could not run — reported, never passed silently."""
    NOT_RUN.append((section_id, reason))
    trace(f"NOT RUN: {section_id} ({reason})")


def section(title):
    print(f"\n{BOLD}{title}{NC}")


def relpath(root, path):
    try:
        return str(Path(path).relative_to(root))
    except ValueError:
        return str(path)


def json_type_name(value):
    """JSON's name for a decoded value — the report is about a JSON file, not Python."""
    names = {type(None): "null", bool: "boolean", int: "number",
             float: "number", str: "string", list: "array", dict: "object"}
    return names.get(type(value), type(value).__name__)


def read_text(path):
    """Decoded file contents, or None when the file is binary or unreadable."""
    try:
        return path.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def is_bytecode(path):
    """Python writes these next to scripts it runs; they are never shipped content."""
    return "__pycache__" in path.parts or path.suffix == ".pyc"


def shipped_files(root):
    """Every regular file under the shipped directories, in a stable order.

    Bytecode is skipped: running a validator writes scripts/lib/__pycache__ on a
    contributor's tree and on an installed copy alike, and marshalled bytecode can
    hold the bytes of a CRLF or a path.
    """
    skipped = 0
    for name in SHIPPED_DIRS:
        base = root / name
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            if is_bytecode(path):
                skipped += 1
                continue
            yield path
    trace(f"skipped {skipped} bytecode file(s)")


def parse_frontmatter(text):
    """The flat key/value block between the leading `---` fences.

    Deliberately not a YAML parser: the SKILL.md contract is a handful of flat
    scalar keys, and depending on pyyaml would put a third-party import in a
    validator that must run anywhere.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    fields = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return fields
        key, sep, value = line.partition(":")
        if sep and not key.startswith((" ", "\t", "#")):
            fields[key.strip()] = value.strip()
    return None  # unterminated block


# --- 1. manifest -------------------------------------------------------------

def check_manifest(root):
    """Returns the parsed manifest, or None when it cannot be used."""
    section("1. Manifest")
    ran("manifest")
    rel = f".claude-plugin{_SEP}plugin.json"
    path = root / ".claude-plugin" / "plugin.json"
    trace(f"manifest: {path}")

    if not path.is_file():
        error("MANIFEST_MISSING", rel, f"{rel} not found — the plugin cannot load")
        return None

    manifest = load_manifest(path, rel)
    if manifest is None:
        return None

    check_manifest_fields(root, manifest, rel)
    trace(f"manifest keys: {', '.join(sorted(manifest))}")
    return manifest


def load_manifest(path, rel):
    """The manifest as a dict, or None — having reported exactly why.

    Every unusable outcome must report before returning. `None` is not a safe
    sentinel for "unreadable" on its own: read_text() returns it for an
    undecodable file and json.loads("null") returns it for a well-formed one,
    so a single `is None` branch once swallowed both — a manifest the plugin
    cannot load, reported as CLEAN.
    """
    text = read_text(path)
    if text is None:
        error("MANIFEST_UNPARSEABLE", rel, f"{rel} is not readable as UTF-8 text")
        return None

    try:
        manifest = json.loads(text)
    except json.JSONDecodeError as exc:
        error("MANIFEST_UNPARSEABLE", rel, f"{rel} is not valid JSON: {exc}")
        return None

    if not isinstance(manifest, dict):
        error("MANIFEST_UNPARSEABLE", rel,
              f"{rel} must contain a JSON object, not {json_type_name(manifest)}")
        return None
    return manifest


def check_manifest_fields(root, manifest, rel):
    name = manifest.get("name")
    if not name:
        error("MANIFEST_NAME_MISSING", rel, f"{rel} has no `name` — the plugin cannot load")
    elif name != root.name:
        error("MANIFEST_NAME_MISMATCH", rel,
              f"{rel} name `{name}` does not match the directory `{root.name}`")
    elif not NAME_PATTERN.match(name):
        error("MANIFEST_NAME_INVALID", rel, f"{rel} name `{name}` is not kebab-case")

    version = manifest.get("version")
    if version is not None and not SEMVER_PATTERN.match(str(version)):
        error("MANIFEST_VERSION_INVALID", rel, f"{rel} version `{version}` is not semver")


# --- 2. component paths ------------------------------------------------------

def check_component_paths(root, manifest):
    section("2. Component paths")
    if manifest is None:
        not_run("component-paths", "no usable manifest")
        return
    ran("component-paths")

    declared = [key for key in COMPONENT_KEYS if key in manifest]
    if not declared:
        trace("no component keys declared; defaults apply")
        info("no component paths declared — the defaults apply")
        return

    for key in declared:
        value = manifest[key]
        entries = value if isinstance(value, list) else [value]
        for entry in entries:
            check_component_path(root, key, entry)


def check_component_path(root, key, entry):
    rel = f".claude-plugin{_SEP}plugin.json"
    if not isinstance(entry, str):
        error("COMPONENT_PATH_TYPE", rel, f"`{key}` must be a string or a list of strings")
        return

    trace(f"{key}: {entry}")
    if entry.startswith(_SEP) or entry.startswith("~") or re.match(r"[A-Za-z]:", entry):
        error("COMPONENT_PATH_ABSOLUTE", rel, f"`{key}` path `{entry}` is absolute")
        return
    if "\\" in entry:
        error("COMPONENT_PATH_SEPARATOR", rel, f"`{key}` path `{entry}` must use forward slashes")
        return
    if ".." in Path(entry).parts:
        error("COMPONENT_PATH_ESCAPES", rel, f"`{key}` path `{entry}` escapes the plugin root")
        return
    if not entry.startswith("." + _SEP):
        error("COMPONENT_PATH_UNANCHORED", rel, f"`{key}` path `{entry}` must start with ./")
        return
    if not (root / entry).exists():
        error("COMPONENT_PATH_MISSING", rel, f"`{key}` path `{entry}` does not exist")


# --- 3. skill slices ---------------------------------------------------------

def check_skill_slices(root):
    section("3. Skill slices")
    skills_dir = root / "skills"
    if not skills_dir.is_dir():
        not_run("skill-slices", f"no skills{_SEP} directory")
        return
    ran("skill-slices")

    slices = sorted(path for path in skills_dir.iterdir() if path.is_dir())
    if not slices:
        trace("skills/ is empty")
        return

    for slice_dir in slices:
        check_skill_slice(root, slice_dir)


def check_skill_slice(root, slice_dir):
    skill_file = slice_dir / "SKILL.md"
    rel = relpath(root, skill_file)
    trace(f"slice: {rel}")

    if not skill_file.is_file():
        error("SKILL_FILE_MISSING", relpath(root, slice_dir),
              f"{slice_dir.name}{_SEP} has no SKILL.md — the skill will not register")
        return

    text = read_text(skill_file)
    fields = parse_frontmatter(text) if text is not None else None
    if fields is None:
        error("SKILL_FRONTMATTER_MISSING", rel, f"{rel} has no closed YAML frontmatter block")
        return

    check_frontmatter_yaml(rel, fields)
    name = fields.get("name", "")
    if name != slice_dir.name:
        error("SKILL_NAME_MISMATCH", rel,
              f"{rel} name `{name}` does not match its directory `{slice_dir.name}`")
    if not fields.get("description"):
        error("SKILL_DESCRIPTION_MISSING", rel, f"{rel} has an empty `description`")
    if not fields.get("allowed-tools"):
        error("SKILL_TOOLS_MISSING", rel, f"{rel} declares no `allowed-tools`")


def yaml_unsafe(value):
    """Why YAML would not read `value` as the plain string the flat parser sees, or None."""
    if not value:
        return None
    if value[0] in "\"'":
        return None if len(value) > 1 and value.endswith(value[0]) else "opens a quote it never closes"
    if value.startswith("- "):
        return "starts with `- `, which YAML reads as a list item"
    if value.endswith(":"):
        return "ends with `:`, which YAML reads as a mapping key"
    if value.startswith(YAML_UNSAFE_START):
        return f"starts with `{value[0]}`"
    if ": " in value:
        return "contains `: `"
    if " #" in value:
        return "contains ` #`, which YAML reads as a comment"
    return None


def check_frontmatter_yaml(rel, fields):
    """Claude Code reads the block as YAML; the doctor reads it flat. They must agree."""
    for key, value in fields.items():
        why = yaml_unsafe(value)
        trace(f"{rel}: `{key}` yaml-safe={why is None}")
        if why:
            error("SKILL_FRONTMATTER_YAML", rel,
                  f"{rel} `{key}` {why} — YAML reads it differently or not at all, so the skill may not "
                  "load; quote the value")


# --- 4. portability ----------------------------------------------------------

def check_portability(root):
    section("4. Portability")
    ran("portability")
    for path in shipped_files(root):
        text = read_text(path)
        if text is None:
            continue
        rel = relpath(root, path)
        for lineno, line in enumerate(text.splitlines(), 1):
            marker = next((m for m in ABSOLUTE_PATH_MARKERS if m in line), None)
            if marker:
                warn("ABSOLUTE_PATH", rel,
                     f"{rel}:{lineno} contains `{marker}` — breaks for other users")
            match = DGF_PATH_PATTERN.search(line)
            if match:
                error("DGF_PATH", rel,
                      f"{rel}:{lineno} names DGF repository path `{match.group(0)}…` — "
                      "a developer's install has no DGF checkout (ADR 0012)")
            if path.suffix == ".md":
                check_plugin_paths(root, rel, lineno, line)
    trace("scanned shipped files for machine-specific, DGF repository and dangling plugin paths")


def exists_exact(root, rel):
    """True when every segment of `rel` exists under `root` in exactly this case.

    Path.exists() matches regardless of case on APFS and NTFS; the plugin runs on
    Linux too, where a wrong-case path does not resolve.
    """
    current = Path(root)
    for part in [p for p in rel.split(_SEP) if p]:
        try:
            names = os.listdir(current)
        except OSError:
            return False
        if part not in names:
            return False
        current = current / part
    return True


def check_plugin_paths(root, rel, lineno, line):
    """Every `${CLAUDE_PLUGIN_ROOT}/<path>` a shipped Markdown file cites must exist."""
    for match in PLUGIN_PATH.finditer(line):
        target = (match.group(1) or "").rstrip(".,;:")
        if any(marker in target for marker in TEMPLATE_MARKERS):
            trace(f"{rel}:{lineno} template `{PLUGIN_ROOT_TOKEN}{target}` skipped")
            continue
        exists = exists_exact(root, target.lstrip(_SEP))
        trace(f"{rel}:{lineno} `{PLUGIN_ROOT_TOKEN}{target}` exists={exists}")
        if not exists:
            error("PLUGIN_PATH_DANGLING", rel,
                  f"{rel}:{lineno} cites `{PLUGIN_ROOT_TOKEN}{target}`, which does not exist in the plugin")


# --- 5. line endings ---------------------------------------------------------

def check_line_endings(root):
    section("5. Line endings")
    ran("line-endings")
    for path in shipped_files(root):
        try:
            if b"\r\n" in path.read_bytes():
                rel = relpath(root, path)
                warn("CRLF", rel, f"{rel} has CRLF line endings — breaks shebangs and heredocs")
        except OSError:
            continue
    trace("scanned shipped files for CRLF")


# --- 6. validator runtime ----------------------------------------------------

def check_validator_runtime(root):
    section("6. Validator runtime")
    scripts_dir = root / "scripts"
    if not scripts_dir.is_dir():
        not_run("validator-runtime", f"no scripts{_SEP} directory — no validators to check")
        return
    ran("validator-runtime")
    check_validator_dependencies(root)
    check_requirement_pins(root)
    check_knowledge_tables(root)


def install_command(root):
    user = "" if sys.prefix != sys.base_prefix else " --user"
    requirements = root / "scripts" / "requirements.txt"
    return f'python3 -m pip install{user} --require-hashes -r "{requirements}"'


def check_validator_dependencies(root):
    absent = [name for name in VALIDATOR_DEPENDENCIES if importlib.util.find_spec(name) is None]
    trace(f"dependency probe: missing={','.join(absent) or 'none'} python={sys.version.split()[0]}")
    if absent:
        warn("VALIDATOR_DEPS_MISSING", f"scripts{_SEP}requirements.txt",
             f"{', '.join(absent)} not installed — the validators exit 3 until they are. "
             f"Install with: {install_command(root)}")
        return
    info("validator dependencies — lxml and jsonschema import")


def requirement_entries(text):
    """Logical requirement lines: continuations joined, comments and blanks dropped."""
    entries, current = [], ""
    for line in text.splitlines():
        stripped = line.strip()
        if not current and (not stripped or stripped.startswith("#")):
            continue
        current += " " + stripped.rstrip("\\").strip()
        if not stripped.endswith("\\"):
            entries.append(current.strip())
            current = ""
    if current:
        entries.append(current.strip())
    return entries


def check_requirement_pins(root):
    rel = f"scripts{_SEP}requirements.txt"
    path = root / "scripts" / "requirements.txt"
    if not path.is_file():
        error("REQUIREMENTS_UNPINNED", rel, f"{rel} is missing — the validators' dependencies are unpinned")
        return
    text = read_text(path)
    if text is None:
        error("REQUIREMENTS_UNPINNED", rel, f"{rel} is not readable as UTF-8 text")
        return
    entries = requirement_entries(text)
    trace(f"{rel}: {len(entries)} requirement(s)")
    for entry in entries:
        name = entry.split()[0]
        if not PINNED_REQUIREMENT.match(entry):
            error("REQUIREMENTS_UNPINNED", rel, f"{rel}: `{name}` is not pinned as name==version")
        elif not REQUIREMENT_HASH.search(entry):
            error("REQUIREMENTS_UNPINNED", rel, f"{rel}: `{name}` has no --hash=sha256")


def load_lib_module(root, name):
    """scripts/lib/<name>.py under `root`, loaded by path — it imports nothing from its package.

    None when the file is absent. knowledge.py and gate_result.py are both
    stdlib-only for this reason: a relative import cannot resolve here.
    """
    path = root / "scripts" / "lib" / f"{name}.py"
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location(f"dgf_doctor_{name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_knowledge_tables(root):
    try:
        module = load_lib_module(root, "knowledge")
    except (OSError, SyntaxError, ImportError) as exc:
        error("KNOWLEDGE_TABLE", f"scripts{_SEP}lib{_SEP}knowledge.py",
              f"scripts{_SEP}lib{_SEP}knowledge.py cannot be loaded: {exc}")
        return
    if module is None:
        trace("no scripts/lib/knowledge.py — no machine-read tables to check")
        return
    for table_id in module.TABLES:
        try:
            rows = module.load(table_id, root / "knowledge")
        except module.KnowledgeTableError as exc:
            error("KNOWLEDGE_TABLE", f"knowledge{_SEP}{module.TABLES[table_id][0]}", str(exc))
            continue
        trace(f"table {table_id}: {len(rows)} row(s)")
    info(f"machine-read knowledge tables — {len(module.TABLES)} checked")


# --- 7. build progress (INFO only — never affects the exit code) -------------

def report_build_progress(root):
    section("7. Build progress")
    for name in ("knowledge", "scripts", "agents"):
        state = "present" if (root / name).is_dir() else "not yet built"
        info(f"{name}{_SEP} — {state}")

    skills_dir = root / "skills"
    for slice_name in EXPECTED_SLICES:
        state = "present" if (skills_dir / slice_name).is_dir() else "not yet built"
        info(f"skills{_SEP}{slice_name}{_SEP} — {state}")
    trace("build progress is informational; it does not affect the exit code")


# --- reporting ---------------------------------------------------------------

def load_gate_builder():
    """scripts/lib/gate_result.py from this script's own plugin — never from the root it checks.

    The builder is the doctor's machinery, not the thing checked. When it is
    missing or does not load, exit 3 with no block: a caller reads a missing
    block as a gate that did not run.
    """
    own_root = Path(__file__).resolve().parents[3]
    path = own_root / "scripts" / "lib" / "gate_result.py"
    try:
        module = load_lib_module(own_root, "gate_result")
    except Exception as exc:  # whatever the file raises while it loads, the builder did not load
        fail(3, f"{path} cannot be loaded: {exc!r} — the gate block cannot be built; reinstall the plugin")
    if module is None:
        fail(3, f"{path} is missing — the gate block cannot be built; reinstall the plugin")
    absent = [name for name in BUILDER_API if not hasattr(module, name)]
    if absent:
        fail(3, f"{path} has no {', '.join(absent)} — the gate block cannot be built; reinstall the plugin")
    trace(f"gate: loaded {path}")
    return module


def gate_block(gate, status, errors):
    """The machine-readable verdict, built by gate_result.py. Emitted last; nothing may follow it.

    `schema_family`, `affected_components` and `affected_processes` are left
    out: this gate reads no DGF configuration, and a field it never computed
    must not read as "none" (ADR 0022 §7).
    """
    blockers = [gate.entry(f["id"], f["severity"], f["summary"], file=f["file"])
                for f in FINDINGS if f["severity"] == "error"]
    warnings = [gate.entry(f["id"], f["severity"], f["summary"], file=f["file"])
                for f in FINDINGS if f["severity"] == "warning"]
    warnings += [gate.not_run(section_id, reason) for section_id, reason in NOT_RUN]
    if status == "fail":
        reason = f"{errors} blocking finding(s) — the plugin is not fit to install; fix them by hand and re-run"
    elif status == "warn":
        reason = f"{len(warnings)} warning(s) — the plugin loads but is not clean; fix them by hand and re-run"
    else:
        reason = "no findings; nothing to fix"
    try:
        payload = gate.build(GATE_ID, blockers, warnings, None, reason, checks_run=CHECKS_RUN, required=SECTIONS)
    except gate.GateContractError as exc:
        fail(3, f"the doctor built a contradictory gate block: {exc}")
    print()
    print(gate.render(payload))


def report(root):
    gate = load_gate_builder()
    errors = sum(1 for f in FINDINGS if f["severity"] == "error")
    warnings = sum(1 for f in FINDINGS if f["severity"] == "warning")

    section("Summary")
    print(f"Root:     {root}")
    print(f"CHECKS RUN: {', '.join(CHECKS_RUN) if CHECKS_RUN else '(none)'}")
    for section_id, reason in NOT_RUN:
        print(f"NOT RUN: {section_id} ({reason})")
    print(f"Errors:   {errors}")
    print(f"Warnings: {warnings}")
    print(f"Info:     {len(INFOS)}")

    if errors:
        print(f"\n{RED}BLOCKED{NC}")
        code, status = 1, "fail"
    elif warnings or NOT_RUN:
        print(f"\n{YELLOW}WARNINGS{NC}")
        code, status = 2, "warn"
    else:
        print(f"\n{GREEN}CLEAN{NC}")
        code, status = 0, "pass"

    gate_block(gate, status, errors)
    return code


def resolve_root(argv):
    if len(argv) > 1:
        fail(3, f"Usage: {Path(argv[0]).name} [<plugin-root>]   (DEBUG=1 for a per-check trace)")
    if not argv:
        # skills/<slice>/scripts/doctor.py — never the working directory.
        return Path(__file__).resolve().parents[3]

    root = Path(argv[0]).expanduser().resolve()
    if not root.is_dir():
        fail(3, f"Not a directory: {root}")
    if not (root / ".claude-plugin").is_dir():
        fail(3, f"Not a plugin root (no .claude-plugin{_SEP}): {root}")
    return root


def main(argv):
    root = resolve_root(argv[1:])

    print(f"{BOLD}Plugin structure check{NC}")
    print(f"Root: {root}")

    manifest = check_manifest(root)
    check_component_paths(root, manifest)
    check_skill_slices(root)
    check_portability(root)
    check_line_endings(root)
    check_validator_runtime(root)
    report_build_progress(root)

    return report(root)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
