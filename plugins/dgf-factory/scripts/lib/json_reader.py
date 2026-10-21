"""json_reader.py — parse a component JSON file the way DGF's runtime does.

The facts are in knowledge/json-reader.md §1: System.Text.Json with comments
skipped, one UTF-8 byte-order mark ignored, and otherwise strict JSON — a
trailing comma is an error, and so are NaN and Infinity.

Comments are stripped by a string-aware scanner that replaces every comment
character with a space and keeps every newline, so the line and column `json`
reports, and that findings cite, are the file's own. Every object is a JsonObject,
which remembers keys that collide once case is ignored: the runtime binds names
case-insensitively, so such keys silently overwrite each other. Stdlib only.
"""

import json

from . import report

UTF8_BOM = b"\xef\xbb\xbf"


class JsonParseError(Exception):
    def __init__(self, message, line=None, column=None):
        super().__init__(message)
        self.message = message
        self.line = line
        self.column = column


class JsonObject(dict):
    """A dict that records keys duplicated once case is ignored."""

    def __init__(self, pairs):
        super().__init__()
        self.case_duplicates = []
        seen = {}
        for key, value in pairs:
            folded = key.lower()
            if folded in seen and key not in self.case_duplicates:
                self.case_duplicates.append(key)
                if seen[folded] not in self.case_duplicates:
                    self.case_duplicates.insert(0, seen[folded])
            seen.setdefault(folded, key)
            self[key] = value

    def get_folded(self, name):
        """The value under `name`, matched the way the runtime matches it."""
        folded = name.lower()
        for key, value in self.items():
            if key.lower() == folded:
                return key, value
        return None, None


def _blank(text):
    """The same text with every character but a line break turned into a space."""
    return "".join(ch if ch in "\r\n" else " " for ch in text)


def strip_comments(text):
    """`text` with // and /* */ comments blanked out, strings left alone.

    Returns (text, number of comments). An unterminated /* comment is a parse
    error, as it is for the runtime.
    """
    out, i, n, comments = [], 0, len(text), 0
    in_string = False
    while i < n:
        ch = text[i]
        if in_string:
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if ch == '"':
                in_string = False
            i += 1
            continue
        if ch == '"':
            in_string = True
            out.append(ch)
            i += 1
            continue
        if text.startswith("//", i):
            end = text.find("\n", i)
            end = n if end < 0 else end
            out.append(_blank(text[i:end]))
            comments += 1
            i = end
            continue
        if text.startswith("/*", i):
            end = text.find("*/", i + 2)
            if end < 0:
                line = text.count("\n", 0, i) + 1
                raise JsonParseError("unterminated /* comment", line, i - text.rfind("\n", 0, i))
            out.append(_blank(text[i:end + 2]))
            comments += 1
            i = end + 2
            continue
        out.append(ch)
        i += 1
    return "".join(out), comments


def _reject_constant(name):
    raise ValueError(f"{name} is not valid JSON")


def parse_text(text):
    """The decoded value of `text`, read as the runtime reads it."""
    stripped, comments = strip_comments(text)
    report.debug("json_reader.parse_text", "comments stripped", count=comments)
    try:
        return json.loads(stripped, object_pairs_hook=JsonObject, parse_constant=_reject_constant)
    except json.JSONDecodeError as exc:
        raise JsonParseError(exc.msg, exc.lineno, exc.colno) from exc
    except ValueError as exc:
        raise JsonParseError(str(exc)) from exc


def decode(data):
    """Bytes to text: one UTF-8 BOM dropped, strict UTF-8 otherwise."""
    if data.startswith(UTF8_BOM):
        data = data[len(UTF8_BOM):]
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise JsonParseError(f"not UTF-8 text: {exc.reason} at byte {exc.start}") from exc


def parse_bytes(data):
    return parse_text(decode(data))


def load(path):
    return parse_bytes(path.read_bytes())
