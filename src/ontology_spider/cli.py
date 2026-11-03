"""CLI interface for running .dialog files and launching interactive REPL."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ontology_spider.dialog import ParseError, parse_dialog
from ontology_spider.dialog_runner import DialogSession


def run_batch(file_path: str) -> int:
    """Execute a dialog script in batch mode."""
    path = Path(file_path)
    if not path.is_file():
        print(f"Error: Dialog file not found: {path}", file=sys.stderr)
        return 1

    session = DialogSession(base_dir=path.parent)
    try:
        results = session.run_file(path)
        for res in results:
            print(res.summary_text)
            if res.statement_type == "query":
                for ans in res.answers:
                    print(f"  -> {ans.value}")
        return 0
    except ParseError as err:
        print(f"Parse error in {path}: {err}", file=sys.stderr)
        return 2
    except Exception as err:
        print(f"Runtime error: {err}", file=sys.stderr)
        return 3


def run_repl() -> int:
    """Launch interactive Dialog REPL."""
    print("Ontology-Spider Dialog REPL")
    print("Type assertions or queries. Commands: 'exit', 'quit', 'where am I'.")
    print("-" * 50)

    session = DialogSession()

    while True:
        try:
            line = input("dialog> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting REPL.")
            break

        if not line:
            continue
        if line.lower() in ("exit", "quit", ":q"):
            print("Goodbye.")
            break
        if line.lower() in ("where am i", "where am i?"):
            print(f"Active URI: {session.model.uri}")
            print(f"Total entities: {len(session.model.entities)}")
            print(f"Total assertions: {len(session.model.assertions)}")
            continue

        try:
            doc = parse_dialog(f"dialog urn:repl\n{line}")
            for stmt in doc.statements:
                res = session.execute_statement(stmt)
                print(res.summary_text)
                if res.statement_type == "query":
                    for ans in res.answers:
                        print(f"  -> {ans.value}")
        except ParseError as err:
            print(f"Parse error: {err}", file=sys.stderr)
        except Exception as err:
            print(f"Error: {err}", file=sys.stderr)

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="dialog",
        description="Ontology-Spider conversational ontological engine CLI",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # run command
    run_parser = subparsers.add_parser("run", help="Run a .dialog script in batch mode")
    run_parser.add_argument("file", help="Path to .dialog file")

    # repl command
    subparsers.add_parser("repl", help="Start interactive dialog REPL session")

    args = parser.parse_args(argv)

    if args.command == "run":
        return run_batch(args.file)
    elif args.command == "repl":
        return run_repl()

    return 0


if __name__ == "__main__":
    sys.exit(main())
