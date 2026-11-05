"""plan_layers.py: the next layer a coordinator may dispatch, and what is held serial (ADR 0033 §3)."""

import shutil
import tempfile
import unittest
from pathlib import Path

from tests import helpers
import check_plan
import plan_layers
from lib import plan

HEADER = ["plan_format: 1", "mode: full", "branch: feature/x", "created: 2026-11-03", "affects_workspaces: [zims]"]


def task(number, files="", deletes="", depends=(), checked=False):
    after = f" (depends on {', '.join(map(str, depends))})" if depends else ""
    lines = [f"- [{'x' if checked else ' '}] Task {number}: task {number}{after}", "  - kind: config"]
    if files:
        lines.append(f"  - files: {files}")
    if deletes:
        lines.append(f"  - deletes: {deletes}")
    return "\n".join(lines)


def plan_text(tasks, header=HEADER, body=""):
    return "---\n" + "\n".join(header) + "\n---\n\n# Plan\n\n" + body + "## Tasks\n\n" + "\n".join(tasks) + "\n"


def f(n):
    return f"zims/FM/_COMPONENTS/Button/b{n}.json"


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.root = self.tmp / "root"
        (self.root / ".dgf-factory" / "plans").mkdir(parents=True)

    def write(self, text, name="feature-x.md"):
        path = self.root / ".dgf-factory" / "plans" / name
        path.write_text(text, encoding="utf-8")
        return path

    def layers(self, tasks=None, text=None, cap=plan_layers.DEFAULT_MAX_PARALLEL, path=None):
        path = path or self.write(text if text is not None else plan_text(tasks))
        self.rep, self.lines = plan_layers.layers(path, cap)
        return self.lines

    def line(self, prefix):
        return next(line for line in self.lines if line.startswith(prefix))

    def codes(self):
        return [found.code for found in self.rep.findings]


class Layers(Base):
    def test_independent_tasks_form_one_parallel_batch(self):
        self.layers([task(1, f(1)), task(2, f(2)), task(3, f(3), depends=[1, 2])])
        self.assertEqual(self.line("READY:"), "READY: 1,2")
        self.assertEqual(self.line("PARALLEL:"), "PARALLEL: 1,2")
        self.assertEqual(self.line("REMAINING:"), "REMAINING: 1")
        self.assertIn("progress=0/3", self.line("PLAN:"))
        self.assertEqual(self.codes(), [])
        self.assertEqual(self.rep.checks_run, ["plan-parse", "layers"])

    def test_ready_means_every_dependency_checked(self):
        self.layers([task(1, f(1), checked=True), task(2, f(2), depends=[1]), task(3, f(3), depends=[2])])
        self.assertEqual(self.line("READY:"), "READY: 2")
        self.assertEqual(self.line("PARALLEL:"), "PARALLEL: 2")
        self.assertEqual(self.line("REMAINING:"), "REMAINING: 1")

    def test_a_batch_of_one(self):
        self.layers([task(1, f(1)), task(2, f(2), depends=[1])])
        self.assertEqual(self.line("PARALLEL:"), "PARALLEL: 1")

    def test_a_shared_file_holds_the_later_task_serial(self):
        self.layers([task(1, f"{f(1)}, {f(2)}"), task(2, f(3), deletes=f(2)), task(3, f(4))])
        self.assertEqual(self.line("PARALLEL:"), "PARALLEL: 1,3")
        self.assertEqual(self.line("SERIAL:"), f"SERIAL: 2 — shares {f(2)} with task 1")
        self.assertEqual(self.codes(), ["LAYERS_SERIAL"])
        self.assertEqual(self.rep.exit_code(), 0, "serial is INFO")

    def test_paths_that_differ_only_in_case_are_one_file(self):
        self.layers([task(1, f(1)), task(2, f(1).upper())])
        self.assertEqual(self.line("PARALLEL:"), "PARALLEL: 1")
        self.assertIn("shares", self.line("SERIAL:"))

    def test_paths_that_differ_only_in_unicode_normalisation_are_one_file(self):
        composed, decomposed = "zims/FM/_DATA/Caf\u00e9/settings.xml", "zims/FM/_DATA/Cafe\u0301/settings.xml"
        self.layers([task(1, composed), task(2, decomposed.upper())])
        self.assertEqual(self.line("PARALLEL:"), "PARALLEL: 1")
        self.assertIn(f"SERIAL: 2 — shares {decomposed.upper()} ({composed}) with task 1", self.lines)

    def test_a_folder_and_a_path_inside_it_never_run_at_once(self):
        folder = "zims/FM/_PROCESS/P"
        self.layers([task(1, f"{folder}/process.xml"), task(2, deletes=folder), task(3, f(3))])
        self.assertEqual(self.line("PARALLEL:"), "PARALLEL: 1,3")
        self.assertEqual(self.line("SERIAL:"), f"SERIAL: 2 — declares {folder}, a folder holding {folder}/process.xml "
                                               f"of task 1")
        self.layers([task(1, folder + "/"), task(2, f"{folder.lower()}/_workflow.xml")])
        self.assertEqual(self.line("PARALLEL:"), "PARALLEL: 1")
        self.assertEqual(self.line("SERIAL:"), f"SERIAL: 2 — declares {folder.lower()}/_workflow.xml, inside "
                                               f"{folder}/ of task 1")

    def test_a_shared_prefix_that_is_no_folder_runs_at_once(self):
        self.layers([task(1, "zims/FM/_DATA/A/settings.xml"), task(2, "zims/FM/_DATA/AB/settings.xml")])
        self.assertEqual(self.line("PARALLEL:"), "PARALLEL: 1,2")

    def test_a_task_that_declares_no_files_is_held(self):
        self.layers([task(1), task(2, f(2))])
        self.assertEqual(self.line("PARALLEL:"), "PARALLEL: 2")
        self.assertEqual(self.line("SERIAL:"), "SERIAL: 1 — declares no files")

    def test_the_cap_holds_the_rest(self):
        self.layers([task(n, f(n)) for n in range(1, 6)], cap=2)
        self.assertEqual(self.line("PARALLEL:"), "PARALLEL: 1,2")
        self.assertEqual([l for l in self.lines if l.startswith("SERIAL:")],
                         [f"SERIAL: {n} — over --max-parallel 2" for n in (3, 4, 5)])

    def test_the_default_cap_is_four(self):
        self.layers([task(n, f(n)) for n in range(1, 7)])
        self.assertEqual(self.line("PARALLEL:"), "PARALLEL: 1,2,3,4")

    def test_a_complete_plan_is_clean(self):
        self.layers([task(1, f(1), checked=True), task(2, f(2), checked=True)])
        self.assertEqual(self.line("READY:"), "READY: none")
        self.assertEqual(self.line("PARALLEL:"), "PARALLEL: none")
        self.assertEqual(self.line("REMAINING:"), "REMAINING: 0")
        self.assertEqual(self.rep.exit_code(), 0)


class Graph(Base):
    def test_a_cycle_is_blocked_and_names_its_tasks(self):
        self.layers([task(1, f(1)), task(2, f(2), depends=[3]), task(3, f(3), depends=[2]), task(4, f(4), depends=[3])])
        self.assertEqual(self.codes(), ["LAYERS_CYCLE"])
        self.assertIn("Task 2, Task 3, Task 4 can never become ready", self.rep.findings[0].message)
        self.assertEqual(self.rep.exit_code(), 1)
        self.assertEqual(self.line("READY:"), "READY: 1")

    def test_a_task_depending_on_itself_is_a_cycle(self):
        self.layers([task(1, f(1), depends=[1])])
        self.assertEqual(self.codes(), ["LAYERS_CYCLE"])

    def test_a_missing_dependency_is_blocked(self):
        self.layers([task(1, f(1)), task(2, f(2), depends=[9])])
        self.assertEqual(self.codes(), ["LAYERS_CYCLE"])
        self.assertIn("Task 2 depends on Task 9, which does not exist", self.rep.findings[0].message)
        self.assertEqual(self.line("REMAINING:"), "REMAINING: 1")

    def test_a_checked_dependency_inside_an_old_cycle_does_not_block(self):
        self.layers([task(1, f(1), depends=[2], checked=True), task(2, f(2), depends=[1], checked=True),
                     task(3, f(3), depends=[1])])
        self.assertEqual(self.codes(), [])
        self.assertEqual(self.line("READY:"), "READY: 3")


class Formats(Base):
    def test_an_unreadable_plan_is_exit_3(self):
        self.layers(text="# no frontmatter\n")
        self.assertEqual(self.codes(), ["PLAN_UNREADABLE"])
        self.assertEqual(self.rep.exit_code(), 3)

    def test_an_unsupported_format_is_exit_3(self):
        self.layers(text=plan_text([task(1, f(1))], header=["plan_format: 2"] + HEADER[1:]))
        self.assertEqual(self.codes(), ["PLAN_FORMAT_UNSUPPORTED"])
        self.assertEqual(self.rep.exit_code(), 3)

    def test_the_format_constant_lives_in_lib_plan_and_check_plan_reexports_it(self):
        self.assertEqual(plan.SUPPORTED_FORMAT, "1")
        self.assertIs(check_plan.SUPPORTED_FORMAT, plan.SUPPORTED_FORMAT)

    def test_an_ultra_bundle_names_each_ready_tasks_phase_file(self):
        bundle = self.root / ".dgf-factory" / "plans" / "feature-x"
        bundle.mkdir()
        body = "## Phase Index\n\n- [Phase 1](phase-1.md)\n- [Phase 2](phase-2.md)\n\n"
        header = HEADER[:1] + ["mode: ultra"] + HEADER[2:]
        (bundle / "index.md").write_text(plan_text([task(1, f(1)), task(2, f(2)), task(3, f(3), depends=[1])],
                                                   header=header, body=body), encoding="utf-8")
        (bundle / "phase-1.md").write_text("# Phase 1\n\n## Task 1\n\nsteps\n\n## Task 3\n\nsteps\n", encoding="utf-8")
        (bundle / "phase-2.md").write_text("# Phase 2\n\n## Task 2\n\nsteps\n", encoding="utf-8")
        self.layers(path=bundle)
        phases = [l for l in self.lines if l.startswith("PHASE:")]
        self.assertEqual(len(phases), 2, self.lines)
        self.assertTrue(phases[0].startswith("PHASE: 1 ") and phases[0].endswith("phase-1.md"))
        self.assertTrue(phases[1].startswith("PHASE: 2 ") and phases[1].endswith("phase-2.md"))
        self.assertEqual(self.line("PARALLEL:"), "PARALLEL: 1,2")


class Cli(Base):
    def run_cli(self, *args):
        return helpers.run_cli("plan_layers.py", "--workspaces-root", self.root, *args)

    def test_the_output_and_its_exit(self):
        path = self.write(plan_text([task(1, f(1)), task(2, f(1))]))
        code, out, _ = self.run_cli("--plan", path)
        self.assertEqual(code, 0, out)
        lines = out.splitlines()
        self.assertEqual(lines[0], "Plan layers")
        for expected in ("READY: 1,2", "PARALLEL: 1", f"SERIAL: 2 — shares {f(1)} with task 1", "REMAINING: 0",
                         "CHECKS RUN: plan-parse, layers"):
            self.assertIn(expected, lines)
        self.assertIn("INFO LAYERS_SERIAL", out)
        self.assertEqual(lines[-1], "CLEAN")

    def test_a_cycle_exits_1(self):
        path = self.write(plan_text([task(1, f(1), depends=[2]), task(2, f(2), depends=[1])]))
        self.assertEqual(self.run_cli("--plan", path)[0], 1)

    def test_max_parallel_out_of_range_is_a_usage_error(self):
        path = self.write(plan_text([task(1, f(1))]))
        for value in ("0", "9", "two", "-1"):
            code, _, err = self.run_cli("--plan", path, "--max-parallel", value)
            self.assertEqual(code, 3, value)
        self.assertEqual(self.run_cli("--plan", path, "--max-parallel", "8")[0], 0)

    def test_a_missing_root_is_a_usage_error(self):
        path = self.write(plan_text([task(1, f(1))]))
        code, _, _ = helpers.run_cli("plan_layers.py", "--workspaces-root", self.tmp / "nowhere", "--plan", path)
        self.assertEqual(code, 3)

    def test_it_runs_without_the_validator_dependencies(self):
        path = self.write(plan_text([task(1, f(1)), task(2, f(2))]))
        code, out, err = helpers.run_cli_blocking("plan_layers.py", "--workspaces-root", self.root, "--plan", path)
        self.assertEqual(code, 0, out + err)
        self.assertIn("PARALLEL: 1,2", out)

    def test_help_lists_every_flag(self):
        code, out, _ = helpers.run_cli("plan_layers.py", "--help")
        self.assertEqual(code, 0)
        for flag in ("--workspaces-root", "--plan", "--max-parallel", "--verbose"):
            self.assertIn(flag, out)


if __name__ == "__main__":
    unittest.main()
