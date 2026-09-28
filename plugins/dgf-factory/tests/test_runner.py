"""scripts/lib/runner.py: the validators the gate and the known-good run share (ADR 0018 §2, ADR 0023 §3)."""

import shutil
import tempfile
import unittest
from pathlib import Path

from tests import helpers
from lib import runner

ENTITY = '<entity><primarykey>Id</primarykey><fields><field name="Id" type="PrimaryKey"/></fields></entity>\n'
FILES = {
    "webasm/FM/.keep": "",
    "a/FM/_DATA/Cases/settings.xml": ENTITY,
    "a/FM/_DATA/Cases/_forms/edit/_form.xml": "<form><tabs/></form>\n",
    "a/FM/_DATA/Cases/_views/all/_view.xml": "<view/>\n",
    "a/FM/_DATA/Cases/_lookupviews/default/_view.xml": "<view/>\n",
    "a/FM/_COMPONENTS/Page/home.json": '{"type": "Page"}\n',
    "a/FM/_WORKFLOW/W/_workflow.xml": "<Workflow><Sequence/></Workflow>\n",
}


class Validators(unittest.TestCase):
    def test_the_gate_runs_four_validators(self):
        self.assertEqual(runner.VALIDATORS, ("validate_process.py", "validate_config.py", "resolve_components.py",
                                             "validate_model.py"))


@unittest.skipUnless(helpers.have_dependencies(), "lxml / jsonschema not installed")
class Routing(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.root = helpers.make_root(self.tmp, FILES)

    def routed(self, runs):
        """{root-relative file: [validators that read it]}."""
        found = {}
        for name, reports in runs.items():
            for rep in reports:
                rel = Path(rep.file).resolve().relative_to(self.root.resolve()).as_posix()
                found.setdefault(rel, []).append(name)
        return {rel: sorted(names) for rel, names in found.items()}

    def test_validate_model_receives_only_settings_and_form_files(self):
        runs, _ = runner.run(self.root)
        model = sorted(Path(rep.file).name for rep in runs["validate_model.py"])
        self.assertEqual(model, ["_form.xml", "settings.xml"])

    def test_a_whole_root_run_and_a_files_run_route_a_file_alike(self):
        whole = self.routed(runner.run(self.root)[0])
        for rel in FILES:
            if rel.endswith(".keep"):
                continue
            with self.subTest(file=rel):
                narrowed = self.routed(runner.run(self.root, files=[rel])[0])
                self.assertEqual(narrowed, {rel: whole[rel]})


if __name__ == "__main__":
    unittest.main()
