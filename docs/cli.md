# CLI Reference

`Ontology-Spider` includes a zero-dependency command line interface built using Python's standard library `argparse`.

Execute commands via:
```bash
python -m ontology_spider <subcommand> [flags]
# Or using the console script entrypoint:
ontology-spider <subcommand> [flags]
```

---

## 1. `run` — Batch Dialog Execution

Executes a `.dialog` script from start to finish and prints query results, asserted facts, and turn summaries to stdout.

```bash
python -m ontology_spider run <file>
```

### Arguments
- `file` (positional, required): Path to the `.dialog` script to execute.

### Example
```bash
python -m ontology_spider run examples/tutorial.dialog
```

---

## 2. `repl` — Interactive Exploration

Starts an interactive terminal REPL with multi-turn conversational traversal frames, focal tracking, and constraint push/pop operations.

```bash
python -m ontology_spider repl [--file <path>]
```

### Options
- `--file`, `-f`: Optional path to an initial `.dialog` or `.json` model to preload into the REPL session.

### Commands inside REPL
- `focus <Entity>`: Move traversal focus to the designated entity.
- `constrain <key>=<val>`: Push an attribute constraint onto the current frame.
- `pop`: Pop the active constraint frame back to the parent context.
- `why_not <Entity>`: Inspect why a candidate entity failed the current active constraints.
- `status`: Display the current traversal frame, focal entity, and active constraints.
- `quit` / `exit`: Exit the REPL session.

---

## 3. `validate` — Integrity & Constraint Checker

Runs structural and semantic validation over an ontology model and exits with code `0` on clean models or `1` if violations are found.

```bash
python -m ontology_spider validate <file>
```

### Arguments
- `file` (positional, required): Path to the `.dialog` or `.json` model to validate.

### Checks Performed
- **Cycle Detection**: Verifies that acyclic relations (e.g. `subclass_of`, `part_of`) contain no directed cycles.
- **Disjointness**: Ensures entities do not inherit from mutually disjoint classes.
- **Domain & Range**: Checks that relation subjects and objects satisfy declared class constraints.
- **Orphan Instances**: Reports instances that have no declared `instance_of` classification.

---

## 4. `export` — Model Serialization

Converts an ontology model from `.dialog` or `.json` into target formats.

```bash
python -m ontology_spider export <file> [--format <fmt>] [--output <path>]
```

### Options
- `file` (positional, required): Path to the source model.
- `--format`, `-f`: Target output format. Choices: `json`, `dialog`, `dot`, `html`. (Default: `json`).
- `--output`, `-o`: Optional destination file path. If omitted, output is printed to stdout.

### Example
```bash
python -m ontology_spider export examples/tutorial.dialog --format html --output tutorial_graph.html
```

---

## 5. `elicit` — Schema Elicitation Wizard

Launches an interactive, mixed-initiative dialogue wizard guiding users through schema definition (classes, hierarchies, relations, entity attributes) with validation and export.

```bash
python -m ontology_spider elicit [--output <path>]
```

### Options
- `--output`, `-o`: Optional path where the finalized `.dialog` model will be saved upon completion.

---

## 6. `mcp` — Model Context Protocol Stdio Server

Runs a Model Context Protocol (MCP) server over standard I/O (JSON-RPC 2.0 with NDJSON transport) allowing AI assistants to query, traverse, and author ontology models.

```bash
python -m ontology_spider mcp [flags]
```

### Options
- `--model <path>`: Optional path to an ontology model to preload into the `default` session on startup.
- `--backend {auto,prolog,python}`: Reasoner backend selection. (Default: `auto`, which selects Prolog if `swipl` is available, falling back to pure-Python BFS).
- `--read-only`: Disallows mutating tools (`assert_triple`, `declare_entity`, `retract`, `run_dialog`, `focus`, `constrain`). Default is `False` (in-memory session mutation allowed).
- `--root <path>`: Root filesystem sandbox directory. Confines all file loads and exports within this path. (Default: current working directory).
- `--timeout <seconds>`: Per-query execution timeout in seconds. (Default: `10.0`).
- `--max-inferences <count>`: Maximum inference steps permitted per query before raising an error. (Default: `1000000`).
- `--max-sessions <count>`: Maximum concurrent active in-memory sessions allowed. (Default: `32`).
- `--max-assertions <count>`: Maximum assertions allowed per session. (Default: `50000`).

### Example
```bash
python -m ontology_spider mcp --root . --model examples/tutorial.dialog --timeout 5.0 --max-inferences 50000
```
