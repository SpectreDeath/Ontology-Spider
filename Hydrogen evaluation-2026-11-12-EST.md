# Hydrogen Evaluation — Ontology-Spider — 2026-11-12 EST

*Read-only analysis of `Ontology-Spider` at `HEAD` `2d69823` (code base `4950d5c`), following `Hydrogen evaluation brief-2026-11-12-EST.md`.*

---

## 1. Live State Measured (2026-11-12)

All checks below were executed directly in this environment (Windows 11, Python 3.x, SWI-Prolog installed):

| Check | Command / Method | Observed Result |
| :--- | :--- | :--- |
| **Test Suite (with `swipl`)** | `coverage run --source=src/ontology_spider -m unittest discover -s tests` | **105/105 passed** in `15.527s` (`0` failures, `0` errors, `0` skipped) |
| **Test Suite (genuine degraded mode)** | Monkeypatched `prolog.reasoner.find_swipl_executable` and `shutil.which` to return `None`; verified `PrologReasoner().is_available == False` | **91 passed, 14 skipped** (`105` total) in `6.236s` (`0` failures, `0` errors) |
| **Statement Coverage** | `coverage report` | **91%** (`3576` statements, `315` missed; passes `--fail-under=90` in `pyproject.toml:62`) |
| **Differential Parity** | `python -m ontology_spider.harness parity` | **5/5 matched (100.0%)** |
| **Scenario Corpus** | `python -m ontology_spider.harness run` | **5/5 scenarios passed** (`drones` 5/5, `lattice` 2/2, `multi_recommend` 4/4, `tutorial` 3/3, `violations` 2/2) |
| **Benchmarks & Budgets** | `python -m ontology_spider.harness bench --budget src/ontology_spider/harness/baselines/bench_budgets.json` | **All 6 budgets passed**: `chain_50_ancestors_p50_ms=6.91` (<25.0), `tree_100_recommend_p50_ms=0.42` (<15.0), `lattice_50_validate_p50_ms=0.46` (<10.0), `lattice_20_ancestors_p50_ms=1.39` (<15.0), `python_10k_query_p50_ms=0.01` (<5.0), `lattice_10k_validate_ms=720.97` (<1500.0) |
| **Ruff Lint** | `ruff check src tests` | **Passed** (`All checks passed!`, exit `0`) |
| **Ruff Format** | `ruff format --check src tests` | **Failed** (exit `1`; unformatted legacy files, intentionally not gated in CI per `docs/decisions.md:223-224`) |
| **Mypy (`src`)** | `mypy src` | **Passed** (`Success: no issues found in 30 source files`, exit `0`) |
| **Mypy (`tests`)** | `mypy tests` | **Failed** (exit `1`; `58 errors in 18 files`, `[import-untyped]` due to missing `py.typed`, intentionally excluded from CI per `docs/decisions.md:226-227`) |

---

## 2. Ranked Findings (Highest Value First)

### Rank 1 — Bug (Crash): `TypeError` on assertion attributes in `Session.assert_triple` and `MCPServer` (`model_load`, `assert_triple`)
- **What it is**: `OntologyModel.add_assertion` accepts `attributes: Mapping[str, Any] | None = None` (`src/ontology_spider/model.py:251-257`) and does **not** accept `**kwargs`. However, three call sites unpack attribute dicts as keyword arguments (`**...`):
  1. `Session.assert_triple` (`src/ontology_spider/engine.py:192-201`) accepts `**attributes: Any` and calls `self.model.add_assertion(..., **attributes)`.
  2. `MCPServer._handle_tools_call` for `assert_triple` (`src/ontology_spider/mcp/server.py:452-458`) passes `**args.get("attributes", {})` to `session.assert_triple(...)`.
  3. `MCPServer._handle_tools_call` for `model_load` (`src/ontology_spider/mcp/server.py:446`) calls `session.model.add_assertion(asrt.relation, asrt.provenance, **dict(asrt.attributes))`.
- **Evidence**: Code inspection of `model.py:251-257`, `engine.py:201`, and `mcp/server.py:446,457`. Any MCP `assert_triple` call with non-empty `attributes` or `model_load` of a `.dialog` file containing assertion attributes (e.g., `examples/drones.dialog:27-30`) will raise `TypeError: OntologyModel.add_assertion() got an unexpected keyword argument ...`.
- **Concrete Scope**:
  - In `engine.py:201`, pass `attributes=attributes` (or accept `attributes: Mapping[str, Any] | None = None` and forward it).
  - In `mcp/server.py:446`, pass `assertion_id=asrt.assertion_id, attributes=asrt.attributes`.
  - In `mcp/server.py:457`, pass `attributes=args.get("attributes")`.
  - Add regression tests in `tests/test_mcp.py` covering `assert_triple` with `attributes` and `model_load` on a model with assertion attributes.
  - **Do NOT** change `OntologyModel.add_assertion`'s signature.
- **Risk / Irreversibility**: Low risk, zero syntax or seam impact.
- **Recommendation**: **Fix now.**

---

### Rank 2 — Bug & Parity Gap: `PrologReasoner` fails on `filter` queries via `Engine`/`api.run_query`, and `rules.pl` `subclass_closure/3` lacks a cycle guard
- **What it is**:
  1. `PrologReasoner._execute_under_lock` (`src/ontology_spider/prolog/reasoner.py:190-245`) handles `transitive`, `ancestors`, `recommend`, `lookup`, and `pattern`, but has **no branch for `filter`**, raising `ValueError("Unknown goal type: filter")`. `DialogSession` masks this in CLI `run` by bypassing `self.reasoner` for `filter` (`dialog_runner.py:428-468`), and `PythonReasoner` implements `_query_filter` (`python_backend.py:256-295`), but `Engine` / `api.run_query` routes directly to `self.reasoner.query(...)` (`engine.py:257`).
  2. `subclass_closure/3` in `src/ontology_spider/prolog/rules.pl:78-81` is naive recursion without a visited-node cycle guard. In contrast, `PythonReasoner._query_recommend` (`python_backend.py:305-318`) maintains `seen_classes`.
- **Evidence**:
  - Live execution: `run_query(load_model('examples/tutorial.dialog'), 'query filter instance_of where payload_kg=5')` raised `ValueError: Unknown goal type: filter`.
  - Code inspection: `rules.pl:78-81` vs `python_backend.py:305-318`. On a cyclic `subclass_of` graph, `recommend` in Prolog will recurse until `QueryInferenceLimitError`, whereas Python terminates cleanly.
- **Concrete Scope**:
  - Implement `filter` in `prolog/reasoner.py` / `rules.pl` matching `docs/semantics.md:37-39` and `python_backend.py:256-295`.
  - Add a visited-node cycle guard to `subclass_closure/3` in `rules.pl:78-81` (or replace with BFS subclass discovery matching `python_backend.py:304-318`).
  - Add parity tests for `filter` via `api.run_query` and `recommend` on cyclic `subclass_of` graphs.
  - **Do NOT** alter `.dialog` syntax.
- **Risk / Irreversibility**: Low-to-medium (Prolog rule change), fully reversible, no syntax/seam impact.
- **Recommendation**: **Fix now.**

---

### Rank 3 — Security / Trust Boundary: `MCPServer` `run_dialog` bypasses `--root` sandbox on `import` statements
- **What it is**: `docs/architecture.md:143` states that MCP file access (`model_load`, `import`, file `export`) is confined to `--root` via `Path.resolve().relative_to(root_dir)`. However, `MCPServer._handle_tools_call` for `run_dialog` (`src/ontology_spider/mcp/server.py:469-475`) calls `session.run_dialog(args["dialog_text"])` -> `Session.execute_statement` (`engine.py:131-132`) -> `load_imported_model(stmt.path, base_dir=self.base_dir)`.
- **Evidence**:
  - `MCPServer` never passes `base_dir=self.root_dir` to `self.sessions.open_session(...)` (`mcp/server.py:69-75, 381-396`), so `Session.base_dir` defaults to `Path.cwd()` (`engine.py:90`).
  - `load_imported_model` (`seam.py:27-51`) resolves relative and absolute paths without any `root_dir` containment check. Thus `run_dialog` with `import /path/outside/root.dialog` or `import ../../outside.json` escapes `--root`.
  - Additionally, `run_dialog` checks `len(session.model.assertions) > self.max_assertions_per_session` *after* committing assertions (`mcp/server.py:473-474`).
- **Concrete Scope**:
  - Pass `base_dir=self.root_dir` and an optional `allowed_root=self.root_dir` (or pre-parse `dialog_text` in `MCPServer.run_dialog` to validate all `DialogImport.path` targets via `_resolve_safe_path` before executing).
  - Pre-check statement assertion count against `max_assertions_per_session` before mutating `session.model` in `run_dialog`.
  - Add negative sandbox tests in `tests/test_mcp.py` for `run_dialog` with escaping `import` paths.
  - **Do NOT** restrict normal relative imports in non-MCP `cli.py` / `seam.py` usage.
- **Risk / Irreversibility**: Low risk, no syntax or seam breaking changes.
- **Recommendation**: **Fix now.**

---

### Rank 4 — Bug / State Split: `MCPServer` `query`/`explain` vs `run_dialog` state split, `retract` silent no-op, and `0.1.0` version drift
- **What it is**:
  1. In `MCPServer._handle_tools_call` (`mcp/server.py:472, 478, 485`), `run_dialog` executes via `session.run_dialog(...)` (updating `session.last_query_result`), whereas `query` and `explain` execute via `mgr = session.traversal` (`TraversalDialogueManager`, which uses `mgr.session.last_query_result`). Calling `explain` after a query inside `run_dialog` will not see that query.
  2. `MCPServer` `retract` (`mcp/server.py:465-467`) ignores the `bool` returned by `session.retract_assertion(...)` (`engine.py:206-207`) and always returns `"Retracted assertion <id>"`, even when the ID did not exist.
  3. `MCPServer._handle_initialize` (`mcp/server.py:158`) hardcodes `"version": "0.1.0"`, while `pyproject.toml:7` and `README.md:33` are `0.2.0`.
- **Concrete Scope**:
  - Route `run_dialog` queries or sync `last_query_result` between `session` and `session.traversal`, surface `retract` `bool` status in the MCP response, and source server version from `importlib.metadata.version("ontology-spider")` (with fallback `"0.2.0"`).
- **Risk / Irreversibility**: Low risk.
- **Recommendation**: **Fix now.**

---

### Rank 5 — Architecture / Duplication: `DialogSession._execute_degraded_query` duplicates and diverges from `PythonReasoner`
- **What it is**: `DialogSession._execute_degraded_query` (`src/ontology_spider/dialog_runner.py:148-270`) duplicates the BFS graph traversal logic of `PythonReasoner` (`src/ontology_spider/reasoning/python_backend.py:120-373`).
- **Evidence**:
  - For `recommend`, `dialog_runner.py:225-268` uses a plain `set` (`target_classes`) rather than BFS-ordered `ordered_target_classes`, omits `subclass_of` assertion IDs from `fact_ids` (`fact_ids=[a.assertion_id]`), and does not enforce `timeout_seconds` or `max_inferences` — unlike `PythonReasoner._query_recommend` (`python_backend.py:297-373`).
- **Concrete Scope**:
  - Replace `DialogSession._execute_degraded_query` with delegation to `PythonReasoner().query(self.model, spec)`, keeping the `[Degraded Mode: swipl unavailable] ` summary prefix.
  - **Do NOT** change `Reasoner` protocol or `docs/semantics.md`.
- **Risk / Irreversibility**: Low risk; removes ~120 lines of duplicated logic and improves degraded-mode parity and bound enforcement.
- **Recommendation**: **Fix now.**

---

### Rank 6 — Docs-vs-Code Drift & Minor UX/Edge-Case Gaps
- **Evidence & Scope**:
  1. `cli.py:134-137` (`run_repl --file <missing>`): silently ignores a nonexistent file and opens an empty REPL instead of returning an error like `run_batch`/`run_validate`/`run_export`.
  2. `seam.py:106-118` (`DialogModelSource.load`): when given a `str` path to a missing file, `Path(self.source).is_file()` is `False`, so it parses the filename string as inline `.dialog` text (`ParseError`) instead of raising `FileNotFoundError`.
  3. `traversal.py:149-173`: active frame constraint post-filtering checks `self.model.get_entity(ans.value)` assuming `ans.value` is an entity ID; for `lookup`/`filter`/`pattern` queries where `ans.value` is a formatted triple string or dict, active constraints silently filter out all answers.
  4. `docs/cli.md:47`: states REPL `explain` prints *"an explanation of the current frame context and constraints"*, whereas `cli.py:192-194` calls `traversal.explain()` (explaining the previous query's answers, matching `README.md:106`).
  5. `dialog.py:351,380`: `where <key>=<val>` uses `\S+` for `<val>`, so quoted values with spaces fail in `where` clauses (while `[key="val with spaces"]` works via `_parse_attributes`).
- **Recommendation**: **Low-effort cleanup; worth doing opportunistically.**

---

### Rank 7 — Phase-5 Backlog Items (Gap Analysis)
From `plan archive/Ontology-Spider development cycle plan-2026-11-06-0649-EST.md:138-141`:

1. **Multi-turn retraction and amendment over MCP (`plan:138`)**:
   - *Existing machinery*: `OntologyModel.retract_by_turn_id(turn_id)` (`model.py:311-319`), `Provenance.parent_turn_ids` (`model.py:89`), `ElicitationManager` amendment flow (`elicitation.py`), and `MCPServer` `retract(assertion_id)`.
   - *Missing*: An MCP `retract_turn` tool exposing `retract_by_turn_id`, plus populating `turn_id` on `Session.assert_triple` (`engine.py:200` currently leaves `turn_id=None`).
   - *Verdict*: **Worth doing only if an active MCP agent workflow needs turn-level undo**; single-assertion `retract` already works (once Rank 4's `bool` return is surfaced).
2. **Persistent sessions (save/restore to `.dialog` or JSON) (`plan:140`)**:
   - *Existing machinery*: Lossless `to_dialog`/`to_json` (`export.py`), `OntologyModel.from_dict` (`model.py:375-388`), `DialogModelSource`/`JsonModelSource` (`seam.py`).
   - *Missing*: Serialization of `Session` runtime state (`TraversalFrame` stack, `turn_counter`, `history`, `last_query_result`) and `session_save`/`session_restore` MCP tools.
   - *Verdict*: **Defer** until multi-process session resumption is needed; model-level save/load already works via `export` + `session_open(model_path=...)`.
3. **Query language growth (`path from X to Y`, negation `not instance_of`, counting) (`plan:139`)**:
   - *Existing machinery*: `dialog.py`, `rules.pl`, `python_backend.py`, `docs/semantics.md`.
   - *Missing*: New `.dialog` grammar forms, `QuerySpec` kinds, Prolog + Python parity implementations, and `semantics.md` contracts.
   - *Verdict*: **Defer** — `.dialog` grammar is an **irreversible joint**. Do not add until a real corpus/query requirement fires.

---

## 3. Do Not Develop Next

| Item | Reason | Evidence |
| :--- | :--- | :--- |
| **Full OWL2 DL Reasoning** (Track 10) | **No trigger fired.** Triples + 6 canonical predicates + Prolog/BFS cover all 5 corpus scenarios at 100% parity. | `docs/architecture.md:150`, `harness run` 5/5 pass |
| **Datalog Engine** (Track 10) | **No trigger fired.** Prolog (`chain_50` `6.91 ms`, `lattice_20` `1.39 ms`) and Python (`10k` `0.01 ms`) are well under budgets. | `docs/architecture.md:147-155`, `bench` output |
| **Free-Form NLU / LLM Parsing** (Track 10) | **Standing guardrail.** Explicitly deferred; controlled `.dialog` grammar is v1. | `docs/architecture.md:155`, `plan archive/...1105-EST.md:608-612` |
| **Topos / Continuous Truth / Multi-Agent Consensus** (Track 10) | **No trigger fired.** No multi-author federated use case exists. | `docs/architecture.md:151` |
| **Distributed Execution / WASM / GPU** (Track 10) | **No trigger fired.** Local execution is sub-millisecond to sub-second. | `docs/architecture.md:152`, `bench` output |
| **Eclipse IDE Parity & Speech I/O** (Track 10) | **No trigger fired.** CLI, REPL, MCP, and HTML/DOT export cover v1. | `docs/architecture.md:153-154` |
| **Incremental Validation** (Phase 5 backlog) | **Premature.** Whole-model validation is `0.46 ms` on 50-node lattice and `720.97 ms` on 10k-assertion lattice (budget `1500.0 ms`). | `validation.py:73-353`, `bench` output |
| **Gating `ruff format --check` or `mypy tests` in CI** | **Already dispositioned.** 31 legacy files unformatted; `tests/` uses dynamic idioms. | `docs/decisions.md:219-227` |
| **New Third-Party Dependencies** | **Standing guardrail.** `dependencies = []` remains sufficient. | `pyproject.toml:15`, `docs/decisions.md:7-14` |

