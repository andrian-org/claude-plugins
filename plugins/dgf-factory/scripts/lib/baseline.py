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
"""

import os
from collections import Counter

from . import report


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
