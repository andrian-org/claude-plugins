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


def sample_root(tmp):
    """Two applications, `a` and `b`, and webasm, holding one of every DD10 target."""
    return helpers.make_root(tmp, {
        "a/FM/_WORKFLOW/Shared/_workflow.xml": "<Workflow />",
        "b/FM/_WORKFLOW/Shared/_workflow.xml": "<Workflow />",
        "a/FM/_WORKFLOW/OnlyA/_workflow.xml": "<Workflow />",
        "a/FM/_WORKFLOW/Local/_workflow.xml": "<Workflow />",
        "a/FM/_PROCESS/Case/process.xml": "<Process />",
        "a/FM/_PROCESS/Case/Local/_workflow.xml": "<Workflow />",
        "a/FM/_PROCESS/Q/process.xml": "<Process />",
        "b/FM/_PROCESS/Q/process.xml": "<Process />",
        "a/FM/_PROCESS/OnlyAQ/process.xml": "<Process />",
        "webasm/FM/_WORKFLOW/Base/_workflow.xml": "<Workflow />",
        "webasm/FM/_PROCESS/Review/process.xml": "<Process />",
        "webasm/FM/_PROCESS/Review/Step/_workflow.xml": "<Workflow />",
        "webasm/FM/_PROCESS/BQ/process.xml": "<Process />",
        "a/FM/_WORKFLOW/Mixed/_Workflow.xml": "<Workflow />",
    })


class Presentation(unittest.TestCase):
    def test_kind_and_name(self):
        self.assertEqual(workspace.presentation("WORKFLOW:X"), ("WORKFLOW", "X"))
        self.assertEqual(workspace.presentation("WORKFLOW:/X;id=1"), ("WORKFLOW", "/X"))
        self.assertEqual(workspace.presentation("FORM:F"), ("FORM", "F"))

    def test_both_base_spellings_become_base_x(self):
        self.assertEqual(workspace.presentation("WORKFLOW:BASE:X"), ("WORKFLOW", "BASE:X"))
        self.assertEqual(workspace.presentation("WORKFLOW:/BASE:X"), ("WORKFLOW", "BASE:X"))
        self.assertEqual(workspace.presentation("WORKFLOW:/BASE:P/X"), ("WORKFLOW", "BASE:P/X"))

    def test_no_kind(self):
        self.assertEqual(workspace.presentation(""), ("", ""))
        self.assertEqual(workspace.presentation("X"), ("", ""))
        self.assertEqual(workspace.presentation(":X"), ("", ""))

    def test_action_names_are_process_local_unless_base_or_slash(self):
        self.assertEqual(workspace.action_workflow_name("X", "Case"), "Case/X")
        self.assertEqual(workspace.action_workflow_name("X", "BASE:Review"), "BASE:Review/X")
        self.assertEqual(workspace.action_workflow_name("/X", "Case"), "/X")
        self.assertEqual(workspace.action_workflow_name("BASE:X", "Case"), "BASE:X")

    def test_workflow_manager_branches(self):
        self.assertEqual(workspace.workflow_location("BASE:X"), ("base", ["FM", "_WORKFLOW", "X", "_workflow.xml"]))
        self.assertEqual(workspace.workflow_location("BASE:P/X"),
                         ("base", ["FM", "_PROCESS", "P", "X", "_workflow.xml"]))
        self.assertEqual(workspace.workflow_location("/X"), ("selected", ["FM", "_WORKFLOW", "X", "_workflow.xml"]))
        self.assertEqual(workspace.workflow_location("P/X"),
                         ("selected", ["FM", "_PROCESS", "P", "X", "_workflow.xml"]))
        self.assertEqual(workspace.workflow_location("X"), ("selected", ["FM", "_WORKFLOW", "X", "_workflow.xml"]))


class Resolvers(unittest.TestCase):
    """One test per cell of the DD10 table."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.root = sample_root(self.tmp)
        self.app, self.base = self.root / "a", self.root / "webasm"

    def ref(self, value, process_ref, owner):
        return workspace.resolve_workflow_ref(value, process_ref, owner, self.root)

    def test_base_workflow_from_either_workspace(self):
        for value in ("WORKFLOW:BASE:Base", "WORKFLOW:/BASE:Base"):
            self.assertEqual(self.ref(value, "Case", self.app), workspace.Resolved("webasm/FM/_WORKFLOW/Base/_workflow.xml"))
            self.assertIsInstance(self.ref(value, "BASE:Review", self.base), workspace.Resolved)

    def test_slash_workflow_from_an_application(self):
        self.assertEqual(self.ref("WORKFLOW:/OnlyA", "Case", self.app),
                         workspace.Resolved("a/FM/_WORKFLOW/OnlyA/_workflow.xml"))
        self.assertIsInstance(self.ref("WORKFLOW:/Base", "Case", self.app), workspace.Unresolved)

    def test_slash_workflow_from_webasm_all_some_and_no_apps(self):
        self.assertIsInstance(self.ref("WORKFLOW:/Shared", "BASE:Review", self.base), workspace.Resolved)
        some = self.ref("WORKFLOW:/OnlyA", "BASE:Review", self.base)
        self.assertEqual((some.resolved_in, some.missing_in), (["a"], ["b"]))
        none = self.ref("WORKFLOW:/Nowhere", "BASE:Review", self.base)
        self.assertEqual((none.resolved_in, none.missing_in), ([], ["a", "b"]))

    def test_bare_workflow_is_process_local(self):
        self.assertEqual(self.ref("WORKFLOW:Local", "Case", self.app),
                         workspace.Resolved("a/FM/_PROCESS/Case/Local/_workflow.xml"))
        self.assertEqual(self.ref("WORKFLOW:Step", "BASE:Review", self.base),
                         workspace.Resolved("webasm/FM/_PROCESS/Review/Step/_workflow.xml"))
        self.assertIsInstance(self.ref("WORKFLOW:Step", "Case", self.app), workspace.Unresolved)

    def test_non_workflow_actions_are_not_references(self):
        self.assertIsNone(self.ref("FORM:Edit", "Case", self.app))
        self.assertIsNone(self.ref("workflow:Local", "Case", self.app))
        self.assertIsNone(self.ref("", "Case", self.app))

    def test_validation_flow_bare_and_base(self):
        self.assertEqual(workspace.resolve_validation_flow("Local", self.app, self.root),
                         workspace.Resolved("a/FM/_WORKFLOW/Local/_workflow.xml"))
        self.assertEqual(workspace.resolve_validation_flow("BASE:Base", self.app, self.root),
                         workspace.Resolved("webasm/FM/_WORKFLOW/Base/_workflow.xml"))
        from_base = workspace.resolve_validation_flow("OnlyA", self.base, self.root)
        self.assertEqual((from_base.resolved_in, from_base.missing_in), (["a"], ["b"]))

    def test_change_state_process(self):
        self.assertEqual(workspace.resolve_process("BASE:BQ", self.app, self.root),
                         workspace.Resolved("webasm/FM/_PROCESS/BQ/process.xml"))
        self.assertEqual(workspace.resolve_process("OnlyAQ", self.app, self.root),
                         workspace.Resolved("a/FM/_PROCESS/OnlyAQ/process.xml"))
        self.assertIsInstance(workspace.resolve_process("Q", self.base, self.root), workspace.Resolved)
        partial = workspace.resolve_process("OnlyAQ", self.base, self.root)
        self.assertEqual((partial.resolved_in, partial.missing_in), (["a"], ["b"]))

    def test_base_prefix_is_case_sensitive_for_processes(self):
        self.assertIsInstance(workspace.resolve_process("base:BQ", self.app, self.root), workspace.Unresolved)

    def test_case_only_directory_match(self):
        result = self.ref("WORKFLOW:/mixed", "Case", self.app)
        self.assertEqual(result, workspace.CaseOnly("a/FM/_WORKFLOW/mixed/_workflow.xml",
                                                    "a/FM/_WORKFLOW/Mixed/_Workflow.xml"))

    def test_a_webasm_reference_found_everywhere_keeps_every_application(self):
        result = self.ref("WORKFLOW:/Shared", "BASE:Review", self.base)
        self.assertEqual(result, workspace.Resolved("<app>/FM/_WORKFLOW/Shared/_workflow.xml", ("a", "b")))

    def test_rooted_names_never_resolve(self):
        # Path.Combine discards everything before a rooted segment, as the engine's .NET does.
        for result in (workspace.resolve_process("/Case", self.app, self.root),
                       workspace.resolve_process("BASE:/BQ", self.app, self.root),
                       self.ref("WORKFLOW:BASE:/Base", "Case", self.app),
                       self.ref("WORKFLOW://OnlyA", "Case", self.app),
                       workspace.resolve_component_file("/home", "Page", self.app, self.root),
                       workspace.resolve_component_file("base:/home", "Page", self.app, self.root)):
            self.assertIsInstance(result, workspace.Unresolved)
            self.assertEqual(result.reason, workspace.ROOTED_REASON)

    def test_an_empty_workflow_name_is_unresolved(self):
        result = self.ref("WORKFLOW:", "Case", self.app)
        self.assertIsInstance(result, workspace.Unresolved)
        self.assertIn("empty workflow name", result.reason)

    def test_a_relative_root_override_is_made_absolute(self):
        self.assertTrue(workspace.workspaces_root("/x/app/FM/p.xml", "ws").is_absolute())

    def test_component_file_base_prefix_in_any_case(self):
        self.assertEqual(workspace.component_location("base:x", "Page"),
                         ("base", ["FM", "_COMPONENTS", "Page", "x.json"]))



class OneApplication(unittest.TestCase):
    """`app` fixes the selected workspace of a webasm reference (ADR 0023 §4)."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.root = sample_root(self.tmp)
        self.app, self.base = self.root / "a", self.root / "webasm"

    def test_a_webasm_reference_resolves_in_that_application_alone(self):
        ref = workspace.resolve_workflow_ref
        self.assertEqual(ref("WORKFLOW:/OnlyA", "BASE:Review", self.base, self.root, app="a"),
                         workspace.Resolved("a/FM/_WORKFLOW/OnlyA/_workflow.xml"))
        self.assertEqual(ref("WORKFLOW:/OnlyA", "BASE:Review", self.base, self.root, app="b"),
                         workspace.Unresolved("b/FM/_WORKFLOW/OnlyA/_workflow.xml"))

    def test_with_app_it_is_never_app_dependent(self):
        for app in ("a", "b"):
            for result in (workspace.resolve_workflow_name("/OnlyA", self.base, self.root, app=app),
                           workspace.resolve_process("OnlyAQ", self.base, self.root, app=app),
                           workspace.resolve_validation_flow("OnlyA", self.base, self.root, app=app),
                           workspace.resolve_component_file("nowhere", "Page", self.base, self.root, app=app)):
                self.assertNotIsInstance(result, workspace.AppDependent)

    def test_a_case_only_match_in_that_application(self):
        result = workspace.resolve_workflow_name("/Mixed", self.base, self.root, app="a")
        self.assertEqual(result, workspace.CaseOnly("a/FM/_WORKFLOW/Mixed/_workflow.xml",
                                                    "a/FM/_WORKFLOW/Mixed/_Workflow.xml"))

    def test_base_references_ignore_app(self):
        self.assertEqual(workspace.resolve_workflow_name("BASE:Base", self.base, self.root, app="b"),
                         workspace.resolve_workflow_name("BASE:Base", self.base, self.root))

    def test_an_applications_own_reference_ignores_app(self):
        self.assertEqual(workspace.resolve_workflow_name("/OnlyA", self.app, self.root, app="b"),
                         workspace.Resolved("a/FM/_WORKFLOW/OnlyA/_workflow.xml"))


if __name__ == "__main__":
    unittest.main()
