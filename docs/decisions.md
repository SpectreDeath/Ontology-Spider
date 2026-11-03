# Track 0 — Architectural & Design Decisions

This document records the foundational decisions for the `Ontology-Spider` engine as mandated by Track 0 of the development plan. Every decision is grounded in concrete technical rationale, simplicity, and adherence to user guardrails.

---

## 1. Third-Party Dependency Approval & Guardrail

- **Decision**: Zero third-party runtime dependencies. The engine core is implemented entirely in standard library Python (`dataclasses`, `typing`, `json`, `subprocess`, `pathlib`, `argparse`). Testing and test execution are handled using stdlib `unittest`.
- **Status on Third-Party Packages**:
  - `pyproject.toml` lists `dependencies = []`.
  - Zero unapproved packages are installed or required.
  - If third-party dev tools (such as `pytest` or `ruff`) or FFI bindings (`pyswip`) are considered in the future, they require explicit written approval from the user before being added to dependencies.
- **Rationale**: Strictly obeys the user's standing guardrail: *"No new third-party dependencies without the user's explicit approval"*. Python's standard library provides all necessary primitives for data structures, serialization, subprocess orchestration, and test execution.

---

## 2. Language Grammar: Fresh Minimal Syntax vs. ASKE SADL/Dialog Port

- **Decision**: Design a fresh minimal `.dialog` syntax inspired by the concepts of ASKE Dialog, rather than porting the Eclipse Xtext SADL grammar directly.
- **Rationale**:
  1. The original ASKE Dialog was built as Eclipse plugins (`com.ge.research.sadl.darpa.aske.dialog.parent`) on Java 8 and Eclipse 2018-12. Porting or retaining the Xtext grammar introduces substantial Eclipse-era baggage without modern benefits.
  2. A fresh, human-readable, line/block-oriented syntax provides complete control over error messages (precise line numbers and token expectations instead of opaque parse stack traces).
  3. Avoids license entanglements while retaining the foundational dialogue model: header with model imports, assertions, conversational queries, and explanatory follow-ups.

---

## 3. Data Model: Semantic Triples + Canonical Built-in Vocabulary

- **Decision**: Triples `(subject, predicate, object)` + key-value attributes on entities and assertions, augmented with a canonical built-in schema relation vocabulary:
  - `instance_of`: Type membership linking an instance entity to a class entity.
  - `subclass_of`: Taxonomic hierarchy linking a subclass to a superclass.
  - `domain`: Restricts the subject class of a relation.
  - `range`: Restricts the object class/type of a relation.
  - `disjoint_with`: Declares mutual exclusivity between classes.
  - `acyclic`: Declares that a relation must not contain directed cycles.
- **Provenance**: Every assertion carries an immutable `assertion_id`, `source`, `timestamp`, `turn_id`, and optional `parent_turn_ids` (to support mixed-initiative retraction graphs).
- **Rationale**: Full OWL2 DL reasoning is deferred to Track 10. Triples plus this canonical built-in vocabulary cleanly satisfy all requirements of Tracks 1, 3, 4, 5, and 6 without the computational overhead or implementation complexity of description logic reasoners.

---

## 4. Reasoner Runtime & SWI-Prolog Bridge

- **Decision**: SWI-Prolog via a zero-Python-dependency `swipl` CLI/subprocess bridge with in-Prolog timeouts and process lifecycle management.
- **Comparison**:
  - `PySWIP` uses C FFI (`ctypes`) binding against `libswipl`. On Windows and Python 3.13 with SWI-Prolog 10.x, PySWIP is notoriously brittle (DLL lookup failures, thread safety lockouts, inability to cleanly interrupt C execution from Python threads).
  - A dedicated `swipl` subprocess bridge communicates via standard streams / batch scripts. It requires zero pip dependencies, handles SWI-Prolog 10.0.2 out of the box, cleanly enforces timeouts using SWI-Prolog's internal `call_with_time_limit/2`, and prevents engine memory pollution by ensuring dynamic facts are explicitly scoped or run in isolated invocations.
- **Fallback when SWI-Prolog is not installed**:
  - Degraded mode: In-memory triple storage, model loading, validation (such as simple cycle checks and domain/range checks), and `.dialog` parsing/export continue to function. If a deductive reasoning or assumption-checking query requiring Prolog is invoked, the engine returns a clean, structured diagnostic notifying the user that SWI-Prolog (`swipl`) is required for logic reasoning.

---

## 5. Parser Implementation

- **Decision**: Hand-written recursive-descent / structured token scanner in pure standard library Python.
- **Rationale**:
  - Requires zero third-party parser packages (e.g. `lark`, `ply`, `antlr4-python3-runtime`).
  - Small, deterministic grammar can be parsed in <300 lines of robust, readable Python code.
  - Formats syntax errors with line numbers, columns, and helpful error messages rather than raw parser generator exceptions.

---

## 6. Python Floor

- **Decision**: Python `>= 3.10`.
- **Rationale**:
  - Aligns with the user's companion repositories (`Em-Cubed` and `brain-harness`, which both floor at 3.10).
  - Enables modern Python features: pattern matching (`match/case`), improved union type syntax (`X | Y`), and modern dataclass features, while remaining compatible with standard enterprise and developer installations.
