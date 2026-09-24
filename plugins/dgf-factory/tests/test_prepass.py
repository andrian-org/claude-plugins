"""The NJsonSchema inheritance pre-pass (ADR 0015 §4) — tested before any other JSON check."""

import copy
import json
import unittest
from pathlib import Path

from tests import helpers
from lib import prepass

FIXTURES = helpers.FIXTURES / "unit" / "prepass"
VENDORED = helpers.PLUGIN_ROOT / "knowledge" / "schemas" / "json"


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class MergeShape(unittest.TestCase):
    def setUp(self):
        self.schema = load("schema.json")
        self.merged = prepass.merge(self.schema)

    def test_root_is_one_object(self):
        self.assertNotIn("allOf", self.merged)
        self.assertEqual(set(self.merged["properties"]), {"Type", "Name", "Label", "Placeholder"})
        self.assertIs(self.merged["additionalProperties"], False)

    def test_required_is_the_union(self):
        self.assertEqual(self.merged["required"], ["Type"])

    def test_derived_overrides_base(self):
        self.assertEqual(self.merged["properties"]["Name"].get("maxLength"), 20)

    def test_definitions_are_merged_too(self):
        middle = self.merged["definitions"]["MiddleBase"]
        self.assertNotIn("allOf", middle)
        self.assertEqual(set(middle["properties"]), {"Type", "Name", "Label"})

    def test_siblings_of_allof_survive(self):
        self.assertEqual(self.merged["title"], "LeafConfiguration")
        self.assertEqual(self.merged["$schema"], "http://json-schema.org/draft-04/schema#")

    def test_input_is_not_mutated(self):
        self.assertEqual(self.schema, load("schema.json"))

    def test_non_inheritance_allof_is_untouched(self):
        schema = {"allOf": [{"minLength": 1}, {"maxLength": 3}]}
        self.assertEqual(prepass.merge(schema), schema)

    def test_cycle_terminates(self):
        schema = {"definitions": {
            "A": {"allOf": [{"$ref": "#/definitions/B"}, {"type": "object", "properties": {"a": {}}}]},
            "B": {"allOf": [{"$ref": "#/definitions/A"}, {"type": "object", "properties": {"b": {}}}]},
        }, "$ref": "#/definitions/A"}
        merged = prepass.merge(copy.deepcopy(schema))
        self.assertIn("definitions", merged)


@unittest.skipUnless(helpers.have_dependencies(), "lxml / jsonschema not installed")
class MergedSchemaValidates(unittest.TestCase):
    """The fixtures through a plain Draft4Validator: what the merge alone decides."""

    def errors(self, instance_name):
        import jsonschema
        validator = jsonschema.Draft4Validator(prepass.merge(load("schema.json")))
        return list(validator.iter_errors(load(instance_name)))

    def test_inherited_properties_pass(self):
        self.assertEqual(self.errors("inherited-pass.json"), [])

    def test_one_unknown_property_is_one_error(self):
        errors = self.errors("unknown-property-fail.json")
        self.assertEqual([e.validator for e in errors], ["additionalProperties"])
        self.assertIn("Colour", errors[0].message)

    def test_required_from_the_base_is_enforced(self):
        errors = self.errors("required-from-base-fail.json")
        self.assertEqual([e.validator for e in errors], ["required"])

    def test_unmerged_schema_rejects_inherited_properties(self):
        # The reason the pre-pass exists: each allOf branch evaluates on its own.
        import jsonschema
        validator = jsonschema.Draft4Validator(load("schema.json"))
        self.assertTrue(list(validator.iter_errors(load("inherited-pass.json"))))


class VendoredSet(unittest.TestCase):
    def test_every_vendored_schema_merges(self):
        files = sorted(VENDORED.glob("*.json"))
        self.assertEqual(len(files), 69)
        inheriting = 0
        for path in files:
            schema = json.loads(path.read_text(encoding="utf-8"))
            merged = prepass.merge(schema)
            if prepass.is_inheritance(schema.get("allOf"), schema):
                inheriting += 1
                self.assertNotIn("allOf", merged, path.name)
                self.assertIsInstance(merged.get("properties"), dict, path.name)
        self.assertGreater(inheriting, 50)

    def test_no_inheritance_allof_survives_anywhere(self):
        for path in sorted(VENDORED.glob("*.json")):
            merged = prepass.merge(json.loads(path.read_text(encoding="utf-8")))
            self.assertEqual(prepass.count_inheritance(merged), 0, path.name)


if __name__ == "__main__":
    unittest.main()
