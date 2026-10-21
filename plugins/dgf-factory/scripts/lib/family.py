"""family.py — resolve a file's schema family before anything parses it (DD8).

Bytes in. The byte-order mark is sniffed on the raw bytes, a short prefix is
decoded only to look for `<?xml`, and lxml always receives the original bytes —
it refuses a decoded string that carries an encoding declaration, and it honours
the BOM and the declaration itself. So a real UTF-16 `_form.xml` parses.

- XSD family: the prefix begins with `<?xml`, or lxml parses the bytes and the
  root element is the root of a vendored XSD.
- JSON family: decoded as UTF-8 (one BOM dropped) with comments stripped, the
  text parses as a JSON object.
- Otherwise the family is unresolved, and both parse errors are reported. A
  document with an XML declaration that does not parse is malformed XML.

Never falls back to JSON. Requires lxml — deps.require() must have run first.
"""

from dataclasses import dataclass

from lxml import etree

from . import json_reader, report

BOMS = ((b"\xef\xbb\xbf", "utf-8"), (b"\xff\xfe", "utf-16-le"), (b"\xfe\xff", "utf-16-be"))
PREFIX_BYTES = 256


def xml_parser():
    """The only parser the validators use: no entities, no network, no DTD."""
    return etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False, huge_tree=False)


@dataclass
class Detection:
    family: object = None      # "xsd", "json" or None
    tree: object = None        # the parsed lxml tree, for XSD
    document: object = None    # the parsed JSON value, for JSON
    code: object = None        # FAMILY_UNRESOLVED or XML_MALFORMED on failure
    message: str = ""
    line: object = None


def sniff(data):
    """(encoding the BOM names or None, decoded prefix for sniffing only)."""
    for bom, encoding in BOMS:
        if data.startswith(bom):
            return encoding, data[len(bom):len(bom) + PREFIX_BYTES].decode(encoding, errors="ignore")
    return None, data[:PREFIX_BYTES].decode("utf-8", errors="ignore")


def detect(data, known_roots):
    """Detection for `data`; `known_roots` are the vendored XSDs' root element names."""
    bom, prefix = sniff(data)
    declared = prefix.lstrip().startswith("<?xml")
    report.debug("family.detect", "sniffed", bom=bom or "none", xml_declaration=declared, bytes=len(data))

    xml_error = None
    try:
        tree = etree.ElementTree(etree.fromstring(data, xml_parser()))
    except etree.XMLSyntaxError as exc:
        tree, xml_error = None, exc
    if declared:
        if tree is None:
            return Detection(code="XML_MALFORMED", message=f"not well-formed XML: {xml_error.msg}",
                             line=getattr(xml_error, "lineno", None))
        return Detection(family="xsd", tree=tree)
    if tree is not None and etree.QName(tree.getroot()).localname in known_roots:
        return Detection(family="xsd", tree=tree)

    try:
        document = json_reader.parse_bytes(data)
    except json_reader.JsonParseError as exc:
        return _unresolved(tree, xml_error, f"{exc.message} (line {exc.line})" if exc.line else exc.message)
    if not isinstance(document, dict):
        return _unresolved(tree, xml_error, "the JSON text is not an object")
    return Detection(family="json", document=document)


def _unresolved(tree, xml_error, json_problem):
    if tree is not None:
        xml_problem = f"parses as XML, but root `{etree.QName(tree.getroot()).localname}` is no vendored XSD's root"
    else:
        xml_problem = f"not XML: {xml_error.msg if xml_error is not None else 'empty'}"
    return Detection(code="FAMILY_UNRESOLVED",
                     message=f"neither family resolves — XSD: {xml_problem}; JSON: {json_problem}. "
                             f"Refusing to assume either.")
