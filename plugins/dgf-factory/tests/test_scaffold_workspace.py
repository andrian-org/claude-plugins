"""skills/dgf-scaffold workspace templates: the workspace minimum and the register, service and page patterns."""

import copy
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from tests import helpers

GENERATE = helpers.PLUGIN_ROOT / "skills" / "dgf-scaffold" / "scripts" / "generate.py"
FIXTURES = helpers.PLUGIN_ROOT / "tests" / "fixtures" / "unit" / "scaffold"
EXAMPLE = json.loads((FIXTURES / "example.application.json").read_text(encoding="utf-8"))
WEBASM = str(FIXTURES / "webasm")
XML_SUFFIXES = (".xml", ".sitemap")
NASTY = "Fish & Chips <\"quoted\"> 'single'"


def example():
    doc = copy.deepcopy(EXAMPLE)
    doc["base"]["source"] = WEBASM
    return doc


def own_single():
    doc = example()
    doc["instance_model"] = "own-workspace"
    doc["instances"] = doc["instances"][:1]
    doc["apis"] = [{"name": "Api", "deployments": [{"name": "Lands", "instance": "lands", "auth": ["basic"]}]}]
    return doc


def page_only():
    doc = example()
    doc["instance_model"] = "own-workspace"
    doc["instances"] = doc["instances"][:1]
    doc["apis"] = [{"name": "Api", "deployments": [{"name": "Lands", "instance": "lands", "auth": ["dgpass"]}]}]
    doc["roles"] = []
    doc["modules"] = [{"name": "About", "pattern": "page", "title": "About"}]
    doc["data_model"] = {"entities": []}
    return doc


def nasty():
    doc = example()
    doc["application"]["title"] = NASTY
    doc["roles"] = ["Lead & Co", "Supervisor's"]
    doc["instances"][0]["title"] = NASTY
    doc["modules"] = [
        {"name": "Permits", "pattern": "register", "title": NASTY, "entity": "Permit", "route": "/permits",
         "roles": ["Lead & Co"]},
        {"name": "Approval", "pattern": "service", "title": NASTY, "entity": "Approval", "route": "/approval",
         "roles": ["Supervisor's"]},
        {"name": "About", "pattern": "page", "title": NASTY},
    ]
    for entity in doc["data_model"]["entities"]:
        entity["title"] = NASTY
        for field in entity["fields"]:
            field["title"] = NASTY
    return doc


def generate(doc, name):
    """The folder a design was generated into (a fresh temp folder), or the failing output."""
    tmp = Path(tempfile.mkdtemp())
    folder = tmp / name
    (folder / "docs").mkdir(parents=True)
    (folder / "docs" / "application.json").write_text(json.dumps(doc), encoding="utf-8")
    proc = subprocess.run([sys.executable, str(GENERATE), "--folder", str(folder)], capture_output=True, text=True)
    if proc.returncode != 0:
        raise AssertionError(proc.stdout + proc.stderr)
    return tmp, folder


def workspace_files(folder, directory):
    """{relative path: text} of every file of one generated workspace."""
    root = Path(folder) / "workspaces" / directory
    return {p.relative_to(root).as_posix(): p.read_text(encoding="utf-8") for p in sorted(root.rglob("*"))
            if p.is_file()}


class Generated(unittest.TestCase):
    designs = {}

    @classmethod
    def setUpClass(cls):
        cls.tmps, cls.folders = [], {}
        for key, doc in (("shared", example()), ("own", own_single()), ("page", page_only()), ("nasty", nasty())):
            tmp, folder = generate(doc, key)
            cls.tmps.append(tmp)
            cls.folders[key] = folder

    @classmethod
    def tearDownClass(cls):
        for tmp in cls.tmps:
            shutil.rmtree(tmp, ignore_errors=True)

    def files(self, key, directory):
        return workspace_files(self.folders[key], directory)


class FileSet(Generated):
    def test_shared_workspace_holds_the_minimum_the_patterns_and_a_sitemap_per_instance(self):
        files = set(self.files("shared", "inspections"))
        expected = {
            "FM/_COMPONENTS/sitemap.json", "FM/_COMPONENTS/Page/SiteMap/home.json",
            "FM/_COMPONENTS/Page/SiteMap/loginPage.json", "_application.sitemap",
            "_application-lands.sitemap", "_application-deeds.sitemap",
            "FM/_COMPONENTS/Page/SiteMap/Permits.json", "FM/_COMPONENTS/Page/SiteMap/Approval.json",
            "FM/_COMPONENTS/Page/SiteMap/About.json",
            "FM/_COMPONENTS/DataSource/Permit.json", "FM/_COMPONENTS/DataSource/Approval.json",
            "FM/_PROFILE/Main/Members/_tree.xml", "FM/_PROFILE/Main/Inspector/_tree.xml",
            "FM/_PROFILE/Main/Supervisor/_tree.xml", "FM/_PROFILE/Main/Inspector/Permits.xml",
            "FM/_PROFILE/Main/Supervisor/Permits.xml", "FM/_PROFILE/Main/Supervisor/Approval.xml",
            "FM/_PROCESS/Approval/process.xml",
        }
        for name in ("Approved", "Draft", "InReview", "Rejected", "Submitted"):
            expected.add(f"FM/_WORKFLOW/Approval.{name}/_workflow.xml")
        for entity in ("Approval", "Permit", "PermitType"):  # every entity, module or not
            expected |= {f"FM/_DATA/{entity}/settings.xml", f"FM/_DATA/{entity}/_forms/default/_form.xml",
                         f"FM/_DATA/{entity}/_lookupviews/default/_view.xml"}
        for entity in ("Approval", "Permit"):
            expected.add(f"FM/_DATA/{entity}/_views/default/_view.xml")
        self.assertEqual(files, expected)

    def test_own_workspace_has_no_per_instance_sitemap(self):
        files = set(self.files("own", "lands"))
        self.assertIn("_application.sitemap", files)
        self.assertFalse([f for f in files if f.startswith("_application-")])
        self.assertTrue((Path(self.folders["own"]) / "workspaces" / "lands").is_dir())

    def test_a_page_only_design_is_the_minimum_alone(self):
        self.assertEqual(set(self.files("page", "lands")), {
            "FM/_COMPONENTS/sitemap.json", "FM/_COMPONENTS/Page/SiteMap/home.json",
            "FM/_COMPONENTS/Page/SiteMap/loginPage.json", "FM/_COMPONENTS/Page/SiteMap/About.json",
            "_application.sitemap", "FM/_PROFILE/Main/Members/_tree.xml"})

    def test_an_entity_is_in_every_own_workspace(self):
        doc = example()
        doc["instance_model"] = "own-workspace"
        tmp, folder = generate(doc, "two")
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        for directory in ("lands", "deeds"):
            files = workspace_files(folder, directory)
            self.assertIn("FM/_DATA/PermitType/settings.xml", files)
            self.assertIn("FM/_DATA/PermitType/_lookupviews/default/_view.xml", files)


class Shape(Generated):
    def sitemap(self, key, directory):
        return json.loads(self.files(key, directory)["FM/_COMPONENTS/sitemap.json"])

    def test_landing_route_is_first_and_never_root(self):
        for key, directory in (("shared", "inspections"), ("own", "lands"), ("page", "lands")):
            routes = self.sitemap(key, directory)["routes"]["routes"]
            self.assertEqual(routes[0]["path"], "/home")
            self.assertNotIn("/", [r["path"] for r in routes])
            self.assertIn("/login", [r["path"] for r in routes])

    def test_every_route_page_exists(self):
        for key, directory in (("shared", "inspections"), ("own", "lands"), ("page", "lands")):
            files = self.files(key, directory)
            for route in self.sitemap(key, directory)["routes"]["routes"]:
                for item in route["content"]:
                    if item["type"] == "page":
                        self.assertIn(f"FM/_COMPONENTS/Page/{item['name']}.json", files)

    def test_sign_in_id_only_when_the_login_page_lists_several_methods(self):
        def ids(key, directory):
            text = json.dumps(self.sitemap(key, directory)["header"])
            return '"signIn"' in text

        self.assertTrue(ids("shared", "inspections"))    # dgpass, azure, basic
        self.assertFalse(ids("own", "lands"))            # basic alone
        self.assertFalse(ids("page", "lands"))           # dgpass alone

    def test_login_page_lists_the_workspace_methods(self):
        def methods(key, directory):
            page = json.loads(self.files(key, directory)["FM/_COMPONENTS/Page/SiteMap/loginPage.json"])
            return [m["name"] for m in page["content"][0]["authenticationMethods"]]

        self.assertEqual(methods("shared", "inspections"), ["dgpass", "azure", "basic"])
        self.assertEqual(methods("own", "lands"), ["basic"])
        self.assertEqual(methods("page", "lands"), ["dgpass"])

    def test_role_groups_hold_only_their_modules(self):
        files = self.files("shared", "inspections")
        self.assertNotIn("FM/_PROFILE/Main/Members/Permits.xml", files)
        self.assertIn('name="Permits"', files["FM/_PROFILE/Main/Inspector/_tree.xml"])
        self.assertNotIn('name="Approval"', files["FM/_PROFILE/Main/Inspector/_tree.xml"])
        self.assertIn('name="Approval"', files["FM/_PROFILE/Main/Supervisor/_tree.xml"])

    def test_nodes_create_and_open_records(self):
        files = self.files("shared", "inspections")
        register = ET.fromstring(files["FM/_PROFILE/Main/Inspector/Permits.xml"])
        sets = {e.get("name"): e.get("value") for e in register.findall("set")}
        self.assertEqual((sets["TableName"], sets["CreateForm"], sets["OpenForm"]), ("Permit", "FORM:default", "FORM:default"))
        service = ET.fromstring(files["FM/_PROFILE/Main/Supervisor/Approval.xml"])
        sets = {e.get("name"): e.get("value") for e in service.findall("set")}
        self.assertEqual((sets["CreateForm"], sets["OpenForm"]), ("STATEPROCESS:Approval", "STATEPROCESS:"))

    def test_the_map_names_each_profile_and_the_dbprefix(self):
        root = ET.fromstring(self.files("shared", "inspections")["_application.sitemap"])
        self.assertEqual(root.findtext("dbprefix"), "INSPECTIONS")
        tabs = [(n.get("type"), n.get("content")) for n in root.find("tabs")]
        self.assertEqual(tabs, [("PROFILE", "Main")])
        lands = ET.fromstring(self.files("shared", "inspections")["_application-lands.sitemap"])
        self.assertEqual(lands.findtext("title"), "Lands Directorate")

    def test_service_process_states_and_review_tasks(self):
        root = ET.fromstring(self.files("shared", "inspections")["FM/_PROCESS/Approval/process.xml"])
        self.assertEqual([s.get("name") for s in root.find("States")],
                         ["Draft", "Submitted", "InReview", "Approved", "Rejected"])
        review = root.find("States/State[@name='InReview']")
        self.assertEqual([t.get("role") for t in review.findall("OnInit/Task")], ["Supervisor"])

    def test_the_second_instance_column_is_in_settings(self):
        text = self.files("shared", "inspections")["FM/_DATA/Permit/settings.xml"]
        self.assertIn('name="ApplicationId"', text)
        self.assertNotIn('name="ApplicationId"', self.files("own", "lands")["FM/_DATA/Permit/settings.xml"])


class Sound(Generated):
    def every_file(self):
        for key in self.folders:
            for path in sorted((self.folders[key] / "workspaces").rglob("*")):
                if path.is_file() and "webasm" not in path.relative_to(self.folders[key] / "workspaces").parts[:1]:
                    yield path

    def test_every_xml_and_json_file_parses(self):
        count = 0
        for path in self.every_file():
            text = path.read_text(encoding="utf-8")
            if path.suffix == ".json":
                json.loads(text)
            elif path.suffix in XML_SUFFIXES:
                ET.fromstring(text.encode("utf-8"))
            count += 1
        self.assertGreater(count, 60)

    def test_no_base_reference_anywhere(self):
        for path in self.every_file():
            self.assertNotIn("base:", path.read_text(encoding="utf-8").lower(), str(path))

    def test_titles_and_roles_survive_every_format(self):
        files = self.files("nasty", "inspections")
        self.assertEqual(json.loads(files["FM/_COMPONENTS/sitemap.json"])["title"], NASTY)
        home = json.loads(files["FM/_COMPONENTS/Page/SiteMap/home.json"])
        self.assertEqual(home["content"][0]["content"][0]["content"][0]["value"], NASTY)
        self.assertEqual(ET.fromstring(files["_application.sitemap"]).findtext("title"), NASTY)
        self.assertEqual(ET.fromstring(files["_application-lands.sitemap"]).findtext("title"), NASTY)
        process = ET.fromstring(files["FM/_PROCESS/Approval/process.xml"])
        self.assertEqual(process.get("title"), NASTY)
        self.assertEqual([t.get("role") for t in process.findall(".//Task[@role]")], ["Supervisor's"])
        settings = ET.fromstring(files["FM/_DATA/Permit/settings.xml"])
        self.assertEqual({f.get("title") for f in settings.iter("field") if f.get("name") == "Holder"}, {NASTY})
        folder = "FM/_PROFILE/Main/Lead & Co/_tree.xml"
        tree = ET.fromstring(files[folder])
        self.assertEqual([f.get("title") for f in tree.iter("Folder") if f.get("control")], [NASTY])
        page = json.loads(files["FM/_COMPONENTS/Page/SiteMap/Permits.json"])
        self.assertEqual(page["content"][0]["content"][0]["content"][0]["value"], NASTY)


@unittest.skipUnless(helpers.have_dependencies(), "lxml / jsonschema not installed")
class Validated(Generated):
    """The plugin's validators over the generated workspace files: INFO, and the site map's NO_SCHEMA, only."""

    def findings(self, out):
        return [(line.split()[0], line.split()[1], line.split()[2]) for line in out.splitlines()
                if line.split()[:1] in (["ERROR"], ["WARN"])]

    def check(self, key, directory):
        root = self.folders[key] / "workspaces"
        base = root / directory
        files = [p for p in sorted(base.rglob("*")) if p.is_file() and "_PROFILE" not in p.parts
                 and p.suffix in (".json", ".xml")]
        model = [p for p in files if p.name in ("settings.xml", "_form.xml")]
        process = [p for p in files if p.name in ("process.xml", "_workflow.xml")]
        runs = [("validate_config.py", files, ()), ("resolve_components.py", [p for p in files if p.suffix == ".json"], ()),
                ("validate_model.py", model, ("--workspaces-root", str(root))),
                ("validate_process.py", process, ("--workspaces-root", str(root)))]
        for script, paths, extra in runs:
            if not paths:
                continue
            code, out, err = helpers.run_cli(script, *paths, *extra)
            bad = [f for f in self.findings(out) if not (f[1] == "NO_SCHEMA" and f[2].endswith("sitemap.json"))]
            self.assertEqual(bad, [], f"{script} on {key}:\n{out}{err}")
            self.assertIn(code, (0, 2), f"{script} on {key} exited {code}:\n{out}{err}")

    def test_shared_workspace(self):
        self.check("shared", "inspections")

    def test_own_workspace(self):
        self.check("own", "lands")

    def test_page_only(self):
        self.check("page", "lands")

    def test_special_characters(self):
        self.check("nasty", "inspections")


if __name__ == "__main__":
    unittest.main()
