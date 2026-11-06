"""Persistent SWI-Prolog worker process communicating over stdin/stdout lines."""

from __future__ import annotations

import atexit
import json
import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Any, Optional


class PersistentPrologWorker:
    """Manages a long-lived swipl subprocess to eliminate per-query startup latency."""

    def __init__(self, swipl_path: str, rules_path: Path) -> None:
        self.swipl_path = swipl_path
        self.rules_path = rules_path
        self._proc: Optional[subprocess.Popen[str]] = None
        self._lock = threading.Lock()
        self._loaded_key: Optional[tuple[str, int]] = None
        self._tmpdir = tempfile.TemporaryDirectory()
        atexit.register(self.close)

    def _ensure_started(self) -> subprocess.Popen[str]:
        if self._proc is not None and self._proc.poll() is None:
            return self._proc

        worker_pl = Path(self._tmpdir.name) / "worker.pl"
        worker_script = f"""
:- if(exists_source(library(http/json))).
:- use_module(library(http/json)).
:- elif(exists_source(library(json))).
:- use_module(library(json)).
:- endif.

:- consult('{self.rules_path.as_posix()}').

worker_loop :-
    read_line_to_string(user_input, Line),
    ( Line == end_of_file ->
        halt(0)
    ; Line == "" ->
        worker_loop
    ;
        handle_line(Line),
        worker_loop
    ).

handle_line(Line) :-
    catch(
        (
            atom_json_dict(Line, Req, []),
            Cmd = Req.get(cmd),
            ( Cmd == "load_facts" ->
                File = Req.get(file),
                retractall(triple(_, _, _, _)),
                retractall(attribute(_, _, _)),
                style_check(-singleton),
                load_files(File, [silent(true)]),
                json_write(current_output, json([status=ok]), [width(0)])
            ; Cmd == "query" ->
                GoalStr = Req.get(goal),
                MaxInf = Req.get(max_inferences),
                term_string(active_goal(Result) :- GoalBody, GoalStr),
                call_with_inference_limit(
                    findall(Result, GoalBody, RawResults),
                    MaxInf,
                    InfStatus
                ),
                ( InfStatus == inference_limit_exceeded ->
                    json_write(current_output, json([status=inference_limit_exceeded, limit=MaxInf]), [width(0)])
                ;
                    json_write(current_output, json([status=ok, answers=RawResults]), [width(0)])
                )
            ;
                json_write(current_output, json([status=error, error=unknown_cmd]), [width(0)])
            )
        ),
        Err,
        (
            term_string(Err, ErrStr),
            json_write(current_output, json([status=error, error=ErrStr]), [width(0)])
        )
    ),
    nl,
    flush_output(current_output).

:- initialization(worker_loop, main).
"""
        worker_pl.write_text(worker_script, encoding="utf-8")
        cmd = [
            self.swipl_path,
            "--no-pce",
            "--no-packs",
            "--tty=false",
            "-q",
            str(worker_pl),
        ]
        self._proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )
        self._loaded_key = None
        return self._proc

    def sync_facts(self, cache_key: tuple[str, int], facts_text: str) -> None:
        with self._lock:
            proc = self._ensure_started()
            if self._loaded_key == cache_key:
                return
            facts_file = Path(self._tmpdir.name) / "active_facts.pl"
            facts_file.write_text(facts_text, encoding="utf-8")
            req = json.dumps({"cmd": "load_facts", "file": facts_file.as_posix()})
            assert proc.stdin is not None and proc.stdout is not None
            proc.stdin.write(req + "\n")
            proc.stdin.flush()
            resp_line = proc.stdout.readline()
            if not resp_line:
                self._kill_proc()
                raise RuntimeError("Prolog worker terminated unexpectedly during load_facts")
            data = json.loads(resp_line)
            if data.get("status") != "ok":
                raise RuntimeError(f"Failed to load facts into worker: {data}")
            self._loaded_key = cache_key

    def execute_goal(self, goal_str: str, max_inferences: int, timeout_seconds: int) -> dict[str, Any]:
        with self._lock:
            proc = self._ensure_started()
            clause_str = f"active_goal(Result) :- ({goal_str})."
            req = json.dumps({
                "cmd": "query",
                "goal": clause_str,
                "max_inferences": max_inferences,
            })
            assert proc.stdin is not None and proc.stdout is not None

            result_holder: list[Optional[str]] = [None]
            err_holder: list[Optional[BaseException]] = [None]

            def reader() -> None:
                try:
                    assert proc.stdout is not None
                    result_holder[0] = proc.stdout.readline()
                except BaseException as e:
                    err_holder[0] = e

            proc.stdin.write(req + "\n")
            proc.stdin.flush()

            t = threading.Thread(target=reader, daemon=True)
            t.start()
            t.join(timeout=timeout_seconds)
            if t.is_alive():
                self._kill_proc()
                raise TimeoutError(f"Prolog query timed out after {timeout_seconds}s")

            if err_holder[0] is not None:
                self._kill_proc()
                raise err_holder[0]

            line = result_holder[0]
            if not line:
                self._kill_proc()
                raise RuntimeError("Empty response from Prolog worker")
            return json.loads(line)

    def _kill_proc(self) -> None:
        if self._proc is not None:
            try:
                self._proc.kill()
                self._proc.wait(timeout=1)
            except Exception:
                pass
            for stream in (self._proc.stdin, self._proc.stdout, self._proc.stderr):
                if stream is not None:
                    try:
                        stream.close()
                    except Exception:
                        pass
            self._proc = None
            self._loaded_key = None

    def close(self) -> None:
        with self._lock:
            self._kill_proc()
            try:
                self._tmpdir.cleanup()
            except Exception:
                pass
