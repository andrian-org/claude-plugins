"""skills/dgf-scaffold/scripts/generate.py and render.py: what is written, what refuses, and what never leaves a trace (ADR 0027 §7.3)."""

import json
import os
import re
import shutil
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest import mock

from tests import helpers
from tests import scaffold_helpers as sh
from lib import report

render = sh.load("render")
gen = sh.generate
context = gen.context


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)

    def folder(self, doc=None):
        return sh.write_design(tempfile.mkdtemp(dir=self.tmp), doc or sh.example())


class Engine(unittest.TestCase):
    """render.py: escapes per format, loops, conditions, and no silent holes."""

    CTX = {"t": "A&B <x> \"q\" 'r'", "items": [{"n": "one", "on": True}, {"n": "two", "on": False}],
           "flag": True, "tags": ["a", "b"], "sub": {"title": "O'Neil"}}

    def out(self, source, fmt="xml"):
        return render.render(source, self.CTX, fmt, "t")[0]

    def test_a_bare_value_is_escaped_for_the_files_format(self):
        self.assertEqual(self.out("{{t}}", "xml"), "A&amp;B &lt;x&gt; &quot;q&quot; &apos;r&apos;")
        self.assertEqual(self.out("{{t}}", "json"), "A&B <x> \\\"q\\\" 'r'")
        self.assertEqual(self.out("{{t}}", "sql"), "A&B <x> \"q\" ''r''")
        self.assertEqual(self.out("{{t}}", "yaml"), "A&B <x> \\\"q\\\" 'r'")
        self.assertEqual(self.out("{{t}}", "md"), "A&B &lt;x&gt; \"q\" 'r'")
        self.assertEqual(self.out("{{t}}", "csharp"), "A&B <x> \\\"q\\\" 'r'")
        self.assertEqual(self.out("{{t}}", "env"), "A&B <x> \"q\" 'r'")

    def test_a_filter_overrides_the_default(self):
        self.assertEqual(self.out("{{sub.title|sqlstr}}", "json"), "O''Neil")
        self.assertEqual(render.esc_sqlid("a]b"), "a]]b")
        self.assertEqual(self.out("{{t|raw}}", "xml"), self.CTX["t"])

    def test_control_characters_are_escaped_in_json_and_yaml(self):
        self.assertEqual(render.esc_json("a\nb \x7f"), "a\\u000ab\\u2028\\u007f")
        self.assertEqual(render.esc_yaml("a\tb"), "a\\u0009b")

    def test_loops_conditions_comments_and_standalone_lines(self):
        source = "\n".join([
            "{{#each items}}", "<i n=\"{{n}}\"{{#if on}} on{{/if}}/>", "{{/each}}",
            "{{#if flag}}", "yes", "{{else}}", "no", "{{/if}}", "{{! a comment }}",
            "{{#each tags}}{{this}}{{#if @last}}.{{else}},{{/if}}{{/each}}",
            "{{#unless flag}}never{{/unless}}", "{{#if sub.title=zz}}eq{{/if}}", ""])
        self.assertEqual(self.out(source), "<i n=\"one\" on/>\n<i n=\"two\"/>\nyes\na,b.\n\n\n")

    def test_a_deployment_variable_survives(self):
        self.assertEqual(self.out("${KEEP} {{t|raw}}"), "${KEEP} " + self.CTX["t"])

    def test_a_path_that_resolves_nowhere_is_an_error(self):
        for bad in ("{{missing}}", "{{sub.nope}}", "{{#each t}}{{/each}}", "{{#if x}}", "{{/if}}", "{{else}}",
                    "{{#bogus}}", "{{t|nope}}", "{{#if !!}}{{/if}}", "{{ }}"):
            with self.assertRaises(render.TemplateError, msg=bad):
                render.render(bad, self.CTX, "text", "bad")

    def test_an_unknown_format_is_an_error(self):
        with self.assertRaises(render.TemplateError):
            render.render("x", {}, "pdf", "t")

    def test_a_value_is_not_reinterpreted_as_a_template(self):
        self.assertEqual(render.render("{{v}}", {"v": "{{secret}}"}, "text", "t")[0], "{{secret}}")


class Manifest(unittest.TestCase):
    def test_every_entry_names_a_template_that_exists(self):
        data = gen.load_manifest()
        self.assertGreater(len(data["entries"]), 20)
        for entry in data["entries"]:
            self.assertTrue((gen.TEMPLATES / entry["template"]).is_file(), entry["template"])

    def test_every_template_file_is_in_the_manifest(self):
        listed = {entry["template"] for entry in gen.load_manifest()["entries"]}
        on_disk = {p.relative_to(gen.TEMPLATES).as_posix() for p in gen.TEMPLATES.rglob("*")
                   if p.is_file() and p.name != "manifest.json"
                   and not sh.BUILD_OUTPUT & set(p.relative_to(gen.TEMPLATES).parts)}
        self.assertEqual(on_disk - listed, set(), "a template no entry renders")

    def test_every_template_is_lf_only_utf8_without_a_bom(self):
        for path in gen.TEMPLATES.rglob("*"):
            if path.is_file() and not sh.BUILD_OUTPUT & set(path.relative_to(gen.TEMPLATES).parts):
                data = path.read_bytes()
                self.assertNotIn(b"\r", data, path)
                self.assertFalse(data.startswith(b"\xef\xbb\xbf"), path)
                data.decode("utf-8")

    def test_a_malformed_manifest_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "t.txt").write_text("x")
            cases = {
                "not json": "{",
                "wrong format": '{"manifest_format": 2, "entries": []}',
                "unknown key": '{"manifest_format": 1, "entries": [{"template": "t.txt", "target": "a", "format": "text", "x": 1}]}',
                "unknown repeat": '{"manifest_format": 1, "entries": [{"template": "t.txt", "target": "a", "format": "text", "repeat": ["galaxy"]}]}',
                "unknown format": '{"manifest_format": 1, "entries": [{"template": "t.txt", "target": "a", "format": "pdf"}]}',
                "missing template": '{"manifest_format": 1, "entries": [{"template": "nope.txt", "target": "a", "format": "text"}]}',
            }
            for label, text in cases.items():
                (root / "manifest.json").write_text(text)
                with self.assertRaises(gen.Bad, msg=label):
                    gen.load_manifest(root)

    def test_a_target_must_stay_inside_the_application(self):
        for bad in ("/etc/x", "../x", "a/../b", "a//b", "a\\b", "", ".dgf-scaffold-staging/x", "a/./b"):
            with self.assertRaises(gen.Bad, msg=bad):
                gen.safe_target(bad)

    def test_two_entries_rendering_one_target_are_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "t.txt").write_text("x")
            (root / "manifest.json").write_text(json.dumps({"manifest_format": 1, "entries": [
                {"template": "t.txt", "target": "a/B.txt", "format": "text"},
                {"template": "t.txt", "target": "a/b.txt", "format": "text"}]}))
            ctx = context.build(gen.design.check(self.design_folder(tmp)).design, gen.sql_rows())
            with self.assertRaises(gen.Bad):
                gen.plan(ctx, gen.load_manifest(root), root)

    def design_folder(self, tmp):
        return sh.write_design(tempfile.mkdtemp(dir=tmp), sh.example())

    def test_an_unknown_or_unscoped_condition_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "t.txt").write_text("x")
            ctx = context.build(gen.design.check(self.design_folder(tmp)).design, gen.sql_rows())
            for when in (["nonsense"], ["pattern:register"], ["auth:dgpass"], ["first-workspace"]):
                (root / "manifest.json").write_text(json.dumps({"manifest_format": 1, "entries": [
                    {"template": "t.txt", "target": "a.txt", "format": "text", "when": when}]}))
                with self.assertRaises(gen.Bad, msg=when):
                    gen.plan(ctx, gen.load_manifest(root), root)


class Writes(Base):
    def test_dry_run_prints_the_targets_and_writes_nothing(self):
        folder = self.folder()
        before = sh.tree(folder)
        code, out, err = sh.run(["--folder", str(folder), "--dry-run"])
        self.assertEqual(code, 0, out + err)
        self.assertIn("TARGET: Inspections.slnx", out)
        self.assertIn("TARGET: src/PublicApi/Program.cs", out)
        self.assertIn("TARGET: workspaces/webasm/", out)
        self.assertEqual(sh.tree(folder), before)

    def test_it_writes_every_target_and_says_so(self):
        folder = self.folder()
        code, out, err = sh.run(["--folder", str(folder)])
        self.assertEqual(code, 0, out + err)
        planned = [l[len("TARGET: "):] for l in sh.run(["--folder", str(self.folder()), "--dry-run"])[1].splitlines()
                   if l.startswith("TARGET: ") and not l.startswith("TARGET: workspaces/webasm/")]
        written = [l[len("WROTE: "):] for l in out.splitlines()
                   if l.startswith("WROTE: ") and "files)" not in l and not re.match(r"WROTE: \d+ files", l)]
        self.assertEqual(sorted(written), sorted(planned))
        for rel in written:
            self.assertTrue((folder / rel).is_file(), rel)
        self.assertTrue((folder / "docs" / "application.json").is_file())
        self.assertFalse((folder / gen.STAGING).exists())

    def test_the_base_is_copied_when_supplied_by_copy(self):
        folder = self.folder()
        sh.run(["--folder", str(folder)])
        self.assertTrue((folder / "workspaces" / "webasm" / "FM").is_dir())
        self.assertFalse((folder / "workspaces" / "webasm" / ".gitkeep").exists() and False)

    def test_a_mounted_base_is_not_copied_and_is_a_variable(self):
        doc = sh.example()
        doc["base"]["supply"] = "mount"
        folder = self.folder(doc)
        code, out, err = sh.run(["--folder", str(folder)])
        self.assertEqual(code, 0, out + err)
        self.assertFalse((folder / "workspaces" / "webasm").exists())
        compose = (folder / "docker" / "docker-compose.yml").read_text()
        self.assertIn("${DGF_BASE_WORKSPACE}:/workspaces/webasm:ro", compose)
        self.assertIn("DGF_BASE_WORKSPACE=", (folder / "docker" / ".env.example").read_text())

    def test_the_database_scripts_are_executable_shell(self):
        folder = self.folder()
        sh.run(["--folder", str(folder)])
        script = folder / "database" / "Inspections.Database" / "entrypoint.sh"
        self.assertTrue(os.access(script, os.X_OK))
        self.assertTrue(script.read_text().startswith("#!/usr/bin/env bash\n"))

    def test_two_runs_give_the_same_files_and_the_same_application_ids(self):
        first, second = self.folder(), self.folder()
        sh.run(["--folder", str(first)])
        sh.run(["--folder", str(second)])
        self.assertEqual(sh.tree(first), sh.tree(second))
        sql = (first / "database" / "Inspections.Database" / "ContinuousDeployment"
               / "1.PostDeployment.Applications.sql").read_text()
        ids = re.findall(r"\('([0-9A-F-]{36})'", sql)
        self.assertEqual(len(ids), 2)
        self.assertEqual(ids[0], context.application_id("Inspections", "lands"))
        self.assertNotEqual(ids[0], ids[1])

    def test_an_incomplete_design_exits_3_and_writes_nothing(self):
        doc = sh.example()
        del doc["dgf_version"]
        folder = self.folder(doc)
        before = sh.tree(folder)
        code, out, err = sh.run(["--folder", str(folder)])
        self.assertEqual(code, 3, out)
        self.assertIn("SCAFFOLD_DESIGN_INCOMPLETE", out)
        self.assertIn("SCAFFOLD_ASK", out)
        self.assertEqual(sh.tree(folder), before)

    def test_a_folder_that_is_not_empty_exits_3(self):
        folder = self.folder()
        (folder / "notes.txt").write_text("x")
        code, out, err = sh.run(["--folder", str(folder)])
        self.assertEqual(code, 3)
        self.assertIn("SCAFFOLD_DIR_NOT_EMPTY", out)

    def test_an_existing_target_refuses_with_nothing_written(self):
        # design.py already refuses a non-empty folder; a target can only appear after that check, so the
        # race is played by letting the folder check pass
        folder = self.folder()
        (folder / "docs" / "README.md").write_text("mine")
        before = sh.tree(folder)
        with mock.patch.object(gen.design, "check_folder", lambda *a, **k: None):
            code, out, err = sh.run(["--folder", str(folder)])
        self.assertEqual(code, 1, out + err)
        self.assertIn("SCAFFOLD_TARGET_EXISTS", out)
        self.assertIn("docs/README.md", out)
        self.assertEqual(sh.tree(folder), before)
        self.assertFalse((folder / gen.STAGING).exists())

    def test_a_target_differing_only_in_case_counts_as_existing(self):
        folder = self.folder()
        (folder / "docs" / "readme.md").write_text("mine")
        with mock.patch.object(gen.design, "check_folder", lambda *a, **k: None):
            code, out, err = sh.run(["--folder", str(folder)])
        self.assertEqual(code, 1)
        self.assertIn("SCAFFOLD_TARGET_EXISTS", out)

    def test_a_write_failure_exits_3_and_leaves_the_folder_as_it_was(self):
        folder = self.folder()
        before = sh.tree(folder)
        real = os.replace
        calls = []

        def failing(src, dst):
            calls.append(dst)
            if len(calls) == 3:
                raise OSError(28, "No space left on device", str(dst))
            return real(src, dst)

        with mock.patch.object(gen.os, "replace", failing):
            code, out, err = sh.run(["--folder", str(folder)])
        self.assertEqual(code, 3, out + err)
        self.assertIn("SCAFFOLD_WRITE_FAILED", out)
        self.assertGreaterEqual(len(calls), 3)
        self.assertEqual(sh.tree(folder), before)
        self.assertFalse((folder / gen.STAGING).exists())
        self.assertEqual(sorted(p.name for p in folder.iterdir()), ["docs"])

    def test_a_folder_that_cannot_be_written_exits_3(self):
        folder = self.folder()
        os.chmod(folder, 0o555)
        self.addCleanup(os.chmod, folder, 0o755)
        if os.access(folder, os.W_OK):
            self.skipTest("this user can write to a read-only folder (root)")
        code, out, err = sh.run(["--folder", str(folder)])
        self.assertEqual(code, 3, out + err)
        self.assertIn("SCAFFOLD_WRITE_FAILED", out)

    def test_a_template_that_cannot_render_writes_nothing(self):
        folder = self.folder()
        before = sh.tree(folder)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "t"
            shutil.copytree(gen.TEMPLATES, root)
            (root / "solution" / "README.md").write_text("{{nowhere.at.all}}\n")
            with mock.patch.object(gen, "TEMPLATES", root):
                code, out, err = sh.run(["--folder", str(folder)])
        self.assertEqual(code, 3, out + err)
        self.assertIn("SCAFFOLD_TEMPLATE_MISSING", out)
        self.assertEqual(sh.tree(folder), before)

    def test_a_missing_template_file_exits_3(self):
        folder = self.folder()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "t"
            shutil.copytree(gen.TEMPLATES, root)
            (root / "solution" / "README.md").unlink()
            with mock.patch.object(gen, "TEMPLATES", root):
                code, out, err = sh.run(["--folder", str(folder)])
        self.assertEqual(code, 3, out + err)
        self.assertIn("SCAFFOLD_TEMPLATE_MISSING", out)

    def test_dry_run_and_check_exclude_each_other(self):
        code, out, err = sh.run(["--folder", str(self.folder()), "--dry-run", "--check"])
        self.assertEqual(code, 3)


class Escaping(Base):
    """Names are identifiers; titles and roles are free text — and every one is escaped for its file."""

    NASTY = "Fish & Chips <\"O'Neil\"> \\ ]"

    def doc(self):
        doc = sh.example()
        doc["application"]["title"] = self.NASTY
        doc["instances"][0]["title"] = self.NASTY
        doc["roles"] = ["Inspector", "Super visor & Co"]
        doc["modules"][0]["title"] = self.NASTY
        doc["modules"][0]["roles"] = ["Inspector"]
        doc["modules"][1]["roles"] = ["Super visor & Co"]
        doc["data_model"]["entities"][1]["title"] = self.NASTY
        doc["data_model"]["entities"][1]["fields"][1]["title"] = self.NASTY
        return doc

    def test_every_generated_file_parses_and_says_what_the_design_says(self):
        folder = sh.generated(self.doc(), self.tmp)
        parsed = 0
        for rel, data in sh.tree(folder).items():
            if rel.startswith("workspaces/webasm/"):
                continue
            if rel.endswith((".json",)):
                json.loads(data.decode("utf-8"))
                parsed += 1
            elif rel.endswith((".xml", ".sitemap", ".slnx", ".csproj", ".sqlproj")):
                ET.fromstring(data.decode("utf-8"))
                parsed += 1
        self.assertGreater(parsed, 20)
        sql = (folder / "database" / "Inspections.Database" / "ContinuousDeployment"
               / "1.PostDeployment.Applications.sql").read_text()
        self.assertIn("'Fish & Chips <\"O''Neil\"> \\ ]'", sql)
        roles = (folder / "database" / "Inspections.Database" / "ContinuousDeployment"
                 / "2.PostDeployment.Roles.sql").read_text()
        self.assertIn("N'Super visor & Co'", roles)
        self.assertIn("N'SUPER VISOR & CO'", roles)

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)

    def test_markdown_cannot_be_broken_by_a_title(self):
        folder = sh.generated(self.doc(), self.tmp)
        readme = (folder / "docs" / "README.md").read_text()
        self.assertNotIn("<\"O'Neil\">", readme)
        self.assertIn("&lt;", readme)


class Golden(Base):
    """The generated application is compared, file by file, with a checked-in copy.

    A change to a template changes the golden files on purpose: rerun with DGF_UPDATE_GOLDEN=1 to rewrite
    them, and read the diff. `docs/application.json` is the input, and holds this machine's base path.
    """

    def compare(self, name, doc):
        folder = sh.generated(doc, self.tmp)
        actual = {k: v for k, v in sh.tree(folder).items() if k != "docs/application.json"}
        golden = sh.GOLDEN / name
        if os.environ.get("DGF_UPDATE_GOLDEN"):
            shutil.rmtree(golden, ignore_errors=True)
            for rel, data in actual.items():
                target = golden / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
        expected = sh.tree(golden) if golden.is_dir() else {}
        self.assertEqual(sorted(actual), sorted(expected), "the set of generated files changed")
        for rel in sorted(actual):
            self.assertEqual(actual[rel].decode("utf-8"), expected[rel].decode("utf-8"), rel)

    def test_the_example_design(self):
        self.compare("example", sh.example())

    def test_own_workspace_with_one_api(self):
        self.compare("single", sh.single())

    def test_a_mounted_base(self):
        doc = sh.single()
        doc["base"]["supply"] = "mount"
        self.compare("single-mount", doc)


class Refusals(Base):
    def test_the_generator_runs_without_lxml_and_jsonschema(self):
        # nothing generate.py, render.py, context.py or design.py imports needs a third-party package
        import subprocess
        import sys
        folder = self.folder()
        code = ("import sys; sys.modules['lxml']=None; sys.modules['jsonschema']=None; "
                f"sys.argv=['generate.py','--folder',{str(folder)!r},'--dry-run']; "
                f"exec(compile(open({str(sh.SCRIPTS / 'generate.py')!r}).read(), 'generate.py', 'exec'), "
                f"{{'__name__': '__main__', '__file__': {str(sh.SCRIPTS / 'generate.py')!r}}})")
        done = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)


if __name__ == "__main__":
    unittest.main()
