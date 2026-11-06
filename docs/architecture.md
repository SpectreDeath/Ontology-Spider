# Architecture Note: Seam, Trust Boundary & Deferred List

This document describes the architectural boundaries, security trust model, and deferred components of `Ontology-Spider`.

---

## 1. The Model Import Seam (Track 1 & Track 9)

The seam is a decoupled boundary separating the core reasoner from external storage formats:
- **`ModelSource` Interface**: Defined in `src/ontology_spider/seam.py`. Any external store (such as the future `brain-harness` vault plugin) implements one single method: `load() -> OntologyModel`.
- **Zero Foreign Imports**: The seam module imports zero third-party or companion repository code, preventing circular dependencies and implementation forking.
- **Bi-directional Round-Trip**: Models export to both JSON and `.dialog` authoring syntax and re-import identically.

---

## 2. Trust Boundary (Track 3)

- **Local Trusted Models Only**: v1 is designed for local, trusted models.
- **Prolog Goal Construction**: User input queries in `.dialog` are parsed into a typed AST and compiled into strict, predefined rule goals with escaped arguments. Raw user input strings are never passed directly to Prolog as arbitrary execution goals.
- **Prolog I/O Boundary**: Prolog goals in user-authored external rule files can execute standard SWI-Prolog I/O; the engine makes no claim of an uncircumventable sandbox. Workloads requiring untrusted multi-tenant isolation are deferred.
- **Timeouts & Inference Limits**: Subprocess timeouts and in-Prolog inference caps (`call_with_inference_limit/3`) ensure that cyclic data or infinite loops terminate deterministically without locking the process.
- **MCP Trust Boundary**: File access (`model_load`, `import`, file `export`) is confined to `--root` via `Path.resolve().relative_to(root_dir)`. Mutating tools (`assert_triple`, `declare_entity`, `retract`, `run_dialog`, `focus`, `constrain`) are disabled when started with `--read-only`. Active sessions and assertions per session are bounded (max 32 active sessions, max 50,000 assertions per session).

---

## 3. Deferred-by-Design Features (Track 10)

The following components are deferred by design to maintain simplicity:
1. **Full OWL2 DL Reasoning**: Triples with custom Prolog rules cover transitive hierarchy, disjointness, domain/range, and cycles. Complex description logic tableau classifiers are deferred until triples prove insufficient.
2. **Topos / Continuous Truth Values & Multi-Agent Consensus**: Heavier Em-Cubed ontology machinery is deferred until multi-author federated use cases arise.
3. **Distributed Execution / WASM / GPU Surfaces**: Local SWI-Prolog execution handles standard ontologies with sub-second latency.
4. **Eclipse IDE Parity**: Replaced by lightweight CLI, REPL, and web-ready HTML/DOT exports.
5. **Speech I/O (ASR/TTS)**: Text-based conversational dialogue is v1.
6. **Free-Form Natural Language Understanding (LLM Parsing)**: Deterministic controlled `.dialog` syntax provides provable, reproducible reasoning. LLM-based prose extraction is deferred until an explicit requirement is approved.
