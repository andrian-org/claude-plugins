"""helpers.py — shared test plumbing: import path, temp workspaces roots, CLI runner.

Not shipped. Importing this module puts <plugin>/scripts on sys.path once, so a
test imports `lib.<module>` exactly as the validators do. Nothing imports
`scripts.lib…`.
"""

import os
import subprocess
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = PLUGIN_ROOT / "scripts"
TOOLS = PLUGIN_ROOT / "tools"
FIXTURES = Path(__file__).resolve().parent / "fixtures"

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def have_dependencies():
    """True when lxml and jsonschema import — tests that need them skip otherwise."""
    try:
        import jsonschema  # noqa: F401
        import lxml.etree  # noqa: F401
    except ImportError:
        return False
    return True


def make_root(tmp, files):
    """Write {relative path: str | bytes} under `tmp` and return it as a Path."""
    root = Path(tmp)
    for rel, content in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")
    return root


def run_cli(script, *args, env=None, cwd=None):
    """Run a script under scripts/ (or an absolute path) → (exit code, stdout, stderr)."""
    path = Path(script)
    if not path.is_absolute():
        path = SCRIPTS / script
    full_env = dict(os.environ)
    full_env.pop("DEBUG", None)
    full_env.pop("LOG_LEVEL", None)
    full_env.update(env or {})
    proc = subprocess.run([sys.executable, str(path), *map(str, args)], capture_output=True,
                          text=True, env=full_env, cwd=cwd)
    return proc.returncode, proc.stdout, proc.stderr
