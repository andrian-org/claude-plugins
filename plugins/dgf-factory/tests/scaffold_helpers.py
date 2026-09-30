"""What the scaffold tests share: the design of the example, a generated application, and a way to break one file."""

import contextlib
import copy
import importlib.util
import io
import json
import shutil
import tempfile
from pathlib import Path

from tests import helpers

SCRIPTS = helpers.PLUGIN_ROOT / "skills" / "dgf-scaffold" / "scripts"
FIXTURES = helpers.PLUGIN_ROOT / "tests" / "fixtures" / "unit" / "scaffold"
GOLDEN = helpers.PLUGIN_ROOT / "tests" / "fixtures" / "golden" / "scaffold"
WEBASM = FIXTURES / "webasm"
EXAMPLE = json.loads((FIXTURES / "example.application.json").read_text(encoding="utf-8"))


def load(name):
    spec = importlib.util.spec_from_file_location(f"scaffold_test_{name}", SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


generate = load("generate")


def example():
    """The complete example design, with its base path made real."""
    doc = copy.deepcopy(EXAMPLE)
    doc["base"]["source"] = str(WEBASM)
    return doc


def single():
    """`own-workspace`, one instance, one API with one deployment: the smallest application with a register."""
    doc = example()
    doc["instance_model"] = "own-workspace"
    doc["instances"] = doc["instances"][:1]
    doc["apis"] = [{"name": "Api", "deployments": [{"name": "Web", "instance": "lands", "auth": ["basic"]}]}]
    doc["modules"] = [m for m in doc["modules"] if m["name"] != "Approval"]
    doc["data_model"]["entities"] = [e for e in doc["data_model"]["entities"] if e["name"] != "Approval"]
    return doc


def write_design(folder, doc):
    folder = Path(folder)
    (folder / "docs").mkdir(parents=True, exist_ok=True)
    (folder / "docs" / "application.json").write_text(json.dumps(doc), encoding="utf-8")
    return folder


def run(argv):
    """(exit code, stdout, stderr) of generate.main(argv), captured."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = generate.main(argv)
        except SystemExit as stop:
            code = stop.code
    return code, out.getvalue(), err.getvalue()


def generated(doc, parent):
    """A folder holding `doc`'s application, freshly generated; the generator must have exited 0."""
    folder = write_design(tempfile.mkdtemp(dir=parent), doc)
    code, out, err = run(["--folder", str(folder)])
    if code != 0:
        raise AssertionError(f"generate exited {code}\n{out}\n{err}")
    return folder


def tree(folder):
    """{relative path: bytes} of every file under `folder`."""
    folder = Path(folder)
    return {p.relative_to(folder).as_posix(): p.read_bytes() for p in sorted(folder.rglob("*")) if p.is_file()}


def copy_of(folder, parent):
    target = Path(tempfile.mkdtemp(dir=parent)) / "app"
    shutil.copytree(folder, target)
    return target
