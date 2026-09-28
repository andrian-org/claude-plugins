"""The machine-read table loader in scripts/lib/knowledge.py."""

import shutil
import tempfile
import unittest
from pathlib import Path

from tests import helpers
from lib import knowledge

EXPECTED_ROWS = {
    "legacy-artifacts": 8,
    "code-places": 4,
    "component-classes": 67,
    "datasource-discriminators": 9,
    "component-folders": 6,
    "enum-member-names": 4,
    "layout-components": 8,
    "dispatchable": 34,
    "correspondence": 7,
    "parity": 67,
    "process-divergence": 26,
    "reference-edges": 21,
    "run-time-names": 3,
    "role-sources": 6,
}


class RealTables(unittest.TestCase):
    def test_every_declared_table_loads(self):
        tables = knowledge.load_all()
        self.assertEqual(set(tables), set(knowledge.TABLES))
        for table_id, rows in tables.items():
            self.assertEqual(len(rows), EXPECTED_ROWS[table_id], table_id)

    def test_backticks_are_stripped(self):
        row = knowledge.index("component-classes")["Date"]
        self.assertEqual(row["Configuration schema"], "DatePickerConfiguration.schema.json")
        self.assertEqual(knowledge.index("component-classes")["Search"]["Configuration schema"], knowledge.NONE)

    def test_code_places_are_keyed_by_place(self):
        places = knowledge.index("code-places")
        self.assertEqual(set(places), {"form-script", "global-script", "global-script-base", "global-style"})
        self.assertEqual(places["form-script"]["Filename"], "_form.js")
        self.assertEqual(places["form-script"]["New file loaded"], "yes")
        self.assertEqual(places["global-style"]["Extension"], ".css")
        for place in ("global-script", "global-script-base", "global-style"):
            self.assertEqual(places[place]["Filename"], knowledge.NONE, place)
            self.assertEqual(places[place]["New file loaded"], "no", place)


class ReferenceEdges(unittest.TestCase):
    """The reference-edges table and its cell grammar (knowledge/README.md §7)."""

    def test_values_split_alternatives_and_keep_a_composite_whole(self):
        self.assertEqual(knowledge.values("action expiredaction postviewaction"),
                         ["action", "expiredaction", "postviewaction"])
        self.assertEqual(knowledge.values("table+form"), ["table+form"])
        self.assertEqual(knowledge.parts("table+form"), ["table", "form"])
        self.assertEqual(knowledge.values(knowledge.NONE), [])

    def test_a_multi_valued_cell_loses_only_its_outer_backticks(self):
        row = knowledge.index("reference-edges")["record-table"]
        self.assertEqual(knowledge.values(row["Element"]), ["UpdateRecord/Settings", "CreateRecord/Settings"])
        self.assertEqual(knowledge.values(knowledge.index("reference-edges")["form-table"]["Attribute"]), [])

    def test_every_rule_takes_as_many_parts_as_each_alternative_passes(self):
        for row in knowledge.edges():
            for value in knowledge.values(row["Attribute"]) or [""]:
                count = len(knowledge.parts(value)) if value else 0
                self.assertEqual(count, knowledge.RESOLVES_AS[row["Resolves as"]], row["Edge"])

    def test_every_checked_by_names_a_script(self):
        for row in knowledge.edges():
            if row["Checked by"] != knowledge.NONE:
                self.assertTrue((helpers.SCRIPTS / row["Checked by"]).is_file(), row["Edge"])

    def test_the_run_time_names_replace_attributes_their_steps_have(self):
        steps = {row["Name"]: (row["Step"], row["Replaces"]) for row in knowledge.load("run-time-names")}
        self.assertEqual(steps, {"_WORKFLOWNAME_": ("SubWorkflow", "workflow"), "_TABLENAME_": ("Invoke", "table"),
                                 "_FORMNAME_": ("Invoke", "form")})


class RoleSources(unittest.TestCase):
    def test_the_sitemap_sources_split_on_a_comma_and_the_others_do_not(self):
        sources = knowledge.index("role-sources")
        self.assertEqual({name for name, row in sources.items() if row["Separator"] == ","},
                         {"sitemap-roles", "sitemap-deny"})
        self.assertEqual(sources["sitemap-roles"]["File"], "_application.sitemap")
        self.assertEqual(sources["profile-group"]["Element"], "(folder)")

    def test_a_separator_outside_the_allowed_set_is_malformed(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        shutil.copytree(helpers.PLUGIN_ROOT / "knowledge", tmp / "k", ignore=shutil.ignore_patterns("schemas"))
        path = tmp / "k" / "permissions.md"
        path.write_text(path.read_text(encoding="utf-8").replace("| `roles` | `,` |", "| `roles` | `;` |", 1),
                        encoding="utf-8")
        with self.assertRaises(knowledge.KnowledgeTableError) as ctx:
            knowledge.load("role-sources", tmp / "k")
        self.assertIn("Separator `;`", str(ctx.exception))


class MalformedTables(unittest.TestCase):
    """Each fault is planted in a temporary copy of knowledge/, never the real one."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.dir = Path(self.tmp) / "knowledge"
        shutil.copytree(helpers.PLUGIN_ROOT / "knowledge", self.dir,
                        ignore=shutil.ignore_patterns("schemas"))
        knowledge._CACHE.clear()
        self.addCleanup(knowledge._CACHE.clear)

    def mutate(self, filename, old, new):
        path = self.dir / filename
        text = path.read_text(encoding="utf-8")
        self.assertIn(old, text)
        path.write_text(text.replace(old, new, 1), encoding="utf-8")

    def assert_malformed(self, table_id, fragment):
        with self.assertRaises(knowledge.KnowledgeTableError) as ctx:
            knowledge.load(table_id, self.dir)
        self.assertIn(fragment, str(ctx.exception))

    def test_missing_marker(self):
        self.mutate("schema-families.md", "<!-- machine-read: parity -->", "")
        self.assert_malformed("parity", "marker not found")

    def test_wrong_header(self):
        self.mutate("json-reader.md", "| Discriminator | Schema |", "| Discriminator | Schema file |")
        self.assert_malformed("datasource-discriminators", "header is")

    def test_duplicate_key(self):
        self.mutate("json-reader.md", "| `LookupTable` |", "| `Table` |")
        self.assert_malformed("datasource-discriminators", "duplicate key `Table`")

    def test_value_outside_the_allowed_set(self):
        self.mutate("process-model.md", "| `Process/@hideDesc` | attribute |", "| `Process/@hideDesc` | attr |")
        self.assert_malformed("process-divergence", "Kind `attr`")

    def test_marker_inside_a_code_fence_is_not_a_table(self):
        self.mutate("schema-families.md", "<!-- machine-read: parity -->", "```\n<!-- machine-read: parity -->\n```")
        self.assert_malformed("parity", "marker not found")

    def test_code_places_renamed_header(self):
        self.mutate("composition-specs.md", "| Place | Path | Filename |", "| Place | Folder | Filename |")
        self.assert_malformed("code-places", "header is")

    def test_code_places_new_file_loaded_is_lower_case(self):
        self.mutate("composition-specs.md", "`_form.xml` | yes |", "`_form.xml` | Yes |")
        self.assert_malformed("code-places", "New file loaded `Yes`")

    def test_unknown_table_id(self):
        self.assert_malformed("no-such-table", "unknown table id")

    def test_a_row_missing_its_closing_pipe_is_malformed_not_the_end(self):
        path = self.dir / "schema-families.md"
        lines = path.read_text(encoding="utf-8").splitlines()
        index = next(i for i, line in enumerate(lines) if line.startswith("| 19 | Form"))
        lines[index] = lines[index].rstrip().rstrip("|")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.assert_malformed("parity", "is not a `| … |` row")

    def test_an_edge_value_outside_the_allowed_set(self):
        for column, old, new in (("Reach", "| `follow` | `validate_process.py` |", "| `walk` | `validate_process.py` |"),
                                 ("When absent", "| `throws` | `unknown` | `follow` |", "| `explodes` | `unknown` | `follow` |"),
                                 ("When empty", "| `throws` | `throws` | `none` |", "| `throws` | `sometimes` | `none` |"),
                                 ("From", "| `sub-workflow` | `workflow` |", "| `sub-workflow` | `flow` |"),
                                 ("To", "| `control-form` | `settings` |", "| `control-form` | `entity` |"),
                                 ("Condition", "| `control-form` |", "| `control-FORM` |"),
                                 ("Checked by", "| `validate_model.py` |", "| `validate_models.py` |"),
                                 ("Resolves as", "| `table-name` |", "| `table-by-name` |")):
            with self.subTest(column=column):
                knowledge._CACHE.clear()
                self.setUp()
                self.mutate("reference-graph.md", old, new)
                self.assert_malformed("reference-edges", f"{column} `")

    def test_an_edge_whose_parts_do_not_match_its_rule_is_malformed(self):
        self.mutate("reference-graph.md", "| `table+view` | — | `lookup-view` |", "| `view` | — | `lookup-view` |")
        self.assert_malformed("reference-edges", "edge `extract-view`: Attribute `view` passes [1] part(s), but "
                                                 "`lookup-view` takes 2")

    def test_a_malformed_edge_row_is_malformed(self):
        self.mutate("reference-graph.md", "| `sub-workflow` | `workflow` |", "| `sub-workflow` |")
        self.assert_malformed("reference-edges", "cells, expected 11")

    def test_a_file_that_is_not_utf8_is_malformed_not_a_crash(self):
        path = self.dir / "composition-specs.md"
        path.write_bytes(path.read_bytes().replace("—".encode(), b"\x97", 1))
        self.assert_malformed("legacy-artifacts", "is not UTF-8")


if __name__ == "__main__":
    unittest.main()
