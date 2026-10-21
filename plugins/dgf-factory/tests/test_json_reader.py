"""The runtime-faithful JSON parse step in scripts/lib/json_reader.py."""

import unittest

from tests import helpers  # noqa: F401 — puts scripts/ on sys.path
from lib import json_reader


class Comments(unittest.TestCase):
    def test_line_and_block_comments_are_skipped(self):
        value = json_reader.parse_text('{\n  // a note\n  "a": 1, /* inline */ "b": 2\n}')
        self.assertEqual(value, {"a": 1, "b": 2})

    def test_comment_markers_inside_strings_survive(self):
        value = json_reader.parse_text('{"url": "http://x/y", "c": "/* not a comment */", "d": "a\\"//b"}')
        self.assertEqual(value["url"], "http://x/y")
        self.assertEqual(value["c"], "/* not a comment */")
        self.assertEqual(value["d"], 'a"//b')

    def test_positions_are_preserved_after_a_multiline_block(self):
        text = '{\n/* one\n   two\n   three */\n  "a": 1,\n  "b": ,\n}'
        with self.assertRaises(json_reader.JsonParseError) as ctx:
            json_reader.parse_text(text)
        self.assertEqual(ctx.exception.line, 6)

    def test_stripped_text_keeps_every_newline(self):
        text = '{ /* a\nb */ "k": 1 // c\n}'
        stripped, count = json_reader.strip_comments(text)
        self.assertEqual(count, 2)
        self.assertEqual(stripped.count("\n"), text.count("\n"))
        self.assertEqual(len(stripped), len(text))

    def test_unterminated_block_comment_fails(self):
        with self.assertRaises(json_reader.JsonParseError):
            json_reader.parse_text('{"a": 1 /* never closed }')


class Strictness(unittest.TestCase):
    def test_trailing_comma_fails(self):
        with self.assertRaises(json_reader.JsonParseError):
            json_reader.parse_text('{"a": 1,}')

    def test_nan_and_infinity_fail(self):
        for text in ('{"a": NaN}', '{"a": Infinity}', '{"a": -Infinity}'):
            with self.assertRaises(json_reader.JsonParseError, msg=text):
                json_reader.parse_text(text)

    def test_one_utf8_bom_is_ignored(self):
        self.assertEqual(json_reader.parse_bytes(b'\xef\xbb\xbf{"a": 1}'), {"a": 1})

    def test_utf16_is_not_utf8(self):
        with self.assertRaises(json_reader.JsonParseError):
            json_reader.parse_bytes('{"a": 1}'.encode("utf-16"))


class CaseDuplicates(unittest.TestCase):
    def test_keys_differing_only_in_case_are_recorded(self):
        value = json_reader.parse_text('{"name": "a", "Name": "b", "other": 1}')
        self.assertEqual(value.case_duplicates, ["name", "Name"])

    def test_exact_duplicates_are_recorded_too(self):
        value = json_reader.parse_text('{"a": 1, "a": 2}')
        self.assertEqual(value.case_duplicates, ["a"])

    def test_distinct_keys_are_clean(self):
        self.assertEqual(json_reader.parse_text('{"a": {"b": 1}}')["a"].case_duplicates, [])

    def test_folded_lookup(self):
        value = json_reader.parse_text('{"Type": "page"}')
        self.assertEqual(value.get_folded("type"), ("Type", "page"))


if __name__ == "__main__":
    unittest.main()
