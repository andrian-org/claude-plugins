"""Schema selection for a component JSON file (DD6) in scripts/lib/json_resolve.py."""

import unittest

from tests import helpers  # noqa: F401 — puts scripts/ on sys.path
from lib import json_resolve

WS = "/root/app/FM/_COMPONENTS/"


def codes(selection):
    return [code for code, _ in selection.findings]


class Tables(unittest.TestCase):
    def test_index_mirrors_schema_index_service(self):
        found = json_resolve.index()
        self.assertEqual(len(found), 58)
        self.assertEqual(found["page"], "PageConfiguration.schema.json")
        self.assertEqual(found["componentvalidator"], "componentValidator.schema.json")
        self.assertNotIn("tabledatasource", found)

    def test_class_for_prefix_and_name(self):
        self.assertEqual(json_resolve.class_for("Date"), ("DatePickerConfiguration.schema.json", "prefix"))
        self.assertEqual(json_resolve.class_for("Page"), ("PageConfiguration.schema.json", "name"))
        self.assertEqual(json_resolve.class_for("Search"), (None, "none"))

    def test_member_parsing_is_case_insensitive_and_trimmed(self):
        self.assertEqual(json_resolve.component_member(" dataTable "), "DataTable")
        self.assertIsNone(json_resolve.component_member("dataTabel"))

    def test_datasource_discriminators(self):
        self.assertEqual(json_resolve.datasource_for("rawsql"), ("RawSql", "RawSqlDataSource.schema.json"))
        self.assertEqual(json_resolve.datasource_for("StoredProcedure")[1], "RawSqlDataSource.schema.json")
        self.assertIsNone(json_resolve.datasource_for("None"))

    def test_generic_parameter_is_a_number(self):
        self.assertEqual(json_resolve.merged_schema("NumberConfiguration.schema.json")["definitions"]["T"],
                         {"type": "number"})

    def test_custom_enum_names_are_annotated(self):
        target = json_resolve.merged_schema("LinkConfiguration.schema.json")["definitions"]["LinkTarget"]
        self.assertEqual(target[json_resolve.JSON_NAMES_KEY]["Blank"], "_blank")


class Folders(unittest.TestCase):
    def test_type_folder_uses_the_type(self):
        sel = json_resolve.select(WS + "Page/home.json", {"type": "page"})
        self.assertEqual((sel.kind, sel.schema), ("component", "PageConfiguration.schema.json"))
        self.assertEqual(codes(sel), [])

    def test_type_folder_mismatch(self):
        sel = json_resolve.select(WS + "Page/home.json", {"type": "text"})
        self.assertEqual(sel.schema, "TextConfiguration.schema.json")
        self.assertEqual(codes(sel), ["TYPE_FOLDER_MISMATCH"])

    def test_template_is_typed_by_its_own_type(self):
        sel = json_resolve.select(WS + "Template/Eligibility/row.json", {"type": "row"})
        self.assertEqual((sel.kind, sel.schema, codes(sel)), ("component", "RowConfig.schema.json", []))

    def test_datasource_folder_uses_the_discriminator(self):
        sel = json_resolve.select(WS + "DataSource/people.json", {"type": "Table"})
        self.assertEqual((sel.kind, sel.schema), ("datasource", "TableDataSource.schema.json"))

    def test_endpoints_have_no_schema(self):
        sel = json_resolve.select(WS + "Endpoints/api.json", {"baseUrl": "x"})
        self.assertEqual((sel.kind, codes(sel)), ("none", ["NO_SCHEMA"]))

    def test_root_file_is_a_site_map(self):
        sel = json_resolve.select(WS + "sitemap.json", {"routes": {}})
        self.assertEqual((sel.kind, codes(sel)), ("none", ["NO_SCHEMA"]))
        self.assertIn("site map", sel.findings[0][1])

    def test_forms_folder_is_read_by_no_loader(self):
        sel = json_resolve.select(WS + "Forms/Calendar/add.json", {"type": "form"})
        self.assertEqual((sel.kind, codes(sel)), ("none", ["NO_SCHEMA"]))
        self.assertIn("read by no loader", sel.findings[0][1])

    def test_folder_in_the_wrong_case_is_unreferenced(self):
        sel = json_resolve.select(WS + "page/home.json", {"type": "page"})
        self.assertIn("differs in case", sel.findings[0][1])

    def test_wrong_case_type_key_still_selects_but_is_invalid(self):
        sel = json_resolve.select(WS + "Page/home.json", {"Type": "page"})
        self.assertEqual(sel.schema, "PageConfiguration.schema.json")
        self.assertEqual(codes(sel), ["SCHEMA_INVALID"])


class OutsideComponents(unittest.TestCase):
    def test_type_decides(self):
        sel = json_resolve.select("/tmp/x.json", {"type": "DataTable"})
        self.assertEqual(sel.schema, "DataTableConfiguration.schema.json")

    def test_datasource_type_outside_components(self):
        sel = json_resolve.select("/tmp/x.json", {"type": "Api"})
        self.assertEqual((sel.kind, sel.schema), ("datasource", "ApiDataSource.schema.json"))

    def test_nothing_to_go_on_is_unselectable(self):
        sel = json_resolve.select("/tmp/x.json", {"name": "x"})
        self.assertEqual((sel.kind, codes(sel)), ("unselectable", ["SCHEMA_UNSELECTABLE"]))

    def test_override_wins(self):
        sel = json_resolve.select("/tmp/x.json", {"type": "page"}, override="Form")
        self.assertEqual(sel.schema, "FormConfiguration.schema.json")

    def test_unknown_override_is_unselectable(self):
        sel = json_resolve.select("/tmp/x.json", {"type": "page"}, override="Nope")
        self.assertEqual(codes(sel), ["SCHEMA_UNSELECTABLE"])

    def test_legal_type_without_a_class(self):
        sel = json_resolve.select("/tmp/x.json", {"type": "Search"})
        self.assertEqual((sel.kind, codes(sel)), ("interface", ["NO_CONFIG_CLASS"]))


if __name__ == "__main__":
    unittest.main()
