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


def read_as_component_json(path):
    """True for a *.json a walk should validate: under FM/_COMPONENTS/, or outside every workspace.

    Component JSON is read only from a workspace's FM/_COMPONENTS/ (knowledge/json-reader.md
    §4); a JSON file elsewhere under FM/ is read by no loader, so it is not configuration.
    Nor is one inside a workspace but outside its FM/ — a chart's GeoJSON under `<workspace>/maps/`,
    since DGF 1.1.16 — which the API serves as a static workspace file (knowledge/composition-specs.md
    §3). A file outside every workspace is a draft, validated by its own `type`. Split from the
    absolute path, so a walk started inside FM/ sees the same folders.
    """
    parts = Path(os.path.abspath(path)).parts
    if "FM" not in parts:
        return not _inside_workspace(Path(os.path.abspath(path)))
    last_fm = len(parts) - 1 - parts[::-1].index("FM")
    below = parts[last_fm + 1:]
    return len(below) > 1 and below[0] == "_COMPONENTS"


def _inside_workspace(path):
    """True when an ancestor of `path` is a workspace: a directory holding an `FM/` directory."""
    for ancestor in path.parents:
        if (ancestor / "FM").is_dir():
            report.debug("cli.collect", "inside a workspace, outside its FM/", file=path, workspace=ancestor)
            return True
    return False


def collect(paths, want_json=True, want_xml=True):
    """Files named on the command line, directories walked for validator inputs.

    A named file is always returned. A walk returns the legacy artifact files and
    the *.json files read_as_component_json() accepts.
    """
    names = artifact_names() if want_xml else set()
    found, skipped = [], 0
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
                candidate = Path(dirpath) / name
                if name in names:
                    found.append(candidate)
                elif want_json and name.endswith(".json"):
                    if read_as_component_json(candidate):
                        found.append(candidate)
                    else:
                        skipped += 1
                        report.debug("cli.collect", "skipped: read by no loader", file=candidate)
    report.debug("cli.collect", "collected", files=len(found), skipped_json=skipped)
    return found


def display(path):
    """A path for the report: relative to the working directory when it can be."""
    try:
        return str(Path(path).resolve().relative_to(Path.cwd()))
    except ValueError:
        return str(path)
