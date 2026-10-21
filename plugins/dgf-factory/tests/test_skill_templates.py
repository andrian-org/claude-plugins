"""The skills' templates are output shapes, and each validates where a skill would place it (plan D14)."""

import re
import shutil
import tempfile
import unittest
from pathlib import Path

from tests import helpers

TEMPLATES = {
    "skills/dgf-process/templates/process.xml": "app/FM/_PROCESS/Example/process.xml",
    "skills/dgf-process/templates/_workflow.xml": "app/FM/_WORKFLOW/Example/_workflow.xml",
    "skills/dgf-model/templates/settings.xml": "app/FM/_DATA/Example/settings.xml",
}
FINDING = re.compile(r"^(?:ERROR|WARN|INFO) ([A-Z_]+) ", re.MULTILINE)


@unittest.skipUnless(helpers.have_dependencies(), "lxml / jsonschema not installed")
class Templates(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.root = helpers.make_root(self.tmp, {"webasm/FM/.keep": ""})
        for template, target in TEMPLATES.items():
            (self.root / target).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(helpers.PLUGIN_ROOT / template, self.root / target)

    def run_on(self, script, *args):
        code, out, err = helpers.run_cli(script, *args)
        return code, FINDING.findall(out), out + err

    def test_the_process_and_workflow_templates_are_clean(self):
        code, codes, out = self.run_on("validate_process.py", "--workspaces-root", self.root, "--all")
        self.assertEqual((code, codes), (0, []), out)
        code, codes, out = self.run_on("validate_config.py", self.root / TEMPLATES[
            "skills/dgf-process/templates/_workflow.xml"])
        self.assertEqual((code, codes), (0, []), out)

    def test_the_settings_template_is_clean_or_warns_only_that_its_grammar_lags(self):
        settings = self.root / TEMPLATES["skills/dgf-model/templates/settings.xml"]
        code, codes, out = self.run_on("validate_config.py", settings)
        self.assertIn(code, (0, 2), out)
        self.assertEqual(set(codes) - {"XSD_LAGS_RUNTIME"}, set(), out)
        code, codes, out = self.run_on("validate_model.py", "--workspaces-root", self.root, settings)
        self.assertEqual((code, codes), (0, []), out)

    def test_every_template_names_the_placeholder_a_skill_replaces(self):
        for template in TEMPLATES:
            self.assertIn('"Example"', (helpers.PLUGIN_ROOT / template).read_text(encoding="utf-8"), template)


if __name__ == "__main__":
    unittest.main()
