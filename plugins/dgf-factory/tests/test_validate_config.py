"""scripts/validate_config.py end to end: every finding code it emits, with its exit code."""

import shutil
import tempfile
import unittest

from tests import helpers

XML = helpers.FIXTURES / "unit" / "xml"
JSON = helpers.FIXTURES / "unit" / "json"
APP = "ws/app/FM/"


@unittest.skipUnless(helpers.have_dependencies(), "lxml / jsonschema not installed")
class ValidateConfig(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)

    def run_on(self, files, *extra, target=None):
        root = helpers.make_root(self.tmp, files)
        path = root / (target or next(iter(files)))
        return helpers.run_cli("validate_config.py", path, *extra)

    def assert_result(self, result, code, finding):
        exit_code, out, err = result
        self.assertEqual(exit_code, code, out + err)
        self.assertIn(f" {finding} ", out + err, out + err)

    # --- JSON family ---------------------------------------------------------

    def test_clean_json(self):
        code, out, _ = self.run_on({APP + "_COMPONENTS/Page/home.json": '{"type": "page", "name": "home"}'})
        self.assertEqual(code, 0, out)
        self.assertIn("CHECKS RUN: json-schema, runtime-parity", out)
        self.assertIn("NOT RUN: json-format (annotation-only, ADR 0015)", out)
        self.assertTrue(out.rstrip().endswith("CLEAN"))

    def test_json_workflow_is_not_runtime_supported(self):
        result = self.run_on({APP + "_COMPONENTS/Workflow/w.json": '{"type": "workflow", "name": "w"}'})
        self.assert_result(result, 2, "PARITY_NOT_RUNTIME")

    def test_json_form_is_partial(self):
        result = self.run_on({APP + "_COMPONENTS/Form/f.json": '{"type": "form", "name": "f"}'})
        self.assert_result(result, 2, "PARITY_PARTIAL")

    def test_schema_invalid(self):
        result = self.run_on({APP + "_COMPONENTS/Text/t.json": '{"type": "text", "name": "t", "cols": "6"}'})
        self.assert_result(result, 1, "SCHEMA_INVALID")

    def test_unknown_component(self):
        result = self.run_on({APP + "_COMPONENTS/Template/t.json": '{"type": "dataTabel", "name": "t"}'})
        self.assert_result(result, 1, "UNKNOWN_COMPONENT")

    def test_unknown_discriminator(self):
        result = self.run_on({APP + "_COMPONENTS/DataSource/d.json": '{"type": "tabel", "name": "d"}'})
        self.assert_result(result, 1, "UNKNOWN_DISCRIMINATOR")

    def test_unknown_property(self):
        result = self.run_on({APP + "_COMPONENTS/Text/t.json": '{"type": "text", "name": "t", "colour": "red"}'})
        self.assert_result(result, 2, "UNKNOWN_PROPERTY")

    def test_no_schema(self):
        result = self.run_on({APP + "_COMPONENTS/Endpoints/api.json": '{"baseUrl": "https://x"}'})
        self.assert_result(result, 2, "NO_SCHEMA")

    def test_type_folder_mismatch(self):
        result = self.run_on({APP + "_COMPONENTS/Page/t.json": '{"type": "text", "name": "t"}'})
        self.assert_result(result, 2, "TYPE_FOLDER_MISMATCH")

    def test_no_config_class(self):
        result = self.run_on({APP + "_COMPONENTS/Template/s.json": '{"type": "search", "name": "s"}'})
        self.assert_result(result, 2, "NO_CONFIG_CLASS")

    def test_no_parity_row_is_info(self):
        code, out, _ = self.run_on({APP + "_COMPONENTS/Template/s.json": '{"type": "search", "name": "s"}'})
        self.assertIn("INFO NO_PARITY_ROW", out)

    def test_schema_unselectable(self):
        result = self.run_on({"loose/x.json": '{"name": "x"}'})
        self.assert_result(result, 3, "SCHEMA_UNSELECTABLE")

    def test_component_type_override(self):
        code, out, _ = self.run_on({"loose/x.json": '{"type": "page", "name": "x"}'}, "--component-type", "Page")
        self.assertEqual(code, 0, out)

    # --- XML family ----------------------------------------------------------

    def test_process_with_ftitle_is_a_divergence(self):
        result = self.run_on({APP + "_PROCESS/Case/process.xml": (XML / "process-ftitle.xml").read_text()})
        self.assert_result(result, 2, "XSD_RUNTIME_DIVERGENCE")

    def test_process_with_unknown_element_is_invalid(self):
        result = self.run_on({APP + "_PROCESS/Case/process.xml": (XML / "process-unknown-element.xml").read_text()})
        self.assert_result(result, 1, "XSD_INVALID")

    def test_workflow_state_process_lags_the_xsd(self):
        result = self.run_on({APP + "_WORKFLOW/Move/_workflow.xml": (XML / "workflow-stateprocess.xml").read_text()})
        self.assert_result(result, 2, "XSD_LAGS_RUNTIME")

    def test_tree_root_is_not_compilable(self):
        result = self.run_on({APP + "_PROFILE/p.xml": (XML / "profile-tree.xml").read_text()})
        self.assert_result(result, 2, "XSD_NOT_COMPILABLE")

    def test_xml_malformed(self):
        result = self.run_on({APP + "_DATA/T/settings.xml": '<?xml version="1.0"?>\n<entity>\n'})
        self.assert_result(result, 1, "XML_MALFORMED")

    def test_view_without_a_folder_is_unselectable(self):
        result = self.run_on({"loose/_view.xml": '<?xml version="1.0"?>\n<view />\n'})
        self.assert_result(result, 3, "SCHEMA_UNSELECTABLE")

    def test_utf16_form_with_a_space_in_its_path(self):
        data = b"\xff\xfe" + ('<?xml version="1.0" encoding="utf-16"?>\n<form padding="4" />\n').encode("utf-16-le")
        code, out, _ = self.run_on({APP + "_DATA/T/_forms/My Form/_form.xml": data})
        self.assertEqual(code, 0, out)
        self.assertIn("FAMILY: xsd", out)

    # --- neither family, and usage --------------------------------------------

    def test_plain_text_is_exit_3(self):
        result = self.run_on({"notes.txt": "just some words\n"})
        self.assert_result(result, 3, "FAMILY_UNRESOLVED")

    def test_no_arguments_is_exit_3(self):
        self.assertEqual(helpers.run_cli("validate_config.py")[0], 3)

    def test_unknown_flag_is_exit_3(self):
        self.assertEqual(helpers.run_cli("validate_config.py", "--nope", self.tmp)[0], 3)

    def test_directory_walk_picks_artifacts_and_json(self):
        root = helpers.make_root(self.tmp, {
            APP + "_COMPONENTS/Page/home.json": '{"type": "page", "name": "home"}',
            APP + "_PROCESS/Case/process.xml": (XML / "process-valid.xml").read_text(),
            APP + "_PROCESS/Case/notes.xml": "<notes />",
        })
        code, out, _ = helpers.run_cli("validate_config.py", root)
        self.assertEqual(code, 0, out)
        self.assertEqual(out.count("FAMILY:"), 2)

    def test_directory_walk_skips_json_no_loader_reads(self):
        root = helpers.make_root(self.tmp, {
            APP + "_COMPONENTS/Page/home.json": '{"type": "page", "name": "home"}',
            APP + "_DATA/T/_forms/F/_form.json": '{"fields": []}',
            APP + "_PROFILE/P/_settings.json": '{}',
        })
        code, out, _ = helpers.run_cli("validate_config.py", root)
        self.assertEqual(code, 0, out)
        self.assertEqual(out.count("FAMILY:"), 1, out)

    def test_the_verdict_does_not_depend_on_the_working_directory(self):
        root = helpers.make_root(self.tmp, {APP + "_COMPONENTS/Page/t.json": '{"type": "text", "name": "t"}',
                                            APP + "_DATA/T/_forms/F/_form.json": '{"fields": []}'})
        inside = root / APP / "_COMPONENTS"
        code, out, _ = helpers.run_cli("validate_config.py", "Page/t.json", cwd=inside)
        self.assertEqual(code, 2, out)
        self.assertIn(" TYPE_FOLDER_MISMATCH ", out)
        code, out, _ = helpers.run_cli("validate_config.py", ".", cwd=root / APP)
        self.assertEqual(code, 2, out)
        self.assertEqual(out.count("FAMILY:"), 1, out)

    def test_named_json_outside_components_is_still_checked(self):
        result = self.run_on({APP + "_DATA/T/_forms/F/_form.json": '{"fields": []}'})
        self.assert_result(result, 3, "SCHEMA_UNSELECTABLE")


if __name__ == "__main__":
    unittest.main()
