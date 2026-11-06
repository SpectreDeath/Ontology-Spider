# Canonical Query Semantics Specification

This document defines the canonical meaning, answer deduplication, path derivation, and attribute matching for each query form in Ontology-Spider.

---

## 1. Query Forms

### 1.1 `lookup(subject)`
- **Goal**: Retrieve all direct facts where `subject` participates as either the subject or the object.
- **Deduplication**: Assertions are emitted uniquely by `assertion_id`.
- **Proof Trace**: Rules fired: `['direct_fact']`, path: `[subject, object]`.

### 1.2 `ancestors(entity)`
- **Goal**: Retrieve all classes that `entity` belongs to, either directly or transitively through `instance_of` and `subclass_of` relationships.
- **Closure**: Full transitive closure over directed edges `(Current, subclass_of, Super)` and `(Current, instance_of, Super)`.
- **Deduplication**: Answers are emitted uniquely by ancestor class identifier.
- **Proof Path**: The shortest graph path from `entity` to `Ancestor`.
- **Lattices & Diamonds**: If multiple paths exist (`A -> B -> D` and `A -> C -> D`), `D` is emitted exactly once with its first/shortest witness path.

### 1.3 `transitive(predicate, start)`
- **Goal**: Multi-hop directed graph traversal beginning at `start` following edges with predicate `predicate`.
- **Closure**: Transitive reachability with cycle guards preventing infinite loops.
- **Deduplication**: Each reachable node is emitted uniquely.
- **Proof Path**: The shortest directed path from `start` to `target`.

### 1.4 `recommend(class, [filters])`
- **Goal**: Recommend instance candidates that belong to `class` or any transitive subclass of `class`, satisfying all specified attribute constraints.
- **Candidate Pool**: Any entity `C` such that `(C instance_of TargetClass)` and `(TargetClass subclass_of* Class)` (where `subclass_of*` is the reflexive transitive closure of `subclass_of`).
- **Filters**:
  - Zero filters (`query recommend X`): returns all instances of `X` or its subclasses.
  - Single filter (`query recommend X where k=v`): returns matching instances where attribute `k == v`.
  - Multi-attribute filters (`query recommend X [k1=v1, k2=v2]`): returns matching instances where all `k_i == v_i` are satisfied.
  - Attributes are checked on both the `Entity` declaration and the `instance_of` `Assertion`.
- **Deduplication**: Each candidate entity is emitted at most once, even if it satisfies attributes through multiple paths or declarations.

### 1.5 `filter(predicate, key=value)`
- **Goal**: Find all assertions with predicate `predicate` that have attribute `key == value`, either on the assertion or on its subject entity.
- **Deduplication**: Unique by `assertion_id`.

### 1.6 `pattern(subject, predicate, object)`
- **Goal**: Match triples with wildcards (`?`, `*`, `_`).
- **Deduplication**: Unique by `assertion_id`.

---

## 2. Deterministic Ordering & Canonical Proof Trace

To ensure 100% cross-backend parity between the SWI-Prolog reasoner and the pure-Python reasoner across operating systems and `PYTHONHASHSEED` configurations, answer order, proof paths, and fact identifier lists are defined deterministically:

### 2.1 Answer Ordering Rules

1. **`lookup(subject)`**:
   - Outgoing assertions `(subject, P, O)` in exact assertion insertion order.
   - Incoming assertions `(S, P, subject)` in exact assertion insertion order.
2. **`ancestors(entity)` and `transitive(predicate, start)`**:
   - Breadth-First Search (BFS) discovery layer-by-layer.
   - Outgoing edges from the frontier are expanded in exact assertion insertion order.
   - Nodes visited on earlier layers or earlier along the frontier are deduplicated and never re-expanded.
3. **`recommend(class, [filters])`**:
   - Reflexive target class examined first.
   - Subclasses examined in BFS discovery order (layer-by-layer, edges expanded in assertion insertion order).
   - Candidate instances for each class are collected from matching `instance_of` assertions in insertion order.
   - Candidates satisfying all attribute filters are emitted upon first encounter and deduplicated.
4. **`filter(predicate, key=value)` and `pattern(subject, predicate, object)`**:
   - Assertions are evaluated and emitted in exact assertion insertion order.

### 2.2 Canonical Proof Trace & Fact Identifiers

Every query answer includes a canonical proof trace (`path`, `rules`, and `fact_ids`) explaining how the answer was established:

- **`lookup`**:
  - `path`: `[subject, object]`
  - `rules`: `["direct_fact"]`
  - `fact_ids`: `[assertion_id]`
- **`ancestors`**:
  - `path`: `[entity, ..., Ancestor]` (shortest insertion-ordered witness path)
  - `rules`: `["subclass_closure"]`
  - `fact_ids`: `[asrt1_id, asrt2_id, ...]` along the shortest witness path
- **`transitive`**:
  - `path`: `[start, ..., target]` (shortest insertion-ordered witness path)
  - `rules`: `["transitive_closure"]`
  - `fact_ids`: `[asrt1_id, asrt2_id, ...]` along the shortest witness path
- **`recommend`**:
  - `path`: `[Class, Candidate]`
  - `rules`: `["recommendation"]`
  - `fact_ids`: `[instance_asrt_id, *subclass_chain_asrt_ids]` (the candidate's `instance_of` assertion ID followed by the `subclass_of` chain assertion IDs linking the candidate's direct class to the requested `Class`)
- **`filter`**:
  - `path`: `[subject, object]`
  - `rules`: `["attribute_filter"]`
  - `fact_ids`: `[assertion_id]`
- **`pattern`**:
  - `path`: `[subject, object]`
  - `rules`: `["pattern_match"]`
  - `fact_ids`: `[assertion_id]`
