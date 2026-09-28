"""scripts/validate_model.py end to end, on synthetic workspaces roots (ADR 0023 §3)."""

import shutil
import tempfile
import unittest
from pathlib import Path

from tests import helpers

APP = "ws/a/FM/_DATA/"
OTHER = "ws/b/FM/_DATA/"
BASE = "ws/webasm/FM/_DATA/"


def entity(*fields):
    """An entity settings.xml with an `Id` key and the given `<field>` elements."""
    body = "".join(f"    {field}\n" for field in fields)
    return (f'<entity>\n  <primarykey>Id</primarykey>\n  <fields>\n    <field name="Id" type="PrimaryKey"/>\n'
            f'{body}  </fields>\n</entity>\n')


def lookup(name, **extract):
    attributes = " ".join(f'{key}="{value}"' for key, value in extract.items())
    return f'<field name="{name}" type="Lookup"><extract {attributes}/></field>'


def grid(name, **slavegrid):
    attributes = " ".join(f'{key}="{value}"' for key, value in slavegrid.items())
    return f'<field name="{name}" type="EditableGrid"><slavegrid {attributes}/></field>'


def form(*cells, hidden=()):
    rows = "".join(f"<row>{cell}</row>" for cell in cells)
    hide = "".join(hidden)
    return (f"<form><tabs><tab><sections><section><rows>{rows}</rows></section></sections></tab></tabs>"
            f"<hidden>{hide}</hidden></form>\n")


@unittest.skipUnless(helpers.have_dependencies(), "lxml / jsonschema not installed")
class ValidateModel(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.files = {"ws/webasm/FM/.keep": "", APP + "Status/settings.xml": entity()}

    def run_on(self, files, *targets, extra=()):
        root = helpers.make_root(self.tmp, {**self.files, **files})
        args = [str(root / target) for target in targets] or ["--all"]
        return helpers.run_cli("validate_model.py", "--workspaces-root", str(root / "ws"), *args, *extra)

    def codes(self, out):
        return [line.split()[1] for line in out.splitlines() if line.split()[:1] in (["ERROR"], ["WARN"], ["INFO"])]

    # --- extract ----------------------------------------------------------------

    def test_an_extract_whose_table_and_view_exist_is_clean(self):
        code, out, _ = self.run_on({APP + "Cases/settings.xml": entity(lookup("S", table="Status", view="v")),
                                    APP + "Status/_lookupviews/v/_view.xml": "<view/>"}, APP + "Cases/settings.xml")
        self.assertEqual((code, self.codes(out)), (0, []), out)
        self.assertIn("CHECKS RUN: model-references", out)

    def test_a_missing_extract_table_blocks(self):
        code, out, _ = self.run_on({APP + "Cases/settings.xml": entity(lookup("S", table="Nowhere"))},
                                   APP + "Cases/settings.xml")
        self.assertEqual((code, self.codes(out)), (1, ["MODEL_REFERENCE_UNRESOLVED"]), out)
        self.assertIn("extract-table: `field` `S` names `Nowhere`, but `a/FM/_DATA/Nowhere/settings.xml`", out)
        self.assertNotIn(self.tmp, out.split("MODEL_REFERENCE_UNRESOLVED", 1)[1].split(" ", 2)[2])

    def test_a_missing_view_warns_that_the_runtime_writes_one(self):
        code, out, _ = self.run_on({APP + "Cases/settings.xml": entity(lookup("S", table="Status", view="short")),
                                    APP + "Status/settings.xml": entity('<field name="Name" type="Text"/>')},
                                   APP + "Cases/settings.xml")
        self.assertEqual((code, self.codes(out)), (2, ["MODEL_REFERENCE_TEMPLATED"]), out)
        self.assertIn("writes it into the workspace", out)

    def test_a_missing_view_blocks_when_its_table_has_no_text_field_besides_its_key(self):
        """LookUpViewManager.GetXmlTemplate needs a Text field that is not the key; `Status` has only its key."""
        code, out, _ = self.run_on({APP + "Cases/settings.xml": entity(lookup("S", table="Status", view="short"))},
                                   APP + "Cases/settings.xml")
        self.assertEqual((code, self.codes(out)), (1, ["MODEL_REFERENCE_UNRESOLVED"]), out)
        self.assertIn("a `Text` field besides the key `Id`", out)
        self.assertIn("the loader throws", out)

    def test_a_missing_view_blocks_when_the_generated_view_would_not_parse(self):
        """The runtime pastes the display field's title unescaped and re-parses: `&` makes the view throw."""
        code, out, _ = self.run_on({APP + "Cases/settings.xml": entity(lookup("S", table="Status", view="short")),
                                    APP + "Status/settings.xml": entity('<field name="Name" type="Text" '
                                                                        'title="Name &amp; Surname"/>')},
                                   APP + "Cases/settings.xml")
        self.assertEqual((code, self.codes(out)), (1, ["MODEL_REFERENCE_UNRESOLVED"]), out)
        self.assertIn("the title of `Name`", out)

    def test_an_empty_view_is_default(self):
        code, out, _ = self.run_on({APP + "Cases/settings.xml": entity(lookup("S", table="Status")),
                                    APP + "Status/_lookupviews/default/_view.xml": "<view/>"}, APP + "Cases/settings.xml")
        self.assertEqual((code, self.codes(out)), (0, []), out)

    def test_a_view_is_not_reported_when_its_table_is_missing(self):
        code, out, _ = self.run_on({APP + "Cases/settings.xml": entity(lookup("S", table="Nowhere", view="v"))},
                                   APP + "Cases/settings.xml")
        self.assertEqual(self.codes(out), ["MODEL_REFERENCE_UNRESOLVED"], out)

    def test_a_dialog_is_checked_only_when_the_extract_has_no_table(self):
        code, out, _ = self.run_on({APP + "Cases/settings.xml": entity(lookup("S", dialog="Gone"),
                                                                       lookup("T", table="Status", dialog="Gone")),
                                    APP + "Status/_lookupviews/default/_view.xml": "<view/>"},
                                   APP + "Cases/settings.xml")
        self.assertEqual((code, self.codes(out)), (1, ["MODEL_REFERENCE_UNRESOLVED"]), out)
        self.assertIn("extract-dialog: `field` `S` names `Gone`", out)

    def test_an_extract_with_neither_table_nor_dialog_blocks(self):
        """BaseDataRowProvider throws `Lookup table/view or dialog not defined` (data-model.md §3.2)."""
        code, out, _ = self.run_on({APP + "Cases/settings.xml": entity(lookup("S"))}, APP + "Cases/settings.xml")
        self.assertEqual((code, self.codes(out)), (1, ["MODEL_REFERENCE_UNRESOLVED"]), out)
        self.assertIn("extract-dialog: `field` `S` names no dialog", out)
        self.assertNotIn("names ``", out)

    def test_a_dialog_in_the_application_is_clean(self):
        code, out, _ = self.run_on({APP + "Cases/settings.xml": entity(lookup("S", dialog="People")),
                                    "ws/a/FM/_LOOKUP/People/_dialog.xml": "<dialog/>"}, APP + "Cases/settings.xml")
        self.assertEqual((code, self.codes(out)), (0, []), out)

    def test_base_dbo_x_resolves_in_the_application(self):
        code, out, _ = self.run_on({APP + "Cases/settings.xml": entity(lookup("S", table="BASE:dbo.Status")),
                                    APP + "Status/_lookupviews/default/_view.xml": "<view/>"}, APP + "Cases/settings.xml")
        self.assertEqual((code, self.codes(out)), (0, []), out)

    def test_a_case_only_table_warns(self):
        code, out, _ = self.run_on({APP + "Cases/settings.xml": entity(lookup("S", table="status")),
                                    APP + "Status/_lookupviews/default/_view.xml": "<view/>"}, APP + "Cases/settings.xml")
        self.assertIn("CASE_ONLY_MATCH", self.codes(out), out)
        self.assertNotIn("MODEL_REFERENCE_UNRESOLVED", self.codes(out), out)

    def test_a_case_only_table_is_reported_once_not_again_by_its_view(self):
        """On Linux the table load throws first, so the view part would only repeat the table's finding."""
        code, out, _ = self.run_on({APP + "Cases/settings.xml": entity(lookup("S", table="status")),
                                    APP + "Status/_lookupviews/default/_view.xml": "<view/>"}, APP + "Cases/settings.xml")
        self.assertEqual(self.codes(out), ["CASE_ONLY_MATCH"], out)
        self.assertIn("extract-table", out)
        self.assertNotIn("extract-view", out)

    # --- slavegrid ----------------------------------------------------------------

    def test_a_missing_slavegrid_table_blocks_and_a_missing_grid_warns(self):
        code, out, _ = self.run_on({APP + "Cases/settings.xml": entity(grid("R", table="Rows"),
                                                                       grid("Q", table="Status", grid="wide"))},
                                   APP + "Cases/settings.xml")
        self.assertEqual((code, sorted(self.codes(out))), (1, ["MODEL_REFERENCE_TEMPLATED", "MODEL_REFERENCE_UNRESOLVED"]),
                         out)
        self.assertIn("slavegrid-table: `field` `R` names `Rows`", out)
        self.assertIn("slavegrid-grid: `field` `Q`", out)

    def test_a_slavegrid_with_no_table_blocks_once(self):
        """TableManager.LoadAsync throws on an empty name (data-model.md §3.1), before the grid is looked for."""
        code, out, _ = self.run_on({APP + "Cases/settings.xml": entity(grid("R", grid="rows"))},
                                   APP + "Cases/settings.xml")
        self.assertEqual((code, self.codes(out)), (1, ["MODEL_REFERENCE_UNRESOLVED"]), out)
        self.assertIn("slavegrid-table: `field` `R` names no table", out)

    def test_a_grid_folder_without_its_file_blocks_when_the_table_has_a_default(self):
        """Copying `default` into a folder that exists throws (EditableGridManager.Copy, data-model.md §3.6)."""
        code, out, _ = self.run_on({APP + "Cases/settings.xml": entity(grid("Q", table="Status", grid="wide")),
                                    APP + "Status/_gridforms/default/_grid.xml": "<view/>",
                                    APP + "Status/_gridforms/wide/notes.txt": "x"}, APP + "Cases/settings.xml")
        self.assertEqual((code, self.codes(out)), (1, ["MODEL_REFERENCE_UNRESOLVED"]), out)
        self.assertIn("`a/FM/_DATA/Status/_gridforms/wide/` exists without `_grid.xml`", out)

    def test_a_grid_folder_without_its_file_warns_when_the_table_has_no_default(self):
        """With no `default` to copy, the runtime generates the grid and saves it into the folder."""
        code, out, _ = self.run_on({APP + "Cases/settings.xml": entity(grid("Q", table="Status", grid="wide")),
                                    APP + "Status/_gridforms/wide/notes.txt": "x"}, APP + "Cases/settings.xml")
        self.assertEqual((code, self.codes(out)), (2, ["MODEL_REFERENCE_TEMPLATED"]), out)

    def test_a_rooted_table_names_why_it_resolves_nowhere(self):
        code, out, _ = self.run_on({APP + "Cases/settings.xml": entity(lookup("S", table="/Status"))},
                                   APP + "Cases/settings.xml")
        self.assertEqual(self.codes(out), ["MODEL_REFERENCE_UNRESOLVED"], out)
        self.assertIn("does not exist — a name starting with `/` is rooted", out)

    # --- webasm ---------------------------------------------------------------------

    def test_a_webasm_entitys_unprefixed_table_is_app_dependent_naming_both_lists(self):
        code, out, _ = self.run_on({"ws/b/FM/.keep": "",
                                    BASE + "Cases/settings.xml": entity(lookup("S", table="Status")),
                                    APP + "Status/_lookupviews/default/_view.xml": "<view/>"},
                                   BASE + "Cases/settings.xml")
        self.assertEqual((code, self.codes(out)), (2, ["MODEL_REFERENCE_APP_DEPENDENT"]), out)
        self.assertIn("present in a, absent from b", out)

    def test_a_webasm_entitys_unprefixed_table_every_application_has_is_clean(self):
        code, out, _ = self.run_on({OTHER + "Status/settings.xml": entity(),
                                    BASE + "Cases/settings.xml": entity(lookup("S", table="Status")),
                                    APP + "Status/_lookupviews/default/_view.xml": "<view/>",
                                    OTHER + "Status/_lookupviews/default/_view.xml": "<view/>"},
                                   BASE + "Cases/settings.xml")
        self.assertEqual((code, self.codes(out)), (0, []), out)

    def test_a_webasm_form_reads_xsd_like_validate_config(self):
        files = {BASE + "Cases/settings.xml": entity(), BASE + "Cases/_forms/edit/_form.xml": form('<cell name="Id"/>')}
        code, out, _ = self.run_on(files, BASE + "Cases/_forms/edit/_form.xml")
        self.assertEqual(code, 0, out)
        self.assertRegex(out, r"FAMILY: xsd \S*webasm/FM/_DATA/Cases/_forms/edit/_form\.xml")
        _, config, _ = helpers.run_cli("validate_config.py", str(Path(self.tmp) / BASE / "Cases/_forms/edit/_form.xml"))
        self.assertRegex(config, r"FAMILY: xsd ")

    # --- forms ------------------------------------------------------------------------

    def test_a_form_whose_entity_is_missing_blocks(self):
        code, out, _ = self.run_on({APP + "Gone/_forms/edit/_form.xml": form()}, APP + "Gone/_forms/edit/_form.xml")
        self.assertEqual((code, self.codes(out)), (1, ["MODEL_REFERENCE_UNRESOLVED"]), out)
        self.assertIn("form-table: the file needs `a/FM/_DATA/Gone/settings.xml`, which does not exist, and the loader "
                      "throws", out)
        self.assertNotIn("names ``", out)
        self.assertIn("NOT RUN: form-cells (the form's entity does not load)", out)

    def test_a_bound_cell_that_names_no_field_blocks(self):
        files = {APP + "Cases/settings.xml": entity(),
                 APP + "Cases/_forms/edit/_form.xml": form('<cell name="Id"/>', '<cell name="Removed"/>',
                                                           hidden=('<cell name="AlsoGone"/>',))}
        code, out, _ = self.run_on(files, APP + "Cases/_forms/edit/_form.xml")
        self.assertEqual((code, self.codes(out)), (1, ["MODEL_CELL_UNBOUND", "MODEL_CELL_UNBOUND"]), out)
        self.assertIn("cell `Removed` names no field of `Cases`", out)
        self.assertIn("CHECKS RUN: model-references, form-cells", out)

    def test_hidden_cells_are_not_bound_when_the_form_has_no_tabs(self):
        """Form.InitFields returns before it binds the hidden cells when `Tabs` is null (data-model.md §4)."""
        files = {APP + "Cases/settings.xml": entity(),
                 APP + "Cases/_forms/edit/_form.xml": '<form><hidden><cell name="Gone"/></hidden></form>\n',
                 APP + "Cases/_forms/empty/_form.xml": '<form><tabs/><hidden><cell name="Gone"/></hidden></form>\n'}
        code, out, _ = self.run_on(files, APP + "Cases/_forms/edit/_form.xml")
        self.assertEqual((code, self.codes(out)), (0, []), out)
        code, out, _ = self.run_on(files, APP + "Cases/_forms/empty/_form.xml")
        self.assertEqual((code, self.codes(out)), (1, ["MODEL_CELL_UNBOUND"]), out)

    def test_an_empty_cell_and_a_custom_cell_are_skipped(self):
        files = {APP + "Cases/settings.xml": entity(),
                 APP + "Cases/_forms/edit/_form.xml": form("<cell/>", '<cell name="control_x"><content>x</content></cell>')}
        code, out, _ = self.run_on(files, APP + "Cases/_forms/edit/_form.xml")
        self.assertEqual((code, self.codes(out)), (0, []), out)

    def test_a_field_name_is_matched_exactly(self):
        files = {APP + "Cases/settings.xml": entity(),
                 APP + "Cases/_forms/edit/_form.xml": form('<cell name="id"/>')}
        code, out, _ = self.run_on(files, APP + "Cases/_forms/edit/_form.xml")
        self.assertEqual(self.codes(out), ["MODEL_CELL_UNBOUND"], out)

    # --- not run, skipped edges, malformed files -------------------------------------

    def test_relation_and_datasource_are_not_run(self):
        code, out, _ = self.run_on({}, APP + "Status/settings.xml")
        self.assertEqual(code, 0, out)
        self.assertIn("NOT RUN: relation-table (a relation's table is a database object outside the root)", out)
        self.assertIn("NOT RUN: entity-datasource", out)

    def test_a_malformed_settings_file_is_xml_malformed(self):
        code, out, _ = self.run_on({APP + "Cases/settings.xml": "<entity><fields>"}, APP + "Cases/settings.xml")
        self.assertEqual((code, self.codes(out)), (1, ["XML_MALFORMED"]), out)

    # --- the entity's own load --------------------------------------------------------

    def test_an_entity_table_init_fields_throws_on_blocks(self):
        """TableManager.LoadAsync calls Table.InitFields, which throws on each of these (data-model.md §1)."""
        cases = {
            "NoKey": '<entity><fields><field name="Id" type="PrimaryKey"/></fields></entity>\n',
            "Unknown": '<entity><primarykey>Nope</primarykey><fields><field name="Id"/></fields></entity>\n',
            "Twice": entity('<field name="Id" type="Text"/>'),
            "Nameless": entity('<field type="Text"/>'),
        }
        for name, body in cases.items():
            code, out, _ = self.run_on({APP + f"{name}/settings.xml": body}, APP + f"{name}/settings.xml")
            self.assertEqual((code, self.codes(out)), (1, ["MODEL_ENTITY_UNLOADABLE"]), f"{name}\n{out}")
            self.assertIn("CHECKS RUN: model-references, entity-load", out)

    def test_an_entity_that_loads_is_clean_and_says_the_check_ran(self):
        code, out, _ = self.run_on({}, APP + "Status/settings.xml")
        self.assertEqual((code, self.codes(out)), (0, []), out)
        self.assertIn("CHECKS RUN: model-references, entity-load", out)

    def test_an_entity_key_is_the_first_primarykey_as_xml_serializer_reads_it(self):
        """The first `<primarykey>` binds, without a text node of whitespace alone outside xml:space="preserve" and
        in no namespace; a CDATA section stays, and so does a decimal character reference (data-model.md §1)."""
        def body(key, *names):
            fields = "".join(f'<field name="{name}" type="Text"/>' for name in names)
            return f"<entity>{key}<fields>{fields}</fields></entity>\n"
        cases = {
            "FirstOfTwo": (body("<primarykey>Id</primarykey><primarykey>Name</primarykey>", "Id", "Name"), 0),
            "EmptyFirst": (body("<primarykey/><primarykey>Id</primarykey>", "Id"), 1),
            "Cdata": (body("<primarykey>\n  <![CDATA[Id]]>\n</primarykey>", "Id"), 0),
            "Commented": (body("<primarykey> <!-- the key -->Id</primarykey>", "Id"), 0),
            "Blank": (body("<primarykey> </primarykey>", " "), 1),
            "Preserved": (body('<primarykey xml:space="preserve"> </primarykey>', " "), 0),
            "DecimalRef": (body("<primarykey>&#32;</primarykey>", " "), 0),
            "HexRef": (body("<primarykey>&#x20;</primarykey>", " "), 1),
            "Namespaced": (body('<primarykey xmlns="urn:x">Id</primarykey>', "Id"), 1),
            "PaddedPreserve": (body('<primarykey xml:space=" preserve "> </primarykey>', " "), 0),
            "Composite": (body("<primarykey>Id,Code</primarykey>", "Id", "Code"), 0),
        }
        for name, (xml, exit_code) in cases.items():
            code, out, _ = self.run_on({APP + f"{name}/settings.xml": xml}, APP + f"{name}/settings.xml")
            expected = ["MODEL_ENTITY_UNLOADABLE"] if exit_code else []
            self.assertEqual((code, self.codes(out)), (exit_code, expected), f"{name}\n{out}")

    def test_an_entity_with_a_dtd_is_not_checked_for_its_load_and_says_so(self):
        body = '<!DOCTYPE entity>\n<entity><fields><field name="Id"/></fields></entity>\n'
        code, out, _ = self.run_on({APP + "Dtd/settings.xml": body}, APP + "Dtd/settings.xml")
        self.assertNotIn("MODEL_ENTITY_UNLOADABLE", self.codes(out), out)
        self.assertIn("NOT RUN: entity-load (the file holds a DTD, which this check does not read)", out)

    def test_an_entity_whose_text_does_not_parse_as_the_runtime_decodes_it_says_so(self):
        """UTF-16 with no byte-order mark: lxml reads it by its declaration, the runtime as UTF-8 — NULs."""
        body = ("<?xml version='1.0' encoding='UTF-16'?><entity><primarykey>Id</primarykey><fields>"
                "<field name='Id'/></fields></entity>").encode("utf-16-le")
        root = helpers.make_root(self.tmp, self.files)
        path = root / APP / "Utf16/settings.xml"
        path.parent.mkdir(parents=True)
        path.write_bytes(body)
        code, out, _ = helpers.run_cli("validate_model.py", "--workspaces-root", str(root / "ws"), str(path))
        self.assertNotIn("MODEL_ENTITY_UNLOADABLE", self.codes(out), out)
        self.assertIn("NOT RUN: entity-load (the file does not parse once decoded as the runtime decodes it", out)

    def test_a_table_that_declares_an_encoding_python_does_not_know_is_read_as_the_runtime_reads_it(self):
        """The runtime ignores the declaration: the table's view is generated from its text, and nothing raises."""
        odd = ("<?xml version='1.0' encoding='bogus-enc'?><entity><primarykey>Id</primarykey><fields>"
               "<field name='Id' type='PrimaryKey'/><field name='Name' type='Text'/></fields></entity>\n")
        code, out, err = self.run_on({APP + "Odd/settings.xml": odd,
                                      APP + "Cases/settings.xml": entity(lookup("S", table="Odd", view="short"))},
                                     APP + "Cases/settings.xml")
        self.assertEqual((code, self.codes(out)), (2, ["MODEL_REFERENCE_TEMPLATED"]), out + err)

    def test_a_file_declared_latin1_is_loaded_as_the_runtime_decodes_it_as_utf8(self):
        """`é` and `è` are both U+FFFD to the runtime: the key names the one field, and two fields become one name."""
        cases = {
            "Pair": (b"<primarykey>Id\xe9</primarykey><fields><field name='Id\xe8' type='Text'/></fields>", 0, []),
            "Twins": (b"<primarykey>A\xe9</primarykey><fields><field name='A\xe9' type='Text'/>"
                      b"<field name='A\xe8' type='Text'/></fields>", 1, ["MODEL_ENTITY_UNLOADABLE"]),
        }
        root = helpers.make_root(self.tmp, self.files)
        for name, (body, exit_code, codes) in cases.items():
            path = root / APP / name / "settings.xml"
            path.parent.mkdir(parents=True)
            path.write_bytes(b"<?xml version='1.0' encoding='ISO-8859-1'?><entity>" + body + b"</entity>")
            code, out, _ = helpers.run_cli("validate_model.py", "--workspaces-root", str(root / "ws"), str(path))
            self.assertEqual((code, self.codes(out)), (exit_code, codes), f"{name}\n{out}")

    def test_a_file_that_is_neither_is_a_usage_error(self):
        code, out, _ = self.run_on({"ws/a/FM/_PROCESS/P/process.xml": "<Process/>"}, "ws/a/FM/_PROCESS/P/process.xml")
        self.assertEqual((code, self.codes(out)), (3, ["SCHEMA_UNSELECTABLE"]), out)

    # --- the command line ----------------------------------------------------------

    def test_all_checks_every_settings_and_form(self):
        files = {APP + "Cases/settings.xml": entity(lookup("S", table="Nowhere")),
                 APP + "Cases/_forms/edit/_form.xml": form('<cell name="Id"/>'),
                 "ws/a/FM/_COMPONENTS/Page/p.json": "{}"}
        code, out, _ = self.run_on(files)
        self.assertEqual(code, 1, out)
        self.assertEqual(out.count("FAMILY: "), 3, out)

    def test_all_needs_a_root_and_takes_no_files(self):
        root = helpers.make_root(self.tmp, self.files)
        self.assertEqual(helpers.run_cli("validate_model.py", "--all")[0], 3)
        self.assertEqual(helpers.run_cli("validate_model.py", "--workspaces-root", str(root / "ws"), "--all",
                                         str(root / APP / "Status/settings.xml"))[0], 3)
        self.assertEqual(helpers.run_cli("validate_model.py")[0], 3)


class SkippedEdges(unittest.TestCase):
    """A `skipped` edge is never reported, whatever its target does (reference-graph.md §1)."""

    @unittest.skipUnless(helpers.have_dependencies(), "lxml / jsonschema not installed")
    def test_a_skipped_edge_is_never_reported(self):
        from lib import knowledge
        import validate_model
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        shutil.copytree(helpers.PLUGIN_ROOT / "knowledge", tmp / "knowledge", ignore=shutil.ignore_patterns("schemas"))
        graph = tmp / "knowledge/reference-graph.md"
        graph.write_text(graph.read_text(encoding="utf-8").replace(
            "| `extract-table` | `settings` | `field/extract` | `table` | — | `settings` | `table-name` | `throws` |",
            "| `extract-table` | `settings` | `field/extract` | `table` | — | `settings` | `table-name` | `skipped` |"),
            encoding="utf-8")
        root = helpers.make_root(tmp, {"ws/webasm/FM/.keep": "",
                                       APP + "Cases/settings.xml": entity(lookup("S", table="Nowhere"))})
        saved = knowledge.KNOWLEDGE_DIR
        knowledge.KNOWLEDGE_DIR = tmp / "knowledge"
        knowledge._CACHE.clear()
        try:
            rep = validate_model.check_file(root / APP / "Cases/settings.xml", root / "ws")
        finally:
            knowledge.KNOWLEDGE_DIR = saved
            knowledge._CACHE.clear()
        self.assertEqual([f.code for f in rep.findings], [])


class Dependencies(unittest.TestCase):
    def test_without_lxml_it_exits_3(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        root = helpers.make_root(tmp, {APP + "Cases/settings.xml": entity()})
        code, _, err = helpers.run_cli_blocking("validate_model.py", str(root / APP / "Cases/settings.xml"))
        self.assertEqual(code, 3, err)


if __name__ == "__main__":
    unittest.main()
