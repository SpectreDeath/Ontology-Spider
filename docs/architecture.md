# Architecture: System Design, Pipelines, Boundaries & Deferred Capabilities

This document provides a comprehensive technical overview of `Ontology-Spider`: its module map, end-to-end execution pipeline, reasoner abstractions, session lifecycle, security trust boundaries, and deferred capabilities.

---

## 1. Module Map

All production source code lives under `src/ontology_spider/` with zero third-party dependencies (`dependencies = []`):

- **Core Model & AST**:
  - `model.py` — Immutable, slotted dataclasses (`Entity`, `Relation`, `Assertion`, `Provenance`, `OntologyModel`) representing knowledge graphs, fact versions, and attribute mappings.
  - `dialog.py` — Lexer and recursive-descent parser compiling `.dialog` controlled text into strongly-typed AST statements (`DialogDoc`, `DialogImport`, `DialogEntityDecl`, `DialogAssertion`, `DialogQuery`).
  - `seam.py` — `ModelSource` abstraction (`DialogModelSource`, `JsonModelSource`) defining storage and format boundaries without circular coupling.
- **Reasoning Engines**:
  - `reasoning/base.py` — `@runtime_checkable` `Reasoner` protocol, `QuerySpec`, `Explanation`, `ReasonerAnswer`, `ReasonerResult`, and unified error hierarchies (`QueryExecutionError`, `QueryTimeoutError`, `QueryInferenceLimitError`).
  - `reasoning/python_backend.py` — Pure-Python Breadth-First Search (BFS) graph reasoner supporting transitive inheritance, pattern queries, attribute filtering, and recommendations with deadline and inference bounds.
  - `prolog/reasoner.py` — High-performance bridge to SWI-Prolog (`swipl`), translating models into Prolog facts and invoking rules with inference and timeout caps.
  - `prolog/translator.py` — Deterministic translator compiling Python ontology entities and assertions into SWI-Prolog safe fact syntax.
  - `prolog/worker.py` — `PersistentPrologWorker` managing long-lived `swipl` subprocesses with class-level caching keyed by `swipl_path`.
  - `prolog/rules.pl` — Declarative Prolog rulebase implementing transitive closures, ancestor chains, subclass recommendations, and cycle detection without unbounded backtracking.
- **Execution & Orchestration**:
  - `engine.py` — Core facade (`Engine`, `Session`, `SessionManager`, `QueryResult`) orchestrating session state, reasoner routing, and one-shot queries.
  - `dialog_runner.py` — `DialogSession` executing sequential `.dialog` scripts, managing assertion history, degraded fallback, and query explanations.
  - `traversal.py` — `TraversalDialogueManager` and `TraversalFrame` maintaining conversational focus, active constraint stacks, and interactive graph exploration.
  - `elicitation.py` — `ElicitationDialogueManager` guiding interactive, step-by-step schema authoring with competency queries and mixed-initiative corrections.
  - `validation.py` — `OntologyValidator` verifying domain/range constraints, acyclicity, class disjointness, and finding orphan instances.
  - `export.py` — Serialization utilities exporting models to JSON, `.dialog` scripts, Graphviz DOT graphs, and standalone interactive HTML visualizers.
- **Interfaces & Protocols**:
  - `api.py` — Python programmatic facade (`load_model`, `run_query`, `validate_model`, `export_model`).
  - `cli.py` — Click-free standard library CLI entrypoint providing 6 subcommands: `run`, `repl`, `validate`, `export`, `elicit`, and `mcp`.
  - `mcp/server.py` — Model Context Protocol (MCP) server implementing 16 tools, 3 resource templates, session lifecycle, and sandboxing.
  - `mcp/transport.py` — Stdio JSON-RPC 2.0 transport supporting newline-delimited JSON (NDJSON) and Content-Length framing.
  - `mcp/__main__.py` — Standalone execution module for `python -m ontology_spider.mcp`.
- **Testing & Harness**:
  - `harness/` — Synthetic topology generators, property checkers, microbenchmarks, and 5 corpus scenarios evaluating reasoner differential parity.

---

## 2. End-to-End Execution Pipeline & Import DAG

### High-Level Call Flow
```
CLI / API / MCP Entrypoints
            │
            ▼
      Engine / Session
            │
    ┌───────┴────────────────────────┐
    ▼                                ▼
TraversalDialogueManager       DialogSession
    │                                │
    └───────► Reasoner Protocol ◄────┘
                     │
       ┌─────────────┴─────────────┐
       ▼                           ▼
PrologReasoner (swipl)     PythonReasoner (BFS)
       │                           │
  rules.pl                   python_backend
```

### Import DAG
The repository strictly adheres to an acyclic dependency graph:
1. `model.py` and `dialog.py` import zero internal modules.
2. `reasoning/base.py` imports only `model.py`.
3. `prolog/` and `reasoning/python_backend.py` import `model.py` and `reasoning/base.py`.
4. `seam.py` imports `model.py` and `dialog.py`.
5. `engine.py`, `dialog_runner.py`, `traversal.py`, and `elicitation.py` compose the model and reasoner layers.
6. `api.py`, `cli.py`, and `mcp/` act as thin outer boundaries.

---

## 3. Reasoner Selection & Degraded Mode

1. **Auto Selection**:
   - `Engine` probes `PrologReasoner().is_available` once per instance. If SWI-Prolog (`swipl`) is present on system `PATH`, Prolog is chosen for optimal performance.
   - If `swipl` is absent or `--backend python` is passed, `PythonReasoner` serves as the primary engine.
2. **Degraded Mode Parity**:
   - `PythonReasoner` implements 100% feature parity for supported query goals (`ancestors`, `transitive`, `recommend`, `filter`, `pattern`).
   - Pure-Python execution enforces identical inference caps and monotonic timeout limits.
   - Proof traces emitted under degraded mode are tagged with `degraded_python_fallback` in their explanation rules.

---

## 4. Session Lifecycle & Operational Caps

Sessions represent stateful, in-memory conversational contexts:
- **`SessionManager`**:
  - Tracks sessions by string identifier (`session_id`).
  - Caps maximum concurrent active sessions (default: 32) to prevent memory exhaustion in multi-tenant environments.
- **Assertion Limits**:
  - Each session enforces a maximum assertion budget (default: 50,000 assertions).
  - Mutating calls (`assert_triple`, `model_load`, `run_dialog`) validate assertions against this cap before committing state.
- **Query Bounds**:
  - Queries execute under strict per-query deadlines (default: 10.0 seconds) and maximum inference steps (default: 1,000,000 inferences).

---

## 5. Facts Cache & Persistent Prolog Worker

To eliminate the overhead of repeated subprocess spawns:
- **Worker Persistence**:
  - `PersistentPrologWorker` maintains a persistent SWI-Prolog daemon communicating over piped stdin/stdout.
  - Subprocesses are cached at the class level and keyed by `swipl_path`.
- **Facts Cache**:
  - An `OrderedDict` LRU cache (capacity: 8 models) stores translated Prolog fact strings keyed by `(model.uri, model.version)`.
  - When a model mutates (assertions added or retracted), `model.version` increments, automatically invalidating stale cache entries.

---

## 6. Architecture Review Dispositions (Track 5)

During the 2026-11-08 architecture audit, the following findings were dispositioned:

1. **Reasoner Sharing (5.1)**:
   - `Session.__init__` previously initialized separate reasoners for the session and `TraversalDialogueManager`. This was refactored: `TraversalDialogueManager` now explicitly receives `session.reasoner` and shares the same cache and persistent worker.
2. **Unread Reasoner Attributes (5.2)**:
   - `Session.python_reasoner` was retained as a fallback instance, and `Session.traversal` was wired directly to the session's active reasoner and query timeout parameters.
3. **Backend Availability Caching (5.3)**:
   - `Engine.active_backend_name` and `available_backends` now cache the Prolog availability probe on first access per `Engine` instance rather than constructing fresh reasoners repeatedly.
4. **One-Shot API Construction (5.4)**:
   - Evaluated `api.run_query` and `Engine.query`: one-shot construction was confirmed as the desired behavior for isolated functional API invocations, while stateful workflows leverage `SessionManager` and `MCPServer`.
5. **Single-File State Machine Structure (5.5)**:
   - Verified that `mcp/server.py` and `elicitation.py` remain single cohesive modules with clear section boundaries; avoiding superficial splitting preserves maintainability without compromising test coverage.

---

## 7. The Model Import Seam (Track 1 & Track 9)

The seam is a decoupled boundary separating the core reasoner from external storage formats:
- **`ModelSource` Interface**: Defined in `src/ontology_spider/seam.py`. External stores (including the Brain-Harness vault plugin) implement `load() -> OntologyModel`.
- **Zero Foreign Imports**: The seam module imports zero third-party or companion repository code, preventing circular dependencies and implementation forking.
- **Bi-directional Round-Trip**: Models export to both JSON and `.dialog` authoring syntax and re-import identically.

---

## 8. Trust & Security Boundary (Track 3)

- **Local Trusted Models Only**: Designed for local, verified semantic models.
- **Prolog Goal Construction**: User input queries in `.dialog` are parsed into a typed AST and compiled into strict, predefined rule goals with escaped arguments. Raw user input strings are never passed directly to Prolog as arbitrary execution goals.
- **Prolog I/O Boundary**: Prolog goals in user-authored external rule files can execute standard SWI-Prolog I/O; the engine makes no claim of an uncircumventable sandbox. Workloads requiring untrusted multi-tenant isolation are deferred.
- **Timeouts & Inference Limits**: Subprocess timeouts and in-Prolog inference caps (`call_with_inference_limit/3`) ensure that cyclic data or infinite loops terminate deterministically without locking the process.
- **MCP Trust Boundary**: File access (`model_load`, `import`, file `export`) is confined to `--root` via `Path.resolve().relative_to(root_dir)`. Mutating tools (`assert_triple`, `declare_entity`, `retract`, `run_dialog`, `focus`, `constrain`) are disabled when started with `--read-only`. Active sessions and assertions per session are bounded (max 32 active sessions, max 50,000 assertions per session).

---

## 9. Deferred-by-Design Features (Track 10)

The following components are deferred by design to maintain simplicity:
1. **Full OWL2 DL Reasoning**: Triples with custom Prolog rules cover transitive hierarchy, disjointness, domain/range, and cycles. Complex description logic tableau classifiers are deferred until triples prove insufficient.
2. **Topos / Continuous Truth Values & Multi-Agent Consensus**: Heavier Em-Cubed ontology machinery is deferred until multi-author federated use cases arise.
3. **Distributed Execution / WASM / GPU Surfaces**: Local SWI-Prolog execution handles standard ontologies with sub-second latency.
4. **Eclipse IDE Parity**: Replaced by lightweight CLI, REPL, and web-ready HTML/DOT exports.
5. **Speech I/O (ASR/TTS)**: Text-based conversational dialogue is v1.
6. **Free-Form Natural Language Understanding (LLM Parsing)**: Deterministic controlled `.dialog` syntax provides provable, reproducible reasoning. LLM-based prose extraction is deferred until an explicit requirement is approved.
