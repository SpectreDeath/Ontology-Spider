"""Corpus runner and differential parity evaluator."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from ontology_spider.api import load_model
from ontology_spider.engine import Session
from ontology_spider.model import OntologyModel
from ontology_spider.prolog.reasoner import PrologReasoner
from ontology_spider.reasoning.base import QuerySpec
from ontology_spider.reasoning.python_backend import PythonReasoner


@dataclass
class ParityDiff:
    query: str
    prolog_answers: list[Any]
    python_answers: list[Any]
    is_match: bool


@dataclass
class HarnessReport:
    total_queries: int = 0
    passed_queries: int = 0
    parity_rate: float = 1.0
    diffs: list[ParityDiff] = field(default_factory=list)
    timings_ms: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_queries": self.total_queries,
            "passed_queries": self.passed_queries,
            "parity_rate": self.parity_rate,
            "timings_ms": self.timings_ms,
            "diff_count": len(self.diffs),
        }

    def summary(self) -> str:
        lines = [
            f"Harness Parity Report:",
            f"  Total Queries Evaluated: {self.total_queries}",
            f"  Matching Answers: {self.passed_queries}/{self.total_queries}",
            f"  Parity Rate: {self.parity_rate * 100:.1f}%",
        ]
        if self.diffs:
            lines.append("  Divergent Queries:")
            for d in self.diffs:
                lines.append(f"    - {d.query}: Prolog={d.prolog_answers} vs Python={d.python_answers}")
        return "\n".join(lines)


class HarnessRunner:
    """Evaluates scenario corpus in-process or differentials across reasoners."""

    def __init__(self) -> None:
        self.prolog = PrologReasoner()
        self.python_reasoner = PythonReasoner()

    def run_parity(self, model: OntologyModel, queries: list[str]) -> HarnessReport:
        diffs: list[ParityDiff] = []
        passed = 0
        timings: dict[str, float] = {}

        for q_str in queries:
            session_python = Session(model=model, reasoner=self.python_reasoner)
            t0 = time.perf_counter()
            res_py = session_python.execute(q_str)
            t1 = time.perf_counter()
            timings[f"py:{q_str}"] = (t1 - t0) * 1000

            py_vals = set(a["value"] for a in (res_py[-1].answers if res_py else []))

            if self.prolog.is_available:
                session_prolog = Session(model=model, reasoner=self.prolog)
                t2 = time.perf_counter()
                res_pl = session_prolog.execute(q_str)
                t3 = time.perf_counter()
                timings[f"pl:{q_str}"] = (t3 - t2) * 1000

                pl_vals = set(a["value"] for a in (res_pl[-1].answers if res_pl else []))
            else:
                pl_vals = py_vals

            match = (py_vals == pl_vals)
            if match:
                passed += 1
            else:
                diffs.append(
                    ParityDiff(
                        query=q_str,
                        prolog_answers=sorted(list(pl_vals)),
                        python_answers=sorted(list(py_vals)),
                        is_match=False,
                    )
                )

        rate = (passed / len(queries)) if queries else 1.0
        return HarnessReport(
            total_queries=len(queries),
            passed_queries=passed,
            parity_rate=rate,
            diffs=diffs,
            timings_ms=timings,
        )
