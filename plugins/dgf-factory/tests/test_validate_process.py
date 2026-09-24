"""scripts/validate_process.py end to end, on synthetic workspaces roots (ADR 0014 §2–3)."""

import shutil
import tempfile
import unittest

from tests import helpers

APP = "ws/a/FM/"
OTHER = "ws/b/FM/"
BASE = "ws/webasm/FM/"
PROCESS = "_PROCESS/Case/process.xml"
CHECKS = "CHECKS RUN: xsd-structure, dead-transition, unreachable-state, workflow-reference, validation-flow"


def process_xml(states, start=None, start_action="", validation_flow=None):
    """A process.xsd-valid process. `states` is {name: {"to": [...], "action": str, "timeout": target}}."""
    start = list(states)[:1] if start is None else start
    flow = f' validationFlow="{validation_flow}"' if validation_flow is not None else ""
    lines = ['<?xml version="1.0" encoding="utf-8"?>',
             f'<Process title="Case" table="Cases" keyName="id" allowBack="false" allowHistory="true" '
             f'assignTasks="false"{flow}>',
             f'  <OnStart action="{start_action}">', "    <Transitions>"]
    lines += [f'      <Transition state="{target}" />' for target in start]
    lines += ["    </Transitions>", "  </OnStart>", "  <States>"]
    for name, spec in states.items():
        action = f' action="{spec["action"]}"' if "action" in spec else ""
        lines += [f'    <State name="{name}" type="Task"{action}>', "      <Transitions>"]
        lines += [f'        <Transition state="{target}" />' for target in spec.get("to", ["End"])]
        lines += ["      </Transitions>"]
        if "timeout" in spec:
            lines += [f'      <OnTimeout interval="1.00:00:00" state="{spec["timeout"]}" />']
        lines += ["    </State>"]
    lines += ["  </States>", "</Process>", ""]
    return "\n".join(lines)


def workflow_xml(*steps):
    """A workflow of StateProcess steps, each a dict of its attributes."""
    body = []
    for step in steps:
        attributes = {"title": "s", "name": "s", "mode": "CHANGE_STATE", "table": "Cases", "state": "",
                      "applyforstates": "", **step}
        body.append("    <StateProcess " + " ".join(f'{k}="{v}"' for k, v in attributes.items()) + " />")
    return "\n".join(['<?xml version="1.0" encoding="utf-8"?>', '<Workflow name="W">', "  <Sequence>", *body,
                      "  </Sequence>", "</Workflow>", ""])


EMPTY_WORKFLOW = workflow_xml()


@unittest.skipUnless(helpers.have_dependencies(), "lxml / jsonschema not installed")
class ValidateProcess(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)

    def run_on(self, files, target=None, *extra):
        """Write `files` into a fresh root and run on `target` (default: the first file)."""
        root = helpers.make_root(tempfile.mkdtemp(dir=self.tmp), files)
        return helpers.run_cli("validate_process.py", root / (target or next(iter(files))), *extra)

    def assert_result(self, result, code, finding):
        exit_code, out, err = result
        self.assertEqual(exit_code, code, out + err)
        self.assertIn(f" {finding} ", out + err, out + err)

    # --- dead transition ---------------------------------------------------------

    def test_a_transition_to_end_passes(self):
        code, out, _ = self.run_on({APP + PROCESS: process_xml({"A": {"to": ["End"]}})})
        self.assertEqual(code, 0, out)
        self.assertIn(CHECKS, out)

    def test_lowercase_end_is_a_dead_transition(self):
        self.assert_result(self.run_on({APP + PROCESS: process_xml({"A": {"to": ["end"]}})}), 1, "DEAD_TRANSITION")

    def test_a_timeout_to_an_undeclared_state_is_dead(self):
        result = self.run_on({APP + PROCESS: process_xml({"A": {"timeout": "Gone"}})})
        self.assert_result(result, 1, "DEAD_TRANSITION")
        self.assertIn(" XSD_RUNTIME_DIVERGENCE ", result[1])

    # --- unreachable state ------------------------------------------------------------

    def test_an_unreached_state_warns(self):
        result = self.run_on({APP + PROCESS: process_xml({"A": {}, "B": {}})})
        self.assert_result(result, 2, "UNREACHABLE_STATE")
        self.assertIn("state `B`", result[1])

    def test_a_timeout_edge_makes_a_state_reachable(self):
        code, out, _ = self.run_on({APP + PROCESS: process_xml({"A": {"timeout": "B"}, "B": {}})})
        self.assertNotIn("UNREACHABLE_STATE", out)
        self.assertEqual(code, 2, out)  # OnTimeout under a State is a runtime divergence

    def test_a_change_state_target_makes_a_state_reachable(self):
        code, out, _ = self.run_on({APP + PROCESS: process_xml({"A": {}, "B": {}}),
                                    APP + "_WORKFLOW/Move/_workflow.xml": workflow_xml({"process": "Case",
                                                                                        "state": "B"})})
        self.assertEqual(code, 0, out)

    def test_a_start_state_makes_a_state_reachable(self):
        code, out, _ = self.run_on({APP + PROCESS: process_xml({"A": {}, "B": {}}),
                                    APP + "_WORKFLOW/Open/_workflow.xml": workflow_xml({"mode": "START",
                                                                                        "process": "Case",
                                                                                        "state": "B"})})
        self.assertEqual(code, 0, out)

    def test_applyforstates_are_not_entries(self):
        result = self.run_on({APP + PROCESS: process_xml({"A": {}, "B": {}}),
                              APP + "_WORKFLOW/Move/_workflow.xml": workflow_xml({"process": "Case", "state": "A",
                                                                                  "applyforstates": "B"})})
        self.assert_result(result, 2, "UNREACHABLE_STATE")

    # --- change-state targets ---------------------------------------------------------

    def test_an_applyforstates_token_with_a_leading_space_is_undeclared(self):
        files = {APP + "_WORKFLOW/Move/_workflow.xml": workflow_xml({"process": "Case", "state": "A",
                                                                     "applyforstates": "A; B"}),
                 APP + PROCESS: process_xml({"A": {}, "B": {}})}
        result = self.run_on(files)
        self.assert_result(result, 1, "CHANGE_STATE_STATE_UNDECLARED")
        self.assertIn("' B'", result[1])
        self.assertEqual(result[1].count("CHANGE_STATE_STATE_UNDECLARED"), 1, result[1])

    def test_a_move_to_an_undeclared_state_blocks(self):
        files = {APP + "_WORKFLOW/Move/_workflow.xml": workflow_xml({"process": "Case", "state": "Gone"}),
                 APP + PROCESS: process_xml({"A": {}})}
        self.assert_result(self.run_on(files), 1, "CHANGE_STATE_STATE_UNDECLARED")

    def test_a_move_to_end_passes(self):
        files = {APP + "_WORKFLOW/Move/_workflow.xml": workflow_xml({"process": "Case", "state": "End"}),
                 APP + PROCESS: process_xml({"A": {}})}
        code, out, _ = self.run_on(files)
        self.assertEqual(code, 0, out)
        self.assertIn("CHECKS RUN: change-state-target", out)

    def test_an_unresolved_process_blocks(self):
        result = self.run_on({APP + "_WORKFLOW/Move/_workflow.xml": workflow_xml({"process": "Nope", "state": "A"})})
        self.assert_result(result, 1, "CHANGE_STATE_PROCESS_UNRESOLVED")

    def test_mode_is_compared_exactly(self):
        files = {APP + "_WORKFLOW/Move/_workflow.xml": workflow_xml({"mode": "change_state", "process": "Nope",
                                                                     "state": "Gone"})}
        code, out, _ = self.run_on(files)
        self.assertEqual(code, 0, out)

    def test_a_lowercase_mode_does_not_make_a_state_reachable(self):
        files = {APP + PROCESS: process_xml({"A": {}, "B": {}}),
                 APP + "_WORKFLOW/Move/_workflow.xml": workflow_xml({"mode": "change_state", "process": "Case",
                                                                     "state": "B"})}
        self.assert_result(self.run_on(files), 2, "UNREACHABLE_STATE")

    def test_a_webasm_workflow_moves_every_applications_process(self):
        files = {BASE + "_WORKFLOW/Move/_workflow.xml": workflow_xml({"process": "Case", "state": "A"}),
                 APP + PROCESS: process_xml({"A": {}}),
                 OTHER + "_WORKFLOW/Other/_workflow.xml": EMPTY_WORKFLOW}
        result = self.run_on(files)
        self.assert_result(result, 2, "WORKFLOW_APP_DEPENDENT")
        self.assertIn("present in a, absent from b", result[1])

    # --- structure ----------------------------------------------------------------------

    def test_invalid_structure_skips_the_semantic_checks(self):
        broken = process_xml({"A": {}}).replace("<States>", "<States>\n    <Bogus />")
        exit_code, out, err = self.run_on({APP + PROCESS: broken})
        self.assertEqual(exit_code, 1, out + err)
        self.assertIn(" XSD_INVALID ", out)
        for check in ("dead-transition", "unreachable-state", "workflow-reference", "validation-flow"):
            self.assertIn(f"NOT RUN: {check} (structure invalid)", out)

    # --- workflow references --------------------------------------------------------------

    def test_a_webasm_slash_workflow_in_one_of_two_apps_is_app_dependent(self):
        files = {BASE + PROCESS: process_xml({"A": {"action": "WORKFLOW:/W"}}),
                 APP + "_WORKFLOW/W/_workflow.xml": EMPTY_WORKFLOW,
                 OTHER + "_WORKFLOW/Other/_workflow.xml": EMPTY_WORKFLOW}
        result = self.run_on(files)
        self.assert_result(result, 2, "WORKFLOW_APP_DEPENDENT")
        self.assertIn("present in a, absent from b", result[1])

    def test_a_webasm_slash_workflow_found_only_in_webasm_hints_at_base(self):
        files = {BASE + PROCESS: process_xml({"A": {"action": "WORKFLOW:/W"}}),
                 BASE + "_WORKFLOW/W/_workflow.xml": EMPTY_WORKFLOW,
                 APP + "_WORKFLOW/Other/_workflow.xml": EMPTY_WORKFLOW}
        result = self.run_on(files)
        self.assert_result(result, 2, "WORKFLOW_APP_DEPENDENT")
        self.assertIn("only a `BASE:` name reaches", result[1])

    def test_a_bare_workflow_is_process_local(self):
        files = {APP + PROCESS: process_xml({"A": {"action": "WORKFLOW:Local"}}),
                 APP + "_WORKFLOW/Local/_workflow.xml": EMPTY_WORKFLOW}
        self.assert_result(self.run_on(files), 1, "WORKFLOW_UNRESOLVED")
        files[APP + "_PROCESS/Case/Local/_workflow.xml"] = EMPTY_WORKFLOW
        self.assertEqual(self.run_on(files, APP + PROCESS)[0], 0)

    def test_a_base_workflow_reads_webasm(self):
        files = {APP + PROCESS: process_xml({"A": {"action": "WORKFLOW:/BASE:W"}}),
                 BASE + "_WORKFLOW/W/_workflow.xml": EMPTY_WORKFLOW}
        self.assertEqual(self.run_on(files)[0], 0)

    def test_a_case_only_workflow_warns(self):
        files = {APP + PROCESS: process_xml({"A": {"action": "WORKFLOW:/w"}}),
                 APP + "_WORKFLOW/W/_workflow.xml": EMPTY_WORKFLOW}
        self.assert_result(self.run_on(files), 2, "CASE_ONLY_MATCH")

    def test_a_multitask_action_resolves_from_the_settings_file(self):
        settings = '<MultiTaskSettings>\n  <TaskGroup role="R" action="WORKFLOW:/Missing" />\n</MultiTaskSettings>\n'
        result = self.run_on({APP + PROCESS: process_xml({"A": {}}), APP + "_PROCESS/Case/A.xml": settings})
        self.assert_result(result, 1, "WORKFLOW_UNRESOLVED")
        self.assertIn("a/FM/_PROCESS/Case/A.xml:2 ", result[1])

    def test_form_actions_are_not_workflow_references(self):
        code, out, _ = self.run_on({APP + PROCESS: process_xml({"A": {"action": "FORM:Edit"}})})
        self.assertEqual(code, 0, out)
        self.assertIn("NOT RUN: form-reference", out)

    def test_an_unresolved_validation_flow_blocks(self):
        result = self.run_on({APP + PROCESS: process_xml({"A": {}}, validation_flow="Check")})
        self.assert_result(result, 1, "VALIDATION_FLOW_UNRESOLVED")

    # --- --all and usage ----------------------------------------------------------------

    def test_all_covers_every_process_and_workflow(self):
        root = helpers.make_root(self.tmp, {APP + PROCESS: process_xml({"A": {}}),
                                            APP + "_WORKFLOW/Move/_workflow.xml": workflow_xml({"process": "Case",
                                                                                                "state": "A"})})
        code, out, _ = helpers.run_cli("validate_process.py", "--all", "--workspaces-root", root / "ws")
        self.assertEqual(code, 0, out)
        self.assertEqual(out.count("FAMILY: xsd"), 2, out)
        self.assertIn(CHECKS + ", change-state-target", out)

    def test_usage_errors_are_exit_3(self):
        self.assertEqual(helpers.run_cli("validate_process.py")[0], 3)
        self.assertEqual(helpers.run_cli("validate_process.py", "--all")[0], 3)
        self.assertEqual(helpers.run_cli("validate_process.py", "--all", "--workspaces-root", self.tmp, "x")[0], 3)

    def test_a_json_file_is_exit_3(self):
        self.assert_result(self.run_on({APP + "_COMPONENTS/Page/p.json": '{"type": "page"}'}), 3,
                           "SCHEMA_UNSELECTABLE")


if __name__ == "__main__":
    unittest.main()
