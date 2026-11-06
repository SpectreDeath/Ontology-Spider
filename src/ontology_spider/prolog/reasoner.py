"""SWI-Prolog reasoner bridge executing queries with proof traces and limits."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from ontology_spider.model import Assertion, OntologyModel
from ontology_spider.prolog.translator import model_to_prolog_facts, prolog_safe_string


class PrologError(Exception):
    """Base error for Prolog reasoning."""


class PrologUnavailableError(PrologError):
    """Raised when swipl executable is not installed on the system."""


class PrologExecutionError(PrologError):
    """Raised when a query fails runtime caps or execution constraints."""


class QueryTimeoutError(PrologError):
    """Raised when a query exceeds its allocated time limit."""


class QueryInferenceLimitError(PrologError):
    """Raised when a query exceeds its allocated inference cap."""


@dataclass
class Explanation:
    """Audit trace proving how an answer was derived."""
    rules_fired: list[str] = field(default_factory=list)
    fact_ids: list[str] = field(default_factory=list)
    path: list[str] = field(default_factory=list)
    provenance_assertions: list[Assertion] = field(default_factory=list)

    def summary(self) -> str:
        lines = []
        if self.rules_fired:
            lines.append(f"Rules: {', '.join(self.rules_fired)}")
        if self.path:
            lines.append(f"Path: {' -> '.join(self.path)}")
        if self.provenance_assertions:
            lines.append("Base Facts:")
            for asrt in self.provenance_assertions:
                p = asrt.provenance
                src_info = f"source={p.source}"
                if p.turn_id:
                    src_info += f", turn={p.turn_id}"
                lines.append(
                    f"  - [{asrt.assertion_id}] ({asrt.relation.subject} {asrt.relation.predicate} {asrt.relation.object}) ({src_info})"
                )
        return "\n".join(lines)


@dataclass
class ReasonerAnswer:
    """An individual derived answer item with its explanation."""
    value: Any
    explanation: Explanation


@dataclass
class ReasonerResult:
    """Complete results of a query evaluation."""
    query_goal: str
    answers: list[ReasonerAnswer]
    raw_response: dict[str, Any] = field(default_factory=dict)


def find_swipl_executable() -> Optional[str]:
    """Locate the SWI-Prolog executable on PATH or standard directories."""
    found = shutil.which("swipl")
    if found:
        return found

    # Windows fallback locations
    windows_candidates = [
        r"C:\Program Files\swipl\bin\swipl.exe",
        r"C:\Program Files (x86)\swipl\bin\swipl.exe",
    ]
    for cand in windows_candidates:
        if os.path.isfile(cand):
            return cand

    # Linux / macOS fallback locations
    posix_candidates = [
        "/usr/bin/swipl",
        "/usr/local/bin/swipl",
        "/opt/homebrew/bin/swipl",
    ]
    for cand in posix_candidates:
        if os.path.isfile(cand):
            return cand

    return None


class PrologReasoner:
    """Thread-safe interface to the SWI-Prolog reasoner with process isolation."""

    _lock = threading.Lock()

    def __init__(
        self, swipl_path: Optional[str] = None, max_results: int = 1000
    ) -> None:
        self.swipl_path = swipl_path or find_swipl_executable()
        self.rules_path = Path(__file__).parent / "rules.pl"
        self.max_results = max_results
        self._facts_cache: OrderedDict[tuple[str, int], str] = OrderedDict()
        self._cache_capacity: int = 8

    @property
    def is_available(self) -> bool:
        return bool(self.swipl_path and os.path.isfile(self.swipl_path))

    @property
    def name(self) -> str:
        return "prolog"

    def query(
        self,
        model: OntologyModel,
        goal_type: str | Any = "",
        subject: Optional[str] = None,
        predicate: Optional[str] = None,
        object: Optional[str] = None,
        req_key: Optional[str] = None,
        req_val: Optional[Any] = None,
        timeout_seconds: int = 10,
        max_inferences: int = 1000000,
    ) -> ReasonerResult:
        """Run a query goal against model facts using SWI-Prolog."""
        if not self.is_available:
            raise PrologUnavailableError(
                "SWI-Prolog (swipl) was not found. Please install SWI-Prolog to enable logic reasoning."
            )

        # Support QuerySpec instance passed as goal_type
        if hasattr(goal_type, "kind"):
            spec = goal_type
            g_type = spec.kind
            s = spec.subject or (spec.object if spec.kind == "recommend" else None)
            p = spec.predicate
            o = spec.object
            rk = spec.filter_key
            rv = spec.filter_val
            to = spec.timeout_seconds
            mi = spec.max_inferences
        else:
            g_type = str(goal_type)
            s = subject
            p = predicate
            o = object
            rk = req_key
            rv = req_val
            to = timeout_seconds
            mi = max_inferences

        with self._lock:
            return self._execute_under_lock(
                model=model,
                goal_type=g_type,
                subject=s,
                predicate=p,
                object=o,
                req_key=rk,
                req_val=rv,
                timeout_seconds=to,
                max_inferences=mi,
            )

    def _execute_under_lock(
        self,
        model: OntologyModel,
        goal_type: str,
        subject: Optional[str],
        predicate: Optional[str],
        object: Optional[str],
        req_key: Optional[str],
        req_val: Optional[Any],
        timeout_seconds: int,
        max_inferences: int,
    ) -> ReasonerResult:
        model_uuid = getattr(model, "uuid", str(id(model)))
        cache_key = (model_uuid, getattr(model, "version", 0))
        if cache_key in self._facts_cache:
            facts_text = self._facts_cache[cache_key]
            self._facts_cache.move_to_end(cache_key)
        else:
            facts_text = model_to_prolog_facts(model)
            self._facts_cache[cache_key] = facts_text
            self._facts_cache.move_to_end(cache_key)
            if len(self._facts_cache) > self._cache_capacity:
                self._facts_cache.popitem(last=False)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            facts_file = tmppath / "facts.pl"
            facts_file.write_text(facts_text, encoding="utf-8")

            # Formulate the goal
            s = prolog_safe_string(subject) if subject else "Subj"
            p = prolog_safe_string(predicate) if predicate else "Pred"
            o = prolog_safe_string(object) if object else "Obj"

            if goal_type == "transitive":
                if not subject or not predicate:
                    raise ValueError("Transitive query requires subject and predicate")
                goal_str = (
                    f"transitive_path({s}, {p}, Target, Path, Rules, FactIds), "
                    f"Result = json([value=Target, path=Path, rules=Rules, facts=FactIds])"
                )
            elif goal_type == "ancestors":
                if not subject:
                    raise ValueError("Ancestors query requires subject")
                goal_str = (
                    f"ancestor_of({s}, Ancestor, Path, Rules, FactIds), "
                    f"Result = json([value=Ancestor, path=Path, rules=Rules, facts=FactIds])"
                )
            elif goal_type == "recommend":
                if not subject:
                    raise ValueError("Recommend query requires subject")
                if req_key and req_val is not None:
                    rk = prolog_safe_string(req_key)
                    rv = prolog_safe_string(req_val)
                    goal_str = (
                        f"recommend_match({s}, {rk}, {rv}, Rec, Rules, FactIds), "
                        f"Result = json([value=Rec, rules=Rules, facts=FactIds, path=[{s}, Rec]])"
                    )
                else:
                    goal_str = (
                        f"recommend({s}, Rec, Rules, FactIds), "
                        f"Result = json([value=Rec, rules=Rules, facts=FactIds, path=[{s}, Rec]])"
                    )
            elif goal_type == "lookup":
                if not subject:
                    raise ValueError("Lookup query requires subject")
                goal_str = (
                    f"( triple({s}, Pred, Obj, AsrtId), OutS = {s}, OutO = Obj, Path = [{s}, Obj] "
                    f"; triple(Subj, Pred, {s}, AsrtId), OutS = Subj, OutO = {s}, Path = [Subj, {s}] ), "
                    f"format(string(Val), '(~w ~w ~w)', [OutS, Pred, OutO]), "
                    f"Result = json([value=Val, rules=['direct_fact'], facts=[AsrtId], path=Path])"
                )
            elif goal_type == "pattern":
                goal_str = (
                    f"triple({s}, {p}, {o}, AsrtId), "
                    f"Result = json([value=json([subject={s}, predicate={p}, object={o}]), "
                    f"rules=['base_fact'], facts=[AsrtId], path=[{s}, {o}]])"
                )
            elif goal_type == "infinite_loop_test":
                goal_str = "infinite_loop"
            else:
                raise ValueError(f"Unknown goal type: {goal_type}")

            # Script to run inside SWI-Prolog
            runner_script = f"""
:- if(exists_source(library(http/json))).
:- use_module(library(http/json)).
:- elif(exists_source(library(json))).
:- use_module(library(json)).
:- endif.

:- consult('{self.rules_path.as_posix()}').
:- consult('{facts_file.as_posix()}').

run :-
    catch(
        (
            call_with_inference_limit(
                findall(Result, ({goal_str}), RawResults),
                {max_inferences},
                InferenceStatus
            ),
            ( InferenceStatus == inference_limit_exceeded ->
                json_write(current_output, json([status=inference_limit_exceeded, limit={max_inferences}]))
            ;
                json_write(current_output, json([status=ok, answers=RawResults]))
            )
        ),
        Error,
        json_write(current_output, json([status=error, error=Error]))
    ),
    nl,
    flush_output,
    halt(0).
run :-
    halt(1).

:- initialization(run, main).
"""
            runner_file = tmppath / "runner.pl"
            runner_file.write_text(runner_script, encoding="utf-8")

            cmd = [
                self.swipl_path,
                "--no-pce",
                "--no-packs",
                "--tty=false",
                "-q",
                str(runner_file),
            ]
            try:
                proc = subprocess.run(
                    cmd,
                    stdin=subprocess.DEVNULL,
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds,
                )
            except subprocess.TimeoutExpired as exc:
                raise QueryTimeoutError(
                    f"Prolog query timed out after {timeout_seconds}s"
                ) from exc

            stdout = proc.stdout.strip()
            if not stdout:
                raise PrologError(f"Empty output from swipl. stderr: {proc.stderr}")

            # Extract full JSON block from stdout
            start_idx = stdout.find("{")
            end_idx = stdout.rfind("}")
            if start_idx == -1 or end_idx == -1 or end_idx < start_idx:
                raise PrologError(f"Failed to find JSON response in Prolog output: {stdout}")

            json_text = stdout[start_idx : end_idx + 1]
            try:
                data = json.loads(json_text)
            except json.JSONDecodeError as err:
                raise PrologError(f"Malformed JSON from Prolog: {json_text}") from err

            status = data.get("status")

            if status == "timeout":
                limit = data.get("limit", timeout_seconds)
                raise QueryTimeoutError(f"Prolog query timed out after {limit}s")

            if status == "inference_limit_exceeded":
                limit = data.get("limit", max_inferences)
                raise QueryInferenceLimitError(
                    f"Prolog query exceeded inference cap of {limit} steps"
                )

            if status == "error":
                raise PrologExecutionError(f"Prolog error: {data.get('error')}")

            raw_answers = data.get("answers", [])
            if len(raw_answers) > self.max_results:
                raise PrologExecutionError(
                    f"Query result count ({len(raw_answers)}) exceeds max_results cap ({self.max_results})."
                )

            answers: list[ReasonerAnswer] = []
            seen_answer_values = set()

            for item in raw_answers:
                val = item.get("value")
                # Deduplicate answers
                val_key = json.dumps(val, sort_keys=True) if isinstance(val, dict) else str(val)
                if val_key in seen_answer_values:
                    continue
                seen_answer_values.add(val_key)

                rules = item.get("rules", [])
                facts = item.get("facts", [])
                path = item.get("path", [])

                # Map fact IDs back to Track 1 Assertion objects
                provenance_assertions = [
                    model.assertions[fid]
                    for fid in facts
                    if fid in model.assertions
                ]

                explanation = Explanation(
                    rules_fired=rules,
                    fact_ids=facts,
                    path=path,
                    provenance_assertions=provenance_assertions,
                )
                answers.append(ReasonerAnswer(value=val, explanation=explanation))

            return ReasonerResult(
                query_goal=goal_str,
                answers=answers,
                raw_response=data,
            )
