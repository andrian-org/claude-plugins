"""scripts/lib/model.py: each model loader's own resolution rule (knowledge/data-model.md §3)."""

import shutil
import tempfile
import unittest
import contextlib
import io
import os
import xml.etree.ElementTree as ET

from tests import helpers
from lib import model, workspace

SETTINGS = ("<entity><primarykey>Id</primarykey><fields><field name='Id' type='PrimaryKey' uimask='00111'/>"
            "<field name='Name' type='Text' uimask='01111'/></fields></entity>")
# An entity whose one Text field is its key, and whose other field has no uimask: the zims sample
# CarModelHasCategory is the first shape, and no template can be generated for either.
BARE = ("<entity><primarykey>ID</primarykey><fields><field name='ID' type='Text' uimask='00111'/>"
        "<field name='ModelId' type='Lookup'/></fields></entity>")
# An entity whose key names no field, so Table.InitFields throws. Were each template check to go on, the view would
# find no Text field, the grid no key field, and the form a field with no uimask.
UNLOADABLE = "<entity><primarykey>Nope</primarykey><fields><field name='Id' type='Integer'/></fields></entity>"


def entity(*fields, key="Id"):
    """An entity whose key `Id` has a uimask, with the given raw `<field>` elements after it."""
    return (f"<entity><primarykey>{key}</primarykey><fields><field name='Id' type='PrimaryKey' uimask='00111'/>"
            + "".join(fields) + "</fields></entity>")


def model_root(tmp):
    """Two applications, `a` and `b`, and webasm, with entities, views, grids, forms and dialogs."""
    return helpers.make_root(tmp, {
        "a/FM/_DATA/Cases/settings.xml": SETTINGS,
        "a/FM/_DATA/Cases/_lookupviews/default/_view.xml": "<view/>",
        "a/FM/_DATA/Cases/_lookupviews/short/_view.xml": "<view/>",
        "a/FM/_DATA/Cases/_gridforms/default/_grid.xml": "<view/>",
        "a/FM/_DATA/Cases/_forms/default/_form.xml": "<form/>",
        "a/FM/_DATA/Cases/_forms/edit/_form.xml": "<form/>",
        "a/FM/_DATA/Cases/_forms/sub/nested/_form.xml": "<form/>",
        "a/FM/_DATA/Mixed/settings.xml": SETTINGS,
        "a/FM/_DATA/OnlyA/settings.xml": SETTINGS,
        "b/FM/_DATA/Cases/settings.xml": SETTINGS,
        "a/FM/_LOOKUP/People/_dialog.xml": "<dialog/>",
        "b/FM/_LOOKUP/Other/_dialog.xml": "<dialog/>",
        "webasm/FM/_DATA/Shared/settings.xml": SETTINGS,
        "webasm/FM/_DATA/Shared/_gridforms/rows/_grid.xml": "<view/>",
        "webasm/FM/_DATA/Shared/_forms/default/_form.xml": "<form/>",
        "webasm/FM/_LOOKUP/BaseOnly/_dialog.xml": "<dialog/>",
    })


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.root = model_root(self.tmp)
        self.app, self.base = self.root / "a", self.root / "webasm"


class Tables(Base):
    def test_cleaning_drops_everything_up_to_the_last_dot(self):
        self.assertEqual(model.clean_table("dbo.Cases"), "Cases")
        self.assertEqual(model.clean_table("srv.dbo.Cases"), "Cases")
        self.assertEqual(model.clean_table("BASE:dbo.Cases"), "Cases")
        self.assertEqual(model.clean_table("Cases"), "Cases")

    def test_a_table_in_the_application(self):
        self.assertEqual(model.resolve_table("Cases", self.app, self.root),
                         workspace.Resolved("a/FM/_DATA/Cases/settings.xml"))

    def test_base_in_any_case_is_webasm(self):
        for name in ("BASE:Shared", "base:Shared", "Base:Shared"):
            self.assertEqual(model.resolve_table(name, self.app, self.root),
                             workspace.Resolved("webasm/FM/_DATA/Shared/settings.xml"), name)

    def test_a_schema_prefix_is_cleaned(self):
        self.assertEqual(model.resolve_table("dbo.Cases", self.app, self.root),
                         workspace.Resolved("a/FM/_DATA/Cases/settings.xml"))

    def test_base_dbo_x_resolves_in_the_application_because_cleaning_comes_first(self):
        self.assertEqual(model.table_location("BASE:dbo.Cases"), ("selected", ["FM", "_DATA", "Cases"]))
        self.assertEqual(model.resolve_table("BASE:dbo.Cases", self.app, self.root),
                         workspace.Resolved("a/FM/_DATA/Cases/settings.xml"))
        self.assertIsInstance(model.resolve_table("BASE:dbo.Shared", self.app, self.root), workspace.Unresolved)

    def test_a_case_only_match(self):
        result = model.resolve_table("mixed", self.app, self.root)
        self.assertEqual(result, workspace.CaseOnly("a/FM/_DATA/mixed/settings.xml", "a/FM/_DATA/Mixed/settings.xml"))

    def test_a_missing_table(self):
        self.assertEqual(model.resolve_table("Nowhere", self.app, self.root),
                         workspace.Unresolved("a/FM/_DATA/Nowhere/settings.xml"))
        self.assertIsInstance(model.resolve_table("", self.app, self.root), workspace.Unresolved)

    def test_no_fallback_to_webasm_for_an_unprefixed_name(self):
        self.assertIsInstance(model.resolve_table("Shared", self.app, self.root), workspace.Unresolved)

    def test_a_webasm_entitys_unprefixed_table_is_app_dependent(self):
        result = model.resolve_table("OnlyA", self.base, self.root)
        self.assertIsInstance(result, workspace.AppDependent)
        self.assertEqual((result.resolved_in, result.missing_in), (["a"], ["b"]))
        self.assertEqual(model.resolve_table("OnlyA", self.base, self.root, app="b"),
                         workspace.Unresolved("b/FM/_DATA/OnlyA/settings.xml"))


class Views(Base):
    def test_a_lookup_view_present_absent_and_empty(self):
        self.assertEqual(model.resolve_lookup_view("Cases", "short", self.app, self.root),
                         workspace.Resolved("a/FM/_DATA/Cases/_lookupviews/short/_view.xml"))
        self.assertIsInstance(model.resolve_lookup_view("Cases", "long", self.app, self.root), workspace.Unresolved)
        self.assertEqual(model.resolve_lookup_view("Cases", "", self.app, self.root),
                         workspace.Resolved("a/FM/_DATA/Cases/_lookupviews/default/_view.xml"))

    def test_a_view_follows_its_cleaned_table(self):
        self.assertEqual(model.resolve_lookup_view("dbo.Cases", "short", self.app, self.root),
                         workspace.Resolved("a/FM/_DATA/Cases/_lookupviews/short/_view.xml"))

    def test_a_missing_view_is_generated_when_its_table_has_a_text_field_besides_its_key(self):
        self.assertFalse(model.resolve_lookup_view("Cases", "long", self.app, self.root).throws)

    def test_a_missing_view_throws_when_its_table_has_no_text_field_besides_its_key(self):
        """LookUpViewManager.GetXmlTemplate reads the first Text field that is not the key, and there is none."""
        helpers.make_root(self.root, {"a/FM/_DATA/Link/settings.xml": BARE})
        for view in ("", "short"):
            result = model.resolve_lookup_view("Link", view, self.app, self.root)
            self.assertEqual((type(result), result.throws), (workspace.Unresolved, True), view)
            self.assertIn("a `Text` field besides the key `ID`", result.reason)

    def test_a_missing_view_throws_when_the_generated_view_would_not_parse(self):
        """GetXmlTemplate pastes the display field's name and title unescaped, and SaveXml re-parses the view."""
        for title in ("Name &amp; Surname", "a &lt; b", "say &quot;hi&quot;"):
            helpers.make_root(self.root, {"a/FM/_DATA/Amp/settings.xml": entity(
                f"<field name='Name' type='Text' uimask='00111' title='{title}'/>")})
            result = model.resolve_lookup_view("Amp", "", self.app, self.root)
            self.assertEqual((type(result), result.throws), (workspace.Unresolved, True), title)
            self.assertIn("the title of `Name`", result.reason)

    def test_a_title_that_parses_once_pasted_or_a_field_the_view_does_not_show_is_harmless(self):
        helpers.make_root(self.root, {"a/FM/_DATA/Safe/settings.xml": entity(
            "<field name='Name' type='Text' title='A &amp;amp; B, O&apos;Neil &gt; x'/>",  # pastes as `A &amp; B…`
            "<field name='Other' type='Text' title='x &amp; y'/>")})  # not the first Text field: not shown
        self.assertFalse(model.resolve_lookup_view("Safe", "", self.app, self.root).throws)

    def test_a_display_field_with_an_empty_name_falls_back_to_the_tables_first_field(self):
        """GetXmlTemplate pastes FieldCollection[0] instead when the display field's name is `""`."""
        helpers.make_root(self.root, {
            "a/FM/_DATA/Blank/settings.xml": ("<entity><primarykey>Id</primarykey><fields><field name='Id' "
                                              "type='PrimaryKey' title='Key &amp; code'/><field name='' type='Text' "
                                              "title='fine'/></fields></entity>"),
            "a/FM/_DATA/Shown/settings.xml": ("<entity><primarykey>Id</primarykey><fields><field name='Id' "
                                              "type='PrimaryKey' title='fine'/><field name='' type='Text' "
                                              "title='x &amp; y'/></fields></entity>")})
        result = model.resolve_lookup_view("Blank", "", self.app, self.root)
        self.assertEqual((type(result), result.throws), (workspace.Unresolved, True))
        self.assertIn("the title of `Id`", result.reason)
        self.assertFalse(model.resolve_lookup_view("Shown", "", self.app, self.root).throws)  # its title is not pasted

    def test_a_quote_breaks_the_view_only_where_the_template_puts_it(self):
        """SaveXml parses the whole view: a title's `"` closes its attribute, and what follows must still parse."""
        helpers.make_root(self.root, {
            "a/FM/_DATA/Twice/settings.xml": entity("<field name='Name' type='Text' title='x&quot; title=&quot;y'/>"),
            "a/FM/_DATA/Extra/settings.xml": entity("<field name='Name' type='Text' title='x&quot; a=&quot;y'/>")})
        twice = model.resolve_lookup_view("Twice", "", self.app, self.root)  # the cell holds `title` twice
        self.assertEqual((type(twice), twice.throws), (workspace.Unresolved, True))
        self.assertIn("the title of `Name`", twice.reason)
        self.assertFalse(model.resolve_lookup_view("Extra", "", self.app, self.root).throws)  # a well-formed attribute

    def test_the_view_pastes_the_key_as_its_keyfield(self):
        helpers.make_root(self.root, {"a/FM/_DATA/Amp/settings.xml": (
            "<entity><primarykey>K&amp;1</primarykey><fields><field name='K&amp;1' type='PrimaryKey'/>"
            "<field name='Name' type='Text'/></fields></entity>")})
        result = model.resolve_lookup_view("Amp", "", self.app, self.root)
        self.assertEqual((type(result), result.throws), (workspace.Unresolved, True))
        self.assertIn("the key `K&1`", result.reason)

    def test_only_the_first_primarykey_element_is_read(self):
        """XmlSerializer binds the first `<primarykey>` to Table.primaryKeyString and skips the next."""
        helpers.make_root(self.root, {"a/FM/_DATA/Two/settings.xml": (
            "<entity><primarykey>Id</primarykey><primarykey>Name</primarykey><fields>"
            "<field name='Id' type='Text' title='A &amp; B'/><field name='Name' type='Text'/></fields></entity>")})
        self.assertEqual(model.read_entity(self.app / "FM/_DATA/Two/settings.xml")[0], "Id")
        self.assertFalse(model.resolve_lookup_view("Two", "", self.app, self.root).throws)  # the key is Id: Name shows

    def test_the_view_is_parsed_as_xml_document_load_xml_reads_it(self):
        """LoadXml reads namespaces, and takes only `preserve` or `default`, trimmed, as an xml:space."""
        cases = {"x&quot; p:a=&quot;1": True, "x&quot; xmlns:p=&quot;u&quot; p:a=&quot;1": False,
                 "x&quot; xml:space=&quot;bogus": True, "x&quot; xml:space=&quot;Preserve": True,
                 "x&quot; xml:space=&quot; preserve ": False, "x&quot; xml:lang=&quot;?": False,
                 "x&quot; xml:space=&quot;default": False, "x&quot; xml:space=&quot; default&#9;": False,
                 "x&quot; xml:space=&quot; preserve": True}
        for i, title in enumerate(cases):
            helpers.make_root(self.root, {f"a/FM/_DATA/T{i}/settings.xml": entity(
                f"<field name='Name' type='Text' title='{title}'/>")})
        for i, (title, throws) in enumerate(cases.items()):
            result = model.resolve_lookup_view(f"T{i}", "", self.app, self.root)
            self.assertEqual((type(result), result.throws), (workspace.Unresolved, throws), title)
            if throws:
                self.assertIn("the title of `Name`", result.reason)

    def test_a_table_whose_own_load_throws_is_left_to_its_settings_xml(self):
        """Table.InitFields throws before any view is generated: validate_model.py blocks the table's own file."""
        helpers.make_root(self.root, {"a/FM/_DATA/Broken/settings.xml": UNLOADABLE})
        result = model.resolve_lookup_view("Broken", "", self.app, self.root)
        self.assertEqual(result, workspace.Unresolved("a/FM/_DATA/Broken/_lookupviews/default/_view.xml"))

    def test_a_text_field_counts_only_when_its_name_is_not_the_first_key_exactly(self):
        """The key `Id,Code` is `Id`, so the view shows `Code`, whose title does not parse once pasted."""
        helpers.make_root(self.root, {"a/FM/_DATA/Pair/settings.xml": (
            "<entity><primarykey>Id,Code</primarykey><fields><field name='Id' type='Text' title='fine'/>"
            "<field name='Code' type='Text' title='a &lt; b'/></fields></entity>")})
        result = model.resolve_lookup_view("Pair", "", self.app, self.root)
        self.assertTrue(result.throws, result)
        self.assertIn("the title of `Code`", result.reason)

    def test_a_table_whose_settings_xml_declares_an_encoding_python_does_not_know_is_read_as_utf8(self):
        """File.ReadAllTextAsync decodes the file, and the StringReader XmlSerializer reads ignores its declaration."""
        helpers.make_root(self.root, {"a/FM/_DATA/Odd/settings.xml": (
            "<?xml version='1.0' encoding='bogus-enc'?><entity><primarykey>Id</primarykey><fields>"
            "<field name='Id' type='PrimaryKey'/><field name='Name' type='Text' title='a &lt; b'/></fields></entity>")})
        result = model.resolve_lookup_view("Odd", "", self.app, self.root)
        self.assertTrue(result.throws, result)
        self.assertIn("the title of `Name`", result.reason)


class Dialogs(Base):
    def test_a_dialog_in_the_application(self):
        self.assertEqual(model.resolve_lookup_dialog("People", self.app, self.root),
                         workspace.Resolved("a/FM/_LOOKUP/People/_dialog.xml"))

    def test_a_dialog_only_in_webasm_is_unresolved_from_an_application(self):
        self.assertIsInstance(model.resolve_lookup_dialog("BaseOnly", self.app, self.root), workspace.Unresolved)
        self.assertIsInstance(model.resolve_lookup_dialog("BASE:BaseOnly", self.app, self.root), workspace.Unresolved)

    def test_a_webasm_entitys_dialog_resolves_in_each_applications_lookup(self):
        result = model.resolve_lookup_dialog("People", self.base, self.root)
        self.assertEqual((result.resolved_in, result.missing_in), (["a"], ["b"]))
        self.assertEqual(model.resolve_lookup_dialog("Other", self.base, self.root, app="b"),
                         workspace.Resolved("b/FM/_LOOKUP/Other/_dialog.xml"))

    def test_a_dialog_name_is_not_cleaned(self):
        self.assertIsInstance(model.resolve_lookup_dialog("x.People", self.app, self.root), workspace.Unresolved)


class Grids(Base):
    def test_a_grid_with_and_without_base(self):
        self.assertEqual(model.resolve_grid("Cases", "", self.app, self.root),
                         workspace.Resolved("a/FM/_DATA/Cases/_gridforms/default/_grid.xml"))
        self.assertEqual(model.resolve_grid("BASE:Shared", "rows", self.app, self.root),
                         workspace.Resolved("webasm/FM/_DATA/Shared/_gridforms/rows/_grid.xml"))
        self.assertEqual(model.resolve_grid("base:Shared", "rows", self.app, self.root),
                         workspace.Resolved("webasm/FM/_DATA/Shared/_gridforms/rows/_grid.xml"))

    def test_a_grid_uses_the_loaded_tables_cleaned_name(self):
        """EditableGridManager builds the path from table.Name, which TableManager has already cleaned."""
        self.assertEqual(model.resolve_grid("dbo.Cases", "default", self.app, self.root),
                         workspace.Resolved("a/FM/_DATA/Cases/_gridforms/default/_grid.xml"))
        self.assertEqual(model.resolve_grid("BASE:dbo.Cases", "default", self.app, self.root),
                         workspace.Resolved("a/FM/_DATA/Cases/_gridforms/default/_grid.xml"))

    def test_a_missing_grid(self):
        self.assertIsInstance(model.resolve_grid("Cases", "wide", self.app, self.root), workspace.Unresolved)
        self.assertFalse(model.resolve_grid("Cases", "wide", self.app, self.root).throws)

    def test_a_blank_grid_name_is_default(self):
        """EditableGridManager.LoadAsync tests the name with IsNullOrWhiteSpace."""
        self.assertEqual(model.resolve_grid("Cases", "  ", self.app, self.root),
                         workspace.Resolved("a/FM/_DATA/Cases/_gridforms/default/_grid.xml"))

    def test_a_grid_folder_without_its_file_throws_when_the_table_has_a_default(self):
        """EditableGridManager.Copy throws into a folder that exists (data-model.md §3.6)."""
        helpers.make_root(self.root, {"a/FM/_DATA/Cases/_gridforms/wide/notes.txt": "x",
                                      "webasm/FM/_DATA/Shared/_gridforms/wide/notes.txt": "x"})
        result = model.resolve_grid("Cases", "wide", self.app, self.root)
        self.assertEqual((type(result), result.throws), (workspace.Unresolved, True))
        self.assertIn("`a/FM/_DATA/Cases/_gridforms/wide/` exists without `_grid.xml`", result.reason)
        self.assertFalse(model.resolve_grid("BASE:Shared", "wide", self.app, self.root).throws)  # no default grid

    def test_a_generated_grid_throws_when_the_column_it_shows_would_not_parse(self):
        """EditableGridManager.GetXmlTemplate shows the first required Text field besides the key, else the first
        Text field, else the key — its name and title pasted unescaped, then re-parsed by SaveXml."""
        amp = "<field name='A' type='Text' title='a &amp; b'/>"
        cases = {
            "OnlyA": (entity(amp), True),                                              # A is shown
            "Required": (entity(amp, "<field name='B' type='Text' required='true' title='ok'/>"), False),  # B is
            "KeyOnly": (entity(key="Id").replace("uimask='00111'", "uimask='00111' title='k &amp; v'"), True),
        }
        helpers.make_root(self.root, {f"a/FM/_DATA/{name}/settings.xml": xml for name, (xml, _) in cases.items()})
        for name, (_, throws) in cases.items():
            result = model.resolve_grid(name, "wide", self.app, self.root)
            self.assertEqual((type(result), result.throws), (workspace.Unresolved, throws), name)

    def test_required_1_makes_a_field_the_grids_column(self):
        """`required` is an xsd:boolean, so `1` is true, and a required Text field is the one shown."""
        helpers.make_root(self.root, {"a/FM/_DATA/One/settings.xml": entity(
            "<field name='Plain' type='Text' title='ok'/>",
            "<field name='Must' type='Text' required='1' title='A &amp; B'/>")})
        result = model.resolve_grid("One", "wide", self.app, self.root)
        self.assertEqual((type(result), result.throws), (workspace.Unresolved, True))
        self.assertIn("the title of `Must`", result.reason)

    def test_a_generated_grid_is_parsed_whole(self):
        helpers.make_root(self.root, {
            "a/FM/_DATA/Quote/settings.xml": entity("<field name='Name' type='Text' title='x&quot; title=&quot;y'/>"),
            "a/FM/_DATA/Prefix/settings.xml": entity("<field name='Name' type='Text' title='x&quot; p:a=&quot;1'/>")})
        for name in ("Quote", "Prefix"):  # `title` twice; a prefix no namespace declaration binds
            result = model.resolve_grid(name, "wide", self.app, self.root)
            self.assertEqual((type(result), result.throws), (workspace.Unresolved, True), name)

    def test_a_table_whose_own_load_throws_is_left_to_its_settings_xml(self):
        helpers.make_root(self.root, {"a/FM/_DATA/Broken/settings.xml": UNLOADABLE})
        self.assertEqual(model.resolve_grid("Broken", "wide", self.app, self.root),
                         workspace.Unresolved("a/FM/_DATA/Broken/_gridforms/wide/_grid.xml"))


class Forms(Base):
    def test_a_form_present_absent_and_empty(self):
        self.assertEqual(model.resolve_form("Cases", "edit", self.app, self.root),
                         workspace.Resolved("a/FM/_DATA/Cases/_forms/edit/_form.xml"))
        self.assertIsInstance(model.resolve_form("Cases", "view", self.app, self.root), workspace.Unresolved)
        self.assertEqual(model.resolve_form("Cases", "", self.app, self.root),
                         workspace.Resolved("a/FM/_DATA/Cases/_forms/default/_form.xml"))
        self.assertEqual(model.resolve_form("BASE:Shared", "", self.app, self.root),
                         workspace.Resolved("webasm/FM/_DATA/Shared/_forms/default/_form.xml"))

    def test_a_form_folder_without_its_file_throws_only_when_the_table_has_a_default(self):
        """FormManager.Copy throws into a folder that exists; with no default, a generated form is saved there."""
        helpers.make_root(self.root, {"a/FM/_DATA/Cases/_forms/view/notes.txt": "x",
                                      "a/FM/_DATA/Mixed/_forms/view/notes.txt": "x"})
        self.assertTrue(model.resolve_form("Cases", "view", self.app, self.root).throws)
        self.assertFalse(model.resolve_form("Mixed", "view", self.app, self.root).throws)
        self.assertFalse(model.resolve_form("Cases", "absent", self.app, self.root).throws)

    def test_a_missing_form_throws_when_it_is_generated_and_a_field_has_no_uimask(self):
        """With no `default` to copy, FormManager.GetXmlTemplate throws on a field whose uimask is null."""
        helpers.make_root(self.root, {"a/FM/_DATA/Link/settings.xml": BARE})
        for form in ("", "edit"):
            result = model.resolve_form("Link", form, self.app, self.root)
            self.assertEqual((type(result), result.throws), (workspace.Unresolved, True), form)
            self.assertIn("no `default` form", result.reason)
            self.assertIn("`ModelId` has no `uimask`", result.reason)

    def test_a_generated_form_throws_when_a_cell_it_writes_would_not_parse(self):
        """FormManager.GetXmlTemplate writes a row for each field required for the form and valid for it, and a hidden
        cell for each audit field it has — names and titles unescaped — then SaveXml re-parses the form."""
        cases = {
            "InForm": ("<field name='Note' type='Text' uimask='01010' title='x &amp; y'/>", True),
            "Required": ("<field name='Note' type='Text' required='true' uimask='00010' title='x &amp; y'/>", True),
            "NotInForm": ("<field name='Note' type='Text' uimask='00000' title='x &amp; y'/>", False),
            "Hidden": ("<field name='CreatedBy' type='Text' uimask='00000' title='by &amp; who'/>", True),
        }
        helpers.make_root(self.root, {f"a/FM/_DATA/{name}/settings.xml": entity(xml)
                                      for name, (xml, _) in cases.items()})
        for name, (_, throws) in cases.items():
            result = model.resolve_form(name, "edit", self.app, self.root)
            self.assertEqual((type(result), result.throws), (workspace.Unresolved, throws), name)

    def test_a_required_field_not_valid_for_the_form_gets_no_row(self):
        """IsValidForForm is uimask position 3: with it `0`, a required field's title is never pasted."""
        helpers.make_root(self.root, {"a/FM/_DATA/Invalid/settings.xml": entity(
            "<field name='Note' type='Text' required='true' uimask='01101' title='x &amp; y'/>")})
        self.assertFalse(model.resolve_form("Invalid", "edit", self.app, self.root).throws)

    def test_uimask_positions_count_utf16_code_units(self):
        """Field.get_uiMask indexes a C# string, so a character outside the BMP takes two positions."""
        helpers.make_root(self.root, {"a/FM/_DATA/Wide/settings.xml": entity(
            "<field name='Pick' type='Lookup' required='true' uimask='\U0001F60011' title='x &amp; y'/>")})
        result = model.resolve_form("Wide", "edit", self.app, self.root)  # position 3 is the second `1`
        self.assertEqual((type(result), result.throws), (workspace.Unresolved, True))

    def test_a_generated_form_is_parsed_whole(self):
        helpers.make_root(self.root, {
            "a/FM/_DATA/Quote/settings.xml": entity(
                "<field name='Note' type='Text' uimask='01010' title='x&quot; colspan=&quot;3'/>"),
            "a/FM/_DATA/Prefix/settings.xml": entity(
                "<field name='CreatedBy' type='Text' uimask='00000' title='x&quot; p:a=&quot;1'/>")})
        for name in ("Quote", "Prefix"):  # the row's cell holds `colspan` twice; a hidden cell an unbound prefix
            result = model.resolve_form(name, "edit", self.app, self.root)
            self.assertEqual((type(result), result.throws), (workspace.Unresolved, True), name)

    def test_a_table_whose_own_load_throws_is_left_to_its_settings_xml(self):
        helpers.make_root(self.root, {"a/FM/_DATA/Broken/settings.xml": UNLOADABLE})
        self.assertEqual(model.resolve_form("Broken", "edit", self.app, self.root),
                         workspace.Unresolved("a/FM/_DATA/Broken/_forms/edit/_form.xml"))

    def test_a_missing_form_copied_from_default_needs_no_uimask(self):
        helpers.make_root(self.root, {"a/FM/_DATA/Link/settings.xml": BARE,
                                      "a/FM/_DATA/Link/_forms/default/_form.xml": "<form/>"})
        self.assertFalse(model.resolve_form("Link", "edit", self.app, self.root).throws)

    def test_an_invoke_form_is_cut_at_readonly(self):
        self.assertEqual(model.resolve_invoke_form("Cases", "edit/READONLY", self.app, self.root),
                         workspace.Resolved("a/FM/_DATA/Cases/_forms/edit/_form.xml"))
        self.assertIsInstance(model.resolve_form("Cases", "edit/READONLY", self.app, self.root), workspace.Unresolved)

    def test_owning_table_for_a_nested_form_name(self):
        form = self.root / "a/FM/_DATA/Cases/_forms/sub/nested/_form.xml"
        self.assertEqual(model.form_parts(form), (self.app, "Cases", "sub/nested"))
        self.assertEqual(model.owning_table(form, self.root), workspace.Resolved("a/FM/_DATA/Cases/settings.xml"))

    def test_owning_table_missing_and_not_a_form(self):
        orphan = helpers.make_root(self.root, {"a/FM/_DATA/Orphan/_forms/x/_form.xml": "<form/>"})
        self.assertIsInstance(model.owning_table(orphan / "a/FM/_DATA/Orphan/_forms/x/_form.xml", self.root),
                              workspace.Unresolved)
        self.assertIsNone(model.owning_table(self.root / "a/FM/_DATA/Cases/settings.xml", self.root))
        self.assertEqual(model.owning_table(self.root / "webasm/FM/_DATA/Shared/_forms/default/_form.xml",
                                            self.root), workspace.Resolved("webasm/FM/_DATA/Shared/settings.xml"))


class EntityLoad(unittest.TestCase):
    def test_what_table_init_fields_throws_on_in_its_order(self):
        """Table.InitFields adds every field by name, then needs a primary key, then looks its first part up."""
        field = lambda name, kind="Text": model.EntityField(name, kind, None, None, False)
        key = field("Id", "PrimaryKey")
        self.assertIsNone(model.init_fields_throws("Id", [key, field("Name")]))
        self.assertIn("a field has no `name`", model.init_fields_throws("Id", [key, field(None)]))
        self.assertIn("two fields are named `Id`", model.init_fields_throws("Id", [key, field("Id")]))
        self.assertIn("no `primarykey`", model.init_fields_throws(None, [key]))
        self.assertIn("its first primary key `Nope` names no field", model.init_fields_throws("Nope", [key]))
        self.assertIn("two fields", model.init_fields_throws(None, [key, field("Id")]))  # the Add loop runs first
        # ... adding each field in turn, so the first bad one decides
        self.assertIn("two fields are named `Id`", model.init_fields_throws("Id", [key, field("Id"), field(None)]))
        self.assertIn("a field has no `name`", model.init_fields_throws("Id", [field(None), key, field("Id")]))

    def test_the_key_is_the_first_primarykeys_text_as_xml_serializer_reads_it(self):
        """XmlSerializer's reader drops a text node of whitespace alone — any markup ends a node — unless xml:space
        is `preserve`. It keeps a CDATA section. A decimal character reference is no whitespace to it, a hexadecimal
        one is. An element in a namespace is not `primarykey`. Each case as a .NET build of Table read it."""
        cases = [
            ("<primarykey>Id</primarykey><primarykey>Name</primarykey>", "Id"),
            ("<primarykey/><primarykey>Id</primarykey>", None),
            ("<primarykey>\n</primarykey><primarykey>Id</primarykey>", None),
            ("<primarykey> </primarykey>", None),
            ("<primarykey>\r\n\t</primarykey>", None),
            ("<primarykey> Id </primarykey>", " Id "),
            ("<primarykey>\n  <![CDATA[Id]]>\n</primarykey>", "Id"),
            ("<primarykey><![CDATA[ ]]> </primarykey>", " "),
            ("<primarykey> <![CDATA[]]> </primarykey>", None),
            ("<primarykey> <!--c-->Id</primarykey>", "Id"),
            ("<primarykey>I<!--c--> </primarykey>", "I"),
            ("<primarykey>I<?p?> <?q?>d</primarykey>", "Id"),
            ("<primarykey> <?p?>Id <?q?> </primarykey>", "Id "),
            ("<primarykey>&#32;</primarykey>", " "),
            ("<primarykey> &#32; </primarykey>", "   "),
            ("<primarykey>&#9;</primarykey>", "\t"),
            ("<primarykey>&#x20;</primarykey>", None),
            ("<primarykey> &#x9; </primarykey>", None),
            ("<primarykey> &lt; </primarykey>", " < "),
            ("<primarykey> </primarykey>", " "),
            ("<primarykey xml:space='preserve'> </primarykey>", " "),
            ("<primarykey xmlns='urn:x'>Id</primarykey>", None),
            ("<p:primarykey xmlns:p='urn:x'>Id</p:primarykey>", None),
            ("<primarykey xmlns=''>Id</primarykey>", "Id"),
            ("<primarykey xml:space=' preserve '> </primarykey>", " "),  # trimmed of XML whitespace
            ("<primarykey xml:space='&#9;preserve'> </primarykey>", " "),
            ("<primarykey xml:space='preserve&#10;'> </primarykey>", " "),
            ("<description xml:space='preserve'/><primarykey> </primarykey>", None),  # closed with its element
            ("<primarykey>Id,Code</primarykey>", "Id"),  # split on `,`, untrimmed
            ("<primarykey>,Id</primarykey>", ""),
            ("<primarykey> Id ,Code</primarykey>", " Id "),
            ("<fields><field name='Id'><primarykey>X</primarykey></field></fields><primarykey>Id</primarykey>", "Id"),
            ("<primarykey>Id</primarykey><fields><field name='Id'><primarykey>X</primarykey></field></fields>", "Id"),
        ]
        preserved = "<entity xml:space='preserve'>"  # inherited, and reset by `default`
        cases = [("<entity>", key, expected) for key, expected in cases] + [
            (preserved, "<primarykey> </primarykey>", " "),
            (preserved, "<primarykey xml:space='default'> </primarykey>", None),
            (preserved, "<primarykey xml:space='default '> </primarykey>", None),
            ("<entity xml:space=' preserve'>", "<primarykey> </primarykey>", " ")]
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        path = os.path.join(tmp, "settings.xml")
        for root, key, expected in cases:
            with open(path, "w", encoding="utf-8", newline="") as out:
                out.write(f"{root}{key}<fields><field name='Id'/></fields></entity>")
            self.assertEqual(model.read_entity(path)[0], expected, repr(root + key))

    def test_the_key_of_a_utf16_file_is_read_as_its_utf8_twin(self):
        """File.ReadAllTextAsync decodes a UTF-16 file by its byte-order mark; a reference is told apart the same."""
        cases = {"<primarykey> &#32; </primarykey>": "   ", "<primarykey> &#x20; </primarykey>": None,
                 "<primarykey> </primarykey>": None, "<primarykey>\n<![CDATA[Id]]>\n</primarykey>": "Id"}
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        path = os.path.join(tmp, "settings.xml")
        for encoding, bom in (("utf-16-le", b"\xff\xfe"), ("utf-16-be", b"\xfe\xff")):
            for key, expected in cases.items():
                xml = (f"<?xml version='1.0' encoding='utf-16'?><entity>{key}<fields><field name='Id'/></fields>"
                       "</entity>")
                with open(path, "wb") as out:
                    out.write(bom + xml.encode(encoding))
                self.assertEqual(model.read_entity(path)[0], expected, f"{encoding} {key!r}")

    def test_the_file_is_decoded_as_file_read_all_text_async_decodes_it(self):
        """UTF-8, or the encoding a byte-order mark names, a bad byte read as U+FFFD — the declaration ignored, since
        XmlSerializer reads the text through a StringReader. Each case as a .NET build read it that way."""
        fields = "<fields><field name='Id'/></fields>"
        cases = [
            (b"<?xml version='1.0' encoding='bogus-enc'?><entity><primarykey>Id</primarykey>" + fields.encode()
             + b"</entity>", "Id", ["Id"]),
            (b"<?xml version='1.0' encoding='ISO-8859-1'?><entity><primarykey>Id\xe9</primarykey><fields>"
             b"<field name='Id\xe8'/></fields></entity>", "Id�", ["Id�"]),
            (b"<?xml version='1.0' encoding='ISO-8859-1'?><entity><primarykey>A\xe9</primarykey><fields>"
             b"<field name='A\xe9'/><field name='A\xe8'/></fields></entity>", "A�", ["A�", "A�"]),
            (b"<entity><primarykey>I\xe2\x82d</primarykey>" + fields.encode() + b"</entity>", "I�d", ["Id"]),
            (b"\xef\xbb\xbf<?xml version='1.0' encoding='UTF-16'?><entity>" + fields.encode() + b"</entity>",
             None, ["Id"]),
            (b"\xff\xfe" + ("<?xml version='1.0' encoding='utf-8'?><entity><primarykey>Id</primarykey>" + fields
                            + "</entity>").encode("utf-16-le"), "Id", ["Id"]),
            (b"\xff\xfe\x00\x00" + ("<entity><primarykey>Id</primarykey>" + fields + "</entity>").encode("utf-32-le"),
             "Id", ["Id"]),
            (b"\x00\x00\xfe\xff" + ("<entity><primarykey>Id</primarykey>" + fields + "</entity>").encode("utf-32-be"),
             "Id", ["Id"]),
        ]
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        path = os.path.join(tmp, "settings.xml")
        for data, key, names in cases:
            with open(path, "wb") as out:
                out.write(data)
            read = model.read_entity(path)
            self.assertEqual((read[0], [field.name for field in read[1]]), (key, names), repr(data))

    def test_only_a_field_directly_under_fields_is_one(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        path = os.path.join(tmp, "settings.xml")
        with open(path, "w", encoding="utf-8") as out:
            out.write("<entity><primarykey>Id</primarykey><other><field name='Id'/></other>"
                      "<fields><field name='Id' type='Text'/></fields></entity>")
        self.assertEqual(model.read_entity(path), ("Id", [model.EntityField("Id", "Text", None, None, False)]))

    def test_a_file_that_holds_a_dtd_is_not_read(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp)
        path = os.path.join(tmp, "settings.xml")
        with open(path, "w", encoding="utf-8") as out:
            out.write("<!DOCTYPE entity><entity><primarykey>Id</primarykey><fields><field name='Id'/></fields></entity>")
        self.assertIsNone(model.read_entity(path))


class Trees(unittest.TestCase):
    def test_fields(self):
        tree = ET.ElementTree(ET.fromstring(SETTINGS))
        self.assertEqual(set(model.fields(tree)), {"Id", "Name"})
        self.assertEqual(model.fields(tree)["Name"][0], "Text")

    def test_cells_on_the_bound_paths_only_including_a_custom_one(self):
        form = ET.fromstring(
            "<form><tabs><tab><sections><section>"
            "<rows><row><cell name='Name'/><cell name='control_x'><content>hi</content></cell><cell/></row></rows>"
            "<cells><cell name='Unbound'/></cells>"
            "</section></sections></tab></tabs>"
            "<hidden><cell name='Id'/></hidden></form>")
        self.assertEqual([(name, custom) for name, _, custom in model.cells(ET.ElementTree(form))],
                         [("Name", False), ("control_x", True), ("Id", False)])

    def test_no_cell_is_bound_when_the_form_has_no_tabs(self):
        """Form.InitFields returns early when `Tabs` is null — an absent `<tabs>`, not an empty one."""
        no_tabs = ET.fromstring("<form><hidden><cell name='Id'/></hidden></form>")
        empty_tabs = ET.fromstring("<form><tabs/><hidden><cell name='Id'/></hidden></form>")
        self.assertEqual(model.cells(ET.ElementTree(no_tabs)), [])
        self.assertEqual([name for name, _, _ in model.cells(ET.ElementTree(empty_tabs))], ["Id"])


class Traces(Base):
    def test_a_resolution_trace_names_the_value_owner_scope_app_and_result(self):
        os.environ["DEBUG"] = "1"
        self.addCleanup(os.environ.pop, "DEBUG", None)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            model.resolve_table("OnlyA", self.base, self.root, app="b")
            model.resolve_lookup_dialog("", self.app, self.root)
        lines = err.getvalue().splitlines()
        table = next(line for line in lines if line.startswith("DEBUG [model.resolve_table]"))
        for key in ("name=OnlyA", "owner=webasm", "scope=selected", "app=b", "result=Unresolved"):
            self.assertIn(key, table)
        self.assertTrue(any(line.startswith("DEBUG [model.resolve_lookup_dialog] empty") for line in lines), lines)


if __name__ == "__main__":
    unittest.main()
