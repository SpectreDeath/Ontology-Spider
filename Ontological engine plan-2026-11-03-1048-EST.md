# Ontological engine plan — 2026-11-03 (Muse draft for Argon review)

**What this is:** a plan for a NEW repository, not a change to an existing one.
The repository (`SpectreDeath/Ontology-Spider`, public, MIT license) was
created 2026-11-03 with an initial commit (LICENSE + README). This plan is the
design that precedes the build: a complete ontological engine, built
standalone first, in the lineage of ASKE Dialog and Em-Cubed's ontology core,
with Prolog as the reasoner and Dialog as the conversational language. The
brain-harness plugin comes later, built by the user once the standalone engine
exists — it is NOT part of this plan except as the seam proof in Track 9.

**Workflow note (read this first):** this plan goes to Gemini Argon on High
effort for checking, and Muse checks any redraft. Lesson from earlier rounds,
stated plainly so it is not repeated: a redraft must preserve every item below
or explicitly record a decision to decline it with a reason — weakening by
rewording is not a fix, and a redraft that invents command lists, counts, or
capabilities without checking will repeat the integrated-toolkits failure. The
"non-weakenable" items are marked **[NW]**. A redraft must cite ancestors by
file or repo, not from memory: ASKE Dialog claims come from the
GEGlobalResearch/DARPA-ASKE-TA1 and TA2 repos and their wikis, Em-Cubed claims
from the Em-Cubed repo at HEAD `755c8e8`, brain-harness claims from that repo
at `46411d8`.

**Boundary:** this plan doc is the only deliverable of this round. It creates
no repository, writes no code, and makes no decision the user has not made.
No new third-party dependencies without the user's explicit approval (the
user's standing guardrail, carried over from brain-harness). Keep it simple:
decide first, smallest fix that closes the item, no upfront over-engineering.
The user's engineering maxim governs this plan: simplicity is the hallmark of
engineering, not complexity.

## Evidence rule (applies to every checkbox)

A box is ticked only alongside one of the following: a commit hash plus the
test name that proves the item, a dated recorded output, or a written decision
with its reason (for decide-items). "Decided" is a valid closure for
decide-items. "Looks fine" is not. Unticking a wrongly ticked box counts as
progress, not regression.

## Current state: ancestors, and what is new

The engine is not built from nothing. Its ancestors, all verified before this
plan was written:

- **ASKE Dialog (GE Research, DARPA ASKE TA1/TA2, open source on GitHub).**
  Eclipse plugins implementing a Dialog grammar and IDE as extensions to SADL
  (`com.ge.research.sadl.darpa.aske.dialog.parent` in the TA1 repo). A
  `.dialog` file has a URI statement, import statements naming the semantic
  models (knowledge graphs) the dialog uses, and then queries. The system
  answers with computed answers plus model visualizations, and supports
  follow-up queries for explanatory details about how answers were obtained,
  through a chat-like Eclipse interface. SADL itself is a controlled-English
  language for writing statements and queries over a knowledge graph ontology.
  ASKE's install instructions list SWI-Prolog as required for assumption
  checking — so the Dialog-plus-Prolog pairing already exists there, with
  Dialog as the conversational query language and Prolog as the checker.
  ASKE Dialog is Eclipse/Xtext-era tech (2019 releases, Java 8, Eclipse
  2018-12) and a prototype with known quirks (a dialog page could get into a
  state where every keystroke re-triggered a query).
- **Em-Cubed ontology core** (`src/em_cubed/ontology/`, 20+ modules, at HEAD
  `755c8e8`). Elicitation turns expert natural language into formal
  BFO/OntoClean ontologies (decision questions, faceted analysis, competency
  questions, confirmation); GraphPathRAG does multi-hop semantic triple
  traversal with auditable paths; there is a ledger with validation, SHACL
  validation, concept induction, consensus, and a visualizer. Thesis:
  "Pydantic at the door, Ontology at the ledger."
- **Em-Cubed logic surfaces.** Prolog via PySWIP SWI-Prolog with one shared
  engine behind a lock (the C engine is not thread-safe for concurrent FFI),
  predicate extraction, and safe value conversion
  (`src/em_cubed/surfaces/prolog_surface.py`). Datalog via pyDatalog for
  fact-heavy queries, plus Clingo, Kanren, and Z3 surfaces.
- **`skill_taxonomy.pl`** (Em-Cubed, `skills/META_ENGINEERING/skill-taxonomy/`).
  A hand-written declarative ontology in Prolog — profession/domain facts,
  domain/reference facts, subskill trees, meta-wrapper guardrails,
  skill/profession mapping — plus inference rules that are the miniature form
  of this engine's query shapes: `recommend_materials`,
  `resolve_skill_ancestry`, `infer_professions_from_keywords`,
  `get_profession_hierarchy`, `get_domain_skills`. Note: no code in
  `src/` or `tests/` references it by name, so whether it is consulted at
  runtime or stands alone as a reference artifact is unverified — do not build
  on an assumed answer.
- **Brain-harness vault (future model, not a dependency).** Dual-file items
  (`metadata.json` + `summary.md`), typed edges, a derivation engine, and a
  lifecycle model. The vault is the first model the engine will one day be
  pointed at, through the import seam — it is not imported or depended on by
  this plan's build.

What is new here, and why it is not just a port:

1. **Creation, not only querying.** ASKE Dialog queries models that already
   exist. This engine adds the other half: an elicitation dialogue that
   *creates* the ontology, turn by turn, with confirmation — Em-Cubed's
   elicitation shape, but as a managed dialogue rather than a pipeline.
2. **Eclipse-free.** The Dialog idea, rebuilt on a modern stack with no IDE
   plugin, no Xtext grammar, no Java 8 floor.
3. **Seam-first.** The model-import seam is a first-class interface, designed
   so the later brain-harness plugin is a thin adapter, not a second
   implementation. If the seam is right, the plugin step is small; if it is
   wrong, the plugin step becomes a fork. That is why the seam is [NW].

## What "complete" means here

Complete means the full loop works end-to-end on a sample corpus: import a
model, create ontology content by dialogue, traverse it by dialogue, validate
it, explain every answer, and export it. Complete does NOT mean every
Em-Cubed or ASKE feature ported. Track 10 names what is explicitly deferred
so "complete" cannot balloon into "everything."

## Design principles (decide against these, not around them)

- **Text dialogue first.** No speech I/O (no ASR/TTS). The DARPA Communicator
  speech stack is an ancestor for dialogue management, not a scope item.
- **Controlled language, not free-form parsing.** Queries and assertions use
  a small, documented syntax. Free-form natural language understanding is a
  separate decision, not a silent default.
- **Every answer carries its explanation.** Which facts fired, which rules
  fired, what path was walked. ASKE's explanatory follow-ups are the model;
  an answer without provenance is a bug, not a feature.
- **Trust stated plainly.** Prolog can execute I/O. The plan must say what is
  and is not sandboxed, and must not repeat the brain-harness failure mode of
  a restriction that does not restrict. v1 runs local, trusted models only,
  and says so.
- **One derivation, few formats.** Exports share one model traversal; v1
  ships two or three formats, not six.

## Suggested order

Track 0 (decide), then Tracks 1+2+3 together (the core loop: import a model,
ask in Dialog, get a Prolog answer with an explanation), then Tracks 4+5 (the
two dialogues), then 6, 7, 8, 9. Track 10 is deferred, not scheduled. Tracks
are pickable one at a time; nothing here is started unasked beyond this plan
doc. This plan goes to Argon (High effort) for checking, then back to Muse
for the redraft check, before any build starts.

## Track 0 — Settle the design (decide-first)

No engine code until the decisions below are recorded with reasons. The only
code in this track is the repository skeleton. This track may overturn the
working assumptions in this plan — that is its job.

- [ ] Repository created (name: Ontology-Spider, license: MIT — decided by
      the user at repo creation 2026-11-03; initial commit holds LICENSE +
      README). Skeleton: README stating what the engine is and is not,
      `.gitignore`, Python package skeleton, CI running lint + test on an
      empty core, green before any engine code lands.
- [ ] Language decision recorded: adopt the ASKE SADL/Dialog grammar as-is,
      adapt it, or design a fresh minimal syntax inspired by Dialog.
      Recommendation: fresh minimal syntax. The Xtext grammar is Eclipse-bound
      and 2019-era; a fresh parser keeps the standalone free of Eclipse. If
      adopting, record the ASKE repos' license compatibility first (see §11).
      Record the decision and its reason either way.
- [ ] Model decision recorded: triples (subject, predicate, object) plus
      attributes, or something richer? Recommendation: triples first. An OWL
      subset only if a concrete need appears during Tracks 1–3, not upfront.
- [ ] Runtime decision recorded: Python + SWI-Prolog via PySWIP, single shared
      engine behind a lock (the Em-Cubed surface pattern). Record the fallback
      if SWI-Prolog is unavailable: hard requirement, or degraded mode with
      Prolog-dependent features disabled? Decide, do not leave implicit.
- [ ] Parser decision recorded: hand-written recursive-descent parser over
      the fresh syntax, or a parser library (which needs the user's dependency
      approval). Recommendation: hand-written — the syntax is small, and a
      library is a dependency for a problem this size does not need.
- [ ] Python floor recorded. Recommendation: 3.10+, matching the user's other
      repos (Em-Cubed and brain-harness both floor at 3.10). Record the floor
      and the reason.
- [ ] Verify: a decisions doc exists with a reason for every decision above;
      skeleton repo builds and CI is green on the empty core.

## Track 1 — Model and import seam **[NW for the seam interface]**

The seam is the load-bearing part of the whole project: the later plugin
depends on it being clean. A seam with brain-harness-specific imports is a
failed seam.

- [ ] Core model types: Entity, Relation (a triple), Attribute. In-memory
      store with add, retract, and query. Provenance on every assertion:
      source, timestamp, and the dialog turn that produced it (for
      elicitation-created content) or the import source (for loaded content).
- [ ] Import seam: a `ModelSource` interface with one method, `load()`, that
      returns a model. Built-in sources for v1: a JSON graph reader, and
      authoring in the Dialog language itself (a model written as a dialog
      file — dogfooding the language as the authoring format). No other
      source in v1.
- [ ] The seam carries no brain-harness-specific code, imports, or field
      names. A second source implemented against the interface (in Track 9's
      seam proof) must work without touching the seam.
- [ ] Verify: two independent sources load the same sample model and produce
      identical query answers; the seam module imports nothing
      brain-harness-specific (checked by import inspection, not by assertion
      alone).

## Track 2 — Dialog language

The language is the user's hands on the engine. It must be small enough to
learn in one sitting and precise enough that a query means one thing.

- [ ] `.dialog` file format: header (a name/URI plus import statements naming
      the models the dialog uses, ASKE-style), then turns: queries and
      assertions in the controlled syntax, plus comments. One file, one
      dialog, readable without tooling.
- [ ] Parser for the Track 0 syntax: queries, assertions, imports, comments.
      Parse errors report the line and the expected form, not a traceback.
- [ ] CLI: `dialog run <file.dialog>` (batch: run every turn, print every
      answer) and `dialog repl` (interactive: one turn at a time, with
      history). Batch and interactive agree on every sample.
- [ ] Query coverage for v1: fact lookup ("what is X?"), one-hop and
      multi-hop relation traversal ("what does X depend on, transitively?"),
      filtered queries (attribute constraints), and "explain this answer"
      (the follow-up that returns the facts, rules, and path behind an
      answer — ASKE's explanatory follow-up, as a first-class query form,
      not an afterthought).
- [ ] Verify: a sample `.dialog` file over the sample model returns the
      expected answers with explanations; REPL and batch agree on all
      samples; a malformed file reports line + expected form.

## Track 3 — Prolog reasoner

Prolog holds the model and does the reasoning. The engine translates the
model into facts and runs the user's query as a goal; the rule library is
what turns facts into answers.

- [ ] SWI-Prolog via PySWIP, single shared engine behind a lock (the
      Em-Cubed surface pattern — the C engine is not thread-safe for
      concurrent FFI). Model-to-facts translation with safe value conversion
      (escaping, quoting, list handling), mirroring the Em-Cubed surface's
      `_prolog_safe_value` approach. Translation is round-trippable: facts
      generated from a model, read back, equal the model.
- [ ] Rule library, mirroring the `skill_taxonomy.pl` query shapes but over
      any model: transitive ancestry ("all ancestors of X"), dependency
      closure ("everything X depends on"), recommendation ("things related
      to X by shared domain/category"), and keyword/attribute inference
      ("things matching these attributes"). Rules live in Prolog source
      files in the repo, not generated strings hidden in Python.
- [ ] Query caps and timeouts: a per-query timeout and a fact/result cap
      (a number decided in this track, recorded with its reason — Em-Cubed's
      Datalog surface uses a 5000 fact-line cap as a precedent for capping,
      not as a number to copy blindly). A query that exceeds either fails
      loudly with the limit named, never silently truncated.
- [ ] Trust boundary stated in the README and in code comments: v1 runs
      local, trusted models only. Prolog goals can perform I/O; this plan
      does not claim a sandbox it does not build. If a sandbox is wanted,
      that is a new track with its own design, not a flag added here.
- [ ] Verify: the rule library answers every sample query; a deliberately
      non-terminating rule (left-recursive test case) hits the timeout and
      reports it; translation round-trips exactly; the trust statement
      exists in the README.

## Track 4 — Creation: elicitation dialogue

The half ASKE Dialog does not have. A managed dialogue that ends in a model,
not a pipeline that runs once and stops.

- [ ] Dialogue manager as an explicit state machine (states, transitions,
      prompts), not a free-form loop. States for v1: eliciting classes,
      eliciting relations, eliciting instances, confirming. Each state has
      its prompts and its exit conditions written down before it is coded.
- [ ] Prompt shape, simplified from Em-Cubed's elicitation: decision
      questions ("what is this ontology about?"), competency questions
      ("what must it be able to answer?"), then confirmation ("here is what
      I understood — correct?"). Confirmation is mandatory before any
      assertion lands in the model.
- [ ] Mixed-initiative correction (the DARPA Communicator lesson): the user
      can amend an earlier answer mid-dialogue. The manager re-asks every
      confirmation affected by the amendment and retracts stale assertions —
      no assertion survives a correction to the answer it came from.
- [ ] Confirmed turns land in the model with provenance (dialog turn id,
      timestamp). The created model exports to the Track 1 formats (JSON and
      Dialog authoring form) so a created ontology is immediately usable as
      an imported model.
- [ ] Verify: a scripted elicitation session (fixed answers, no human)
      produces the expected model; a scripted mid-session correction
      propagates (changed answer, re-confirmation, updated model, zero stale
      assertions); unconfirmed content never reaches the model.

## Track 5 — Traversal: query dialogue

The conversational form of Track 2's queries. Same answers as batch mode,
reached by talking.

- [ ] Dialogue state tracked across turns: current focus entity and active
      constraints, visible to the user on request ("where am I in this
      dialog?"). The manager re-plans on constraint change: a changed
      constraint aborts the subdialogue it invalidates and resurrects the
      ones it does not — the Communicator lesson, applied to ontology
      traversal instead of travel planning.
- [ ] Multi-hop path queries return auditable paths (the GraphPathRAG shape):
      the chain of relations walked, not just the endpoint. A path answer
      names every intermediate entity.
- [ ] Explanatory follow-ups: after any answer, "how was this obtained?"
      returns the rule chain and the facts behind it. This is Track 2's
      explain query, working inside a live dialogue.
- [ ] Verify: a scripted traversal session with a mid-query constraint
      change returns the correct revised answers; every path answer names
      its intermediates; every explanation names its rules and facts; batch
      and dialogue answers agree on the same queries.

## Track 6 — Validation and integrity

An ontology that cannot be checked will rot. Validation runs on demand and
after elicitation, and reports violations with the offending assertions.

- [ ] Constraint checks for v1: domain/range on relations (a relation used
      outside its declared domain or range is a violation), disjointness (an
      entity asserted as two disjoint classes is a violation), and cycle
      detection on relations declared acyclic. Each violation names the
      assertions involved.
- [ ] Assumption checking (ASKE's Prolog role, generalized): a small library
      of checkable assumptions — "every X has a Y", "no orphan instances",
      "every relation has a declared domain and range" — run on demand and
      after every elicitation session. New assumptions are data (a check
      definition), not code changes, wherever that is achievable simply.
- [ ] Verify: a sample model with one planted violation per check type
      reports each violation with its assertions; a clean model passes all
      checks; assumption checks run after elicitation without being asked.

## Track 7 — Interfaces and export

What the future plugin will call, and what a human takes away. Kept small on
purpose: a Python API plus a CLI first, no server until a concrete need
appears.

- [ ] Machine API: Python functions (load a model from a source, run a query,
      return answers with explanations) plus JSON in/out for the same
      operations. This API is the contract the future plugin will be written
      against — its shape is reviewed as carefully as the seam, because
      changing it later breaks the plugin.
- [ ] Export: model to JSON, to DOT (graph rendering), and to a static HTML
      view. One traversal produces all three (the brain-harness export lesson:
      one derivation engine, several formats — but v1 ships three formats,
      not five). No export format is added without a named user of it.
- [ ] Verify: export then import returns the same answers (round-trip);
      the HTML view renders the sample model; the API's example calls run
      verbatim from the docs.

## Track 8 — Tests, CI, docs

The corpus is the demo, the tests are the evidence, and the docs must not
lie — all three are lessons carried over from the brain-harness rounds.

- [ ] Test corpus: one sample ontology plus dialog scripts (elicitation
      scripts, traversal scripts, batch `.dialog` files) with expected
      answers recorded alongside. The corpus doubles as the tutorial's
      worked example. Tests cover the parser, the reasoner, elicitation,
      traversal, and validation. No test ticks a plan box without asserting
      (the evidence rule applies to this plan's own verification too).
- [ ] CI: lint + test on the Track 0 Python floor. Coverage is measured, not
      enforced, until a baseline exists (the brain-harness lesson: measure
      before enforcing, so a new gate does not turn CI red all at once).
- [ ] Docs: README (what the engine is and is not, quickstart), language
      reference (the full `.dialog` syntax), tutorial (build an ontology by
      dialogue, then traverse it), architecture note (the seam, the trust
      boundary, the deferred list). Any count stated in docs is generated
      from the repo or absent — no hand-maintained counts (the stale-count
      failure mode from the brain-harness rounds).
- [ ] Verify: CI green; every example command in the docs runs verbatim
      (copy-paste test); no hand-maintained count appears in docs.

## Track 9 — Seam proof (NOT the plugin)

This track proves the plugin will be small. It does not build the plugin —
that step belongs to the user, once this engine exists.

- [ ] A vault-shaped JSON sample, hand-built and shaped like a brain-harness
      vault export (items plus typed edges), loads through the Track 1 seam
      and answers traversal queries. No brain-harness code is imported; the
      sample is data, not a dependency.
- [ ] A seam doc written for the plugin's author (the user): the one
      interface to implement, plus a mapping table (vault item becomes an
      entity, typed edge becomes a relation, item metadata becomes
      attributes, and whatever does not map, named honestly as not mapping).
- [ ] Dogfood note, recorded not executed: when the plugin is built, the
      brain-harness dock is the natural way to drive the harness from inside
      while testing the adapter (the user's suggestion). The dock is not
      used by this plan's build.
- [ ] Verify: the seam doc plus the sample pass review — acceptance is the
      user confirming the plugin can be implemented from the doc alone,
      recorded as a written decision.

## Track 10 — Deferred-by-design (do NOT build unless a limitation is hit)

Each item names the limitation that would un-defer it. Building any of these
upfront violates the user's simplicity maxim and this plan's scope.

- [ ] Full OWL2 DL reasoning. Un-defer if: a real model needs inferences
      triples plus the Track 3 rule library cannot express.
- [ ] Topos/continuous truth values, multi-agent consensus, federated
      registries (the Em-Cubed ontology core's heavier machinery). Un-defer
      if: a concrete multi-model or multi-author use case appears.
- [ ] Distributed execution, WASM/GPU surfaces. Un-defer if: a workload
      proves local execution too slow, measured not assumed.
- [ ] Eclipse IDE parity (a Dialog IDE plugin). Un-defer if: a user
      population needs IDE integration; the CLI/REPL is the v1 interface.
- [ ] Speech I/O (ASR/TTS). Un-defer if: a hands-free or telephony use case
      appears. Text dialogue is v1.
- [ ] A Datalog engine. Un-defer if: a fact-heavy workload proves Prolog too
      slow, measured not assumed. Prolog covers v1.
- [ ] Free-form natural language understanding (an LLM turning arbitrary
      prose into ontology content). Un-defer if: controlled language proves
      too restrictive for a real elicitation session. Controlled language is
      v1, and any LLM assistance is a separate, explicit decision — never a
      silent default.

## §11 — Verification backlog (confirm during the build, not from memory)

- [ ] ASKE TA1/TA2 repos: license terms and last-release state (2019), before
      adopting any grammar text, syntax, or documentation wording from them.
      If the license does not permit adoption, the fresh syntax in Track 0
      must not resemble it beyond the idea level — record which.
- [ ] SWI-Prolog packaging and PySWIP maintenance state on the target
      platforms for the Track 0 Python floor. If SWI-Prolog is unavailable
      somewhere the engine must run, the Track 0 fallback decision governs.
- [ ] Whether the fresh syntax should stay SADL-compatible for import.
      Decide on evidence: only if a real SADL corpus will actually be
      imported. Compatibility without a corpus is gold-plating.
- [ ] `skill_taxonomy.pl`'s runtime status in Em-Cubed (consulted at runtime
      or standalone artifact — unverified at plan time). If it is consulted,
      its loading path is a precedent for the seam; if standalone, it is only
      a shape reference. Do not assume either.
- [ ] Whether the future plugin should be a brain-harness plugin, a skill,
      or both. The user's later decision; this plan does not presume it, and
      Track 9's seam doc must not presume it either.

## Closing note

When this plan is executed, the deliverable is a repository containing a
working engine: import a model, create one by dialogue, traverse one by
dialogue, validate it, explain every answer, export it — with a seam clean
enough that the brain-harness plugin, built later by the user, is an adapter
and not a second engine. If any track's work contradicts this plan's design
principles, the principles win and the plan is amended in the open, not
quietly reinterpreted. That is how the Argon check and the Muse redraft check
stay honest.
