"""skills/dgf-scaffold/scripts/check.py: the post-generation check decides whether a generated application is sound (ADR 0027 §7.10).

Each test breaks exactly one thing in a copy of a sound application and holds the check to one code. The
secrets, structure and route parts are called directly, so they run without lxml and jsonschema; the
validator part needs both and is skipped without them, as the repo's validator tests are.
"""

import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests import helpers
from tests import scaffold_helpers as sh
from lib import deps

gen = sh.generate
check = gen._sibling("check")  # the module generate.py itself runs, so a patch reaches it
report = gen.report
context = gen.context
NEEDS_VALIDATORS = unittest.skipIf(deps.missing(), "lxml and jsonschema are not installed")

APP = None
SINGLE = None
PARENT = None


def setUpModule():
    global APP, SINGLE, PARENT
    PARENT = tempfile.mkdtemp()
    APP = sh.generated(sh.example(), PARENT)
    SINGLE = sh.generated(sh.single(), PARENT)


def tearDownModule():
    shutil.rmtree(PARENT, ignore_errors=True)


def edit(path, change):
    text = Path(path).read_text(encoding="utf-8")
    new = change(text)
    assert new != text, f"the edit changed nothing in {path}"
    Path(path).write_text(new, encoding="utf-8")


def edit_json(path, change):
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    change(doc)
    Path(path).write_text(json.dumps(doc, indent=2), encoding="utf-8")


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.app = sh.copy_of(APP, self.tmp)

    def parts(self, app=None):
        app = app or self.app
        result = gen.design.check(app, generated=True)
        ctx = context.build(result.design, gen.sql_rows())
        targets = [job[0] for job in gen.plan(ctx, gen.load_manifest())]
        return ctx, targets, [w["dir"] for w in ctx["workspaces"]]

    def run_part(self, name, app=None):
        """[(code, message)] of one part of the check."""
        app = app or self.app
        ctx, targets, workspaces = self.parts(app)
        rep = report.Report(str(app))
        if name == "secrets":
            check.check_secrets(app, targets, ctx, rep, report)
        elif name == "structure":
            check.check_structure(app, workspaces, ctx, rep, report, gen.knowledge, gen)
        elif name == "routes":
            check.check_routes(app, workspaces, rep, report, gen)
        elif name == "validators":
            check.check_validators(app, workspaces, ctx, rep, report, gen)
        return [(f.code, f.message) for f in rep.findings]

    def codes(self, name, app=None):
        return [code for code, _ in self.run_part(name, app)]

    def workspace(self):
        return next(p for p in sorted((self.app / "workspaces").iterdir()) if p.name != "webasm")

    def files(self, pattern):
        return sorted(self.workspace().glob(pattern))


class Sound(Base):
    def test_a_sound_application_has_no_finding_in_the_parts_that_need_no_validator(self):
        for part in ("secrets", "structure", "routes"):
            self.assertEqual(self.run_part(part), [], part)

    def test_the_smallest_application_is_sound_too(self):
        app = sh.copy_of(SINGLE, self.tmp)
        for part in ("secrets", "structure", "routes"):
            self.assertEqual(self.run_part(part, app), [], part)

    @NEEDS_VALIDATORS
    def test_the_whole_check_exits_0(self):
        code, out, err = sh.run(["--folder", str(self.app), "--check"])
        self.assertEqual(code, 0, out + err)
        self.assertIn("CHECKS RUN: secrets, structure, routes, validators", out)

    @NEEDS_VALIDATORS
    def test_the_smallest_application_passes_the_whole_check(self):
        code, out, err = sh.run(["--folder", str(sh.copy_of(SINGLE, self.tmp)), "--check"])
        self.assertEqual(code, 0, out + err)

    def test_the_check_reads_the_design_and_refuses_an_incomplete_one(self):
        edit_json(self.app / "docs" / "application.json", lambda d: d.pop("dgf_version"))
        code, out, err = sh.run(["--folder", str(self.app), "--check"])
        self.assertEqual(code, 3, out)
        self.assertIn("SCAFFOLD_DESIGN_INCOMPLETE", out)

    def test_a_generated_file_that_is_gone_is_reported(self):
        (self.app / "docs" / "README.md").unlink()
        code, out, err = sh.run(["--folder", str(self.app), "--check"])
        self.assertIn("SCAFFOLD_STRUCTURE_INVALID", out)
        self.assertIn("docs/README.md", out)


class Secrets(Base):
    def settings(self):
        return self.app / "src" / "PublicApi" / "appsettings.json"

    def test_a_planted_literal_secret_in_settings(self):
        edit(self.settings(), lambda t: t.replace('"${RA_PRIVATE_KEY}"', '"MIIEvQIBADANBgkqhkiG9w0"'))
        self.assertIn("SCAFFOLD_LITERAL_SECRET", self.codes("secrets"))

    def test_a_literal_connection_string(self):
        edit(self.settings(), lambda t: t.replace('"${DB_CONNECTION_STRING}"', '"Server=db;Password=hunter2"'))
        found = self.run_part("secrets")
        self.assertIn("SCAFFOLD_LITERAL_SECRET", [c for c, _ in found])
        self.assertTrue(any("ConnectionStrings" in m for c, m in found))

    def test_a_literal_in_the_compose_environment(self):
        edit(self.app / "docker" / "docker-compose.yml",
             lambda t: t.replace('MSSQL_SA_PASSWORD: "${MSSQL_SA_PASSWORD}"', 'MSSQL_SA_PASSWORD: "hunter2"', 1))
        self.assertIn("SCAFFOLD_LITERAL_SECRET", self.codes("secrets"))

    def test_a_private_key_anywhere(self):
        edit(self.app / "src" / "PublicApi" / "Program.cs",
             lambda t: t + "// -----BEGIN RSA PRIVATE KEY-----\n")
        self.assertIn("SCAFFOLD_LITERAL_SECRET", self.codes("secrets"))

    def test_a_password_assigned_in_a_script(self):
        edit(self.app / "database" / "Inspections.Database" / "entrypoint.sh",
             lambda t: t + 'PASSWORD_FALLBACK="x"\nexport Password=letmein1\n')
        self.assertIn("SCAFFOLD_LITERAL_SECRET", self.codes("secrets"))

    def test_an_undeclared_variable(self):
        edit(self.settings(), lambda t: t.replace('"Languages": ["en-US"]', '"Languages": ["${NOT_DECLARED}"]'))
        found = self.codes("secrets")
        self.assertIn("SCAFFOLD_VAR_UNDECLARED", found)

    def test_a_variable_declared_in_the_env_file_but_not_in_the_documentation(self):
        edit(self.app / "docs" / "configuration.md",
             lambda t: re.sub(r"(?m)^- \*\*\$\{MSSQL_DB\}\*\*.*\n", "", t))
        found = self.run_part("secrets")
        self.assertTrue(any(c == "SCAFFOLD_VAR_UNDECLARED" and "MSSQL_DB" in m and "configuration.md" in m
                            for c, m in found), found)

    def test_a_variable_declared_in_the_documentation_but_not_in_the_env_file(self):
        edit(self.app / "docker" / ".env.example", lambda t: re.sub(r"(?m)^MSSQL_DB=.*\n", "", t))
        found = self.run_part("secrets")
        self.assertTrue(any(c == "SCAFFOLD_VAR_UNDECLARED" and "MSSQL_DB" in m and ".env.example" in m
                            for c, m in found), found)

    def test_a_variable_named_in_a_comment_declares_and_uses_nothing(self):
        edit(self.app / "docker" / "docker-compose.yml", lambda t: "# see ${ONLY_IN_A_COMMENT}\n" + t)
        self.assertEqual(self.run_part("secrets"), [])

    def test_a_setting_the_compose_service_does_not_set(self):
        edit(self.app / "docker" / "docker-compose.yml",
             lambda t: t.replace("Integrations__DgSign__BaseUrl:", "Integrations__DgSign__BaseUri:", 1))
        found = self.run_part("secrets")
        self.assertTrue(any("Integrations.DgSign.BaseUrl" in m and "does not set" in m for c, m in found), found)

    def test_a_setting_the_compose_service_sets_from_another_variable(self):
        edit(self.app / "docker" / "docker-compose.yml",
             lambda t: t.replace('Integrations__DgSign__BaseUrl: "${SIGN_BASE_URL}"',
                                 'Integrations__DgSign__BaseUrl: "${NOTIFY_BASE_URL}"', 1))
        found = self.run_part("secrets")
        self.assertTrue(any("Integrations.DgSign.BaseUrl" in m and "compose sets" in m for c, m in found), found)

    def test_only_the_deployment_variables_of_an_authentication_provider_that_is_used_exist(self):
        env = (self.app / "docker" / ".env.example").read_text()
        self.assertIn("PUBLICAPI_LANDSPUBLIC_DGPASS_CLIENT_SECRET=", env)
        self.assertNotIn("PUBLICAPI_LANDSPUBLIC_AZURE", env)
        self.assertIn("STAFFAPI_LANDSSTAFF_AZURE_CLIENT_SECRET=", env)

    def test_a_secret_has_no_example_value(self):
        env = (self.app / "docker" / ".env.example").read_text()
        for name in ("MSSQL_SA_PASSWORD", "RA_PRIVATE_KEY", "NUGET_FEED_TOKEN", "DB_CONNECTION_STRING"):
            self.assertRegex(env, rf"(?m)^{name}=$")


class Structure(Base):
    def tree_files(self):
        return self.files("FM/_PROFILE/*/*/_tree.xml")

    def test_a_malformed_tree(self):
        target = self.tree_files()[0]
        target.write_text(target.read_text()[:60])
        self.assertIn("SCAFFOLD_STRUCTURE_INVALID", self.codes("structure"))

    def test_a_tree_with_the_wrong_root(self):
        edit(self.tree_files()[0], lambda t: t.replace("<Tree", "<Forest").replace("</Tree>", "</Forest>"))
        self.assertIn("SCAFFOLD_STRUCTURE_INVALID", self.codes("structure"))

    def test_a_map_without_a_required_element(self):
        edit(self.workspace() / "_application.sitemap", lambda t: re.sub(r"<dbprefix>.*?</dbprefix>", "", t))
        found = self.run_part("structure")
        self.assertTrue(any("dbprefix" in m for c, m in found), found)

    def test_a_map_whose_root_lacks_an_attribute(self):
        edit(self.workspace() / "_application.sitemap", lambda t: t.replace(' visible="true"', "", 1))
        self.assertIn("SCAFFOLD_STRUCTURE_INVALID", self.codes("structure"))

    def test_a_missing_per_instance_map(self):
        (self.workspace() / "_application-lands.sitemap").unlink()
        self.assertIn("SCAFFOLD_STRUCTURE_INVALID", self.codes("structure"))

    def test_a_profile_without_a_members_group(self):
        group = next(p for p in (self.workspace() / "FM" / "_PROFILE").glob("*/Members"))
        group.rename(group.parent / "Somebody")
        found = self.run_part("structure")
        self.assertTrue(any("Members" in m for c, m in found), found)

    def test_a_tree_folder_whose_node_file_is_missing(self):
        node = next(p for p in self.files("FM/_PROFILE/*/*/*.xml") if p.name != "_tree.xml")
        node.unlink()
        self.assertIn("SCAFFOLD_STRUCTURE_INVALID", self.codes("structure"))

    def test_a_node_file_with_the_wrong_root(self):
        node = next(p for p in self.files("FM/_PROFILE/*/*/*.xml") if p.name != "_tree.xml")
        edit(node, lambda t: t.replace("mapNode", "mapnode"))
        self.assertIn("SCAFFOLD_STRUCTURE_INVALID", self.codes("structure"))

    def test_a_map_with_no_tab_for_a_profile(self):
        edit(self.workspace() / "_application.sitemap", lambda t: t.replace('type="PROFILE"', 'type="Page"'))
        found = self.run_part("structure")
        self.assertTrue(any("PROFILE tab" in m for c, m in found), found)

    def test_a_rule_this_check_does_not_know_is_a_defect_of_the_table_not_of_the_application(self):
        rows = gen.knowledge.index("workspace-minimum")
        forged = {k: dict(v) for k, v in rows.items()}
        forged["_application.sitemap"]["Rule"] = "profile-tab teleport"
        with mock.patch.object(gen.knowledge, "index", lambda *a, **k: forged):
            with self.assertRaises(check.Bad):
                self.run_part("structure")


class Routes(Base):
    def sitemap(self):
        return self.workspace() / "FM" / "_COMPONENTS" / "sitemap.json"

    def routes(self, doc):
        return doc["routes"]["routes"]

    def test_a_missing_login_route(self):
        edit_json(self.sitemap(), lambda d: self.routes(d).__setitem__(
            slice(None), [r for r in self.routes(d) if r.get("path") != "/login"]))
        found = self.run_part("routes")
        self.assertTrue(any(c == "SCAFFOLD_ROUTE_UNRESOLVED" and "/login" in m for c, m in found), found)

    def test_a_route_to_a_missing_page(self):
        def change(doc):
            route = self.routes(doc)[-1]
            route["content"][0]["name"] = "SiteMap/Nowhere"
        edit_json(self.sitemap(), change)
        found = self.run_part("routes")
        self.assertTrue(any(c == "SCAFFOLD_ROUTE_UNRESOLVED" and "Nowhere" in m for c, m in found), found)

    def test_a_page_named_in_the_wrong_case(self):
        def change(doc):
            route = self.routes(doc)[0]
            route["content"][0]["name"] = route["content"][0]["name"].lower().replace("sitemap", "SiteMap")
        edit_json(self.sitemap(), change)
        home = self.workspace() / "FM" / "_COMPONENTS" / "Page" / "SiteMap"
        # only a case-sensitive lookup can tell: HOME.json is not home.json on Linux
        edit_json(self.sitemap(), lambda d: self.routes(d)[0]["content"][0].__setitem__("name", "SiteMap/HOME"))
        self.assertTrue(home.is_dir())
        found = self.run_part("routes")
        self.assertTrue(any("HOME" in m for c, m in found), found)

    def test_a_landing_route_that_is_the_root(self):
        edit_json(self.sitemap(), lambda d: self.routes(d)[0].__setitem__("path", "/"))
        found = self.run_part("routes")
        self.assertTrue(any("landing" in m for c, m in found), found)

    def test_no_routes_at_all(self):
        edit_json(self.sitemap(), lambda d: d["routes"].__setitem__("routes", []))
        self.assertIn("SCAFFOLD_ROUTE_UNRESOLVED", self.codes("routes"))

    def test_a_login_page_that_lists_no_method(self):
        login = self.workspace() / "FM" / "_COMPONENTS" / "Page" / "SiteMap" / "loginPage.json"

        def change(doc):
            def walk(node):
                if isinstance(node, dict):
                    if node.get("type") == "login":
                        node["authenticationMethods"] = []
                    for value in node.values():
                        walk(value)
                elif isinstance(node, list):
                    for value in node:
                        walk(value)
            walk(doc)
        edit_json(login, change)
        found = self.run_part("routes")
        self.assertTrue(any("login component" in m for c, m in found), found)

    def test_a_router_without_its_profile(self):
        profiles = self.workspace() / "FM" / "_PROFILE"
        shutil.rmtree(next(profiles.iterdir()))
        self.assertIn("SCAFFOLD_ROUTE_UNRESOLVED", self.codes("routes"))

    def test_a_missing_sitemap(self):
        self.sitemap().unlink()
        self.assertIn("SCAFFOLD_ROUTE_UNRESOLVED", self.codes("routes"))


@NEEDS_VALIDATORS
class Validators(Base):
    def test_no_schema_on_a_sitemap_is_allowed_and_really_happens(self):
        import subprocess
        import sys
        done = subprocess.run([sys.executable, str(helpers.PLUGIN_ROOT / "scripts" / "validate_config.py"),
                               str(self.workspace() / "FM" / "_COMPONENTS" / "sitemap.json")],
                              capture_output=True, text=True)
        self.assertIn("NO_SCHEMA", done.stdout)
        self.assertEqual(self.run_part("validators"), [])

    def test_a_warning_outside_the_allow_list_is_a_failure_quoting_the_validator(self):
        page = self.workspace() / "FM" / "_COMPONENTS" / "Page" / "SiteMap" / "home.json"
        edit_json(page, lambda d: d.__setitem__("noSuchProperty", 1))
        found = self.run_part("validators")
        self.assertTrue(any(c == "SCAFFOLD_VALIDATION_FAILED" and "UNKNOWN_PROPERTY" in m and m.startswith("validate_config.py")
                            for c, m in found), found)

    def test_an_error_is_a_failure(self):
        page = self.workspace() / "FM" / "_COMPONENTS" / "Page" / "SiteMap" / "home.json"
        edit_json(page, lambda d: d.__setitem__("type", "NoSuchComponentType"))
        found = self.codes("validators")
        self.assertIn("SCAFFOLD_VALIDATION_FAILED", found)

    def test_the_copied_bases_own_findings_are_not_the_generators(self):
        bad = self.app / "workspaces" / "webasm" / "FM" / "_COMPONENTS" / "Broken.json"
        bad.parent.mkdir(parents=True, exist_ok=True)
        bad.write_text('{"type": "NoSuchThing"')
        self.assertEqual(self.run_part("validators"), [])

    def test_the_process_validator_runs_only_when_the_design_has_a_process(self):
        seen = []

        def record(folder, script, args, rep, report, sitemap_ok=True):
            seen.append((script, list(args)))

        with mock.patch.object(check, "run_validator", record):
            self.run_part("validators")
            with_process = [s for s, _ in seen]
            seen.clear()
            self.run_part("validators", sh.copy_of(SINGLE, self.tmp))
            without = [s for s, _ in seen]
        self.assertIn("validate_process.py", with_process)
        self.assertNotIn("validate_process.py", without)
        for script in ("validate_config.py", "resolve_components.py", "validate_model.py"):
            self.assertIn(script, with_process)
            self.assertIn(script, without)

    def test_no_validator_is_run_over_the_whole_root(self):
        seen = []
        with mock.patch.object(check, "run_validator", lambda f, s, a, r, p, sitemap_ok=True: seen.append(list(a))):
            self.run_part("validators")
        for args in seen:
            self.assertNotIn("--all", args)
            scanned = [a for i, a in enumerate(args) if not (i and args[i - 1] == "--workspaces-root")]
            for arg in scanned:
                self.assertNotEqual(arg.rstrip("/"), "workspaces")
                self.assertNotIn("webasm", arg)


class Cannot(Base):
    """A validator that cannot run is not a finding about the application."""

    def fake(self, body):
        scripts = Path(self.tmp) / "scripts"
        scripts.mkdir()
        for name in ("validate_config", "resolve_components", "validate_model", "validate_process"):
            (scripts / f"{name}.py").write_text(body)
        return scripts

    def test_a_missing_dependency_is_relayed_as_exit_3(self):
        scripts = self.fake("import sys\nprint('ERROR DEPENDENCY_MISSING lxml, jsonschema not installed', file=sys.stderr)\n"
                            "sys.exit(3)\n")
        with mock.patch.object(check, "SCRIPTS", scripts):
            code, out, err = sh.run(["--folder", str(self.app), "--check"])
        self.assertEqual(code, 3, out)
        self.assertIn("DEPENDENCY_MISSING", out)

    def test_an_unresolved_family_on_a_generated_file_is_a_validation_failure(self):
        scripts = self.fake("import sys\nprint('ERROR FAMILY_UNRESOLVED workspaces/x/FM/_COMPONENTS/a.json no family')\n"
                            "sys.exit(3)\n")
        with mock.patch.object(check, "SCRIPTS", scripts):
            found = self.run_part("validators")
        self.assertIn("SCAFFOLD_VALIDATION_FAILED", [c for c, _ in found])
        self.assertTrue(any("FAMILY_UNRESOLVED" in m for c, m in found))

    def test_any_other_exit_3_is_a_validation_failure_quoting_it(self):
        scripts = self.fake("import sys\nprint('the roof is on fire', file=sys.stderr)\nsys.exit(3)\n")
        with mock.patch.object(check, "SCRIPTS", scripts):
            found = self.run_part("validators")
        self.assertTrue(any("the roof is on fire" in m for c, m in found), found)


if __name__ == "__main__":
    unittest.main()
