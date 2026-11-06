"""Minimal, zero-dependency stdio JSON-RPC 2.0 framing and transport."""

from __future__ import annotations

import json
import sys
from typing import Any, Callable, Optional, TextIO


class StdioTransport:
    """Reads and writes JSON-RPC 2.0 messages over standard I/O streams.

    Supports standard newline-delimited JSON and Content-Length framed JSON-RPC.
    """

    def __init__(self, in_stream: Optional[TextIO] = None, out_stream: Optional[TextIO] = None) -> None:
        self.in_stream = in_stream or sys.stdin
        self.out_stream = out_stream or sys.stdout

    def read_message(self) -> Optional[dict[str, Any]]:
        """Read a single JSON-RPC message from in_stream."""
        line = self.in_stream.readline()
        if not line:
            return None

        # Check for Content-Length framing (LSP / standard MCP)
        if line.lower().startswith("content-length:"):
            try:
                length = int(line.split(":", 1)[1].strip())
            except ValueError:
                return None
            # Consume empty separator line
            sep = self.in_stream.readline()
            while sep.strip() != "":
                sep = self.in_stream.readline()
            payload = self.in_stream.read(length)
            if not payload or len(payload) < length:
                return None
            try:
                return json.loads(payload)
            except json.JSONDecodeError:
                return None

        # Fallback to newline-delimited JSON
        line = line.strip()
        if not line:
            return self.read_message()
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            return None

    def write_message(self, message: dict[str, Any]) -> None:
        """Write a JSON-RPC message to out_stream formatted as NDJSON."""
        payload = json.dumps(message, ensure_ascii=False) + "\n"
        self.out_stream.write(payload)
        self.out_stream.flush()
