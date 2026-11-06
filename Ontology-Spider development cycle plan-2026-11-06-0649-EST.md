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

- [ ] **MCP implementation.** (a) Hand-roll the stdio MCP server in stdlib (assessment recommendation; guardrail intact, protocol surface is small), (b) official MCP SDK as an optional extra (`pip install ontology-spider[mcp]`, core stays dependency-free), or (c) both: stdlib stdio now, SDK-backed HTTP transport later. Record the decision with reasons.
- [ ] **Canonical `recommend` semantics (D3).** Prolog's no-filter `recommend X` means "things sharing a category with X"; Python's means "instances of class X, through the subclass closure" (the README examples imply the second). Record which is canonical; the other backend changes to match. This gates the D3 fix in Track 3.
- [ ] **README promises.** Implement multi-attribute `recommend X [k=v, ...]` and inline `explain` (recommended — the README already promises them and agents will want them), or trim the README. Record the decision.
- [ ] **MCP write access.** Default to `--read-only` with opt-in writes, or allow writes by default. Record the decision.
- [ ] **Harness home.** Ship the harness inside the package (`ontology_spider.harness`, usable by agents and Brain Harness; recommended) or keep it under `tests/` only. Record the decision.

## Track 1 — Phase 0: Stabilize (1–2 days, no dependencies)

Exit gate: D1, D2, D4, D5, D7 fixed with regression tests; docs match behavior; CI has a degraded-mode job.

- [ ] D1/D2: add `OntologyModel.upsert_entity(id, name=None, **attrs)`, building a new frozen `Entity` and bumping the version. Expose entity attributes via `MappingProxyType` (or copy on read) so in-place mutation fails loudly. Remove the in-place `existing.name` / `existing.attributes.update(...)` paths in `seam.py` and `dialog_runner.py`.
- [ ] D1/D2 regression tests: re-declare an entity with `name=` and with changed attributes; assert no `FrozenInstanceError`, the version is bumped, and Prolog answers reflect the new attributes (no stale cache).
- [ ] D4: track visited import paths (resolved, absolute) in `DialogModelSource.load`; raise `ImportCycleError` naming the chain. Pull the import logic shared by `seam.py` and `dialog_runner.py` into one place.
- [ ] D4 regression test: cyclic imports (a imports b, b imports a) raise `ImportCycleError`, not `RecursionError`.
- [ ] D5: key the facts cache by a model-owned uuid plus version; bound it with an LRU of about 8 entries.
- [ ] D5 regression test: the cache is bounded, and a new model never receives another model's facts.
- [ ] D7: escape `\n`, `\r`, `\t` and control characters in `prolog_safe_string`; harden `prolog_facts_to_model` against multi-line facts so a value containing a newline cannot silently drop an attribute or entity on round-trip.
- [ ] D7 regression tests: round-trip a value containing newline/control characters through Prolog facts and back.
- [ ] Docs: fix the README `recommend` examples to the syntax the parser accepts (or implement per the Track 0 decision); fix the `repl` flag (`-f/--file`); fix `export` (`-o/--output`, no positional output); fix the license line to MIT; fix "63 unit tests" to the real count.
- [ ] Docs: fix the stale `call_with_time_limit/2` claim in `architecture.md` and in `docs/decisions.md` §4.
- [ ] Docs: extend `test_docs_verbatim` so every README dialog code block gets parsed (it currently covers only `examples/tutorial.dialog` and one `tutorial.md` snippet).
- [ ] CI: add an ubuntu / 3.12 / no-swipl job. Degraded mode must be verified by CI, not by hand.
- [ ] CI: measure the coverage baseline first (the README's "93%" is unverified — no coverage measurement exists); record the real number; only then add a `coverage --fail-under=90` step.
- [ ] D8 explicitly not a defect: record that the `traversal.py:145` post-filter enforces all frame constraints; do not touch the post-filter. (The redundant first-constraint injection may be tidied only if a test proves the post-filter alone is sufficient.)

## Track 2 — Phase 1: Testing harness (3–5 days, depends on Track 1)

Exit gate: `python -m ontology_spider.harness run` green; parity report generated; bench baseline recorded as JSON. Stdlib only — the harness is a product feature (agents and CI both use it), not just test scaffolding.

- [ ] Harness package `src/ontology_spider/harness/` + corpus dir (per the Track 0 harness-home decision).
- [ ] Scenario format (`*.scenario.json`, or `.dialog` with `# expect:` annotations): model source, ordered turns, expected answers, expected rules and fact IDs, expected violations. Golden files are produced from reviewed runs.
- [ ] Runner: `harness run [--backend prolog|python|both] [--transport inproc|mcp]`; writes a JSON + Markdown report (pass/fail, diffs, timings).
- [ ] Differential / parity mode: `harness parity` runs every query on both backends and diffs answers as sets, plus paths. This is the check that would have caught D3.
- [ ] Generators: `harness gen chain|tree|lattice|random_dag|cyclic --size N --seed S`; deterministic synthetic ontologies for scale and edge cases, with seeded random.
- [ ] Property checks (stdlib, seeded): round-trip json → model → json is identity; dialog export re-parses to an equal model; ancestors are a superset of direct parents; adding a cycle edge always triggers `cycle_violation`.
- [ ] Bench: `harness bench --budget bench_budgets.json`; p50/p95 latency per operation × size. Output is a JSON baseline committed to `harness/baselines/`, and CI fails on a regression beyond the budget. Budgets calibrated on the CI machine first (assessment timings are laptop-specific).
- [ ] Extend the existing tutorial golden-answer corpus (`tests/test_corpus_tutorial.py` + `examples/expected_tutorial_answers.json`) to a multi-scenario corpus. It already exists as a single scenario — do not rebuild from zero.
- [ ] MCP contract suite stubbed (enabled in Track 4): same scenarios over stdio, plus protocol checks — `initialize`, `tools/list` schema validity, error codes, cancellation.

## Track 3 — Phase 2: Engine core (3–4 days, depends on Track 1; can run in parallel with Track 2)

Exit gate: Reasoner protocol and Engine/Session exist, CLI and API are ported, D3 is fixed with parity at 100% on the corpus.

- [ ] `reasoning/base.py`: a Reasoner protocol with `query(model, QuerySpec) -> ReasonerResult`, plus capabilities.
- [ ] Move the degraded BFS into `reasoning/python_backend.py` as a first-class `PythonReasoner`. Selection order: explicit choice, then swipl if present, then Python.
- [ ] `docs/semantics.md`: the canonical meaning of each query kind, including dedup, full transitive subclass closure, and ordering (per the Track 0 D3 decision).
- [ ] Fix `rules.pl` to match `semantics.md`; D3 fixed; parity at 100% on the corpus (`harness parity` green).
- [ ] `engine.py`: `Engine`, `SessionManager`, and `Session` (session_id, model, history, frames, last_result, an optional elicitation sub-state). Results use a single JSON-serializable `QueryResult` schema, so CLI, API, and MCP all emit the same shape.
- [ ] Split `ElicitationManager.step()` (366 lines) into per-state handlers, with the harness catching regressions.
- [ ] Automated stdlib-membership import-scan test (the assessment's "enforced" claim was overstated — the existing scan only checks for `brain_harness` tokens).

## Track 4 — Phase 3: MCP server (3–4 days, depends on Tracks 2 and 3)

Exit gate: `dialog mcp` starts a server; the harness drives the full scenario corpus over MCP; Brain Harness connects.

- [ ] Transport: stdio, newline-delimited JSON-RPC 2.0. Implements `initialize`, `ping`, `tools/list`, `tools/call`, `resources/list`, `resources/read`, and `notifications/cancelled`. Hand-rolled in stdlib (~300–400 LOC) per the Track 0 decision. Streamable HTTP can come later behind the same dispatcher, only if Track 0 says so.
- [ ] Entry points: `dialog mcp [--model PATH] [--backend …] [--read-only] [--root DIR]` and `python -m ontology_spider.mcp`.
- [ ] Tools, each returning the Phase 2 `QueryResult` / JSON schema: `session_open` / `session_close` / `session_list`; `model_load`; `assert_triple` / `declare_entity` / `retract` (provenance-tagged with `source=mcp:<client>`; disabled under `--read-only`); `run_dialog`; `query`; `explain`; `validate`; `export` (json / dialog / dot / html); `focus` / `constrain` / `where_am_i`; `engine_info`.
- [ ] Resources: `ontology://session/{id}/model.json`, `ontology://examples/{name}`, `ontology://docs/language-reference`.
- [ ] Trust boundary: file access confined to `--root`; writes off under `--read-only`; per-call timeout and inference cap; max sessions and max assertions per session. Record all of this in `architecture.md`.
- [ ] MCP contract suite green over stdio (from Track 2).
- [ ] Brain-Harness follow-up (not in this repo): add an MCP connection config next to the existing plugin so the harness can use the engine over MCP as well as through the in-process adapter. Record as a Brain-Harness-side item.

## Track 5 — Phase 4: Performance (4–6 days, depends on Tracks 2 and 3)

Exit gate: budgets pass in CI; no exponential case in the generator suite.

- [ ] Persistent `PrologWorker`: a long-lived swipl process that loads rules once, reloads facts only when the model version changes (incrementally via `assertz`/`retract` where possible), and takes goals over stdin/stdout JSON lines. Small pool with a per-instance lock instead of the class lock.
- [ ] Tabling (`:- table transitive_reach/3`) for reachability. Reconstruct proof paths from BFS parent pointers rather than enumerating all paths.
- [ ] Validator: Tarjan SCC for cycles (report one witness cycle per SCC), memoized superclass closure, disjointness computed per class and not per (constraint × entity).
- [ ] Model: zero-copy read views (`MappingProxyType`), an `iter_assertions()` API, and a predicate-subject adjacency index. Removes O(N) copies in hot loops.
- [ ] Harness-driven budgets pass in CI, calibrated on the CI machine. Proposed: Prolog query p50 < 15 ms; Python query on 10k assertions p50 < 5 ms; validate 10k-assertion lattice < 1 s; full test suite < 4 s.

## Track 6 — Phase 5: Direction (ongoing, depends on Tracks 4 and 5)

Exit gate: backlog re-prioritized against harness data.

- [ ] Multi-turn retraction and amendment over MCP (`retract_by_turn` is already in the model).
- [ ] Query language growth: multi-constraint `recommend`, path from X to Y, negation (`not instance_of`), and counting.
- [ ] Persistent sessions (save and restore to `.dialog` or JSON), so an agent can resume work.
- [ ] Incremental validation (validate only the delta since the last version).
- [ ] Re-test the Track 10 deferrals (OWL2, Datalog) against measured harness data, using their existing un-defer conditions. No Track 10 work starts before its trigger fires.

## Track 7 — Verification

Exit gate: the whole plan is checked, not just built.

- [ ] Full suite green in both swipl and swipl-less modes (degraded CI job green).
- [ ] `harness parity` at 100% on the corpus; `harness run` green in-process and over MCP.
- [ ] Dock `verify-ontology` entrypoint passes (Brain-Harness side check).
- [ ] Independent check of the completed plan against code (same discipline as the assessment check): every ticked item against its commit+test or dated output; any item that cannot be evidenced stays unticked with a reason.
