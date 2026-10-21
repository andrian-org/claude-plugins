"""render.py — the scaffold's template engine (ADR 0027 §7.3).

Logic-less on purpose: a template holds text, values, loops and conditions, and nothing
else, so what a generated file says is decided by the design and never by the template.
Imported by generate.py; stdlib only.

  {{path}}                 a value, escaped for the file's format (see FORMATS); `path` is dotted
  {{path|filter}}          the same, escaped by `filter` instead: raw, md, xml, json, sqlstr, sqlid, yaml, cs
  {{#each list}}…{{/each}} the block once per item; inside it `this` is the item and its keys resolve
                           bare, then outward; @index, @first and @last are set
  {{#if cond}}…{{else}}…{{/if}}   cond is `path`, `!path`, `path=word` or `path!=word`
  {{! text }}              a comment
  ${NAME}                  survives untouched: a deployment-time variable, never a template value

A line holding only a block tag or a comment leaves no blank line behind. A path that resolves
nowhere is an error, not an empty string: a template that names a value the context lacks is
wrong, and a generated file must never carry a silent hole.
"""

import re

FORMATS = {
    # file format -> the filter a bare {{value}} gets
    "xml": "xml", "msbuild": "xml", "html": "xml",
    "json": "json",
    "sql": "sqlstr",
    "yaml": "yaml",
    "csharp": "cs",
    "md": "md",
    "text": "raw", "env": "raw", "sh": "raw", "docker": "raw", "ignore": "raw",
}

TAG = re.compile(r"\{\{(.*?)\}\}", re.DOTALL)
BLOCK_LINE = re.compile(r"^[ \t]*\{\{\s*(?:[#/][a-z]+[^}]*|else|![^}]*)\s*\}\}[ \t]*\r?\n", re.MULTILINE)
COND = re.compile(r"(!?)\s*([A-Za-z_@][\w.@]*)\s*(?:(!?=)\s*(\S+))?\s*\Z")


class TemplateError(Exception):
    """The template or its context is wrong; the caller reports it as a missing or malformed template."""


# --- escapes -------------------------------------------------------------------

def _text(value):
    if value is None:
        return ""
    if value is True:
        return "true"
    if value is False:
        return "false"
    return str(value)


def esc_xml(value):
    return (_text(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;").replace("'", "&apos;"))


def esc_json(value):
    out = []
    for ch in _text(value):
        code = ord(ch)
        if ch == '"':
            out.append('\\"')
        elif ch == "\\":
            out.append("\\\\")
        elif code < 0x20 or code in (0x2028, 0x2029) or 0x7F <= code <= 0x9F:
            out.append(f"\\u{code:04x}")
        else:
            out.append(ch)
    return "".join(out)


def esc_sqlstr(value):
    return _text(value).replace("'", "''")


def esc_sqlid(value):
    return _text(value).replace("]", "]]")


def esc_yaml(value):
    """The inside of a double-quoted YAML scalar."""
    out = []
    for ch in _text(value):
        code = ord(ch)
        if ch == '"':
            out.append('\\"')
        elif ch == "\\":
            out.append("\\\\")
        elif code < 0x20 or code in (0x2028, 0x2029) or 0x7F <= code <= 0x9F:
            out.append(f"\\u{code:04x}")
        else:
            out.append(ch)
    return "".join(out)


def esc_md(value):
    """A value inside Markdown prose or a table cell: nothing in it can start a span, a table cell or a tag."""
    return (_text(value).replace("\\", "\\\\").replace("|", "\\|").replace("`", "\\`")
            .replace("<", "&lt;").replace(">", "&gt;"))


def esc_cs(value):
    return esc_yaml(value)  # a C# regular string literal escapes the same characters the same way


FILTERS = {"raw": _text, "md": esc_md, "xml": esc_xml, "json": esc_json, "sqlstr": esc_sqlstr, "sqlid": esc_sqlid,
           "yaml": esc_yaml, "cs": esc_cs}


# --- parsing -------------------------------------------------------------------

def parse(source, name="<template>"):
    """The template as a tree of ('text', s), ('var', path, filter), ('each', path, body), ('if', cond, then, else)."""
    source = BLOCK_LINE.sub(lambda m: "\x00" + m.group(0).strip() + "\x00", source)
    tokens = []
    position = 0
    for match in TAG.finditer(source):
        if match.start() > position:
            tokens.append(("text", source[position:match.start()]))
        tokens.append(("tag", match.group(1).strip()))
        position = match.end()
    if position < len(source):
        tokens.append(("text", source[position:]))
    # a standalone block line was wrapped in NULs; drop the NULs, and with them the line
    cleaned = []
    for token in tokens:
        if token[0] == "text":
            text = token[1]
            text = re.sub("\x00\x00", "", text)
            text = text.replace("\x00", "")
            if text:
                cleaned.append(("text", text))
        else:
            cleaned.append(token)
    (tree, _), _ = _block(cleaned, 0, name, None)
    return tree


def _block(tokens, index, name, closing):
    body = []
    else_body = None
    current = body
    while index < len(tokens):
        kind, value = tokens[index][0], tokens[index][1]
        index += 1
        if kind == "text":
            current.append(("text", value))
            continue
        if value.startswith("!"):
            continue
        if value == "/each" or value == "/if" or value == "/unless":
            if closing != value[1:]:
                raise TemplateError(f"{name}: `{{{{{value}}}}}` closes nothing")
            return (body, else_body), index
        if value == "else":
            if closing not in ("if", "unless"):
                raise TemplateError(f"{name}: `{{{{else}}}}` outside an if")
            else_body = []
            current = else_body
            continue
        if value.startswith("#each "):
            path = value[6:].strip()
            inner, index = _block(tokens, index, name, "each")
            current.append(("each", path, inner[0]))
            continue
        if value.startswith("#if ") or value.startswith("#unless "):
            negate = value.startswith("#unless ")
            cond = value.split(None, 1)[1].strip()
            if not COND.match(cond):
                raise TemplateError(f"{name}: `{cond}` is not a condition")
            inner, index = _block(tokens, index, name, "unless" if negate else "if")
            then, other = inner
            current.append(("if", cond, then, other or [], negate))
            continue
        if value.startswith("#") or value.startswith("/"):
            raise TemplateError(f"{name}: unknown block `{{{{{value}}}}}`")
        path, _, flt = value.partition("|")
        path, flt = path.strip(), flt.strip() or None
        if not re.fullmatch(r"[A-Za-z_@][\w.@]*", path):
            raise TemplateError(f"{name}: `{{{{{value}}}}}` is not a value")
        if flt is not None and flt not in FILTERS:
            raise TemplateError(f"{name}: `{flt}` is not a filter — {', '.join(sorted(FILTERS))}")
        current.append(("var", path, flt))
    if closing is not None:
        raise TemplateError(f"{name}: a `{{{{#{closing}}}}}` block is never closed")
    return (body, None), index


# --- rendering -----------------------------------------------------------------

def _lookup(stack, path, name):
    first, *rest = path.split(".")
    for scope in reversed(stack):
        if isinstance(scope, dict) and first in scope:
            value = scope[first]
            break
        if first == "this" and scope is not None:
            value = scope
            break
    else:
        raise TemplateError(f"{name}: `{path}` resolves nowhere")
    for part in rest:
        if isinstance(value, dict) and part in value:
            value = value[part]
        else:
            raise TemplateError(f"{name}: `{path}` resolves nowhere (no `{part}`)")
    return value


def _truth(value):
    return bool(value) and value != "false"


def _cond(cond, stack, name):
    match = COND.match(cond)
    negate, path, operator, word = match.groups()
    value = _lookup(stack, path, name)
    if operator:
        result = _text(value) == word
        result = result if operator == "=" else not result
    else:
        result = _truth(value)
    return (not result) if negate else result


def _emit(nodes, stack, default_filter, name, out, escaped):
    for node in nodes:
        kind = node[0]
        if kind == "text":
            out.append(node[1])
        elif kind == "var":
            _, path, flt = node
            flt = flt or default_filter
            out.append(FILTERS[flt](_lookup(stack, path, name)))
            escaped.append(flt)
        elif kind == "each":
            _, path, body = node
            items = _lookup(stack, path, name)
            if not isinstance(items, (list, tuple)):
                raise TemplateError(f"{name}: `{path}` is not a list")
            for position, item in enumerate(items):
                frame = dict(item) if isinstance(item, dict) else {}
                frame.update({"this": item, "@index": position, "@first": position == 0,
                              "@last": position == len(items) - 1})
                _emit(body, stack + [frame], default_filter, name, out, escaped)
        elif kind == "if":
            _, cond, then, other, negate = node
            taken = _cond(cond, stack, name)
            if negate:
                taken = not taken
            _emit(then if taken else other, stack, default_filter, name, out, escaped)


def render(source, context, file_format="text", name="<template>"):
    """(text, filters used) — `source` rendered against `context` with the format's default escape."""
    if file_format not in FORMATS:
        raise TemplateError(f"{name}: `{file_format}` is not a format — {', '.join(sorted(FORMATS))}")
    tree = parse(source, name)
    out, escaped = [], []
    _emit(tree, [context], FORMATS[file_format], name, out, escaped)
    return "".join(out), escaped
