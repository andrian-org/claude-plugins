"""scripts/resolve_components.py end to end: component types in both families, and component file references."""

import json
import shutil
import tempfile
import unittest

from tests import helpers

APP = "ws/app/FM/"
OTHER = "ws/other/FM/"
BASE = "ws/webasm/FM/"


def page(*content, **extra):
    return json.dumps({"type": "page", "name": "p", "content": list(content), **extra})


def reference(name, component_type="page"):
    return {"type": "referenceComponent", "name": "r", "componentType": component_type, "componentName": name}


def form(component_type):
    return (f'<?xml version="1.0"?>\n<form>\n  <cell name="c">\n    <component type="{component_type}" />\n'
            f'  </cell>\n</form>\n')


@unittest.skipUnless(helpers.have_dependencies(), "lxml / jsonschema not installed")
class ResolveComponents(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)

    def run_on(self, files, target=None, *extra):
        """Write `files` into a fresh root and run on `target` (default: the first file)."""
        root = helpers.make_root(tempfile.mkdtemp(dir=self.tmp), files)
        return helpers.run_cli("resolve_components.py", root / (target or next(iter(files))), *extra)

    def assert_result(self, result, code, finding):
        exit_code, out, err = result
        self.assertEqual(exit_code, code, out + err)
        self.assertIn(f" {finding} ", out + err, out + err)

    # --- JSON component types --------------------------------------------------

    def test_camel_case_types_pass(self):
        code, out, _ = self.run_on({APP + "_COMPONENTS/Page/p.json": page({"type": "dataTable", "name": "t"})})
        self.assertEqual(code, 0, out)
        self.assertIn("CHECKS RUN: component-types, component-file-references", out)

    def test_unknown_top_level_type_blocks(self):
        result = self.run_on({APP + "_COMPONENTS/Template/t.json": '{"type": "dataTabel", "name": "t"}'})
        self.assert_result(result, 1, "UNKNOWN_COMPONENT")

    def test_unknown_nested_type_names_its_path(self):
        result = self.run_on({APP + "_COMPONENTS/Page/p.json": page({"type": "row", "content": [{"type": "dataTabel"}]})})
        self.assert_result(result, 1, "UNKNOWN_COMPONENT")
        self.assertIn("$.content[0].content[0]:", result[1])

    def test_no_service_is_info_once_per_member(self):
        code, out, _ = self.run_on({APP + "_COMPONENTS/Page/p.json": page({"type": "button"}, {"type": "BUTTON"})})
        self.assertEqual(code, 0, out)
        self.assertEqual(out.count("INFO NO_SERVICE"), 1, out)
        self.assertIn("`Button` (2 times)", out)

    def test_no_config_class_warns(self):
        result = self.run_on({APP + "_COMPONENTS/Page/p.json": page({"type": "search"})})
        self.assert_result(result, 2, "NO_CONFIG_CLASS")
        self.assertNotIn("NO_SERVICE", result[1])

    def test_none_parses_but_has_no_class(self):
        result = self.run_on({APP + "_COMPONENTS/Page/p.json": page({"type": "none"})})
        self.assert_result(result, 2, "NO_CONFIG_CLASS")

    def test_sitemap_is_not_run(self):
        code, out, _ = self.run_on({APP + "_COMPONENTS/sitemap.json": '{"pages": []}'})
        self.assertEqual(code, 2, out)
        self.assertIn("NOT RUN: component-types (no schema selects the file)", out)

    # --- JSON component file references ---------------------------------------

    def test_reference_component_resolves(self):
        code, out, _ = self.run_on({APP + "_COMPONENTS/Page/p.json": page(reference("q")),
                                    APP + "_COMPONENTS/Page/q.json": page()})
        self.assertEqual(code, 0, out)

    def test_reference_component_missing_blocks(self):
        result = self.run_on({APP + "_COMPONENTS/Page/p.json": page(reference("q"))})
        self.assert_result(result, 1, "COMPONENT_FILE_UNRESOLVED")
        self.assertIn("app/FM/_COMPONENTS/Page/q.json", result[1])

    def test_reference_type_is_read_in_any_case(self):
        code, out, _ = self.run_on({APP + "_COMPONENTS/Page/p.json": page(reference("t", "DATATABLE")),
                                    APP + "_COMPONENTS/DataTable/t.json": '{"type": "dataTable", "name": "t"}'})
        self.assertEqual(code, 0, out)

    def test_base_prefix_reads_webasm_only(self):
        files = {APP + "_COMPONENTS/Page/p.json": page(reference("BASE:q")), APP + "_COMPONENTS/Page/q.json": page()}
        self.assert_result(self.run_on(files), 1, "COMPONENT_FILE_UNRESOLVED")
        files[BASE + "_COMPONENTS/Page/q.json"] = page()
        self.assertEqual(self.run_on(files, APP + "_COMPONENTS/Page/p.json")[0], 0)

    def test_case_only_match_warns(self):
        result = self.run_on({APP + "_COMPONENTS/Page/p.json": page(reference("q")),
                              APP + "_COMPONENTS/Page/Q.json": page()})
        self.assert_result(result, 2, "CASE_ONLY_MATCH")

    def test_path_on_a_direct_child_is_resolved(self):
        child = {"type": "text", "name": "t", "path": "intro"}
        self.assert_result(self.run_on({APP + "_COMPONENTS/Page/p.json": page(child)}), 1, "COMPONENT_FILE_UNRESOLVED")
        code, out, _ = self.run_on({APP + "_COMPONENTS/Page/p.json": page(child),
                                    APP + "_COMPONENTS/Text/intro.json": '{"type": "text", "name": "intro"}'})
        self.assertEqual(code, 0, out)

    def test_path_is_not_expanded_deeper_or_in_a_template(self):
        deep = {"type": "row", "content": [{"type": "text", "path": "absent"}]}
        self.assertEqual(self.run_on({APP + "_COMPONENTS/Page/p.json": page(deep)})[0], 0)
        direct = {"type": "text", "path": "absent"}
        self.assertEqual(self.run_on({APP + "_COMPONENTS/Template/p.json": page(direct)})[0], 0)

    def test_webasm_reference_is_app_dependent(self):
        files = {BASE + "_COMPONENTS/Page/p.json": page(reference("q")),
                 APP + "_COMPONENTS/Page/q.json": page(),
                 OTHER + "_COMPONENTS/Page/other.json": page()}
        exit_code, out, err = self.run_on(files)
        self.assertEqual(exit_code, 2, out + err)
        self.assertIn("present in app, absent from other", out)
        files[OTHER + "_COMPONENTS/Page/q.json"] = page()
        self.assertEqual(self.run_on(files, BASE + "_COMPONENTS/Page/p.json")[0], 0)

    def test_webasm_reference_hints_at_base(self):
        exit_code, out, _ = self.run_on({BASE + "_COMPONENTS/Page/p.json": page(reference("q")),
                                         BASE + "_COMPONENTS/Page/q.json": page(),
                                         APP + "_COMPONENTS/Page/other.json": page()})
        self.assertEqual(exit_code, 2, out)
        self.assertIn("which only a `BASE:` name reaches", out)

    def test_file_outside_a_workspace_skips_references(self):
        code, out, _ = self.run_on({"loose/p.json": page(reference("q"))})
        self.assertEqual(code, 0, out)
        self.assertIn("NOT RUN: component-file-references (the file is not under a workspace's FM/)", out)

    # --- XML forms ---------------------------------------------------------------

    def test_form_with_an_unknown_type_blocks(self):
        result = self.run_on({APP + "_DATA/T/_forms/F/_form.xml": form("dataTabel")})
        self.assert_result(result, 1, "UNKNOWN_COMPONENT")
        self.assertIn("_form.xml:4 ", result[1])

    def test_form_with_a_member_the_xsd_omits_warns(self):
        result = self.run_on({APP + "_DATA/T/_forms/F/_form.xml": form("comboBox")})
        self.assert_result(result, 2, "XSD_LAGS_RUNTIME")

    def test_form_with_a_listed_type_passes(self):
        code, out, _ = self.run_on({APP + "_DATA/T/_forms/F/_form.xml": form("query")})
        self.assertEqual(code, 0, out)

    def test_process_names_no_component_types(self):
        code, out, _ = self.run_on({APP + "_PROCESS/P/process.xml": (helpers.FIXTURES / "unit" / "xml" /
                                                                    "process-valid.xml").read_text()})
        self.assertEqual(code, 0, out)
        self.assertIn("NOT RUN: component-types (a `Process` document names no component types)", out)

    # --- both families, and usage ------------------------------------------------

    def test_both_families_in_one_invocation(self):
        root = helpers.make_root(self.tmp, {APP + "_COMPONENTS/Page/p.json": page(),
                                            APP + "_DATA/T/_forms/F/_form.xml": form("dataTabel")})
        code, out, _ = helpers.run_cli("resolve_components.py", root)
        self.assertEqual(code, 1, out)
        self.assertIn("FAMILY: json", out)
        self.assertIn("FAMILY: xsd", out)

    def test_no_arguments_is_exit_3(self):
        self.assertEqual(helpers.run_cli("resolve_components.py")[0], 3)


if __name__ == "__main__":
    unittest.main()
