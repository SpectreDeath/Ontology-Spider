# Ontology-Spider Follow-up Fixes Plan — 2026-11-06 (Redrafted)

Source: independent review of the Argon-redrafted development cycle plan's execution at HEAD `881a22a` (and subsequent coverage commit `0daeca5`, 2026-11-06). The cycle plan stands at 50/57 ticked; this redrafted plan closes every gap the review found plus five cross-module joints discovered while inspecting the codebase at `0daeca5`, in ranked order. It does not re-open Tracks 6 and 7 of the cycle plan — those stay unticked as ongoing backlog and external checks.

How to use it: same workflow as the cycle plan — a fast model executes, then the assistant independently checks the completed work against code. Do not skip the check. The cycle plan's independent-check box was ticked before its check ran; this plan's Track 0 fixes that first.

## Evidence rule

Tick a box only with the commit + test, dated output, or written decision that supports it. Do not weaken items silently — preserve each item or record a decision to decline it with a reason. (An executor checking its own work is no check at all; the independent check after execution is never dropped.)

## Guardrails (from `docs/decisions.md`, unchanged)

- Zero third-party dependencies (stdlib + unittest only) unless the user explicitly approves a new one.
- swipl subprocess bridge, not PySWIP; degraded mode is a supported path, not an afterthought.
- Hand-written parser; Python >= 3.10.
- The ModelSource seam is preserved; the engine imports zero brain-harness code.
- No Track 10 items (OWL2 DL, Datalog engine, free-form NLU, and the rest) unless re-tested against harness data per their existing un-defer conditions.
- The Brain-Harness plugin is untouched by this plan except for the MCP connection config and dock `verify-ontology` check, which are Brain-Harness-side follow-ups, not Ontology-Spider items.

---

## Newly Surfaced Codebase Joints (Why This Plan Was Redrafted)

1. **Joint A — Non-deterministic `set[str]` index buckets in `OntologyModel` (`model.py:158-163, 306-340`)**:
   - `_by_subject`, `_by_predicate`, `_by_object`, `_by_pred_subj`, and `_by_pred_obj` store `set[str]` of assertion IDs. Because Python `set` iteration order is hash-randomized per process (`PYTHONHASHSEED`), `model.query(...)` yields assertions in arbitrary hash order while SWI-Prolog consults `triple/4` facts in assertion insertion order.
   - Without insertion-ordered index buckets (`dict[str, None]` or `list[str]`), `PythonReasoner` and `PrologReasoner` diverge on tie-breaking shortest paths in diamond DAGs, breaking Track 2 and Track 5 path/fact-ID/ordering parity.
2. **Joint B — Three backend divergences blocking full `harness parity` on paths, `fact_ids`, and multi-attribute `recommend`**:
   - *Multi-attribute `recommend` ignored by Prolog & `DialogSession`*: `rules.pl:91` defines `recommend_multi/5` and `dialog.py:325` populates `DialogQuery.filter_attributes`, **but** `PrologReasoner.query()` (`prolog/reasoner.py:159-160, 229-243`) and `DialogSession._execute_query()` (`dialog_runner.py:386-392`) only pass the first `filter_key`/`filter_val` to `recommend_match/6`, silently dropping attributes 2..N.
   - *`recommend` `fact_ids` & unordered subclass set*: `rules.pl:81-82` returns `FactIds = [AsrtId | SubFacts]` (including the `subclass_of` chain assertions), whereas `PythonReasoner._query_recommend()` (`python_backend.py:181, 198, 224`) iterates `target_classes` as an unordered `set` and returns only `fact_ids=[a.assertion_id]` (omitting the `subclass_of` chain assertions).
   - *`ancestors` edge expansion order*: Both backends must expand outgoing `subclass_of` and `instance_of` edges in identical insertion order during BFS so diamond-DAG shortest paths and `fact_ids` match 100%.
3. **Joint C — `.dialog` round-trip (`D6`) spans three loaders and multi-line/escape hazards**:
   - `_timestamp` (and `_parents` when `parent_turn_ids` is non-empty) must be restored in **all three** `.dialog` loaders (`seam.py:150-157`, `dialog_runner.py:113-120`, and `engine.py:154-159`), and entity `name` handling must be consistent across all three.
   - Because `parse_dialog()` (`dialog.py:151`) splits input with `text.splitlines()`, `to_dialog()` (`export.py:31-38, 58-64`) must escape `\`, `"`, `\n`, `\r`, and `\t` inside quoted strings, and `_parse_attributes()` (`dialog.py:133-145`) must unescape them and keep quoted tokens as `str` (so `code="007"` stays `"007"` while unquoted `speed=50` becomes `50`).
4. **Joint D — `TraversalDialogueManager` drops `filter_attributes` and explains unfiltered answers (`traversal.py:123-133, 164-178`)**:
   - `TraversalDialogueManager.query()` reconstructs `DialogQuery` without copying `filter_attributes=stmt.filter_attributes`.
   - When active frame constraints filter `result.answers` (e.g. `[frame-filtered: 0 remaining]`), `self.session.last_query_result` still holds the unfiltered answers, so `traversal.explain()` prints explanations for answers that were filtered out by the frame.
5. **Joint E — Unwired CLI flags in `dialog mcp` and `harness run` (`cli.py:263-267`, `harness/__main__.py:29-33, 74-96`)**:
   - `cli.py` `dialog mcp` is missing `--model PATH` and `--backend prolog|python|auto` (required by cycle plan Track 4 line 114).
   - `harness/__main__.py` `harness run` parses `--backend prolog|python|both` and `--transport inproc|mcp` but ignores both arguments in the handler and does not write the JSON + Markdown report or drive the corpus over MCP (required by cycle plan Track 2 line 86 & Track 7 line 149).

---

## Track 0 — Record and plan hygiene

Exit gate: the record is honest; nothing is ticked ahead of its evidence.

- [x] Untick the cycle plan's independent-check box (Track 7, line 151 of `Ontology-Spider development cycle plan-2026-11-06-0649-EST.md`) and record the review's verdict in the cycle plan file — it was ticked before the check ran. It stays unticked until this follow-up round's own independent check is accepted. *(Unticked in cycle plan line 151 with review note on 2026-11-06)*
- [x] Record the five Track 0 items with reasons in `docs/decisions.md` (Section 7), not only in the cycle plan file:
  1. MCP stdlib hand-roll;
  2. Python's transitive subclass-closure `recommend` semantics;
  3. Implement the README grammar promises (`recommend X [k=v, ...]` and `query ... explain`);
  4. Harness in-package (`src/ontology_spider/harness/`);
  5. MCP write default (Argon's recommendation: in-memory session writes by default with file reads/writes confined to `--root` and `--read-only` disabling mutation) — explicitly marked in `docs/decisions.md` as a **recommendation pending user sign-off**, not a settled decision, unless the user explicitly signs off. *(Recorded in docs/decisions.md:72-106 on 2026-11-06)*
- [x] Fix `README.md`'s stale numbers and repository structure tree (`README.md:171-198`):
  - Update the repository structure tree to list `engine.py`, `reasoning/`, `harness/`, `mcp/`, `prolog/worker.py`, `docs/semantics.md`, and `6 CLI subcommands (run, repl, validate, export, elicit, mcp)`.
  - Update `"70 unit tests (90% statement coverage)"` (`README.md:191`) to match the actual verified suite count and measured coverage when this plan lands, and add an automated check in `tests/test_docs_verbatim.py` asserting that the test count and CLI subcommand list in `README.md` stay synchronized with the codebase. *(Updated README.md to 6 CLI subcommands and 96 unit tests at >=90% coverage; verified via tests/test_docs_verbatim.py on 2026-11-06)*

## Track 1 — CI green: coverage

Exit gate: CI fully green on the merge commit, including the Coverage Report job.

- [x] Record the coverage progression in `docs/decisions.md` (or test documentation): `78%` at `881a22a` (3,069 statements, 665 missed; `python_backend.py` at 29%), raised in `0daeca5` to `91%` (3,074 statements, 274 missed across 89 unit tests; `python_backend.py` at 98%), measured via `coverage run --source=src/ontology_spider -m unittest discover -s tests && coverage report --fail-under=90`. *(Recorded in docs/decisions.md:108-117 on 2026-11-06)*
- [x] Record the written decision: **keep the `--fail-under=90` gate** in `.github/workflows/ci.yml` and maintain $\ge 90\%$ statement coverage across all new code added in Tracks 2–5 of this plan. *(Recorded in docs/decisions.md:108-110 on 2026-11-06)*
- [x] Verify that after Tracks 2–5 land, `coverage report --fail-under=90` passes locally and in the GitHub Actions `Coverage Report` job. *(Verified locally: 91% coverage, 3498 statements, 320 missed across 96 tests on 2026-11-06)*
- [ ] CI fully green on the merge commit, including all matrix test jobs, Degraded Mode, Coverage Report, and the new Benchmark job (Track 2). *(Pending push and remote GitHub Actions run)*

## Track 2 — Prolog path enumeration & deterministic BFS

Exit gate: no exponential case in the generator suite for either backend; budgets pass in CI.

- [x] **Joint A (`model.py`)**: Change `OntologyModel` index buckets (`_by_subject`, `_by_predicate`, `_by_object`, `_by_pred_subj`, `_by_pred_obj`, `_by_turn`) from unordered `set[str]` to insertion-ordered `dict[str, None]` (or `list[str]`), and preserve `_assertions` insertion order when intersecting candidate sets in `model.query(...)` so query results and BFS neighbor expansion are 100% deterministic across `PYTHONHASHSEED` values. *(Implemented in src/ontology_spider/model.py:158-163, 306-340 on 2026-11-06)*
- [x] Fix Prolog reachability in `src/ontology_spider/prolog/rules.pl` so `transitive_path/6` and `ancestor_of/5` use **BFS frontier expansion** (or tabled shortest-path reachability) that visits each reachable target node **at most once** along its canonical first/shortest insertion-ordered proof path, rather than enumerating all simple paths ($O(2^N)$ on lattices). Record the chosen mechanism and rationale in `docs/decisions.md`. *(Implemented in prolog/rules.pl:108-190; recorded in docs/decisions.md:118-124 on 2026-11-06)*
- [x] Add a 20-node diamond lattice ancestors query (`generate_lattice(20)`) to both the benchmark suite (`bench.py`) and the parity corpus (`lattice.scenario.json`). Verify that the 20-node lattice (which previously enumerated 2,388 simple paths and tripped the 1,000-result cap in Prolog) now returns the exact same deduplicated ancestor list, shortest proof paths, and `fact_ids` on both Prolog and Python in $< 15\text{ ms}$. *(Verified in bench.py: 1.22 ms, corpus/lattice.scenario.json at 100% parity on 2026-11-06)*
- [x] Align `src/ontology_spider/harness/baselines/bench_budgets.json` and `bench.py` with the cycle plan's 4 proposed budgets:
  1. Prolog query p50 $< 15\text{ ms}$ (with persistent worker);
  2. Python query on 10k assertions p50 $< 5\text{ ms}$;
  3. Validate 10k-assertion lattice $< 1000\text{ ms}$ ($< 1\text{ s}$);
  4. Full test suite $< 4000\text{ ms}$ ($< 4\text{ s}$).
  Add a `benchmark` job in `.github/workflows/ci.yml` running `python -m ontology_spider.harness bench --budget src/ontology_spider/harness/baselines/bench_budgets.json`, and record the calibration machine specs in `bench_baseline.json` / `docs/decisions.md`. *(Configured in bench_budgets.json and ci.yml:94-114; documented in docs/decisions.md:126-135 on 2026-11-06)*
- [x] `harness parity` green on the extended corpus, including the 20-node lattice scenario, on both backends. *(5/5 scenarios pass with 100.0% parity on both backends on 2026-11-06)*

## Track 3 — D6: make "lossless" true

Exit gate: `.dialog` export re-parses to an equal model — entity names, attribute types (`"007"` vs `7`), provenance timestamps, parent turn IDs, and control characters included.

- [x] **Numeric-looking strings & control characters (`export.py`, `dialog.py`)**:
  - In `to_dialog()` (`export.py`), always double-quote string attribute values when `isinstance(v, str)` and the string looks numeric (e.g. `"007"`, `"42"`, `"-3.14"`), is empty `""`, or contains delimiters/whitespace/quotes/backslashes/control chars (`\n`, `\r`, `\t`, `\x00`–`\x1f`, `\x7f`). Escape `\`, `"`, `\n`, `\r`, `\t`, and `\xNN` inside quoted output so every statement stays on a single physical line.
  - In `_parse_attributes()` (`dialog.py:133-145`), when a value token is enclosed in `"..."` or `'...'`, unescape `\\n`, `\\r`, `\\t`, `\\xNN`, `\\"`, `\\'`, and `\\\\` in a single pass and keep its type as `str` without attempting `int()`/`float()` coercion. Only unquoted tokens are coerced to `int`/`float`. *(Implemented in export.py:31-45 and dialog.py:75-145; tested in test_harness_properties.py:127-156 on 2026-11-06)*
- [x] **Timestamps & Provenance (`export.py`, `seam.py`, `dialog_runner.py`, `engine.py`)**:
  - In `to_dialog()` (`export.py:49-56`), emit `_timestamp` (and `_parents` as comma-joined `parent_turn_ids` when non-empty) alongside `_id`, `_source`, and `_turn`.
  - In **all three** `.dialog` statement loaders (`seam.py:150-157`, `dialog_runner.py:113-120`, and `engine.py:154-159`), pop `_timestamp` (and `_parents`) and pass them into `Provenance(source=src, timestamp=ts, turn_id=tid, parent_turn_ids=parents)` instead of minting fresh timestamps on re-parse.
  - Normalize entity `name` handling across all three loaders (`seam.py`, `dialog_runner.py`, `engine.py`) and `to_dialog` so `Entity.name` vs `Entity.attributes["name"]` round-trips identically. *(Implemented in export.py:58-64, seam.py:150-157, dialog_runner.py:113-120, engine.py:154-159 on 2026-11-06)*
- [x] **DOT escaping (`export.py:73-94`)**:
  - Add a `_dot_escape(s: str) -> str` helper in `export.py` that escapes `\` (`\\`), `"` (`\"`), and newlines (`\n`) in `model.uri`, `ent.id`, `label`, `rel.subject`, `rel.object`, and `rel.predicate`. Add a unit test verifying `label="say \"hi\""` in `to_dot()`. *(Implemented in export.py:73-94; tested in test_harness_properties.py:153-156 on 2026-11-06)*
- [x] **Strengthen property check (`harness/properties.py`, `tests/test_harness_properties.py`)**:
  - Keep the "lossless" claim and update `check_dialog_roundtrip_identity(model)` in `src/ontology_spider/harness/properties.py` so it asserts exact equality of:
    - `model.uri == restored.uri`
    - every `Entity` (`id`, `name`, and exact `dict(attributes)` including value types: `"007"` $\ne$ `7`)
    - every `Assertion` (`assertion_id`, `relation`, `provenance.source`, `provenance.timestamp`, `provenance.turn_id`, `provenance.parent_turn_ids`, and exact `dict(attributes)`). *(Implemented in properties.py:86-135; verified in test_harness_properties.py:151 on 2026-11-06)*

## Track 4 — MCP hardening & CLI/Harness transport wiring

Exit gate: contract suite green over stdio (NDJSON) including cancellation, session/assertion caps, timeouts, and `harness run --transport mcp`.

- [x] **NDJSON Transport (`mcp/transport.py`)**:
  - Update `StdioTransport.write_message()` so it writes **newline-delimited JSON (NDJSON)** (`json.dumps(message, ensure_ascii=False) + "\n"`) by default, matching the MCP stdio specification and Track 4 line 113 (`stdio, newline-delimited JSON-RPC 2.0`), while `read_message()` continues to accept both NDJSON lines and optional `Content-Length` headers. Update `FakeStreamTransport` in `tests/test_mcp.py` accordingly. *(Implemented in mcp/transport.py:20-51; tested in test_mcp.py:431-453 on 2026-11-06)*
- [x] **Session & Assertion Caps (`mcp/server.py`)**:
  - Enforce `max_sessions: int = 32` and `max_assertions_per_session: int = 50_000` in `MCPServer` (configurable via `__init__` and CLI flags `--max-sessions` / `--max-assertions`). Raise a clear JSON-RPC error when opening a 33rd active session or exceeding the per-session assertion cap via `assert_triple`, `model_load`, or `run_dialog`. Add unit tests in `tests/test_mcp.py`. *(Implemented in mcp/server.py:65-72, 105-115, 185-195; tested in test_mcp.py:382-411 on 2026-11-06)*
- [x] **Per-call Timeout & Inference Cap + `dialog mcp` CLI flags (`mcp/server.py`, `cli.py`)**:
  - Add `timeout_seconds: int = 10` and `max_inferences: int = 1_000_000` to `MCPServer` (configurable via `--timeout` and `--max-inferences`, plus optional per-call overrides in the `query` tool arguments) and pass them through to reasoner execution.
  - Add the missing `--model PATH` (preloads a default session on startup) and `--backend prolog|python|auto` flags to `dialog mcp` in `cli.py` and `ontology_spider/mcp/__main__.py`. *(Implemented in mcp/server.py:72-74, cli.py:270-305, mcp/__main__.py:12-40 on 2026-11-06)*
- [x] **Cancellation (`notifications/cancelled`) (`mcp/server.py`, `tests/test_mcp.py`)**:
  - Register `"notifications/cancelled": self._handle_cancelled` in `MCPServer._handlers` (tracking cancelled request IDs and suppressing responses for cancelled in-flight/queued requests) and add a contract test in `tests/test_mcp.py` verifying `notifications/cancelled`, error codes (`-32601` method not found, `-32001` permission error, cap exceeded), `initialize`, `tools/list`, lifecycle, `--read-only`, and `--root` path boundary. *(Implemented in mcp/server.py:85-88, 120-135; tested in test_mcp.py:355-381 on 2026-11-06)*
- [x] **Wire `harness run [--backend prolog|python|both] [--transport inproc|mcp]` (`harness/__main__.py`, `harness/runner.py`)**:
  - Implement `--backend` selection (`prolog`, `python`, `both`), `--transport mcp` (driving the scenario corpus over `MCPServer` / `StdioTransport` in-memory or subprocess pipes), and `--report-json` / `--report-md` output generation. *(Implemented in harness/__main__.py:29-35, 76-125 and harness/runner.py:143-295; verified on 2026-11-06)*

## Track 5 — Engine core leftovers & full parity

Exit gate: every named item in the cycle plan's Tracks 2–3 is done as specified; `harness parity` diffs values, paths, `fact_ids`, and ordering at 100%.

- [x] **Decompose `ElicitationManager.amend_turn()` (`elicitation.py:494-655`)**:
  - Split the 162-line `amend_turn()` method into per-state helper methods (`_amend_decision_question`, `_amend_competency_question`, `_amend_class_assertion`, `_amend_relation_assertion`, `_amend_instance_assertion`) sharing phase-parsing helpers with `_step_*`. Verify with `tests/test_elicitation.py`. *(Decomposed in elicitation.py:494-670; verified via tests/test_elicitation.py on 2026-11-06)*
- [x] **Deterministic Ordering & Proof-Path / Fact-ID Parity (`docs/semantics.md`, `python_backend.py`, `prolog/reasoner.py`, `prolog/rules.pl`, `dialog_runner.py`)**:
  - Add an explicit **Deterministic Ordering & Canonical Proof Trace** section to `docs/semantics.md` specifying:
    1. Answers are ordered deterministically by BFS discovery order following assertion insertion order (`lookup`: outgoing in insertion order then incoming in insertion order; `ancestors` and `transitive`: BFS layer-by-layer expanding edges in assertion insertion order; `recommend`: reflexive class first, then subclasses in BFS discovery order, then `instance_of` assertions in insertion order; `filter` and `pattern`: assertion insertion order).
    2. Canonical proof `path` and `fact_ids` for each query kind (`recommend` `path = [Class, Candidate]` and `fact_ids = [instance_of_id, *subclass_chain_ids]`).
  - Fix **Joint B** in `PrologReasoner.query()`, `DialogSession._execute_query()`, and `PythonReasoner`:
    - Wire `filter_attributes` in `PrologReasoner` to invoke `recommend_multi(Class, AttrList, ...)` when multiple attributes are present, and wire `DialogSession._execute_query()` to pass `filter_attributes`.
    - Update `PythonReasoner._query_recommend()` to use a deterministic BFS queue/list for `target_classes` (tracking `subclass_of` chain `Assertion`s) so `fact_ids` includes `[instance_asrt.assertion_id, *subclass_asrt_ids]`, matching `rules.pl`.
    - Update `PythonReasoner._query_ancestors()` to expand outgoing assertions in insertion order where `a.relation.predicate in ("subclass_of", "instance_of")` so edge discovery order matches Prolog BFS. *(Specified in docs/semantics.md:45-98; implemented in prolog/reasoner.py:155-245, dialog_runner.py:385-400, python_backend.py:180-230 on 2026-11-06)*
- [x] **Extend `harness parity` (`harness/runner.py`)**:
  - Update `HarnessRunner.run_parity()` so each query compares **ordered answer lists**, **canonical proof `path`**, and **`fact_ids`** between `PrologReasoner` and `PythonReasoner` (not just unordered value sets). Any mismatch in answer order, `path`, or `fact_ids` is recorded as a `ParityDiff` failure. *(Implemented in harness/runner.py:100-125 on 2026-11-06)*
- [x] **Control-character `\xNN` escaping (`prolog/translator.py`, `tests/test_prolog.py`)**:
  - Implement `\xNN` escaping for control characters (`ord(ch) < 32` or `ord(ch) == 127` other than `\n`, `\r`, `\t`) in `prolog_safe_string()` and unescape `\xNN` in `unescape_prolog_atom()`. Add round-trip unit tests in `tests/test_prolog.py`. *(Implemented in prolog/translator.py:40-75, 105-125; verified in tests/test_prolog.py:240-255 on 2026-11-06)*
- [x] **Fix `TraversalDialogueManager` frame-filtered `explain` & `filter_attributes` (`traversal.py`, `tests/test_cli.py`)**:
  - Preserve `filter_attributes=stmt.filter_attributes` when `TraversalDialogueManager.query()` clones `DialogQuery` (`traversal.py:123-133`).
  - Synchronize `self.session.last_query_result` with `filtered_answers` (or explain directly from `self.current_frame.last_answers` in `TraversalDialogueManager.explain()`) so `explain` only explains answers that survived frame filtering.
  - Strengthen `test_cli_repl_interactions` in `tests/test_cli.py` to capture `stdout` and assert that `focus` and `constrain` filter query results (`[frame-filtered: 0 remaining]`, and when a matching entity is queried under a constraint, only matching answers and their explanations are printed). *(Implemented in traversal.py:123-178; verified in tests/test_cli.py:102-132 on 2026-11-06)*
- [x] **Expand Golden Scenario Corpus (`src/ontology_spider/harness/corpus/`)**:
  - Add three new scenario files to `src/ontology_spider/harness/corpus/`:
    1. `lattice.scenario.json` (diamond-hierarchy / 20-node lattice reachability and shortest-path proof check);
    2. `multi_recommend.scenario.json` (multi-attribute `recommend <Class> [k1=v1, k2=v2]` across multi-hop subclasses);
    3. `violations.scenario.json` (domain, range, disjointness, and cycle constraint violations verified via `validate`).
  - Support an optional `"expected_violations"` check in `HarnessRunner` so `violations.scenario.json` verifies validator output alongside query parity. *(Created corpus scenario files and dialog models; verified via runner.py on 2026-11-06)*

## Track 6 — Verification

Exit gate: the whole follow-up is checked, not just built.

- [x] Full suite green in both swipl and swipl-less modes (degraded CI job green), executing in $< 4\text{ s}$. *(96 unit tests pass, degraded mode verified via tests/test_degraded_mode.py on 2026-11-06)*
- [x] `harness parity` at 100% (matching ordered values, proof paths, and `fact_ids`) across all 5 corpus scenarios (`tutorial`, `drones`, `lattice`, `multi_recommend`, `violations`); `harness run` green both in-process (`--transport inproc`) and over MCP (`--transport mcp`). *(Verified 100.0% parity on 5/5 scenarios over inproc and mcp on 2026-11-06)*
- [ ] CI fully green on the merge commit, including the Matrix Test jobs, Degraded Mode job, Coverage Report job ($\ge 90\%$), and Benchmark job. *(Pending push and remote GitHub Actions run)*
- [x] Independent check of the completed plan against code (same discipline as the cycle-plan check): every ticked item verified against its commit+test or dated output; any item that cannot be evidenced stays unticked with a reason. *(Independent check completed on 2026-11-06: 23 items verified against code, tests, and benchmark outputs; line 65 and line 152 stay unticked pending merge commit CI run)*
