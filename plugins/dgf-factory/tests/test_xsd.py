"""Family detection and the legacy XML layer: scripts/lib/family.py and scripts/lib/xsd.py."""

import unittest

from tests import helpers

XML = helpers.FIXTURES / "unit" / "xml"
FORM_UTF16 = '<?xml version="1.0" encoding="utf-16"?>\n<form padding="4">\n  <header title="Grüße" />\n</form>\n'


@unittest.skipUnless(helpers.have_dependencies(), "lxml / jsonschema not installed")
class Family(unittest.TestCase):
    def detect(self, data):
        from lib import family, xsd
        return family.detect(data, set(xsd.roots()))

    def test_xml_declaration_is_xsd(self):
        self.assertEqual(self.detect((XML / "form-valid.xml").read_bytes()).family, "xsd")

    def test_known_root_without_declaration_is_xsd(self):
        self.assertEqual(self.detect(b"<form />").family, "xsd")

    def test_utf16_with_bom_and_declaration_parses_from_bytes(self):
        data = b"\xff\xfe" + FORM_UTF16.encode("utf-16-le")
        detection = self.detect(data)
        self.assertEqual(detection.family, "xsd")
        self.assertEqual(detection.tree.getroot().find("header").get("title"), "Grüße")

    def test_utf8_bom_with_declaration_parses(self):
        data = b"\xef\xbb\xbf" + FORM_UTF16.replace("utf-16", "utf-8").encode("utf-8")
        self.assertEqual(self.detect(data).family, "xsd")

    def test_json_object_is_json(self):
        self.assertEqual(self.detect(b'// c\n{"type": "page"}').family, "json")

    def test_json_array_is_unresolved(self):
        self.assertEqual(self.detect(b"[1, 2]").code, "FAMILY_UNRESOLVED")

    def test_plain_text_is_unresolved_with_both_reasons(self):
        detection = self.detect(b"hello world")
        self.assertEqual(detection.code, "FAMILY_UNRESOLVED")
        self.assertIn("XSD:", detection.message)
        self.assertIn("JSON:", detection.message)

    def test_unknown_root_without_declaration_is_unresolved(self):
        self.assertEqual(self.detect(b"<rules />").code, "FAMILY_UNRESOLVED")

    def test_declared_but_broken_xml_is_malformed(self):
        detection = self.detect(b'<?xml version="1.0"?>\n<form>\n<header>\n</form>')
        self.assertEqual(detection.code, "XML_MALFORMED")
        self.assertIsNotNone(detection.line)


@unittest.skipUnless(helpers.have_dependencies(), "lxml / jsonschema not installed")
class Grammars(unittest.TestCase):
    def test_roots_of_the_vendored_set(self):
        from lib import xsd
        roots = xsd.roots()
        self.assertEqual(roots["Process"], ["process.xsd"])
        self.assertEqual(sorted(roots["view"]), ["grid-form.xsd", "lookup-view.xsd", "table-view.xsd"])
        self.assertIn("Tree", roots)

    def test_view_grammar_from_the_folder(self):
        from lib import xsd
        base = "/r/app/FM/_DATA/People/"
        self.assertEqual(xsd.grammar_for("view", base + "_views/All/_view.xml")[0], "table-view.xsd")
        self.assertEqual(xsd.grammar_for("view", base + "_lookupviews/Pick/_view.xml")[0], "lookup-view.xsd")
        self.assertEqual(xsd.grammar_for("view", base + "_gridforms/Edit/_grid.xml")[0], "grid-form.xsd")
        self.assertEqual(xsd.grammar_for("view", "/tmp/_view.xml", "lookup")[0], "lookup-view.xsd")
        self.assertIsNone(xsd.grammar_for("view", "/tmp/_view.xml")[0])

    def test_a_view_with_an_empty_name_sits_in_the_kind_folder(self):
        from lib import xsd
        base = "/r/app/FM/_DATA/People/"
        self.assertEqual(xsd.grammar_for("view", base + "_views/_view.xml")[0], "table-view.xsd")
        self.assertEqual(xsd.grammar_for("view", base + "_lookupviews/_view.xml")[0], "lookup-view.xsd")
        self.assertEqual(xsd.grammar_for("view", base + "_gridforms/_grid.xml")[0], "grid-form.xsd")

    def test_form_component_type_enumeration(self):
        from lib import xsd
        listed = xsd.enumeration("form.xsd", "componentTypeValue")
        self.assertEqual(len(listed), 15)
        self.assertIn("query", listed)
        self.assertNotIn("comboBox", listed)
        with self.assertRaises(LookupError):
            xsd.enumeration("form.xsd", "noSuchType")

    def test_profile_does_not_compile(self):
        from lib import xsd
        self.assertIsNone(xsd.schema("profile.xsd"))
        self.assertIn("xmlns", xsd.uncompilable_reason("profile.xsd"))

    def test_construct_names(self):
        from lib import xsd
        self.assertEqual(xsd.construct_of("/Process/States/State[2]", "Element 'State', attribute 'ftitle': x"),
                         "State/@ftitle")
        self.assertEqual(xsd.construct_of("/Process/States/State[3]/OnInit/StoredProcedureActivity",
                                          "Element 'StoredProcedureActivity': This element is not expected."),
                         "OnInit/StoredProcedureActivity")


@unittest.skipUnless(helpers.have_dependencies(), "lxml / jsonschema not installed")
class ProcessStructure(unittest.TestCase):
    def structure(self, fixture):
        from lxml import etree
        from lib import family, report, xsd
        rep = report.Report(fixture, "xsd")
        tree = etree.parse(str(XML / fixture), family.xml_parser())
        usable = xsd.validate_process_structure(tree, rep)
        return usable, [f.code for f in rep.findings]

    def test_valid_process(self):
        self.assertEqual(self.structure("process-valid.xml"), (True, []))

    def test_runtime_bound_attribute_is_a_divergence(self):
        self.assertEqual(self.structure("process-ftitle.xml"), (True, ["XSD_RUNTIME_DIVERGENCE"]))

    def test_unknown_element_is_invalid(self):
        usable, codes = self.structure("process-unknown-element.xml")
        self.assertFalse(usable)
        self.assertIn("XSD_INVALID", codes)

    def structure_of(self, process_body):
        from lxml import etree
        from lib import report, xsd
        rep = report.Report("inline", "xsd")
        xml = ('<Process title="C" table="T" keyName="id" allowBack="false" allowHistory="true" '
               f'assignTasks="false">{process_body}</Process>')
        usable = xsd.validate_process_structure(etree.ElementTree(etree.fromstring(xml)), rep)
        return usable, sorted({f.code for f in rep.findings})

    def test_any_child_order_the_runtime_reads_is_not_blocked(self):
        # XmlSerializer reads child elements in any order; pass 2 must accept every placement.
        states = ('<States><State name="A"><OnTimeout interval="1.00:00:00" state="End" />'
                  '<Transitions><Transition state="End" /></Transitions></State></States>')
        on_start = ('<OnStart action=""><OnInit><UpdateRecord /></OnInit>'
                    '<Transitions><Transition state="A" /></Transitions></OnStart>')
        activities = ('<States><State name="A"><OnInit><Task state="NEW" /><UpdateRecord /></OnInit>'
                      '<Transitions><Transition state="End" /></Transitions></State></States>')
        plain = '<OnStart action=""><Transitions><Transition state="A" /></Transitions></OnStart>'
        for body in (plain + states, on_start + states, plain + activities):
            with self.subTest(body=body):
                self.assertEqual(self.structure_of(body), (True, ["XSD_RUNTIME_DIVERGENCE"]))

    def test_an_added_element_keeps_its_own_type(self):
        body = ('<OnStart action=""><OnInit><Bogus /></OnInit><Transitions><Transition state="A" />'
                '</Transitions></OnStart><States><State name="A"><Transitions><Transition state="End" />'
                '</Transitions></State></States>')
        usable, codes = self.structure_of(body)
        self.assertFalse(usable)
        self.assertIn("XSD_INVALID", codes)

    def test_vendored_xsd_is_untouched(self):
        from lib import xsd
        xsd.extended_process_schema()
        self.assertNotIn(b"hideDesc", (xsd.XSD_DIR / "process.xsd").read_bytes())


if __name__ == "__main__":
    unittest.main()
