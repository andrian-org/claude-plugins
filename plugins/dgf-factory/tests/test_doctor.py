"""doctor.py against temporary copies of the plugin — never the real tree for faults."""

import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from tests import helpers

DOCTOR = Path("skills") / "dgf-doctor" / "scripts" / "doctor.py"
GATE = re.compile(r"```dgf-gate-result\n(.*?)\n```", re.S)


def load_doctor(root):
    import importlib.util
    spec = importlib.util.spec_from_file_location("doctor_under_test", root / DOCTOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def gate(stdout):
    """The last gate block — the only part callers may parse."""
    return json.loads(GATE.findall(stdout)[-1])


def gate_entries(stdout, list_name):
    """The entry ids in one list of the last gate block: `blockers` or `warnings`."""
    return [entry["id"] for entry in gate(stdout)[list_name]]


def every_id(stdout):
    """Both lists together — a negative assertion must read both, or a warning passes it vacuously."""
    return gate_entries(stdout, "blockers") + gate_entries(stdout, "warnings")


SECTIONS = ["manifest", "component-paths", "skill-slices", "portability", "line-endings", "validator-runtime"]


class DoctorOnACopy(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.root = Path(self.tmp) / "dgf-factory"
        shutil.copytree(helpers.PLUGIN_ROOT, self.root,
                        ignore=shutil.ignore_patterns(".venv", "__pycache__", ".claude", "tests"))

    def run_doctor(self):
        return helpers.run_cli(self.root / DOCTOR, self.root)

    def test_real_tree_is_clean_or_warns_about_dependencies_only(self):
        code, out, _ = self.run_doctor()
        self.assertIn(code, (0, 2), out)
        self.assertEqual(gate_entries(out, "blockers"), [], out)
        if code == 2:
            self.assertEqual(set(gate_entries(out, "warnings")), {"VALIDATOR_DEPS_MISSING"}, out)

    def test_the_block_is_the_doctors_own_and_claims_only_what_ran(self):
        code, out, _ = self.run_doctor()
        payload = gate(out)
        self.assertEqual(payload["gate"], "doctor")
        self.assertEqual(payload["status"], {0: "pass", 2: "warn"}[code], out)
        self.assertIs(payload["blocking"], False)
        self.assertIsNone(payload["suggested_next"]["command"])
        self.assertEqual(payload["checks_run"], SECTIONS)
        for absent in ("schema_family", "affected_components", "affected_processes"):
            self.assertNotIn(absent, payload)
        self.assertIn("CHECKS RUN: " + ", ".join(SECTIONS), out)
        self.assertTrue(out.rstrip().endswith("```"), out[-200:])
        self.assertNotIn("/dgf-fix", out)

    def test_a_failing_copy_blocks_and_suggests_no_command(self):
        (self.root / "scripts" / "requirements.txt").unlink()
        code, out, _ = self.run_doctor()
        payload = gate(out)
        self.assertEqual(code, 1, out)
        self.assertEqual((payload["status"], payload["blocking"]), ("fail", True))
        self.assertIsNone(payload["suggested_next"]["command"])
        self.assertNotIn("/dgf-fix", out)
        self.assertTrue(out.rstrip().endswith("```"), out[-200:])

    def test_a_section_that_cannot_run_is_a_warning_not_a_pass(self):
        # The real doctor checks a copy with no scripts/: its own builder is still there (ADR 0020 §1).
        # Only dgf-doctor is kept, because the other skills cite scripts/ and would dangle.
        for path in (self.root / "skills").iterdir():
            if path.name != "dgf-doctor":
                shutil.rmtree(path)
        shutil.rmtree(self.root / "scripts")
        code, out, _ = helpers.run_cli(helpers.PLUGIN_ROOT / DOCTOR, self.root)
        self.assertEqual(code, 2, out)
        self.assertEqual(gate_entries(out, "warnings"), ["not-run-validator-runtime"], out)
        self.assertNotIn("validator-runtime", gate(out)["checks_run"])
        self.assertIn("NOT RUN: validator-runtime (no scripts/ directory", out)

    def test_a_missing_builder_is_exit_3_with_no_block(self):
        builder = self.root / "scripts" / "lib" / "gate_result.py"
        builder.unlink()
        code, out, err = self.run_doctor()
        self.assertEqual(code, 3, out + err)
        self.assertNotIn("dgf-gate-result", out)
        self.assertIn(str(builder.resolve()), err)

    def test_a_builder_that_does_not_load_or_lacks_its_api_is_exit_3(self):
        builder = self.root / "scripts" / "lib" / "gate_result.py"
        for text in ('raise RuntimeError("broken on import")\n', '"""A builder with nothing in it."""\n'):
            with self.subTest(text=text):
                builder.write_text(text, encoding="utf-8")
                code, out, err = self.run_doctor()
                self.assertEqual(code, 3, out + err)
                self.assertNotIn("dgf-gate-result", out)
                self.assertIn(str(builder.resolve()), err)
                self.assertNotIn("Traceback", err)

    def test_requirement_without_hash_blocks(self):
        (self.root / "scripts" / "requirements.txt").write_text("lxml==6.1.3\n", encoding="utf-8")
        code, out, _ = self.run_doctor()
        self.assertEqual(code, 1, out)
        self.assertIn("REQUIREMENTS_UNPINNED", gate_entries(out, "blockers"))

    def test_unpinned_requirement_blocks(self):
        (self.root / "scripts" / "requirements.txt").write_text(
            "lxml>=6 \\\n    --hash=sha256:" + "a" * 64 + "\n", encoding="utf-8")
        code, out, _ = self.run_doctor()
        self.assertEqual(code, 1, out)
        self.assertIn("REQUIREMENTS_UNPINNED", gate_entries(out, "blockers"))

    def test_missing_requirements_file_blocks(self):
        (self.root / "scripts" / "requirements.txt").unlink()
        code, out, _ = self.run_doctor()
        self.assertEqual(code, 1, out)
        self.assertIn("REQUIREMENTS_UNPINNED", gate_entries(out, "blockers"))

    def test_broken_table_marker_blocks(self):
        path = self.root / "knowledge" / "json-reader.md"
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace("<!-- machine-read: component-folders -->", ""), encoding="utf-8")
        code, out, _ = self.run_doctor()
        self.assertEqual(code, 1, out)
        self.assertIn("KNOWLEDGE_TABLE", gate_entries(out, "blockers"))

    def test_dgf_path_in_a_shipped_script_blocks(self):
        dgf_path = "src" + "/" + "Core" + "/DGF.Kernel/WorkspaceSettings.cs"
        (self.root / "scripts" / "lib" / "planted.py").write_text(
            f'"""Mirrors {dgf_path}."""\n', encoding="utf-8")
        code, out, _ = self.run_doctor()
        self.assertEqual(code, 1, out)
        self.assertIn("DGF_PATH", gate_entries(out, "blockers"))

    def test_bytecode_is_not_scanned(self):
        cache = self.root / "scripts" / "lib" / "__pycache__"
        cache.mkdir(exist_ok=True)
        (cache / "x.cpython-39.pyc").write_bytes(b"\x00\x01\r\n\x02")
        code, out, _ = self.run_doctor()
        self.assertNotIn("CRLF", every_id(out), out)
        self.assertIn(code, (0, 2), out)

    # --- the spine slices, plugin paths and YAML-safe frontmatter (DD12) ------------

    def write_skill(self, name, frontmatter, body=""):
        path = self.root / "skills" / name / "SKILL.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("---\n" + "\n".join(frontmatter) + "\n---\n\n# Skill\n" + body, encoding="utf-8")
        return path

    FRONTMATTER = ["name: dgf-plan", "description: Plan a DGF change. Use for \"dgf plan\".",
                   "argument-hint: \"[fast | full | ultra] <description>\"",
                   "allowed-tools: Read Bash(python3 *)", "disable-model-invocation: false", "version: 0.1.0"]

    def test_expected_slices_report_present_or_not_yet_built(self):
        code, out, _ = self.run_doctor()
        for name in ("dgf", "dgf-plan", "dgf-implement", "dgf-verify", "dgf-commit"):
            self.assertRegex(out, rf"INFO  skills/{name}/ — (present|not yet built)")
        self.write_skill("dgf-plan", self.FRONTMATTER)
        _, out, _ = self.run_doctor()
        self.assertIn("INFO  skills/dgf-plan/ — present", out)

    def test_a_dangling_plugin_path_blocks_with_file_and_line(self):
        token = "${" + "CLAUDE_PLUGIN_ROOT}"
        self.write_skill("dgf-plan", self.FRONTMATTER, f'\nRun:\n\n    python3 "{token}/scripts/no_such.py"\n')
        code, out, _ = self.run_doctor()
        self.assertEqual(code, 1, out)
        self.assertEqual(gate_entries(out, "blockers").count("PLUGIN_PATH_DANGLING"), 1, out)
        self.assertRegex(out, r"skills/dgf-plan/SKILL\.md:\d+ cites `\$\{CLAUDE_PLUGIN_ROOT\}/scripts/no_such\.py`")

    def test_template_and_existing_plugin_paths_are_clean(self):
        token = "${" + "CLAUDE_PLUGIN_ROOT}"
        body = (f"\nRead `{token}/knowledge/README.md`, then `{token}/knowledge/schemas/`.\n"
                f"A component is `{token}/knowledge/schemas/json/<Type>.schema.json`; globs `{token}/scripts/*.py`.\n"
                f'Run python3 "{token}/scripts/check_plan.py".\n')
        self.write_skill("dgf-plan", self.FRONTMATTER, body)
        code, out, _ = self.run_doctor()
        self.assertNotIn("PLUGIN_PATH_DANGLING", every_id(out), out)
        self.assertIn(code, (0, 2), out)

    def test_unquoted_yaml_indicators_block(self):
        for bad in ("argument-hint: [fast | full | ultra] <description>", "description: Plan: a DGF change"):
            key = bad.split(":")[0]
            frontmatter = [line for line in self.FRONTMATTER if not line.startswith(key + ":")] + [bad]
            with self.subTest(bad=bad):
                self.write_skill("dgf-plan", frontmatter)
                code, out, _ = self.run_doctor()
                self.assertEqual(code, 1, out)
                self.assertEqual(gate_entries(out, "blockers"), ["SKILL_FRONTMATTER_YAML"], out)
                self.assertIn(f"`{key}`", out)

    def test_more_yaml_shapes_the_flat_parser_misreads(self):
        doctor = load_doctor(self.root)
        for value, unsafe in (("- a list item", True), ("ends with a colon:", True), ('"never closes', True),
                              ("'single'", False), ('"double"', False), ("0.1.0", False)):
            self.assertEqual(doctor.yaml_unsafe(value) is not None, unsafe, value)

    def test_a_plugin_path_in_the_wrong_case_dangles(self):
        token = "${" + "CLAUDE_PLUGIN_ROOT}"
        self.write_skill("dgf-plan", self.FRONTMATTER, f'\nRun python3 "{token}/scripts/Check_Plan.py".\n')
        code, out, _ = self.run_doctor()
        self.assertEqual(code, 1, out)
        self.assertIn("PLUGIN_PATH_DANGLING", gate_entries(out, "blockers"))

    def test_quoted_values_and_tool_lists_are_clean(self):
        self.write_skill("dgf-plan", self.FRONTMATTER + [])
        code, out, _ = self.run_doctor()
        self.assertNotIn("SKILL_FRONTMATTER_YAML", every_id(out), out)
        self.assertIn(code, (0, 2), out)


if __name__ == "__main__":
    unittest.main()
