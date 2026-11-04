"""doctor.py against temporary copies of the package source, and against installed projects."""

import json
import os
import re
import shutil
import subprocess
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


SECTIONS = ["install", "skill-slices", "portability", "line-endings", "validator-runtime"]
TOKEN = "{{" + "dgf_runtime}}"


class DoctorOnACopy(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.root = Path(self.tmp) / "dgf-factory"
        shutil.copytree(helpers.PLUGIN_ROOT, self.root,
                        ignore=shutil.ignore_patterns(".venv", "__pycache__", ".claude", ".claude-plugin", "tests",
                                                      "node_modules", "obj"))

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
        self.assertNotIn("/dgf-fix", json.dumps(payload))  # build progress names skills/dgf-fix/; the block never does

    def test_a_failing_copy_blocks_and_suggests_no_command(self):
        (self.root / "scripts" / "requirements.txt").unlink()
        code, out, _ = self.run_doctor()
        payload = gate(out)
        self.assertEqual(code, 1, out)
        self.assertEqual((payload["status"], payload["blocking"]), ("fail", True))
        self.assertIsNone(payload["suggested_next"]["command"])
        self.assertNotIn("/dgf-fix", json.dumps(payload))
        self.assertTrue(out.rstrip().endswith("```"), out[-200:])

    def test_a_section_that_cannot_run_is_a_warning_not_a_pass(self):
        # The real doctor checks a copy with no scripts/: its own builder is still there (ADR 0022 §1).
        # Only dgf-doctor is kept, because the other skills and the agents cite scripts/ and would dangle.
        for path in (self.root / "skills").iterdir():
            if path.name != "dgf-doctor":
                shutil.rmtree(path)
        shutil.rmtree(self.root / "agents", ignore_errors=True)
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
        for name in ("dgf", "dgf-plan", "dgf-implement", "dgf-verify", "dgf-commit", "dgf-fix", "dgf-evolve",
                     "dgf-component", "dgf-process", "dgf-audit", "dgf-model", "dgf-scaffold",
                     "dgf-review", "dgf-rules", "dgf-rules-check", "dgf-qa", "dgf-docs", "dgf-explore", "dgf-grounded", "dgf-archive", "dgf-security"):
            self.assertRegex(out, rf"INFO  skills/{name}/ — (present|not yet built)")
        self.write_skill("dgf-plan", self.FRONTMATTER)
        _, out, _ = self.run_doctor()
        self.assertIn("INFO  skills/dgf-plan/ — present", out)

    def test_a_dangling_runtime_path_blocks_with_file_and_line(self):
        self.write_skill("dgf-plan", self.FRONTMATTER, f'\nRun:\n\n    python3 "{TOKEN}/scripts/no_such.py"\n')
        code, out, _ = self.run_doctor()
        self.assertEqual(code, 1, out)
        self.assertEqual(gate_entries(out, "blockers").count("RUNTIME_PATH_DANGLING"), 1, out)
        self.assertRegex(out, r"skills/dgf-plan/SKILL\.md:\d+ cites `\{\{dgf_runtime\}\}/scripts/no_such\.py`")

    def test_template_and_existing_runtime_paths_are_clean(self):
        token = TOKEN
        body = (f"\nRead `{token}/knowledge/README.md`, then `{token}/knowledge/schemas/`.\n"
                f"A component is `{token}/knowledge/schemas/json/<Type>.schema.json`; globs `{token}/scripts/*.py`.\n"
                f'Run python3 "{token}/scripts/check_plan.py".\n')
        self.write_skill("dgf-plan", self.FRONTMATTER, body)
        code, out, _ = self.run_doctor()
        self.assertNotIn("RUNTIME_PATH_DANGLING", every_id(out), out)
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

    def test_a_runtime_path_in_the_wrong_case_dangles(self):
        self.write_skill("dgf-plan", self.FRONTMATTER, f'\nRun python3 "{TOKEN}/scripts/Check_Plan.py".\n')
        code, out, _ = self.run_doctor()
        self.assertEqual(code, 1, out)
        self.assertIn("RUNTIME_PATH_DANGLING", gate_entries(out, "blockers"))

    def test_a_link_out_of_the_shipped_set_blocks(self):
        self.write_skill("dgf-plan", self.FRONTMATTER, "\nSee [the ADRs](../../docs/adr/README.md).\n")
        code, out, _ = self.run_doctor()
        self.assertEqual(code, 1, out)
        self.assertIn("LINK_LEAVES_SHIPPED", gate_entries(out, "blockers"))

    def test_links_inside_the_shipped_set_and_urls_are_clean(self):
        self.write_skill("dgf-plan", self.FRONTMATTER,
                         "\nSee [x](../dgf/SKILL.md), [y](https://example.org/a.md) and [z](#anchor).\n")
        code, out, _ = self.run_doctor()
        self.assertNotIn("LINK_LEAVES_SHIPPED", every_id(out), out)

    def test_the_package_source_needs_package_json(self):
        (self.root / "package.json").unlink()
        code, out, _ = self.run_doctor()
        self.assertEqual(code, 1, out)
        self.assertIn("PACKAGE_MISSING", gate_entries(out, "blockers"))

    def test_quoted_values_and_tool_lists_are_clean(self):
        self.write_skill("dgf-plan", self.FRONTMATTER + [])
        code, out, _ = self.run_doctor()
        self.assertNotIn("SKILL_FRONTMATTER_YAML", every_id(out), out)
        self.assertIn(code, (0, 2), out)


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class DoctorInAProject(unittest.TestCase):
    """The doctor an installed project runs: `.dgf-factory/runtime/skills/dgf-doctor/scripts/doctor.py`."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.project = Path(self.tmp) / "project"
        self.project.mkdir()
        done = subprocess.run(["node", str(helpers.PLUGIN_ROOT / "bin" / "dgf-factory.mjs"), "setup", "--root",
                               str(self.project), "--harness", "claude,gemini", "--yes", "--no-python"],
                              capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.runtime = self.project / ".dgf-factory" / "runtime"

    def run_doctor(self):
        return helpers.run_cli(self.runtime / DOCTOR, env={"PATH": "/usr/bin:/bin"})

    def test_a_fresh_install_is_clean(self):
        code, out, _ = self.run_doctor()
        self.assertIn(code, (0, 2), out)
        self.assertEqual(gate_entries(out, "blockers"), [], out)
        if code == 2:
            self.assertEqual(set(gate_entries(out, "warnings")), {"VALIDATOR_DEPS_MISSING"}, out)
        self.assertEqual(gate(out)["checks_run"], SECTIONS)
        shipped = sum(1 for path in (helpers.PLUGIN_ROOT / "skills").iterdir() if (path / "SKILL.md").is_file())
        self.assertIn(f"claude — all {shipped} skills installed", out)

    def test_an_edited_skill_warns(self):
        skill = self.project / ".claude" / "skills" / "dgf-plan" / "SKILL.md"
        skill.write_text(skill.read_text(encoding="utf-8") + "\nmine\n", encoding="utf-8")
        code, out, _ = self.run_doctor()
        self.assertIn("INSTALL_FILE_EDITED", gate_entries(out, "warnings"), out)
        self.assertEqual(gate_entries(out, "blockers"), [], out)

    def test_a_missing_skill_blocks(self):
        (self.project / ".gemini" / "skills" / "dgf-audit" / "SKILL.md").unlink()
        code, out, _ = self.run_doctor()
        self.assertEqual(code, 1, out)
        self.assertIn("INSTALL_FILE_MISSING", gate_entries(out, "blockers"))

    def test_a_harness_missing_a_skill_in_the_receipt_blocks(self):
        receipt = self.project / ".dgf-factory" / "install.json"
        data = json.loads(receipt.read_text(encoding="utf-8"))
        del data["files"][".claude/skills/dgf-model/SKILL.md"]
        receipt.write_text(json.dumps(data), encoding="utf-8")
        code, out, _ = self.run_doctor()
        self.assertEqual(code, 1, out)
        self.assertIn("INSTALL_HARNESS_INCOMPLETE", gate_entries(out, "blockers"))

    def test_a_dangling_rendered_path_in_a_harness_skill_blocks(self):
        skill = self.project / ".claude" / "skills" / "dgf-plan" / "SKILL.md"
        skill.write_text(skill.read_text(encoding="utf-8") + '\npython3 ".dgf-factory/runtime/scripts/gone.py"\n',
                         encoding="utf-8")
        code, out, _ = self.run_doctor()
        self.assertEqual(code, 1, out)
        self.assertIn("RUNTIME_PATH_DANGLING", gate_entries(out, "blockers"))

    @unittest.skipUnless(shutil.which("git"), "git is not installed")
    def test_a_committed_venv_blocks_and_is_never_run(self):
        marker = Path(self.tmp) / "ran"
        python = self.runtime / ".venv" / "bin" / "python"
        python.parent.mkdir(parents=True)
        python.write_text(f"#!/bin/sh\ntouch '{marker}'\nexit 0\n", encoding="utf-8")
        python.chmod(0o755)
        subprocess.run(["git", "init", "-q"], cwd=self.project, check=True)
        subprocess.run(["git", "-c", "core.autocrlf=false", "add", "-f", ".dgf-factory/runtime/.venv/bin/python"], cwd=self.project, check=True)
        code, out, _ = self.run_doctor()
        self.assertEqual(code, 1, out)
        self.assertIn("INSTALL_VENV_COMMITTED", gate_entries(out, "blockers"), out)
        self.assertFalse(marker.exists(), "the committed interpreter ran")

    def test_a_receipt_entry_setup_never_writes_blocks(self):
        receipt = self.project / ".dgf-factory" / "install.json"
        data = json.loads(receipt.read_text(encoding="utf-8"))
        (self.project / "src").mkdir()
        (self.project / "src" / "Program.cs").write_text("class P {}\n", encoding="utf-8")
        data["files"]["src/Program.cs"] = {"source": "scripts/x.py", "owner": "runtime", "sourceHash": "a",
                                           "installedHash": "b"}
        receipt.write_text(json.dumps(data), encoding="utf-8")
        code, out, _ = self.run_doctor()
        self.assertEqual(code, 1, out)
        self.assertIn("INSTALL_RECEIPT_ENTRY_MISPLACED", gate_entries(out, "blockers"), out)
        self.assertNotIn("INSTALL_FILE_EDITED", every_id(out), out)



@unittest.skipUnless(shutil.which("node"), "node is not installed")
class DoctorLine(unittest.TestCase):
    """The installed DGF line against the estate's declared version, and the version gate (ADR 0036 §6)."""

    setUp_install = DoctorInAProject.setUp
    run_doctor = DoctorInAProject.run_doctor

    def setUp(self):
        self.setUp_install()
        receipt = json.loads((self.project / ".dgf-factory" / "install.json").read_text(encoding="utf-8"))
        self.line = receipt["dgfLine"]
        self.knowledge = self.runtime / "knowledge"

    def declare(self, version):
        (self.project / ".dgf-factory" / "config.yaml").write_text(f'dgf:\n  version: "{version}"\n', encoding="utf-8")

    def restamp(self, version, extra=""):
        """Every installed fact stamped `version` (an edit the doctor also warns about); `extra` joins one fact's frontmatter."""
        import re
        for path in self.knowledge.rglob("*.md"):
            if path.name == "README.md":
                continue
            text = re.sub(r'(?m)^dgf_version: .*$', f'dgf_version: "{version}"', path.read_text(encoding="utf-8"), count=1)
            if extra and path.name == "permissions.md":
                text = text.replace("\n---\n", f"\n{extra}---\n", 1)
            path.write_text(text, encoding="utf-8")

    def test_no_declared_version_is_information_only(self):
        _code, out, _ = self.run_doctor()
        self.assertIn("no declared DGF version yet", out)
        self.assertFalse({"DGF_LINE_MISMATCH", "DGF_VERSION_UNKNOWN"} & set(every_id(out)), out)

    def test_unknown_warns(self):
        (self.project / ".dgf-factory" / "config.yaml").write_text("dgf:\n  version: unknown\n", encoding="utf-8")
        _code, out, _ = self.run_doctor()
        self.assertIn("DGF_VERSION_UNKNOWN", gate_entries(out, "warnings"), out)

    def test_another_line_warns_with_the_setup_command(self):
        self.declare("9.9.0")
        _code, out, _ = self.run_doctor()
        self.assertIn("DGF_LINE_MISMATCH", gate_entries(out, "warnings"), out)
        self.assertIn("run `dgf-factory setup --dgf-version 9.9.0`", out)

    def test_an_older_patch_than_the_pack_warns(self):
        self.restamp(f"{self.line}.5")
        self.declare(f"{self.line}.1")
        _code, out, _ = self.run_doctor()
        self.assertIn("DGF_VERSION_BEHIND_PACK", gate_entries(out, "warnings"), out)
        self.assertIn(f'get_release_notes("since:{self.line}.1")', out)

    def test_a_receipt_without_a_line_warns(self):
        file = self.project / ".dgf-factory" / "install.json"
        receipt = json.loads(file.read_text(encoding="utf-8"))
        del receipt["dgfLine"]
        file.write_text(json.dumps(receipt), encoding="utf-8")
        _code, out, _ = self.run_doctor()
        self.assertIn("DGF_LINE_UNRECORDED", gate_entries(out, "warnings"), out)

    def test_below_since_blocks_and_above_until_warns(self):
        self.restamp(f"{self.line}.5", f'applies:\n  since: "{self.line}.9"\n  until: "{self.line}.7"\n')
        self.declare(f"{self.line}.8")
        code, out, _ = self.run_doctor()
        self.assertEqual(code, 1, out)
        self.assertIn("VERSION_BELOW_SINCE", gate_entries(out, "blockers"), out)
        self.assertIn("VERSION_ABOVE_UNTIL", gate_entries(out, "warnings"), out)

    def test_a_restriction_may_opt_out_to_a_warning(self):
        self.restamp(f"{self.line}.5", f'applies:\n  since: "{self.line}.9"\n  until: null\nout_of_range: warn\n')
        self.declare(f"{self.line}.5")
        _code, out, _ = self.run_doctor()
        self.assertNotIn("VERSION_BELOW_SINCE", gate_entries(out, "blockers"), out)
        self.assertIn("VERSION_BELOW_SINCE", gate_entries(out, "warnings"), out)


class DoctorPacks(unittest.TestCase):
    """Package mode: the pack registry, and every pack's machine-read tables (ADR 0036 §2)."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.root = Path(self.tmp) / "dgf-factory"
        shutil.copytree(helpers.PLUGIN_ROOT, self.root,
                        ignore=shutil.ignore_patterns(".venv", "__pycache__", ".claude", ".claude-plugin", "tests",
                                                      "node_modules", "obj"))
        self.registry = self.root / "packs" / "lines.json"
        self.data = json.loads(self.registry.read_text(encoding="utf-8"))

    def add_pack(self, line="0.9"):
        shutil.copytree(self.root / "knowledge", self.root / "packs" / line, ignore=shutil.ignore_patterns("README.md"))
        self.data["lines"].append({"line": line, "dir": f"packs/{line}", "dgf_version": f"{line}.1",
                                   "read_date": "2026-11-04"})
        self.registry.write_text(json.dumps(self.data), encoding="utf-8")

    def run_doctor(self):
        return helpers.run_cli(self.root / DOCTOR, self.root)

    def test_a_second_pack_is_checked_table_by_table(self):
        self.add_pack()
        facts = self.root / "packs" / "0.9" / "json-reader.md"
        facts.write_text(facts.read_text(encoding="utf-8").replace("<!-- machine-read: component-classes -->",
                                                                   "<!-- machine-read: component-classes -->\nbroken"),
                         encoding="utf-8")
        code, out, _ = self.run_doctor()
        self.assertEqual(code, 1, out)
        self.assertIn("KNOWLEDGE_TABLE", gate_entries(out, "blockers"), out)
        self.assertIn(f"packs{os.sep}0.9{os.sep}json-reader.md", out)

    def test_a_registered_pack_that_is_missing_blocks(self):
        self.data["lines"].append({"line": "0.8", "dir": "packs/0.8", "dgf_version": "0.8.1", "read_date": "2026-11-04"})
        self.registry.write_text(json.dumps(self.data), encoding="utf-8")
        code, out, _ = self.run_doctor()
        self.assertEqual(code, 1, out)
        self.assertIn("PACK_MISSING", gate_entries(out, "blockers"), out)

    def test_a_malformed_registry_blocks(self):
        self.data["current"] = "7.7"
        self.registry.write_text(json.dumps(self.data), encoding="utf-8")
        code, out, _ = self.run_doctor()
        self.assertEqual(code, 1, out)
        self.assertIn("PACK_REGISTRY", gate_entries(out, "blockers"), out)


if __name__ == "__main__":
    unittest.main()
