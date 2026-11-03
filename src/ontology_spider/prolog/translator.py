"""Translation between OntologyModel and Prolog facts with safe escaping and round-tripping."""

from __future__ import annotations

import re
from typing import Any

from ontology_spider.model import (
    Assertion,
    Entity,
    OntologyModel,
    Provenance,
    Relation,
)


def prolog_safe_string(value: Any) -> str:
    """Escape and quote an atom or string safely for Prolog."""
    val_str = str(value)
    # Escape internal single quotes and backslashes
    escaped = val_str.replace("\\", "\\\\").replace("'", "\\'")
    return f"'{escaped}'"


def unescape_prolog_atom(atom_str: str) -> str:
    """Unescape an atom read from Prolog."""
    atom_str = atom_str.strip()
    if atom_str.startswith("'") and atom_str.endswith("'") and len(atom_str) >= 2:
        atom_str = atom_str[1:-1]
    return atom_str.replace("\\'", "'").replace("\\\\", "\\")


def model_to_prolog_facts(model: OntologyModel) -> str:
    """Serialize an OntologyModel into SWI-Prolog facts."""
    lines: list[str] = [
        f"% Ontology Facts for {model.uri}",
        ":- dynamic triple/4.",
        ":- dynamic attribute/3.",
    ]

    for asrt in model.assertions.values():
        s = prolog_safe_string(asrt.relation.subject)
        p = prolog_safe_string(asrt.relation.predicate)
        o = prolog_safe_string(asrt.relation.object)
        aid = prolog_safe_string(asrt.assertion_id)
        lines.append(f"triple({s}, {p}, {o}, {aid}).")

        for k, v in asrt.attributes.items():
            ek = prolog_safe_string(k)
            ev = prolog_safe_string(v)
            lines.append(f"attribute({aid}, {ek}, {ev}).")

    for ent in model.entities.values():
        eid = prolog_safe_string(ent.id)
        for k, v in ent.attributes.items():
            ek = prolog_safe_string(k)
            ev = prolog_safe_string(v)
            lines.append(f"attribute({eid}, {ek}, {ev}).")

    return "\n".join(lines) + "\n"


TRIPLE_FACT_REGEX = re.compile(
    r"^triple\(\s*'((?:\\'|[^'])*)'\s*,\s*'((?:\\'|[^'])*)'\s*,\s*'((?:\\'|[^'])*)'\s*,\s*'((?:\\'|[^'])*)'\s*\)\.$"
)

ATTRIBUTE_FACT_REGEX = re.compile(
    r"^attribute\(\s*'((?:\\'|[^'])*)'\s*,\s*'((?:\\'|[^'])*)'\s*,\s*'((?:\\'|[^'])*)'\s*\)\.$"
)


def _coerce_attr_val(raw: str) -> Any:
    try:
        if "." in raw:
            return float(raw)
        return int(raw)
    except ValueError:
        return raw


def prolog_facts_to_model(
    facts_text: str, uri: str = "urn:ontology:prolog_loaded"
) -> OntologyModel:
    """Reconstruct an OntologyModel from serialized Prolog facts for round-trip parity."""
    model = OntologyModel(uri=uri)
    deferred_attrs: list[tuple[str, str, Any]] = []

    for line in facts_text.splitlines():
        line = line.strip()
        if not line or line.startswith("%") or line.startswith(":-"):
            continue

        m = TRIPLE_FACT_REGEX.match(line)
        if m:
            s = unescape_prolog_atom(m.group(1))
            p = unescape_prolog_atom(m.group(2))
            o = unescape_prolog_atom(m.group(3))
            aid = unescape_prolog_atom(m.group(4))

            prov = Provenance(source="prolog_facts", turn_id=None)
            model.add_assertion(
                relation=Relation(subject=s, predicate=p, object=o),
                provenance=prov,
                assertion_id=aid,
            )
            continue

        ma = ATTRIBUTE_FACT_REGEX.match(line)
        if ma:
            target_id = unescape_prolog_atom(ma.group(1))
            k = unescape_prolog_atom(ma.group(2))
            v = _coerce_attr_val(unescape_prolog_atom(ma.group(3)))
            deferred_attrs.append((target_id, k, v))

    for target_id, k, v in deferred_attrs:
        if target_id in model.assertions:
            model.assertions[target_id].attributes[k] = v
        else:
            existing = model.get_entity(target_id)
            if existing:
                existing.attributes[k] = v
            else:
                model.add_entity(Entity(id=target_id, attributes={k: v}))

    return model

