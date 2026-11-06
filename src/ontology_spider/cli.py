"""CLI interface for running, validating, exporting, eliciting, and REPL traversal."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

from ontology_spider.api import export_model, load_model
from ontology_spider.dialog import ParseError, parse_dialog
from ontology_spider.dialog_runner import DialogSession
from ontology_spider.elicitation import ElicitationManager, ElicitationState
from ontology_spider.model import OntologyModel
from ontology_spider.traversal import TraversalDialogueManager
from ontology_spider.validation import OntologyValidator, validate_model_hook


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


def run_validate(file_path: str) -> int:
    """Validate ontology constraints and assumptions."""
    path = Path(file_path)
    if not path.is_file():
        print(f"Error: Ontology file not found: {path}", file=sys.stderr)
        return 1

    try:
        model = load_model(path)
        validator = OntologyValidator()
        violations = validator.validate(model)
        if not violations:
            print(f"Validation passed: 0 violations found in {path.name}.")
            return 0
        print(f"Validation failed with {len(violations)} violation(s):")
        for v in violations:
            print(f"  {v.summary()}")
        return 1
    except Exception as err:
        print(f"Error during validation: {err}", file=sys.stderr)
        return 3


def run_export(
    file_path: str, format: str = "json", output_path: Optional[str] = None
) -> int:
    """Export an ontology to JSON, .dialog, DOT, or HTML."""
    path = Path(file_path)
    if not path.is_file():
        print(f"Error: Ontology file not found: {path}", file=sys.stderr)
        return 1

    try:
        model = load_model(path)
        content = export_model(model, format=format)
        if output_path:
            out = Path(output_path)
            out.write_text(content, encoding="utf-8")
            print(f"Exported {model.uri} to {out} ({format}).")
        else:
            print(content)
        return 0
    except Exception as err:
        print(f"Error during export: {err}", file=sys.stderr)
        return 3


def run_elicit(output_path: Optional[str] = None) -> int:
    """Launch a 4-stage guided elicitation session."""
    print("Ontology-Spider Guided Elicitation Session")
    print("Follow prompts to author an ontology. Type 'exit' to quit.")
    print("-" * 50)
    manager = ElicitationManager(validation_hook=validate_model_hook)
    prompt = manager.start()
    print(prompt)

    while manager.stage != ElicitationState.COMPLETED:
        try:
            line = input("elicit> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nElicitation session interrupted.")
            break

        if not line:
            continue
        if line.lower() in ("exit", "quit", ":q"):
            print("Elicitation aborted.")
            return 0

        response = manager.handle_input(line)
        print(response)

    if output_path:
        out = Path(output_path)
        dialog_text = export_model(manager.model, format="dialog")
        out.write_text(dialog_text, encoding="utf-8")
        print(f"Saved elicited ontology to {out}.")

    return 0


def run_repl(file_path: Optional[str] = None) -> int:
    """Launch interactive Dialog REPL with conversational frame stack."""
    print("Ontology-Spider Conversational Traversal REPL")
    print(
        "Commands: 'where am I', 'focus <entity>', 'constrain <key>=<val>', "
        "'validate', 'export <fmt>', 'exit'."
    )
    print("-" * 50)

    model = None
    if file_path:
        p = Path(file_path)
        if p.is_file():
            model = load_model(p)
            print(f"Loaded ontology from {p.name} ({len(model.assertions)} assertions).")

    traversal = TraversalDialogueManager(
        model=model or OntologyModel(uri="urn:dialog:repl")
    )

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
            print(traversal.where_am_i())
            continue

        if line.lower().startswith("focus "):
            ent_id = line[6:].strip()
            print(traversal.set_focus(ent_id))
            continue

        if line.lower().startswith("constrain "):
            c_part = line[10:].strip()
            if "=" in c_part:
                k, v = c_part.split("=", 1)
                print(traversal.change_constraint(k.strip(), v.strip()))
            else:
                print("Usage: constrain <key>=<value>")
            continue

        if line.lower() == "validate":
            validator = OntologyValidator()
            violations = validator.validate(traversal.model)
            if not violations:
                print("Validation passed: 0 violations.")
            else:
                for v in violations:
                    print(f"  {v.summary()}")
            continue

        if line.lower().startswith("export "):
            fmt = line[7:].strip()
            try:
                print(export_model(traversal.model, format=fmt))
            except Exception as err:
                print(f"Export error: {err}", file=sys.stderr)
            continue

        if line.lower() == "explain":
            print(traversal.explain())
            continue

        try:
            doc = parse_dialog(f"dialog {traversal.model.uri}\n{line}")
            for stmt in doc.statements:
                if stmt.__class__.__name__ == "DialogQuery":
                    res = traversal.query(line)
                else:
                    res = traversal.session.execute_statement(stmt)
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

    # validate command
    val_parser = subparsers.add_parser(
        "validate", help="Validate an ontology against integrity rules"
    )
    val_parser.add_argument("file", help="Path to ontology file (.dialog or .json)")

    # export command
    exp_parser = subparsers.add_parser(
        "export", help="Export an ontology to json, dialog, dot, or html"
    )
    exp_parser.add_argument("file", help="Path to ontology file (.dialog or .json)")
    exp_parser.add_argument(
        "--format",
        default="json",
        choices=["json", "dialog", "dot", "html"],
        help="Export format",
    )
    exp_parser.add_argument("-o", "--output", help="Optional output file path")

    # elicit command
    elicit_parser = subparsers.add_parser(
        "elicit", help="Start 4-stage guided elicitation session"
    )
    elicit_parser.add_argument(
        "-o", "--output", help="Optional path to save elicited .dialog file"
    )

    # repl command
    repl_parser = subparsers.add_parser(
        "repl", help="Start interactive dialog REPL session"
    )
    repl_parser.add_argument(
        "-f", "--file", help="Optional path to preload an ontology into REPL"
    )

    # mcp command
    mcp_parser = subparsers.add_parser(
        "mcp", help="Run stdio JSON-RPC 2.0 MCP server"
    )
    mcp_parser.add_argument("--read-only", action="store_true", help="Disallow mutating sessions or models")
    mcp_parser.add_argument("--root", default=str(Path.cwd()), help="Root filesystem sandbox path")

    args = parser.parse_args(argv)

    if args.command == "run":
        return run_batch(args.file)
    elif args.command == "validate":
        return run_validate(args.file)
    elif args.command == "export":
        return run_export(args.file, format=args.format, output_path=args.output)
    elif args.command == "elicit":
        return run_elicit(output_path=args.output)
    elif args.command == "repl":
        return run_repl(file_path=args.file)
    elif args.command == "mcp":
        from ontology_spider.mcp.server import MCPServer
        from ontology_spider.mcp.transport import StdioTransport
        server = MCPServer(transport=StdioTransport(), read_only=args.read_only, root_dir=Path(args.root))
        server.run()
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
