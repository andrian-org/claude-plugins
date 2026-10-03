"""deps.py — the validators' import guard.

The validators need lxml (XSD family) and jsonschema (JSON family). A plugin
cannot install its own dependencies, so a missing one is reported, never passed:
exit 3 with the exact install command (ADR 0015 §6-7). Every validator calls
require() before importing any module that uses either package.
"""

import sys
from pathlib import Path

from . import report

# (import name, distribution name) — the distribution is what pip installs.
REQUIRED = (("lxml.etree", "lxml"), ("jsonschema", "jsonschema"))

REQUIREMENTS = Path(__file__).resolve().parent.parent / "requirements.txt"


def in_virtualenv():
    return sys.prefix != sys.base_prefix


def install_command():
    """The command for this interpreter. `pip install --user` fails inside a venv."""
    user = "" if in_virtualenv() else " --user"
    return f'python3 -m pip install{user} --require-hashes -r "{REQUIREMENTS}"'


def missing():
    """Distribution names that cannot be imported, in REQUIRED order."""
    absent = []
    for module, dist in REQUIRED:
        try:
            __import__(module)
        except ImportError as exc:
            report.debug("deps.missing", "import failed", module=module, error=exc)
            absent.append(dist)
    return absent


def require():
    """Return when every dependency imports; otherwise exit 3 with the fix."""
    absent = missing()
    report.debug("deps.require", "probed", missing=",".join(absent) or "none")
    if not absent:
        return
    report.fail(report.EXIT_USAGE,
                f"ERROR DEPENDENCY_MISSING {', '.join(absent)} not installed — the validators "
                f"cannot run.\nInstall with:\n  {install_command()}")
