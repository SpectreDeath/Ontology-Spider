# Python API Reference

`ontology_spider.api` provides a direct, programmatic interface to load, query, validate, and export ontology models in Python.

---

## 1. `load_model`

```python
def load_model(source: Union[str, Path, ModelSource]) -> OntologyModel
```

Loads an `OntologyModel` from a file path, raw string, or custom `ModelSource` adapter.

### Parameters
- `source`:
  - `Path` or `str` path pointing to an existing `.dialog` or `.json` file.
  - Raw `str` content: JSON object string (starting with `{`) or `.dialog` script.
  - `ModelSource`: An instance implementing the seam boundary (`load() -> OntologyModel`).

### Returns
- `OntologyModel`: Parsed in-memory model containing entities, assertions, and version metadata.

### Example
```python
from ontology_spider.api import load_model

# From raw .dialog text
dialog_code = """
dialog urn:example:drones
assert quadcopter subclass_of drone
assert delivery_drone subclass_of quadcopter
"""
model = load_model(dialog_code)
print(f"Loaded {len(model.assertions)} assertions from {model.uri}")
```

---

## 2. `run_query`

```python
def run_query(model: OntologyModel, query_str: str) -> QueryResult
```

Executes a single `.dialog` query against the specified model, returning structured answers, proof explanations, and provenance assertions.

### Parameters
- `model`: An in-memory `OntologyModel`.
- `query_str`: A controlled query string (e.g. `"query ancestors of delivery_drone"` or `"query recommend delivery_drone [payload_kg=5]"`).

### Performance Note
`run_query` creates a fresh, isolated `Engine` and `Session` per call. For batch workflows or multi-turn conversational traversal, instantiate `Engine.session_manager.open_session()` or `TraversalDialogueManager` directly to reuse session state.

### Returns
- `QueryResult`:
  - `.statement_type`: `"query"` or `"explain"`
  - `.summary`: Human-readable summary string (e.g. `"Query ancestors: quadcopter, drone"`)
  - `.answers`: List of dictionary answers containing `value`, `rules_fired`, `path`, `fact_ids`, and `provenance`
  - `.explanation`: Detailed audit trace with rules, path, and base assertions
  - `.to_dict()`: JSON-serializable dictionary representation

### Example
```python
from ontology_spider.api import load_model, run_query

model = load_model("""
dialog urn:example:drones
assert quadcopter subclass_of drone
assert delivery_drone subclass_of quadcopter
""")

result = run_query(model, "query ancestors of delivery_drone")
print(result.summary)
# Output: Query ancestors: quadcopter, drone
for ans in result.answers:
    print(f"Answer: {ans['value']} via {ans['rules_fired']}")
```

---

## 3. `validate_model`

```python
def validate_model(model: OntologyModel) -> list[dict[str, Any]]
```

Evaluates structural integrity, domain/range constraints, class disjointness, and acyclicity over the model.

### Returns
A list of violation dictionaries with keys:
- `check_type`: Rule violated (e.g. `"cycle_violation"`, `"domain_violation"`, `"range_violation"`, `"disjointness_violation"`, `"assumption_violation"`)
- `message`: Descriptive diagnostic explanation
- `offending_assertion_ids`: List of assertion IDs responsible for the violation
- `details`: Granular metadata (entities, classes, relations involved)

### Example
```python
from ontology_spider.api import load_model, validate_model

model = load_model("""
dialog urn:example:cycles
assert drone subclass_of aircraft
assert aircraft subclass_of drone
""")

violations = validate_model(model)
for v in violations:
    print(f"[{v['check_type']}] {v['message']}")
```

---

## 4. `export_model`

```python
def export_model(model: OntologyModel, format: str = "json") -> str
```

Serializes an `OntologyModel` into a target serialization format.

### Supported Formats
- `"json"`: Canonical JSON model serialization
- `"dialog"`: Formatted `.dialog` syntax
- `"dot"`: Graphviz DOT digraph format
- `"html"`: Standalone interactive HTML page with interactive force-directed graph canvas

### Example
```python
from ontology_spider.api import export_model, load_model

model = load_model("assert quadcopter subclass_of drone")
json_str = export_model(model, format="json")
dialog_str = export_model(model, format="dialog")
dot_str = export_model(model, format="dot")
html_str = export_model(model, format="html")
```
