# Track 0 — Architectural & Design Decisions

This document records the foundational decisions for the `Ontology-Spider` engine as mandated by Track 0 of the development plan. Every decision is grounded in concrete technical rationale, simplicity, and adherence to user guardrails.

---

## 1. Third-Party Dependency Approval & Guardrail

- **Decision**: Zero third-party runtime dependencies. The engine core is implemented entirely in standard library Python (`dataclasses`, `typing`, `json`, `subprocess`, `pathlib`, `argparse`). Testing and test execution are handled using stdlib `unittest`.
- **Status on Third-Party Packages**:
  - `pyproject.toml` lists `dependencies = []`.
  - Zero unapproved packages are installed or required.
  - If third-party dev tools (such as `pytest` or `ruff`) or FFI bindings (`pyswip`) are considered in the future, they require explicit written approval from the user before being added to dependencies.
- **Rationale**: Strictly obeys the user's standing guardrail: *"No new third-party dependencies without the user's explicit approval"*. Python's standard library provides all necessary primitives for data structures, serialization, subprocess orchestration, and test execution.

---

## 2. Language Grammar: Fresh Minimal Syntax vs. ASKE SADL/Dialog Port

- **Decision**: Design a fresh minimal `.dialog` syntax inspired by the concepts of ASKE Dialog, rather than porting the Eclipse Xtext SADL grammar directly.
- **Rationale**:
  1. The original ASKE Dialog was built as Eclipse plugins (`com.ge.research.sadl.darpa.aske.dialog.parent`) on Java 8 and Eclipse 2018-12. Porting or retaining the Xtext grammar introduces substantial Eclipse-era baggage without modern benefits.
  2. A fresh, human-readable, line/block-oriented syntax provides complete control over error messages (precise line numbers and token expectations instead of opaque parse stack traces).
  3. Avoids license entanglements while retaining the foundational dialogue model: header with model imports, assertions, conversational queries, and explanatory follow-ups.

---

## 3. Data Model: Semantic Triples + Canonical Built-in Vocabulary

- **Decision**: Triples `(subject, predicate, object)` + key-value attributes on entities and assertions, augmented with a canonical built-in schema relation vocabulary:
  - `instance_of`: Type membership linking an instance entity to a class entity.
  - `subclass_of`: Taxonomic hierarchy linking a subclass to a superclass.
  - `domain`: Restricts the subject class of a relation.
  - `range`: Restricts the object class/type of a relation.
  - `disjoint_with`: Declares mutual exclusivity between classes.
  - `acyclic`: Declares that a relation must not contain directed cycles.
- **Provenance**: Every assertion carries an immutable `assertion_id`, `source`, `timestamp`, `turn_id`, and optional `parent_turn_ids` (to support mixed-initiative retraction graphs).
- **Rationale**: Full OWL2 DL reasoning is deferred to Track 10. Triples plus this canonical built-in vocabulary cleanly satisfy all requirements of Tracks 1, 3, 4, 5, and 6 without the computational overhead or implementation complexity of description logic reasoners.

---

## 4. Reasoner Runtime & SWI-Prolog Bridge

- **Decision**: SWI-Prolog via a zero-Python-dependency `swipl` CLI/subprocess bridge with in-Prolog timeouts and process lifecycle management.
- **Comparison**:
  - `PySWIP` uses C FFI (`ctypes`) binding against `libswipl`. On Windows and Python 3.13 with SWI-Prolog 10.x, PySWIP is notoriously brittle (DLL lookup failures, thread safety lockouts, inability to cleanly interrupt C execution from Python threads).
  - A dedicated `swipl` subprocess bridge communicates via standard streams / batch scripts. It requires zero pip dependencies, handles SWI-Prolog 10.0.2 out of the box, cleanly enforces subprocess timeouts via `subprocess.run(timeout=...)` alongside internal `call_with_inference_limit/3`, and prevents engine memory pollution by ensuring dynamic facts are explicitly scoped or run in isolated invocations.
- **Fallback when SWI-Prolog is not installed**:
  - Degraded mode: In-memory triple storage, model loading, validation (such as simple cycle checks and domain/range checks), and `.dialog` parsing/export continue to function. If deductive reasoning or assumption-checking queries are invoked when `swipl` is unavailable, the engine falls back to an integrated pure-Python graph reasoner (BFS transitive closure and ancestry traversal) with proof traces.

---

## 5. Parser Implementation

- **Decision**: Hand-written recursive-descent / structured token scanner in pure standard library Python.
- **Rationale**:
  - Requires zero third-party parser packages (e.g. `lark`, `ply`, `antlr4-python3-runtime`).
  - Small, deterministic grammar can be parsed in <300 lines of robust, readable Python code.
  - Formats syntax errors with line numbers, columns, and helpful error messages rather than raw parser generator exceptions.

---

## 6. Python Floor

- **Decision**: Python `>= 3.10`.
- **Rationale**:
  - Aligns with the user's companion repositories (`Em-Cubed` and `brain-harness`, which both floor at 3.10).
  - Enables modern Python features: pattern matching (`match/case`), improved union type syntax (`X | Y`), and modern dataclass features, while remaining compatible with standard enterprise and developer installations.

---

## 7. Development Cycle Track 0 Decisions & Recommendations

### 7.1 MCP Server Implementation: Stdlib Hand-Roll
- **Decision**: Hand-roll the Model Context Protocol (MCP) server using Python's standard library (`sys.stdin`, `sys.stdout`, `json`) without importing third-party MCP SDKs (e.g. `mcp`).
- **Rationale**:
  - Strictly adheres to the zero-external-dependencies guardrail (`dependencies = []`).
  - Stdio JSON-RPC 2.0 transport requires <350 lines of code, covering `initialize`, `ping`, `tools/list`, `tools/call`, `resources/list`, and `resources/read`.

### 7.2 Canonical `recommend` Semantics: Transitive Subclass Closure
- **Decision**: Canonical `recommend <Class>` semantics evaluate over the full transitive reflexive closure of `subclass_of` relations, matching Python's graph search behavior rather than shallow 1-hop peer search.
- **Rationale**:
  - If `quadcopter subclass_of drone` and `drone subclass_of aerial_vehicle`, asking for recommendations of `aerial_vehicle` must include instances of `quadcopter`.
  - Prolog rules (`rules.pl`) were updated with `subclass_closure/3` to achieve 100% differential parity.

### 7.3 Grammar Realization: Multi-Attribute Recommend & Trailing Explain
- **Decision**: Implement grammar support in `dialog.py` for bracketed multi-attribute queries (`recommend <Class> [key=val, ...]`) and trailing `... explain`.
- **Rationale**:
  - Synchronizes the formal grammar with examples presented in documentation and the README.
  - Eliminates silent syntax errors when executing multi-constraint recommendations or requesting inline explanations.

### 7.4 Test & Benchmark Harness Placement
- **Decision**: Package the testing, synthetic topology generator, and benchmarking harness directly inside `src/ontology_spider/harness/` rather than outside in a detached directory.
- **Rationale**:
  - The harness is a product feature callable by agents and CI via `python -m ontology_spider.harness`.
  - Enables self-contained property checks, benchmarking, and differential parity tests across backends without relying on external test frameworks.

### 7.5 MCP Mutation & Sandboxing Policy
- **Status**: **Settled Decision** (ratified 2026-11-08 per Consolidated follow-through plan Track 0.1).
- **Exact Provenance**:
  - **Session / Channel**: Local Antigravity IDE session `a4389347-bf24-4794-85ec-998c4fb91def`, `ask_question` interactive multiple-choice widget (recorded in `.system_generated/logs/transcript.jsonl` steps `691`–`692`).
  - **Timestamps**: Question posed `2026-11-08T11:34:37-05:00` (`16:34:37Z`); user response completed `2026-11-08T11:40:35-05:00` (`16:40:35Z`).
  - **Question & Verbatim Selection**: `"Which MCP write default policy should be settled for Track 0.1?"` $\to$ `A1: (Recommended) Accept Argon's recommendation — in-memory session writes by default (read_only=False), file writes confined to --root, and --read-only disables all mutation (ratifies what the server currently ships)`.
- **Settled Policy**:
  - By default, allow in-memory session mutations (`assert_triple`, `declare_entity`, `retract`, `run_dialog`, `focus`, `constrain`) over stdio MCP (`read_only=False`).
  - Strictly disable all mutation tools when launched with `--read-only` (returning error code `-32001`).
  - Confine all file system reads and writes (`model_load`, `export`) to `--root` directory via `Path.resolve().relative_to(root_dir)`.
  - Enforce bounds on max active sessions (32) and max assertions per session (50,000).
- **Rationale**:
  - In-memory mutations permit agents to explore counterfactuals or build interactive ontologies without persistent disk side-effects, while `--read-only` provides a strict safety latch and `--root` prevents traversal escape. Ratified Argon's recommendation to match shipped server implementation.

### 7.6 CI Statement Coverage Progression and Fail-Under Gate
- **Decision**: Enforce a mandatory `--fail-under=90` gate in `.github/workflows/ci.yml` and keep statement coverage above 90% across the codebase.
- **Progression**:
  - `881a22a`: 78% statement coverage (3,069 statements, 665 missed; `python_backend.py` at 29%).
  - `0daeca5`: 91% statement coverage (3,074 statements, 274 missed across 89 unit tests; `python_backend.py` at 98%).
  - `7970a12` (Track 4 HEAD): 91% statement coverage (3,563 statements, 322 missed across 99 unit tests).
  - 2026-11-08 (Track 3 & 5 Corrections HEAD): 91% statement coverage (3,566 statements, 318 missed on Windows, 322 missed on Linux across 101 unit tests; `prolog/reasoner.py:95-101` Windows candidate fallbacks unhit on Linux).
- **Rationale**:
  - A strict 90% coverage bar ensures that newly added features (such as MCP transports, synthetic generators, elicitation amendments, and multi-attribute recommendations) do not create unexercised code paths or regressions.

### 7.7 Prolog BFS Frontier Reachability & Diamond DAG Termination
- **Decision**: Replace recursive DFS path search in `src/ontology_spider/prolog/rules.pl` (`transitive_path/6` and `ancestor_of/5`) with deterministic Breadth-First Search (BFS) frontier expansion (`bfs_transitive_all`, `bfs_ancestors_all`).
- **Rationale**:
  - Naive recursive DFS enumerates all simple paths between nodes, resulting in $O(2^N)$ path explosion on lattice and diamond DAGs. On a 20-node diamond lattice, Prolog previously enumerated 2,388 simple paths, exceeding the 1,000-result cap.
  - The BFS loop visits each reachable target node exactly once along its first insertion-ordered shortest proof path, executing the 20-node lattice ancestor query in ~1.5 ms without path explosion, exactly matching the Python reasoner's BFS behavior.

### 7.8 Benchmark Suite Budgets & Calibration Calibration Baseline
- **Decision**: Enforce performance budgets via `src/ontology_spider/harness/baselines/bench_budgets.json` in a dedicated CI job:
  1. `lattice_20_ancestors_p50_ms` < 15.0 ms
  2. `python_10k_query_p50_ms` < 5.0 ms
  3. `lattice_10k_validate_ms` < 1000.0 ms
  4. Full test suite execution < 4000.0 ms (target)
- **Baseline Machine Specs**:
  - OS: Windows 11 Pro 64-bit
  - CPU: AMD Ryzen 9 / x86_64
  - Python: 3.13.0 64-bit
  - SWI-Prolog: 9.2.x 64-bit (persistent worker subprocess bridge)

### 7.9 Architecture Review Dispositions & Refactorings (Track 5)
- **Date**: 2026-11-08
- **Dispositions**:
  - **5.1 Reasoner Sharing in TraversalDialogueManager**: `Session.__init__` now explicitly forwards `reasoner=self.reasoner` and timeout/inference parameters into `TraversalDialogueManager`, eliminating redundant `PrologReasoner` construction and facts cache duplication.
  - **5.2 Session Reasoner & Traversal Wiring**: Eliminated unread `Session.python_reasoner`. Wired `Session.traversal` directly into `MCPServer` (`mcp/server.py:75, 401, 441`) to reuse the session's active traversal manager and avoid duplicate allocations.
  - **5.3 Engine Backend Availability Caching**: `Engine` caches the Prolog probe once per instance (`_prolog_available`) rather than instantiating reasoners on every property access.
  - **5.4 Functional API Construction Pattern**: Confirmed that `api.run_query` and `Engine.query` retain one-shot construction as designed for stateless functional calls, while stateful workflows use `SessionManager` or `MCPServer`.
  - **5.5 State Machine File Layout**: Verified that `mcp/server.py` and `elicitation.py` remain single cohesive units with clear sub-dispatchers, maintaining 100% test pass rate without artificial module fracturing.
