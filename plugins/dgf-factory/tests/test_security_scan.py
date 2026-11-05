"""scripts/security-scan.sh: its exits follow the contract, and a fully skipped run is offline (ADR 0034 §1)."""

import os
import re
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

from tests import helpers

SCAN = helpers.SCRIPTS / "security-scan.sh"
STEPS = "runtime,deps,secrets,config,code,image,dast,sbom"
# Every tool the scan can call out to: Docker, the network, and each scanner. A stub records its own name and fails.
CALLED_OUT = ("docker", "curl", "trivy", "gitleaks", "semgrep", "npm", "dotnet", "node", "jq")
OPTION = re.compile(r"^\s+(--[a-z-]+)(?:\|[^)]*)?\)", re.MULTILINE)


def stub_bin(folder, log):
    """A folder of stubs for CALLED_OUT, each appending its name to `log` and exiting 1."""
    folder.mkdir()
    for name in CALLED_OUT:
        path = folder / name
        path.write_text(f'#!/bin/sh\necho {name} >> "{log}"\nexit 1\n', encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return folder


def run(*args, path_first=None):
    env = dict(os.environ)
    if path_first:
        env["PATH"] = f"{path_first}{os.pathsep}{env.get('PATH', '')}"
    proc = subprocess.run(["bash", str(SCAN), *map(str, args)], capture_output=True, text=True, env=env)
    return proc.returncode, proc.stdout, proc.stderr


@unittest.skipUnless(shutil.which("bash"), "bash not installed")
class Usage(unittest.TestCase):
    def test_help_exits_0_and_lists_every_option(self):
        code, out, _ = run("--help")
        self.assertEqual(code, 0, out)
        options = OPTION.findall(SCAN.read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(options), 9, options)
        for option in options:
            self.assertRegex(out, rf"(?<![\w-]){re.escape(option)}(?![\w-])", f"--help does not list {option}")

    def test_help_states_the_exit_codes(self):
        _, out, _ = run("--help")
        for code in ("0", "1", "2", "3"):
            self.assertRegex(out, rf"(?m)^\s+{code}\s+\S", f"--help does not say what exit {code} means")

    def test_an_unknown_option_is_a_usage_error(self):
        code, out, err = run("--no-such-option")
        self.assertEqual(code, 3, out + err)
        self.assertIn("--no-such-option", err)

    def test_a_history_that_is_not_a_number_is_a_usage_error(self):
        code, out, err = run("--history", "x")
        self.assertEqual(code, 3, out + err)

    def test_a_severity_that_is_not_a_comma_list_of_words_is_a_usage_error(self):
        for bad in ("HIGH;touch /tmp/x", "HIGH,", ",HIGH", "HIGH CRITICAL", "HIGH,$(id)", "", "HIGH,,LOW"):
            code, out, err = run("--severity", bad, "--path", "/nonexistent-folder-for-the-test")
            self.assertEqual(code, 3, f"{bad!r}: {out}{err}")
            self.assertIn("--severity", err, bad)

    def test_a_severity_list_in_any_case_is_accepted(self):
        code, out, err = run("--severity", "high,Critical", "--path", "/nonexistent-folder-for-the-test")
        self.assertEqual(code, 3, out + err)
        self.assertNotIn("--severity", err)  # it got past the severity check, to the missing folder

    def test_an_option_without_its_value_is_a_usage_error(self):
        code, out, err = run("--path")
        self.assertEqual(code, 3, out + err)

    def test_a_missing_folder_is_a_usage_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "no-such-folder"
            code, out, err = run("--path", missing)
        self.assertEqual(code, 3, out + err)
        self.assertIn(str(missing), err)


@unittest.skipUnless(shutil.which("bash"), "bash not installed")
class FullySkipped(unittest.TestCase):
    """Every step skipped: nothing ran, so the run warns — and it calls out to nothing."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.project = self.tmp / "project"
        self.project.mkdir()
        self.log = self.tmp / "called.log"
        self.stubs = stub_bin(self.tmp / "stubs", self.log)

    def scan(self, out):
        return run("--path", self.project, "--out", out, "--skip", STEPS, path_first=self.stubs)

    def test_it_exits_2_with_warnings_last(self):
        code, out, err = self.scan(self.project / "reports")
        self.assertEqual(code, 2, out + err)
        lines = out.rstrip("\n").splitlines()
        self.assertEqual(lines[-1], "WARNINGS")
        self.assertIn("RESULT: INCOMPLETE (no failures in the checks that ran)", lines)
        self.assertIn("INCOMPLETE: 8 check(s) skipped; see the SKIP rows above.", lines)
        self.assertEqual(len(re.findall(r"(?m)^\s+.+\s+SKIP\s+skipped with --skip ", out)), 8, out)

    def test_it_writes_a_report_under_the_out_folder(self):
        reports = self.project / "reports"
        _, out, _ = self.scan(reports)
        written = sorted(reports.glob("*_security-report.md"))
        self.assertEqual(len(written), 1, out)
        named = [line[len("Report: "):] for line in out.splitlines() if line.startswith("Report: ")]
        self.assertEqual([Path(p).resolve() for p in named], [written[0].resolve()], out)
        self.assertIn("## Result: INCOMPLETE", written[0].read_text(encoding="utf-8"))

    def test_a_report_folder_it_creates_ignores_itself(self):
        reports = self.project / "reports"
        self.scan(reports)
        self.assertEqual((reports / ".gitignore").read_text(encoding="utf-8"), "*\n")

    def test_a_report_folder_that_already_existed_is_left_without_one(self):
        reports = self.project / "reports"
        reports.mkdir()
        self.scan(reports)
        self.assertFalse((reports / ".gitignore").exists())

    def test_the_report_and_raw_output_are_readable_by_the_owner_alone(self):
        reports = self.project / "reports"
        self.scan(reports)
        report = next(reports.glob("*_security-report.md"))
        raw = next(reports.glob("*_raw"))
        for path in [report, raw, *raw.rglob("*")]:
            self.assertEqual(path.stat().st_mode & 0o077, 0, f"{path} is open to group or others")

    def test_it_calls_no_scanner_docker_or_network_tool(self):
        self.scan(self.project / "reports")
        called = self.log.read_text(encoding="utf-8").split() if self.log.exists() else []
        self.assertEqual(called, [], f"a fully skipped run called {called}")


class DockerRuns(unittest.TestCase):
    """What each container may touch, read from the script: the repository read-only, an image the user
    names isolated."""

    TEXT = SCAN.read_text(encoding="utf-8")

    def test_every_mount_of_the_repository_is_read_only(self):
        mounts = re.findall(r'-v "\$REPO":(\S+)', self.TEXT)
        self.assertTrue(mounts, "no docker run mounts the repository")
        self.assertTrue(all(m.endswith(":ro") for m in mounts), mounts)

    def test_the_user_named_image_runs_without_network_capabilities_or_privilege_gain(self):
        runs = [line for line in self.TEXT.splitlines() if 'docker run' in line and '"$1" -c' in line]
        self.assertEqual(len(runs), 1, runs)
        for flag in ("--network none", "--cap-drop ALL", "--security-opt no-new-privileges"):
            self.assertIn(flag, runs[0])


if __name__ == "__main__":
    unittest.main()
