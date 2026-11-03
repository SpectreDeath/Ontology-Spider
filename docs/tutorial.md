# Ontology-Spider Tutorial

This tutorial demonstrates how to build an ontology using dialogue, run reasoning queries, validate constraints, and export the model.

---

## 1. Running a .dialog Script via the CLI

Execute the tutorial corpus using the command-line interface:

```bash
python -m ontology_spider.cli run examples/tutorial.dialog
```

Output:
```
Asserted: (vehicle subclass_of system) [asrt_0c49beec0a2d]
Asserted: (ground_vehicle subclass_of vehicle) [asrt_63529328ff9a]
Asserted: (aerial_vehicle subclass_of vehicle) [asrt_8f0a386ea4b0]
Asserted: (delivery_drone subclass_of aerial_vehicle) [asrt_8e8efeb05943]
Asserted: (sky_scout instance_of delivery_drone) [asrt_5d6e24391e4f]
Asserted: (terra_bot instance_of ground_vehicle) [asrt_1bf0a5390772]
Asserted: (sky_scout depends_on navigation_module) [asrt_75094254f199]
Asserted: (navigation_module depends_on gps_sensor) [asrt_a1998f57faee]
Found 2 facts for 'sky_scout'.
  -> (sky_scout instance_of delivery_drone)
  -> (sky_scout depends_on navigation_module)
Ancestors of delivery_drone: aerial_vehicle, vehicle, system
  -> aerial_vehicle
  -> vehicle
  -> system
Transitive depends_on from sky_scout: navigation_module, gps_sensor
  -> navigation_module
  -> gps_sensor
Filtered instance_of (payload_kg=5): 1 matches
  -> (sky_scout instance_of delivery_drone)
Explanation for previous answers:
Answer #1 [(sky_scout instance_of delivery_drone)]:
  Rules: attribute_filter
  Path: sky_scout -> delivery_drone
  Base Facts:
    - [asrt_5d6e24391e4f] (sky_scout instance_of delivery_drone) (source=inline.dialog, turn=stmt_5)
```

---

## 2. Using the Python Machine API

You can programmatically load, query, validate, and export models:

```python
from ontology_spider.api import load_model, run_query, validate_model, export_model

# Load model from dialog file
model = load_model("examples/tutorial.dialog")

# Run query with provenance
result = run_query(model, "query ancestors of delivery_drone")
print(result["summary"])
for ans in result["answers"]:
    print(f"  - {ans['value']} (path: {' -> '.join(ans['path'])})")

# Validate integrity
violations = validate_model(model)
print(f"Violations detected: {len(violations)}")

# Export to static HTML
html_view = export_model(model, "html")
```

---

## 3. Interactive Dialogue REPL

Start an interactive conversational REPL session:

```bash
python -m ontology_spider.cli repl
```
