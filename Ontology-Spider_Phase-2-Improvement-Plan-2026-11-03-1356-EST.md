# Ontology-Spider — Phase 2 Engineering Improvement Plan (v0.2.0)

**Target Repository:** `d:\GitHub\projects\Ontology-Spider`  
**Baseline Commit:** `a420531` (`v0.1.0` — Tracks 0–9 green across 8/8 CI matrix jobs)  
**Guiding Maxim:** *"Simplicity is the hallmark of engineering, not complexity."*

---

## 0. Context & Guardrails for the Coding Agent

`Ontology-Spider` v0.1.0 established the core architecture: a standalone in-memory `OntologyModel` with provenance, a SWI-Prolog subprocess reasoner (`src/ontology_spider/prolog/`), the `.dialog` DSL (`dialog.py`, `dialog_runner.py`), a four-stage elicitation state machine (`elicitation.py`), a DARPA Communicator-style frame stack (`traversal.py`), integrity validation (`validation.py`), and four single-traversal exporters (`export.py`).

An engineering audit of v0.1.0 identified specific shortcuts and completeness gaps between the implementation and the architectural specification. This plan specifies **7 self-contained, test-gated tracks** to close every gap and bring the engine to **v0.2.0**.

### Hard Constraints (Must Not Be Violated)
1. **Zero Third-Party Runtime Dependencies**: Keep `dependencies = []` in `pyproject.toml`. Use only the Python standard library (`>=3.10`) and the external `swipl` binary.
2. **Respect Track 10 Non-Goals**: Do **not** add web servers, database backends, `rdflib`/`owlready2`, LLM API clients, or heavy parser frameworks.
3. **Preserve Public API Compatibility**: All existing tests (`pytest`) and benchmark scripts (`examples/drones.dialog`) must continue to pass without regression.
4. **Test-Gated Execution**: Complete the tracks in order (`Track 1` → `Track 7`). Do not mark a track complete until its verification command passes.

---

## Track 1: Elicitation Turn-Dependency Graph, Amendments & Extended Grammar

**Target File:** `src/ontology_spider/elicitation.py`  
**Test File:** `tests/test_elicitation.py`

### Problem Statement
1. `ElicitedTurn.depends_on_turn_ids` (line 42) is declared on the dataclass and checked during `amend_turn()` (lines 308–316), **but it is never populated** when class, relation, or instance turns are created.
2. `amend_turn(turn_id, new_input)` retracts the target turn's assertions, but ignores `new_input` (never parses or applies it) and does not re-prompt the user to confirm invalidated downstream turns.
3. `_handle_classes` only supports `<child> subclass_of <parent>` (missing `<c1> disjoint_with <c2>`), and `_handle_instances` does not parse trailing bracketed attributes `[k=v, ...]`.

### Implementation Steps
1. **Track Symbol-to-Turn Provenance in `ElicitationManager`**:
   - Add `self._symbol_turn_map: dict[str, str] = {}` mapping each elicited class ID or relation predicate to the `turn_id` that first introduced it.
   - When `_stage_turn(...)` creates a turn, compute `depends_on_turn_ids: list[str]` by looking up any referenced classes (`parent`, `disjoint` target, `domain` class, `range` class, `instance_of` class) and relations (`predicate`) in `self._symbol_turn_map`.
   - When a turn is confirmed (`_confirm_pending()`), register its newly introduced class or relation symbols in `self._symbol_turn_map`.
2. **Support `disjoint_with` in `_handle_classes` (lines 126–163)**:
   - Accept `<c1> disjoint_with <c2>` in addition to `<child> subclass_of <parent>`.
   - Stage a turn with ` staged_assertions=[(c1, DISJOINT_WITH, c2, {})]`, recording any upstream `turn_id` for `c1` or `c2` in `depends_on_turn_ids`.
3. **Support Bracketed Attributes `[k=v, ...]` in `_handle_instances` (lines 222–261)**:
   - Reuse `_parse_attributes` from `ontology_spider.dialog` (or parse optional trailing `[...]`).
   - For `<inst> instance_of <Class> [k1=v1, ...]`: attach parsed attributes to the `<inst>` entity when confirmed (update `ElicitedTurn.staged_entities` from `list[str]` to `list[tuple[str, dict[str, Any]]]` or store `entity_attributes: dict[str, dict[str, Any]]` on `ElicitedTurn`).
   - For `<subj> <rel> <obj> [k1=v1, ...]`: pass the parsed attributes dict into the 4th element of the `staged_assertions` tuple `(subj, rel, obj, attrs)`.
4. **Full Amendment & Downstream Re-Confirmation Flow in `amend_turn(turn_id, new_input)`**:
   - Locate `target = self.turns[turn_id]`.
   - Find all transitively dependent turns (`invalidated: list[ElicitedTurn]`) by traversing `depends_on_turn_ids` in turn order.
   - Retract assertions from `self.model` for `target` and all `invalidated` turns (`self.model.retract_by_turn(...)`).
   - Parse `new_input` using the stage handler corresponding to `target.stage` (`ELICIT_CLASSES`, `ELICIT_RELATIONS`, or `ELICIT_INSTANCES`), keeping the same `turn_id` (or replacing `target` in-place) and immediately committing its new entities/assertions to `self.model`.
   - Add `self.pending_reconfirmations: list[ElicitedTurn] = []` on `ElicitationManager`. Populate it with the `invalidated` downstream turns.
   - While `self.pending_reconfirmations` is non-empty, `prompt()` and `handle_input()` should ask the user to confirm (`yes`) or drop/amend (`no`) the next invalidated downstream turn before returning to normal stage progression.

### Verification
- Run `pytest tests/test_elicitation.py -v`.
- Add tests verifying:
  - `depends_on_turn_ids` links an instance turn → relation turn → class turn.
  - Calling `amend_turn("turn_1", "rover subclass_of ground_robot")` updates `turn_1` in the model, invalidates dependent relation/instance turns, and queues them in `pending_reconfirmations`.
  - Confirming the re-confirmation re-asserts valid downstream turns into `model`.
  - `<c1> disjoint_with <c2>` and `<inst> instance_of <Class> [payload_kg=5]` work end-to-end in elicitation.

---

## Track 2: Lossless `.dialog` & Prolog Fact Round-Tripping

**Target Files:**
- `src/ontology_spider/dialog.py`
- `src/ontology_spider/dialog_runner.py`
- `src/ontology_spider/seam.py`
- `src/ontology_spider/export.py`
- `src/ontology_spider/prolog/translator.py`

**Test Files:** `tests/test_dialog_parser.py`, `tests/test_translator.py`, `tests/test_export_and_api.py`

### Problem Statement
1. `export.to_dialog()` writes entity attributes as `# Entity <id> [k=v]` comments, and drops `assertion_id` and `Provenance` (`source`, `turn_id`), so `DialogModelSource(to_dialog(model)).load()` loses entity attributes and generates new assertion IDs.
2. `prolog_facts_to_model()` in `src/ontology_spider/prolog/translator.py` (lines 68–91) only parses `triple/4` lines and ignores `attribute/3` lines, losing all entity and assertion attributes on Prolog round-trip.

### Implementation Steps
1. **Add First-Class `entity` Declarations to `.dialog` (`dialog.py`, `dialog_runner.py`, `seam.py`)**:
   - In `dialog.py`, add dataclass `DialogEntityDecl`:
     ```python
     @dataclass(frozen=True)
     class DialogEntityDecl:
         entity_id: str
         attributes: dict[str, Any] = field(default_factory=dict)
         line_num: int = 0
     ```
   - Include `DialogEntityDecl` in `DialogStatement` union.
   - In `parse_dialog()`, parse `entity <id> [k=v, ...]` (and `entity <id>`) into `DialogEntityDecl`.
   - In `DialogSession.execute_statement()` and `DialogModelSource._load_file()`, handle `DialogEntityDecl` by calling `model.add_entity(stmt.entity_id, name=stmt.attributes.get("name"), attributes={k: v for k, v in stmt.attributes.items() if k != "name"})` (or preserving all attributes on `Entity.attributes`).
2. **Preserve Assertion Provenance Metadata in `to_dialog()` and `DialogModelSource` / `DialogSession`**:
   - In `export.to_dialog(model)`:
     - Emit `entity <ent.id> [<attrs>]` for every entity in `model.entities.values()` that has non-empty `attributes` or `name`.
     - For each assertion in `model.assertions.values()`, include reserved metadata keys in the attribute bracket when exporting: `_id=<assertion_id>`, `_source=<provenance.source>`, and (if set) `_turn=<provenance.turn_id>`.
   - In `DialogModelSource._load_file()` and `DialogSession.execute_statement()`:
     - When processing `DialogAssertion`, extract optional `_id`, `_source`, and `_turn` from `stmt.attributes` (removing them from the user-facing `attributes` dict).
     - Pass `assertion_id=_id`, `source=_source or default_source`, and `turn_id=_turn` to `model.add_assertion(...)`.
3. **Parse `attribute/3` in `prolog_facts_to_model()` (`src/ontology_spider/prolog/translator.py`)**:
   - Add regex `_ATTR_RE = re.compile(r"^attribute\((.+),\s*(.+),\s*(.+)\)\.$")`.
   - Add a helper `_parse_prolog_val(raw: str) -> Any` that unquotes `'...'` atoms or parses numeric literals (`int`, `float`).
   - In `prolog_facts_to_model()`, after collecting `triple/4` assertions, apply `attribute(TargetId, Key, Val).`:
     - If `TargetId` is in `model.assertions`, set `model.assertions[TargetId].attributes[Key] = Val`.
     - Otherwise, ensure `TargetId` exists in `model.entities` and set `model.entities[TargetId].attributes[Key] = Val`.

### Verification
- Run `pytest tests/test_dialog_parser.py tests/test_translator.py tests/test_export_and_api.py -v`.
- Add round-trip tests asserting:
  - `DialogModelSource(to_dialog(model)).load().to_dict()` matches `model.to_dict()` across entities, entity attributes, assertions, `assertion_id`s, assertion attributes, and provenance (`source`, `turn_id`).
  - `prolog_facts_to_model(model_to_prolog_facts(model))` preserves both entity attributes and assertion attributes.

---

## Track 3: Frame-Constraint Filtering, `recommend` Queries & Inline `explain <query>`

**Target Files:**
- `src/ontology_spider/dialog.py`
- `src/ontology_spider/dialog_runner.py`
- `src/ontology_spider/traversal.py`

**Test Files:** `tests/test_dialog_parser.py`, `tests/test_traversal.py`

### Problem Statement
1. `src/ontology_spider/prolog/rules.pl` defines `recommend(Class, ReqKey, ReqVal, Candidate, Explanation)` and `PrologReasoner` supports `goal_type="recommend"`, **but `.dialog` has no query syntax wired to `recommend`**.
2. `explain <query>` is specified in Track 2 of the architecture plan, but `dialog.py` ignores everything after `explain` and `dialog_runner.py` only explains `self.last_query_result`.
3. `TraversalDialogueManager.query()` in `src/ontology_spider/traversal.py` inherits `focus_entity` from the active frame, **but ignores `self.current_frame.active_constraints`** when returning query answers.

### Implementation Steps
1. **Add `recommend` Query Grammar to `dialog.py` and `dialog_runner.py`**:
   - In `dialog.py` (`_parse_query`), match:
     - `recommend <Class> where <attr> = <val>` → `DialogQuery(kind="recommend", object=cls_name, filter_key=attr, filter_val=val, raw_text=line, line_num=line_num)`
     - `recommend <Class>` (without `where`, useful inside a constrained traversal frame) → `DialogQuery(kind="recommend", object=cls_name, raw_text=line, line_num=line_num)`
   - In `dialog_runner.py` (`_execute_query`), handle `query.kind == "recommend"`:
     - If `query.filter_key` and `query.filter_val` are provided, call `self.reasoner.query(self.model, "recommend", class_name=query.object, req_key=query.filter_key, req_val=self._coerce_val(query.filter_val))`.
     - If `query.filter_key` is omitted, query `instances_of` `query.object`.
2. **Support Inline `explain <query>` (`dialog.py` & `dialog_runner.py`)**:
   - Add `subquery: Optional[DialogQuery] = None` to `DialogQuery`.
   - In `_parse_query()`, when `line.startswith("explain ")`:
     - Extract `rest = line[len("explain"):].strip()`.
     - If `rest` is non-empty, recursively call `_parse_query(rest, line_num)` and attach it as `subquery`.
   - In `DialogSession._execute_query()`, when `query.kind == "explain"`:
     - If `query.subquery is not None`, execute `self._execute_query(query.subquery)` first, set `self.last_query_result`, and then format and return the explanation for those answers.
3. **Apply `active_constraints` in `TraversalDialogueManager.query()` (`src/ontology_spider/traversal.py`)**:
   - In `TraversalDialogueManager.query()`, after executing `stmt` (or when rewriting a `recommend <Class>` query with no explicit `where` clause):
     - If `self.current_frame.active_constraints` is non-empty, filter `result.answers` for queries whose answers represent candidate entities (`instances`, `descendants`, `recommend`, `filter`), keeping only answers where the entity in `self.model.entities` satisfies all `k=v` pairs in `self.current_frame.active_constraints` ( checking both entity attributes and assertion attributes on the entity's `instance_of` assertions).
     - Append `"filtered_by_frame_constraints"` to `ans.explanation.rules_fired` when frame constraints narrow the answer set.

### Verification
- Run `pytest tests/test_dialog_parser.py tests/test_traversal.py -v`.
- Verify:
  - `recommend delivery_drone where payload_kg = 5` invokes Prolog `recommend/5` and returns `quad_x1` with rule trace `["recommend", "instance_of_transitive", ..., "match_attribute"]`.
  - `explain ancestors of cargo_drone_1` works on a fresh session without requiring a separate preceding query turn.
  - Setting `constrain payload_kg=5` in `TraversalDialogueManager` filters subsequent `instances of delivery_drone` or `recommend delivery_drone` queries in that frame.

---

## Track 4: Reasoner `max_results` Cap, Fact Caching & Degraded Mode

**Target Files:**
- `src/ontology_spider/model.py`
- `src/ontology_spider/prolog/reasoner.py`
- `src/ontology_spider/dialog_runner.py`

**Test Files:** `tests/test_reasoner.py`, `tests/test_traversal.py`

### Problem Statement
1. `PrologReasoner` enforces `max_facts` prior to query execution, but does not enforce a `max_results` cap on returned solutions (Track 3 requires both a timeout and a result/fact cap that fails loudly when exceeded).
2. `PrologReasoner` re-translates the entire `OntologyModel` to Prolog text on every query even when the model has not mutated.
3. When `swipl` is unavailable on a host, `DialogSession` raises `PrologUnavailableError` on all queries instead of providing a degraded-mode fallback with a clear diagnostic.

### Implementation Steps
1. **Add Mutation Version Counter to `OntologyModel` (`src/ontology_spider/model.py`)**:
   - Add `self._version: int = 0` to `OntologyModel.__init__`.
   - Increment `self._version += 1` whenever `add_entity`, `add_assertion`, `retract_assertion`, or `retract_by_turn` mutates the model.
   - Expose `@property def version(self) -> int: return self._version`.
2. **Cache Translated Facts & Enforce `max_results` in `PrologReasoner` (`src/ontology_spider/prolog/reasoner.py`)**:
   - Add `max_results: int = 1000` to `PrologReasoner.__init__`.
   - Cache `(id(model), model.version) -> str` for `model_to_prolog_facts(model)` so repeated queries against an unchanged model skip re-translation.
   - In `_execute_under_lock`, after parsing `raw_results = payload.get("results", [])`, check:
     ```python
     if len(raw_results) > self.max_results:
         raise PrologExecutionError(
             f"Query result count ({len(raw_results)}) exceeds max_results cap ({self.max_results})."
         )
     ```
3. **Degraded-Mode Fallback in `DialogSession` (`src/ontology_spider/dialog_runner.py`)**:
   - Add `allow_degraded_fallback: bool = True` to `DialogSession.__init__`.
   - In `_execute_query()`, if `not self.reasoner.is_available()`:
     - If `not self.allow_degraded_fallback`, raise `PrologUnavailableError`.
     - Otherwise, execute a clean Python graph traversal fallback for `ancestors`, `descendants`, `instances`, `transitive`, `pattern`, and `recommend`, populating `ReasonerExplanation(rules_fired=["degraded_python_fallback"], path=..., fact_ids=..., provenance_assertions=...)` and prefixing `summary_text` with `[Degraded Mode: swipl unavailable] `.

### Verification
- Run `pytest tests/test_reasoner.py -v`.
- Add unit tests verifying:
  - Setting `max_results=2` raises `PrologExecutionError` when a query matches 3 facts.
  - Fact translation cache hits when `model.version` is unchanged and invalidates immediately after `model.add_assertion(...)`.
  - When `PrologReasoner(swipl_path="nonexistent_swipl")` is passed to `DialogSession`, queries succeed in degraded mode with `"degraded_python_fallback"` in `rules_fired` and `[Degraded Mode: swipl unavailable]` in `summary_text`.

---

## Track 5: Validator Completeness — Intrinsic `subclass_of` Acyclicity, Multi-Cycle Detection & Class Disjointness Provenance

**Target File:** `src/ontology_spider/validation.py`  
**Test File:** `tests/test_validation.py`

### Problem Statement
1. Cycle detection in `OntologyValidator.validate()` (lines 171–216) only checks predicates with an explicit `assert <pred> acyclic true` assertion; `subclass_of` cycles are missed unless manually declared acyclic.
2. Cycle detection breaks after the first cycle (`break` on line 215), missing multiple disconnected cycles in the same relation.
3. Disjointness checks (lines 148–170) only look up `INSTANCE_OF` assertions for `offending_assertion_ids`, omitting `SUBCLASS_OF` assertion IDs along the inheritance chain.

### Implementation Steps
1. **Treat `SUBCLASS_OF` as Intrinsically Acyclic**:
   - Initialize `acyclic_preds = {SUBCLASS_OF} | {a.relation.subject for a in model.query(predicate=ACYCLIC) if a.relation.object.lower() in ("true", "yes", "1")}`.
2. **Detect All Independent Cycles per Acyclic Predicate**:
   - Remove the early `break` at line 215.
   - Track `seen_cycle_sets: set[frozenset[str]] = set()` (using the `frozenset` of `cycle_aids`). For each `start_node`, if `dfs` finds a cycle whose `frozenset(cycle_aids)` is not yet in `seen_cycle_sets`, record the `Violation` and add `frozenset(cycle_aids)` to `seen_cycle_sets`.
3. **Include Inheritance Chain Assertion IDs in Disjointness Violations**:
   - Write a small helper `get_type_assertion_ids(entity_id: str, target_classes: set[str]) -> list[str]` that collects both `INSTANCE_OF` and `SUBCLASS_OF` assertion IDs connecting `entity_id` to `c1` and `c2`.
   - Include those assertion IDs in `offending_assertion_ids` for `disjointness_violation`.

### Verification
- Run `pytest tests/test_validation.py -v`.
- Add unit tests verifying:
  - A `subclass_of` cycle (`a subclass_of b`, `b subclass_of a`) triggers a `cycle_violation` without needing `assert subclass_of acyclic true`.
  - Two separate cycles in the same relation both get reported.
  - A class hierarchy where `amphibious_drone subclass_of air_vehicle` and `amphibious_drone subclass_of ground_vehicle` (with `air_vehicle disjoint_with ground_vehicle`) reports a `disjointness_violation` whose `offending_assertion_ids` includes the `subclass_of` assertions.

---

## Track 6: CLI Completeness (`validate`, `export`, `elicit`) & Frame-Aware REPL

**Target File:** `src/ontology_spider/cli.py`  
**Test File:** `tests/test_cli.py` (new)

### Problem Statement
`src/ontology_spider/cli.py` currently only exposes `dialog run` and a minimal `dialog repl` wrapping `DialogSession` (missing frame stack commands, validation, export, and elicitation).

### Implementation Steps
1. **Add `dialog validate <file>` Subcommand**:
   - Load the model via `api.load_model(file_path)`.
   - Run `OntologyValidator().validate(model)`.
   - If clean, print `Validation passed: 0 violations.` and return exit code `0`.
   - If violations exist, print each `v.summary()` and return exit code `1`.
2. **Add `dialog export <file> --format {json,dialog,dot,html} [-o <output>]` Subcommand**:
   - Load the model via `api.load_model(file_path)`.
   - Export via `api.export_model(model, format=args.format)`.
   - Write to `args.output` if `-o`/`--output` is specified, else print to `stdout`. Return `0`.
3. **Add `dialog elicit [-o <output.dialog>]` Subcommand**:
   - Instantiate `ElicitationManager(validator_hook=validate_model_hook)`.
   - Loop printing `manager.prompt()`, reading `input("elicit> ")`, and printing `manager.handle_input(line)` until `manager.stage == ElicitationStage.COMPLETE` or EOF/`exit`.
   - If `-o`/`--output` is provided, write `export_model(manager.model, format="dialog")` to that path.
4. **Upgrade `dialog repl` to Use `TraversalDialogueManager`**:
   - Support optional `--file <path>` on `dialog repl` to preload an ontology.
   - Inside `run_repl()`, support frame-stack and inspection commands alongside standard `.dialog` statements:
     - `where am i` / `where am i?` → prints `traversal.where_am_i()`
     - `focus <entity_id>` → prints `traversal.set_focus(entity_id)`
     - `constrain <key>=<val>` → prints `traversal.change_constraint(key, val)`
     - `validate` → runs `OntologyValidator().validate(traversal.model)` and prints results
     - `export <json|dialog|dot|html>` → prints exported model

### Verification
- Create `tests/test_cli.py` testing `main(["run", ...])`, `main(["validate", ...])`, `main(["export", ...])`, `main(["elicit", ...])` (with monkeypatched `input`), and `main(["repl", ...])` (with monkeypatched `input` exercising `focus`, `constrain`, `where am i`, `validate`, and queries).
- Run `pytest tests/test_cli.py -v`.

---

## Track 7: Documentation Sync, Version Bump & Full Verification Suite

**Target Files:**
- `pyproject.toml`
- `src/ontology_spider/__init__.py`
- `docs/language_reference.md`
- `docs/tutorial.md`

### Implementation Steps
1. Bump version from `0.1.0` to `0.2.0` in `pyproject.toml` and `src/ontology_spider/__init__.py`.
2. Update `docs/language_reference.md` to document:
   - `entity <id> [k=v, ...]` declarations
   - `recommend <Class> [where <attr> = <val>]` queries
   - Inline `explain <query>` syntax
   - CLI subcommands: `dialog run`, `dialog repl`, `dialog validate`, `dialog export`, and `dialog elicit`.
3. Update `docs/tutorial.md` with examples of `dialog validate`, `dialog export`, and frame-constrained `recommend` queries.
4. Run the full verification suite:
   ```powershell
   pytest --cov=ontology_spider --cov-report=term-missing
   ```
   Confirm 100% of tests pass and overall package test coverage is **>= 90%**.
