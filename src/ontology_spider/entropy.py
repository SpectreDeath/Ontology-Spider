"""Pure-stdlib Shannon/Laya attribute entropy ranking and Gruber competency evaluation."""

from __future__ import annotations

import json
import math
from collections import Counter
from collections.abc import Sequence
from typing import Any

from ontology_spider.model import (
    BUILTIN_SCHEMA_PREDICATES,
    DOMAIN,
    INSTANCE_OF,
    RANGE,
    SUBCLASS_OF,
    OntologyModel,
)
from ontology_spider.validation import OntologyValidator


def _freeze_value(value: Any) -> str:
    if isinstance(value, (dict, list, tuple, set)):
        return json.dumps(value, sort_keys=True, default=str)
    return str(value)


def rank_discriminating_attributes(
    model: OntologyModel,
    candidate_ids: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    """Rank entity attributes by expected information gain (Shannon entropy * coverage)."""
    if candidate_ids is None:
        entities = list(model.entities.values())
    else:
        entities = [model.entities[eid] for eid in candidate_ids if eid in model.entities]

    total = len(entities)
    if total == 0:
        return []

    attr_values: dict[str, list[str]] = {}
    for ent in entities:
        for key, val in ent.attributes.items():
            if str(key).startswith("_"):
                continue
            attr_values.setdefault(str(key), []).append(_freeze_value(val))

    ranked: list[dict[str, Any]] = []
    for attr_name, values in attr_values.items():
        n_present = len(values)
        if n_present == 0:
            continue
        counts = Counter(values)
        entropy_bits = 0.0
        for count in counts.values():
            if count > 0:
                p = count / n_present
                entropy_bits -= p * math.log2(p)
        coverage = n_present / total
        laya_score = round(entropy_bits * coverage, 4)
        distinct_count = len(counts)
        uniqueness_ratio = distinct_count / n_present
        is_identifier_like = n_present >= 10 and uniqueness_ratio >= 0.80
        cardinality_factor = (
            (n_present - distinct_count) / max(1, n_present - 1)
            if n_present >= 10
            else 1.0
        )
        classification_score = round(laya_score * cardinality_factor, 4)
        ranked.append({
            "attribute": attr_name,
            "entropy_bits": round(entropy_bits, 4),
            "coverage": round(coverage, 4),
            "distinct_values": distinct_count,
            "laya_score": laya_score,
            "classification_score": classification_score,
            "is_identifier_like": is_identifier_like,
        })

    ranked.sort(
        key=lambda item: (
            bool(item["is_identifier_like"]),
            -item["classification_score"],
            -item["laya_score"],
            -item["entropy_bits"],
            item["attribute"],
        )
    )
    return ranked


def evaluate_competency_questions(
    model: OntologyModel,
    questions: Sequence[str],
) -> dict[str, Any]:
    """Evaluate .dialog competency questions and compute Gruber 5-criteria scorecard."""
    from ontology_spider.engine import Engine

    engine = Engine()
    question_results: list[dict[str, Any]] = []
    answered_count = 0

    for raw_q in questions:
        q_str = raw_q.strip()
        if not q_str:
            continue
        query_line = q_str if q_str.lower().startswith("query ") else f"query {q_str}"
        res = engine.query(model, query_line)
        ans_values = [a.get("value") for a in res.answers]
        passed = len(ans_values) > 0
        if passed:
            answered_count += 1
        question_results.append({
            "query": query_line,
            "passed": passed,
            "answers_count": len(ans_values),
            "answers": ans_values,
        })

    violations = OntologyValidator().validate(model)
    v_dicts = [v.to_dict() for v in violations]

    total_entities = len(model.entities)
    documented_entities = sum(
        1 for ent in model.entities.values() if bool(ent.name) or bool(ent.attributes)
    )
    relations_with_schema = {
        a.relation.subject
        for a in model.assertions.values()
        if a.relation.predicate in (DOMAIN, RANGE)
    }
    clarity = (
        round((documented_entities + min(len(relations_with_schema), 1)) / (total_entities + 1), 4)
        if total_entities > 0
        else 1.0
    )
    coherence = 1.0 if not violations else round(max(0.0, 1.0 - 0.25 * len(violations)), 4)

    subclass_asrts = [
        a for a in model.assertions.values() if a.relation.predicate == SUBCLASS_OF
    ]
    taxonomic_assertions = len(subclass_asrts)
    all_classes = (
        {a.relation.subject for a in subclass_asrts}
        | {a.relation.object for a in subclass_asrts}
        | {
            a.relation.object
            for a in model.assertions.values()
            if a.relation.predicate == INSTANCE_OF
        }
    )
    extendibility = (
        round(min(1.0, taxonomic_assertions / max(1, len(all_classes))), 4)
        if taxonomic_assertions > 0
        else 0.0
    )
    non_builtin_preds = {
        a.relation.predicate
        for a in model.assertions.values()
        if a.relation.predicate not in BUILTIN_SCHEMA_PREDICATES
    }
    minimal_encoding_bias = (
        round(len(relations_with_schema & non_builtin_preds) / len(non_builtin_preds), 4)
        if non_builtin_preds
        else 1.0
    )
    evaluated_count = len(question_results)
    minimal_commitment = (
        round(answered_count / evaluated_count, 4) if evaluated_count > 0 else 1.0
    )
    overall_score = round(
        (clarity + coherence + extendibility + minimal_encoding_bias + minimal_commitment) / 5.0,
        4,
    )

    return {
        "uri": model.uri,
        "total_questions": evaluated_count,
        "answered_questions": answered_count,
        "violation_count": len(violations),
        "clarity": clarity,
        "coherence": coherence,
        "extendibility": extendibility,
        "minimal_encoding_bias": minimal_encoding_bias,
        "minimal_commitment": minimal_commitment,
        "overall_score": overall_score,
        "question_results": question_results,
        "violations": v_dicts,
    }
