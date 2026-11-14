"""Pure-stdlib Shannon/Laya attribute entropy ranking and Gruber competency evaluation."""

from __future__ import annotations

import json
import math
from collections import Counter
from collections.abc import Sequence
from typing import Any

from ontology_spider.model import DOMAIN, RANGE, SUBCLASS_OF, OntologyModel
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
        ranked.append({
            "attribute": attr_name,
            "entropy_bits": round(entropy_bits, 4),
            "coverage": round(coverage, 4),
            "distinct_values": len(counts),
            "laya_score": laya_score,
        })

    ranked.sort(key=lambda item: (-item["laya_score"], -item["entropy_bits"], item["attribute"]))
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

    total_assertions = len(model.assertions)
    taxonomic_assertions = sum(
        1 for a in model.assertions.values() if a.relation.predicate == SUBCLASS_OF
    )
    extendibility = (
        round(min(1.0, taxonomic_assertions / max(1, total_assertions)), 4)
        if total_assertions > 0
        else 0.0
    )
    minimal_encoding_bias = 1.0
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
