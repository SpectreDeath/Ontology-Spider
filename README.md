# Ontology-Spider

A standalone ontological engine combining controlled conversational dialogue and formal logic reasoning.

## What This Is

Ontology-Spider is an end-to-end ontological engine in the lineage of **ASKE Dialog** (DARPA ASKE TA1/TA2) and **Em-Cubed's ontology core**, featuring:
- **Prolog as Reasoner**: Formal logic reasoning over facts, inheritance, transitive closure, domain/range constraints, and cycle detection.
- **Dialog as Conversational Language**: A controlled language for querying, asserting, and eliciting ontology models without heavyweight IDE dependencies.
- **Provable Explanations**: Every query answer carries its proof trace: which base assertions fired (with provenance), which rules executed, and what graph path was traversed.
- **Bi-directional Dialogue**: Supports both traversal (querying existing knowledge) and creation (step-by-step elicitation dialogue with mandatory confirmation and mixed-initiative correction).
- **Seam-First Architecture**: Clean `ModelSource` abstraction enabling pluggable model adapters (e.g., JSON graphs, `.dialog` authoring files, and future vault plugins) with zero vendor lock-in.

## What This Is NOT

- **Not an IDE Plugin**: Unlike the 2019-era Eclipse/Xtext ASKE Dialog prototype, this is a clean, modern Python CLI and library with no Java 8 or Eclipse requirements.
- **Not Free-Form LLM Prompting**: It uses a deterministic, controlled grammar for queries and assertions. Free-form natural language parsing is explicitly deferred.
- **Not a Full OWL2 DL Classifier**: It reasons over semantic triples and a canonical schema vocabulary with custom Prolog inference rules rather than complex tableau algorithms.
- **Not an Unrestricted Sandbox**: v1 operates over local, trusted models. Prolog goals run with strictly escaped inputs against predefined rule libraries, but full arbitrary Prolog goal execution is not an untrusted sandbox.

## Quickstart

### Prerequisites
- Python >= 3.10
- SWI-Prolog (optional for basic graph models; required for logic reasoning and assumption verification)

### Running Tests
```bash
python -m unittest discover -s tests
```

### Running a .dialog Script
```bash
python -m ontology_spider.cli run examples/tutorial.dialog
```

### Starting the Interactive REPL
```bash
python -m ontology_spider.cli repl
```

## Documentation

- [Language Reference](docs/language_reference.md): Grammar and query specification for `.dialog` files.
- [Tutorial & Worked Example](docs/tutorial.md): Step-by-step walkthrough covering creation, traversal, validation, and export.
- [Architecture & Boundaries](docs/architecture.md): Trust model, seam architecture, and deferred feature list.
- [Seam Specification](docs/seam.md): Guide for connecting future repository and vault plugins.
- [Design Decisions](docs/decisions.md): Foundational Track 0 architectural decisions.
