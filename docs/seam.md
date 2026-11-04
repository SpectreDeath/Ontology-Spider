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

## Track 0 Architectural Decision: Integration Form (Plugin, Skill, or Both)

**Decision**: **Both** (Brain Harness Plugin + Companion Agent Skill).

### Rationale:
1. **Brain Harness Plugin (`plugins/memory_and_epistemics/ontology_spider`)**:
   - Implements native micro-kernel IoC integration (`HarnessPlugin`).
   - Registers service `service.ontology_spider` in the `ServiceContext`.
   - Houses the concrete `VaultModelSource` adapter that ingests vault/knowledge items and typed edges through the `ModelSource` seam.
   - Exposes programmatic entrypoints (`load_vault_ontology`, `query_ontology`, `validate_ontology`) executable via the micro-kernel, CLI, runtime tasks, and dock commands (`dock.yaml`).
   - *What a plugin does that a skill cannot*: Direct in-memory and subprocess RPC service registration in the harness lifecycle without human-in-the-loop prompts.
2. **Companion Agent Skill (`SKILL.md`)**:
   - Instructs AI coding agents (Antigravity, Claude Code) how and when to navigate, query, validate, and explain domain ontologies during active paired programming and refactoring sessions.
   - *What a skill does that a plugin cannot*: Cognitive reasoning heuristics, prompt guidance, and natural-language workflow context for agents.
3. **Location of Adapter Code**:
   - The adapter lives entirely on the Brain Harness side: `plugins/memory_and_epistemics/ontology_spider`.
   - It imports `ontology_spider.seam`, `ontology_spider.model`, and `ontology_spider.api`.
   - The core `ontology_spider` package remains 100% stdlib-only with zero brain-harness imports.
4. **Execution Owner**:
   - Executed by the AI Agent under explicit user direction on 2026-11-03. This formally closes the §11 verification backlog item from the original plan.

---

## Working Verification Example

### 1. Standalone Verification Adapter
See `examples/vault_adapter.py` for a complete, fully tested, zero-dependency implementation of `VaultModelSource` operating over `examples/vault_sample.json`.

### 2. Integrated Brain Harness Plugin Adapter
The production adapter lives on the Brain Harness side:
- **Adapter**: `Brain Harness/plugins/memory_and_epistemics/ontology_spider/adapter.py` (`HarnessVaultModelSource`)
- **Service**: `Brain Harness/plugins/memory_and_epistemics/ontology_spider/service.py` (`OntologySpiderService`)
- **Plugin Manifest**: `Brain Harness/plugins/memory_and_epistemics/ontology_spider/plugin.json`
- **Companion Skill**: `Brain Harness/plugins/memory_and_epistemics/ontology_spider/SKILL.md`

#### Worked Example: Vault In, Traversal Answers & Proofs Out
```python
from plugins.memory_and_epistemics.ontology_spider.service import OntologySpiderService

service = OntologySpiderService()
vault_path = "examples/vault_sample.json"

# Execute multi-hop transitive dependency traversal
result = service.query(vault_path, "query transitive depends_on from impl_plugin")

# Extracted answers
answers = [a["value"] for a in result["answers"]]
# => ['spec_seam', 'spec_core']

# Proof explanation for spec_core
spec_core_trace = next(a for a in result["answers"] if a["value"] == "spec_core")
print("Path:", spec_core_trace["path"])
# => ['impl_plugin', 'spec_seam', 'spec_core']
print("Rules:", spec_core_trace["rules_fired"])
# => ['transitive_closure']
```

#### Dock Execution Route
The integration is verified through Brain Harness's Agent Dock:
```bash
python -m harness.cli dock run brain-harness verify-ontology
```

