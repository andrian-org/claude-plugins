"""PLAN-FORMAT.md's worked example passes check_plan.py, and prints what the text says it prints.

`/dgf-plan` writes plans by that example, so an example the checks refuse teaches the model to
write plans the gate refuses. This keeps `.ai-factory/RULES.md` rule 4 for `/dgf-plan` by test
rather than by hand (roadmap follow-up "A test for PLAN-FORMAT.md's worked example").
"""

import re
import shutil
import tempfile
import unittest
from pathlib import Path

from tests import helpers
import check_plan

FORMAT = helpers.PLUGIN_ROOT / "skills" / "dgf-plan" / "references" / "PLAN-FORMAT.md"
# The estate the example describes: an application workspace holding the form it edits, and the base.
ROOT_FILES = {
    "zims/FM/_DATA/Inspection/_forms/Apply/_form.xml": "<form/>\n",
    "webasm/FM/_COMPONENTS/.keep": "",
}


def worked_example():
    """The fenced Markdown block under `## A worked example`."""
    text = FORMAT.read_text(encoding="utf-8")
    section = text.split("## A worked example", 1)[1]
    match = re.search(r"^```markdown\n(.*?)^```$", section, re.MULTILINE | re.DOTALL)
    if not match:
        raise AssertionError("PLAN-FORMAT.md has no ```markdown block under `## A worked example`")
    return match.group(1)


class WorkedExample(unittest.TestCase):
    def setUp(self):
        tmp = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, tmp)
        self.root = helpers.make_root(tmp / "root", ROOT_FILES)
        example = worked_example()
        branch = re.search(r"^branch: (\S+)$", example, re.MULTILINE).group(1)
        # a full plan's file stem is its branch with `/` replaced by `-` (PLAN-FORMAT.md §"Where the file goes")
        self.plan = self.root / ".dgf-factory" / "plans" / (branch.replace("/", "-") + ".md")
        self.plan.parent.mkdir(parents=True)
        self.plan.write_text(example, encoding="utf-8")

    def test_it_has_no_error_or_warning(self):
        rep, _ = check_plan.check(self.plan, self.root, False)
        self.assertEqual([f"{f.code} {f.message}" for f in rep.findings], [])

    def test_it_prints_one_task_line_per_task_and_its_progress(self):
        _, lines = check_plan.check(self.plan, self.root, False)
        self.assertEqual(len([line for line in lines if line.startswith("TASK: ")]), 3)
        self.assertIn("PROGRESS: 0/3", lines)


if __name__ == "__main__":
    unittest.main()
