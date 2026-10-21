"""scripts/audit_root.py: the whole-root audit and blast radius, read-only, never a gate (ADR 0027 §5)."""

import hashlib
import shutil
import tempfile
import unittest
from pathlib import Path

from tests import helpers


def process(action):
    """A process.xsd-valid process whose OnStart runs `action`."""
    return (f'<?xml version="1.0" encoding="utf-8"?>\n<Process title="P" table="T" keyName="id" allowBack="false" '
            f'allowHistory="true" assignTasks="false"><OnStart action="{action}"><Transitions><Transition '
            f'state="Open" /></Transitions></OnStart><States><State name="Open" type="Task"><Transitions>'
            f'<Transition state="End" /></Transitions></State></States></Process>\n')


def workflow(*steps):
    return "<Workflow><Sequence>" + "".join(steps) + "</Sequence></Workflow>\n"


def sub(name):
    return f'<SubWorkflow name="s"><Settings workflow="{name}"/></SubWorkflow>'


ROOT = {
    "webasm/FM/_WORKFLOW/Notify/_workflow.xml": workflow(),
    "webasm/FM/_WORKFLOW/Idle/_workflow.xml": workflow(),
    "webasm/FM/_PROCESS/Review/process.xml": process("WORKFLOW:BASE:Notify"),
    "a/FM/_PROCESS/Case/process.xml": process("WORKFLOW:/Submit"),
    "a/FM/_WORKFLOW/Submit/_workflow.xml": workflow(sub("BASE:Notify"), sub("Missing")),
    "b/FM/_PROCESS/Permit/process.xml": process("WORKFLOW:/Apply"),
    "b/FM/_WORKFLOW/Apply/_workflow.xml": workflow(sub("BASE:Notify")),
    "a/_application.sitemap": '<map><mapNode name="x" roles="Case Officer, Supervisor"/></map>\n',
}


def snapshot(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(Path(root).rglob("*")) if p.is_file()}


@unittest.skipUnless(helpers.have_dependencies(), "lxml / jsonschema not installed")
class Audit(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.root = helpers.make_root(Path(self.tmp) / "ws", ROOT)

    def audit(self, *args):
        before = snapshot(self.root)
        code, out, err = helpers.run_cli("audit_root.py", "--workspaces-root", str(self.root), *args)
        self.assertEqual(snapshot(self.root), before, "the audit wrote under the root")
        self.assertNotIn("dgf-gate-result", out)
        return code, out, err

    def codes(self, out):
        return [line.split()[1] for line in out.splitlines() if line.split()[:1] in (["ERROR"], ["WARN"], ["INFO"])]

    # --- whole root ---------------------------------------------------------------

    def test_a_whole_root_audit(self):
        code, out, _ = self.audit()
        self.assertEqual(code, 2, out)
        self.assertIn("APPLICATIONS: a b (base webasm)", out)
        self.assertRegex(out, r"GRAPH: a nodes=\d+ edges=\d+ resolved=\d+ unresolved=1 ")
        self.assertIn("VALIDATOR: validate_model.py files=0", out)
        self.assertIn('ROLE: " Supervisor" sitemap-roles=1', out)
        self.assertIn('ROLE: "Case Officer" sitemap-roles=1', out)
        self.assertIn("CHECKS RUN: graph, validators, roles", out)
        self.assertIn("NOT RUN: role-check (nothing in the root declares roles", out)
        self.assertIn("LIMIT: static reach only", out)
        self.assertIn("AUDIT_REFERENCE_UNRESOLVED", self.codes(out))
        self.assertIn("INFO AUDIT_WORKFLOW_UNREACHED webasm/FM/_WORKFLOW/Idle/_workflow.xml", out)

    def test_skip_validators(self):
        code, out, _ = self.audit("--skip-validators")
        self.assertIn("NOT RUN: validators (skipped by --skip-validators)", out)
        self.assertNotIn("VALIDATOR:", out)

    def test_app_narrows_and_says_so(self):
        code, out, _ = self.audit("--app", "a", "--skip-validators")
        self.assertEqual(code, 2, out)
        self.assertIn("AUDIT_NARROWED", self.codes(out))
        self.assertIn("NOT RUN: applications (narrowed to a by --app; the other applications were not audited)", out)
        self.assertNotIn("GRAPH: b", out)

    def test_an_unresolved_reference_a_validator_checks_is_left_to_it(self):
        self.root = helpers.make_root(self.root, {
            "a/FM/_DATA/Cases/settings.xml": ('<entity><primarykey>Id</primarykey><fields><field name="Id" '
                                              'type="PrimaryKey"/><field name="S" type="Lookup"><extract '
                                              'table="Gone"/></field></fields></entity>\n')})
        code, out, _ = self.audit()
        self.assertEqual(self.codes(out).count("MODEL_REFERENCE_UNRESOLVED"), 1, out)
        self.assertNotIn("extract-table", "\n".join(l for l in out.splitlines() if "AUDIT_REFERENCE_UNRESOLVED" in l))

    def test_a_validator_usage_code_about_a_file_is_an_error_in_the_root_not_a_usage_error(self):
        """FAMILY_UNRESOLVED is exit 3 for validate_config.py's call; for the audit it is a defect in the root."""
        helpers.make_root(self.root, {"a/FM/_COMPONENTS/DataTable/broken.json": "not json at all\n"})
        code, out, _ = self.audit()
        self.assertEqual(code, 1, out)
        self.assertIn("FAMILY_UNRESOLVED", self.codes(out))
        self.assertTrue(out.rstrip().splitlines()[-1].endswith("BLOCKED"))

    def test_an_unresolved_template_reference_no_validator_checks_is_reported(self):
        """A missing form a record step names is generated and written into the workspace — the audit says so."""
        self.root = helpers.make_root(self.root, {
            "a/FM/_WORKFLOW/Save/_workflow.xml": workflow('<UpdateRecord name="u"><Settings table="Cases" form="edit"/>'
                                                          '</UpdateRecord>'),
            "a/FM/_DATA/Cases/settings.xml": ('<entity><primarykey>Id</primarykey><fields><field name="Id" '
                                              'type="PrimaryKey" uimask="00111"/></fields></entity>\n')})
        code, out, _ = self.audit("--skip-validators")
        (line,) = [l for l in out.splitlines() if "AUDIT_REFERENCE_UNRESOLVED" in l and "record-form" in l]
        self.assertIn("expected `a/FM/_DATA/Cases/_forms/edit/_form.xml`", line)
        self.assertIn("the runtime generates a default and writes it into the workspace", line)

    def test_a_case_only_tables_form_is_left_to_its_table(self):
        """On Linux the table load throws first; the form part must not claim the runtime writes a default."""
        self.root = helpers.make_root(self.root, {
            "a/FM/_WORKFLOW/Save/_workflow.xml": workflow('<UpdateRecord name="u"><Settings table="cases" form="edit"/>'
                                                          '</UpdateRecord>'),
            "a/FM/_DATA/Cases/settings.xml": ('<entity><primarykey>Id</primarykey><fields><field name="Id" '
                                              'type="PrimaryKey" uimask="00111"/></fields></entity>\n')})
        code, out, _ = self.audit("--skip-validators")
        mine = [l for l in out.splitlines() if "a/FM/_WORKFLOW/Save/_workflow.xml" in l and l.split()[:1] == ["WARN"]]
        self.assertEqual([l.split()[1] for l in mine], ["CASE_ONLY_MATCH"], out)
        self.assertIn("record-table", mine[0])

    def test_a_vendored_schema_the_validators_cannot_read_stays_a_usage_error(self):
        """An unreadable schema dialect is the install's defect, not the root's: exit 3, as for KNOWLEDGE_TABLE."""
        import contextlib
        import io
        from unittest import mock
        import audit_root
        from lib import json_validate
        helpers.make_root(self.root, {"a/FM/_COMPONENTS/Text/t.json": '{"type": "Text"}\n'})
        with mock.patch.object(json_validate, "validator_class", return_value=None), \
                mock.patch.dict(json_validate._VALIDATORS, clear=True), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            code = audit_root.main(["--workspaces-root", str(self.root)])
        self.assertEqual(code, 3, out.getvalue())
        self.assertEqual(self.codes(out.getvalue()), ["SCHEMA_UNSELECTABLE"], out.getvalue())

    def test_a_generated_form_that_throws_is_reported_as_throwing(self):
        """With no `default` form, FormManager.GetXmlTemplate throws on a field with no uimask."""
        self.root = helpers.make_root(self.root, {
            "a/FM/_WORKFLOW/Save/_workflow.xml": workflow('<UpdateRecord name="u"><Settings table="Cases" form="edit"/>'
                                                          '</UpdateRecord>'),
            "a/FM/_DATA/Cases/settings.xml": ('<entity><primarykey>Id</primarykey><fields><field name="Id" '
                                              'type="PrimaryKey"/></fields></entity>\n')})
        code, out, _ = self.audit("--skip-validators")
        (line,) = [l for l in out.splitlines() if "AUDIT_REFERENCE_UNRESOLVED" in l and "record-form" in l]
        self.assertIn("`Id` has no `uimask`", line)
        self.assertIn("and the loader throws", line)

    def test_a_generated_form_whose_title_would_not_parse_is_reported_as_throwing(self):
        """GetXmlTemplate pastes a row's title unescaped, and SaveXml re-parses the form (data-model.md §3.6)."""
        self.root = helpers.make_root(self.root, {
            "a/FM/_WORKFLOW/Save/_workflow.xml": workflow('<UpdateRecord name="u"><Settings table="Cases" form="edit"/>'
                                                          '</UpdateRecord>'),
            "a/FM/_DATA/Cases/settings.xml": ('<entity><primarykey>Id</primarykey><fields><field name="Id" '
                                              'type="PrimaryKey" uimask="00111"/><field name="Name" type="Text" '
                                              'uimask="01111" title="A &amp; B"/></fields></entity>\n')})
        code, out, _ = self.audit("--skip-validators")
        (line,) = [l for l in out.splitlines() if "AUDIT_REFERENCE_UNRESOLVED" in l and "record-form" in l]
        self.assertIn("pastes the title of `Name`, `A & B`, unescaped, and does not parse", line)
        self.assertIn("and the loader throws", line)
        self.assertNotIn("the runtime generates a default", line)

    def test_a_json_file_outside_every_fm_is_a_draft_no_loader_reads(self):
        """A validator's call on it is exit 3, but for the root it is no configuration: not a defect in it."""
        helpers.make_root(self.root, {"a/package.json": '{"name": "tooling"}\n'})
        code, out, _ = self.audit()
        self.assertEqual(code, 2, out)
        self.assertNotIn("SCHEMA_UNSELECTABLE", self.codes(out))
        self.assertIn("NOT RUN: drafts (1 JSON file outside every FM/, which no loader reads)", out)

    def test_a_validator_that_raises_is_exit_3_with_the_report_so_far(self):
        """A crash is no finding about the root: the audit could not check it, and says so."""
        folder = self.root / "a/FM/_DATA/Cases"
        folder.mkdir(parents=True)
        (folder / "settings.xml").symlink_to(self.root / "nowhere.xml")
        code, out, err = self.audit()
        self.assertEqual(code, 3, out + err)
        self.assertIn("AUDIT_CHECK_FAILED", self.codes(out))
        self.assertIn("FileNotFoundError", out)
        self.assertRegex(out, r"NOT RUN: validators \(stopped on FileNotFoundError")
        self.assertNotRegex(out, r"CHECKS RUN: .*validators")
        self.assertIn("GRAPH: a", out)
        self.assertTrue(out.rstrip().splitlines()[-1].endswith("BLOCKED"))

    def test_a_reach_through_a_component_whose_schema_cannot_be_read_is_a_usage_error(self):
        """A reference the unreadable dialect hides is reported as that dialect, never dropped."""
        import contextlib
        import io
        from unittest import mock
        import audit_root
        from lib import json_validate
        helpers.make_root(self.root, {
            "a/FM/_COMPONENTS/Page/home.json": '{"type": "Page", "content": [{"type": "Form", "path": "f"}]}\n',
            "a/FM/_COMPONENTS/Form/f.json": '{"type": "Form"}\n'})
        with mock.patch.object(json_validate, "validator_class", return_value=None), \
                mock.patch.dict(json_validate._VALIDATORS, clear=True), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            code = audit_root.main(["--workspaces-root", str(self.root), "--reach", "a/FM/_COMPONENTS/Form/f.json"])
        self.assertEqual(code, 3, out.getvalue())
        self.assertEqual(self.codes(out.getvalue()), ["SCHEMA_UNSELECTABLE"], out.getvalue())
        self.assertIn("APPLICATIONS: a b (base webasm)", out.getvalue())  # the report so far

    def raising(self, target, name, *args):
        """audit_root.main's exit and output with `target.name` raising RuntimeError("boom")."""
        import contextlib
        import io
        from unittest import mock
        import audit_root
        with mock.patch.object(target, name, side_effect=RuntimeError("boom")), \
                contextlib.redirect_stdout(io.StringIO()) as out:
            code = audit_root.main(["--workspaces-root", str(self.root), *args])
        out = out.getvalue()
        self.assertEqual(code, 3, out)
        self.assertEqual(self.codes(out), ["AUDIT_CHECK_FAILED"], out)
        self.assertIn("NOT RUN: audit (stopped on RuntimeError: boom)", out)
        self.assertIn(f"ROOT: {self.root.resolve()}", out)
        self.assertIn("APPLICATIONS: a b (base webasm)", out)
        self.assertIn("LIMIT: static reach only", out)
        return out

    def test_a_check_that_raises_before_anything_ran_is_exit_3_and_claims_nothing_ran(self):
        from lib import graph
        for mode in ((), ("--reach", "webasm/FM/_WORKFLOW/Notify/_workflow.xml")):
            out = self.raising(graph, "build", *mode)
            self.assertRegex(out, r"(?m)^CHECKS RUN: \(none\)$", mode)
            self.assertNotIn("GRAPH:", out)

    def test_a_check_that_raises_after_the_graph_is_exit_3_with_the_report_so_far(self):
        from lib import roles
        out = self.raising(roles, "inventory")
        self.assertRegex(out, r"(?m)^CHECKS RUN: graph, validators$")  # roles raised: not run
        self.assertRegex(out, r"GRAPH: a nodes=\d+ edges=\d+ ")
        self.assertRegex(out, r"GRAPH: b nodes=\d+ edges=\d+ ")
        self.assertIn("VALIDATOR: validate_process.py files=", out)
        self.assertNotIn("ROLE:", out)

    def test_a_reach_that_raises_is_exit_3_with_the_report_so_far(self):
        from lib import graph
        out = self.raising(graph.Graph, "reach", "--reach", "webasm/FM/_WORKFLOW/Notify/_workflow.xml")
        self.assertRegex(out, r"(?m)^CHECKS RUN: graph$")  # the reach raised: not run
        self.assertIn("REACH: webasm/FM/_WORKFLOW/Notify/_workflow.xml artifact=workflow name=Notify", out)

    def test_a_malformed_knowledge_table_a_validator_meets_stops_the_audit_as_one(self):
        """A malformed table is the install's defect, which every script reports the same way — never as a check."""
        import contextlib
        import io
        from unittest import mock
        import audit_root
        from lib import knowledge, runner
        with mock.patch.object(runner, "run", side_effect=knowledge.KnowledgeTableError("reference-edges", "x")), \
                contextlib.redirect_stdout(io.StringIO()) as out, contextlib.redirect_stderr(io.StringIO()) as err, \
                self.assertRaises(SystemExit) as stop:
            audit_root.main(["--workspaces-root", str(self.root)])
        self.assertEqual(stop.exception.code, 3)
        self.assertIn("ERROR KNOWLEDGE_TABLE knowledge table `reference-edges` malformed", err.getvalue())
        self.assertNotIn("AUDIT_CHECK_FAILED", out.getvalue())

    # --- reach ----------------------------------------------------------------------

    def test_reach_on_a_lookup_dialog_names_the_entities_that_use_it(self):
        self.root = helpers.make_root(self.root, {
            "a/FM/_DATA/Cases/settings.xml": ('<entity><primarykey>Id</primarykey><fields><field name="Id" '
                                              'type="PrimaryKey"/><field name="P" type="Lookup"><extract '
                                              'dialog="People"/></field></fields></entity>\n'),
            "a/FM/_LOOKUP/People/_dialog.xml": "<dialog/>\n"})
        code, out, _ = self.audit("--reach", "a/FM/_LOOKUP/People/_dialog.xml")
        self.assertEqual(code, 0, out)
        self.assertIn("REACH: a/FM/_LOOKUP/People/_dialog.xml artifact=lookup-dialog name=People", out)
        self.assertRegex(out, r"REFERRER: a extract-dialog a/FM/_DATA/Cases/settings.xml:\d+")

    def test_reach_on_a_shared_workflow_two_processes_reach_in_two_applications(self):
        code, out, _ = self.audit("--reach", "webasm/FM/_WORKFLOW/Notify/_workflow.xml")
        self.assertEqual(code, 0, out)
        self.assertIn("REACH: webasm/FM/_WORKFLOW/Notify/_workflow.xml artifact=workflow name=Notify", out)
        self.assertIn("APP: a processes=2", out)
        self.assertIn("APP: b processes=2", out)
        self.assertIn("PROCESS: a Case via a/FM/_PROCESS/Case/process.xml:2 > a/FM/_WORKFLOW/Submit/_workflow.xml:1 > "
                      "webasm/FM/_WORKFLOW/Notify/_workflow.xml", out)
        self.assertIn("PROCESS: b BASE:Review via webasm/FM/_PROCESS/Review/process.xml:2 > "
                      "webasm/FM/_WORKFLOW/Notify/_workflow.xml", out)
        self.assertIn("REFERRER: a sub-workflow a/FM/_WORKFLOW/Submit/_workflow.xml:1", out)
        self.assertIn("CHECKS RUN: graph, reach", out)
        self.assertTrue(out.rstrip().splitlines()[-1].endswith("CLEAN"))
        self.assertIn("LIMIT: static reach only", out)

    def test_a_chain_through_a_run_time_name_is_marked_dynamic(self):
        """The step's own Assign sets _WORKFLOWNAME_, so it may load another workflow (reference-graph.md §3.1)."""
        self.root = helpers.make_root(self.root, {
            "a/FM/_PROCESS/Routed/process.xml": process("WORKFLOW:/Route"),
            "a/FM/_WORKFLOW/Route/_workflow.xml": workflow('<SubWorkflow name="s"><Settings workflow="Target"/>'
                                                           '<Assign><Field name="_WORKFLOWNAME_" value="x"/></Assign>'
                                                           '</SubWorkflow>'),
            "a/FM/_WORKFLOW/Target/_workflow.xml": workflow()})
        code, out, _ = self.audit("--reach", "a/FM/_WORKFLOW/Target/_workflow.xml")
        self.assertEqual((code, self.codes(out)), (0, ["AUDIT_REFERENCE_DYNAMIC"]), out)
        self.assertIn("PROCESS: a Routed via a/FM/_PROCESS/Routed/process.xml:2 > a/FM/_WORKFLOW/Route/_workflow.xml:1 > "
                      "a/FM/_WORKFLOW/Target/_workflow.xml", out)
        (line,) = [l for l in out.splitlines() if "AUDIT_REFERENCE_DYNAMIC" in l]
        self.assertIn("a/FM/_WORKFLOW/Route/_workflow.xml:1 (sub-workflow)", line)
        code, out, _ = self.audit("--reach", "webasm/FM/_WORKFLOW/Notify/_workflow.xml")  # no run-time name on it
        self.assertNotIn("AUDIT_REFERENCE_DYNAMIC", self.codes(out))

    def test_reach_on_an_application_file_reports_that_application_only(self):
        code, out, _ = self.audit("--reach", "a/FM/_WORKFLOW/Submit/_workflow.xml")
        self.assertIn("APP: a processes=1", out)
        self.assertNotIn("APP: b", out)

    def test_a_reach_into_an_application_the_audit_narrowed_away_says_it_was_not_audited(self):
        code, out, _ = self.audit("--app", "a", "--reach", "b/FM/_WORKFLOW/Apply/_workflow.xml")
        self.assertEqual(code, 2, out)
        self.assertIn("NOT AUDITED: b — --app narrowed the audit to a, so no process of b was walked", out)
        self.assertNotIn("APP: a", out)  # a's processes cannot reach b's own file
        self.assertNotIn("NONE:", out)   # nothing was walked, so no reach is claimed either way

    def test_a_change_in_a_workspace_no_longer_under_the_root_is_not_blamed_on_app(self):
        code, out, _ = self.audit("--changed", "D:gone/FM/_WORKFLOW/X/_workflow.xml")
        self.assertEqual(code, 0, out)
        self.assertNotIn("NOT AUDITED", out)  # no --app was given
        self.assertIn("NONE: gone — no application `gone` is under the root now, so no process of it was walked", out)

    def test_reach_on_a_file_nothing_reaches(self):
        code, out, _ = self.audit("--reach", "webasm/FM/_WORKFLOW/Idle/_workflow.xml")
        self.assertIn("NONE: a — no traced reference reaches it", out)
        self.assertIn("LIMIT:", out)

    def test_reach_on_a_non_artifact_is_exit_3(self):
        helpers.make_root(self.root, {"a/notes.txt": "x"})
        code, out, _ = self.audit("--reach", "a/notes.txt")
        self.assertEqual((code, self.codes(out)), (3, ["AUDIT_REACH_NOT_ARTIFACT"]), out)

    def test_reach_on_a_path_that_matches_only_in_case_is_exit_3(self):
        """On Linux, where DGF runs, the path names no file; APFS and NTFS must not say otherwise (RULES.md rule 2)."""
        code, out, _ = self.audit("--reach", "webasm/FM/_WORKFLOW/notify/_workflow.xml")
        self.assertEqual((code, self.codes(out)), (3, ["AUDIT_REACH_NOT_ARTIFACT"]), out)
        self.assertIn("on disk it is `webasm/FM/_WORKFLOW/Notify/_workflow.xml`", out)
        self.assertNotIn("NONE:", out)

    def test_a_form_folder_without_its_file_is_reported_when_the_table_has_a_default(self):
        """FormManager.Copy throws into a folder that exists, so a `template` edge's target throws here."""
        self.root = helpers.make_root(self.root, {
            "a/FM/_WORKFLOW/Save/_workflow.xml": workflow('<UpdateRecord name="u"><Settings table="Cases" form="edit"/>'
                                                          '</UpdateRecord>'),
            "a/FM/_DATA/Cases/settings.xml": ('<entity><primarykey>Id</primarykey><fields><field name="Id" '
                                              'type="PrimaryKey"/></fields></entity>\n'),
            "a/FM/_DATA/Cases/_forms/default/_form.xml": "<form/>\n",
            "a/FM/_DATA/Cases/_forms/edit/notes.txt": "x"})
        code, out, _ = self.audit("--skip-validators")
        (line,) = [l for l in out.splitlines() if "AUDIT_REFERENCE_UNRESOLVED" in l and "record-form" in l]
        self.assertIn("`a/FM/_DATA/Cases/_forms/edit/` exists without `_form.xml`", line)

    def test_skip_validators_with_a_reach_mode_is_exit_3(self):
        code, _, err = self.audit("--reach", "webasm/FM/_WORKFLOW/Notify/_workflow.xml", "--skip-validators")
        self.assertEqual(code, 3, err)

    def test_a_path_that_leaves_the_root_or_a_base_that_is_an_option_is_exit_3(self):
        self.assertEqual(self.audit("--reach", "a/FM/../../x.xml")[0], 3)
        self.assertEqual(self.audit("--base", "--output=x")[0], 3)
        self.assertEqual(self.audit("--app", "nowhere")[0], 3)

    def test_changed_without_git(self):
        code, out, _ = self.audit("--changed", "M:webasm/FM/_WORKFLOW/Notify/_workflow.xml", "A:a/notes.txt")
        self.assertIn("REACH: webasm/FM/_WORKFLOW/Notify/_workflow.xml artifact=workflow name=Notify change=M", out)
        self.assertIn("SKIP: a/notes.txt — not a configuration file", out)

    def test_a_deleted_file_is_reached_through_the_references_that_now_dangle(self):
        (self.root / "a/FM/_WORKFLOW/Submit/_workflow.xml").unlink()
        code, out, _ = self.audit("--changed", "D:a/FM/_WORKFLOW/Submit/_workflow.xml")
        self.assertIn("deleted — reached through references that now resolve nowhere", out)
        self.assertIn("PROCESS: a Case via a/FM/_PROCESS/Case/process.xml:2 > a/FM/_WORKFLOW/Submit/_workflow.xml", out)


@unittest.skipUnless(helpers.have_dependencies() and helpers.have_git(), "needs lxml, jsonschema and git")
class Branch(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.root = helpers.make_repo(Path(self.tmp) / "ws", ROOT)
        helpers.git(self.root, "checkout", "-q", "-b", "feature/x")

    def test_a_branch_that_edits_a_shared_workflow(self):
        (self.root / "webasm/FM/_WORKFLOW/Notify/_workflow.xml").write_text(workflow(sub("Other")), encoding="utf-8")
        code, out, _ = helpers.run_cli("audit_root.py", "--workspaces-root", str(self.root), "--base", "main")
        self.assertIn("change=M", out)
        self.assertIn("APP: a processes=2", out)

    def test_a_branch_that_deletes_it(self):
        (self.root / "webasm/FM/_WORKFLOW/Notify/_workflow.xml").unlink()
        code, out, _ = helpers.run_cli("audit_root.py", "--workspaces-root", str(self.root), "--base", "main")
        self.assertIn("change=D deleted", out)
        self.assertIn("APP: b processes=2", out)


class Dependencies(unittest.TestCase):
    def test_without_lxml_it_exits_3(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        root = helpers.make_root(Path(tmp) / "ws", ROOT)
        code, _, err = helpers.run_cli_blocking("audit_root.py", "--workspaces-root", str(root))
        self.assertEqual(code, 3, err)


if __name__ == "__main__":
    unittest.main()
