# Testing & Benchmark Harness Reference

`ontology_spider.harness` is an in-tree testing, property checking, differential parity, and benchmarking harness designed to evaluate reasoning engines, verify zero-drift parity, and enforce latency budgets.

---

## 1. Running the Harness CLI

```bash
# Run scenario corpus
python -m ontology_spider.harness run

# Run differential parity across Prolog and Python backends
python -m ontology_spider.harness parity --model examples/drones.dialog

# Run microbenchmarks and check budgets
python -m ontology_spider.harness bench --budget src/ontology_spider/harness/baselines/bench_budgets.json

# Generate synthetic topologies
python -m ontology_spider.harness gen lattice --size 50
```

---

## 2. Performance Budgets & Calibration Baseline

Performance budgets are defined in `src/ontology_spider/harness/baselines/bench_budgets.json` and enforced during continuous integration:

```json
{
  "chain_50_ancestors_p50_ms": 25.0,
  "tree_100_recommend_p50_ms": 15.0,
  "lattice_50_validate_p50_ms": 10.0,
  "lattice_20_ancestors_p50_ms": 15.0,
  "python_10k_query_p50_ms": 5.0,
  "lattice_10k_validate_ms": 1500.0
}
```

### Authoritative Calibration Hardware
- **OS**: Windows 11 Pro 64-bit
- **CPU**: AMD Ryzen 9 7950X / x86_64
- **Python**: 3.13.0 64-bit
- **SWI-Prolog**: 9.2.x 64-bit (persistent worker subprocess bridge)

*Note: Machines with lower single-core clock speeds or containerized virtualization overhead may experience higher p50 latencies; the calibration machine above serves as the authoritative baseline. Local runs on standard or battery-throttled laptops may exhibit $\pm 20\text{--}30\%$ variance, while CI runners enforce the authoritative gate.*

---

## 3. Corpus Scenarios (5 Bundled Scenarios)

The harness includes 5 declarative scenario files in `src/ontology_spider/harness/corpus/`:
1. **`tutorial.scenario.json`**: Basic taxonomy, instance resolution, and property queries based on `examples/tutorial.dialog`.
2. **`drones.scenario.json`**: Complex drone taxonomy, equipment dependencies, multi-attribute recommendations, and ancestor chains.
3. **`lattice.scenario.json`**: Diamond DAG topologies stress-testing BFS frontier expansion and verifying absence of exponential path enumeration.
4. **`multi_recommend.scenario.json`**: Multi-constraint recommendation queries testing attribute filtering across class inheritance hierarchies.
5. **`violations.scenario.json`**: Negative tests asserting that intentional cycle, domain/range, and disjointness violations are caught deterministically.

---

## 4. Property-Based Testing

Defined in `src/ontology_spider/harness/properties.py`:
- **Monotonicity**: Adding true assertions never invalidates existing derived facts.
- **Round-Trip Serialization**: Parsing `.dialog` $\to$ `OntologyModel` $\to$ `.dialog` preserves identical entity, relation, and assertion graphs.
- **Acyclicity Verification**: Validated DAGs never contain cycles; introduced cyclic edges always trigger `cycle_violation` violations.

---

## 5. Adding a New Scenario

To add a new scenario:
1. Create a `.dialog` model under `examples/` (or define inline in the scenario).
2. Author `<name>.scenario.json` in `src/ontology_spider/harness/corpus/`:
   ```json
   {
     "scenario": "my_new_scenario",
     "model": "examples/my_model.dialog",
     "queries": [
       "query ancestors of my_entity",
       "query recommend my_class [status=active]"
     ],
     "expected_violations": 0
   }
   ```
3. Run `python -m ontology_spider.harness run` to verify execution against both Prolog and Python backends.
