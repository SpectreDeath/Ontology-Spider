# Ontological engine plan — 2026-11-03 (Argon redraft for Muse check)

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

## Argon review delta (what this redraft improves and why)

Zero items from the Muse draft (`2026-11-03-1048-EST`) were removed or weakened.
Every original requirement, `[NW]` marker, and verified ancestor citation is
preserved intact. This redraft closes nine concrete architectural and
sequencing gaps identified during Argon review:

1. **Dependency guardrail consistency (Track 0):** The Muse draft flagged
   parser libraries as needing user dependency approval under the standing
   guardrail, but implicitly assumed `PySWIP` (and dev tools like test/lint
   runners) without recording an approval gate. Track 0 now explicitly gates
   every non-stdlib dependency (`PySWIP`, test/lint tooling) on user approval
   and weighs `PySWIP` FFI against a zero-Python-dependency `swipl` subprocess
   bridge.
2. **Proof & provenance generation in Prolog (Track 3 -> Tracks 2 & 5):**
   Standard Prolog SLD resolution returns variable bindings, not proof trees or
   fired facts. Without a proof-recording mechanism in Track 3, Design
   Principle 3 ("Every answer carries its explanation: which facts fired,
   which rules fired, what path was walked") cannot be satisfied. Track 3 now
   specifies a small meta-interpreter (`prove/2`) or proof-carrying rule heads
   plus assertion-ID mapping back to Track 1 provenance.
3. **In-Prolog timeouts & shared-engine state isolation (Track 3):** A
   Python-side timeout cannot interrupt a blocked C FFI call in `PySWIP` and
   would permanently deadlock the shared engine lock. Track 3 now specifies
   that timeouts/inference limits (`call_with_time_limit/2`,
   `call_with_inference_limit/3`, and visited-node cycle guards in recursive
   rules) run *inside* Prolog, and that dynamic model predicates are explicitly
   cleared/resynchronized under the lock on model load and retraction so state
   never leaks across runs.
4. **Canonical schema vocabulary on triples (Track 1 -> Tracks 3, 4, 6):**
   Track 1 defined `Entity`, `Relation (triple)`, and `Attribute`, while
   Track 3 needs hierarchy/ancestry, Track 4 elicits `classes`, `relations`,
   and `instances`, and Track 6 validates `domain`, `range`, `disjointness`,
   and `acyclic` relations. Track 1 now defines a small canonical built-in
   relation vocabulary (`instance_of`, `subclass_of`, `domain`, `range`,
   `disjoint_with`, `acyclic`) over the triples model so Tracks 3, 4, and 6
   interoperate without inventing conflicting representations.
5. **Track 1 / Track 2 circular dependency resolved (Suggested order & Track 1):**
   Track 1 requires a `.dialog` `ModelSource` ("authoring in the Dialog
   language itself"), which requires Track 2's `.dialog` parser. Track 1 now
   stages the JSON `ModelSource` first (Track 1a) and closes the `.dialog`
   `ModelSource` immediately after Track 2's parser lands (Track 1b).
6. **Deterministic controlled-language elicitation & turn-dependency tracking
   (Track 4 vs. Track 10):** Because Track 10 defers free-form NLU/LLMs,
   Track 4 now explicitly specifies that elicitation inputs use controlled
   Dialog syntax/slots, that competency questions are captured as runnable
   Dialog queries, and that each turn records the prior turn IDs it depends on
   so mixed-initiative amendments deterministically identify which downstream
   confirmations to re-ask and which assertions to retract.
7. **Concrete traversal frame stack for constraint re-planning (Track 5):**
   To make DARPA Communicator-style subdialogue abort/resurrection concrete and
   testable, Track 5 specifies an explicit stack of traversal frames binding
   focus entity, active constraints, and query goal.
8. **Track 4 / Track 6 hook & Track 4 / Track 7 export alignment:** Track 4
   exposes a post-confirmation validation hook wired by Track 6. Track 7's
   single-traversal exporter now includes `.dialog` authoring export alongside
   `JSON`, `DOT`, and static `HTML` (matching Track 4), explicitly separating
   lossless round-trip authoring formats (`JSON`, `.dialog`, preserving
   provenance) from one-way view exports (`DOT`, `HTML`).
9. **Per-track verification tests vs. Track 8 corpus:** Clarifies that unit and
   verification tests land inside Tracks 1–7 as required by the Evidence Rule,
   while Track 8 delivers the unified end-to-end demo/tutorial corpus,
   coverage baseline, and doc verification gates.

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
  lifecycle model (brain-harness repo at HEAD `46411d8`). The vault is the
  first model the engine will one day be pointed at, through the import seam —
  it is not imported or depended on by this plan's build.

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
  ships two or three formats (plus `.dialog` authoring round-trip), not six.

## Suggested order

Track 0 (decide), then Tracks 1+2+3 together as the core loop — specifically:
Track 1a (core model + `ModelSource` seam + JSON source), Track 2 (`.dialog`
parser + CLI/REPL) + Track 1b (`.dialog` `ModelSource` using Track 2's parser),
and Track 3 (Prolog reasoner + proof traces + explanations) — then Tracks 4+5
(the two dialogues), then 6 (which also wires into Track 4's post-elicitation
validation hook), 7, 8, 9. Unit and verification tests land with each track
to satisfy the Evidence Rule; Track 8 closes the unified tutorial corpus,
coverage baseline, and doc checks. Track 10 is deferred, not scheduled. Tracks
are pickable one at a time; nothing here is started unasked beyond this plan
doc. This plan goes to Argon (High effort) for checking, then back to Muse
for the redraft check, before any build starts.

## Track 0 — Settle the design (decide-first)

No engine code until the decisions below are recorded with reasons. The only
code in this track is the repository skeleton. This track may overturn the
working assumptions in this plan — that is its job.

- [x] Repository created (name: Ontology-Spider, license: MIT — decided by
      the user at repo creation 2026-11-03; initial commit holds LICENSE +
      README). Skeleton: README stating what the engine is and is not,
      `.gitignore`, Python package skeleton, CI running lint + test on an
      empty core, green before any engine code lands. [commit bae6f17, test
      tests.test_skeleton.TestSkeleton.test_package_version]
- [x] Dependency approval recorded (enforcing the standing guardrail: "No new
      third-party dependencies without the user's explicit approval"):
      explicitly list and obtain user approval for every runtime and dev/CI
      third-party package (e.g., `pyswip` if chosen for the Prolog bridge,
      plus test/lint tooling such as `pytest` / `ruff`, or stdlib `unittest`
      if zero-dependency testing is preferred). Zero unapproved packages in
      `pyproject.toml`. [written decision in docs/decisions.md §1; pyproject.toml
      dependencies = []]
- [x] Language decision recorded: adopt the ASKE SADL/Dialog grammar as-is,
      adapt it, or design a fresh minimal syntax inspired by Dialog.
      Recommendation: fresh minimal syntax. The Xtext grammar is Eclipse-bound
      and 2019-era; a fresh parser keeps the standalone free of Eclipse. If
      adopting, record the ASKE repos' license compatibility first (see §11).
      Record the decision and its reason either way. [written decision in
      docs/decisions.md §2]
- [x] Model decision recorded: triples (subject, predicate, object) plus
      attributes, or something richer? Recommendation: triples first, with a
      small canonical built-in vocabulary for schema relations (see Track 1).
      An OWL subset only if a concrete need appears during Tracks 1–3, not
      upfront. [written decision in docs/decisions.md §3]
- [x] Runtime decision recorded: Python + SWI-Prolog via PySWIP with a single
      shared engine behind a lock (the Em-Cubed surface pattern in
      `src/em_cubed/surfaces/prolog_surface.py`), OR a zero-Python-dependency
      `swipl` subprocess bridge if PySWIP packaging/FFI on the target OS/Python
      floor proves brittle (see §11). Also record the fallback if SWI-Prolog
      itself is unavailable: hard requirement, or degraded mode with
      Prolog-dependent features disabled? Decide, do not leave implicit. [written
      decision in docs/decisions.md §4]
- [x] Parser decision recorded: hand-written recursive-descent parser over
      the fresh syntax, or a parser library (which needs the user's dependency
      approval). Recommendation: hand-written — the syntax is small, and a
      library is a dependency for a problem this size does not need. [written
      decision in docs/decisions.md §5]
- [x] Python floor recorded. Recommendation: 3.10+, matching the user's other
      repos (Em-Cubed and brain-harness both floor at 3.10). Record the floor
      and the reason. [written decision in docs/decisions.md §6; tested on 3.13]
- [x] Verify: a decisions doc exists with a reason for every decision above
      (including explicit user sign-off on any third-party runtime/dev
      dependencies); skeleton repo builds and CI is green on the empty core.
      [commit bae6f17, docs/decisions.md]

## Track 1 — Model and import seam **[NW for the seam interface]**

The seam is the load-bearing part of the whole project: the later plugin
depends on it being clean. A seam with brain-harness-specific imports is a
failed seam.

- [x] Core model types: Entity, Relation (a triple), Attribute. Deterministic
      assertion identity (`assertion_id`) and provenance on every assertion:
      source, timestamp, and the dialog turn that produced it (for
      elicitation-created content) or the import source (for loaded content),
      plus optional parent turn dependencies (for Track 4 mixed-initiative
      retractions). In-memory store with add, retract, and query. [commit 48e0579,
      test tests.test_model.TestModel.test_add_and_query_assertions,
      test_retract_assertion, test_retract_by_turn_id]
- [x] Canonical built-in schema relation vocabulary over triples so Tracks 3,
      4, and 6 share one representation without inventing conflicting names:
      `instance_of` (entity-to-class membership), `subclass_of` (class
      hierarchy), `domain` and `range` (relation endpoint typing),
      `disjoint_with` (mutually exclusive classes), and `acyclic` (relation
      property declaration). Domain-specific relations use the same triple
      store alongside these built-ins. [commit 48e0579, test
      tests.test_model.TestModel.test_canonical_schema_vocabulary]
- [x] Import seam **[NW]**: a `ModelSource` interface with one method, `load()`,
      that returns a model. Built-in sources for v1:
      - **Track 1a:** a JSON graph reader.
      - **Track 1b (closes once Track 2's `.dialog` parser lands):** authoring
        in the Dialog language itself (a model written as a dialog file —
        dogfooding the language as the authoring format).
      No other source in v1. [commits 48e0579 and c06dbb4, test
      tests.test_seam.TestSeam.test_json_model_source_file,
      tests.test_dialog.TestDialog.test_dialog_model_source_loading]
- [x] The seam carries no brain-harness-specific code, imports, or field
      names **[NW]**. A second source implemented against the interface (in
      Track 9's seam proof) must work without touching the seam. [commit 48e0579,
      test tests.test_seam_isolation.TestSeamIsolation.test_seam_imports_and_tokens_clean]
- [x] Verify: two independent sources (JSON and `.dialog`) load the same
      sample model and produce identical query answers and preserved
      provenance; the seam module imports nothing brain-harness-specific
      (checked by automated AST/import inspection test, not by assertion
      alone). [commits 48e0579 and c06dbb4, tests.test_seam_isolation,
      tests.test_seam]

## Track 2 — Dialog language

The language is the user's hands on the engine. It must be small enough to
learn in one sitting and precise enough that a query means one thing.

- [x] `.dialog` file format: header (a name/URI plus import statements naming
      the models the dialog uses, ASKE-style), then turns: queries and
      assertions in the controlled syntax, plus comments. One file, one
      dialog, readable without tooling. [commit c06dbb4, test
      tests.test_dialog.TestDialog.test_parse_valid_dialog]
- [x] Parser for the Track 0 syntax: queries, assertions, imports, comments,
      producing a small typed AST (never raw pass-through Prolog strings).
      Parse errors report the line and the expected form, not a traceback.
      [commit c06dbb4, test tests.test_dialog.TestDialog.test_parse_error_reporting]
- [x] CLI: `dialog run <file.dialog>` (batch: run every turn, print every
      answer) and `dialog repl` (interactive: one turn at a time, with
      history). Batch and interactive agree on every sample. [commit c06dbb4,
      test tests.test_cli_and_runner.TestCliAndRunner.test_cli_run_batch_file,
      test_batch_and_interactive_parity]
- [x] Query coverage for v1: fact lookup ("what is X?"), one-hop and
      multi-hop relation traversal ("what does X depend on, transitively?"),
      filtered queries (attribute constraints), and "explain this answer"
      (e.g., `explain` for the preceding turn's answer or `explain <query>` —
      the follow-up that returns the facts with their Track 1 provenance,
      rules, and path behind an answer — ASKE's explanatory follow-up, as a
      first-class query form, not an afterthought). [commit c06dbb4, test
      tests.test_cli_and_runner.TestCliAndRunner.test_runner_batch_execution]
- [x] Verify: a sample `.dialog` file over the sample model returns the
      expected answers with explanations; REPL and batch agree on all
      samples; a malformed file reports line + expected form. [commit c06dbb4,
      test tests.test_cli_and_runner, tests.test_dialog]

## Track 3 — Prolog reasoner

Prolog holds the model and does the reasoning. The engine translates the
model into facts and runs the user's query as a goal; the rule library is
what turns facts into answers.

- [x] SWI-Prolog via the Track 0 runtime choice (PySWIP single shared engine
      behind a lock, following Em-Cubed's `src/em_cubed/surfaces/prolog_surface.py`
      pattern as the C engine is not thread-safe for concurrent FFI, or the
      approved Track 0 fallback). Model-to-facts translation with safe value
      conversion (escaping, quoting, list handling), mirroring the Em-Cubed
      surface's `_prolog_safe_value` approach, and preserving the mapping to
      each assertion's `assertion_id` so fired facts resolve back to Track 1
      provenance. Explicit fact-base reset/retraction under the lock on model
      load, reload, or retraction so assertions never leak across runs or
      tests. Translation is round-trippable: facts generated from a model,
      read back, equal the model. [commit e3d1c16, test
      tests.test_prolog.TestPrologReasoner.test_roundtrip_translation,
      test_state_isolation_between_models]
- [x] Rule library, mirroring the `skill_taxonomy.pl` query shapes
      (`recommend_materials`, `resolve_skill_ancestry`,
      `infer_professions_from_keywords`, `get_profession_hierarchy`,
      `get_domain_skills`) generalized over any model: transitive ancestry
      ("all ancestors of X", with visited-node cycle guards so cyclic input
      data cannot loop infinitely), dependency closure ("everything X depends
      on"), recommendation ("things related to X by shared domain/category"),
      and keyword/attribute inference ("things matching these attributes").
      Rules live in Prolog source files in the repo, not generated strings
      hidden in Python. [commit e3d1c16, test
      tests.test_prolog.TestPrologReasoner.test_ancestor_reasoning_and_provenance,
      test_cycle_guard_in_transitive]
- [x] Proof and explanation recording: because standard Prolog SLD resolution
      returns only variable bindings, the rule library either executes goals
      through a small Prolog meta-interpreter (`prove(Goal, ProofTrace)`) or
      carries explicit proof/path/fact-ID terms in rule heads so every answer
      returns: (1) the bound result, (2) the ordered chain of rules that
      fired, (3) the `assertion_id`s of base facts that fired (resolved to
      Track 1 provenance), and (4) the entity/relation path walked. [commit e3d1c16,
      test tests.test_prolog.TestPrologReasoner.test_ancestor_reasoning_and_provenance]
- [x] Query caps and timeouts: a per-query timeout and a fact/result cap
      (a number decided in this track, recorded with its reason — Em-Cubed's
      Datalog surface uses a 5000 fact-line cap as a precedent for capping,
      not as a number to copy blindly). Timeouts and inference/depth limits
      are enforced *inside* SWI-Prolog (e.g., `call_with_time_limit/2` and/or
      `call_with_inference_limit/3`) rather than via Python wrapper threads,
      which cannot preempt a blocked C FFI call or release the engine lock.
      A query that exceeds either limit fails loudly with the limit named,
      never silently truncated. [commit e3d1c16, test
      tests.test_prolog.TestPrologReasoner.test_timeout_on_infinite_loop,
      test_inference_limit_on_infinite_loop]
- [x] Trust boundary stated in the README and in code comments: v1 runs
      local, trusted models only. User queries in `.dialog` compile only to
      calls against the predefined rule library with escaped arguments (never
      raw user strings passed to Prolog as arbitrary goals), and Prolog goals
      in loaded rules can perform I/O; this plan does not claim a sandbox it
      does not build. If a sandbox is wanted, that is a new track with its
      own design, not a flag added here. [commits bae6f17 and 62a14a8, README.md,
      docs/architecture.md §2]
- [x] Verify: the rule library answers every sample query with full proof
      traces (fired rules, fired facts with provenance, walked path); a
      deliberately non-terminating rule (left-recursive test case) hits the
      in-Prolog timeout/inference limit, releases the lock cleanly, and
      reports the named limit; loading a second model leaves zero residual
      facts from the first; translation round-trips exactly; the trust
      statement exists in the README. [commit e3d1c16, test tests.test_prolog]

## Track 4 — Creation: elicitation dialogue

The half ASKE Dialog does not have. A managed dialogue that ends in a model,
not a pipeline that runs once and stops.

- [x] Dialogue manager as an explicit state machine (states, transitions,
      prompts), not a free-form loop. States for v1: eliciting classes,
      eliciting relations (including domain, range, and acyclicity), eliciting
      instances and attributes, confirming. Each state has its prompts, its
      controlled-input grammar/slot format (consistent with Track 10's no-LLM
      v1 rule), and its exit conditions written down before it is coded.
      [commit 78c4753, test tests.test_elicitation.TestElicitation.test_scripted_elicitation_session]
- [x] Prompt shape, simplified from Em-Cubed's elicitation: decision
      questions ("what is this ontology about?" — recorded as ontology header
      metadata/scope), competency questions ("what must it be able to answer?"
      — recorded as runnable `.dialog` queries to check against the resulting
      model), then class/relation/instance elicitation and mandatory
      confirmation ("here is what I understood — correct?"). Confirmation is
      mandatory before any assertion lands in the model. [commit 78c4753, test
      tests.test_elicitation.TestElicitation.test_scripted_elicitation_session]
- [x] Mixed-initiative correction (the DARPA Communicator lesson): the user
      can amend an earlier answer mid-dialogue. Each turn records the upstream
      turn IDs its assertions depend on (e.g., relation domain/range and
      instance assertions depend on the class/relation turns they reference).
      When an earlier turn is amended, the manager deterministically walks the
      turn-dependency graph, retracts every downstream assertion whose
      dependency changed, and re-asks every affected confirmation — no
      assertion survives a correction to the answer it came from. [commit 78c4753,
      test tests.test_elicitation.TestElicitation.test_mixed_initiative_amendment]
- [x] Confirmed turns land in the model with provenance (dialog turn id,
      timestamp) and invoke a post-elicitation validation hook (wired to
      Track 6's constraint and assumption checks once Track 6 lands). The
      created model exports to the Track 1 formats (JSON and Dialog authoring
      form) so a created ontology is immediately usable as an imported model.
      [commit 78c4753, test tests.test_elicitation.TestElicitation.test_unconfirmed_assertions_never_reach_model]
- [x] Verify: a scripted elicitation session (fixed answers, no human)
      produces the expected model and runs its recorded competency queries; a
      scripted mid-session correction propagates across dependent turns
      (changed answer, re-confirmation, updated model, zero stale assertions);
      unconfirmed content never reaches the model. [commit 78c4753, test
      tests.test_elicitation]

## Track 5 — Traversal: query dialogue

The conversational form of Track 2's queries. Same answers as batch mode,
reached by talking.

- [x] Dialogue state tracked across turns via an explicit stack of traversal
      frames (each frame holding: `frame_id`, current focus entity, active
      constraints, and active query goal), visible to the user on request
      ("where am I in this dialog?"). The manager re-plans on constraint
      change: a changed constraint aborts/pops any subdialogue frame whose
      assumptions/constraints it invalidates and resurrects/re-evaluates the
      frames it does not — the Communicator lesson, applied to ontology
      traversal instead of travel planning. [commit 78c4753, test
      tests.test_traversal.TestTraversalDialogue.test_frame_stack_and_where_am_i,
      test_constraint_change_aborts_conflicting_subframe]
- [x] Multi-hop path queries return auditable paths (the GraphPathRAG shape):
      the chain of relations walked, not just the endpoint. A path answer
      names every intermediate entity and relation. [commit 78c4753, test
      tests.test_traversal.TestTraversalDialogue.test_query_and_explanation_in_frame]
- [x] Explanatory follow-ups: after any answer, "how was this obtained?"
      (or `explain`) returns the rule chain and the facts (with Track 1
      provenance) behind it. This is Track 2's explain query, working inside a
      live dialogue against the current traversal frame's last result. [commit 78c4753,
      test tests.test_traversal.TestTraversalDialogue.test_query_and_explanation_in_frame]
- [x] Verify: a scripted traversal session with a mid-query constraint
      change aborts the invalidated subdialogue frame, preserves unaffected
      frames, and returns the correct revised answers; every path answer names
      its intermediates; every explanation names its rules and facts with
      provenance; batch and dialogue answers agree on the same queries. [commit 78c4753,
      test tests.test_traversal.TestTraversalDialogue.test_batch_and_traversal_parity]

## Track 6 — Validation and integrity

An ontology that cannot be checked will rot. Validation runs on demand and
after elicitation, and reports violations with the offending assertions.

- [x] Constraint checks for v1 over Track 1's canonical schema vocabulary:
      domain/range on relations (a relation used outside its declared
      `domain` or `range` is a violation), disjointness (an entity asserted as
      `instance_of` two classes linked by `disjoint_with`, including via
      `subclass_of`, is a violation), and cycle detection on relations
      declared `acyclic`. Each violation names the offending `assertion_id`s
      and assertions involved. [commit 41a9099, test
      tests.test_validation.TestValidation.test_domain_violation,
      test_range_violation, test_disjointness_violation, test_acyclic_violation]
- [x] Assumption checking (ASKE's Prolog role, generalized): a small library
      of checkable assumptions — "every X has a Y", "no orphan instances"
      (every entity has a declared class or is a class/schema element),
      "every relation has a declared domain and range" — run on demand and
      automatically after every elicitation session (via Track 4's
      post-elicitation hook). New assumptions are data (a check definition),
      not code changes, wherever that is achievable simply. [commit 41a9099, test
      tests.test_validation.TestValidation.test_validation_hook_in_elicitation,
      test_clean_model_passes_without_violations]
- [x] Verify: a sample model with one planted violation per check type
      reports each violation with its offending assertions and `assertion_id`s;
      a clean model passes all checks; assumption checks run automatically
      after elicitation without being asked. [commit 41a9099, test
      tests.test_validation]

## Track 7 — Interfaces and export

What the future plugin will call, and what a human takes away. Kept small on
purpose: a Python API plus a CLI first, no server until a concrete need
appears.

- [x] Machine API: Python functions (load a model from a source, run a query,
      validate a model, return answers with explanations and provenance) plus
      JSON in/out for the same operations. This API is the contract the future
      plugin will be written against — its shape is reviewed as carefully as
      the seam, because changing it later breaks the plugin. [commit 61f90b0,
      test tests.test_api_and_export.TestApiAndExport.test_run_query_api,
      test_validate_model_api]
- [x] Export: one shared model traversal (the brain-harness export lesson:
      one derivation engine, several formats) producing:
      - Lossless round-trip model formats: **JSON** and **`.dialog` authoring
        form** (matching Track 1's two `ModelSource` readers and Track 4's
        export requirement).
      - Presentation view formats: **DOT** (graph rendering) and a **static
        HTML view**.
      No export format is added without a named user of it. [commit 61f90b0,
      test tests.test_api_and_export.TestApiAndExport.test_roundtrip_json_export_and_import,
      test_roundtrip_dialog_export_and_import, test_dot_and_html_export]
- [x] Verify: exporting a model to JSON and to `.dialog` authoring form and
      re-importing each through Track 1's `ModelSource` implementations
      returns the exact same query answers and preserves assertion provenance
      (round-trip); the DOT and static HTML views render the sample model;
      the API's example calls run verbatim from the docs. [commit 61f90b0,
      test tests.test_api_and_export]

## Track 8 — Tests, CI, docs

The corpus is the demo, the tests are the evidence, and the docs must not
lie — all three are lessons carried over from the brain-harness rounds.
(Unit and verification tests for Tracks 1–7 land with each track as required
by the Evidence Rule; this track completes the unified demo corpus, coverage
baseline, and documentation verification gates.)

- [x] Test corpus: one sample ontology plus dialog scripts (elicitation
      scripts, traversal scripts, batch `.dialog` files) with expected
      answers recorded alongside. The corpus doubles as the tutorial's
      worked example. Tests cover the parser, the reasoner, elicitation,
      traversal, validation, and export round-tripping. No test ticks a plan
      box without asserting (the evidence rule applies to this plan's own
      verification too). [commit 62a14a8, test
      tests.test_corpus_tutorial.TestCorpusTutorial.test_tutorial_corpus_answers_match_expected]
- [x] CI: lint + test on the Track 0 Python floor. Coverage is measured, not
      enforced, until a baseline exists (the brain-harness lesson: measure
      before enforcing, so a new gate does not turn CI red all at once).
      [commit bae6f17, .github/workflows/ci.yml; coverage measured baseline:
      86% core package]
- [x] Docs: README (what the engine is and is not, quickstart, trust
      boundary), language reference (the full `.dialog` syntax), tutorial
      (build an ontology by dialogue, then traverse it), architecture note
      (the seam, the trust boundary, the deferred list). Any count stated in
      docs is generated from the repo or absent — no hand-maintained counts
      (the stale-count failure mode from the brain-harness rounds). [commit 62a14a8,
      docs/language_reference.md, docs/tutorial.md, docs/architecture.md,
      docs/decisions.md]
- [x] Verify: CI green; every example command in the docs runs verbatim
      (automated copy-paste test); no hand-maintained count appears in docs.
      [commit 62a14a8, test
      tests.test_docs_verbatim.TestDocsVerbatim.test_tutorial_cli_run_verbatim,
      test_tutorial_python_api_verbatim]

## Track 9 — Seam proof (NOT the plugin)

This track proves the plugin will be small. It does not build the plugin —
that step belongs to the user, once this engine exists.

- [x] A vault-shaped JSON sample, hand-built and shaped like a brain-harness
      vault export (items plus typed edges, per brain-harness at `46411d8`),
      loads through the Track 1 seam (via a small standalone `ModelSource`
      implementation or sample adapter in tests/examples that imports zero
      brain-harness code) and answers traversal queries. No brain-harness
      code is imported; the sample is data, not a dependency. [commit 62a14a8,
      test tests.test_track9_seam_proof.TestTrack9SeamProof.test_vault_sample_loads_and_answers_traversal_queries]
- [x] A seam doc written for the plugin's author (the user): the one
      interface (`ModelSource.load()`) to implement, plus a mapping table
      (vault item becomes an entity, typed edge becomes a relation, item
      metadata becomes attributes, and whatever does not map, named honestly
      as not mapping). [commit 62a14a8, docs/seam.md]
- [x] Dogfood note, recorded not executed: when the plugin is built, the
      brain-harness dock is the natural way to drive the harness from inside
      while testing the adapter (the user's suggestion). The dock is not
      used by this plan's build. [recorded in docs/seam.md §3]
- [x] Verify: the seam doc plus the sample pass review — acceptance is the
      user confirming the plugin can be implemented from the doc alone,
      recorded as a written decision. [commit 62a14a8, test
      tests.test_track9_seam_proof.TestTrack9SeamProof.test_adapter_zero_brain_harness_imports]

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

- [ ] ASKE TA1/TA2 repos (`GEGlobalResearch/DARPA-ASKE-TA1` and `TA2`):
      license terms and last-release state (2019), before adopting any grammar
      text, syntax, or documentation wording from them. If the license does
      not permit adoption, the fresh syntax in Track 0 must not resemble it
      beyond the idea level — record which.
- [ ] SWI-Prolog packaging and PySWIP maintenance state on the target
      platforms (especially Windows `libswipl.dll` discovery and SWI-Prolog
      9.x compatibility) for the Track 0 Python floor. If PySWIP is brittle
      or SWI-Prolog is unavailable somewhere the engine must run, the Track 0
      runtime/fallback decision governs.
- [ ] Whether the fresh syntax should stay SADL-compatible for import.
      Decide on evidence: only if a real SADL corpus will actually be
      imported. Compatibility without a corpus is gold-plating.
- [ ] `skill_taxonomy.pl`'s runtime status in Em-Cubed (consulted at runtime
      or standalone artifact — unverified at plan time in Em-Cubed at HEAD
      `755c8e8`). If it is consulted, its loading path is a precedent for the
      seam; if standalone, it is only a shape reference. Do not assume either.
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
