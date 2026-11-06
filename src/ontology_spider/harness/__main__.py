"""CLI entrypoint for ontology harness: run, parity, gen, bench, corpus."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ontology_spider.api import load_model
from ontology_spider.harness.bench import run_benchmarks
from ontology_spider.harness.generators import (
    generate_chain,
    generate_cyclic,
    generate_lattice,
    generate_random_dag,
    generate_tree,
)
from ontology_spider.harness.runner import HarnessRunner


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ontology-spider.harness",
        description="Testing, parity, and benchmark harness for Ontology-Spider",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # run command
    run_parser = subparsers.add_parser("run", help="Run full scenario corpus")
    run_parser.add_argument("--backend", choices=["prolog", "python", "both"], default="both")
    run_parser.add_argument("--transport", choices=["inproc", "mcp"], default="inproc")
    run_parser.add_argument("--dir", default=str(Path(__file__).parent / "corpus"), help="Corpus directory")
    run_parser.add_argument("--report-json", help="Optional path to write scenario run report JSON")
    run_parser.add_argument("--report-md", help="Optional path to write scenario run report Markdown")

    # parity command
    parity_parser = subparsers.add_parser("parity", help="Run parity diff between Prolog and Python backends")
    parity_parser.add_argument("--model", default="examples/drones.dialog", help="Model file path")

    # bench command
    bench_parser = subparsers.add_parser("bench", help="Run performance benchmarks")
    bench_parser.add_argument("--save", help="Optional path to write benchmark json output")
    bench_parser.add_argument("--budget", help="Optional path to JSON budget file to enforce")

    # corpus command
    corpus_parser = subparsers.add_parser("corpus", help="Run parity across all corpus scenarios")
    corpus_parser.add_argument("--dir", default=str(Path(__file__).parent / "corpus"), help="Corpus directory")

    # gen command
    gen_parser = subparsers.add_parser("gen", help="Generate synthetic ontology topology")
    gen_parser.add_argument("topology", choices=["chain", "tree", "lattice", "random_dag", "cyclic"])
    gen_parser.add_argument("--size", type=int, default=20)
    gen_parser.add_argument("--seed", type=int, default=42)

    args = parser.parse_args(argv)

    if args.command == "parity":
        model_path = Path(args.model)
        if not model_path.is_file():
            print(f"Error: model file not found: {model_path}", file=sys.stderr)
            return 1
        model = load_model(model_path)
        queries = [
            "query what is sky_scout?",
            "query ancestors of delivery_drone",
            "query transitive depends_on from sky_scout",
            "query recommend delivery_drone where payload_kg=5",
            "query recommend delivery_drone",
        ]
        runner = HarnessRunner()
        report = runner.run_parity(model, queries)
        print(report.summary())
        return 0 if report.parity_rate == 1.0 else 2

    elif args.command in ("corpus", "run"):
        corpus_dir = Path(args.dir)
        scenario_files = list(corpus_dir.glob("*.scenario.json"))
        if not scenario_files:
            print(f"No scenario files found in {corpus_dir}", file=sys.stderr)
            return 1

        backend = getattr(args, "backend", "both")
        transport = getattr(args, "transport", "inproc")
        report_json = getattr(args, "report_json", None)
        report_md = getattr(args, "report_md", None)

        runner = HarnessRunner()
        results = []
        all_passed = True
        for sf in scenario_files:
            spec = json.loads(sf.read_text(encoding="utf-8"))
            res = runner.run_scenario(spec, backend=backend, transport=transport)
            results.append(res)
            status_str = "PASS" if res.passed else "FAIL"
            print(f"Scenario [{res.scenario}]: {res.queries_passed}/{res.queries_run} queries matched ({res.parity_rate*100:.1f}%) [{status_str}]")
            if not res.passed:
                all_passed = False
                if res.details:
                    print(f"  {res.details}")

        if report_json:
            report_data = {
                "backend": backend,
                "transport": transport,
                "all_passed": all_passed,
                "scenarios": [r.to_dict() for r in results],
            }
            Path(report_json).write_text(json.dumps(report_data, indent=2), encoding="utf-8")

        if report_md:
            md_lines = [
                "# Ontology-Spider Harness Scenario Report",
                "",
                f"- **Backend**: `{backend}`",
                f"- **Transport**: `{transport}`",
                f"- **Overall Status**: `{'PASS' if all_passed else 'FAIL'}`",
                "",
                "| Scenario | Queries Run | Queries Passed | Parity Rate | Violations Passed | Status |",
                "|---|---|---|---|---|---|",
            ]
            for r in results:
                status = "PASS" if r.passed else "FAIL"
                v_status = "PASS" if r.violations_passed else "FAIL"
                md_lines.append(f"| {r.scenario} | {r.queries_run} | {r.queries_passed} | {r.parity_rate*100:.1f}% | {v_status} | {status} |")
            Path(report_md).write_text("\n".join(md_lines) + "\n", encoding="utf-8")

        return 0 if all_passed else 2

    elif args.command == "bench":
        data = run_benchmarks()
        json_output = json.dumps(data, indent=2)
        print(json_output)
        if args.save:
            Path(args.save).write_text(json_output, encoding="utf-8")
        if args.budget:
            budgets = json.loads(Path(args.budget).read_text(encoding="utf-8"))
            failed = False
            for k, max_ms in budgets.items():
                actual = data.get(k)
                if actual is not None and actual > max_ms:
                    print(f"Budget exceeded for {k}: {actual}ms > {max_ms}ms", file=sys.stderr)
                    failed = True
            if failed:
                return 2
        return 0

    elif args.command == "gen":
        if args.topology == "chain":
            m = generate_chain(args.size, args.seed)
        elif args.topology == "tree":
            m = generate_tree(args.size, seed=args.seed)
        elif args.topology == "lattice":
            m = generate_lattice(args.size, args.seed)
        elif args.topology == "random_dag":
            m = generate_random_dag(args.size, seed=args.seed)
        elif args.topology == "cyclic":
            m = generate_cyclic(args.size, args.seed)
        print(f"Generated {args.topology} with {len(m.entities)} entities and {len(m.assertions)} assertions.")
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
