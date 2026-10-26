"""scripts/lib/runtime.py — the switch into the project's virtual environment (ADR 0031 §7)."""

import importlib
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests import helpers
from lib import runtime

ENTRY_GUARD = re.compile(r'\Aif __name__ == "__main__":\n    from lib import runtime; runtime\.use_project_venv\(\)\n')


def entry_scripts():
    return sorted(p for p in helpers.SCRIPTS.glob("*.py") if '__name__ == "__main__"' in p.read_text(encoding="utf-8"))


class Switch(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, ignore_errors=True))
        patcher = mock.patch.dict(os.environ, {}, clear=False)
        patcher.start()
        self.addCleanup(patcher.stop)
        for key in ("DGF_NO_VENV", "DGF_IN_VENV"):
            os.environ.pop(key, None)

    def make_venv(self, windows=False):
        python = self.tmp / ".venv" / ("Scripts/python.exe" if windows else "bin/python")
        python.parent.mkdir(parents=True)
        python.write_text("")
        return python

    def run_switch(self, windows=False):
        with mock.patch.object(runtime, "runtime_root", return_value=self.tmp), \
                mock.patch.object(runtime, "_windows", return_value=windows), \
                mock.patch.object(runtime.os, "execve") as execve, \
                mock.patch.object(runtime.subprocess, "run") as run:
            run.return_value.returncode = 7
            try:
                runtime.use_project_venv(["script.py", "--flag"])
                code = None
            except SystemExit as exc:
                code = exc.code
        return execve, run, code

    def test_no_venv_runs_as_is(self):
        execve, run, code = self.run_switch()
        execve.assert_not_called()
        run.assert_not_called()
        self.assertIsNone(code)

    def test_a_venv_is_exec_d_with_the_same_arguments(self):
        python = self.make_venv()
        execve, _, _ = self.run_switch()
        execve.assert_called_once()
        target, args, env = execve.call_args.args
        self.assertEqual(target, str(python))
        self.assertEqual(args, [str(python), "script.py", "--flag"])
        self.assertEqual(env["DGF_IN_VENV"], "1")

    def test_windows_runs_a_child_and_keeps_its_exit_code(self):
        self.make_venv(windows=True)
        execve, run, code = self.run_switch(windows=True)
        execve.assert_not_called()
        run.assert_called_once()
        self.assertEqual(code, 7)

    def test_dgf_no_venv_disables_it(self):
        self.make_venv()
        os.environ["DGF_NO_VENV"] = "1"
        execve, _, _ = self.run_switch()
        execve.assert_not_called()

    def test_the_loop_guard_stops_a_second_switch(self):
        self.make_venv()
        os.environ["DGF_IN_VENV"] = "1"
        execve, _, _ = self.run_switch()
        execve.assert_not_called()

    def test_already_inside_does_not_switch(self):
        self.make_venv()
        with mock.patch.object(runtime.sys, "prefix", str(self.tmp / ".venv")):
            execve, _, _ = self.run_switch()
        execve.assert_not_called()


class EntryScripts(unittest.TestCase):
    def test_every_entry_script_switches_first_and_only_under_main(self):
        scripts = entry_scripts()
        self.assertGreaterEqual(len(scripts), 13)
        for path in scripts:
            text = path.read_text(encoding="utf-8")
            body = re.sub(r'\A(#![^\n]*\n)?"""[\s\S]*?"""\n\n', "", text, count=1)
            self.assertRegex(body, ENTRY_GUARD, path.name)

    def test_importing_an_entry_script_does_not_switch(self):
        with mock.patch.object(runtime, "use_project_venv") as switch:
            sys.modules.pop("route_means", None)
            importlib.import_module("route_means")
        switch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
