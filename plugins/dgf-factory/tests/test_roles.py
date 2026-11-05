"""scripts/lib/roles.py: the role names a root uses, read as the runtime reads them (ADR 0027 §6)."""

import os
import shutil
import tempfile
import unittest

from tests import helpers
from lib import roles

SITEMAP = ('<map><mapNode name="home" roles="Members"/><mapNode name="cases" roles="Case Officer, Supervisor" '
           'deny="Applicant"/><mapNode name="open" roles=""/></map>\n')


class Inventory(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.root = helpers.make_root(self.tmp, {
            "a/_application.sitemap": SITEMAP,
            "a/FM/_application.sitemap": '<map><mapNode name="x" roles="Ignored"/></map>',
            "a/FM/_COMPONENTS/sitemap.json": '{"routes": [{"metaData": {"requireClaims": [{"name": "entityId"}]}}]}',
            "a/FM/_PROFILE/Main/Cashier/_tree.xml": "<tree/>",
            "a/FM/_PROFILE/Main/Members/_tree.xml": "<tree/>",
            "a/FM/_PROCESS/Case/process.xml": ('<Process><States><State name="S"><OnInit><Task role="CaseOfficer"/>'
                                               '</OnInit></State></States></Process>'),
            "a/FM/_PROCESS/Case/S.xml": '<MultiTaskSettings><TaskGroup role="Reviewer"/></MultiTaskSettings>',
            "webasm/FM/_PROCESS/Broken/process.xml": "<Process><Task role=",
        })
        self.found = roles.inventory(self.root)

    def sources(self, name):
        return set(self.found.get(name, {}))

    def test_each_role_source_is_read(self):
        self.assertEqual(self.sources("Members"), {"sitemap-roles", "profile-group"})
        self.assertEqual(self.sources("Applicant"), {"sitemap-deny"})
        self.assertEqual(self.sources("entityId"), {"sitemap-claims"})
        self.assertEqual(self.sources("Cashier"), {"profile-group"})
        self.assertEqual(self.sources("CaseOfficer"), {"task-role"})
        self.assertEqual(self.sources("Reviewer"), {"taskgroup-role"})

    def test_a_comma_list_is_split_and_trimmed_as_dgf_1_3_tests_it(self):
        # the current pack is DGF 1.3, whose SiteMapManager trims each name and drops empty ones
        self.assertIn("Case Officer", self.found)
        self.assertIn("Supervisor", self.found)
        self.assertNotIn(" Supervisor", self.found)

    def test_an_older_line_splits_untrimmed_through_the_same_code(self):
        # ADR 0036: one codebase, a pack per DGF line; the pack's `Separator` cell says how its runtime splits
        from lib import knowledge
        packs = helpers.load_tool("packs")
        saved = knowledge.KNOWLEDGE_DIR
        self.addCleanup(knowledge.use_dir, saved)
        knowledge.use_dir(packs.pack_dir("1.2"))
        found = roles.inventory(self.root)
        self.assertIn(" Supervisor", found)
        self.assertNotIn("Supervisor", found)

    def test_the_split_rules(self):
        self.assertEqual(roles._split("A, B,,", ","), ["A", " B", "", ""])
        self.assertEqual(roles._split("A, B,,", ", trimmed"), ["A", "B"])
        self.assertEqual(roles._split("A, B", "—"), ["A, B"])
        self.assertEqual(roles._split("", ", trimmed"), [])

    def test_a_dtd_is_refused_so_its_entities_are_never_expanded(self):
        # the billion laughs, kept small enough that an unguarded reader still finishes: 10^5 expansions
        laughs = "".join(f'<!ENTITY l{i} "{"&l%d;" % (i - 1) * 10}">' for i in range(1, 6))
        bomb = (f'<?xml version="1.0"?><!DOCTYPE map [<!ENTITY l0 "lol">{laughs}<!ENTITY r "Smuggled">]>'
                '<map><mapNode name="x" roles="&r;"/><mapNode name="y" roles="&l5;"/></map>\n')
        root = helpers.make_root(os.path.join(self.tmp, "dtd"), {"a/_application.sitemap": bomb,
                                                                 "a/FM/_PROCESS/Case/process.xml": "<Process/>"})
        found = roles.inventory(root)
        self.assertNotIn("Smuggled", found)
        self.assertFalse(any("lol" in name for name in found), sorted(found)[:3])

    def test_an_empty_roles_value_names_no_role(self):
        self.assertNotIn("", self.found)

    def test_the_sitemap_is_read_at_the_workspace_root_and_not_under_fm(self):
        self.assertNotIn("Ignored", self.found)
        self.assertEqual(self.found["Applicant"]["sitemap-deny"], [("a/_application.sitemap", 1)])

    def test_a_profile_group_is_its_folder_name(self):
        self.assertEqual(self.found["Cashier"]["profile-group"], [("a/FM/_PROFILE/Main/Cashier/_tree.xml", None)])

    def test_an_unparsable_file_is_skipped_with_a_trace(self):
        self.assertFalse(any("webasm" in rel for sources in self.found.values() for places in sources.values()
                             for rel, _ in places))
        os.environ["DEBUG"] = "1"
        self.addCleanup(os.environ.pop, "DEBUG", None)
        import contextlib
        import io
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            roles.inventory(self.root)
        self.assertIn("DEBUG [roles.inventory] unparsable", err.getvalue())


if __name__ == "__main__":
    unittest.main()
