"""Entrypoint for `python -m ontology_spider.mcp` stdio MCP server."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ontology_spider.mcp.server import MCPServer
from ontology_spider.mcp.transport import StdioTransport


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="ontology-spider-mcp",
        description="Stdio JSON-RPC 2.0 MCP server for Ontology-Spider",
    )
    parser.add_argument("--model", help="Optional path to preload an ontology into default session")
    parser.add_argument(
        "--backend",
        choices=["prolog", "python", "auto"],
        default="auto",
        help="Reasoner backend selection",
    )
    parser.add_argument("--read-only", action="store_true", help="Disallow mutating sessions or models")
    parser.add_argument("--root", default=str(Path.cwd()), help="Root filesystem sandbox path")
    parser.add_argument("--max-sessions", type=int, default=32, help="Maximum concurrent active sessions (default: 32)")
    parser.add_argument("--max-assertions", type=int, default=50_000, help="Maximum assertions allowed per session (default: 50000)")
    parser.add_argument("--timeout", type=float, default=10.0, help="Per-query timeout limit in seconds (default: 10.0)")
    parser.add_argument("--max-inferences", type=int, default=1_000_000, help="Maximum inferences allowed per query (default: 1000000)")

    args = parser.parse_args(argv)

    root_path = Path(args.root).resolve()
    transport = StdioTransport()
    server = MCPServer(
        transport=transport,
        read_only=args.read_only,
        root_dir=root_path,
        max_sessions=args.max_sessions,
        max_assertions_per_session=args.max_assertions,
        timeout_seconds=args.timeout,
        max_inferences=args.max_inferences,
        backend=None if args.backend == "auto" else args.backend,
        preload_model_path=Path(args.model) if args.model else None,
    )
    server.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
