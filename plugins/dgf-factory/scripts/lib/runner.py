"""runner.py — every validator over a workspaces root, or over some of its files (ADR 0018 §2).

One runner for the gate and for the maintainers' known-good run, so the two
cannot drift apart. Over a root it validates:

  - every `<ws>/FM/_PROCESS/<P>/process.xml` and every workflow, with
    validate_process's checks (structure, semantics, references);
  - every file a directory walk collects — the legacy artifact files and the
    component JSON — with validate_config and resolve_components;
  - of those, every entity `settings.xml` and every `_form.xml`, with
    validate_model too: the references they make, and a form's cells (ADR 0023 §3).

With `files` (paths relative to the root), the same three lists are made and
kept to those files, so a file is routed to exactly the validators the
whole-root run gives it. A file the walk would not collect is not validated.

The validators need lxml and jsonschema. They are imported inside run(), after
deps.require(), so a caller that never runs them — check_change.py
--skip-validators, or --help — needs neither package.
"""

import os
from pathlib import Path
from types import SimpleNamespace

from . import cli, deps, report

VALIDATORS = ("validate_process.py", "validate_config.py", "resolve_components.py", "validate_model.py")
PROCESS_SEMANTICS = "process-semantics"  # validate_config's pointer to validate_process


def _keep(paths, wanted):
    if wanted is None:
        return list(paths)
    return [path for path in paths if os.path.abspath(path) in wanted]


def targets(root, files=None):
    """(processes, workflows, configuration files) under `root`, kept to `files` when given."""
    from . import process_checks
    wanted = None if files is None else {os.path.abspath(Path(root) / rel) for rel in files}
    processes = _keep(process_checks.processes_under(root), wanted)
    workflows = _keep(process_checks.workflows_under(root), wanted)
    configs = _keep(cli.collect([root]), wanted)
    report.debug("runner.targets", "targets", root=root, scoped=files is not None, processes=len(processes),
                 workflows=len(workflows), configs=len(configs))
    return processes, workflows, configs


def _drop_satisfied_pointers(runs):
    """validate_config marks a process `process-semantics` NOT RUN, pointing at validate_process.
    This runner gave the same file to validate_process, so the pointer is satisfied."""
    checked = {rep.file for rep in runs["validate_process.py"]}
    for rep in runs["validate_config.py"]:
        if rep.file in checked:
            rep.not_run = [(check, why) for check, why in rep.not_run if check != PROCESS_SEMANTICS]


def run(root, files=None):
    """({cli name: [Report]}, unresolved CHANGE_STATE process names) for `root`.

    Exits 3 through deps.require() when lxml or jsonschema is missing.
    """
    deps.require()
    import resolve_components
    import validate_config
    import validate_model
    import validate_process
    from . import process_checks
    options = SimpleNamespace(component_type=None, view_kind=None)
    runs = {name: [] for name in VALIDATORS}
    unresolved = set()
    processes, workflows, configs = targets(root, files)
    for path in processes:
        runs["validate_process.py"].append(validate_process.check_file(path, root))
    for path in workflows:
        rep = report.Report(cli.display(path))
        tree = process_checks.parse(path)
        rep.family = "xsd"
        if tree is None:
            rep.add("XML_MALFORMED", "the workflow does not parse")
        else:
            unresolved |= set(process_checks.check_workflow(path, tree, rep, root))
        runs["validate_process.py"].append(rep)
    for path in configs:
        runs["validate_config.py"].append(validate_config.validate_file(path, options))
        runs["resolve_components.py"].append(resolve_components.check_file(path, options))
        if validate_model.artifact_of(path, root):
            runs["validate_model.py"].append(validate_model.check_file(path, root))
    _drop_satisfied_pointers(runs)
    for name, reports in runs.items():
        for rep in reports:
            report.debug("runner.run", "validated", cli=name, file=rep.file,
                         codes=",".join(sorted({f.code for f in rep.findings})) or "-")
    return runs, unresolved
