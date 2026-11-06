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

    # parity command
    parity_parser = subparsers.add_parser("parity", help="Run parity diff between Prolog and Python backends")
    parity_parser.add_argument("--model", default="examples/drones.dialog", help="Model file path")

    # bench command
    bench_parser = subparsers.add_parser("bench", help="Run performance benchmarks")
    bench_parser.add_argument("--save", help="Optional path to write benchmark json output")

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

    elif args.command == "corpus":
        corpus_dir = Path(args.dir)
        scenario_files = list(corpus_dir.glob("*.scenario.json"))
        if not scenario_files:
            print(f"No scenario files found in {corpus_dir}", file=sys.stderr)
            return 1

        runner = HarnessRunner()
        all_passed = True
        for sf in scenario_files:
            spec = json.loads(sf.read_text(encoding="utf-8"))
            m_path = Path(spec["model"])
            if not m_path.is_file():
                print(f"Scenario {spec['scenario']}: model not found {m_path}", file=sys.stderr)
                all_passed = False
                continue
            model = load_model(m_path)
            report = runner.run_parity(model, spec["queries"])
            print(f"Scenario [{spec['scenario']}]: {report.passed_queries}/{report.total_queries} queries matched ({report.parity_rate*100:.1f}%)")
            if report.parity_rate < 1.0:
                all_passed = False
                for d in report.diffs:
                    print(f"  - Query: {d.query}")
                    print(f"    Prolog: {d.prolog_answers}")
                    print(f"    Python: {d.python_answers}")

        return 0 if all_passed else 2

    elif args.command == "bench":
        data = run_benchmarks()
        json_output = json.dumps(data, indent=2)
        print(json_output)
        if args.save:
            Path(args.save).write_text(json_output, encoding="utf-8")
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
