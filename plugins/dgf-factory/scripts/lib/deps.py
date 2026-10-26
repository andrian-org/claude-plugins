"""deps.py — the validators' import guard.

The validators need lxml (XSD family) and jsonschema (JSON family).
`dgf-factory setup` installs them into the project's `<runtime>/.venv`, and every
entry script switches to it first (lib/runtime.py). A missing one is still
reported, never passed: exit 3 with the exact install command (ADR 0031 §6-8).
Every validator calls require() before importing any module that uses either
package.
"""

import os
import sys
from pathlib import Path

from . import report

# (import name, distribution name) — the distribution is what pip installs.
REQUIRED = (("lxml.etree", "lxml"), ("jsonschema", "jsonschema"))

REQUIREMENTS = Path(__file__).resolve().parent.parent / "requirements.txt"
RUNTIME_ROOT = REQUIREMENTS.parent.parent
SETUP_HINT = "or re-run `dgf-factory setup`"


def in_virtualenv():
    return sys.prefix != sys.base_prefix


def installed(root=None):
    """True in a project: the runtime sits beside the receipt `dgf-factory setup` wrote."""
    return ((root or RUNTIME_ROOT).parent / "install.json").is_file()


def venv_python(root=None):
    venv = (root or RUNTIME_ROOT) / ".venv"
    return venv / "Scripts" / "python.exe" if os.name == "nt" else venv / "bin" / "python"


def install_command():
    """In a project, the install into its own environment; otherwise the command for this
    interpreter, where `pip install --user` fails inside a venv."""
    if installed():
        return (f'python3 -m venv "{RUNTIME_ROOT / ".venv"}" && '
                f'"{venv_python()}" -m pip install --require-hashes -r "{REQUIREMENTS}"')
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
                f"cannot run.\nInstall with:\n  {install_command()}"
                + (f"\n  {SETUP_HINT}" if installed() else ""))
