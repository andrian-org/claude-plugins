"""baseline.py — which validator findings a branch introduced (ADR 0018 §3–§4).

A finding's key is (code, root-relative file, normalised message). The message
is normalised by removing every form of the tree's root path — as given,
absolute, and with symlinks resolved — so the same finding reads the same at
the working tree and at the base tree in a temporary directory. The line
number is not in the key: lines inserted above a pre-existing finding move it
without making it new.

Keys are compared as multisets. A head finding whose key is still available at
the base is pre-existing and consumes one copy; a second copy is new. Base
findings left unconsumed were fixed by the branch. INFO findings are not
compared: they never block, and they pass through as they are. Stdlib only.

Without git, the base is a run a writing skill saved before its write (ADR
0025): save() writes that run's findings with their root already removed, and
load() reads them back for compare(), with no root left to remove. A saved
baseline holds its root and its --files scope, and is refused for any other.
"""

import json
import os
from collections import Counter
from pathlib import Path

from . import report

FORMAT = 1


class Unusable(Exception):
    """A saved baseline that cannot stand for the tree before the write; the reason says why."""


def root_forms(root):
    """Every spelling of `root` a message may carry, longest first; a list of forms is kept as it is."""
    if isinstance(root, (list, tuple)):
        return list(root)
    # Only absolute forms: a relative one such as `.` would be stripped from every message.
    forms = {os.path.abspath(root), os.path.realpath(root)}
    return sorted((f.rstrip(os.sep) for f in forms if os.path.isabs(f)), key=len, reverse=True)


def _normalise(text, forms):
    for form in forms:
        text = text.replace(form + os.sep, "").replace(form + "/", "").replace(form, "<root>")
    return text


def key(finding, forms):
    return finding.code, _normalise(finding.file, forms).replace(os.sep, "/"), _normalise(finding.message, forms)


def compare(head, base, head_root, base_root):
    """(new, pre_existing, fixed) lists of Findings; `new` keeps head INFO findings as they are.

    Each root is a path, or the list root_forms() gave for it while it existed.
    """
    head_forms, base_forms = root_forms(head_root), root_forms(base_root)
    available = Counter(key(f, base_forms) for f in base if f.severity != report.EXIT_CLEAN)
    new, pre_existing = [], []
    for finding in head:
        if finding.severity == report.EXIT_CLEAN:
            new.append(finding)
            continue
        found = key(finding, head_forms)
        if available[found] > 0:
            available[found] -= 1
            pre_existing.append(finding)
        else:
            new.append(finding)
    fixed = []
    for finding in base:
        found = key(finding, base_forms)
        if finding.severity != report.EXIT_CLEAN and available[found] > 0:
            available[found] -= 1
            fixed.append(finding)
    report.debug("baseline.compare", "compared", head=len(head), base=len(base), new=len(new),
                 pre_existing=len(pre_existing), fixed=len(fixed))
    return new, pre_existing, fixed


def _scope(files):
    return sorted(files) if files else None


def save(path, findings, root, files):
    """Write the findings compare() weighs — every one but INFO — keyed as at `root`; return them."""
    forms = root_forms(root)
    kept = [f for f in findings if f.severity != report.EXIT_CLEAN]
    rows = [{"code": code, "file": file, "line": f.line, "message": message}
            for f, (code, file, message) in ((f, key(f, forms)) for f in kept)]
    data = {"format": FORMAT, "root": os.path.realpath(root), "files": _scope(files), "findings": rows}
    Path(path).write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    report.debug("baseline.save", "saved", file=path, root=data["root"], findings=len(rows))
    return kept


def load(path, root, files):
    """The Findings a saved baseline holds, for compare() with no root to remove; Unusable when it cannot stand."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise Unusable(f"`{path}` does not exist — save it with --save-baseline before the write") from None
    except (OSError, ValueError) as exc:
        raise Unusable(f"`{path}` is not a baseline --save-baseline wrote: {(str(exc).splitlines() or [''])[0]}") \
            from None
    if not isinstance(data, dict) or data.get("format") != FORMAT or not isinstance(data.get("findings"), list):
        raise Unusable(f"`{path}` is not a baseline --save-baseline wrote")
    if data.get("root") != os.path.realpath(root):
        raise Unusable(f"`{path}` was saved for another workspaces root, `{data.get('root')}`")
    if data.get("files") != _scope(files):
        raise Unusable(f"`{path}` was saved over another validator scope — save and compare with the same --files")
    findings = []
    for row in data["findings"]:
        code = row.get("code") if isinstance(row, dict) else None
        if not isinstance(code, str) or code not in report.CODES or not isinstance(row.get("file"), str) or \
                not isinstance(row.get("message"), str) or not isinstance(row.get("line"), (int, type(None))):
            raise Unusable(f"`{path}` holds a finding no validator writes: {row!r}"[:240])
        findings.append(report.Finding(code, report.CODES[code], row["file"], row["line"], row["message"]))
    report.debug("baseline.load", "loaded", file=path, root=data["root"], findings=len(findings))
    return findings
