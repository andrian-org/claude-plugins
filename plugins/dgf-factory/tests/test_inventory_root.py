"""inventory_root.py: workspaces, counts, and what is not a workspace (ADR 0017 §4)."""

import shutil
import tempfile
import unittest
from pathlib import Path

from tests import helpers

ROOT = {
    "webasm/FM/_PROCESS/Base/process.xml": "<process/>",
    "webasm/FM/js/formhelper.js": "// base helper",
    "zims/FM/_PROCESS/Apply/process.xml": "<process/>",
    "zims/FM/_PROCESS/Apply/Local/_workflow.xml": "<workflow/>",
    "zims/FM/_WORKFLOW/Submit/_workflow.xml": "<workflow/>",
    "zims/FM/_WORKFLOW/Loud/_workflow.XML": "<workflow/>",  # a Linux runtime never opens it
    "zims/FM/_COMPONENTS/DataSource/Fee.json": "{}",
    "zims/FM/_COMPONENTS/Page/SiteMap/login.json": "{}",
    "zims/FM/_COMPONENTS/sitemap.json": "{}",
    "zims/FM/_DATA/Case/settings.xml": "<settings/>",
    "zims/FM/_DATA/Case/_options.xml": "<options/>",
    "zims/FM/_DATA/Case/_forms/Apply/_form.xml": "<form/>",
    "zims/FM/_DATA/Case/_forms/Apply/_form.js": "// form script",
    "zims/FM/_DATA/Case/_forms/Deep/Name/_form.xml": "<form/>",
    "zims/FM/_DATA/Case/_views/All/_view.xml": "<view/>",
    "zims/FM/_DATA/Case/_lookupviews/Pick/_view.xml": "<view/>",
    "zims/FM/_DATA/Case/_gridforms/Rows/_grid.xml": "<grid/>",
    "zims/js/formhelper.js": "// helper",
    "zims/js/forms.shared.js": "// shared",
    "zims/css/custom.css": "body {}",
    "applibs-zims/Zims.Plugin.dll": b"MZ",
    "docs/readme.md": "not a workspace",
    "lower/fm/x.xml": "<x/>",
}


class Inventory(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.root = helpers.make_root(self.tmp / "root", ROOT)

    def inventory(self, root=None, blocking=False):
        run = helpers.run_cli_blocking if blocking else helpers.run_cli
        return run("inventory_root.py", "--workspaces-root", root or self.root)

    def line(self, out, prefix):
        return next(line for line in out.splitlines() if line.startswith(prefix))

    def test_counts(self):
        code, out, _ = self.inventory()
        self.assertIn(code, (0, 2))
        self.assertEqual(self.line(out, "WORKSPACE: zims"),
                         "WORKSPACE: zims role=application processes=1 workflows=2 components=3 forms=2 settings=1 "
                         "views=3 options=1 form_scripts=1 global_scripts=2 global_styles=1")
        self.assertIn("role=base processes=1", self.line(out, "WORKSPACE: webasm"))
        self.assertIn("global_scripts=1", self.line(out, "WORKSPACE: webasm"))

    def test_what_is_not_a_workspace(self):
        _, out, _ = self.inventory()
        self.assertEqual(self.line(out, "NOT A WORKSPACE: applibs-zims"),
                         "NOT A WORKSPACE: applibs-zims (plugin assemblies — 1 .dll file(s), no FM/)")
        self.assertIn("no FM/", self.line(out, "NOT A WORKSPACE: docs"))
        self.assertIn("only when case is ignored", self.line(out, "NOT A WORKSPACE: lower"))

    def test_the_knowledge_stamp(self):
        _, out, _ = self.inventory()
        self.assertRegex(self.line(out, "KNOWLEDGE: "), r"^KNOWLEDGE: dgf_version=\d+\.\d+\.\d+$")

    def test_no_git(self):
        _, out, _ = self.inventory()
        self.assertTrue(self.line(out, "GIT: ").startswith("GIT: none"))

    @unittest.skipUnless(helpers.have_git(), "git is not installed")
    def test_git_position(self):
        repo = helpers.make_repo(self.tmp / "estate")
        root = helpers.make_root(repo / "Web" / "workspaces", ROOT)
        helpers.commit_all(repo, "estate")
        _, out, _ = self.inventory(root)
        self.assertEqual(self.line(out, "GIT: "), f"GIT: toplevel={repo} branch=main root=Web/workspaces")

    def test_no_base_workspace(self):
        shutil.rmtree(self.root / "webasm")
        code, out, _ = self.inventory()
        self.assertIn("WARN BASE_WORKSPACE_ABSENT", out)
        self.assertIn(code, (2,))

    def test_not_a_workspaces_root(self):
        bare = helpers.make_root(self.tmp / "bare", {"docs/readme.md": "x", "applibs/A.dll": b"MZ"})
        code, out, _ = self.inventory(bare)
        self.assertEqual(code, 3)
        self.assertIn("ERROR ROOT_NO_WORKSPACE", out)

    def test_it_never_imports_the_validator_dependencies(self):
        code, out, err = self.inventory(blocking=True)
        self.assertEqual(code, 2, err)
        self.assertIn("VALIDATORS: missing: lxml, jsonschema", out)
        self.assertIn("WARN VALIDATOR_DEPS_MISSING", out)
        self.assertIn("--require-hashes", out)

    @unittest.skipUnless(helpers.have_dependencies(), "lxml / jsonschema not installed")
    def test_dependencies_present(self):
        code, out, _ = self.inventory()
        self.assertEqual(code, 0, out)
        self.assertIn("VALIDATORS: dependencies present", out)


if __name__ == "__main__":
    unittest.main()
