# .dialog Language Reference

The `.dialog` format is a controlled language for defining, querying, and verifying ontology graphs.

---

## 1. File Structure

A `.dialog` file consists of:
1. An optional **header** declaring the ontology URI.
2. Optional **import statements** linking external models.
3. Turn statements: **entity declarations**, **assertions**, **queries**, and **explanations**.
4. Comments beginning with `#`.

```dialog
# Vehicle System Dialog
dialog urn:ontology:vehicles

import "common_models.json"

entity quad_x1 [payload_kg=5, max_speed=45]

assert car subclass_of vehicle
assert prius instance_of car [electric=true]

query what is prius?
query ancestors of car
query recommend car where electric = true
explain query ancestors of car
```

---

## 2. Statements

### Headers
- `dialog <URI>` or `ontology <URI>`: Sets the identifier for the active ontology.

### Imports
- `import <path_or_uri>`: Loads an existing JSON (`.json`) or Dialog (`.dialog`) model through the `ModelSource` seam.

### Entities
- `entity <id> [key=value, key2=value2]`: Declares an entity and its attributes explicitly for lossless round-tripping.

### Assertions
- `assert <subject> <predicate> <object>`
- `assert <subject> <predicate> <object> [key=value, key2=value2]`
  - Attributes inside brackets are attached to the assertion.
  - Built-in schema predicates: `instance_of`, `subclass_of`, `domain`, `range`, `disjoint_with`, `acyclic`.
  - Provenance preservation metadata (`_id`, `_source`, `_turn`) is supported for lossless serialization.

---

## 3. Query Forms

### Fact Lookup
- `query what is <entity>?`: Returns all incoming and outgoing relations for `<entity>`.

### Hierarchical Ancestry
- `query ancestors of <class_or_instance>`: Traverses transitive `subclass_of` and `instance_of` links with visited-node cycle guards.

### Transitive Traversal
- `query transitive <predicate> from <subject>`: Multi-hop graph traversal over `<predicate>` returning endpoints and intermediate nodes.

### Filter Queries
- `query filter <predicate> where <attribute>=<value>`: Returns assertions matching the specified attribute key and value.

### Recommendation Queries
- `query recommend <Class> where <attribute> = <value>`: Recommends candidates belonging to `<Class>` (or its subclasses) satisfying the specified attribute requirement.
- `query recommend <Class>`: Recommends candidates belonging to `<Class>` (optionally filtered by active conversational frame constraints).

### Pattern Queries
- `query <subject> <predicate> <object>?`: Matches triple patterns where any position can be `?`, `*`, or `_`.

### Explanatory Follow-Ups
- `explain`: Explains how the previous turn's answers were obtained.
- `explain <query>`: Evaluates `<query>` inline and immediately outputs:
  - Fired inference rules
  - Graph path walked
  - Base assertions with immutable IDs and provenance metadata (source, timestamp, turn ID).

---

## 4. Command Line Interface (CLI)

The `dialog` CLI provides five subcommands:

```bash
# 1. Run a .dialog script in batch mode
dialog run script.dialog

# 2. Validate ontology integrity rules and constraints
dialog validate ontology.dialog

# 3. Export an ontology to JSON, .dialog, DOT (Graphviz), or standalone HTML
dialog export ontology.dialog --format html -o view.html

# 4. Guided 4-stage elicitation loop
dialog elicit -o new_ontology.dialog

# 5. Interactive traversal REPL with frame stack
dialog repl --file ontology.dialog
```
Inside the interactive REPL:
- `where am I` / `where am i?`: Inspect current DARPA Communicator frame stack position.
- `focus <entity>`: Push a subdialogue frame focusing on `<entity>`.
- `constrain <key>=<val>`: Set or update an active constraint (automatically popping conflicting frames).
- `validate`: Run integrity checks on the active in-memory model.
- `export <json|dialog|dot|html>`: Export current model.
- `exit` / `quit`: Exit REPL.
