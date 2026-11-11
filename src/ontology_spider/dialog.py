"""Parser and AST for the .dialog controlled conversational language."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


class ParseError(Exception):
    """Structured parse error reporting exact line number and expected form."""

    def __init__(self, line_num: int, message: str, expected: str = "") -> None:
        self.line_num = line_num
        self.message = message
        self.expected = expected
        details = f"Line {line_num}: {message}"
        if expected:
            details += f" (expected: {expected})"
        super().__init__(details)


@dataclass(frozen=True)
class DialogHeader:
    uri: str
    line_num: int = 1


@dataclass(frozen=True)
class DialogImport:
    path: str
    line_num: int = 1


@dataclass(frozen=True)
class DialogEntityDecl:
    entity_id: str
    attributes: dict[str, Any] = field(default_factory=dict)
    line_num: int = 1


@dataclass(frozen=True)
class DialogAssertion:
    subject: str
    predicate: str
    object: str
    attributes: dict[str, Any] = field(default_factory=dict)
    line_num: int = 1


@dataclass(frozen=True)
class DialogQuery:
    kind: str  # "lookup", "transitive", "ancestors", "pattern", "filter", "explain", "recommend"
    subject: str | None = None
    predicate: str | None = None
    object: str | None = None
    filter_key: str | None = None
    filter_val: str | None = None
    filter_attributes: dict[str, Any] = field(default_factory=dict)
    subquery: DialogQuery | None = None
    raw_text: str = ""
    line_num: int = 1


@dataclass
class DialogDoc:
    uri: str
    imports: list[DialogImport] = field(default_factory=list)
    statements: list[
        DialogImport | DialogEntityDecl | DialogAssertion | DialogQuery
    ] = field(default_factory=list)



def _unescape_string(raw: str) -> str:
    r"""Unescape backslash escapes (\n, \r, \t, \xNN, \", \', \\) in a single pass."""
    i = 0
    n = len(raw)
    out: list[str] = []
    while i < n:
        if raw[i] == "\\" and i + 1 < n:
            nxt = raw[i + 1]
            if nxt == "n":
                out.append("\n")
                i += 2
            elif nxt == "r":
                out.append("\r")
                i += 2
            elif nxt == "t":
                out.append("\t")
                i += 2
            elif nxt == '"':
                out.append('"')
                i += 2
            elif nxt == "'":
                out.append("'")
                i += 2
            elif nxt == "\\":
                out.append("\\")
                i += 2
            elif nxt == "x" and i + 3 < n:
                hex_part = raw[i + 2 : i + 4]
                try:
                    code = int(hex_part, 16)
                    out.append(chr(code))
                    i += 4
                except ValueError:
                    out.append(raw[i : i + 2])
                    i += 2
            else:
                out.append(nxt)
                i += 2
        else:
            out.append(raw[i])
            i += 1
    return "".join(out)


def _parse_attributes(attr_str: str, line_num: int) -> dict[str, Any]:
    """Parse key=value pairs inside brackets, respecting quoted strings with commas."""
    attr_str = attr_str.strip()
    if not (attr_str.startswith("[") and attr_str.endswith("]")):
        raise ParseError(
            line_num,
            f"Malformed attribute list '{attr_str}'",
            "[key=value, ...]",
        )
    content = attr_str[1:-1].strip()
    if not content:
        return {}

    # Tokenize comma-separated items respecting quotes
    items = []
    current: list[str] = []
    in_quote: str | None = None
    escaped = False

    for ch in content:
        if escaped:
            current.append(ch)
            escaped = False
            continue
        if ch == "\\":
            current.append(ch)
            escaped = True
            continue
        if ch in ('"', "'"):
            if in_quote == ch:
                in_quote = None
            elif in_quote is None:
                in_quote = ch
            current.append(ch)
            continue
        if ch == "," and in_quote is None:
            items.append("".join(current).strip())
            current = []
            continue
        current.append(ch)

    if current:
        items.append("".join(current).strip())

    attributes: dict[str, Any] = {}
    for item in items:
        if not item:
            continue
        if "=" not in item:
            raise ParseError(
                line_num,
                f"Attribute missing '=' in '{item}'",
                "key=value",
            )
        k, v = item.split("=", 1)
        k = k.strip()
        v = v.strip()
        if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
            # Quoted values remain str without numeric coercion
            attributes[k] = _unescape_string(v[1:-1])
            continue

        # Try numeric conversion for unquoted tokens
        try:
            if "." in v:
                attributes[k] = float(v)
            else:
                attributes[k] = int(v)
            continue
        except ValueError:
            pass
        attributes[k] = v
    return attributes


def parse_dialog(text: str) -> DialogDoc:
    """Parse a .dialog file into a typed DialogDoc AST."""
    lines = text.splitlines()
    uri = "urn:dialog:unnamed"
    imports: list[DialogImport] = []
    statements: list[DialogImport | DialogEntityDecl | DialogAssertion | DialogQuery] = []

    for idx, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        # Strip comments and skip empty lines
        if not line or line.startswith("#"):
            continue

        # Header declaration: dialog <URI> or ontology <URI>
        if line.startswith("dialog ") or line.startswith("ontology "):
            parts = line.split(maxsplit=1)
            uri = parts[1].strip()
            continue

        # Import statement: import <path> or import "<path>"
        if line.startswith("import "):
            parts = line.split(maxsplit=1)
            if len(parts) < 2 or not parts[1].strip():
                raise ParseError(
                    idx,
                    "Import statement missing path",
                    "import <path_or_uri>",
                )
            target = parts[1].strip().strip('"').strip("'")
            imp = DialogImport(path=target, line_num=idx)
            imports.append(imp)
            statements.append(imp)
            continue

        # Entity statement: entity <id> [attr=val, ...]
        if line.startswith("entity "):
            body = line[7:].strip()
            ent_attrs: dict[str, Any] = {}
            if "[" in body and body.endswith("]"):
                main_part, attr_part = body.rsplit("[", 1)
                attr_part = "[" + attr_part
                ent_attrs = _parse_attributes(attr_part, idx)
                body = main_part.strip()
            ent_id = body.strip()
            if not ent_id:
                raise ParseError(
                    idx,
                    "Entity statement missing entity id",
                    "entity <id> [key=value, ...]",
                )
            statements.append(
                DialogEntityDecl(
                    entity_id=ent_id,
                    attributes=ent_attrs,
                    line_num=idx,
                )
            )
            continue

        # Assertion statement:
        # assert <subject> <predicate> <object> [attr=val, ...]
        if line.startswith("assert "):
            body = line[7:].strip()
            # Check for attributes block at end
            asrt_attrs: dict[str, Any] = {}
            if "[" in body and body.endswith("]"):
                main_part, attr_part = body.rsplit("[", 1)
                attr_part = "[" + attr_part
                asrt_attrs = _parse_attributes(attr_part, idx)
                body = main_part.strip()

            tokens = body.split()
            if len(tokens) != 3:
                raise ParseError(
                    idx,
                    f"Assertion must have 3 tokens (subject predicate object), found {len(tokens)}: '{body}'",
                    "assert <subject> <predicate> <object> [key=value, ...]",
                )
            asrt = DialogAssertion(
                subject=tokens[0],
                predicate=tokens[1],
                object=tokens[2],
                attributes=asrt_attrs,
                line_num=idx,
            )
            statements.append(asrt)
            continue

        # Explain statement: explain OR explain <query>
        if line == "explain" or line.startswith("explain "):
            rest = line[7:].strip()
            subquery = None
            if rest:
                sub_line = rest if rest.startswith("query ") else f"query {rest}"
                sub_doc = parse_dialog(f"dialog {uri}\n{sub_line}")
                for sub_stmt in sub_doc.statements:
                    if isinstance(sub_stmt, DialogQuery):
                        subquery = sub_stmt
                        break
            statements.append(
                DialogQuery(
                    kind="explain",
                    subquery=subquery,
                    raw_text=line,
                    line_num=idx,
                )
            )
            continue

        # Query statement:
        if line.startswith("query "):
            query_body = line[6:].strip()

            # Check for trailing inline explain: e.g. "query recommend X [attrs] explain"
            trailing_explain = False
            if query_body.lower().endswith(" explain"):
                query_body = query_body[:-8].strip()
                trailing_explain = True

            # Normalize trailing question mark without stripping standalone wildcard '?'
            if query_body.endswith("?") and not query_body.endswith(" ?"):
                clean_body = query_body[:-1].strip()
            else:
                clean_body = query_body

            parsed_query: DialogQuery | None = None

            # Pattern 1: what is <X>
            m_what_is = re.match(r"^what\s+is\s+(\S+)$", clean_body, re.IGNORECASE)
            if m_what_is:
                parsed_query = DialogQuery(
                    kind="lookup",
                    subject=m_what_is.group(1),
                    raw_text=line,
                    line_num=idx,
                )

            # Pattern 2: ancestors of <X>
            elif (m_anc := re.match(r"^ancestors\s+of\s+(\S+)$", clean_body, re.IGNORECASE)):
                parsed_query = DialogQuery(
                    kind="ancestors",
                    subject=m_anc.group(1),
                    raw_text=line,
                    line_num=idx,
                )

            # Pattern 3: transitive <predicate> from <subject>
            elif (m_trans := re.match(r"^transitive\s+(\S+)\s+from\s+(\S+)$", clean_body, re.IGNORECASE)):
                parsed_query = DialogQuery(
                    kind="transitive",
                    predicate=m_trans.group(1),
                    subject=m_trans.group(2),
                    raw_text=line,
                    line_num=idx,
                )

            # Pattern 4: filter <predicate> where <key>=<val>
            elif (m_filter := re.match(r"^filter\s+(\S+)\s+where\s+(\S+)\s*=\s*(\S+)$", clean_body, re.IGNORECASE)):
                parsed_query = DialogQuery(
                    kind="filter",
                    predicate=m_filter.group(1),
                    filter_key=m_filter.group(2),
                    filter_val=m_filter.group(3).strip('"').strip("'"),
                    raw_text=line,
                    line_num=idx,
                )

            # Pattern 4b: recommend with bracketed attributes: recommend <Class> [key=val, ...]
            elif clean_body.lower().startswith("recommend ") and "[" in clean_body and clean_body.endswith("]"):
                rec_part = clean_body[10:].strip()
                bracket_idx = rec_part.find("[")
                target_cls = rec_part[:bracket_idx].strip()
                attr_str = rec_part[bracket_idx:].strip()
                attrs = _parse_attributes(attr_str, idx)
                first_k, first_v = (next(iter(attrs.items()))) if attrs else (None, None)
                parsed_query = DialogQuery(
                    kind="recommend",
                    object=target_cls,
                    filter_key=first_k,
                    filter_val=str(first_v) if first_v is not None else None,
                    filter_attributes=attrs,
                    raw_text=line,
                    line_num=idx,
                )

            # Pattern 4c: recommend <Class> where <attr> = <val> OR recommend <Class>
            elif (m_rec := re.match(r"^recommend\s+(\S+)(?:\s+where\s+(\S+)\s*=\s*(\S+))?$", clean_body, re.IGNORECASE)):
                fk = m_rec.group(2) if m_rec.group(2) else None
                fv = m_rec.group(3).strip('"').strip("'") if m_rec.group(3) else None
                fattrs = {fk: fv} if fk and fv is not None else {}
                parsed_query = DialogQuery(
                    kind="recommend",
                    object=m_rec.group(1),
                    filter_key=fk,
                    filter_val=fv,
                    filter_attributes=fattrs,
                    raw_text=line,
                    line_num=idx,
                )

            # Pattern 5: general triple pattern query: <subject> <predicate> <object>
            elif len(q_tokens := clean_body.split()) == 3:
                q_s, q_p, q_o = q_tokens
                parsed_query = DialogQuery(
                    kind="pattern",
                    subject=None if q_s in ("?", "*", "_") else q_s,
                    predicate=None if q_p in ("?", "*", "_") else q_p,
                    object=None if q_o in ("?", "*", "_") else q_o,
                    raw_text=line,
                    line_num=idx,
                )

            if parsed_query is not None:
                if trailing_explain:
                    statements.append(
                        DialogQuery(
                            kind="explain",
                            subquery=parsed_query,
                            raw_text=line,
                            line_num=idx,
                        )
                    )
                else:
                    statements.append(parsed_query)
                continue

            raise ParseError(
                idx,
                f"Unrecognized query syntax: '{query_body}'",
                "query what is <X>? | query ancestors of <X>? | query transitive <rel> from <X>? | query recommend <C> [k=v] | query <S> <P> <O>?",
            )

        # If line does not match any recognized command:
        raise ParseError(
            idx,
            f"Unexpected statement: '{line}'",
            "dialog <URI> | import <path> | entity <id> [attrs] | assert <S> <P> <O> | query <form> | explain",
        )

    return DialogDoc(uri=uri, imports=imports, statements=statements)
