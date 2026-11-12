# Hydrogen evaluation brief — Ontology-Spider — 2026-11-12 EST

## What this is

Instructions for Gemini 4 Hydrogen (in Antigravity) to analyze the Ontology-Spider repository and evaluate where improvements can be made and where further development is possible — and to report what it finds.

This is an **analysis task, not an implementation task**. Read the repo, run the checks, evaluate, and write up the findings. Do not build anything yet; the user decides what gets built.

## The repository

Ontology-Spider is a standalone successor to GE Research's DARPA ASKE **Dialog** language (NOT Datalog) for creating and traversing ontologies conversationally, with SWI-Prolog as the reasoner and a Python BFS fallback. It has a brain-harness plugin through a clean model-import seam (thin adapter, not a fork) — the plugin lives in the Brain-Harness repo, not here; the seam is documented in `docs/seam.md`.

Repo layout: `src/` (engine, reasoners, MCP server, CLI, elicitation, harness), `tests/`, `docs/`, `examples/`, `plan archive/` (completed plans — they show what was done, what was deferred, and what the evidence rules are).

Last verified state (2026-11-12, head `4950d5c`): suite 105/105 with swipl, 91 passed + 14 skipped in degraded mode, coverage 91%, parity 100% (5/5), `ruff check` + `mypy src` clean, CI 11/11 green. **Do not trust these numbers — re-verify them yourself as the first step.**

## Standing decisions (do not relitigate without new evidence)

From `docs/decisions.md`, Track 0 and later sections:

- Zero third-party dependencies (stdlib + unittest only). Fresh minimal `.dialog` syntax. Triples + canonical vocabulary + provenance on every assertion. swipl **subprocess bridge, NOT PySWIP**, with a degraded mode. Hand-written parser. Python >= 3.10.
- MCP write default is **settled**: in-memory session writes by default, `--read-only` opt-in.
- Engineering stance: "keep it simple unless we hit limitations" — no upfront over-engineering; deferred items stay deferred until their trigger fires.
- Language syntax is an **irreversible joint**: syntax changes need a frontier model and a written decision, never drive-by edits.
- Free-form NLU / LLM parsing is **deferred with a guardrail**: any LLM assistance is a separate, explicit decision — never a silent default. Do NOT wire an LLM into the reasoner or the grammar as part of this evaluation.
- No new third-party dependencies in any proposal without flagging the guardrail explicitly.

## What to do

1. **Read the repo.** `README.md`, `docs/architecture.md`, `docs/decisions.md` (all sections, including the latest), `docs/seam.md`, `docs/mcp.md`, `docs/language_reference.md`, `docs/tutorial.md`, `pyproject.toml`, the `src/` layout (note line counts per module), `tests/`, `examples/`, and the plans in `plan archive/`. Note where the docs and the code disagree.
2. **Run the checks yourself.** The suite in both modes (with swipl; and genuine degraded mode), coverage, `ruff check` + `ruff format --check` + `mypy`, the bench, and parity. Record exact numbers. Method note: degraded mode is engaged by making swipl genuinely unavailable — verify the mode actually engaged (check the skip count and the reasoner's availability flag). Hiding swipl from `PATH` alone does not engage it; there is an absolute-path fallback in the reasoner.
3. **Evaluate.** Look at:
   - (a) The deferred Track 10 items (OWL2 DL, Datalog engine, free-form NLU, topos/consensus, distributed/WASM/GPU, Eclipse parity, speech, and anything else listed as deferred). For each: has its trigger fired? What is the evidence, measured not assumed?
   - (b) The Phase-5 backlog items still unticked in the completed plans (multi-turn retraction/amendment over MCP, persistent sessions, incremental validation, query language growth). For each: what machinery already exists, and what is actually missing?
   - (c) Architecture kinks recorded as decisions rather than fixed (check the architecture inspection notes and the decisions record).
   - (d) Anything the docs promise that the code does not deliver, or vice versa.
   - (e) Test, lint, and typing gaps (coverage, format enforcement, mypy scope).
   - (f) Anything else you find that the above does not cover.
4. **For each finding, record:** what it is; the evidence (file:line, test name, doc quote, or measured number); the concrete scope of the work (and what NOT to do); the risk and irreversibility (especially anything touching language syntax or the seam); and whether it is worth doing now or should stay deferred — with the trigger that would change that answer.

## Deliverable

Write the findings to a dated file at the repo root, e.g. `Hydrogen evaluation-2026-11-12-EST.md`:

- A **ranked list** (highest value first), each item with its evidence and concrete scope.
- A **"do not develop next"** section, each item with its reason (no trigger, contradicts a recorded decision, duplicates existing machinery, premature).
- A short note on the live state you measured (suite, coverage, parity, bench, lint/type), so the next reader can see what the numbers were on this run.

## Rules

- Verify every claim against the code by running it or reading it — do not assert from memory or from this brief. If a claim in this brief is wrong, say so with the evidence; do not repeat it.
- Separate observed output from inference in every finding.
- Do not edit source code. Do not tick or untick any checkbox in any plan file. Do not push anything. This is read-only analysis; the user decides what gets built and what gets ticked.
- Keep it tight and checkable: file:line evidence for every decisive claim.
