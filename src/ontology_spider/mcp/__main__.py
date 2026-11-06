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
    parser.add_argument("--read-only", action="store_true", help="Disallow mutating sessions or models")
    parser.add_argument("--root", default=str(Path.cwd()), help="Root filesystem sandbox path")

    args = parser.parse_args(argv)

    root_path = Path(args.root).resolve()
    transport = StdioTransport()
    server = MCPServer(transport=transport, read_only=args.read_only, root_dir=root_path)
    server.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
