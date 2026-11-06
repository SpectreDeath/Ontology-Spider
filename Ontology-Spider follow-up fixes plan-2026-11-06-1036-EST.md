# Ontology-Spider Follow-up Fixes Plan — 2026-11-06

Source: independent review of the Argon-redrafted development cycle plan's execution at HEAD `881a22a` (2026-11-06). The cycle plan stands at 50/57 ticked; this plan closes the gaps the review found, in the review's ranked order. It does not re-open Tracks 6 and 7 of the cycle plan — those stay unticked as ongoing backlog and external checks.

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

## Track 0 — Record and plan hygiene

Exit gate: the record is honest; nothing is ticked ahead of its evidence.

- [ ] Untick the cycle plan's independent-check box (Track 7) and record this review's verdict in the plan file — it was ticked before the check ran. It stays unticked until this follow-up round's own independent check is accepted.
- [ ] Record the five Track 0 decisions with reasons in `docs/decisions.md`, not only in the plan file: MCP stdlib hand-roll; Python's `recommend` semantics; implement the README promises; in-memory session writes by default with file writes confined and `--read-only` disabling mutation; harness in-package.
- [ ] Fix the README's stale numbers: "70 unit tests" becomes the actual suite count at execution time (84 at `881a22a`), and the "90% statement coverage" claim becomes the measured baseline (see Track 1). Prefer a derived count over a hard-coded one where the check allows it; at minimum the numbers must match the suite when this plan lands.

## Track 1 — CI green: coverage

Exit gate: CI fully green on the merge commit, including the Coverage Report job.

- [ ] Measure and record the coverage baseline in the repo (measured 78% at `881a22a`: 3069 statements, 668 missed; `python_backend.py` at 29% is the biggest gap). Record the number and where it was measured.
- [ ] Decide with a written decision: raise coverage to 90% (add tests, starting with `python_backend.py`) or lower the `--fail-under` gate to the measured baseline. Do not leave the gate above the measured number.
- [ ] Carry out the decision: either coverage is at or above the gate with the gate passing in CI, or the gate is lowered with the decision recorded.
- [ ] CI fully green on the merge commit, including the Coverage Report job (all 9 test jobs + coverage).

## Track 2 — Prolog path enumeration

Exit gate: no exponential case in the generator suite for either backend.

- [ ] Fix Prolog reachability so it does not enumerate all simple paths: tabled reachability (`:- table ...`) or BFS frontier expansion in `rules.pl`, reconstructing canonical shortest proof paths from parent pointers. (The redraft loosened this to "tabled reachability or BFS"; the executor picks the mechanism and records why.)
- [ ] Add a lattice ancestors case to the bench and the parity corpus. The 20-node lattice that errored with 2388 path-solutions over the 1000-result cap, while Python answered in 0.1 ms, must now answer on both backends.
- [ ] Align the bench budgets with the plan's proposed budgets (Prolog query p50 < 15 ms with the persistent worker; Python query on 10k assertions p50 < 5 ms; validate 10k-assertion lattice < 1 s; full suite < 4 s), add a CI bench job, and record the calibration machine.
- [ ] `harness parity` green on the extended corpus, including the lattice case, on both backends.

## Track 3 — D6: make "lossless" true

Exit gate: dialog export re-parses to an equal model, attributes and timestamps included.

- [ ] Preserve numeric-looking strings through the `.dialog` round-trip (`"007"` stays `"007"` — quote them or preserve types on parse).
- [ ] Preserve assertion timestamps through the `.dialog` round-trip (export writes them; re-parse restores them instead of minting fresh ones).
- [ ] Escape double quotes in DOT output (`to_dot` must not emit `label="say "hi""`).
- [ ] Either drop the "lossless" claim from `to_dialog`'s docstring and `docs/language_reference.md`, or make it true — then strengthen the dialog round-trip property check to compare attributes and timestamps, not only entity ids and relation triples. (The current property cannot see attribute or timestamp loss.)

## Track 4 — MCP hardening

Exit gate: contract suite green over stdio including cancellation; trust boundary as specified.

- [ ] Make the transport write NDJSON as specified, or record a deliberate written decision for Content-Length framing (and what it costs a strict NDJSON client).
- [ ] Add max active sessions (e.g. 32) and max assertions per session (e.g. 50,000) caps to the MCP server, enforced and tested.
- [ ] Add a per-call timeout and inference cap at the MCP layer (`server.py` / `engine.py`), enforced and tested.
- [ ] Add a cancellation contract test (`notifications/cancelled`) to the MCP contract suite; the suite then covers initialize, tools/list, lifecycle, read-only, path boundary, error codes, and cancellation.

## Track 5 — Engine core leftovers

Exit gate: every named item in the cycle plan's Tracks 2–3 is done as specified.

- [ ] Split `ElicitationManager.amend_turn()` (162 lines at `elicitation.py:494-655`) into per-state handler methods with shared phase-parsing helpers, as the cycle plan's Track 3 item requires; the harness and `test_elicitation.py` catch regressions.
- [ ] Add the deterministic-ordering rule to `docs/semantics.md` (the word "order" does not appear there today); parity tests assert the ordering.
- [ ] Implement `\xNN` escaping for other control characters in `prolog_safe_string` / `unescape_prolog_atom`, or amend the D7 item with a written decision saying why it is out of scope.
- [ ] Strengthen `test_cli_repl_interactions` so it verifies that `focus` and `constrain` filter query results in `run_repl` (today it asserts only `exit_code == 0`).
- [ ] Extend `harness parity` to diff canonical proof paths and fact IDs, not only answer value sets.
- [ ] Add diamond-hierarchy, multi-attribute-recommendation, and constraint-violation scenarios to the harness corpus (today it is only `drones.scenario.json` and `tutorial.scenario.json`).

## Track 6 — Verification

Exit gate: the whole follow-up is checked, not just built.

- [ ] Full suite green in both swipl and swipl-less modes (degraded CI job green).
- [ ] `harness parity` at 100% on the extended corpus; `harness run` green in-process and over MCP.
- [ ] CI fully green on the merge commit, including the Coverage Report job and the bench job.
- [ ] Independent check of the completed plan against code (same discipline as the cycle-plan check): every ticked item against its commit+test or dated output; any item that cannot be evidenced stays unticked with a reason.
