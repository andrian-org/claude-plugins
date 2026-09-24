"""The workspaces-root model and exact-case lookup in scripts/lib/workspace.py."""

import shutil
import tempfile
import unittest
from pathlib import Path

from tests import helpers
from lib import workspace


class Model(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.root = helpers.make_root(self.tmp, {
            "app/FM/_COMPONENTS/Page/home.json": "{}",
            "other/FM/_WORKFLOW/W/_workflow.xml": "<Workflow />",
            "webasm/FM/_COMPONENTS/Page/base.json": "{}",
            "notes/readme.txt": "not a workspace",
        })

    def test_owning_workspace_is_the_directory_above_fm(self):
        path = self.root / "app/FM/_COMPONENTS/Page/home.json"
        self.assertEqual(workspace.owning_workspace(path), self.root / "app")
        self.assertIsNone(workspace.owning_workspace(self.root / "notes/readme.txt"))

    def test_root_is_the_owners_parent_unless_overridden(self):
        path = self.root / "app/FM/_COMPONENTS/Page/home.json"
        self.assertEqual(workspace.workspaces_root(path), self.root)
        self.assertEqual(workspace.workspaces_root(path, "/elsewhere"), Path("/elsewhere"))

    def test_applications_exclude_webasm_and_non_workspaces(self):
        self.assertEqual(workspace.applications(self.root), ["app", "other"])

    def test_exact_child(self):
        components = self.root / "app/FM/_COMPONENTS"
        self.assertEqual(workspace.exact_child(components, "Page"), (workspace.OK, "Page"))
        self.assertEqual(workspace.exact_child(components, "page"), (workspace.CASE_ONLY, "Page"))
        self.assertEqual(workspace.exact_child(components, "Form"), (workspace.MISSING, None))

    def test_exact_file(self):
        base = self.root / "app"
        status, actual = workspace.exact_file(base, ["FM", "_COMPONENTS", "Page", "home.json"])
        self.assertEqual((status, actual), (workspace.OK, base / "FM/_COMPONENTS/Page/home.json"))
        status, actual = workspace.exact_file(base, ["FM", "_COMPONENTS", "page", "Home.json"])
        self.assertEqual((status, actual), (workspace.CASE_ONLY, base / "FM/_COMPONENTS/Page/home.json"))
        self.assertEqual(workspace.exact_file(base, ["FM", "_COMPONENTS", "page", "none.json"])[0], workspace.MISSING)
        self.assertEqual(workspace.exact_file(base, ["FM", "_COMPONENTS", "Page"])[0], workspace.MISSING)


if __name__ == "__main__":
    unittest.main()
