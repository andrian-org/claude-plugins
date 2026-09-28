"""model.py — resolve the data model's references the way each loader does (ADR 0023 §3, DD6).

knowledge/data-model.md §3 is the source, loader by loader:

  table        TableManager: clean the name (drop everything up to the last `.`),
               then `BASE:` in any case is webasm's FM/_DATA; otherwise the
               selected workspace's. So `BASE:dbo.X` is `X` in the application.
  lookup view  LookUpViewManager: the table's folder, then _lookupviews/<view>/;
               an empty view is `default`.
  grid         EditableGridManager: the loaded table's folder — its name already
               cleaned — then _gridforms/<grid>/; an empty or blank grid is `default`.
  form         FormManager: the table's folder, then _forms/<form>/; an empty form
               is `default`.
  dialog       LookUpDialogManager: the selected workspace's FM/_LOOKUP/<dialog>/,
               with no `BASE:` form and no cleaning.

Each resolver returns a workspace result — Resolved, Unresolved, CaseOnly or
AppDependent — through workspace._resolve, so existence is exact-case and a
webasm reference the selected workspace decides is resolved in every
application, or in `app` alone when the caller fixes one. A missing form or
grid whose folder exists is Unresolved with `throws`, when the table has a
`default` to copy (§3.6). So is a missing view, grid or form whose generated
replacement cannot be built from the table's fields, or does not parse once
their names and titles are pasted in (§3.2, §3.4, §3.6, §4). init_fields_throws()
says why an entity's own load throws (§1). Stdlib only; the trees handed to
fields() and cells() come from the caller's parser, and the one kind of file read
here — an entity's settings.xml, for its key and fields — is decoded as the
runtime decodes it and read with expat.
"""

import codecs
import os
from collections import namedtuple
from pathlib import Path
from xml.parsers import expat

from . import report, workspace

DEFAULT = "default"  # Table.DefaultFormName and Table.DefaultViewName
DATA = "_DATA"
SETTINGS_FILE = "settings.xml"
FORM_FILE = "_form.xml"
READONLY_SUFFIX = "/READONLY"  # FormControl cuts an Invoke's form name here (reference-graph.md §2)

# Where Form.InitFields binds cells (data-model.md §4); a section's own `cells` list is not bound, and
# nothing is bound in a form with no `tabs` element.
TABS = "tabs"
BOUND_CELLS = ("tabs/tab/sections/section/rows/row/cell", "hidden/cell")


def clean_table(name):
    """ViewManagerBase.GetCleanTableName: everything up to and including the last `.` is dropped."""
    return name[name.rfind(".") + 1:] if "." in name else name


def table_location(name):
    """(scope, the table folder's parts under the workspace) — cleaned first, then `BASE:` in any case."""
    name = clean_table(name)
    if name[:len(workspace.BASE_PREFIX)].lower() == workspace.BASE_PREFIX.lower():
        rest = name[len(workspace.BASE_PREFIX):]
        if rest.startswith("/"):
            return workspace.ROOTED_SCOPE, workspace._segments(rest)
        return workspace.BASE_SCOPE, [workspace.FM, DATA] + workspace._segments(rest)
    if name.startswith("/"):
        return workspace.ROOTED_SCOPE, workspace._segments(name)
    return workspace.SELECTED_SCOPE, [workspace.FM, DATA] + workspace._segments(name)


def _in_table(module_fn, table, tail, owner, root, app, **trace):
    """Resolve `tail` inside the folder `table` resolves to."""
    if not table:
        report.debug(module_fn, "empty table name", name="", app=app or "-", result="Unresolved", **trace)
        return workspace.Unresolved("", "names no table — the loader throws on an empty table name")
    scope, parts = table_location(table)
    return workspace._resolve(scope, parts + tail, owner, root, module_fn, app=app, name=table, **trace)


def _exact_dir(root, parts):
    """True when root/parts… is a folder every segment of which matches exactly, as on Linux."""
    current = Path(root)
    for name in parts:
        if workspace.exact_child(current, name)[0] != workspace.OK:
            return False
        current = current / name
    return current.is_dir()


def _folders(result, name):
    """(the target's folder, its table's folder) as parts, for a plain Unresolved target inside a table; else None.

    `result.path` is root-relative: <workspace>/FM/_DATA/<table…>/<kind_dir>/<name…>/<file>.
    """
    segments = workspace._segments(name)
    if type(result) is not workspace.Unresolved or not result.path or result.reason or not segments:
        return None
    folder = result.path.split("/")[:-1]
    return folder, folder[:len(folder) - len(segments) - 1]


def _has_default(root, table_folder, kind_dir, file_name):
    return workspace.exact_file(root, table_folder + [kind_dir, DEFAULT, file_name])[0] == workspace.OK


EntityField = namedtuple("EntityField", "name type uimask title required")
# The audit fields FormManager.GetXmlTemplate writes a hidden cell for, when the table has them, with the
# `oncreatevalue` and `onupdatevalue` its `properties` element carries (data-model.md §4).
HIDDEN_FIELDS = (("CreatedBy", "~USERID", ""), ("CreatedIP", "~IP", ""), ("CreatedOn", "~NOW", ""),
                 ("ModifiedBy", "~USERID", "~USERID"), ("ModifiedIP", "~IP", "~IP"), ("ModifiedOn", "~NOW", "~NOW"),
                 ("ApplicationId", "~APPLICATIONID", ""))


def entity_fields(root, table_folder):
    """read_entity() on the table's settings.xml; None too when the file is not there exactly — which its own
    reference reports."""
    found, actual = workspace.exact_file(root, list(table_folder) + [SETTINGS_FILE])
    if found != workspace.OK:
        return None
    return read_entity(actual)


XML_SPACE = "http://www.w3.org/XML/1998/namespace space"  # `xml:space`, as a namespace-aware expat names it
WHITESPACE = " \t\n\r"  # XML's
# The byte-order marks File.ReadAllTextAsync's StreamReader detects. UTF-32 LE's begins with UTF-16 LE's, so it is
# tried first, as the StreamReader tries it.
BYTE_ORDER_MARKS = ((codecs.BOM_UTF32_LE, "utf-32-le"), (codecs.BOM_UTF16_LE, "utf-16-le"),
                    (codecs.BOM_UTF16_BE, "utf-16-be"), (codecs.BOM_UTF8, "utf-8"), (codecs.BOM_UTF32_BE, "utf-32-be"))


def _runtime_text(data):
    """(a file's text, the encoding read) as File.ReadAllTextAsync gives it: by its byte-order mark, else UTF-8, and a
    byte that is not in the encoding read as U+FFFD. The XML declaration's encoding plays no part."""
    for mark, encoding in BYTE_ORDER_MARKS:
        if data.startswith(mark):
            return data[len(mark):].decode(encoding, errors="replace"), encoding
    return data.decode("utf-8", errors="replace"), "utf-8"


def _space(attributes):
    """An element's xml:space, trimmed of XML whitespace as .NET's readers trim it; None when it has none."""
    space = attributes.get(XML_SPACE)
    return None if space is None else space.strip(WHITESPACE)


def _blank(text, raw):
    """True when one expat text event is whitespace to the runtime's XmlTextReader: XML whitespace alone, and not
    a decimal character reference, which that reader keeps as text (a hexadecimal one it reads as the whitespace it
    is). `raw` is the UTF-8 input from the event on."""
    return all(c in WHITESPACE for c in text) and not (raw[:2] == b"&#" and raw[2:3].isdigit())


def read_entity(path):
    """(the first primary-key name, [EntityField]) as XmlSerializer binds a settings.xml, or None when not read.

    What Table.InitFields and a generated view, grid or form are built from. The file's text is what
    File.ReadAllTextAsync gives (_runtime_text), and XmlSerializer reads it through a StringReader, so the XML
    declaration's encoding is ignored. Only the first `<primarykey>` in no namespace binds `primaryKeyString`, with
    its text as XmlSerializer's reader gives it: any markup — a comment, a processing instruction, a CDATA section —
    ends a text node; a node of whitespace alone is dropped unless xml:space, trimmed, is `preserve` there; a CDATA
    section is kept. `Table.PrimaryKeys` is that text split on `,`, untrimmed. Each `fields/field` gives its `name`,
    `type`, `uimask` and `title`, None when absent, and `required`, which XmlSerializer reads as an xsd:boolean.
    None when the text does not parse as expat parses it, or holds a DTD, which the runtime reads and this reader
    refuses (a follow-up): the checks built on this one do not run on such a file.
    """
    parser = expat.ParserCreate(encoding="UTF-8", namespace_separator=" ")  # the declaration's encoding overridden
    tags, preserve, cdata = [], [False], [False]
    key, rows, keys_seen, node = [], [], [], []  # node: the key's text node being read, as [(text, blank)]

    def refuse_dtd(*_):
        raise ValueError("a DTD is not read")

    def end_node():
        if node and (preserve[-1] or not all(blank for _, blank in node)):
            key.append("".join(text for text, _ in node))
        node.clear()

    def start(tag, attributes):
        end_node()
        tags.append(tag)
        space = _space(attributes)
        preserve.append(space == "preserve" if space in ("preserve", "default") else preserve[-1])
        if tags[1:] == ["primarykey"]:
            keys_seen.append(tag)
        elif tags[1:] == ["fields", "field"]:
            required = (attributes.get("required") or "").strip() in ("true", "1")
            rows.append(EntityField(attributes.get("name"), attributes.get("type"), attributes.get("uimask"),
                                    attributes.get("title"), required))

    def end(tag):
        end_node()
        tags.pop()
        preserve.pop()

    def text(chunk):
        if tags[1:] == ["primarykey"] and len(keys_seen) == 1:  # a second <primarykey> is an unknown node
            start_at = parser.CurrentByteIndex
            node.append((chunk, not cdata[0] and _blank(chunk, data[start_at:start_at + 3])))

    def cdata_section(inside):
        end_node()
        cdata[0] = inside

    parser.StartDoctypeDeclHandler = refuse_dtd
    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.CharacterDataHandler = text
    parser.StartCdataSectionHandler = lambda: cdata_section(True)
    parser.EndCdataSectionHandler = lambda: cdata_section(False)
    parser.CommentHandler = lambda _: end_node()
    parser.ProcessingInstructionHandler = lambda *_: end_node()
    try:
        content, encoding = _runtime_text(Path(path).read_bytes())
        if "\x00" in content:  # no XML character, which XmlTextReader refuses; expat would read `<` NUL as UTF-16
            raise ValueError("the text holds a NUL")
        data = content.encode("utf-8")
        parser.Parse(data, True)
    except (expat.ExpatError, OSError, RecursionError, ValueError) as exc:
        report.debug("model.read_entity", "unreadable", file=str(path), error=str(exc).splitlines()[0])
        return None
    primary = "".join(key)
    report.debug("model.read_entity", "read", file=str(path), encoding=encoding, replaced=content.count("�"),
                 primarykey=repr(primary), fields=len(rows))
    return (primary.split(",")[0] if primary else None), rows


def init_fields_throws(key, rows):
    """Why Table.InitFields throws on this first key and these fields, in its own order; None when it does not.

    It adds every field to a dictionary by name, which throws on a null name and on a second field of one name;
    then it needs a primary key; then it looks the key's first part up (data-model.md §1).
    """
    names = set()
    for field in rows:
        if field.name is None:
            return "a field has no `name`, and Table.InitFields adds every field by name"
        if field.name in names:
            return f"two fields are named `{field.name}`, and Table.InitFields adds every field by name"
        names.add(field.name)
    if key is None:
        return "it has no `primarykey`, or an empty one — Table.InitFields throws `The Primary Key not defined`"
    if key not in names:
        return f"its first primary key `{key}` names no field, and Table.InitFields looks it up"
    return None


def _mask(field, position):
    """Field.get_uiMask: the flag at `position` is a `1` — a position in UTF-16 code units, as a C# string counts."""
    units = (field.uimask or "").encode("utf-16-le")
    return units[2 * position:2 * position + 2] == "1".encode("utf-16-le")


# The files the generators build, as they build them: LookUpViewManager.GetXmlTemplate with string.Format, the grid's
# and the form's with string interpolation — every value pasted unescaped, a null as "" (data-model.md §3.6).

def _view_xml(key, name, title):
    return (f'<view select="true" preview="false">\n\t<header title="" />\n  <description title="" />\n'
            f'  <row keyfield="{key}">\n    <cell name="{name}" title="{title}"/>\n  </row>\n\t<fetch>\n\t  <sort>\n'
            f'\t    <column name="{name}" ascending="true"/>\n\t  </sort>\n\t  <filter />\n\t</fetch>\n</view>')


def _grid_xml(name, title):
    return f'\n<view>\n  <row>\n    <cell name="{name}" title="{title}"/>\n  </row>\n</view>'


def _hidden_cell(name, title, create, update):
    on_create = f' oncreatevalue="{create}"' if create else ""
    on_update = f' onupdatevalue="{update}"' if update else ""
    return (f'\n\t\t\t\t\t\t<cell name="{name}" title="{title}">\n\t\t\t\t\t\t<properties{on_create}{on_update} />'
            f'\n\t\t\t\t\t\t</cell>')


def _form_xml(rows, hidden):
    """A row per (name, title), and a hidden cell per (name, title, oncreatevalue, onupdatevalue)."""
    cells = "".join(f'\n\t\t\t\t\t\t<row><cell name="{name}" title="{title}" colspan="2"/></row>'
                    for name, title in rows)
    return ('<form>\n  <header title=""/>\n\t<description title=""/>\n\t<print title=""/>\n  <tabs>\n'
            '    <tab title="General" name="tab_general">\n      <sections>\n'
            '        <section name="sec_info" title="Info" showlabel="true" decoration="line" columns="2">\n'
            f'          <rows>{cells}\n\t\t\t\t\t</rows>\n        </section>\n      </sections>\n    </tab>\n'
            '  </tabs>\n'
            f'  <hidden>{"".join(_hidden_cell(*cell) for cell in hidden)}\n\t</hidden>\n</form>')


def _check_space(_, attributes):
    space = _space(attributes)
    if space is not None and space not in ("preserve", "default"):
        raise ValueError(f"`{attributes[XML_SPACE]}` is not an xml:space value")


def _parse_error(xml):
    """None when `xml` parses — SaveXml parses it with XmlDocument.LoadXml — else why not.

    LoadXml reads namespaces, and takes only `preserve` or `default`, trimmed, as an `xml:space`. A reference to a
    character XML does not allow, `&#0;` or a lone surrogate, passes LoadXml; Save then throws, or writes a file the
    load after it refuses, so refusing it here gives the runtime's outcome. Two refusals are not the runtime's: a
    prefix or the default namespace bound to the XML namespace, and a surrogate pair written as two references, which
    LoadXml joins into one character (a follow-up).
    """
    parser = expat.ParserCreate(namespace_separator=" ")
    parser.StartElementHandler = _check_space
    try:
        parser.Parse(xml.encode("utf-8"), True)
    except (expat.ExpatError, ValueError) as exc:
        return str(exc)
    return None


def _pasted(field):
    return [(f"the name of `{field.name}`", field.name), (f"the title of `{field.name}`", field.title)]


def _generated_throws(module_fn, result, what, table_folder, reason, **trace):
    report.debug(module_fn, f"the generated {what} throws", table="/".join(table_folder), **trace)
    return workspace.Unresolved(result.path, f"the {what} generated in its place {reason}", throws=True)


def _broken(module_fn, result, what, table_folder, build, slots):
    """Unresolved(throws) when the file `build` makes of the pasted values does not parse; the result otherwise.

    `slots` is [(what the value is, the value)], in the order `build` takes the values. The value named is the first
    that breaks the file with every other value put as `x`; a break the values make only together is said so.
    """
    values = [value or "" for _, value in slots]
    error = _parse_error(build(values))
    if error is None:
        return result
    for index, (shown, _) in enumerate(slots):
        alone = ["x"] * len(values)
        alone[index] = values[index]
        if _parse_error(build(alone)) is not None:
            return _generated_throws(module_fn, result, what, table_folder,
                                     f"pastes {shown}, `{values[index]}`, unescaped, and does not parse",
                                     value=values[index])
    return _generated_throws(module_fn, result, what, table_folder,
                             f"pastes names and titles unescaped that together do not parse ({error})", error=error)


def _view_template_throws(module_fn, result, view, root):
    """A missing view is always generated by LookUpViewManager.GetXmlTemplate (data-model.md §3.2).

    It shows the first field whose type is exactly `Text` and whose name is not the first primary key, and reads its
    name — a NullReferenceException when there is none — and pastes the key, that field's name and its title;
    SaveXml then parses the whole view.
    """
    folders = _folders(result, view)
    if folders is None:
        return result
    table_folder = folders[1]
    read = entity_fields(Path(os.path.abspath(root)), table_folder)
    if read is None or init_fields_throws(*read):
        return result  # unread, or the table's own load throws first: validate_model.py blocks its settings.xml
    key, rows = read
    shown = next((field for field in rows if field.type == "Text" and field.name != key), None)
    if shown is None:
        return _generated_throws(module_fn, result, "view", table_folder,
                                 f"needs a `Text` field besides the key `{key}`, which `{table_folder[-1]}` lacks",
                                 key=key)
    if shown.name == "":
        shown = rows[0]  # an empty display name falls back to the first field
    return _broken(module_fn, result, "view", table_folder, lambda values: _view_xml(*values),
                   [(f"the key `{key}`", key)] + _pasted(shown))


def _grid_template_throws(module_fn, result, grid, root):
    """With no `default` to copy, a missing grid is generated by EditableGridManager.GetXmlTemplate (§3.4).

    It shows the first `Text` field besides the key that is `required`, else the first `Text` field besides the key,
    else the key, and pastes that field's name and title; SaveXml then parses the whole grid.
    """
    folders = _folders(result, grid)
    if folders is None:
        return result
    table_folder = folders[1]
    root = Path(os.path.abspath(root))
    if _has_default(root, table_folder, "_gridforms", "_grid.xml"):
        return result  # copied from `default`: _copied_into_existing decides
    read = entity_fields(root, table_folder)
    if read is None or init_fields_throws(*read):
        return result  # unread, or the table's own load throws first: validate_model.py blocks its settings.xml
    key, rows = read
    text = [field for field in rows if field.type == "Text" and field.name != key]
    shown = (next((field for field in text if field.required), None) or (text[0] if text else None)
             or next(field for field in rows if field.name == key))  # InitFields found the key, so it is a field
    return _broken(module_fn, result, "grid", table_folder, lambda values: _grid_xml(*values), _pasted(shown))


def _form_template_throws(module_fn, result, form, root):
    """With no `default` to copy, a missing form is generated by FormManager.GetXmlTemplate (data-model.md §4).

    It throws `Field "…" is not compatible with the version 1.5.` on the first field whose uimask is null. It then
    writes a row for each field `required` or required for the form, and valid for it, and a hidden cell for each
    audit field the table has, pasting their names and titles; SaveXml then parses the whole form.
    """
    folders = _folders(result, form)
    if folders is None:
        return result
    table_folder = folders[1]
    root = Path(os.path.abspath(root))
    if _has_default(root, table_folder, "_forms", FORM_FILE):
        return result  # copied from `default`: _copied_into_existing decides
    read = entity_fields(root, table_folder)
    if read is None or init_fields_throws(*read):
        return result  # unread, or the table's own load throws first: validate_model.py blocks its settings.xml
    rows = read[1]
    bare = next((field for field in rows if field.uimask is None), None)
    if bare is not None:
        return _generated_throws(module_fn, result, "form", table_folder,
                                 f"needs a `uimask` on every field, and the table has no `default` form — "
                                 f"`{bare.name}` has no `uimask`", field=bare.name)
    shown = [field for field in rows if (field.required or _mask(field, 1)) and _mask(field, 3)]
    by_name = {field.name: field for field in rows}  # InitFields found no name twice
    hidden = [(name, create, update) for name, create, update in HIDDEN_FIELDS if name in by_name]
    slots = [slot for field in shown for slot in _pasted(field)]
    slots += [(f"the title of `{name}`", by_name[name].title) for name, _, _ in hidden]

    def build(values):
        pairs = list(zip(values[0:2 * len(shown):2], values[1:2 * len(shown):2]))
        titles = values[2 * len(shown):]
        cells = [(name, title, create, update) for (name, create, update), title in zip(hidden, titles)]
        return _form_xml(pairs, cells)

    return _broken(module_fn, result, "form", table_folder, build, slots)


def _copied_into_existing(module_fn, result, kind_dir, name, file_name, what, root):
    """A missing form or grid is copied from the table's `default`, and the copy throws into a folder that exists.

    FormManager.Copy and EditableGridManager.Copy (data-model.md §3.6). With no `default`, a generated file is saved
    into the folder instead, which _form_template_throws and _grid_template_throws decide.
    """
    folders = _folders(result, name)
    if folders is None:
        return result
    folder, table_folder = folders
    root = Path(os.path.abspath(root))
    if not (_exact_dir(root, folder) and _has_default(root, table_folder, kind_dir, file_name)):
        return result
    shown = "/".join(folder)
    report.debug(module_fn, "a copy into a folder that exists throws", folder=shown)
    return workspace.Unresolved(result.path, f"its folder `{shown}/` exists without `{file_name}`, and the table has "
                                             f"a `{DEFAULT}` {what}, which the loader copies only into a folder that "
                                             f"does not exist", throws=True)


def resolve_table(name, owner, root, app=None):
    """An entity's settings.xml, as TableManager.LoadAsync finds it."""
    return _in_table("model.resolve_table", name, [SETTINGS_FILE], owner, root, app)


def resolve_form(table, form, owner, root, app=None):
    """A form's _form.xml, as FormManager.LoadAsync(table, form) finds it."""
    form = form or DEFAULT
    result = _in_table("model.resolve_form", table, ["_forms"] + workspace._segments(form) + [FORM_FILE],
                       owner, root, app, form=form)
    result = _copied_into_existing("model.resolve_form", result, "_forms", form, FORM_FILE, "form", root)
    return _form_template_throws("model.resolve_form", result, form, root)


def resolve_invoke_form(table, form, owner, root, app=None):
    """An Invoke's form: the name is cut at its first `/READONLY`, then resolved as a form."""
    cut = form.find(READONLY_SUFFIX) if form else -1
    report.debug("model.resolve_invoke_form", "cut" if cut != -1 else "whole", name=table, form=form or "")
    return resolve_form(table, form[:cut] if cut != -1 else form, owner, root, app)


def resolve_lookup_view(table, view, owner, root, app=None):
    """A lookup view's _view.xml, as LookUpViewManager.LoadAsync(table, view) finds it."""
    view = view or DEFAULT
    result = _in_table("model.resolve_lookup_view", table,
                       ["_lookupviews"] + workspace._segments(view) + ["_view.xml"], owner, root, app, view=view)
    return _view_template_throws("model.resolve_lookup_view", result, view, root)


def resolve_grid(table, grid, owner, root, app=None):
    """An editable grid's _grid.xml, as EditableGridManager.LoadAsync(table, grid) finds it."""
    grid = grid if grid and grid.strip() else DEFAULT  # LoadAsync tests the name with IsNullOrWhiteSpace
    result = _in_table("model.resolve_grid", table, ["_gridforms"] + workspace._segments(grid) + ["_grid.xml"],
                       owner, root, app, grid=grid)
    result = _copied_into_existing("model.resolve_grid", result, "_gridforms", grid, "_grid.xml", "grid", root)
    return _grid_template_throws("model.resolve_grid", result, grid, root)


def resolve_lookup_dialog(name, owner, root, app=None):
    """A lookup dialog's _dialog.xml: the selected workspace's FM/_LOOKUP only, the name uncleaned."""
    if not name:
        report.debug("model.resolve_lookup_dialog", "empty dialog name", name="", app=app or "-", result="Unresolved")
        return workspace.Unresolved("", "names no dialog — the loader throws on an empty dialog name")
    if name.startswith("/"):
        scope, parts = workspace.ROOTED_SCOPE, workspace._segments(name) + ["_dialog.xml"]
    else:
        scope, parts = workspace.SELECTED_SCOPE, [workspace.FM, "_LOOKUP"] + workspace._segments(name) + [
            "_dialog.xml"]
    return workspace._resolve(scope, parts, owner, root, "model.resolve_lookup_dialog", app=app, name=name)


def form_parts(path):
    """(owning workspace, entity folder, form name) for `<ws>/FM/_DATA/<E>/_forms/<f…>/_form.xml`, or None."""
    owner = workspace.owning_workspace(path)
    if owner is None:
        return None
    parts = Path(path).resolve().relative_to(owner.resolve()).parts
    if (len(parts) < 6 or parts[:2] != (workspace.FM, DATA) or parts[3] != "_forms"
            or parts[-1] != FORM_FILE):
        return None
    return owner, parts[2], "/".join(parts[4:-1])


def owning_table(form_path, root):
    """The settings.xml of the entity whose folder holds the form, in the form's own workspace; None if not a form."""
    found = form_parts(form_path)
    if found is None:
        return None
    owner, entity, _ = found
    parts = [workspace.FM, DATA, entity, SETTINGS_FILE]
    return workspace._resolve(workspace.BASE_SCOPE if workspace.is_base(owner) else workspace.SELECTED_SCOPE,
                              parts, owner, root, "model.owning_table", form=str(form_path))


def fields(settings_tree):
    """{field name: (type, line)} for every `fields/field` of an entity — the names a cell may bind."""
    found = {}
    for field in settings_tree.getroot().findall("fields/field"):
        name = field.get("name")
        if name is not None and name not in found:
            found[name] = (field.get("type"), getattr(field, "sourceline", None))
    report.debug("model.fields", "fields", count=len(found))
    return found


def cells(form_tree):
    """[(name, line, custom)] for every bound cell with a `name`; a cell with a `content` child is custom."""
    found = []
    root = form_tree.getroot()
    if root.find(TABS) is None:
        # Form.InitFields returns before it binds any cell, the hidden ones included, when `Tabs` is null.
        report.debug("model.cells", "no tabs element: nothing is bound", count=0)
        return found
    for path in BOUND_CELLS:
        for cell in root.findall(path):
            name = cell.get("name")
            if name is None:
                continue
            found.append((name, getattr(cell, "sourceline", None), cell.find("content") is not None))
    report.debug("model.cells", "cells", count=len(found))
    return found
