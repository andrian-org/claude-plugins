"""The machine-read table loader in scripts/lib/knowledge.py."""

import shutil
import tempfile
import unittest
from pathlib import Path

from tests import helpers
from lib import knowledge

EXPECTED_ROWS = {
    "legacy-artifacts": 8,
    "component-classes": 67,
    "datasource-discriminators": 9,
    "component-folders": 6,
    "enum-member-names": 4,
    "layout-components": 8,
    "dispatchable": 34,
    "correspondence": 7,
    "parity": 67,
    "process-divergence": 26,
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

    def test_unknown_table_id(self):
        self.assert_malformed("no-such-table", "unknown table id")


if __name__ == "__main__":
    unittest.main()
