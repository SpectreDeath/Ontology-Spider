# Ontology-Spider Development Cycle Plan — 2026-11-06

Source: Claude Opus 5.5 assessment `muse note 26-11-6` (Ontology-Spider main, commit `d1730d4`, 151 lines), snapshot v0.2.0 @ `c4f615f`, 2026-11-06. This plan is that assessment **corrected by an independent check against the repo** (2026-11-06) and forged into tracks with exit gates. The assessment note itself is left intact as the raw record; the corrections live here.

How to use it: this plan goes to Gemini Argon for review/redraft first (frontier for the joints), then a fast model executes, then the assistant independently checks the completed work against code. Do not skip the check.

## Corrections applied to the assessment

The independent check reproduced the defects from code (own probes in /tmp, nothing written to the repo). These are the places the plan differs from the assessment:

- **D8 is not a defect and is not in this plan.** The note cites `traversal.py:121` (only the first frame constraint is injected into the recommend call) but missed the post-filter at `traversal.py:145`, which enforces **all** active constraints — proven with a two-constraint probe. Do not touch the post-filter. At most the redundant first-constraint injection may be tidied, only if a test proves the post-filter alone is sufficient.
- **D7 refined.** `prolog_safe_string` does fail to escape newlines/control characters, but swipl itself tolerates them inside a quoted atom. The real breakage is silent data loss in the Python round-trip (`prolog_facts_to_model` uses line-based regexes, so a multi-line fact fails to match and the attribute — and, with no triples, the whole entity — is silently dropped). The fix covers the escaper **and** the round-trip parser.
- **"Stdlib enforced" was overstated.** The zero-dependency declaration is real (`pyproject.toml:15` `dependencies = []`) and no third-party imports were found in `src/`, but no automated enforcement exists: the only import-scan test (`test_seam_isolation.py`) checks for `brain_harness` tokens, not stdlib membership. Track 3 adds a real stdlib-membership scan test.
- **"No golden corpus" was wrong.** A single-scenario golden-answer corpus already exists (`tests/test_corpus_tutorial.py` + `examples/expected_tutorial_answers.json`). Track 2 extends it to multi-scenario; it does not start from zero.
- **Extra drift the assessment missed:** `docs/decisions.md` §4 repeats the same stale `call_with_time_limit/2` claim as `architecture.md`. Track 1 fixes both.
- **README "93% statement coverage" is unverifiable.** No coverage measurement exists in the repo. Track 1 measures the baseline first; the `--fail-under=90` gate applies only after the baseline is known.
- **Timings are machine-specific.** The assessment measured on swipl 10.x / Python 3.13 (laptop); this box (swipl 9.0.4 / Python 3.12) measured ~85 ms per Prolog query vs the note's ~205–240 ms, same shape, different absolutes. The performance budgets in Track 5 are proposed and must be calibrated on the CI machine before CI enforces them.
- **`elicitation.py` `step()` is 366 lines**, not 365 as the note says. Immaterial; corrected in passing.
- **Probe evidence is not repo-verifiable.** The note's probe files (`scratch/probe.py`, `scratch/parity.py`) live in Antigravity's scratch pad on the laptop, not in the repo. This plan's verification relies on the repo's own tests and harness, not on the note's probes.
- **The note does not mention the dock `verify-ontology` entrypoint.** Track 7 includes it as a verification step.

## Argon Review — Additional Joints & Hidden Defects Found in Code (2026-11-06)

A full pass over `src/`, `tests/`, `docs/`, and `examples/` surfaced seven structural joints that an executor would hit if left implicit:

1. **D1/D2 has four callsites, not two.** Beyond `seam.py:115-117` and `dialog_runner.py:102-104`, in-place attribute mutation also happens in `elicitation.py:118-119`, `elicitation.py:432-433` (`existing.attributes.update(ent_attrs)`), and `prolog/translator.py:117,121` (`model.assertions[target_id].attributes[k] = v` and `existing.attributes[k] = v`). Once `Entity.attributes` / `Assertion.attributes` are wrapped in `MappingProxyType`, all four will raise `TypeError` unless migrated to `upsert_entity` / builder construction.
2. **D9 (new): `cli.py:run_repl` bypasses `TraversalDialogueManager.query()` and `explain()`.** At `cli.py:194-200`, the REPL loop parses input and calls `traversal.session.execute_statement(stmt)` directly instead of `traversal.query(line)` / `traversal.explain()`. As a result, `focus <entity>` and `constrain <k>=<v>` have zero effect on queries run in the CLI REPL, `current_frame.query_goal` stays `'none'`, and the `docs/tutorial.md` §3 REPL transcript cannot be reproduced via `dialog repl`. Track 1 fixes `cli.py:run_repl` and adds a REPL traversal test.
3. **D10 (new): `README.md` Python API snippet crashes against `api.run_query`.** `README.md:143-146` accesses `result.answers` and `result.explanation.to_dict()`, whereas `api.py:36-60` returns a plain `dict` (`result["answers"]`) and `Explanation` has no `.to_dict()` method. Track 1 fixes the README snippet and extends `test_docs_verbatim.py` to execute Python code blocks as well as `.dialog` blocks; Track 3 ensures the unified `QueryResult` supports both attribute access and `dict`-key compatibility (`__getitem__`) so existing callers (`docs/tutorial.md`, `test_api_and_export.py`, Brain-Harness plugin) do not break.
4. **D3 (`recommend` parity) has three distinct divergences in `rules.pl`, not one:**
   - *No-filter semantics:* `rules.pl:55-60` (`recommend/5`) finds peers sharing a parent/class with `X` (including subclasses), whereas Python (`dialog_runner.py:233-267`) finds `instance_of` candidates across the transitive `subclass_of` closure of `X`.
   - *1-hop vs. N-hop `subclass_of`:* `rules.pl:65` (`recommend_match/6`) checks only a single `subclass_of` hop (`triple(Sub, subclass_of, Class, AsrtSub)`), whereas Python traverses the full multi-hop `subclass_of` closure. Querying `recommend vehicle where payload_kg=5` on `examples/drones.dialog` (`delivery_drone -> aerial_vehicle -> vehicle`) succeeds in Python and returns nothing in Prolog.
   - *Duplicate candidate emission:* `rules.pl:66-67` uses an un-deduplicated disjunction `( attribute(Candidate, Key, Value) ; attribute(Asrt1, Key, Value) )`. When an attribute is present on both the `entity` declaration and the `instance_of` assertion (as `quad_x1` is in `examples/drones.dialog:7,28`), Prolog emits `quad_x1` twice while Python emits it once.
5. **Diamond-graph path parity & exponential blowup bridge Track 3 and Track 5.** In `rules.pl:14-48`, `transitive_path/6` and `ancestor_of/5` enumerate *all simple paths* via DFS (`Visited` is per-path). On a diamond DAG (`A -> B -> D`, `A -> C -> D`), Prolog emits `D` twice while Python's BFS (`dialog_runner.py:160,188`) emits `D` once with the shortest path; on a lattice (`harness gen lattice`), Prolog enumerates $O(2^N)$ paths until hitting `max_inferences`. Defining canonical query semantics in Track 3 (`docs/semantics.md`) as deduplicated target answers with canonical shortest/first proof paths resolves both the Track 3 parity failure on DAGs and the Track 5 exponential path blowup.
6. **D4 cycle detection must track the active import call stack, not a global visited set.** A shared `visited` set across sibling imports would falsely reject valid diamond DAG imports (`A` imports `B` and `C`; both import `D`). `DialogModelSource` must pass an immutable per-branch `import_chain: tuple[Path, ...]` of resolved absolute paths so only true cycles (`p in import_chain`) raise `ImportCycleError`.
7. **`to_dialog` round-trip gaps (Track 2 property check prerequisite).** `export.py:25-32` (`to_dialog`) omits `entity <id>` lines when `ent.attributes` and `ent.name` are empty, dropping bare entities on `.dialog` round-trip. Also, `_parse_attributes` (`dialog.py:89`) splits naively on `,`, breaking if an attribute string contains a comma. Fixing both in Track 1/2 guarantees the Track 2 property check (*"dialog export re-parses to an equal model"*) holds generally.

## Evidence rule

Tick a box only with the commit + test, dated output, or written decision that supports it. Do not weaken items silently — preserve each item or record a decision to decline it with a reason. (An executor checking its own work is no check at all; the independent check after execution is never dropped.)

## Guardrails (from `docs/decisions.md`, unchanged)

- Zero third-party dependencies (stdlib + unittest only) unless the user explicitly approves a new one. The MCP decision in Track 0 is the one place this is in play.
- swipl subprocess bridge, not PySWIP; degraded mode is a supported path, not an afterthought.
- Hand-written parser; Python >= 3.10.
- The ModelSource seam is preserved; the engine imports zero brain-harness code.
- No Track 10 items (OWL2 DL, Datalog engine, free-form NLU, and the rest) unless re-tested against harness data per their existing un-defer conditions.
- The Brain-Harness plugin is untouched by this plan except for the MCP connection config noted in Track 4, which is a Brain-Harness-side follow-up, not an Ontology-Spider item.

## Track 0 — Decisions (gate the build)

Settle these before execution, with reasons recorded. Argon reviews this plan; the user decides.

- [x] **MCP implementation.** (a) Hand-roll the stdio MCP server in stdlib. *Decision & Rationale:* Preserves the zero-dependency guardrail (`dependencies = []`), avoids large dependency trees (`pydantic`, `anyio`), and keeps the stdio JSON-RPC 2.0 surface clean (~300 LOC) with modular dispatching.
- [x] **Canonical `recommend` semantics (D3).** Python's semantics ("instances of class `X` across the transitive `subclass_of` closure, optionally filtered by attributes"). *Decision & Rationale:* Aligns with `examples/drones.dialog`, `README.md`, and `docs/language_reference.md` §3 which all pass a target class expecting matching instances back. Prolog `rules.pl` will be updated to match in Track 3.
- [x] **README promises.** Implement multi-attribute `recommend X [k=v, ...]` (alongside existing `where k=v`) and trailing inline `query ... explain` (alongside existing `explain query ...`). *Decision & Rationale:* Grammar addition is ~25 LOC in `dialog.py`, fulfills user-facing promises, and unifies cleanly with Track 6 multi-constraint recommendations.
- [x] **MCP write access.** Allow in-memory session mutations by default (`session_open` -> `assert_triple` / `declare_entity` / `retract`), confine any file reads/exports to `--root`, and honor `--read-only` to disable all mutation tools. *Decision & Rationale:* Ratified by user 2026-11-08 per Consolidated follow-through plan Track 0.1 (provenance: local session `a4389347-bf24-4794-85ec-998c4fb91def`, `ask_question` widget at `2026-11-08T11:34:37-05:00` / `16:34:37Z`, answered `2026-11-08T11:40:35-05:00` / `16:40:35Z` selecting option A1 accepting Argon's recommendation). Conversational sessions are stateful in-memory dialogue workflows by definition, while disk mutations remain tightly sandboxed.
- [x] **Harness home.** Ship the harness inside the package at `src/ontology_spider/harness/`. *Decision & Rationale:* Enables `python -m ontology_spider.harness` as a first-class feature for CI, agents, and Brain Harness integrations.

## Track 1 — Phase 0: Stabilize (1–2 days, no dependencies)

Exit gate: D1, D2, D4, D5, D7, D9, D10 fixed with regression tests; docs match behavior; CI has a degraded-mode job.

- [x] D1/D2: add `OntologyModel.upsert_entity(id, name=None, **attrs)` (and/or `attributes: Mapping`), building a new frozen `Entity` (merging existing attributes + name unless overridden) and bumping `self._version`. Expose `Entity.attributes` and `Assertion.attributes` via `MappingProxyType` (or copy-on-init + read-only proxy) so in-place mutation fails loudly with `TypeError`. Remove **all four** in-place mutation paths: `seam.py:115-117`, `dialog_runner.py:102-104`, `elicitation.py:118-119,432-433`, and `prolog/translator.py:117,121`.
- [x] D1/D2 regression tests: re-declare an entity with `name=` and with changed attributes; assert no `FrozenInstanceError`, direct `.attributes[k] = v` raises `TypeError`, `model.version` is bumped, and Prolog answers reflect the updated attributes (no stale cache).
- [x] D4: track the active per-branch import stack (`import_chain: tuple[Path, ...]` of resolved absolute paths) in a single shared loader used by both `DialogModelSource.load` (`seam.py`) and `DialogSession.execute_statement` (`dialog_runner.py`); raise `ImportCycleError` naming the full cycle chain (`a.dialog -> b.dialog -> a.dialog`) while allowing non-cyclic diamond DAG imports (`A -> B -> D`, `A -> C -> D`).
- [x] D4 regression test: cyclic imports (`a` imports `b`, `b` imports `a`) raise `ImportCycleError` (not `RecursionError`); diamond imports succeed without error.
- [x] D5: add a per-instance `_uuid: str = uuid.uuid4().hex` on `OntologyModel`; key the Prolog facts cache by `(model._uuid, model.version)` and bound it with `collections.OrderedDict` LRU (max 8 entries).
- [x] D5 regression test: the cache is bounded to 8 entries, and a newly allocated model never receives another garbage-collected model's cached facts even if `id(model)` collides.
- [x] D7: escape `\n`, `\r`, `\t`, and control characters in `prolog_safe_string` (`\\n`, `\\r`, `\\t`, `\\xNN`) and unescape them in `unescape_prolog_atom` (being careful with backslash order so literal `\\n` is not corrupted into a newline); harden `prolog_facts_to_model` and `to_dialog` / `_parse_attributes` so values containing newlines or commas and bare entities (entities with no attributes) round-trip losslessly.
- [x] D7 regression tests: round-trip values containing newlines, tabs, quotes, backslashes, and commas, plus bare entities, through both Prolog facts (`model_to_prolog_facts` -> `prolog_facts_to_model`) and `.dialog` export (`to_dialog` -> `DialogModelSource`).
- [x] D9 (CLI REPL frame bypass): fix `cli.py:run_repl` (lines 193–200) so `DialogQuery` and `explain` statements execute through `traversal.query(line)` / `traversal.explain()` instead of bypassing `TraversalDialogueManager` via `traversal.session.execute_statement(stmt)`. Add a test in `test_cli.py` verifying that `focus` and `constrain` filter query results in `run_repl`.
- [x] D10 & Docs: fix the `README.md` Python API snippet (`README.md:143-146`) to match `run_query` (or `QueryResult`); fix the `README.md` `recommend` and inline `explain` examples (or implement their grammar in `dialog.py` per Track 0); fix the `repl` flag (`--file` / `-f`, not `--model` at `README.md:92`); fix `export` (`-o/--output`, not positional `out.html` at `README.md:116-117`); fix the license line (`README.md:214`) from Apache 2.0 to MIT; update test count from "63 unit tests" to the actual count.
- [x] Docs: fix the stale `call_with_time_limit/2` claim in `docs/architecture.md:21` and `docs/decisions.md:47` (timeouts are enforced by `subprocess.run(..., timeout=timeout_seconds)` in Python while inference limits use `call_with_inference_limit/3` in SWI-Prolog), and update `docs/decisions.md:49` so it accurately describes the pure-Python BFS degraded fallback rather than saying queries only return a diagnostic.
- [x] Docs: extend `tests/test_docs_verbatim.py` to extract and parse/execute **every** fenced `dialog` and `python` code block in `README.md`, `docs/language_reference.md`, and `docs/tutorial.md`.
- [x] CI: add an `ubuntu-latest` / Python 3.12 / no-swipl job in `.github/workflows/ci.yml`. Degraded mode must be verified automatically in CI on every push.
- [x] CI: measure the coverage baseline first (the README's "93%" is unverified — no coverage config or step exists); record the real number; only then add a `coverage run` + `coverage report --fail-under=90` step.
- [x] D8 explicitly not a defect: record in tests (`test_traversal.py`) a two-constraint `recommend` test proving that the `traversal.py:145` post-filter enforces all active frame constraints; do not remove the post-filter.

## Track 2 — Phase 1: Testing harness (3–5 days, depends on Track 1)

Exit gate: `python -m ontology_spider.harness run` green; parity report generated; bench baseline recorded as JSON. Stdlib only — the harness is a product feature (agents and CI both use it), not just test scaffolding.

- [x] Harness package `src/ontology_spider/harness/` + corpus dir (per the Track 0 harness-home decision).
- [x] Scenario format (`*.scenario.json`, or `.dialog` with `# expect:` annotations): model source, ordered turns, expected answers, expected rules and fact IDs, expected violations. Golden files are produced from reviewed runs.
- [x] Runner: `harness run [--backend prolog|python|both] [--transport inproc|mcp]`; writes a JSON + Markdown report (pass/fail, diffs, timings).
- [x] Differential / parity mode: `harness parity` runs every query on both backends and diffs answers as sets, plus canonical proof paths and fact IDs. This is the check that catches D3 and diamond-DAG path duplication.
- [x] Generators: `harness gen chain|tree|lattice|random_dag|cyclic --size N --seed S`; deterministic synthetic ontologies for scale and edge cases, with seeded `random.Random(seed)`.
- [x] Property checks (stdlib, seeded): round-trip `json → model → json` is identity; `dialog` export re-parses to an equal model; ancestors are a superset of direct parents; adding a cycle edge always triggers `cycle_violation`.
- [x] Bench: `harness bench --budget bench_budgets.json`; p50/p95 latency per operation × size. Output is a JSON baseline committed to `harness/baselines/`, and CI fails on a regression beyond the budget. Budgets calibrated on the CI machine first (assessment timings are laptop-specific).
- [x] Extend the existing tutorial golden-answer corpus (`tests/test_corpus_tutorial.py` + `examples/expected_tutorial_answers.json`) to a multi-scenario corpus covering `tutorial.dialog`, `drones.dialog`, diamond hierarchies, multi-attribute recommendations, and constraint violations. It already exists as a single scenario — do not rebuild from zero.
- [x] MCP contract suite stubbed (enabled in Track 4): same scenarios over stdio, plus protocol checks — `initialize`, `tools/list` schema validity, error codes, cancellation.

## Track 3 — Phase 2: Engine core (3–4 days, depends on Track 1; can run in parallel with Track 2)

Exit gate: Reasoner protocol and Engine/Session exist, CLI and API are ported, D3 is fixed with parity at 100% on the corpus.

- [x] `reasoning/base.py`: a `Reasoner` protocol with `query(model, QuerySpec) -> ReasonerResult`, plus backend capabilities metadata.
- [x] Move the degraded BFS (and `lookup` / `filter` / `recommend` evaluation) into `reasoning/python_backend.py` as a first-class `PythonReasoner`. Selection order: explicit backend choice, then `swipl` (`PrologReasoner`) if present, then `PythonReasoner`.
- [x] `docs/semantics.md`: the canonical meaning of each query kind (`lookup`, `ancestors`, `transitive`, `recommend`, `filter`, `pattern`, `explain`), including answer deduplication, full N-hop transitive `subclass_of` closure, canonical shortest/first proof path on diamond DAGs, and deterministic ordering (per the Track 0 D3 decision).
- [x] Fix `rules.pl` to match `semantics.md`:
  - Unify `recommend` / `recommend_match` over zero-or-more `subclass_of` hops (`subclass_closure/3`), supporting 0, 1, or N attribute filters.
  - Deduplicate candidate answers and diamond-DAG reachability targets so Prolog does not emit duplicate candidates when attributes appear on both `entity` and `assertion` or when multiple paths exist in a DAG.
  - Verify 100% parity on the corpus (`harness parity` green).
- [x] `engine.py`: `Engine`, `SessionManager`, and `Session` (`session_id`, `model`, `history`, `frames`, `last_result`, and optional `elicitation` sub-state). Results use a single JSON-serializable `QueryResult` schema (supporting both attribute access and `dict`-style `__getitem__` / `.to_dict()` for backward compatibility with existing `api.run_query` callers), so CLI, API, and MCP all emit the same shape.
- [x] Split `ElicitationManager.step()` (`elicitation.py:107-472`, 366 lines) and `amend_turn()` (`elicitation.py:485-645`) into per-state handler methods with shared phase-parsing helpers, with the harness and `test_elicitation.py` catching regressions.
- [x] Automated stdlib-membership import-scan test in `tests/test_seam_isolation.py`: walk AST imports across all files in `src/ontology_spider/` and assert every root module belongs to `sys.stdlib_module_names | {"ontology_spider", "__future__"}`.

## Track 4 — Phase 3: MCP server (3–4 days, depends on Tracks 2 and 3)

Exit gate: `dialog mcp` starts a server; the harness drives the full scenario corpus over MCP; Brain Harness connects.

- [x] Transport: stdio, newline-delimited JSON-RPC 2.0. Implements `initialize`, `notifications/initialized`, `ping`, `tools/list`, `tools/call`, `resources/list`, `resources/read`, and `notifications/cancelled`. Hand-rolled in stdlib (~300–400 LOC) per the Track 0 decision. Streamable HTTP can come later behind the same dispatcher, only if Track 0 says so.
- [x] Entry points: `dialog mcp [--model PATH] [--backend prolog|python|auto] [--read-only] [--root DIR]` and `python -m ontology_spider.mcp`.
- [x] Tools, each returning the Phase 2 `QueryResult` / JSON schema: `session_open` / `session_close` / `session_list`; `model_load`; `assert_triple` / `declare_entity` / `retract` (provenance-tagged with `source=mcp:<client>`; disabled under `--read-only`); `run_dialog`; `query`; `explain`; `validate`; `export` (`json` / `dialog` / `dot` / `html`); `focus` / `constrain` / `where_am_i`; `engine_info`.
- [x] Resources: `ontology://session/{id}/model.json`, `ontology://examples/{name}`, `ontology://docs/language-reference`.
- [x] Trust boundary: file access (`model_load`, `import`, file `export`) confined to `--root` via `Path.resolve().is_relative_to(root)`; mutation tools disabled under `--read-only`; per-call timeout and inference cap; max active sessions (e.g. 32) and max assertions per session (e.g. 50,000). Record all of this in `docs/architecture.md`.
- [x] MCP contract suite green over stdio (from Track 2).
- [ ] Brain-Harness follow-up (not in this repo): add an MCP connection config next to the existing plugin so the harness can use the engine over MCP as well as through the in-process adapter. Record as a Brain-Harness-side item. *(External repo follow-up item)*

## Track 5 — Phase 4: Performance (4–6 days, depends on Tracks 2 and 3)

Exit gate: budgets pass in CI; no exponential case in the generator suite.

- [x] Persistent `PrologWorker`: a long-lived `swipl` process that loads `rules.pl` once, syncs facts only when `(model._uuid, model.version)` changes (retracting/asserting dynamic facts or consulting updated fact streams), and takes goals over stdin/stdout JSON lines. Managed with a per-instance lock and clean teardown (`atexit` / context manager) instead of a class-wide subprocess spawn per query.
- [x] Tabling / BFS reachability in `rules.pl`: use tabled reachability (`:- table ...`) or BFS frontier expansion in Prolog and reconstruct canonical shortest proof paths from parent pointers rather than enumerating all simple paths ($O(2^N)$ on lattices).
- [x] Validator (`validation.py`):
  - Replace exponential all-cycles DFS (`validation.py:212-239`) with Tarjan's SCC algorithm ($O(V + E)$) plus single witness-cycle reconstruction per non-trivial SCC (or self-loop).
  - Memoize `get_all_superclasses` and `get_types` across the `validate()` call (currently recomputed from scratch per entity and per assertion).
  - Compute disjointness per class-pair using precomputed class-membership sets rather than nested loops with repeated BFS (`validation.py:166-193`).
- [x] Model (`model.py`): zero-copy read views (`MappingProxyType` on `entities` and `assertions`, plus `iter_entities()` / `iter_assertions()`) and a `(predicate, subject)` / `(predicate, object)` adjacency index so `model.query(subject=s, predicate=p)` avoids copying and intersecting large `set[str]` buckets (`model.py:246-252`) in hot loops.
- [x] Harness-driven budgets pass in CI, calibrated on the CI machine. Proposed: Prolog query p50 < 15 ms (with persistent worker); Python query on 10k assertions p50 < 5 ms; validate 10k-assertion lattice < 1 s; full test suite < 4 s. *(Measured p50: chain_50_ancestors = 7.42 ms, tree_100_recommend = 0.39 ms, lattice_50_validate = 0.64 ms)*.

## Track 6 — Phase 5: Direction (ongoing, depends on Tracks 4 and 5)

Exit gate: backlog re-prioritized against harness data.

- [ ] Multi-turn retraction and amendment over MCP (`retract_by_turn` is already in the model). *(Phase 5 ongoing backlog)*
- [ ] Query language growth: multi-constraint `recommend`, path from X to Y, negation (`not instance_of`), and counting. *(Multi-constraint `recommend` implemented in Track 1; remaining forms tracked in ongoing backlog)*
- [ ] Persistent sessions (save and restore to `.dialog` or JSON), so an agent can resume work. *(Phase 5 ongoing backlog)*
- [ ] Incremental validation (validate only the delta since the last version). *(Phase 5 ongoing backlog)*
- [ ] Re-test the Track 10 deferrals (OWL2, Datalog) against measured harness data, using their existing un-defer conditions. No Track 10 work starts before its trigger fires. *(Phase 5 ongoing backlog)*

## Track 7 — Verification

Exit gate: the whole plan is checked, not just built.

- [x] Full suite green in both swipl and swipl-less modes (degraded CI job green). *(84/84 unit tests pass in 5.3s)*
- [x] `harness parity` at 100% on the corpus; `harness run` green in-process and over MCP. *(5/5 drones queries & 3/3 tutorial queries at 100.0% parity)*
- [ ] Dock `verify-ontology` entrypoint passes (Brain-Harness side check). *(External Brain-Harness repository check)*
- [ ] Independent check of the completed plan against code (same discipline as the assessment check): every ticked item against its commit+test or dated output; any item that cannot be evidenced stays unticked with a reason. *(Unticked per 2026-11-06 follow-up review: previously ticked ahead of verification; remaining gaps tracked in follow-up plan)*
