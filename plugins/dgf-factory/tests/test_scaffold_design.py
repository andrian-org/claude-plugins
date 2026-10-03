"""skills/dgf-scaffold/scripts/design.py: the design check — what conflicts, what is open, what defaults (ADR 0027 §7.3)."""

import copy
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests import helpers
from lib import report

SCRIPT = helpers.PLUGIN_ROOT / "skills" / "dgf-scaffold" / "scripts" / "design.py"
FIXTURES = helpers.PLUGIN_ROOT / "tests" / "fixtures" / "unit" / "scaffold"
EXAMPLE = json.loads((FIXTURES / "example.application.json").read_text(encoding="utf-8"))
WEBASM = str(FIXTURES / "webasm")


def load_design():
    spec = importlib.util.spec_from_file_location("scaffold_design", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


design = load_design()


def example():
    """The complete example, with its base path made real."""
    doc = copy.deepcopy(EXAMPLE)
    doc["base"]["source"] = WEBASM
    return doc


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)

    def folder(self, doc=None, raw=None, name="app"):
        """A folder holding only docs/application.json — a JSON document, or exact bytes."""
        path = Path(self.tmp) / name
        (path / "docs").mkdir(parents=True)
        target = path / "docs" / "application.json"
        if raw is not None:
            target.write_bytes(raw)
        elif doc is not None:
            target.write_text(json.dumps(doc), encoding="utf-8")
        return path

    def check(self, doc=None, **kw):
        return design.check(self.folder(doc, **kw))

    def codes(self, result):
        return [f.code for f in result.rep.findings]

    def messages(self, result, code):
        return [f.message for f in result.rep.findings if f.code == code]

    def only(self, doc, code):
        """The check of `doc` finds `code`, and exits as that code says."""
        result = self.check(doc)
        self.assertIn(code, self.codes(result), [f.render() for f in result.rep.findings])
        self.assertEqual(result.exit_code, report.CODES[code])
        return result


class Complete(Base):
    def test_the_example_is_complete_and_defaults_what_it_leaves_out(self):
        result = self.check(example())
        self.assertEqual(result.exit_code, 0, [f.render() for f in result.rep.findings])
        self.assertEqual(dict(result.defaults), {
            "workspace": "inspections",
            "modules[About].route": "/about",
        })

    def test_the_resolved_design_carries_the_defaults(self):
        resolved = self.check(example()).design
        self.assertEqual(resolved["workspace"], "inspections")
        self.assertEqual(next(m for m in resolved["modules"] if m["name"] == "About")["route"], "/about")

    def test_a_title_left_out_is_its_name_and_prints_no_default(self):
        doc = example()
        del doc["application"]["title"]
        del doc["instances"][0]["title"]
        result = self.check(doc)
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.design["application"]["title"], "Inspections")
        self.assertEqual(result.design["instances"][0]["title"], "Lands")
        self.assertNotIn("application.title", dict(result.defaults))

    def test_the_cli_prints_the_defaults_and_exits_0(self):
        folder = self.folder(example())
        done = subprocess.run([sys.executable, str(SCRIPT), "--folder", str(folder)], capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("DEFAULT: workspace = \"inspections\"", done.stdout)
        self.assertIn("DEFAULT: modules[About].route = \"/about\"", done.stdout)
        self.assertIn("CLEAN", done.stdout)

    def test_a_single_instance_defaults_its_model(self):
        doc = example()
        doc["instances"] = doc["instances"][:1]
        doc["apis"] = [{"name": "Api", "deployments": [{"name": "Web", "instance": "lands", "auth": ["basic"]}]}]
        del doc["instance_model"]
        result = self.check(doc)
        self.assertEqual(result.exit_code, 0, [f.render() for f in result.rep.findings])
        self.assertEqual(dict(result.defaults)["instance_model"], "own-workspace")
        self.assertIsNone(result.design["workspace"])


class Open(Base):
    """Each value the design leaves out and cannot default is one SCAFFOLD_ASK, and the run exits 2."""

    def ask(self, doc, key):
        result = self.check(doc)
        self.assertEqual(result.exit_code, 2, [f.render() for f in result.rep.findings])
        self.assertIn(key, result.asks)
        return result

    def test_application_name(self):
        doc = example()
        del doc["application"]["name"]
        self.ask(doc, "application.name")

    def test_dgf_version(self):
        doc = example()
        del doc["dgf_version"]
        self.ask(doc, "dgf_version")

    def test_instances(self):
        doc = example()
        del doc["instances"]
        del doc["apis"]
        self.ask(doc, "instances")

    def test_instance_model_with_several_instances(self):
        doc = example()
        del doc["instance_model"]
        self.ask(doc, "instance_model")

    def test_base_source_and_supply(self):
        doc = example()
        del doc["base"]
        result = self.ask(doc, "base.source")
        self.assertIn("base.supply", result.asks)

    def test_a_deployment_needs_its_sign_in_providers(self):
        doc = example()
        del doc["apis"][0]["deployments"][0]["auth"]
        self.ask(doc, "apis[PublicApi].deployments[0].auth")

    def test_apis_left_out_default_and_still_ask_for_sign_in(self):
        doc = example()
        del doc["apis"]
        result = self.ask(doc, "apis[Api].deployments[Lands].auth")
        self.assertIn("apis", dict(result.defaults))
        self.assertEqual([d["name"] for d in result.design["apis"][0]["deployments"]], ["Lands", "Deeds"])

    def test_a_service_needs_its_reviewing_roles(self):
        doc = example()
        del doc["modules"][1]["roles"]
        self.ask(doc, "modules[Approval].roles")

    def test_an_explicitly_empty_role_list_of_a_service_asks_too(self):
        doc = example()
        doc["modules"][1]["roles"] = []
        self.ask(doc, "modules[Approval].roles")

    def test_a_field_needs_its_size(self):
        doc = example()
        del doc["data_model"]["entities"][1]["fields"][1]["size"]
        self.ask(doc, "data_model.entities[Permit].fields[Reference].size")

    def test_a_picklist_needs_its_extract(self):
        doc = example()
        del doc["data_model"]["entities"][1]["fields"][3]["extract"]
        self.ask(doc, "data_model.entities[Permit].fields[PermitTypeId].extract")

    def test_an_ask_names_its_rule_and_candidates(self):
        doc = example()
        del doc["instance_model"]
        text = self.messages(self.check(doc), "SCAFFOLD_ASK")[0]
        self.assertIn("instance_model — ", text)
        self.assertIn("candidates: shared-workspace, own-workspace", text)

    def test_a_conflict_beats_a_question(self):
        doc = example()
        del doc["dgf_version"]
        doc["roles"] = ["a,b"]
        self.assertEqual(self.check(doc).exit_code, 1)


class Conflicts(Base):
    """Each exit-1 code is hit once, with the exit the registry gives it."""

    def test_dir_not_empty(self):
        path = Path(self.tmp) / "full"
        path.mkdir()
        (path / "README.md").write_text("x")
        result = design.check(path, empty_only=True)
        self.assertEqual(result.exit_code, 1)
        self.assertIn("SCAFFOLD_DIR_NOT_EMPTY", self.codes(result))

    def test_only_git_and_the_design_are_allowed_in_the_folder(self):
        path = self.folder(example())
        (path / ".git").mkdir()
        self.assertEqual(design.check(path, empty_only=True).exit_code, 0)
        (path / "docs" / "notes.md").write_text("x")
        self.assertEqual(design.check(path, empty_only=True).exit_code, 1)

    def test_a_missing_folder_is_empty(self):
        self.assertEqual(design.check(Path(self.tmp) / "nowhere", empty_only=True).exit_code, 0)

    def test_name_invalid(self):
        doc = example()
        doc["application"]["name"] = "9 Bad name"
        self.only(doc, "SCAFFOLD_NAME_INVALID")

    def test_option_invalid(self):
        doc = example()
        doc["instance_model"] = "cloned"
        self.only(doc, "SCAFFOLD_OPTION_INVALID")

    def test_reference_invalid(self):
        doc = example()
        doc["modules"][0]["entity"] = "Nowhere"
        self.only(doc, "SCAFFOLD_REFERENCE_INVALID")

    def test_model_invalid(self):
        doc = example()
        doc["data_model"]["entities"][1]["fields"][1]["dbtype"] = "Blob"
        self.only(doc, "SCAFFOLD_MODEL_INVALID")

    def test_sql_type_unknown_when_a_dbtype_has_no_evidence(self):
        # a dbtype the samples use but no pair gives a column type: copy the knowledge base, drop its row
        kdir = Path(self.tmp) / "knowledge"
        shutil.copytree(helpers.PLUGIN_ROOT / "knowledge", kdir)
        text = (kdir / "data-model.md").read_text(encoding="utf-8")
        lines = [l for l in text.splitlines() if not l.startswith("| `Int64` | none |")]
        self.assertEqual(len(lines), len(text.splitlines()) - 1)
        (kdir / "data-model.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        doc = example()
        doc["data_model"]["entities"][1]["fields"].append({"name": "Big", "type": "Integer", "dbtype": "Int64"})
        result = design.check(self.folder(doc, name="guid"), knowledge_dir=kdir)
        self.assertIn("SCAFFOLD_SQL_TYPE_UNKNOWN", self.codes(result))
        self.assertEqual(result.exit_code, 1)

    def test_an_unknown_key_at_any_level(self):
        for path in (("extra",), ("application", "extra"), ("instances", 0, "extra"), ("apis", 0, "extra"),
                     ("apis", 0, "deployments", 0, "extra"), ("base", "extra"), ("modules", 0, "extra"),
                     ("data_model", "extra"), ("data_model", "entities", 0, "extra"),
                     ("data_model", "entities", 1, "fields", 3, "extract", "extra")):
            doc = example()
            node = doc
            for step in path[:-1]:
                node = node[step]
            node[path[-1]] = 1
            result = self.check(doc, name="k" + "-".join(map(str, path)))
            self.assertIn("SCAFFOLD_OPTION_INVALID", self.codes(result), path)

    def test_two_names_that_differ_only_in_case_are_refused(self):
        for section, doc_change in (
                ("entity", lambda d: d["data_model"]["entities"].append(
                    {"name": "PERMIT", "key": "Id", "fields": d["data_model"]["entities"][0]["fields"]})),
                ("instance", lambda d: d["instances"].append({"name": "lands"})),
                ("role", lambda d: d["roles"].append("inspector")),
                ("module", lambda d: d["modules"].append({"name": "PERMITS", "pattern": "page"})),
                ("field", lambda d: d["data_model"]["entities"][0]["fields"].append(
                    {"name": "NAME", "type": "Text", "dbtype": "String", "size": 5})),
        ):
            doc = example()
            doc_change(doc)
            result = self.check(doc, name=section)
            self.assertIn("SCAFFOLD_NAME_INVALID", self.codes(result), section)

    def test_a_role_must_be_a_folder_name_on_every_system(self):
        for role in ("a/b", "a\\b", "a:b", "a*b", "a?b", 'a"b', "a<b", "a>b", "a|b", "ends.", "..", "."):
            doc = example()
            doc["roles"] = [role]
            doc["modules"][0]["roles"] = []
            doc["modules"][1]["roles"] = ["Administrators"]
            self.assertIn("SCAFFOLD_NAME_INVALID", self.codes(self.check(doc, name="f" + str(abs(hash(role))))), role)
        doc = example()
        doc["roles"] = ["Case officer & co", "Registrar's clerk", "Assistant (acting)"]
        doc["modules"][0]["roles"] = []
        doc["modules"][1]["roles"] = ["Administrators"]
        self.assertEqual(self.check(doc, name="fine").exit_code, 0)

    def test_a_role_with_a_comma_or_a_stray_space(self):
        for role in ("a,b", " Inspector", "Inspector "):
            doc = example()
            doc["roles"] = [role]
            doc["modules"][0]["roles"] = []
            doc["modules"][1]["roles"] = ["Administrators"]
            self.assertIn("SCAFFOLD_NAME_INVALID", self.codes(self.check(doc, name=f"r{len(role)}{ord(role[0])}")), role)

    def test_a_route_is_never_the_root_and_is_unique(self):
        for route in ("/", "/login", "/user-profile", "/app-menu", "permits", "/a b"):
            doc = example()
            doc["modules"][0]["route"] = route
            self.assertIn("SCAFFOLD_NAME_INVALID", self.codes(self.check(doc, name="route" + str(abs(hash(route))))), route)
        doc = example()
        doc["modules"][2]["route"] = "/permits"
        self.assertIn("SCAFFOLD_NAME_INVALID", self.codes(self.check(doc, name="dupe")))

    def test_the_base_must_be_a_directory_named_webasm_with_an_fm_folder(self):
        for source, why in ((str(FIXTURES), "not webasm"), (str(FIXTURES / "nope" / "webasm"), "absent"),
                            ("relative/webasm", "relative")):
            doc = example()
            doc["base"]["source"] = source
            result = self.check(doc, name="base" + str(abs(hash(source))))
            self.assertTrue({"SCAFFOLD_REFERENCE_INVALID", "SCAFFOLD_OPTION_INVALID"} & set(self.codes(result)), why)
        bare = Path(self.tmp) / "bare" / "webasm"
        bare.mkdir(parents=True)
        doc = example()
        doc["base"]["source"] = str(bare)
        self.assertIn("SCAFFOLD_REFERENCE_INVALID", self.codes(self.check(doc, name="nofm")))

    def test_a_base_directory_is_matched_by_exact_case(self):
        upper = Path(self.tmp) / "case" / "WEBASM"
        (upper / "FM").mkdir(parents=True)
        doc = example()
        doc["base"]["source"] = str(Path(self.tmp) / "case" / "webasm")
        self.assertIn("SCAFFOLD_REFERENCE_INVALID", self.codes(self.check(doc, name="lowercase")))

    def test_the_model_refuses_what_makes_a_load_throw_or_is_not_generated(self):
        cases = {
            "no key": lambda e: e.update(key="Nope"),
            "no fields": lambda e: e.update(fields=[]),
            "unknown type": lambda e: e["fields"][1].update(type="Memo"),
            "PrimaryKey": lambda e: e["fields"][1].update(type="PrimaryKey"),
            "Checkboxlist": lambda e: e["fields"][1].update(type="Checkboxlist"),
            "EditableGrid": lambda e: e["fields"][1].update(type="EditableGrid"),
            "mismatched dbtype": lambda e: e["fields"][1].update(dbtype="Boolean"),
            "size on an int": lambda e: e["fields"][0].update(size=4),
            "size out of range": lambda e: e["fields"][1].update(size=9000),
            "precision on a string": lambda e: e["fields"][1].update(precision=5),
            "key is not integer": lambda e: e["fields"][0].update(type="Text", dbtype="String", size=5),
            "no text besides the key": lambda e: e.update(fields=[e["fields"][0]]),
            "extract on a text": lambda e: e["fields"][1].update(extract={"entity": "PermitType"}),
        }
        for label, mutate in cases.items():
            doc = example()
            mutate(doc["data_model"]["entities"][0])
            result = self.check(doc, name="m" + str(abs(hash(label))))
            self.assertIn("SCAFFOLD_MODEL_INVALID", self.codes(result), label)

    def test_a_lookup_key_must_have_the_dbtype_of_its_target(self):
        doc = example()
        doc["data_model"]["entities"][1]["fields"][3]["dbtype"] = "Int64"
        self.assertIn("SCAFFOLD_MODEL_INVALID", self.codes(self.check(doc)))

    def test_an_entity_named_like_a_framework_table_is_refused(self):
        doc = example()
        doc["data_model"]["entities"][0]["name"] = "AspNetThings"
        self.assertIn("SCAFFOLD_NAME_INVALID", self.codes(self.check(doc)))

    def test_an_entity_belongs_to_one_module(self):
        doc = example()
        doc["modules"].append({"name": "Again", "pattern": "register", "entity": "Permit"})
        self.assertIn("SCAFFOLD_REFERENCE_INVALID", self.codes(self.check(doc)))

    def test_an_instance_needs_a_deployment(self):
        doc = example()
        doc["apis"][0]["deployments"] = doc["apis"][0]["deployments"][:1]
        doc["apis"][1]["deployments"] = doc["apis"][1]["deployments"][:1]
        self.assertIn("SCAFFOLD_REFERENCE_INVALID", self.codes(self.check(doc)))

    def test_a_string_needs_a_size_and_a_decimal_a_sound_precision(self):
        doc = example()
        doc["data_model"]["entities"][1]["fields"][5].update(precision=4, scale=9)
        self.assertIn("SCAFFOLD_MODEL_INVALID", self.codes(self.check(doc)))


class GeneratedFolder(Base):
    """A folder that already holds the application is checked for everything but its emptiness and its base."""

    def test_the_folder_may_hold_the_application_and_the_base_may_be_gone(self):
        doc = example()
        doc["base"]["source"] = "/nowhere/at/all/webasm"
        folder = self.folder(doc)
        (folder / "src").mkdir()
        (folder / "src" / "Program.cs").write_text("x")
        plain = design.check(folder)
        self.assertEqual(plain.exit_code, 1)
        self.assertEqual(sorted(set(self.codes(plain))), ["SCAFFOLD_DIR_NOT_EMPTY", "SCAFFOLD_REFERENCE_INVALID"])
        made = design.check(folder, generated=True)
        self.assertEqual(made.exit_code, 0, [f.render() for f in made.rep.findings])

    def test_every_other_rule_still_holds(self):
        doc = example()
        doc["roles"] = ["a,b"]
        folder = self.folder(doc)
        (folder / "src").mkdir()
        self.assertEqual(design.check(folder, generated=True).exit_code, 1)


class KnowledgeDir(Base):
    def test_the_cli_reads_another_knowledge_base(self):
        case = helpers.FIXTURES / "known-bad" / "scaffold-sql-type-unknown"
        done = subprocess.run([sys.executable, str(SCRIPT), "--folder", "app", "--knowledge-dir", "knowledge"],
                              capture_output=True, text=True, cwd=case)
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("SCAFFOLD_SQL_TYPE_UNKNOWN", done.stdout)

    def test_a_knowledge_directory_that_is_not_one_is_unreadable(self):
        done = subprocess.run([sys.executable, str(SCRIPT), "--folder", str(self.folder(example())),
                               "--knowledge-dir", str(Path(self.tmp) / "nothing")], capture_output=True, text=True)
        self.assertEqual(done.returncode, 3, done.stdout)
        self.assertIn("SCAFFOLD_DESIGN_UNREADABLE", done.stdout)


class Unreadable(Base):
    """Each exit-3 cause is hit once; none is a traceback."""

    def unreadable(self, **kw):
        result = self.check(**kw)
        self.assertEqual(self.codes(result), ["SCAFFOLD_DESIGN_UNREADABLE"], [f.render() for f in result.rep.findings])
        self.assertEqual(result.exit_code, 3)
        return result

    def test_no_design_file(self):
        path = Path(self.tmp) / "bare"
        path.mkdir()
        result = design.check(path)
        self.assertEqual(self.codes(result), ["SCAFFOLD_DESIGN_UNREADABLE"])

    def test_not_a_regular_file(self):
        path = Path(self.tmp) / "dir"
        (path / "docs" / "application.json").mkdir(parents=True)
        self.assertEqual(design.check(path).exit_code, 3)

    def test_a_symbolic_link_is_not_a_regular_file(self):
        real = Path(self.tmp) / "real.json"
        real.write_text(json.dumps(example()))
        path = Path(self.tmp) / "linked"
        (path / "docs").mkdir(parents=True)
        os.symlink(real, path / "docs" / "application.json")
        self.assertEqual(design.check(path).exit_code, 3)

    def test_too_large(self):
        self.unreadable(raw=b'{"design_format": 1, "x": "' + b"a" * (design.MAX_BYTES + 1) + b'"}')

    def test_not_utf8(self):
        self.unreadable(raw=b'{"design_format": 1, "x": "\xff"}')

    def test_a_byte_order_mark(self):
        self.unreadable(raw=b"\xef\xbb\xbf" + json.dumps(example()).encode())

    def test_not_json(self):
        self.unreadable(raw=b"{not json")

    def test_nested_too_deeply(self):
        self.unreadable(raw=b"[" * 200000 + b"]" * 200000)

    def test_a_duplicate_key(self):
        self.unreadable(raw=b'{"design_format": 1, "design_format": 1}')

    def test_a_json_constant_that_is_not_json(self):
        self.unreadable(raw=b'{"design_format": 1, "x": NaN}')

    def test_not_an_object(self):
        self.unreadable(raw=b"[1, 2]")

    def test_a_format_this_version_does_not_read(self):
        for value in (2, "1", True, None, 1.5):
            doc = example()
            doc["design_format"] = value
            self.unreadable(doc=doc, name="f" + str(abs(hash(repr(value)))))

    def test_a_malformed_knowledge_table(self):
        kdir = Path(self.tmp) / "knowledge"
        shutil.copytree(helpers.PLUGIN_ROOT / "knowledge", kdir)
        path = kdir / "application-layout.md"
        path.write_text(path.read_text(encoding="utf-8").replace("| Provider | Section |", "| Prov | Section |"),
                        encoding="utf-8")
        result = design.check(self.folder(example(), name="kn"), knowledge_dir=kdir)
        self.assertEqual(self.codes(result), ["SCAFFOLD_DESIGN_UNREADABLE"])


def leaves(node, path=()):
    """Every path in a JSON document, containers included."""
    yield path
    if isinstance(node, dict):
        for key, value in node.items():
            yield from leaves(value, path + (key,))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from leaves(value, path + (index,))


def kind(value):
    return design.kind_of(value)


class EveryType(Base):
    """A value of the wrong JSON type is refused, never used as a key or looked up — and never a traceback."""

    WRONG = (None, True, 7, "x", [], {})

    def test_every_value_is_offered_every_json_type(self):
        base = example()
        offered = 0
        for path in leaves(base):
            if not path:
                continue
            original = base
            for step in path:
                original = original[step]
            for wrong in self.WRONG:
                if kind(wrong) == kind(original):
                    continue
                if path[-1] == "size" and wrong == 7:
                    continue  # a size is a number or "MAX": both are valid
                doc = example()
                node = doc
                for step in path[:-1]:
                    node = node[step]
                node[path[-1]] = wrong
                result = self.check(doc, name=f"t{offered}")
                offered += 1
                self.assertNotEqual(
                    result.exit_code, 0,
                    f"{'.'.join(map(str, path))} = {wrong!r} passed (was {kind(original)})")
        self.assertGreater(offered, 500)

    def test_a_list_where_a_name_is_used_as_a_key_does_not_crash(self):
        doc = example()
        doc["modules"][0]["entity"] = ["Permit"]
        doc["modules"][1]["roles"] = [["Supervisor"]]
        doc["apis"][0]["deployments"][0]["instance"] = {"a": 1}
        doc["apis"][0]["deployments"][0]["auth"] = [{"x": 1}]
        self.assertEqual(self.check(doc).exit_code, 1)


class Cli(Base):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)

    def test_empty_only_reads_no_design(self):
        path = Path(self.tmp) / "e"
        path.mkdir()
        done = self.run_cli("--folder", str(path), "--empty-only")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("CHECKS RUN: folder", done.stdout)

    def test_a_usage_error_is_exit_3(self):
        done = self.run_cli("--empty-only")
        self.assertEqual(done.returncode, 3)
        done = self.run_cli("--folder", str(Path(self.tmp) / "x"), "--nope")
        self.assertEqual(done.returncode, 3)

    def test_a_folder_that_is_a_file_is_a_usage_error(self):
        path = Path(self.tmp) / "file"
        path.write_text("x")
        self.assertEqual(self.run_cli("--folder", str(path)).returncode, 3)

    def test_a_finding_prints_on_one_line(self):
        doc = example()
        doc["application"]["name"] = "Bad\nname"
        folder = self.folder(doc)
        done = self.run_cli("--folder", str(folder))
        self.assertEqual(done.returncode, 1)
        self.assertNotIn("Bad\nname", done.stdout)
        self.assertIn("Bad\\x0aname", done.stdout)

    def test_verbose_traces_each_value(self):
        doc = example()
        del doc["dgf_version"]
        done = self.run_cli("--folder", str(self.folder(doc)), "--verbose")
        self.assertIn("[design.check] value key=dgf_version state=open", done.stderr)
        self.assertIn("[design.check] done", done.stderr)
        self.assertIn("[design.read] read", done.stderr)

    def test_it_runs_without_lxml_and_jsonschema(self):
        done = subprocess.run(
            [sys.executable, "-c",
             "import sys; sys.modules['lxml']=None; sys.modules['jsonschema']=None; "
             f"sys.argv=['design.py','--folder',{str(self.folder(example()))!r}]; "
             f"exec(compile(open({str(SCRIPT)!r}).read(), 'design.py', 'exec'), {{'__name__': '__main__', '__file__': {str(SCRIPT)!r}}})"],
            capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)


class Reference(unittest.TestCase):
    """references/DESIGN-FORMAT.md says what design.py does."""

    TEXT = (helpers.PLUGIN_ROOT / "skills" / "dgf-scaffold" / "references" / "DESIGN-FORMAT.md").read_text(
        encoding="utf-8")

    def documented(self, word):
        return re.search(rf"`[^`\n]*\b{re.escape(word)}\b[^`\n]*`", self.TEXT) is not None

    def test_its_example_is_the_fixture(self):
        block = self.TEXT.split("```json\n", 1)[1].split("\n```", 1)[0]
        documented = json.loads(block)
        documented["base"]["source"] = "@WEBASM@"
        self.assertEqual(documented, EXAMPLE)

    def test_every_key_the_check_accepts_is_documented(self):
        for level, keys in design.ALLOWED.items():
            for key in keys:
                self.assertTrue(self.documented(key), f"{level}.{key} is not in DESIGN-FORMAT.md")

    def test_every_pattern_option_and_reserved_route_is_documented(self):
        for word in design.PATTERNS + design.SUPPLIES + tuple(design.RESERVED_ROUTES):
            self.assertTrue(f"`{word}`" in self.TEXT, f"{word} is not in DESIGN-FORMAT.md")
        for prefix in ("AX_", "AspNet", "ZIGS_", "prc_", "DGF_Demo_"):
            self.assertTrue(prefix in self.TEXT, prefix)

    def test_every_type_and_dbtype_pair_is_documented(self):
        for ftype, dbtypes in design.TYPE_DBTYPES.items():
            self.assertTrue(f"`{ftype}`" in self.TEXT, ftype)
            for dbtype in dbtypes:
                self.assertTrue(f"`{dbtype}`" in self.TEXT, dbtype)

    def test_every_code_it_names_is_registered(self):
        for token in re.findall(r"`(SCAFFOLD_[A-Z_]+)`", self.TEXT):
            self.assertIn(token, report.CODES)


if __name__ == "__main__":
    unittest.main()
