# .dialog Language Reference

The `.dialog` format is a controlled language for defining, querying, and verifying ontology graphs.

---

## 1. File Structure

A `.dialog` file consists of:
1. An optional **header** declaring the ontology URI.
2. Optional **import statements** linking external models.
3. Turn statements: **assertions**, **queries**, and **explanations**.
4. Comments beginning with `#`.

```dialog
# Vehicle System Dialog
dialog urn:ontology:vehicles

import "common_models.json"

assert car subclass_of vehicle
assert prius instance_of car [electric=true]

query what is prius?
query ancestors of car
explain
```

---

## 2. Statements

### Headers
- `dialog <URI>` or `ontology <URI>`: Sets the identifier for the active ontology.

### Imports
- `import <path_or_uri>`: Loads an existing JSON (`.json`) or Dialog (`.dialog`) model through the `ModelSource` seam.

### Assertions
- `assert <subject> <predicate> <object>`
- `assert <subject> <predicate> <object> [key=value, key2=value2]`
  - Attributes inside brackets are attached to the assertion and subject entity.
  - Built-in schema predicates: `instance_of`, `subclass_of`, `domain`, `range`, `disjoint_with`, `acyclic`.

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

### Pattern Queries
- `query <subject> <predicate> <object>?`: Matches triple patterns where any position can be `?`, `*`, or `_`.

### Explanatory Follow-Ups
- `explain`: Explains how the previous turn's answers were obtained, outputting:
  - Fired inference rules
  - Graph path walked
  - Base assertions with immutable IDs and provenance metadata (source, timestamp, turn ID).
