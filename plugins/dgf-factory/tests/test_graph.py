"""scripts/lib/graph.py: the reference graph of one application, and reach over it (ADR 0023 §4)."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tests import helpers

ENTITY = ('<entity><primarykey>Id</primarykey><fields><field name="Id" type="PrimaryKey"/>{fields}</fields>'
          '</entity>\n')


def process(action="", states=(), validation_flow=None):
    """A process whose OnStart runs `action`, with one state per (name, action) pair."""
    flow = f' validationFlow="{validation_flow}"' if validation_flow else ""
    body = "".join(f'<State name="{name}" type="Task" action="{act}"><Transitions><Transition state="End"/>'
                   f'</Transitions></State>' for name, act in states)
    first = states[0][0] if states else "End"
    return (f'<Process title="P" table="T" keyName="id"{flow}><OnStart action="{action}"><Transitions>'
            f'<Transition state="{first}"/></Transitions></OnStart><States>{body}</States></Process>\n')


def workflow(*steps):
    return "<Workflow><Sequence>" + "".join(steps) + "</Sequence></Workflow>\n"


def sub(name, assign=""):
    return f'<SubWorkflow name="s"><Settings workflow="{name}"/>{assign}</SubWorkflow>'


def invoke(table, form, control="Form", assign=""):
    return f'<Invoke name="i" control="{control}"><Settings table="{table}" form="{form}"/>{assign}</Invoke>'


def assign(*names):
    return "<Assign>" + "".join(f'<Field name="{name}" value="x"/>' for name in names) + "</Assign>"


def graph_root(tmp):
    return helpers.make_root(tmp, {
        # a, b and webasm
        "a/FM/_PROCESS/Case/process.xml": process("WORKFLOW:/Start", validation_flow="Check"),
        "a/FM/_WORKFLOW/Start/_workflow.xml": workflow(sub("Middle"), '<StateProcess name="x" mode="START" '
                                                                      'process="Other"/>'),
        "a/FM/_WORKFLOW/Middle/_workflow.xml": workflow(sub("Deep"), sub("Start")),
        "a/FM/_WORKFLOW/Deep/_workflow.xml": workflow(invoke("Cases", "edit"),
                                                      '<UpdateRecord name="u"><Settings table="Cases" form=""/>'
                                                      '</UpdateRecord>',
                                                      '<XmlIsland name="x"><Settings table="Empty"/></XmlIsland>',
                                                      '<DataSourceStep name="d" DataSourceName="People"/>'),
        "a/FM/_WORKFLOW/Check/_workflow.xml": workflow(),
        "a/FM/_WORKFLOW/Lonely/_workflow.xml": workflow(),
        "a/FM/_PROCESS/Other/process.xml": process("WORKFLOW:/Unrelated"),
        "a/FM/_WORKFLOW/Unrelated/_workflow.xml": workflow(invoke("Cases", "edit", control="ServerControl")),
        "a/FM/_DATA/Cases/settings.xml": ENTITY.format(
            fields='<field name="S" type="Lookup"><extract table="Status" view="v"/></field>'),
        "a/FM/_DATA/Cases/_forms/edit/_form.xml": "<form/>\n",
        "a/FM/_DATA/Cases/_forms/default/_form.xml": "<form/>\n",
        "a/FM/_DATA/Status/settings.xml": ENTITY.format(fields=""),
        "a/FM/_COMPONENTS/DataSource/People.json": '{"type": "table"}\n',
        "webasm/FM/_PROCESS/Review/process.xml": process("WORKFLOW:/OnlyInA"),
        "a/FM/_WORKFLOW/OnlyInA/_workflow.xml": workflow(),
        "b/FM/_WORKFLOW/Start/_workflow.xml": workflow(),
    })


@unittest.skipUnless(helpers.have_dependencies(), "lxml / jsonschema not installed")
class Build(unittest.TestCase):
    def setUp(self):
        from lib import graph
        self.graph = graph
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.root = graph_root(self.tmp)
        self.a = graph.build(self.root, "a")

    def kinds(self, g=None):
        return {edge.kind for edge in (g or self.a).edges}

    def edge(self, kind, source=None, g=None):
        return [e for e in (g or self.a).edges if e.kind == kind and (source is None or e.source == source)]

    def test_every_kind_the_root_uses_is_resolved(self):
        for kind in ("process-action", "validation-flow", "start-process", "sub-workflow", "invoke-table",
                     "invoke-form", "record-table", "record-form", "datasource-step", "form-table", "extract-table",
                     "extract-view"):
            self.assertIn(kind, self.kinds(), kind)
        self.assertEqual(self.edge("record-form")[0].target, "a/FM/_DATA/Cases/_forms/default/_form.xml")
        self.assertEqual(self.edge("datasource-step")[0].target, "a/FM/_COMPONENTS/DataSource/People.json")
        self.assertEqual(self.edge("form-table")[0].target, "a/FM/_DATA/Cases/settings.xml")

    def test_a_webasm_process_resolves_per_application(self):
        (review,) = self.edge("process-action", "webasm/FM/_PROCESS/Review/process.xml")
        self.assertEqual((review.status, review.target), ("resolved", "a/FM/_WORKFLOW/OnlyInA/_workflow.xml"))
        b = self.graph.build(self.root, "b")
        (review_b,) = self.edge("process-action", "webasm/FM/_PROCESS/Review/process.xml", g=b)
        self.assertEqual((review_b.status, review_b.target), ("unresolved", "b/FM/_WORKFLOW/OnlyInA/_workflow.xml"))

    def test_a_sub_workflow_has_no_process_local_prefix(self):
        targets = {e.target for e in self.edge("sub-workflow", "a/FM/_WORKFLOW/Start/_workflow.xml")}
        self.assertEqual(targets, {"a/FM/_WORKFLOW/Middle/_workflow.xml"})

    def test_a_sub_workflow_cycle_ends(self):
        reached = dict(self.a.reach("a/FM/_WORKFLOW/Deep/_workflow.xml"))
        self.assertEqual(list(reached), ["a/FM/_PROCESS/Case/process.xml"])
        self.assertEqual([e.kind for e in reached["a/FM/_PROCESS/Case/process.xml"]],
                         ["process-action", "sub-workflow", "sub-workflow"])

    def test_reach_stops_at_a_state_process(self):
        self.assertEqual(self.a.reach("a/FM/_WORKFLOW/Unrelated/_workflow.xml"),
                         [("a/FM/_PROCESS/Other/process.xml", self.a.reach("a/FM/_WORKFLOW/Unrelated/_workflow.xml")[0][1])])
        self.assertNotIn("a/FM/_PROCESS/Case/process.xml", dict(self.a.reach("a/FM/_WORKFLOW/Unrelated/_workflow.xml")))

    def test_an_entity_to_entity_edge_is_a_referrer_but_not_walked(self):
        self.assertEqual(self.a.reach("a/FM/_DATA/Status/settings.xml"), [])
        self.assertEqual([e.kind for e in self.a.referrers("a/FM/_DATA/Status/settings.xml")], ["extract-table"])

    def test_an_invoke_with_another_control_is_no_edge(self):
        self.assertEqual(self.edge("invoke-table", "a/FM/_WORKFLOW/Unrelated/_workflow.xml"), [])

    def test_an_island_with_an_empty_fieldset_is_no_edge(self):
        self.assertEqual(self.edge("island-table"), [])

    def test_unreached_lists_shared_workflows_no_edge_reaches(self):
        self.assertEqual([n.path for n in self.a.unreached()], ["a/FM/_WORKFLOW/Lonely/_workflow.xml"])

    def test_two_builds_agree_and_a_second_build_reads_the_files_afresh(self):
        again = self.graph.build(self.root, "a")
        self.assertEqual(sorted(map(repr, again.edges)), sorted(map(repr, self.a.edges)))
        (self.root / "a/FM/_WORKFLOW/Lonely/_workflow.xml").write_text(workflow(sub("Check")), encoding="utf-8")
        changed = self.graph.build(self.root, "a")
        self.assertEqual([e.target for e in changed.edges if e.source == "a/FM/_WORKFLOW/Lonely/_workflow.xml"],
                         ["a/FM/_WORKFLOW/Check/_workflow.xml"])
        self.assertEqual([e for e in self.a.edges if e.source == "a/FM/_WORKFLOW/Lonely/_workflow.xml"], [])


def route_root(tmp, *steps, forms=()):
    """One process whose one shared workflow holds `steps`, an entity `Cases`, and the named forms of it."""
    return helpers.make_root(tmp, {
        "webasm/FM/.keep": "",
        "a/FM/_PROCESS/P/process.xml": process("WORKFLOW:/W"),
        "a/FM/_WORKFLOW/W/_workflow.xml": workflow(*steps),
        "a/FM/_DATA/Cases/settings.xml": ENTITY.format(fields=""),
        **{f"a/FM/_DATA/Cases/_forms/{form}/_form.xml": "<form/>\n" for form in forms},
    })


def kinds(chains, process_path="a/FM/_PROCESS/P/process.xml"):
    return [edge.kind for edge in dict(chains)[process_path]]


@unittest.skipUnless(helpers.have_dependencies(), "lxml / jsonschema not installed")
class Routes(unittest.TestCase):
    """Each way a process reaches a file, in a root where it is the only way (D18)."""

    def setUp(self):
        from lib import graph
        self.graph = graph
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)

    def test_an_entity_is_reached_through_invoke_table(self):
        root = route_root(self.tmp, invoke("Cases", "edit"))  # no form: invoke-form resolves nowhere
        chains = self.graph.build(root, "a").reach("a/FM/_DATA/Cases/settings.xml")
        self.assertEqual(kinds(chains), ["process-action", "invoke-table"])

    def test_an_entity_is_reached_through_record_table(self):
        root = route_root(self.tmp, '<UpdateRecord name="u"><Settings table="Cases" form="edit"/></UpdateRecord>')
        chains = self.graph.build(root, "a").reach("a/FM/_DATA/Cases/settings.xml")
        self.assertEqual(kinds(chains), ["process-action", "record-table"])

    def test_a_form_is_reached_through_invoke_form_and_record_form(self):
        root = route_root(self.tmp, invoke("Cases", "edit"), forms=("edit",))
        self.assertEqual(kinds(self.graph.build(root, "a").reach("a/FM/_DATA/Cases/_forms/edit/_form.xml")),
                         ["process-action", "invoke-form"])
        root = route_root(Path(self.tmp) / "record",
                          '<UpdateRecord name="u"><Settings table="Cases" form="edit"/></UpdateRecord>', forms=("edit",))
        self.assertEqual(kinds(self.graph.build(root, "a").reach("a/FM/_DATA/Cases/_forms/edit/_form.xml")),
                         ["process-action", "record-form"])

    def test_a_sub_workflow_from_a_process_local_workflow_has_no_process_local_prefix(self):
        """`X` from P's own workflow is the shared `FM/_WORKFLOW/X`, never `FM/_PROCESS/P/X` (HumanWorkflow)."""
        root = helpers.make_root(self.tmp, {
            "webasm/FM/.keep": "",
            "a/FM/_PROCESS/P/process.xml": process("WORKFLOW:Local"),
            "a/FM/_PROCESS/P/Local/_workflow.xml": workflow(sub("X")),
            "a/FM/_PROCESS/P/X/_workflow.xml": workflow(),  # where a process-local prefix would lead
            "a/FM/_WORKFLOW/X/_workflow.xml": workflow(),
        })
        g = self.graph.build(root, "a")
        (edge,) = [e for e in g.edges if e.kind == "sub-workflow"]
        self.assertEqual((edge.source, edge.status, edge.target),
                         ("a/FM/_PROCESS/P/Local/_workflow.xml", "resolved", "a/FM/_WORKFLOW/X/_workflow.xml"))
        self.assertEqual(kinds(g.reach("a/FM/_WORKFLOW/X/_workflow.xml")), ["process-action", "sub-workflow"])
        self.assertEqual(g.reach("a/FM/_PROCESS/P/X/_workflow.xml"), [])


@unittest.skipUnless(helpers.have_dependencies(), "lxml / jsonschema not installed")
class EveryOtherKind(unittest.TestCase):
    """The kinds graph_root does not use, each resolved to its file."""

    def test_each_kind_resolves_to_its_target(self):
        from lib import graph
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        root = helpers.make_root(tmp, {
            "webasm/FM/.keep": "",
            "a/FM/_PROCESS/P/process.xml": process("WORKFLOW:/W"),
            "a/FM/_PROCESS/Other/process.xml": process(),
            "a/FM/_WORKFLOW/W/_workflow.xml": workflow(
                '<StateProcess name="c" mode="CHANGE_STATE" process="Other"/>',
                '<XmlIsland name="x"><Settings table="Cases"/><FieldSet><Field name="Id"/></FieldSet></XmlIsland>'),
            "a/FM/_DATA/Cases/settings.xml": ENTITY.format(fields=(
                '<field name="L" type="Lookup"><extract dialog="People"/></field>'
                '<field name="G" type="EditableGrid"><slavegrid table="Rows" grid="wide"/></field>')),
            "a/FM/_DATA/Rows/settings.xml": ENTITY.format(fields=""),
            "a/FM/_DATA/Rows/_gridforms/wide/_grid.xml": "<view/>\n",
            "a/FM/_LOOKUP/People/_dialog.xml": "<dialog/>\n",
            "a/FM/_COMPONENTS/Page/home.json": json.dumps({"type": "page", "name": "home", "content": [
                {"type": "referenceComponent", "name": "r", "componentType": "page", "componentName": "shared"}]}),
            "a/FM/_COMPONENTS/Page/shared.json": json.dumps({"type": "page", "name": "shared", "content": []}),
        })
        found = {e.kind: (e.status, e.target) for e in graph.build(root, "a").edges}
        expected = {
            "change-state-process": ("resolved", "a/FM/_PROCESS/Other/process.xml"),
            "island-table": ("resolved", "a/FM/_DATA/Cases/settings.xml"),
            "extract-dialog": ("resolved", "a/FM/_LOOKUP/People/_dialog.xml"),
            "slavegrid-table": ("resolved", "a/FM/_DATA/Rows/settings.xml"),
            "slavegrid-grid": ("resolved", "a/FM/_DATA/Rows/_gridforms/wide/_grid.xml"),
            "reference-component": ("resolved", "a/FM/_COMPONENTS/Page/shared.json"),
        }
        for kind, want in expected.items():
            self.assertEqual(found.get(kind), want, kind)


@unittest.skipUnless(helpers.have_dependencies(), "lxml / jsonschema not installed")
class RunTimeNames(unittest.TestCase):
    def setUp(self):
        from lib import graph
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        root = helpers.make_root(self.tmp, {
            "webasm/FM/.keep": "",
            "a/FM/_PROCESS/P/process.xml": process("WORKFLOW:/W"),
            "a/FM/_WORKFLOW/W/_workflow.xml": workflow(
                sub("X", assign("_WORKFLOWNAME_")), sub("Y"), invoke("Cases", "edit", assign=assign("_FORMNAME_")),
                invoke("", "edit", assign=assign("_TABLENAME_")), invoke("Cases", "edit", control="form")),
            "a/FM/_WORKFLOW/X/_workflow.xml": workflow(),
            "a/FM/_WORKFLOW/Y/_workflow.xml": workflow(),
            "a/FM/_DATA/Cases/settings.xml": ENTITY.format(fields=""),
            "a/FM/_DATA/Cases/_forms/edit/_form.xml": "<form/>\n",
        })
        self.edges = graph.build(root, "a").edges

    def statuses(self, kind):
        return [(e.value, e.status) for e in self.edges if e.kind == kind]

    def test_a_sub_workflow_is_dynamic_only_when_its_own_assign_sets_the_name(self):
        self.assertEqual(sorted(self.statuses("sub-workflow")), [("X", "dynamic"), ("Y", "resolved")])

    def test_an_invokes_own_formname_or_tablename_makes_its_form_dynamic(self):
        forms = self.statuses("invoke-form")
        self.assertIn(('table="Cases" form="edit"', "dynamic"), forms)
        self.assertIn(('table="" form="edit"', "dynamic"), forms)
        self.assertIn(('table="Cases" form="edit"', "resolved"), forms)

    def test_an_empty_table_filled_at_run_time_is_a_dynamic_edge_with_no_target(self):
        empty = [e for e in self.edges if e.kind == "invoke-table" and e.value == ""]
        self.assertEqual([(e.status, e.target) for e in empty], [("dynamic", None)])

    def test_control_is_compared_upper_cased(self):
        """Three Invoke steps, the last with control="form" in lower case: each is an edge."""
        self.assertEqual(len([e for e in self.edges if e.kind == "invoke-table"]), 3)

    def test_a_dynamic_edge_adds_no_node_for_a_static_target_that_does_not_exist(self):
        from lib import graph
        root = helpers.make_root(self.tmp, {"a/FM/_WORKFLOW/W/_workflow.xml": workflow(
            sub("Missing", assign("_WORKFLOWNAME_")))})
        g = graph.build(root, "a")
        (edge,) = [e for e in g.edges if e.kind == "sub-workflow"]
        self.assertEqual((edge.status, edge.target), ("dynamic", "a/FM/_WORKFLOW/Missing/_workflow.xml"))
        self.assertNotIn("a/FM/_WORKFLOW/Missing/_workflow.xml", g.nodes)
        self.assertIn("a/FM/_WORKFLOW/X/_workflow.xml", g.nodes)  # nothing reaches X now, but it is a file


@unittest.skipUnless(helpers.have_dependencies(), "lxml / jsonschema not installed")
class MultiTaskAndJson(unittest.TestCase):
    def test_a_process_reaches_its_multitask_file_and_its_actions(self):
        from lib import graph
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        root = helpers.make_root(tmp, {
            "webasm/FM/.keep": "",
            "a/FM/_PROCESS/P/process.xml": process(states=(("Review", ""),)),
            "a/FM/_PROCESS/P/Review.xml": '<MultiTaskSettings><TaskGroup action="WORKFLOW:Local"/></MultiTaskSettings>',
            "a/FM/_PROCESS/P/Local/_workflow.xml": workflow(),
            "a/FM/_COMPONENTS/Page/home.json": '{"type": "Page", "content": [{"type": "Form", "path": "gone"}]}',
        })
        g = graph.build(root, "a")
        self.assertIn("a/FM/_PROCESS/P/process.xml", dict(g.reach("a/FM/_PROCESS/P/Local/_workflow.xml")))
        self.assertEqual(g.nodes["a/FM/_PROCESS/P/Review.xml"].artifact, "multitask")
        layout = [e for e in g.edges if e.kind == "layout-child"]
        self.assertEqual([(e.status, e.target) for e in layout], [("unresolved", "a/FM/_COMPONENTS/Form/gone.json")])


class Artifacts(unittest.TestCase):
    def test_a_lookup_dialog_is_named_by_the_graph_itself(self):
        """No plan.artifact row names `_LOOKUP/<dialog>/_dialog.xml`, so graph.py names it (DD8)."""
        from lib import graph
        self.assertEqual(graph.artifact_of("a/FM/_LOOKUP/People/_dialog.xml"), ("lookup-dialog", "People"))
        self.assertEqual(graph.artifact_of("webasm/FM/_LOOKUP/sub/People/_dialog.xml"), ("lookup-dialog", "sub/People"))
        self.assertIsNone(graph.artifact_of("a/FM/_LOOKUP/People/notes.xml"))
        self.assertIsNone(graph.artifact_of("a/FM/_lookup/People/_dialog.xml"))  # a name matches exactly, as on Linux


@unittest.skipUnless(helpers.have_dependencies(), "lxml / jsonschema not installed")
class TableDriven(unittest.TestCase):
    """The walk and the rules come from the table: change a cell and the graph changes."""

    def setUp(self):
        from lib import knowledge
        self.knowledge = knowledge
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        shutil.copytree(helpers.PLUGIN_ROOT / "knowledge", self.tmp / "knowledge", ignore=shutil.ignore_patterns("schemas"))
        self.saved = knowledge.KNOWLEDGE_DIR
        knowledge.KNOWLEDGE_DIR = self.tmp / "knowledge"
        knowledge._CACHE.clear()
        self.addCleanup(self.restore)
        self.root = graph_root(self.tmp / "root")

    def restore(self):
        self.knowledge.KNOWLEDGE_DIR = self.saved
        self.knowledge._CACHE.clear()

    def mutate(self, old, new):
        path = self.tmp / "knowledge/reference-graph.md"
        text = path.read_text(encoding="utf-8")
        self.assertIn(old, text)
        path.write_text(text.replace(old, new, 1), encoding="utf-8")
        self.knowledge._CACHE.clear()

    def test_the_reach_column_decides_the_walk(self):
        from lib import graph
        self.assertTrue(graph.build(self.root, "a").reach("a/FM/_WORKFLOW/Deep/_workflow.xml"))
        self.mutate("| `workflow-name` | `throws` | `unknown` | `follow` | — |",
                    "| `workflow-name` | `throws` | `unknown` | `none` | — |")
        self.assertEqual(graph.build(self.root, "a").reach("a/FM/_WORKFLOW/Deep/_workflow.xml"), [])

    def test_an_entity_is_reached_through_its_form_when_the_table_edge_is_not_walked(self):
        """invoke-form → form-table: the route the shorter invoke-table hides while it is walked."""
        from lib import graph
        root = route_root(self.tmp / "routes", invoke("Cases", "edit"), forms=("edit",))
        self.assertEqual(kinds(graph.build(root, "a").reach("a/FM/_DATA/Cases/settings.xml")),
                         ["process-action", "invoke-table"])
        self.mutate("| `control-form` | `settings` | `table-name` | `throws` | `unknown` | `end` |",
                    "| `control-form` | `settings` | `table-name` | `throws` | `unknown` | `none` |")
        self.assertEqual(kinds(graph.build(root, "a").reach("a/FM/_DATA/Cases/settings.xml")),
                         ["process-action", "invoke-form", "form-table"])

    def test_the_when_empty_column_decides_whether_an_empty_value_is_a_reference(self):
        from lib import graph
        helpers.make_root(self.root, {"a/FM/_WORKFLOW/Lonely/_workflow.xml": workflow(sub(""))})

        def empty_calls():
            return [e.status for e in graph.build(self.root, "a").edges if e.kind == "sub-workflow" and e.value == ""]

        self.assertEqual(empty_calls(), [])
        self.mutate("| `workflow-name` | `throws` | `unknown` | `follow` | — |",
                    "| `workflow-name` | `throws` | `throws` | `follow` | — |")
        self.assertEqual(empty_calls(), ["unresolved"])

    def test_a_rule_no_reader_has_is_a_knowledge_table_error(self):
        from lib import edges, graph
        saved = edges.RESOLVERS.pop("grid")
        self.addCleanup(edges.RESOLVERS.__setitem__, "grid", saved)
        with self.assertRaises(self.knowledge.KnowledgeTableError):
            graph.build(self.root, "a")

    def test_a_condition_no_reader_has_is_a_knowledge_table_error(self):
        from lib import edges, graph
        saved = edges.CONDITIONS.pop("control-form")
        self.addCleanup(edges.CONDITIONS.__setitem__, "control-form", saved)
        with self.assertRaises(self.knowledge.KnowledgeTableError):
            graph.build(self.root, "a")

    def test_an_arity_mismatch_is_a_knowledge_table_error(self):
        from lib import graph
        self.mutate("| `Invoke/Settings` | `table+form` |", "| `Invoke/Settings` | `form` |")
        with self.assertRaises(self.knowledge.KnowledgeTableError):
            graph.build(self.root, "a")


if __name__ == "__main__":
    unittest.main()
