# Model Context Protocol (MCP) Server Reference

`Ontology-Spider` provides a Model Context Protocol (MCP) server running over standard input and output (JSON-RPC 2.0 with newline-delimited JSON transport) without any third-party dependencies.

---

## 1. Starting the Server

```bash
# Start server with in-memory write access (default)
python -m ontology_spider mcp --root .

# Start server in read-only mode (mutation tools disabled)
python -m ontology_spider mcp --root . --read-only

# Start server with explicit timeouts, inference limits, and backend
python -m ontology_spider mcp --root . --backend python --timeout 5.0 --max-inferences 50000
```

---

## 2. Server Configuration & Security Sandbox

- **Read-Only Gate (`--read-only`)**:
  - Default: `read_only=False`. Allows in-memory session mutations (`assert_triple`, `declare_entity`, `retract`, `run_dialog`, `focus`, `constrain`).
  - Opt-In: `--read-only`. Disallows all 6 mutating tools, returning error code `-32001` (`PermissionError: Server is running in read-only mode`).
- **Filesystem Sandbox (`--root`)**:
  - All file load operations (`model_load`, `session_open` with `model_path`) and exports are strictly confined within the `--root` directory via `Path.resolve().relative_to(root_dir)`. Any traversal attempt outside root raises `PermissionError`.
- **Operational Caps**:
  - `max_sessions`: Maximum concurrent in-memory sessions (default: 32).
  - `max_assertions_per_session`: Maximum assertions per session (default: 50,000).
  - `timeout_seconds`: Per-query execution deadline in seconds (default: 10.0). Configurable via `--timeout <float>` flag on CLI and server init. Verified with a synthetic linear chain ($N=10,000$, 9,999 assertions, leaf `c_9999`): querying `c_9999` under the Python backend with bounded explanation provenance completes in `1.151s` under the default `--timeout 10.0` returning all 9,999 ancestors with strictly bounded memory (<85 MB), while tight timeouts (e.g. `--timeout 0.05`) terminate deterministically with `QueryTimeoutError`.
  - `max_inferences`: Per-query inference step budget (default: 1,000,000). Enforced via `--max-inferences <int>` (tested with `max_inferences=2` raising `QueryInferenceLimitError`).
- **Transport**:
  - Stdio JSON-RPC 2.0 with NDJSON and Content-Length framing support.
  - Supports non-blocking client request cancellation via `notifications/cancelled` (`{"requestId": ...}`).

---

## 3. Tool Reference (16 Tools)

### Session Management
1. **`session_open`**:
   - Parameters: `session_id` (optional str), `uri` (optional str), `model_path` (optional relative path).
   - Returns: `{"sessionId": "<id>", "content": [{"type": "text", "text": "Session opened."}]}`
2. **`session_close`**:
   - Parameters: `session_id` (str, required).
   - Returns: Confirmation of closed session.
3. **`session_list`**:
   - Parameters: None.
   - Returns: List of all active session identifiers.
4. **`engine_info`**:
   - Parameters: None.
   - Returns: Active backend (`prolog` or `python`), available backends, read-only status, root sandbox, session counts, timeout, and inference limits.

### Ontology Authoring & Mutation (Gated by `--read-only`)
5. **`model_load`**:
   - Parameters: `session_id` (str), `path` (str, relative to root).
   - Merges entities and assertions from a file into the target session.
6. **`assert_triple`**:
   - Parameters: `session_id` (str), `subject` (str), `predicate` (str), `object` (str), `attributes` (optional dict).
   - Returns: `{"content": [{"type": "text", "text": "Asserted: (s p o) [asrt_id]"}]}`
7. **`declare_entity`**:
   - Parameters: `session_id` (str), `entity_id` (str), `attributes` (optional dict).
   - Returns: Confirmation of declared entity.
8. **`retract`**:
   - Parameters: `session_id` (str), `assertion_id` (str).
   - Removes assertion from the session model.
9. **`run_dialog`**:
   - Parameters: `session_id` (str), `dialog_text` (str).
   - Executes multi-statement `.dialog` syntax against the session.

### Querying, Reasoning & Verification
10. **`query`**:
    - Parameters: `session_id` (str), `query` (str, e.g. `"query ancestors of delivery_drone"` or `"query recommend quadcopter [payload_kg=5]"`).
    - Returns: Summary text and structured `answers` array with derived values, fired rules, proof paths, and provenance assertion IDs. Enforces per-query timeout and inference limits.
11. **`explain`**:
    - Parameters: `session_id` (str).
    - Returns: Formatted proof trace for the previous query answers.
12. **`validate`**:
    - Parameters: `session_id` (str).
    - Returns: Array of violations (cycles, disjointness, domain/range errors) with offending assertion IDs.
13. **`export`**:
    - Parameters: `session_id` (str), `format` (str: `"json"`, `"dialog"`, `"dot"`, `"html"`).
    - Returns: Serialized model content.

### Conversational Traversal Stack
14. **`focus`**:
    - Parameters: `session_id` (str), `entity_id` (str), `constraints` (optional dict).
    - Pushes a new subdialogue frame focusing on the given entity.
15. **`constrain`**:
    - Parameters: `session_id` (str), `key` (str), `value` (str).
    - Adds or updates an active constraint on the current frame.
16. **`where_am_i`**:
    - Parameters: `session_id` (str).
    - Inspects the active traversal frame, focal entity, and active constraints.

---

## 4. MCP Resources Reference (3 Schemes)

1. **`ontology://docs/language-reference`**:
   - Returns the complete Markdown language reference and formal grammar (reads from `docs/language_reference.md` relative to `--root`, falling back to bundled package documentation when run in external workspaces).
2. **`ontology://session/{session_id}/model.json`**:
   - Returns live JSON serialization of the model in the named active session.
3. **`ontology://examples/{stem}`**:
   - Returns raw text of bundled or workspace example dialog scripts (e.g. `examples/tutorial.dialog`, `examples/drones.dialog`), safely resolved through the sandbox root with fallback to package examples.
