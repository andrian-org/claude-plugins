"""runtime.py — run under the project's virtual environment when it has one.

`dgf-factory setup` installs the validators' dependencies into `<runtime>/.venv`,
where the runtime root is the folder that holds `scripts/`: `.dgf-factory/runtime`
in a project, the repository root for a contributor (ADR 0031 §6-7). A skill runs
`python3 "<runtime>/scripts/<x>.py"`, so the first thing an entry script does is
re-run itself under that environment's interpreter.

Stdlib only, and nothing from `lib/`, so the stdlib-only scripts can load it by
path. Call it from an entry script's first lines, only under `__main__`, before
any other `from lib import …`: four lib modules import lxml or jsonschema at top
level, and a test that imports the script must never switch interpreter.

  DGF_NO_VENV=1   never switch
  DGF_IN_VENV=1   set on the re-run, so a broken environment cannot loop
"""

import os
import subprocess
import sys
from pathlib import Path

VENV = ".venv"


def _trace(message):
    if os.environ.get("DEBUG") or os.environ.get("LOG_LEVEL") == "debug":
        print(f"DEBUG [runtime.use_project_venv] {message}", file=sys.stderr)


def _windows():
    return os.name == "nt"


def runtime_root():
    """The folder that holds `scripts/`: two levels above this file."""
    return Path(__file__).resolve().parents[2]


def venv_python(root):
    """The environment's interpreter under `root`, or None when there is none."""
    venv = Path(root) / VENV
    candidate = venv / "Scripts" / "python.exe" if _windows() else venv / "bin" / "python"
    return candidate if candidate.is_file() else None


def _inside(venv):
    """True when the running interpreter belongs to `venv`. A venv's python is often a
    symlink to the base interpreter, so compare prefixes, never resolved executables."""
    try:
        return Path(sys.prefix).resolve() == venv.resolve()
    except OSError:
        return False


def use_project_venv(argv=None):
    """Re-run this script under the project environment, or return to run as is."""
    if os.environ.get("DGF_NO_VENV") == "1":
        _trace("DGF_NO_VENV=1; using " + sys.executable)
        return
    root = runtime_root()
    python = venv_python(root)
    if python is None:
        _trace(f"no project venv at {root / VENV}; using {sys.executable}")
        return
    if _inside(root / VENV):
        _trace(f"already in {root / VENV}")
        return
    if os.environ.get("DGF_IN_VENV") == "1":
        _trace(f"DGF_IN_VENV=1 but running {sys.executable}; not switching again")
        return
    args = [str(python)] + list(sys.argv if argv is None else argv)
    env = dict(os.environ, DGF_IN_VENV="1")
    _trace(f"re-exec into {python}")
    sys.stdout.flush()
    sys.stderr.flush()
    if _windows():
        # execv on Windows starts a new process and returns at once, losing the exit code
        raise SystemExit(subprocess.run(args, env=env).returncode)
    os.execve(str(python), args, env)
