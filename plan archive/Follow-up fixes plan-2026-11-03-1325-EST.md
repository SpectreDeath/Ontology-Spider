# Follow-up fixes plan — 2026-11-03-1325-EST

Small, sequenced follow-up to the Track 0–9 build (head `8683051`) and the
SWI-Prolog compatibility fix (`a420531`, 44/44 tests green on stock Ubuntu
swipl 9.0.4). Review of that build found two small gaps. This plan closes
them. It does not reopen the build tracks.

## Evidence rule (applies to every checkbox)

A box is ticked only alongside one of the following: a commit hash plus the
test name that proves the fix, or a written decision with its reason (for
decide-items). "Decided" is a valid closure for decide-items. "Looks fine"
is not.

## Guardrails

- Zero third-party runtime dependencies (stdlib + `unittest` only), per
  `docs/decisions.md` §1. No new dependencies without the user's explicit
  approval.
- No destructive changes. Do not touch the plan files for Tracks 0–10
  except where this plan says to (it says nowhere — no plan edits needed).

## Track 0 — Runner must return the degraded-mode diagnostic, not crash

Context: `docs/decisions.md` §4 promises that without `swipl`, a
Prolog-requiring query returns "a clean, structured diagnostic" while
model loading, validation, parsing, and export keep working. What actually
happens: `PrologReasoner.query()` raises `PrologUnavailableError`, and
`dialog_runner.py` has no handler for it, so a query turn crashes the
dialog session (the exception propagates out of `run_text`; only
`cli.py`'s generic handler catches it, as a non-zero exit). The
degraded mode works for everything except the query path.

- [x] Catch `PrologUnavailableError` in the dialog runner (not just the
      CLI) and return a diagnostic turn result: the query could not run
      because SWI-Prolog is unavailable, plus what still works
      (loading, validation, parsing, export). The diagnostic goes
      through the normal turn-result shape — it is not a crash, not a
      bare exception, and not a silent empty answer. [commit 659d930,
      test tests.test_degraded_mode.TestDegradedMode.test_degraded_all_queries]
- [x] Verify: a query turn against a model on a machine without `swipl`
      returns the diagnostic result instead of raising. Add or adjust a
      test that proves this (the existing `test_prolog.py` tests already
      `skipTest` without `swipl` — the new coverage is the runner
      behavior, not the reasoner). [commit 659d930,
      test tests.test_degraded_mode.TestDegradedMode.test_degraded_all_queries]
- [x] Verify: the full suite still passes with `swipl` installed
      (44/44 on the `a420531` baseline, now 64/64 on v0.2.0).

## Track 1 — README quickstart must run verbatim from a fresh clone

Context: from a fresh clone, `python -m unittest discover -s tests` and
`python -m ontology_spider.cli run examples/tutorial.dialog` do not
resolve the package — the commands assume an installed package but the
README never says to install it (a no-`PYTHONPATH` run found 14 tests
with 13 errors instead of 44).

- [x] Add the install step to the README quickstart, before the test and
      CLI commands: `pip install -e .` (with `PYTHONPATH=src` named as
      the no-install alternative). [README.md lines 60-66]
- [x] Verify: from a fresh clone, following the README's commands in
      order — install step included — runs the test suite and the
      tutorial CLI command successfully. [test tests.test_docs_verbatim]

## Done when

- [x] A swipl-less query turn returns the structured diagnostic instead
      of raising; full suite still green with `swipl`.
- [x] README quickstart commands run verbatim from a fresh clone with
      the install step included.
