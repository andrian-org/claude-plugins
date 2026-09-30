"""tools/derive_sql_types.py: the SQL type of each dbtype, tallied from settings/table pairs (data-model.md §6.3)."""

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests import helpers

TOOL = helpers.PLUGIN_ROOT / "tools" / "derive_sql_types.py"
FIXTURE = helpers.PLUGIN_ROOT / "tests" / "fixtures" / "unit" / "sql-types"


def load_tool():
    spec = importlib.util.spec_from_file_location("derive_sql_types", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(*args):
    return subprocess.run([sys.executable, str(TOOL), *args], capture_output=True, text=True)


class Tally(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tool = load_tool()
        cls.tally, cls.pairs = cls.tool.collect(FIXTURE)

    def test_only_exact_case_pairs_count(self):
        # Alpha and Beta pair; Gamma has no script, and Delta's script differs from its folder in case only
        self.assertEqual(self.pairs, 2)

    def test_the_majority_and_a_counted_alternative(self):
        counts = self.tally[("String", "size")]
        self.assertEqual(counts["VARCHAR(size)"], 3)
        self.assertEqual(counts["NVARCHAR(size)"], 1)
        self.assertEqual(counts.most_common(1)[0][0], "VARCHAR(size)")

    def test_a_max_column_with_the_max_size_is_the_size_rule(self):
        # Note is size 2147483647 on VARCHAR(MAX): the same rule as VARCHAR(50), not a rule of its own
        self.assertNotIn(("String", "max"), self.tally)
        self.assertNotIn(("String", "fixed"), self.tally)

    def test_a_unicode_string_is_its_own_dbtype(self):
        self.assertEqual(dict(self.tally[("StringUnicode", "size")]), {"NVARCHAR(size)": 1})

    def test_a_decimal_keeps_its_precision_and_scale(self):
        self.assertEqual(dict(self.tally[("Decimal", "precision")]), {"DECIMAL(18,2)": 1})

    def test_a_column_with_no_length_is_the_none_rule(self):
        self.assertEqual(dict(self.tally[("Int32", "none")]), {"INT": 1})

    def test_a_computed_column_is_skipped(self):
        columns = self.tool.table_columns(FIXTURE / "src/samples/Database/dbo/Tables/Alpha.sql")
        self.assertNotIn("calc", columns)
        self.assertEqual(columns["amount"], ("DECIMAL", "18,2"))

    def test_a_field_with_no_column_is_skipped(self):
        self.assertEqual(sum(sum(c.values()) for c in self.tally.values()), 7)  # 9 fields, minus Missing and Calc


class Cli(unittest.TestCase):
    def test_prints_the_tally_and_exits_0(self):
        done = run(str(FIXTURE))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("PAIRS: 2", done.stdout)
        self.assertIn("TYPE: String | size | VARCHAR(size) | 3/4 | NVARCHAR(size) 1/4", done.stdout)

    def test_a_folder_that_is_not_a_dgf_root_is_a_usage_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            done = run(tmp)
        self.assertEqual(done.returncode, 3)
        self.assertIn("not a DGF root", done.stderr)

    def test_a_root_with_no_pair_is_a_usage_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "src" / "samples").mkdir(parents=True)
            done = run(tmp)
        self.assertEqual(done.returncode, 3)
        self.assertIn("no settings/table pair", done.stderr)

    def test_verbose_traces_each_pair_to_stderr(self):
        done = run(str(FIXTURE), "--verbose")
        self.assertIn("[derive_sql_types.pair] matched", done.stderr)
        self.assertIn("[derive_sql_types.pair] computed", done.stderr)
        self.assertIn("[derive_sql_types.pair] no-column", done.stderr)


if __name__ == "__main__":
    unittest.main()
