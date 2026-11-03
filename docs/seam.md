# Track 9 — Seam Specification & Integration Guide

This guide is written for the author of the future `brain-harness` plugin. It defines the single interface contract required to connect the vault to the `Ontology-Spider` engine.

---

## The One Interface to Implement

To connect any repository, graph store, or vault to `Ontology-Spider`, implement the `ModelSource` abstract base class defined in `ontology_spider.seam`:

```python
from ontology_spider.seam import ModelSource
from ontology_spider.model import OntologyModel

class BrainHarnessVaultSource(ModelSource):
    def __init__(self, vault_path: str) -> None:
        self.vault_path = vault_path

    def load(self) -> OntologyModel:
        # Reads vault files/metadata and constructs an OntologyModel
        ...
```

---

## Vault-to-Ontology Mapping Table

| Vault Concept (`brain-harness`) | Ontology-Spider Concept | Implementation Mapping | Notes |
| :--- | :--- | :--- | :--- |
| **Vault Item** (`metadata.json`) | `Entity` | `Entity(id=item.id, name=item.title, attributes=item.metadata)` | Primary node identity. |
| **Item Type** (e.g. `spec`, `note`) | `Assertion` | `(item.id instance_of item.type)` | Automatically enables taxonomic hierarchy reasoning. |
| **Typed Edge** | `Relation` / `Assertion` | `(edge.from edge.rel edge.to)` | Semantic triple enabling multi-hop transitive traversals. |
| **Edge Metadata** | `Assertion.attributes` | `asrt.attributes = edge.metadata` | Filterable in queries (`query filter <rel> where <k>=<v>`). |
| **Item Provenance** | `Provenance` | `Provenance(source="vault", timestamp=item.updated_at)` | Tracks origin and audit trail for every assertion. |

### What Does NOT Map (Honest Boundaries)

1. **Unstructured Markdown Body Text**: `summary.md` and document bodies are narrative prose, not structured assertions. They remain in the vault and are referenced by URI/ID.
2. **Binary Attachments & Blobs**: Images, PDFs, and binary assets are stored in the vault filesystem and referenced by entity attributes; they are not ingested into the logical reasoning store.
3. **Execution Locks & Transient Cache**: Process-level locks belong to the runtime harness, not the declarative ontology model.

---

## Working Verification Example

See `examples/vault_adapter.py` for a complete, fully tested, zero-dependency implementation of `VaultModelSource` operating over `examples/vault_sample.json`.
