"""The runtime-faithful JSON validator in scripts/lib/json_validate.py."""

import json
import unittest

from tests import helpers

FIXTURES = helpers.FIXTURES / "unit" / "json"
WS = "/root/app/FM/_COMPONENTS/"


@unittest.skipUnless(helpers.have_dependencies(), "lxml / jsonschema not installed")
class Validate(unittest.TestCase):
    def check(self, fixture, where):
        from lib import json_reader, json_resolve, json_validate, report
        document = json_reader.load(FIXTURES / fixture)
        rep = report.Report(fixture, "json")
        json_validate.validate(document, json_resolve.select(WS + where, document), rep)
        return rep

    def codes(self, rep):
        return [f.code for f in rep.findings]

    def test_case_folded_keys_enum_names_and_widened_boolean_pass(self):
        rep = self.check("page-case-folded.json", "Page/home.json")
        self.assertEqual(self.codes(rep), [], [f.message for f in rep.findings])
        self.assertIn("json-schema", rep.checks_run)
        self.assertIn(("json-format", "annotation-only, ADR 0015"), rep.not_run)

    def test_keys_differing_only_in_case_fail(self):
        rep = self.check("case-duplicate-keys.json", "Page/p.json")
        self.assertEqual(self.codes(rep), ["SCHEMA_INVALID"])
        self.assertIn("differ only in case", rep.findings[0].message)

    def test_error_two_levels_down_through_dispatch(self):
        rep = self.check("nested-dispatch-error.json", "Template/s.json")
        self.assertEqual(self.codes(rep), ["SCHEMA_INVALID"])
        self.assertIn("$.content[0].content[0].cols", rep.findings[0].message)

    def test_unknown_nested_type(self):
        rep = self.check("unknown-nested-type.json", "Page/p.json")
        self.assertEqual(self.codes(rep), ["UNKNOWN_COMPONENT"])
        self.assertIn("$.content[0]", rep.findings[0].message)

    def test_unknown_datasource_discriminator(self):
        rep = self.check("datasource-unknown-discriminator.json", "DataSource/people.json")
        self.assertEqual(self.codes(rep), ["UNKNOWN_DISCRIMINATOR"])

    def test_custom_enum_name_is_read_exactly(self):
        self.assertEqual(self.codes(self.check("link-custom-enum-name.json", "Link/l.json")), [])
        self.assertEqual(self.codes(self.check("link-csharp-enum-name.json", "Link/l.json")), ["SCHEMA_INVALID"])

    def test_unknown_property_is_a_warning(self):
        rep = self.check("unknown-property.json", "Text/t.json")
        self.assertEqual(self.codes(rep), ["UNKNOWN_PROPERTY"])
        self.assertEqual(rep.exit_code(), 2)

    def test_wrong_case_type_key_is_invalid(self):
        self.assertEqual(self.codes(self.check("type-key-wrong-case.json", "Text/t.json")), ["SCHEMA_INVALID"])

    def test_generic_number_members_read_numbers(self):
        self.assertEqual(self.codes(self.check("number-generic.json", "Number/n.json")), [])

    def test_metadata_datasources_dispatch(self):
        rep = self.check("metadata-datasource.json", "Text/t.json")
        self.assertEqual(self.codes(rep), ["UNKNOWN_DISCRIMINATOR"])
        self.assertIn("$.metaData.dataSources.people", rep.findings[0].message)

    def test_number_written_as_a_string_is_invalid(self):
        self.assertEqual(self.codes(self.check("number-as-string.json", "Text/t.json")), ["SCHEMA_INVALID"])

    def test_no_schema_selection_validates_nothing(self):
        from lib import json_resolve, json_validate, report
        rep = report.Report("sitemap.json", "json")
        document = json.loads('{"routes": {}}')
        json_validate.validate(document, json_resolve.select(WS + "sitemap.json", document), rep)
        self.assertEqual([f.code for f in rep.findings], ["NO_SCHEMA"])
        self.assertNotIn("json-schema", rep.checks_run)


if __name__ == "__main__":
    unittest.main()
