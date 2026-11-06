# Ontology-Spider

[![CI](https://github.com/SpectreDeath/Ontology-Spider/actions/workflows/ci.yml/badge.svg)](https://github.com/SpectreDeath/Ontology-Spider/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://www.python.org/)
[![Dependencies: 0](https://img.shields.io/badge/dependencies-0-success.svg)](pyproject.toml)

A standalone ontological engine combining controlled conversational dialogue and formal logic reasoning.

---

## What This Is

Ontology-Spider is an end-to-end ontological engine in the lineage of **ASKE Dialog** (DARPA ASKE TA1/TA2) and **Em-Cubed's ontology core**, featuring:

- **Prolog as Reasoner**: Formal logic reasoning over facts, inheritance, transitive closure, domain/range constraints, disjointness, and cycle detection. Executes via SWI-Prolog with robust inference limits, subshell timeouts, and an automatic pure-Python degraded fallback when SWI-Prolog is absent.
- **Dialog as Conversational Language**: A controlled language for querying, asserting, and eliciting ontology models without heavyweight IDE dependencies.
- **Provable Explanations**: Every query answer carries a deterministic proof trace: which base assertions fired (with provenance source, turn ID, and timestamps), which rules executed, and what graph path was traversed.
- **Bi-directional Dialogue**: Supports both traversal (querying existing knowledge with conversational focus and constraint stacks) and creation (step-by-step elicitation dialogue with mandatory confirmation and mixed-initiative correction).
- **Seam-First Architecture**: Clean `ModelSource` abstraction enabling pluggable model adapters (e.g. JSON graphs, `.dialog` authoring files, and vault plugins) with zero vendor lock-in.
- **Zero Third-Party Dependencies**: Pure Python standard library implementation (`dependencies = []` in `pyproject.toml`).

---

## What This Is NOT

- **Not an IDE Plugin**: Unlike the 2019-era Eclipse/Xtext ASKE Dialog prototype, this is a clean, modern Python CLI and library with no Java 8 or Eclipse requirements.
- **Not Free-Form LLM Prompting**: It uses a deterministic, controlled grammar for queries and assertions. Free-form natural language parsing is explicitly deferred.
- **Not a Full OWL2 DL Classifier**: It reasons over semantic triples and a canonical schema vocabulary with custom Prolog inference rules rather than complex tableau algorithms.
- **Not an Unrestricted Sandbox**: v1 operates over local, trusted models. Prolog goals run with strictly escaped inputs against predefined rule libraries, and subshells run with bounded inference counts and timeouts.

---

## Key Features in v0.2.0

- **First-Class Entity Declarations**: Explicit entity creation with bracketed key-value attributes:
  ```dialog
  entity sky_scout [payload_kg=5, range_km=25, status=operational]
  ```
- **Recommendation Engine**: Constrained recommendation queries matching target classes and attribute filters:
  ```dialog
  query recommend delivery_drone [payload_kg=5, range_km=20]
  ```
- **Inline & Standalone Explanations**: Request proof traces inline (`query ... explain`) or inspect the last query result with `explain`:
  ```dialog
  query recommend delivery_drone [payload_kg=5] explain
  ```
- **Canonical Schema Constraints**: Built-in verification for `domain`, `range`, `acyclic`, and `disjoint_with`.
- **Integrity Validation**: Standalone and hook-based validation checking for directed cycles in acyclic relations, domain/range violations, disjoint class inheritance conflicts, and unclassified orphan instances.
- **Conversational Traversal Stack**: Multi-turn dialogue frames in REPL tracking focal entities, active constraints, and automatic conflict pruning.
- **Multi-Format Export**: Export models to JSON, `.dialog` scripts, Graphviz DOT, or standalone self-contained HTML visualizations.

---

## Quickstart

### Prerequisites
- **Python**: `>= 3.10` (tested on 3.10, 3.11, 3.12, 3.13 across Ubuntu and Windows)
- **SWI-Prolog** *(optional)*: Provides high-performance formal logic reasoning. If SWI-Prolog (`swipl`) is not on your `PATH`, Ontology-Spider automatically falls back to an integrated pure-Python graph reasoner.

### Installation
Install in editable mode:
```bash
pip install -e .
```
*(Alternative without installation: set `PYTHONPATH=src` or `$env:PYTHONPATH="src;."` before running commands.)*

### Running Tests & Coverage
```bash
# Run all tests
python -m unittest discover -s tests

# Check test coverage
coverage run -m unittest discover -s tests
coverage report
```

---

## CLI Usage

Ontology-Spider provides 5 CLI subcommands:

### 1. Run a `.dialog` Script (`run`)
Batch-executes an authoring script, evaluates queries, and prints formatted answers and explanations:
```bash
python -m ontology_spider.cli run examples/drones.dialog
```

### 2. Interactive Conversational REPL (`repl`)
Launches a multi-turn conversational session with stackable dialogue focus frames:
```bash
python -m ontology_spider.cli repl --file examples/drones.dialog
```
Available REPL commands:
| Command | Description |
|---|---|
| `where am I` | Display active dialogue frame stack, focal entity, and constraints |
| `focus <entity>` | Push a child frame focused on `<entity>` |
| `constrain <k>=<v>` | Add an attribute filter to the active frame (auto-prunes conflicting frames) |
| `assert <S> <P> <O>` | Assert a new triple directly into the active session |
| `query <form>` | Execute any query form (`facts`, `ancestors`, `transitive`, `recommend`, etc.) |
| `explain` | Print the full provenance and proof trace for the previous query |
| `validate` | Run full integrity validation against the current model |
| `export <fmt>` | Export session model to stdout (`json`, `dialog`, `dot`, `html`) |
| `exit` | Terminate the REPL session |

### 3. Model Integrity Validation (`validate`)
Verifies schema constraints and reports violations with rule types and offending assertion IDs:
```bash
python -m ontology_spider.cli validate examples/drones.dialog
```

### 4. Model Export (`export`)
Exports any ontology model source to `json`, `dialog`, `dot`, or `html`:
```bash
python -m ontology_spider.cli export examples/drones.dialog --format html -o out.html
python -m ontology_spider.cli export examples/drones.dialog --format json -o out.json
```

### 5. Guided Elicitation Interview (`elicit`)
Runs a step-by-step competency-driven ontology authoring session with mandatory confirmation:
```bash
python -m ontology_spider.cli elicit --output my_ontology.dialog
```

---

## Python API

Ontology-Spider provides a clean, deep Python API with zero external dependencies:

```python
from ontology_spider.api import load_model, run_query, validate_model, export_model

# 1. Load model from any supported source
model = load_model("examples/drones.dialog")

# 2. Validate structural integrity
violations = validate_model(model)
print(f"Violations: {len(violations)}")

# 3. Query the ontology with proof traces
result = run_query(model, "query recommend delivery_drone [payload_kg=5]")
print("Recommended:", [a["value"] for a in result["answers"]])
for ans in result["answers"]:
    print("Proof Trace:", ans["rules_fired"], ans["path"])

# 4. Export to other formats
json_str = export_model(model, "json")
html_str = export_model(model, "html")
```

---

## Brain Harness Integration

Ontology-Spider connects directly to Brain Harness through the `ModelSource` seam:
- **Plugin Location**: `Brain Harness/plugins/memory_and_epistemics/ontology_spider/`
- **Adapter**: `HarnessVaultModelSource` maps Brain Harness vault items, typed edges, and metadata into `OntologyModel`.
- **Dock Verification**: Exercise the adapter and proof verification via the Brain Harness agent dock:
  ```bash
  python -m harness.cli dock run brain-harness verify-ontology
  ```
- **Companion Skill**: Bundles `SKILL.md` for agent reasoning workflows, dependency analysis, and prompt heuristics.

---

## Repository Structure

```
Ontology-Spider/
├── src/ontology_spider/        # Core engine package
│   ├── model.py                # OntologyModel, Entity, Relation, Assertion, Provenance
│   ├── dialog.py               # DialogParser, AST statements, and serializer
│   ├── dialog_runner.py        # DialogSession, query execution, and proof traces
│   ├── elicitation.py          # Guided elicitation state machine & amendments
│   ├── traversal.py            # DialogueFrame stack & conversational focus
│   ├── validation.py           # OntologyValidator & schema constraints
│   ├── export.py               # Multi-format serializers (JSON, Dialog, DOT, HTML)
│   ├── seam.py                 # Pluggable ModelSource abstraction
│   ├── api.py                  # High-level public facade
│   ├── cli.py                  # 5 CLI subcommands (run, repl, validate, export, elicit)
│   └── prolog/                 # Logic reasoning layer
│       ├── rules.pl            # Pure Prolog inference rules
│       ├── reasoner.py         # SWI-Prolog runner & Python degraded fallback
│       └── translator.py       # Bi-directional Prolog <-> Model translation
├── examples/                   # Reference ontologies & adapter demonstrations
│   ├── tutorial.dialog         # Getting-started tutorial corpus
│   ├── drones.dialog           # Comprehensive UAV & subsystem benchmark
│   └── vault_adapter.py        # Reference Seam adapter implementation
├── tests/                      # 70 unit tests (90% statement coverage)
└── docs/                       # Specifications and reference manuals
    ├── language_reference.md   # .dialog grammar & query syntax
    ├── tutorial.md             # End-to-end tutorial walkthrough
    ├── architecture.md         # Trust model, safety, & deferred features
    ├── seam.md                 # Seam specification for external plugins
    └── decisions.md            # Foundational architectural decisions
```

---

## Documentation

- [Language Reference](docs/language_reference.md): Grammar and query specification for `.dialog` files.
- [Tutorial & Worked Example](docs/tutorial.md): Step-by-step walkthrough covering creation, traversal, validation, and export.
- [Architecture & Boundaries](docs/architecture.md): Trust model, seam architecture, and safety bounds.
- [Seam Specification](docs/seam.md): Guide for connecting future repository and vault plugins.
- [Design Decisions](docs/decisions.md): Foundational architectural decision records.

---

## License

This project is licensed under the MIT License.
