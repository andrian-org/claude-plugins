"""helpers.py — shared test plumbing: import path, temp workspaces roots, CLI runner.

Not shipped. Importing this module puts <plugin>/scripts on sys.path once, so a
test imports `lib.<module>` exactly as the validators do. Nothing imports
`scripts.lib…`.
"""

import os
import shutil
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


def have_git():
    """True when a `git` executable is on PATH — tests that need one skip otherwise."""
    return shutil.which("git") is not None


def git(cwd, *args):
    """Run git in `cwd` and return its stdout; a failure fails the test."""
    proc = subprocess.run(["git", "-C", str(cwd), *map(str, args)], capture_output=True, text=True)
    if proc.returncode != 0:
        raise AssertionError(f"git {' '.join(map(str, args))} failed: {proc.stderr.strip()}")
    return proc.stdout


def make_repo(path, files=None, message="initial"):
    """`git init -b main` at `path` with a local identity, optionally committing `files`."""
    repo = Path(path)
    repo.mkdir(parents=True, exist_ok=True)
    git(repo, "init", "-q", "-b", "main")
    for key, value in (("user.name", "Test"), ("user.email", "test@example.invalid"),
                       ("core.autocrlf", "false"), ("commit.gpgsign", "false")):
        git(repo, "config", key, value)
    if files:
        make_root(repo, files)
        commit_all(repo, message)
    return repo


def commit_all(repo, message):
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "--allow-empty", "-m", message)
    return git(repo, "rev-parse", "HEAD").strip()


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


def run_cli_blocking(script, *args, blocked=("lxml", "jsonschema"), cwd=None):
    """run_cli with `blocked` modules made unimportable — proves a script never imports them."""
    path = SCRIPTS / script
    argv = [str(path), *map(str, args)]
    program = ("import runpy, sys\n"
               f"for name in {list(blocked)!r}:\n    sys.modules[name] = None\n"
               f"sys.argv = {argv!r}\n"
               f"sys.path.insert(0, {str(SCRIPTS)!r})\n"
               f"runpy.run_path({str(path)!r}, run_name='__main__')\n")
    env = dict(os.environ)
    env.pop("DEBUG", None)
    env.pop("LOG_LEVEL", None)
    proc = subprocess.run([sys.executable, "-c", program], capture_output=True, text=True, env=env, cwd=cwd)
    return proc.returncode, proc.stdout, proc.stderr


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
