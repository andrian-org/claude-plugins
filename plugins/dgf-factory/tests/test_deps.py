"""The import guard in scripts/lib/deps.py — runs without lxml or jsonschema."""

import builtins
import contextlib
import io
import sys
import unittest
from unittest import mock

from tests import helpers  # noqa: F401 — puts scripts/ on sys.path
from lib import deps

_REAL_IMPORT = builtins.__import__


def _import_without(*blocked):
    def fake(name, *args, **kwargs):
        if name.split(".")[0] in blocked:
            raise ImportError(f"No module named '{name}'")
        return _REAL_IMPORT(name, *args, **kwargs)
    return fake


class MissingDependency(unittest.TestCase):
    def require_output(self, *blocked):
        err = io.StringIO()
        with mock.patch("builtins.__import__", _import_without(*blocked)), \
                contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as ctx:
            deps.require()
        return ctx.exception.code, err.getvalue()

    def test_missing_lxml_is_exit_3_with_the_command(self):
        code, message = self.require_output("lxml")
        self.assertEqual(code, 3)
        self.assertIn("DEPENDENCY_MISSING lxml", message)
        self.assertIn("--require-hashes -r", message)
        self.assertIn("requirements.txt", message)

    def test_both_missing_are_named(self):
        _, message = self.require_output("lxml", "jsonschema")
        self.assertIn("lxml, jsonschema", message)

    def test_nothing_missing_returns(self):
        if not helpers.have_dependencies():
            self.skipTest("lxml / jsonschema not installed")
        self.assertIsNone(deps.require())


class InstallCommand(unittest.TestCase):
    def test_user_flag_outside_a_venv(self):
        with mock.patch.object(sys, "prefix", sys.base_prefix):
            self.assertIn(" --user ", deps.install_command())

    def test_no_user_flag_inside_a_venv(self):
        with mock.patch.object(sys, "prefix", sys.base_prefix + "-venv"):
            self.assertNotIn("--user", deps.install_command())

    def test_path_is_absolute_and_quoted(self):
        command = deps.install_command()
        self.assertIn(f'"{deps.REQUIREMENTS}"', command)
        self.assertTrue(deps.REQUIREMENTS.is_absolute())

    def test_an_installed_runtime_installs_into_its_own_venv(self):
        with mock.patch.object(deps, "installed", return_value=True):
            command = deps.install_command()
        self.assertNotIn("--user", command)
        self.assertIn(f'-m venv "{deps.RUNTIME_ROOT / ".venv"}"', command)
        self.assertIn(f'"{deps.venv_python()}" -m pip install --require-hashes -r "{deps.REQUIREMENTS}"', command)

    def test_an_installed_runtime_names_setup_in_the_message(self):
        err = io.StringIO()
        with mock.patch.object(deps, "installed", return_value=True), \
                mock.patch("builtins.__import__", _import_without("lxml")), \
                contextlib.redirect_stderr(err), self.assertRaises(SystemExit):
            deps.require()
        self.assertIn("dgf-factory setup", err.getvalue())

    def test_installed_reads_the_receipt_beside_the_runtime(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            runtime_root = Path(tmp) / ".dgf-factory" / "runtime"
            runtime_root.mkdir(parents=True)
            self.assertFalse(deps.installed(runtime_root))
            (runtime_root.parent / "install.json").write_text("{}")
            self.assertTrue(deps.installed(runtime_root))


if __name__ == "__main__":
    unittest.main()
