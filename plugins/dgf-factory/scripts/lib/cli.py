"""cli.py — what the validator entry points share: argument parsing and file walking.

argparse exits with 2 on a bad argument, and 2 means "warnings" here; this
parser exits with 3, the usage-error code, through report.fail(). Stdlib only.
"""

import argparse
import os
from pathlib import Path

from . import knowledge, report


class Parser(argparse.ArgumentParser):
    def error(self, message):
        report.fail(report.EXIT_USAGE, f"{self.format_usage().strip()}\n{self.prog}: error: {message}")


def parser(prog, description):
    built = Parser(prog=prog, description=description)
    built.add_argument("--verbose", action="store_true", help="trace to stderr (same as DEBUG=1)")
    return built


def artifact_names():
    """The legacy artifact filenames the runtime loaders open (legacy-artifacts table)."""
    return {row["Filename"] for row in knowledge.load("legacy-artifacts")}


def collect(paths, want_json=True, want_xml=True):
    """Files named on the command line, directories walked for validator inputs."""
    names = artifact_names() if want_xml else set()
    found = []
    for raw in paths:
        path = Path(raw)
        if path.is_file():
            found.append(path)
            continue
        if not path.is_dir():
            report.fail(report.EXIT_USAGE, f"not a file or directory: {raw}")
        for dirpath, dirnames, filenames in os.walk(path):
            dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
            for name in sorted(filenames):
                if name in names or (want_json and name.endswith(".json")):
                    found.append(Path(dirpath) / name)
    report.debug("cli.collect", "collected", files=len(found))
    return found


def display(path):
    """A path for the report: relative to the working directory when it can be."""
    try:
        return str(Path(path).resolve().relative_to(Path.cwd()))
    except ValueError:
        return str(path)
