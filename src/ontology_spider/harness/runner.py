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
class ScenarioResult:
    scenario: str
    passed: bool
    queries_run: int
    queries_passed: int
    parity_rate: float
    violations_passed: bool
    details: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario": self.scenario,
            "passed": self.passed,
            "queries_run": self.queries_run,
            "queries_passed": self.queries_passed,
            "parity_rate": self.parity_rate,
            "violations_passed": self.violations_passed,
            "details": self.details,
        }


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

            py_answers = res_py[-1].answers if res_py else []
            py_vals = [a["value"] for a in py_answers]
            py_paths = [a.get("path") for a in py_answers]
            py_facts = [a.get("fact_ids") for a in py_answers]

            if self.prolog.is_available:
                session_prolog = Session(model=model, reasoner=self.prolog)
                t2 = time.perf_counter()
                res_pl = session_prolog.execute(q_str)
                t3 = time.perf_counter()
                timings[f"pl:{q_str}"] = (t3 - t2) * 1000

                pl_answers = res_pl[-1].answers if res_pl else []
                pl_vals = [a["value"] for a in pl_answers]
                pl_paths = [a.get("path") for a in pl_answers]
                pl_facts = [a.get("fact_ids") for a in pl_answers]
            else:
                pl_vals = py_vals
                pl_paths = py_paths
                pl_facts = py_facts
                pl_answers = py_answers

            match = (py_vals == pl_vals and py_paths == pl_paths and py_facts == pl_facts)
            if match:
                passed += 1
            else:
                diffs.append(
                    ParityDiff(
                        query=q_str,
                        prolog_answers=pl_answers,
                        python_answers=py_answers,
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

    def run_scenario(
        self,
        spec: dict[str, Any],
        backend: str = "both",
        transport: str = "inproc",
    ) -> ScenarioResult:
        from ontology_spider.validation import OntologyValidator
        sc_name = spec.get("scenario", "unnamed")
        model_path = spec.get("model")
        queries = spec.get("queries", [])
        expected_violations = spec.get("expected_violations")

        if transport == "inproc":
            model = load_model(model_path) if model_path else OntologyModel(uri=f"urn:scenario:{sc_name}")
            violations_ok = True
            if expected_violations is not None:
                validator = OntologyValidator()
                violations = validator.validate(model)
                actual_types = [v.check_type for v in violations]
                if isinstance(expected_violations, int):
                    violations_ok = (len(violations) == expected_violations)
                elif isinstance(expected_violations, list):
                    for ev in expected_violations:
                        if ev not in actual_types:
                            violations_ok = False
                            break

            if backend == "both":
                report = self.run_parity(model, queries)
                passed = (report.parity_rate == 1.0) and violations_ok
                details = report.summary()
                return ScenarioResult(
                    scenario=sc_name,
                    passed=passed,
                    queries_run=report.total_queries,
                    queries_passed=report.passed_queries,
                    parity_rate=report.parity_rate,
                    violations_passed=violations_ok,
                    details=details,
                )
            else:
                reasoner = self.prolog if backend == "prolog" else self.python_reasoner
                session = Session(model=model, reasoner=reasoner)
                q_passed = 0
                for q in queries:
                    res = session.execute(q)
                    if res:
                        q_passed += 1
                rate = (q_passed / len(queries)) if queries else 1.0
                passed = (q_passed == len(queries)) and violations_ok
                return ScenarioResult(
                    scenario=sc_name,
                    passed=passed,
                    queries_run=len(queries),
                    queries_passed=q_passed,
                    parity_rate=rate,
                    violations_passed=violations_ok,
                    details=f"Ran {q_passed}/{len(queries)} queries on {backend} (inproc)",
                )

        elif transport == "mcp":
            from ontology_spider.mcp.server import MCPServer
            from ontology_spider.mcp.transport import StdioTransport

            class InMemoryTransport(StdioTransport):
                def __init__(self, msgs: list[dict[str, Any]]) -> None:
                    self.in_msgs = list(msgs)
                    self.out_msgs: list[dict[str, Any]] = []
                def read_message(self) -> Optional[dict[str, Any]]:
                    if self.in_msgs:
                        return self.in_msgs.pop(0)
                    return None
                def write_message(self, message: dict[str, Any]) -> None:
                    self.out_msgs.append(message)

            in_msgs = [
                {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
                {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
            ]
            if model_path:
                in_msgs.append({
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {"name": "session_open", "arguments": {"session_id": "sc_sess", "model_path": model_path}},
                })
            else:
                in_msgs.append({
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": "tools/call",
                    "params": {"name": "session_open", "arguments": {"session_id": "sc_sess"}},
                })

            req_id_to_q = {}
            for idx, q in enumerate(queries, start=3):
                req_id_to_q[idx] = q
                in_msgs.append({
                    "jsonrpc": "2.0",
                    "id": idx,
                    "method": "tools/call",
                    "params": {"name": "query", "arguments": {"session_id": "sc_sess", "query": q}},
                })

            val_req_id = None
            if expected_violations is not None:
                val_req_id = 9999
                in_msgs.append({
                    "jsonrpc": "2.0",
                    "id": val_req_id,
                    "method": "tools/call",
                    "params": {"name": "validate", "arguments": {"session_id": "sc_sess"}},
                })

            b_arg = None if backend == "both" else backend
            transport_obj = InMemoryTransport(in_msgs)
            server = MCPServer(transport=transport_obj, backend=b_arg)
            server.run()

            responses_by_id = {m.get("id"): m for m in transport_obj.out_msgs if "id" in m}
            q_passed = 0
            for req_id in req_id_to_q:
                resp = responses_by_id.get(req_id)
                if resp and "error" not in resp:
                    q_passed += 1

            violations_ok = True
            if val_req_id is not None:
                resp = responses_by_id.get(val_req_id)
                if resp and "error" not in resp:
                    actual_violations = resp.get("result", {}).get("violations", [])
                    actual_types = [v.get("check_type") for v in actual_violations]
                    if isinstance(expected_violations, int):
                        violations_ok = (len(actual_violations) == expected_violations)
                    elif isinstance(expected_violations, list):
                        for ev in expected_violations:
                            if ev not in actual_types:
                                violations_ok = False
                                break
                else:
                    violations_ok = False

            rate = (q_passed / len(queries)) if queries else 1.0
            passed = (q_passed == len(queries)) and violations_ok
            return ScenarioResult(
                scenario=sc_name,
                passed=passed,
                queries_run=len(queries),
                queries_passed=q_passed,
                parity_rate=rate,
                violations_passed=violations_ok,
                details=f"Ran {q_passed}/{len(queries)} queries over MCP ({backend})",
            )
