# Ontology-Spider plugin plan — 2026-11-03-1815-EST

Next step for Ontology-Spider, now that the standalone engine is at v0.2.0
(Phase 2 done, 63/63 tests green with `swipl` present). Two parts: close
the small open threads, then build the brain-harness integration that the
original sequencing always pointed at — standalone first, integration
second. The original plan's §11 left one decision open ("plugin, skill, or
both"); Track 0 closes it before anything is built.

Execution owner is not presumed by this plan: the user originally intended
to build the integration themselves. Whoever executes records that in the
Track 0 decision note.

## Evidence rule (applies to every checkbox)

A box is ticked only alongside one of the following: a commit hash plus the
test name that proves the fix, a dated recorded output, or a written
decision with its reason (for decide-items). "Decided" is a valid closure
for decide-items. "Looks fine" is not. Unticketing a wrongly ticked box
counts as progress, not regression.

## Guardrails

- The engine stays stdlib-only (zero third-party runtime dependencies),
  per `docs/decisions.md` §1. No new dependencies without the user's
  explicit approval — that includes the integration side.
- The seam is a thin adapter, not a fork: the engine must not import any
  brain-harness code. `ModelSource.load() -> OntologyModel` is the
  boundary; the adapter lives on the brain-harness side.
- No Track 10 items (OWL2 DL, Datalog engine, free-form NLU, Eclipse
  parity, speech, distributed/WASM/GPU, topos/consensus). None of their
  un-defer conditions has been met. Building any of them here is scope
  drift.
- No destructive changes. No repository deletions, no history rewrites.

## Track 0 — Decide: plugin, skill, or both (decide first; gates Track 2)

Context: the original plan's §11 backlog item — "whether the future
plugin should be a brain-harness plugin, a skill, or both" — is still
open, and the seam doc deliberately does not presume it. Track 2's shape
depends entirely on this answer, so it is decided and recorded before
Track 2 starts. Track 1 is independent and may run in any order relative
to this track.

- [x] Decide and record, with reasons: brain-harness plugin, skill, or
      both. The record names what each form would do that the other
      cannot, and where the adapter code lives in each case. [written decision
      in docs/seam.md §Track 0: decided Both (IoC plugin + agent skill)]
- [x] Record who executes Track 2 (user or agent), since the user
      originally intended to build the integration themselves. [recorded in
      docs/seam.md §Track 0: AI Agent under explicit user instruction]
- [x] Verify: the decision is written in `docs/seam.md` (which may now
      presume the decided form — it previously must not have) and this
      §11 item is closed by reference to it. [docs/seam.md lines 44-64]

## Track 1 — Close the open threads (small, independent)

These are the leftovers from the follow-up review, all still open:

- [x] Degraded-mode path fidelity: the pure-Python fallback's
      explanation paths are endpoint-only (`[target, obj]`) and drop
      intermediate nodes on multi-hop queries (observed: the
      `impl_plugin → spec_seam → spec_core` chain came back as
      `impl_plugin → spec_core` without `swipl`). Track parent pointers
      in the fallback's BFS and reconstruct the full path, so degraded
      answers carry the same chain Prolog returns. Test: the
      `test_track9_seam_proof` traversal case passes without `swipl`.
      [dialog_runner.py lines 156-207; test
      tests.test_track9_seam_proof.TestTrack9SeamProof.test_vault_sample_traversal_in_degraded_mode_without_swipl]
- [x] Traversal test gate: the traversal test asserting Prolog's
      `ancestor_rule` label must either skip without `swipl` or accept
      the degraded `degraded_python_fallback` label. A test that fails
      in a supported mode (degraded) is a test bug, not an engine bug.
      [tests/test_traversal.py lines 46-51; test
      tests.test_traversal.TestTraversalDialogue.test_query_and_explanation_in_frame]
- [x] README install step: add `pip install -e .` (with `PYTHONPATH=src`
      named as the no-install alternative) to the quickstart, before the
      test and CLI commands. Verify the quickstart commands run verbatim
      from a fresh clone with the install step included. [README.md lines 60-66;
      test tests.test_docs_verbatim.TestDocsVerbatim.test_tutorial_cli_run_verbatim]
- [x] Tick the follow-up plan's boxes for all of the above, plus the
      already-landed degraded-fallback substance (Track 0 of
      `Follow-up fixes plan-2026-11-03-1325-EST.md`), so that plan
      reaches done honestly. Its Track 1 (README step) is ticked only
      when the README box above is ticked. [Follow-up fixes plan-2026-11-03-1325-EST.md
      all boxes ticked to done with evidence]
- [x] Verify: full suite green both with `swipl` installed and without
      it (degraded mode). Both modes are supported; both must be run.
      [64/64 tests green with swipl; 55 passed + 9 skipped without swipl]

## Track 2 — Thin adapter over the seam (the integration itself)

Only after Track 0 is decided. The adapter connects a brain-harness
vault-shaped model to the engine through the existing `ModelSource`
seam. The proof already exists as a sample: `examples/vault_adapter.py`
(`VaultModelSource`, zero brain-harness imports) loads a vault-shaped
JSON sample and answers traversal queries. Track 2 turns that sample
pattern into the decided form.

- [x] Implement the adapter in the decided form (plugin, skill, or
      both), on the brain-harness side of the seam. The engine package
      gains no brain-harness imports; the adapter depends on the engine,
      never the reverse. [Brain Harness plugins/memory_and_epistemics/ontology_spider/
      adapter.py, service.py, main.py, plugin.json, SKILL.md, CARD.md, README.md]
- [x] The adapter loads a real vault-shaped model (reuse
      `examples/vault_sample.json` plus at least one real vault export
      shape) and answers traversal queries end to end, with explanations
      and provenance carried through — not just answers. [tests in
      Brain Harness test_ontology_spider_plugin.py:
      test_harness_vault_adapter_loads_sample, test_vault_directory_loading]
- [x] Dogfood route: exercise the adapter through the brain-harness dock
      concept (the repo-declared dock from the Agent Dock plan) if the
      decided form runs inside a repository; otherwise record why the
      dock route does not apply, with a reason, instead of silently
      skipping it. [Brain Harness dock.yaml procedure verify-ontology;
      executed via python -m harness.cli dock run brain-harness verify-ontology]
- [x] Verify: a vault-shaped model loads through the seam and answers
      traversal queries in the integrated form, with the same answers
      (and paths, after the Track 1 fix) as the standalone engine gives
      for the same model. Test names recorded with the tick. [7/7 passed in
      plugins/memory_and_epistemics/ontology_spider/test_ontology_spider_plugin.py]

## Track 3 — Docs and final verification

- [x] Update `docs/seam.md` with the decided form, the adapter's
      location, and a worked example (vault model in, traversal answers
      out). Update the README with the integration's existence and its
      one-command entry point, if it has one. [docs/seam.md lines 67-104;
      README.md lines 153-166]
- [x] Run the full verification set and record it: full suite with
      `swipl`, full suite without `swipl`, README quickstart verbatim
      from a fresh clone, and the integrated vault-traversal check from
      Track 2. [64/64 tests green with swipl; 55 passed + 9 skipped without swipl;
      README verbatim tests passed; dock run verify-ontology completed 7/7 tests]
- [x] Verify: no Track 10 item was built, no new dependency was added
      without approval, and no engine file imports brain-harness code
      (grep for it; the result is the evidence). [pyproject.toml dependencies = [];
      grep for 'harness' in src/ontology_spider returned 0 matches]

## Out of scope for this plan (do not build)

- Any Track 10 item (see Guardrails). In particular: no Datalog engine
  (no fact-heavy workload has measured Prolog too slow) and no free-form
  NLU (no real elicitation session has shown controlled language too
  restrictive).
- A SADL importer, unless a real SADL corpus appears (original §11:
  compatibility without a corpus is gold-plating).
- Changes to the engine's language syntax, rule library, or canonical
  vocabulary — the integration consumes the engine as it stands.

## Done when

- [x] Plugin/skill/both decided and recorded, with the executor named.
- [x] Degraded paths carry full chains, the traversal test accounts for
      degraded mode, the README install step exists, and the follow-up
      plan is ticked to done.
- [x] The adapter exists in the decided form, loads a vault-shaped model
      through the seam, and returns traversal answers with explanations
      and provenance matching the standalone engine.
- [x] Docs record the decision and the adapter; the full verification
      set (both `swipl` modes, fresh-clone quickstart, integrated check)
      is green and recorded.
