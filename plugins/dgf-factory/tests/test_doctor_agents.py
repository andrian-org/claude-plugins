"""The doctor over the installed agents: checked by receipt like a skill, scanned as shipped (ADR 0033 §5)."""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests import helpers
from tests.test_doctor import DOCTOR, gate, gate_entries

AGENTS = ("dgf-implement-coordinator.md", "dgf-implement-worker.md")


class TheAgentsShip(unittest.TestCase):
    def test_agents_is_a_shipped_directory(self):
        from tests.test_doctor import load_doctor
        self.assertIn("agents", load_doctor(helpers.PLUGIN_ROOT).SHIPPED_DIRS)

    def test_a_dgf_path_in_an_agent_blocks_on_a_copy_of_the_package(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        root = tmp / "dgf-factory"
        shutil.copytree(helpers.PLUGIN_ROOT, root, ignore=shutil.ignore_patterns(
            ".venv", "__pycache__", ".claude", ".claude-plugin", "tests", "node_modules", "obj"))
        agent = root / "agents" / "claude" / AGENTS[1]
        agent.write_text(agent.read_text(encoding="utf-8") + "\nsee src/" + "Core/DGF.Kernel/x.cs\n", encoding="utf-8")
        code, out, _ = helpers.run_cli(root / DOCTOR, root)
        self.assertEqual(code, 1, out)
        self.assertIn("DGF_PATH", gate_entries(out, "blockers"))


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class AgentsInAProject(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.project = Path(self.tmp) / "project"
        self.project.mkdir()
        done = subprocess.run(["node", str(helpers.PLUGIN_ROOT / "bin" / "dgf-factory.mjs"), "setup", "--root",
                               str(self.project), "--harness", "claude", "--yes", "--no-python"],
                              capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.agents = self.project / ".claude" / "agents"
        self.doctor = self.project / ".dgf-factory" / "runtime" / DOCTOR

    def run_doctor(self):
        return helpers.run_cli(self.doctor, env={"PATH": "/usr/bin:/bin"})

    def test_the_installed_agents_are_clean(self):
        self.assertEqual(sorted(p.name for p in self.agents.iterdir()), list(AGENTS))
        code, out, _ = self.run_doctor()
        self.assertEqual(gate_entries(out, "blockers"), [], out)
        self.assertIn(code, (0, 2), out)
        self.assertNotIn("INSTALL_FILE_EDITED", gate_entries(out, "warnings"), out)

    def test_an_edited_agent_warns_like_a_skill(self):
        agent = self.agents / AGENTS[0]
        agent.write_text(agent.read_text(encoding="utf-8") + "\nmine\n", encoding="utf-8")
        code, out, _ = self.run_doctor()
        self.assertIn("INSTALL_FILE_EDITED", gate_entries(out, "warnings"), out)
        self.assertTrue(any(e["file"] == f".claude/agents/{AGENTS[0]}" for e in gate(out)["warnings"]), out)
        self.assertEqual(gate_entries(out, "blockers"), [], out)

    def test_a_missing_agent_blocks_like_a_skill(self):
        (self.agents / AGENTS[1]).unlink()
        code, out, _ = self.run_doctor()
        self.assertEqual(code, 1, out)
        self.assertIn("INSTALL_FILE_MISSING", gate_entries(out, "blockers"))
        self.assertTrue(any(e["file"] == f".claude/agents/{AGENTS[1]}" for e in gate(out)["blockers"]), out)

    def test_a_dangling_runtime_path_in_an_installed_agent_blocks(self):
        agent = self.agents / AGENTS[0]
        agent.write_text(agent.read_text(encoding="utf-8") + '\npython3 ".dgf-factory/runtime/scripts/gone.py"\n',
                         encoding="utf-8")
        code, out, _ = self.run_doctor()
        self.assertEqual(code, 1, out)
        self.assertIn("RUNTIME_PATH_DANGLING", gate_entries(out, "blockers"))


if __name__ == "__main__":
    unittest.main()
