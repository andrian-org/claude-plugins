"""scripts/route_means.py: one test per rule of ADR 0010 §1's order of means."""

import unittest

from tests import helpers


def route(name):
    code, out, err = helpers.run_cli("route_means.py", name)
    lines = [line for line in out.splitlines() if line.startswith("ROUTE: ")]
    return code, (lines[0] if lines else None), out + err


class RouteMeans(unittest.TestCase):
    def test_rule_1_a_legacy_type_stays_xml_form_included(self):
        code, line, out = route("Form")
        self.assertEqual(code, 0, out)
        self.assertTrue(line.startswith("ROUTE: xml <workspace>/FM/_DATA/<table>/_forms/<form>/_form.xml — "), out)
        self.assertIn("parity row 19 is ◐", line)

    def test_rule_1_workflow_is_a_legacy_type(self):
        code, line, out = route("Workflow")
        self.assertEqual(code, 0, out)
        self.assertIn("ROUTE: xml <workspace>/FM/_WORKFLOW/<workflow>/_workflow.xml", line)

    def test_rule_1_any_case(self):
        code, line, out = route("PROCESS")
        self.assertEqual(code, 0, out)
        self.assertIn("/FM/_PROCESS/<process>/process.xml", line)

    def test_rule_2_not_runtime_is_xml_at_the_counterpart_artifact(self):
        code, line, out = route("ProcessFlow")
        self.assertEqual(code, 0, out)
        self.assertTrue(line.startswith("ROUTE: xml <workspace>/FM/_PROCESS/<process>/process.xml — parity row 34 is ✗"),
                        out)

    def test_rule_3_supported_is_json(self):
        code, line, out = route("dataTable")
        self.assertEqual(code, 0, out)
        self.assertTrue(line.startswith("ROUTE: json <workspace>/FM/_COMPONENTS/DataTable/<name>.json — "), out)

    def test_rule_4_partial_is_json_with_a_warning(self):
        code, line, out = route("Uploader")
        self.assertEqual(code, 2, out)
        self.assertIn("ROUTE: json <workspace>/FM/_COMPONENTS/Uploader/<name>.json", line)
        self.assertIn("WARN PARITY_PARTIAL", out)
        self.assertIn("large-file workflow", out)

    def test_rule_1a_a_loader_folder_is_json(self):
        for name, folder in (("DataSource", "DataSource"), ("template", "Template"), ("Endpoints", "Endpoints")):
            with self.subTest(name):
                code, line, out = route(name)
                self.assertEqual(code, 0, out)
                self.assertTrue(line.startswith(f"ROUTE: json <workspace>/FM/_COMPONENTS/{folder}/<name>.json — "
                                                f"`{folder}` is a loader folder"), out)

    def test_rule_5_no_row_is_exit_3(self):
        code, line, out = route("Search")
        self.assertEqual(code, 3, out)
        self.assertIsNone(line)
        self.assertIn("ERROR ROUTE_NO_ROW", out)

    def test_unknown_name_is_exit_3(self):
        code, line, out = route("dataTabel")
        self.assertEqual(code, 3, out)
        self.assertIsNone(line)

    def test_never_routes_to_code(self):
        for name in ("Form", "ProcessFlow", "DataTable", "Uploader"):
            self.assertNotIn("ROUTE: code", route(name)[2])

    def test_usage_errors_are_exit_3(self):
        self.assertEqual(helpers.run_cli("route_means.py")[0], 3)
        self.assertEqual(helpers.run_cli("route_means.py", "Form", "Page")[0], 3)


if __name__ == "__main__":
    unittest.main()
