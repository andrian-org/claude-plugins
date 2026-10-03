#!/usr/bin/env python3
"""design.py — check a new application's design, and say what is still open (ADR 0027 §7.3).

The /dgf-scaffold skill writes `docs/application.json` from the request and the survey;
this script decides everything about it that a script can decide, so the model only
designs and asks. It is the generator's only gate: generate.py refuses to run unless this
exits 0.

  1  the folder is empty — nothing but `.git/` and `docs/application.json` (--empty-only stops here)
  2  the design parses: `design_format` 1, no unknown key at any level, every value the right JSON type
  3  every required value is present, else one SCAFFOLD_ASK; every defaulted value is one `DEFAULT:` line
  4  names: identifiers, lower-case instance names, roles, routes; unique ignoring case
  5  references: deployments, modules, extracts, keys
  6  the data model, and each column's SQL type
  7  options against the knowledge tables (auth-schemes, instance-models, field-types, db-types, field-sql-types)
  8  the base workspace exists, by exact case

Usage:  design.py --folder <dir> [--empty-only] [--verbose]

Exit codes (contract, see .ai-factory/rules/base.md):
  0  complete — nothing is open, nothing conflicts
  1  conflict — the folder is not empty, or a name, option, reference or the model is wrong
  2  questions remain — every SCAFFOLD_ASK names a key, its rule and its candidates
  3  the design cannot be read, or a usage error

It loads scripts/lib/report.py and scripts/lib/knowledge.py by path (they import nothing from
their package) and needs neither lxml nor jsonschema.
"""

import argparse
import copy
import importlib.util
import json
import os
import re
import stat
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[3]
LIB = PLUGIN_ROOT / "scripts" / "lib"


def _load(name):
    spec = importlib.util.spec_from_file_location(f"dgf_scaffold_{name}", LIB / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


report = _load("report")
knowledge = _load("knowledge")

DESIGN = Path("docs") / "application.json"
MAX_BYTES = 1024 * 1024
DESIGN_FORMAT = 1

IDENT = re.compile(r"[A-Za-z][A-Za-z0-9_]*\Z")
LOWER = re.compile(r"[a-z][a-z0-9]*\Z")
VERSION = re.compile(r"\d+\.\d+\.\d+(?:[-+.][0-9A-Za-z.-]+)?\Z")
ROUTE = re.compile(r"/[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*\Z")
SURROGATE = re.compile("[\ud800-\udfff]")
FOLDER_UNSAFE = re.compile(r'[/\\:*?"<>|]')  # a role names a profile folder, so it must be a folder name on every system
NAME_MAX = 64
INSTANCE_MAX = 40
TITLE_MAX = 200

RESERVED_ROUTES = {"/login", "/home", "/user-profile", "/app-menu"}  # the last is the route of the workspace's menu
RESERVED_MODULES = {"home", "login", "loginpage"}  # the pages every workspace carries
FRAMEWORK_PREFIXES = ("ax_", "aspnet", "zigs_", "prc_", "dgf_demo_")  # tables the baseline owns
BUILT_IN_ROLES = ("Administrators", "Members", "Anonymous", "Registered Users", "PortalUser")
PATTERNS = ("register", "service", "page")
SUPPLIES = ("copy", "mount")
SOURCES = ("prompt", "asked", "default")

# The types version 1 generates, and the dbtypes each takes: the pairs the samples use (data-model.md §6).
TYPE_DBTYPES = {
    "Text": ("String", "StringUnicode"),
    "Integer": ("Int16", "Int32", "Int64"),
    "Float": ("Double", "Decimal"),
    "Money": ("Decimal",),
    "Boolean": ("Boolean",),
    "DateTime": ("DateTime", "DateTimeOffset"),
    "Lookup": ("Guid", "Int16", "Int32", "Int64", "String", "StringUnicode"),
    "Picklist": ("Guid", "Int16", "Int32", "Int64", "String", "StringUnicode"),
    "Html": ("String", "StringUnicode"),
}
NOT_GENERATED = {
    "PrimaryKey": "the vendored settings.xsd lacks it, so every file would warn XSD_LAGS_RUNTIME",
    "Checkboxlist": "the vendored settings.xsd lacks it, so every file would warn XSD_LAGS_RUNTIME",
    "EditableGrid": "version 1 generates no slave grid",
    "Image": "version 1 generates no binary column",
}
STRING_DBTYPES = ("String", "StringUnicode")
SIZE_LIMIT = {"String": 8000, "StringUnicode": 4000}
MAX_SIZE = 2147483647  # how a settings file spells a (MAX) column's size

ALLOWED = {
    "top": ("design_format", "application", "dgf_version", "instance_model", "workspace", "instances", "apis",
            "roles", "base", "modules", "data_model", "sources"),
    "application": ("name", "title"),
    "instance": ("name", "title"),
    "api": ("name", "deployments"),
    "deployment": ("name", "instance", "auth"),
    "base": ("source", "supply"),
    "module": ("name", "pattern", "title", "entity", "route", "roles"),
    "data_model": ("entities",),
    "entity": ("name", "title", "key", "fields"),
    "field": ("name", "title", "type", "dbtype", "size", "required", "precision", "scale", "extract"),
    "extract": ("entity", "view"),
}


def fail(message):
    print(message, file=sys.stderr)
    raise SystemExit(report.EXIT_USAGE)


class Parser(argparse.ArgumentParser):
    def error(self, message):  # usage errors exit 3, as every script's do
        fail(f"{self.prog}: {message}")


class Unreadable(Exception):
    pass


class Result:
    """What one check found: the resolved design, and the three kinds of finding."""

    def __init__(self, folder):
        self.folder = folder
        self.rep = report.Report(str(DESIGN))
        self.design = None
        self.asks = []
        self.defaults = []
        self.conflicts = 0

    def add(self, code, message):
        self.rep.add(code, message)
        if report.CODES[code] == report.EXIT_BLOCKED:
            self.conflicts += 1

    def ask(self, key, rule, candidates=()):
        text = f"{key} — {rule}" + (f" (candidates: {', '.join(candidates)})" if candidates else "")
        self.rep.add("SCAFFOLD_ASK", text)
        self.asks.append(key)
        report.debug("design.check", "value", key=key, state="open")

    def default(self, key, value):
        self.defaults.append((key, value))
        report.debug("design.check", "value", key=key, state="default")

    @property
    def exit_code(self):
        return self.rep.exit_code()


# --- the folder --------------------------------------------------------------

def entries(path):
    """The exact-case names in a directory, from os.scandir — never Path.exists()."""
    with os.scandir(path) as it:
        return {entry.name: entry for entry in it}


def check_folder(folder, result):
    """The folder holds nothing but `.git/` and `docs/application.json` (D2)."""
    result.rep.ran("folder")
    if not folder.exists():
        report.debug("design.check", "value", key="folder", state="absent")
        return
    if not folder.is_dir():
        fail(f"not a directory: {folder}")
    extra = []
    for name, entry in sorted(entries(folder).items()):
        if name == ".git" and entry.is_dir(follow_symlinks=False):
            continue
        if name == "docs" and entry.is_dir(follow_symlinks=False):
            inner = entries(folder / "docs")
            for inner_name, inner_entry in sorted(inner.items()):
                if not (inner_name == "application.json" and inner_entry.is_file(follow_symlinks=False)):
                    extra.append(f"docs/{inner_name}")
            continue
        extra.append(name)
    if extra:
        shown = ", ".join(report.one_line(name) for name in extra[:5])
        more = f" and {len(extra) - 5} more" if len(extra) > 5 else ""
        result.add("SCAFFOLD_DIR_NOT_EMPTY",
                   f"the folder is not empty ({shown}{more}); this command only creates a new application")


# --- reading -----------------------------------------------------------------

def _no_duplicates(pairs):
    seen = {}
    for key, value in pairs:
        if key in seen:
            raise ValueError(f"duplicate key {key!r}")
        seen[key] = value
    return seen


def _no_constant(name):
    raise ValueError(f"{name} is not JSON")


def read_design(folder):
    """The parsed design, bounded and defensive (patch 2026-09-26-21.53); Unreadable otherwise."""
    path = folder / DESIGN
    try:
        info = os.lstat(path)
    except OSError as error:
        raise Unreadable(f"cannot open {DESIGN}: {error.strerror}")
    if not stat.S_ISREG(info.st_mode):
        raise Unreadable(f"{DESIGN} is not a regular file")
    if info.st_size > MAX_BYTES:
        raise Unreadable(f"{DESIGN} is larger than {MAX_BYTES} bytes")
    try:
        with open(path, "rb") as handle:
            data = handle.read(MAX_BYTES + 1)
    except OSError as error:
        raise Unreadable(f"cannot read {DESIGN}: {error.strerror}")
    if len(data) > MAX_BYTES:
        raise Unreadable(f"{DESIGN} is larger than {MAX_BYTES} bytes")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise Unreadable(f"{DESIGN} is not UTF-8: {error.reason} at byte {error.start}")
    try:
        design = json.loads(text, object_pairs_hook=_no_duplicates, parse_constant=_no_constant)
    except RecursionError:
        raise Unreadable(f"{DESIGN} is nested too deeply")
    except ValueError as error:
        raise Unreadable(f"{DESIGN} is not JSON: {error}")
    if not isinstance(design, dict):
        raise Unreadable(f"{DESIGN} is not a JSON object")
    report.debug("design.read", "read", path=path, bytes=len(data), format=design.get("design_format"))
    return design


def kind_of(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    return {str: "string", list: "list", dict: "object"}.get(type(value), type(value).__name__)


class Reader:
    """Typed access to the parsed design: a wrong JSON type is a conflict, never a lookup key."""

    def __init__(self, result):
        self.result = result

    def known(self, obj, level, where):
        for key in obj:
            if key not in ALLOWED[level]:
                self.result.add("SCAFFOLD_OPTION_INVALID", f"{where}: unknown key `{report.one_line(key)}`")

    def get(self, obj, key, kind, where):
        """obj[key] when it is a `kind`; None when absent or of the wrong type (the latter is a conflict)."""
        if key not in obj:
            return None
        value = obj[key]
        if kind_of(value) != kind or (kind == "number" and (isinstance(value, float) or isinstance(value, bool))):
            self.result.add("SCAFFOLD_OPTION_INVALID", f"{where}{key}: expected {kind}, got {kind_of(value)}")
            return None
        return value

    def objects(self, obj, key, where):
        """The list under `key` when every item is an object; wrong items are conflicts and dropped."""
        items = self.get(obj, key, "list", where)
        if items is None:
            return None
        good = []
        for index, item in enumerate(items):
            if isinstance(item, dict):
                good.append((index, item))
            else:
                self.result.add("SCAFFOLD_OPTION_INVALID",
                                f"{where}{key}[{index}]: expected object, got {kind_of(item)}")
        return good

    def strings(self, obj, key, where):
        items = self.get(obj, key, "list", where)
        if items is None:
            return None
        good = []
        for index, item in enumerate(items):
            if isinstance(item, str):
                good.append(item)
            else:
                self.result.add("SCAFFOLD_OPTION_INVALID",
                                f"{where}{key}[{index}]: expected string, got {kind_of(item)}")
        return good


# --- names -------------------------------------------------------------------

def name_ok(result, value, pattern, what, limit=NAME_MAX):
    if not isinstance(value, str) or not pattern.match(value) or len(value) > limit:
        shown = report.one_line(value if isinstance(value, str) else kind_of(value))
        rule = "a lower-case letter then lower-case letters and digits" if pattern is LOWER else \
            "a letter then letters, digits and underscores"
        result.add("SCAFFOLD_NAME_INVALID", f"{what} `{shown}` is not valid — {rule}, at most {limit} characters")
        return False
    return True


def title_ok(result, value, what):
    if (not isinstance(value, str) or not value.strip() or len(value) > TITLE_MAX or SURROGATE.search(value)
            or any(ord(ch) < 0x20 or ord(ch) == 0x7F for ch in value)):
        result.add("SCAFFOLD_NAME_INVALID", f"{what} is not a title — one non-empty line of text, at most {TITLE_MAX} characters")
        return False
    return True


def unique(result, names, what):
    """Names that collide ignoring case: APFS and NTFS would collide their files."""
    seen = {}
    for name in names:
        key = name.casefold()
        if key in seen:
            result.add("SCAFFOLD_NAME_INVALID", f"{what} `{report.one_line(name)}` and `{report.one_line(seen[key])}` differ only in case or repeat")
        else:
            seen[key] = name


def capitalise(name):
    return name[:1].upper() + name[1:]


# --- the check ---------------------------------------------------------------

def check(folder, knowledge_dir=None, empty_only=False, generated=False):
    """Run the checks in order; the Result carries the findings, the defaults and the resolved design.

    `generated` is for a folder that already holds the generated application: the design is still read
    and held to every other rule, but the folder is no longer empty, and the base workspace it named
    may not be where it was — both were checked when the application was generated.
    """
    folder = Path(folder)
    result = Result(folder)
    if not generated:
        check_folder(folder, result)
    if empty_only:
        return result

    try:
        raw = read_design(folder)
    except Unreadable as error:
        result.rep.add("SCAFFOLD_DESIGN_UNREADABLE", str(error))
        return result
    result.rep.ran("design")

    if raw.get("design_format") != DESIGN_FORMAT or isinstance(raw.get("design_format"), bool):
        result.rep.add("SCAFFOLD_DESIGN_UNREADABLE",
                       f"`design_format` is {report.one_line(json.dumps(raw.get('design_format')))}; this version reads {DESIGN_FORMAT}")
        return result

    try:
        tables = {tid: knowledge.load(tid, knowledge_dir) for tid in
                  ("auth-schemes", "instance-models", "field-types", "db-types", "field-sql-types")}
    except knowledge.KnowledgeTableError as error:
        result.rep.add("SCAFFOLD_DESIGN_UNREADABLE", str(error))
        return result

    reader = Reader(result)
    resolved = {"design_format": DESIGN_FORMAT}
    result.design = resolved
    reader.known(raw, "top", "")
    build(reader, result, raw, resolved, tables, generated)
    report.debug("design.check", "done", asks=len(result.asks), defaults=len(result.defaults),
                 conflicts=result.conflicts)
    return result


def build(reader, result, raw, out, tables, generated=False):
    """Resolve each section in turn: check it, default it or ask for it, and record the resolved value."""
    auth_schemes = [row["Provider"] for row in tables["auth-schemes"]]
    instance_models = [row["Model"] for row in tables["instance-models"]]

    # --- application
    app = reader.get(raw, "application", "object", "") or {}
    reader.known(app, "application", "application.")
    name = reader.get(app, "name", "string", "application.")
    if name is None:
        if "name" not in app:
            result.ask("application.name", "the application's name: a letter then letters, digits and underscores")
    else:
        name_ok(result, name, IDENT, "the application name")
    title = reader.get(app, "title", "string", "application.")
    if title is not None:
        title_ok(result, title, "the application title")
    elif "title" not in app and name is not None:
        title = name  # a title left out is its name — an echo, not a decision, so no DEFAULT line
    out["application"] = {"name": name, "title": title}
    result.rep.ran("names")

    # --- version
    version = reader.get(raw, "dgf_version", "string", "")
    if version is None:
        if "dgf_version" not in raw:
            result.ask("dgf_version", "the DGF.API package version to target, such as 1.1.15 — the framework pins none")
    elif not VERSION.match(version):
        result.add("SCAFFOLD_OPTION_INVALID", f"`dgf_version` `{report.one_line(version)}` is not a version such as 1.1.15")
    out["dgf_version"] = version

    # --- instances
    instances = []
    entries_ = reader.objects(raw, "instances", "")
    if entries_ is None and "instances" not in raw:
        result.ask("instances", "the application's instances: at least one, each a lower-case name and a title",
                   ("one instance named after the application",))
    for index, item in entries_ or []:
        where = f"instances[{index}]."
        reader.known(item, "instance", where)
        iname = reader.get(item, "name", "string", where)
        if iname is None:
            if "name" not in item:
                result.ask(f"instances[{index}].name", "a lower-case name: letters and digits, at most 40 characters")
            continue
        if not name_ok(result, iname, LOWER, "the instance name", INSTANCE_MAX):
            continue
        ititle = reader.get(item, "title", "string", where)
        if ititle is not None:
            title_ok(result, ititle, f"the title of instance `{iname}`")
        elif "title" not in item:
            ititle = capitalise(iname)
        instances.append({"name": iname, "title": ititle})
    if entries_ is not None and not entries_:
        result.ask("instances", "at least one instance")
    unique(result, [i["name"] for i in instances], "the instance name")
    out["instances"] = instances

    # --- instance model and workspace
    model = reader.get(raw, "instance_model", "string", "")
    if model is None and "instance_model" not in raw:
        if len(instances) == 1:
            model = "own-workspace"
            result.default("instance_model", model)
        elif len(instances) > 1:
            result.ask("instance_model", "how the instances share a workspace: `shared-workspace` mounts one "
                       "directory under every instance's name; `own-workspace` gives each its own", instance_models)
    elif model is not None and model not in instance_models:
        result.add("SCAFFOLD_OPTION_INVALID", f"`instance_model` `{report.one_line(model)}` is not one of {', '.join(instance_models)}")
    out["instance_model"] = model

    workspace = reader.get(raw, "workspace", "string", "")
    if model == "own-workspace" and "workspace" in raw:
        result.add("SCAFFOLD_OPTION_INVALID", "`workspace` names the one directory of `shared-workspace`; `own-workspace` "
                   "gives each instance a directory named after it")
    elif model == "shared-workspace":
        if workspace is None and "workspace" not in raw and name is not None:
            workspace = re.sub(r"[^a-z0-9]", "", name.lower()) or None
            if workspace and not workspace[0].isalpha():
                workspace = None
            if workspace:
                result.default("workspace", workspace)
        if workspace is not None:
            name_ok(result, workspace, LOWER, "the workspace name", INSTANCE_MAX)
    out["workspace"] = workspace if model == "shared-workspace" else None
    if model == "shared-workspace" and workspace and workspace in {i["name"] for i in instances}:
        pass  # a shared directory may share a name with an instance: it is mounted under it

    # --- roles
    roles = reader.strings(raw, "roles", "")
    if roles is None:
        roles = []
        if "roles" not in raw:
            result.default("roles", roles)
    for role in roles:
        if not role or role != role.strip() or "," in role or SURROGATE.search(role) \
                or any(ord(ch) < 0x20 or ord(ch) == 0x7F for ch in role) or len(role) > 100 \
                or FOLDER_UNSAFE.search(role) or role.endswith(".") or role in (".", ".."):
            result.add("SCAFFOLD_NAME_INVALID", f"role `{report.one_line(role)}` is not a role name — no comma, no leading or trailing space, "
                       "no / \\ : * ? \" < > |, no trailing dot, one line, at most 100 characters "
                       "(the runtime splits on `,` without trimming, and a role is also a folder name)")
    unique(result, roles, "the role")
    out["roles"] = roles
    known_roles = {r.casefold() for r in roles} | {r.casefold() for r in BUILT_IN_ROLES}

    # --- data model (needed by the modules)
    entities = data_model(reader, result, raw, tables)
    out["data_model"] = {"entities": entities}
    result.rep.ran("model")
    entity_names = {e["name"] for e in entities}

    # --- apis and deployments
    apis = []
    api_items = reader.objects(raw, "apis", "")
    if api_items is None and "apis" not in raw and instances:
        apis = [{"name": "Api", "deployments": [
            {"name": capitalise(i["name"]), "instance": i["name"], "auth": None} for i in instances]}]
        result.default("apis", [{"name": "Api", "deployments": [
            {"name": capitalise(i["name"]), "instance": i["name"]} for i in instances]}])
        for dep in apis[0]["deployments"]:
            result.ask(f"apis[Api].deployments[{dep['name']}].auth",
                       "the sign-in providers of this deployment, at least one", auth_schemes)
    for index, item in api_items or []:
        where = f"apis[{index}]."
        reader.known(item, "api", where)
        aname = reader.get(item, "name", "string", where)
        if aname is None:
            if "name" not in item:
                aname = "Api" if len(api_items) == 1 else None
                if aname:
                    result.default(f"apis[{index}].name", aname)
                else:
                    result.ask(f"apis[{index}].name", "a name for the API host project")
        elif not name_ok(result, aname, IDENT, "the API name"):
            aname = None
        deployments = []
        dep_items = reader.objects(item, "deployments", where)
        if dep_items is None and "deployments" not in item:
            result.ask(f"apis[{aname or index}].deployments", "at least one deployment: an API process for one instance",
                       [i["name"] for i in instances])
        for dindex, dep in dep_items or []:
            dwhere = f"apis[{aname or index}].deployments[{dindex}]."
            reader.known(dep, "deployment", dwhere)
            dname = reader.get(dep, "name", "string", dwhere)
            if dname is not None and not name_ok(result, dname, IDENT, "the deployment name"):
                dname = None
            inst = reader.get(dep, "instance", "string", dwhere)
            if inst is None and "instance" not in dep:
                if len(instances) == 1:
                    inst = instances[0]["name"]
                    result.default(f"{dwhere}instance", inst)
                else:
                    result.ask(f"{dwhere}instance", "the instance this deployment serves", [i["name"] for i in instances])
            if dname is None and "name" not in dep and inst:
                dname = capitalise(inst)
                result.default(f"{dwhere}name", dname)
            auth = reader.strings(dep, "auth", dwhere)
            if auth is None and "auth" not in dep:
                result.ask(f"{dwhere}auth", "the sign-in providers of this deployment, at least one", auth_schemes)
            deployments.append({"name": dname, "instance": inst, "auth": auth})
        apis.append({"name": aname, "deployments": deployments})
    if api_items is not None and not api_items:
        result.ask("apis", "at least one API")
    unique(result, [a["name"] for a in apis if a["name"]], "the API name")
    for api in apis:
        unique(result, [d["name"] for d in api["deployments"] if d["name"]], f"a deployment of `{api['name']}`")
    out["apis"] = apis
    result.rep.ran("references")

    # --- modules
    modules = []
    for index, item in reader.objects(raw, "modules", "") or []:
        where = f"modules[{index}]."
        reader.known(item, "module", where)
        mname = reader.get(item, "name", "string", where)
        if mname is None:
            if "name" not in item:
                result.ask(f"{where}name", "a name for the module: a letter then letters, digits and underscores")
            continue
        if not name_ok(result, mname, IDENT, "the module name"):
            continue
        if mname.lower() in RESERVED_MODULES:
            result.add("SCAFFOLD_NAME_INVALID", f"module `{mname}` is a page every workspace already has — {', '.join(sorted(RESERVED_MODULES))} are reserved")
        pattern = reader.get(item, "pattern", "string", where)
        if pattern is None:
            if "pattern" not in item:
                result.ask(f"modules[{mname}].pattern", "what the module is", PATTERNS)
        elif pattern not in PATTERNS:
            result.add("SCAFFOLD_OPTION_INVALID", f"module `{mname}`: pattern `{report.one_line(pattern)}` is not one of {', '.join(PATTERNS)}")
        mtitle = reader.get(item, "title", "string", where)
        if mtitle is not None:
            title_ok(result, mtitle, f"the title of module `{mname}`")
        elif "title" not in item:
            mtitle = mname
        entity = reader.get(item, "entity", "string", where)
        if pattern in ("register", "service"):
            if entity is None and "entity" not in item:
                result.ask(f"modules[{mname}].entity", f"the entity a {pattern} module manages", sorted(entity_names))
            elif entity is not None and entity not in entity_names:
                result.add("SCAFFOLD_REFERENCE_INVALID", f"module `{mname}` names entity `{report.one_line(entity)}`, which the data model does not define")
        elif entity is not None:
            result.add("SCAFFOLD_OPTION_INVALID", f"module `{mname}`: a `page` module manages no entity")
        route = reader.get(item, "route", "string", where)
        if route is None and "route" not in item:
            route = "/" + mname.lower()
            result.default(f"modules[{mname}].route", route)
        if route is not None:
            if route == "/" or not ROUTE.match(route) or route.lower() in RESERVED_ROUTES:
                result.add("SCAFFOLD_NAME_INVALID", f"module `{mname}`: route `{report.one_line(route)}` is not a route — a path such as /permits, "
                           f"never / and not one of {', '.join(sorted(RESERVED_ROUTES))}")
        mroles = reader.strings(item, "roles", where)
        if mroles is None and "roles" not in item:
            if pattern == "service":
                result.ask(f"modules[{mname}].roles", "the roles that review a case, at least one", sorted(known_roles))
            mroles = []
        for role in mroles or []:
            if role.casefold() not in known_roles:
                result.add("SCAFFOLD_REFERENCE_INVALID", f"module `{mname}` names role `{report.one_line(role)}`, which `roles` does not list")
        if pattern == "service" and mroles == [] and "roles" in item:
            result.ask(f"modules[{mname}].roles", "the roles that review a case, at least one", sorted(known_roles))
        modules.append({"name": mname, "pattern": pattern, "title": mtitle, "entity": entity, "route": route,
                        "roles": mroles or []})
    unique(result, [m["name"] for m in modules], "the module name")
    routes = [m["route"] for m in modules if m["route"]]
    unique(result, routes, "the route")
    users = {}
    for module in modules:
        if module["entity"] in entity_names:
            if module["entity"] in users:
                result.add("SCAFFOLD_REFERENCE_INVALID", f"entity `{module['entity']}` is managed by modules `{users[module['entity']]}` and "
                           f"`{module['name']}`; each entity has one module")
            users[module["entity"]] = module["name"]
    out["modules"] = modules

    # --- deployments against instances
    instance_names = {i["name"] for i in instances}
    for api in apis:
        for dep in api["deployments"]:
            if dep["instance"] is not None and dep["instance"] not in instance_names:
                result.add("SCAFFOLD_REFERENCE_INVALID", f"deployment `{dep['name']}` of `{api['name']}` serves instance `{report.one_line(dep['instance'])}`, "
                           "which `instances` does not list")
            for provider in dep["auth"] or []:
                if provider not in auth_schemes:
                    result.add("SCAFFOLD_OPTION_INVALID", f"deployment `{dep['name']}`: sign-in provider `{report.one_line(provider)}` is not one of "
                               f"{', '.join(auth_schemes)}")
            if dep["auth"] == []:
                result.ask(f"apis[{api['name']}].deployments[{dep['name']}].auth", "the sign-in providers of this deployment, at least one", auth_schemes)
    served = {d["instance"] for api in apis for d in api["deployments"]}
    for inst in instances:
        if apis and inst["name"] not in served:
            result.add("SCAFFOLD_REFERENCE_INVALID", f"instance `{inst['name']}` has no deployment")
    result.rep.ran("options")

    # --- the base workspace
    base_raw = reader.get(raw, "base", "object", "") or {}
    reader.known(base_raw, "base", "base.")
    source = reader.get(base_raw, "source", "string", "base.")
    supply = reader.get(base_raw, "supply", "string", "base.")
    if source is None and "source" not in base_raw:
        result.ask("base.source", "an absolute path to a directory named webasm: DGF's, or an estate's — the plugin pins no base")
    elif source is not None and not generated:
        check_base(result, source)
    if supply is None and "supply" not in base_raw:
        result.ask("base.supply", "how the base reaches the application: `copy` puts it in workspaces/webasm; `mount` "
                   "mounts it in compose from a path you set", SUPPLIES)
    elif supply is not None and supply not in SUPPLIES:
        result.add("SCAFFOLD_OPTION_INVALID", f"`base.supply` `{report.one_line(supply)}` is not one of {', '.join(SUPPLIES)}")
    out["base"] = {"source": source, "supply": supply}
    result.rep.ran("base")

    # --- sources
    sources = reader.get(raw, "sources", "object", "")
    if sources is not None:
        for key, value in sources.items():
            if value not in SOURCES:
                result.add("SCAFFOLD_OPTION_INVALID", f"sources.{report.one_line(key)}: `{report.one_line(json.dumps(value))}` is not one of {', '.join(SOURCES)}")
    out["sources"] = sources or {}


def check_base(result, source):
    """`base.source` is an absolute path to a directory named webasm with an exact-case FM/ (D6)."""
    path = Path(source)
    if not path.is_absolute():
        result.add("SCAFFOLD_OPTION_INVALID", f"`base.source` `{report.one_line(source)}` is not an absolute path")
        return
    try:
        parent = entries(path.parent)
    except OSError:
        parent = {}
    entry = parent.get(path.name)
    if entry is None or not entry.is_dir():
        result.add("SCAFFOLD_REFERENCE_INVALID", f"`base.source` `{report.one_line(source)}` is not a directory (matched by exact case)")
        return
    if path.name != "webasm":
        result.add("SCAFFOLD_REFERENCE_INVALID", f"`base.source` `{report.one_line(source)}` is named `{report.one_line(path.name)}`; the base directory is always named webasm")
        return
    fm = entries(path).get("FM")
    if fm is None or not fm.is_dir():
        result.add("SCAFFOLD_REFERENCE_INVALID", f"`base.source` `{report.one_line(source)}` has no FM/ directory (matched by exact case)")


# --- the data model ----------------------------------------------------------

def sql_type(field, rows):
    """The SQL type of a field's column from the field-sql-types table, or None when the table has no row."""
    row = rows.get(field["dbtype"])
    if row is None:
        return None
    rule, text = row["Size rule"], row["SQL type"]
    if rule == "size":
        size = field["size"]
        return text.replace("(size)", "(MAX)" if size in ("MAX", MAX_SIZE) else f"({size})")
    if rule == "precision":
        precision = field.get("precision") if field.get("precision") is not None else 18
        scale = field.get("scale") if field.get("scale") is not None else 2
        return f"{text.split('(')[0]}({precision},{scale})"
    return text


def data_model(reader, result, raw, tables):
    model = reader.get(raw, "data_model", "object", "") or {}
    reader.known(model, "data_model", "data_model.")
    field_types = {row["Type"] for row in tables["field-types"]}
    db_types = {row["Dbtype"] for row in tables["db-types"]}
    sql_rows = {row["Dbtype"]: row for row in tables["field-sql-types"]}
    entities = []
    items = reader.objects(model, "entities", "data_model.")
    if items is None and "entities" not in model:
        result.default("data_model.entities", [])
    for index, item in items or []:
        where = f"data_model.entities[{index}]."
        reader.known(item, "entity", where)
        ename = reader.get(item, "name", "string", where)
        if ename is None:
            if "name" not in item:
                result.ask(f"{where}name", "a name for the entity: a letter then letters, digits and underscores")
            continue
        if not name_ok(result, ename, IDENT, "the entity name"):
            continue
        if ename.lower().startswith(FRAMEWORK_PREFIXES):
            result.add("SCAFFOLD_NAME_INVALID", f"entity `{ename}` starts like a table the framework database owns "
                       f"({', '.join(FRAMEWORK_PREFIXES)}) and would collide with it")
        etitle = reader.get(item, "title", "string", where)
        if etitle is not None:
            title_ok(result, etitle, f"the title of entity `{ename}`")
        elif "title" not in item:
            etitle = ename
        key = reader.get(item, "key", "string", where)
        fields = load_fields(reader, result, item, ename, field_types, db_types, sql_rows, where)
        by_name = {f["name"].casefold(): f for f in fields}
        if key is None:
            if "key" not in item:
                result.ask(f"data_model.entities[{ename}].key", "the primary key: the name of an Integer field",
                           [f["name"] for f in fields if f["type"] == "Integer"])
        elif key.casefold() not in by_name:
            result.add("SCAFFOLD_MODEL_INVALID", f"entity `{ename}`: the primary key `{report.one_line(key)}` is no field of it "
                       "(the table's load throws)")
        else:
            kf = by_name[key.casefold()]
            if kf["type"] != "Integer" or kf["dbtype"] not in ("Int16", "Int32", "Int64"):
                result.add("SCAFFOLD_MODEL_INVALID", f"entity `{ename}`: the key `{kf['name']}` must be an Integer field of dbtype Int16, "
                           "Int32 or Int64 — version 1 generates an identity key")
            key = kf["name"]
        if not fields and "fields" in item:
            result.add("SCAFFOLD_MODEL_INVALID", f"entity `{ename}` has no field (a table with no key throws on load)")
        non_key_text = [f for f in fields if f["type"] == "Text" and f["dbtype"] in STRING_DBTYPES
                        and f["name"] != key]
        if fields and not non_key_text:
            result.add("SCAFFOLD_MODEL_INVALID", f"entity `{ename}` has no Text field of dbtype String or StringUnicode besides its key — "
                       "the lookup view the runtime generates throws on such a table")
        entities.append({"name": ename, "title": etitle, "key": key, "fields": fields})
    unique(result, [e["name"] for e in entities], "the entity name")

    by_entity = {e["name"]: e for e in entities}
    for entity in entities:
        for field in entity["fields"]:
            ext = field.get("extract")
            if not ext:
                continue
            target = by_entity.get(ext["entity"])
            if target is None:
                result.add("SCAFFOLD_REFERENCE_INVALID", f"field `{entity['name']}.{field['name']}` extracts entity `{report.one_line(ext['entity'])}`, "
                           "which the data model does not define")
            elif target["key"]:
                kf = next((f for f in target["fields"] if f["name"] == target["key"]), None)
                if kf and kf["dbtype"] != field["dbtype"]:
                    result.add("SCAFFOLD_MODEL_INVALID", f"field `{entity['name']}.{field['name']}` is {field['dbtype']} but the key of "
                               f"`{target['name']}` is {kf['dbtype']}")
    return entities


def load_fields(reader, result, entity, ename, field_types, db_types, sql_rows, where):
    fields = []
    for index, item in reader.objects(entity, "fields", where) or []:
        fwhere = f"{where}fields[{index}]."
        reader.known(item, "field", fwhere)
        fname = reader.get(item, "name", "string", fwhere)
        if fname is None:
            if "name" not in item:
                result.add("SCAFFOLD_MODEL_INVALID", f"entity `{ename}` has a field with no name (the table's load throws)")
            continue
        if not name_ok(result, fname, IDENT, "the field name"):
            continue
        ftype = reader.get(item, "type", "string", fwhere)
        dbtype = reader.get(item, "dbtype", "string", fwhere)
        label = f"field `{ename}.{fname}`"
        if ftype is None:
            if "type" not in item:
                result.ask(f"data_model.entities[{ename}].fields[{fname}].type", "the field's type", sorted(TYPE_DBTYPES))
            continue
        if ftype in NOT_GENERATED:
            result.add("SCAFFOLD_MODEL_INVALID", f"{label}: type {ftype} is not generated — {NOT_GENERATED[ftype]}")
            continue
        if ftype not in field_types:
            result.add("SCAFFOLD_MODEL_INVALID", f"{label}: `{report.one_line(ftype)}` is not a FieldTypeEnum member")
            continue
        if ftype not in TYPE_DBTYPES:
            result.add("SCAFFOLD_MODEL_INVALID", f"{label}: type {ftype} is not generated")
            continue
        if dbtype is None:
            if "dbtype" not in item:
                result.ask(f"data_model.entities[{ename}].fields[{fname}].dbtype", f"the column's .NET type for a {ftype} field",
                           TYPE_DBTYPES[ftype])
            continue
        if dbtype not in db_types:
            result.add("SCAFFOLD_MODEL_INVALID", f"{label}: dbtype `{report.one_line(dbtype)}` is no value the samples use — {', '.join(sorted(db_types))}")
            continue
        if dbtype not in TYPE_DBTYPES[ftype]:
            result.add("SCAFFOLD_MODEL_INVALID", f"{label}: dbtype {dbtype} does not go with type {ftype} — {', '.join(TYPE_DBTYPES[ftype])}")
            continue
        size = item.get("size") if "size" in item else None
        if "size" in item:
            if size == "MAX":
                pass
            elif isinstance(size, bool) or not isinstance(size, int):
                result.add("SCAFFOLD_OPTION_INVALID", f"{fwhere}size: expected a positive number or \"MAX\", got {kind_of(size)}")
                size = None
        if dbtype in STRING_DBTYPES:
            if "size" not in item:
                result.ask(f"data_model.entities[{ename}].fields[{fname}].size", "the string's length, or \"MAX\"")
                continue
            if isinstance(size, int) and not 1 <= size <= SIZE_LIMIT[dbtype]:
                result.add("SCAFFOLD_MODEL_INVALID", f"{label}: size {size} is outside 1..{SIZE_LIMIT[dbtype]} for {dbtype}; use \"MAX\" for more")
        elif "size" in item:
            result.add("SCAFFOLD_MODEL_INVALID", f"{label}: {dbtype} takes no size")
        precision, scale = item.get("precision"), item.get("scale")
        if ("precision" in item or "scale" in item) and dbtype != "Decimal":
            result.add("SCAFFOLD_MODEL_INVALID", f"{label}: only a Decimal has a precision and a scale")
        else:
            for pname, pvalue in (("precision", precision), ("scale", scale)):
                if pname in item and (isinstance(pvalue, bool) or not isinstance(pvalue, int)):
                    result.add("SCAFFOLD_OPTION_INVALID", f"{fwhere}{pname}: expected a number, got {kind_of(pvalue)}")
            if isinstance(precision, int) and isinstance(scale, int) and not (1 <= precision <= 38 and 0 <= scale <= precision):
                result.add("SCAFFOLD_MODEL_INVALID", f"{label}: precision {precision} and scale {scale} are not 1..38 and 0..precision")
        required = reader.get(item, "required", "boolean", fwhere)
        if required is None:
            required = False
        ftitle = reader.get(item, "title", "string", fwhere)
        if ftitle is not None:
            title_ok(result, ftitle, f"the title of {label}")
        elif "title" not in item:
            ftitle = fname
        extract = None
        ext_raw = reader.get(item, "extract", "object", fwhere)
        if ftype in ("Lookup", "Picklist"):
            if ext_raw is None and "extract" not in item:
                result.ask(f"data_model.entities[{ename}].fields[{fname}].extract", f"the entity a {ftype} field picks from")
            elif ext_raw is not None:
                reader.known(ext_raw, "extract", f"{fwhere}extract.")
                target = reader.get(ext_raw, "entity", "string", f"{fwhere}extract.")
                if target is None:
                    if "entity" not in ext_raw:
                        result.ask(f"data_model.entities[{ename}].fields[{fname}].extract.entity", "the entity to pick from")
                else:
                    view = reader.get(ext_raw, "view", "string", f"{fwhere}extract.") or "default"
                    extract = {"entity": target, "view": view}
        elif ext_raw is not None or "extract" in item:
            result.add("SCAFFOLD_MODEL_INVALID", f"{label}: only a Lookup or a Picklist has an extract")
        field = {"name": fname, "title": ftitle, "type": ftype, "dbtype": dbtype,
                 "size": MAX_SIZE if size == "MAX" else size, "required": required,
                 "precision": precision if isinstance(precision, int) and not isinstance(precision, bool) else None,
                 "scale": scale if isinstance(scale, int) and not isinstance(scale, bool) else None,
                 "extract": extract}
        if sql_type(field, sql_rows) is None:
            result.add("SCAFFOLD_SQL_TYPE_UNKNOWN", f"{label}: no pair of DGF's samples gives dbtype {dbtype} a column type; "
                       "a column type is never guessed")
            continue
        fields.append(field)
    unique(result, [f["name"] for f in fields], f"a field of `{ename}`")
    return fields


# --- output ------------------------------------------------------------------

def show(result):
    lines = [f"FOLDER: {report.one_line(result.folder)}"]
    design = result.design or {}
    app = design.get("application") or {}
    if app.get("name"):
        lines.append(f"APPLICATION: {report.one_line(app['name'])}")
    summary = [f"DEFAULT: {report.one_line(key)} = {report.one_line(json.dumps(value, ensure_ascii=False))}"
               for key, value in result.defaults]
    summary.append(f"OPEN: {len(result.asks)}")
    code = report.render([result.rep], header="Scaffold design", lines=lines, summary=summary)
    return code


def main(argv=None):
    parser = Parser(description="Check a new application's design, and say what is still open.")
    parser.add_argument("--folder", required=True, help="the new application's folder")
    parser.add_argument("--empty-only", action="store_true",
                        help="answer only whether the folder is empty, and read no design")
    parser.add_argument("--knowledge-dir", help="read the knowledge tables from this directory instead of the "
                        "plugin's (for a maintainer checking a design against another knowledge base)")
    parser.add_argument("--verbose", action="store_true", help="trace each value to stderr")
    args = parser.parse_args(argv)
    if args.verbose:
        report.set_verbose()
    result = check(args.folder, knowledge_dir=args.knowledge_dir, empty_only=args.empty_only)
    return show(result)


if __name__ == "__main__":
    raise SystemExit(main())
