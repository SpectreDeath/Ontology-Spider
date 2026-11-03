"""Parser and AST for the .dialog controlled conversational language."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Union


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
    subject: Optional[str] = None
    predicate: Optional[str] = None
    object: Optional[str] = None
    filter_key: Optional[str] = None
    filter_val: Optional[str] = None
    subquery: Optional[DialogQuery] = None
    raw_text: str = ""
    line_num: int = 1


@dataclass
class DialogDoc:
    uri: str
    imports: list[DialogImport] = field(default_factory=list)
    statements: list[
        Union[DialogImport, DialogEntityDecl, DialogAssertion, DialogQuery]
    ] = field(default_factory=list)



def _parse_attributes(attr_str: str, line_num: int) -> dict[str, Any]:
    """Parse key=value pairs inside brackets, e.g. [weight=0.9, category=mammal]."""
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

    attributes: dict[str, Any] = {}
    for item in content.split(","):
        item = item.strip()
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
        v = v.strip().strip('"').strip("'")
        # Try numeric conversion
        try:
            if "." in v:
                attributes[k] = float(v)
            else:
                attributes[k] = int(v)
        except ValueError:
            attributes[k] = v
    return attributes


def parse_dialog(text: str) -> DialogDoc:
    """Parse a .dialog file into a typed DialogDoc AST."""
    lines = text.splitlines()
    uri = "urn:dialog:unnamed"
    imports: list[DialogImport] = []
    statements: list[Union[DialogImport, DialogAssertion, DialogQuery]] = []

    header_found = False

    for idx, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        # Strip comments and skip empty lines
        if not line or line.startswith("#"):
            continue

        # Header declaration: dialog <URI> or ontology <URI>
        if line.startswith("dialog ") or line.startswith("ontology "):
            parts = line.split(maxsplit=1)
            uri = parts[1].strip()
            header_found = True
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
            attrs: dict[str, Any] = {}
            if "[" in body and body.endswith("]"):
                main_part, attr_part = body.rsplit("[", 1)
                attr_part = "[" + attr_part
                attrs = _parse_attributes(attr_part, idx)
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
                    attributes=attrs,
                    line_num=idx,
                )
            )
            continue

        # Assertion statement:
        # assert <subject> <predicate> <object> [attr=val, ...]
        if line.startswith("assert "):
            body = line[7:].strip()
            # Check for attributes block at end
            attrs: dict[str, Any] = {}
            if "[" in body and body.endswith("]"):
                main_part, attr_part = body.rsplit("[", 1)
                attr_part = "[" + attr_part
                attrs = _parse_attributes(attr_part, idx)
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
                attributes=attrs,
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
                for s in sub_doc.statements:
                    if isinstance(s, DialogQuery):
                        subquery = s
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
            # Normalize trailing question mark without stripping standalone wildcard '?'
            if query_body.endswith("?") and not query_body.endswith(" ?"):
                clean_body = query_body[:-1].strip()
            else:
                clean_body = query_body

            # Pattern 1: what is <X>
            m_what_is = re.match(r"^what\s+is\s+(\S+)$", clean_body, re.IGNORECASE)
            if m_what_is:
                statements.append(
                    DialogQuery(
                        kind="lookup",
                        subject=m_what_is.group(1),
                        raw_text=line,
                        line_num=idx,
                    )
                )
                continue

            # Pattern 2: ancestors of <X>
            m_anc = re.match(r"^ancestors\s+of\s+(\S+)$", clean_body, re.IGNORECASE)
            if m_anc:
                statements.append(
                    DialogQuery(
                        kind="ancestors",
                        subject=m_anc.group(1),
                        raw_text=line,
                        line_num=idx,
                    )
                )
                continue

            # Pattern 3: transitive <predicate> from <subject>
            m_trans = re.match(
                r"^transitive\s+(\S+)\s+from\s+(\S+)$", clean_body, re.IGNORECASE
            )
            if m_trans:
                statements.append(
                    DialogQuery(
                        kind="transitive",
                        predicate=m_trans.group(1),
                        subject=m_trans.group(2),
                        raw_text=line,
                        line_num=idx,
                    )
                )
                continue

            # Pattern 4: filter <predicate> where <key>=<val>
            m_filter = re.match(
                r"^filter\s+(\S+)\s+where\s+(\S+)\s*=\s*(\S+)$",
                clean_body,
                re.IGNORECASE,
            )
            if m_filter:
                statements.append(
                    DialogQuery(
                        kind="filter",
                        predicate=m_filter.group(1),
                        filter_key=m_filter.group(2),
                        filter_val=m_filter.group(3).strip('"').strip("'"),
                        raw_text=line,
                        line_num=idx,
                    )
                )
                continue

            # Pattern 4b: recommend <Class> where <attr> = <val> OR recommend <Class>
            m_rec = re.match(
                r"^recommend\s+(\S+)(?:\s+where\s+(\S+)\s*=\s*(\S+))?$",
                clean_body,
                re.IGNORECASE,
            )
            if m_rec:
                statements.append(
                    DialogQuery(
                        kind="recommend",
                        object=m_rec.group(1),
                        filter_key=m_rec.group(2) if m_rec.group(2) else None,
                        filter_val=m_rec.group(3).strip('"').strip("'")
                        if m_rec.group(3)
                        else None,
                        raw_text=line,
                        line_num=idx,
                    )
                )
                continue


            # Pattern 5: general triple pattern query: <subject> <predicate> <object>
            q_tokens = clean_body.split()
            if len(q_tokens) == 3:
                s, p, o = q_tokens
                statements.append(
                    DialogQuery(
                        kind="pattern",
                        subject=None if s in ("?", "*", "_") else s,
                        predicate=None if p in ("?", "*", "_") else p,
                        object=None if o in ("?", "*", "_") else o,
                        raw_text=line,
                        line_num=idx,
                    )
                )
                continue

            raise ParseError(
                idx,
                f"Unrecognized query syntax: '{query_body}'",
                "query what is <X>? | query ancestors of <X>? | query transitive <rel> from <X>? | query <S> <P> <O>?",
            )

        # If line does not match any recognized command:
        raise ParseError(
            idx,
            f"Unexpected statement: '{line}'",
            "dialog <URI> | import <path> | entity <id> [attrs] | assert <S> <P> <O> | query <form> | explain",
        )

    return DialogDoc(uri=uri, imports=imports, statements=statements)
