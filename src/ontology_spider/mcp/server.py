"""Stdio JSON-RPC 2.0 Model Context Protocol (MCP) server for Ontology-Spider.

Exposes ontology management, elicitation, conversational traversal, and reasoning
tools and resources without external dependencies.
"""

from __future__ import annotations

import importlib.metadata
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ontology_spider.engine import Engine
from ontology_spider.export import to_json
from ontology_spider.mcp.handlers import dispatch_tool_call
from ontology_spider.mcp.schemas import get_mcp_tools_schema
from ontology_spider.mcp.transport import StdioTransport
from ontology_spider.seam import load_imported_model
from ontology_spider.traversal import TraversalDialogueManager
from ontology_spider.validation import OntologyValidator


class MCPServer:
    """Stdio JSON-RPC 2.0 MCP server implementation."""

    def __init__(
        self,
        transport: StdioTransport | None = None,
        read_only: bool = False,
        root_dir: Path | None = None,
        max_sessions: int = 32,
        max_assertions_per_session: int = 50_000,
        timeout_seconds: float = 10.0,
        max_inferences: int = 1_000_000,
        backend: str | None = None,
        preload_model_path: Path | None = None,
    ) -> None:
        self.transport = transport or StdioTransport()
        self.read_only = read_only
        self.root_dir = (root_dir or Path.cwd()).resolve()
        self.max_sessions = max_sessions
        self.max_assertions_per_session = max_assertions_per_session
        self.timeout_seconds = float(timeout_seconds)
        self.max_inferences = max_inferences
        self.backend = backend
        self.engine = Engine()
        self.sessions = self.engine.session_manager
        self.dialogue_managers: dict[str, TraversalDialogueManager] = {}
        self.validator = OntologyValidator()
        self._cancelled_requests: set[Any] = set()

        self._handlers: dict[str, Callable[[Any], Any]] = {
            "initialize": self._handle_initialize,
            "notifications/initialized": self._handle_noop,
            "notifications/cancelled": self._handle_cancelled,
            "ping": self._handle_ping,
            "tools/list": self._handle_tools_list,
            "tools/call": self._handle_tools_call,
            "resources/list": self._handle_resources_list,
            "resources/read": self._handle_resources_read,
        }

        if preload_model_path:
            resolved = self._resolve_safe_path(str(preload_model_path))
            loaded = load_imported_model(resolved, base_dir=self.root_dir, allowed_root=self.root_dir)
            reasoner = self._get_reasoner()
            session = self.sessions.open_session(
                "default",
                loaded,
                reasoner=reasoner,
                base_dir=self.root_dir,
                allowed_root=self.root_dir,
                timeout_seconds=self.timeout_seconds,
                max_inferences=self.max_inferences,
            )
            self.dialogue_managers["default"] = session.traversal

    def _get_reasoner(self) -> Any | None:
        if self.backend == "python":
            from ontology_spider.reasoning.python_backend import PythonReasoner
            return PythonReasoner()
        if self.backend == "prolog":
            from ontology_spider.prolog.reasoner import PrologReasoner
            return PrologReasoner()
        return None

    def _resolve_safe_path(self, path_str: str) -> Path:
        """Resolve path and verify it stays within root_dir sandbox."""
        p = (self.root_dir / path_str).resolve()
        try:
            p.relative_to(self.root_dir)
        except ValueError as exc:
            raise PermissionError(f"Access denied: path '{path_str}' is outside root '{self.root_dir}'") from exc
        return p

    def run(self) -> None:
        """Main event loop reading from transport until EOF."""
        while True:
            try:
                msg = self.transport.read_message()
            except Exception as e:
                print(f"Transport read error: {e}", file=sys.stderr)
                break
            if msg is None:
                break

            msg_id = msg.get("id")
            method = msg.get("method")
            params = msg.get("params", {})

            if not method:
                continue

            if msg_id is not None and msg_id in self._cancelled_requests:
                self._cancelled_requests.discard(msg_id)
                continue

            handler = self._handlers.get(method)
            if not handler:
                if msg_id is not None:
                    self.transport.write_message({
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "error": {"code": -32601, "message": f"Method not found: {method}"},
                    })
                continue

            try:
                result = handler(params)
                if msg_id is not None and msg_id in self._cancelled_requests:
                    self._cancelled_requests.discard(msg_id)
                    continue
                if msg_id is not None:
                    self.transport.write_message({"jsonrpc": "2.0", "id": msg_id, "result": result})
            except Exception as e:
                if msg_id is not None and msg_id in self._cancelled_requests:
                    self._cancelled_requests.discard(msg_id)
                    continue
                if msg_id is not None:
                    code = -32001 if isinstance(e, PermissionError) else -32000
                    self.transport.write_message({
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "error": {"code": code, "message": str(e)},
                    })

    def _handle_initialize(self, params: dict[str, Any]) -> dict[str, Any]:
        try:
            pkg_version = importlib.metadata.version("ontology-spider")
        except importlib.metadata.PackageNotFoundError:
            pkg_version = "0.2.0"
        return {
            "protocolVersion": "2024-11-05",
            "serverInfo": {"name": "ontology-spider", "version": pkg_version},
            "capabilities": {"tools": {}, "resources": {}},
        }

    def _handle_noop(self, params: dict[str, Any]) -> None:
        return None

    def _handle_cancelled(self, params: dict[str, Any]) -> None:
        req_id = params.get("requestId")
        if req_id is not None:
            self._cancelled_requests.add(req_id)

    def _handle_ping(self, params: dict[str, Any]) -> dict[str, Any]:
        return {}

    def _handle_tools_list(self, params: dict[str, Any]) -> dict[str, Any]:
        return {"tools": get_mcp_tools_schema()}

    def _handle_tools_call(self, params: dict[str, Any]) -> dict[str, Any]:
        return dispatch_tool_call(self, params.get("name"), params.get("arguments", {}))

    def _handle_resources_list(self, params: dict[str, Any]) -> dict[str, Any]:
        resources = [
            {
                "uri": "ontology://docs/language-reference",
                "name": "Ontology Dialog Language Reference",
                "mimeType": "text/markdown",
            }
        ]
        for sid in self.sessions.list_sessions():
            resources.append({
                "uri": f"ontology://session/{sid}/model.json",
                "name": f"Session '{sid}' Model JSON",
                "mimeType": "application/json",
            })
        examples_dir = self.root_dir / "examples"
        if not examples_dir.is_dir():
            pkg_examples = Path(__file__).resolve().parent.parent.parent.parent / "examples"
            if pkg_examples.is_dir():
                examples_dir = pkg_examples
        if examples_dir.is_dir():
            for f in sorted(examples_dir.glob("*.dialog")):
                resources.append({
                    "uri": f"ontology://examples/{f.stem}",
                    "name": f"Example ontology: {f.name}",
                    "mimeType": "text/plain",
                })
        return {"resources": resources}

    def _handle_resources_read(self, params: dict[str, Any]) -> dict[str, Any]:
        uri = params.get("uri", "")
        if uri == "ontology://docs/language-reference":
            ref_path = self.root_dir / "docs" / "language_reference.md"
            if not ref_path.is_file():
                pkg_doc = Path(__file__).resolve().parent.parent.parent.parent / "docs" / "language_reference.md"
                if pkg_doc.is_file():
                    ref_path = pkg_doc
            text = ref_path.read_text(encoding="utf-8") if ref_path.is_file() else "Language reference not found."
            return {"contents": [{"uri": uri, "mimeType": "text/markdown", "text": text}]}

        if uri.startswith("ontology://session/") and uri.endswith("/model.json"):
            sid = uri.split("/")[3]
            sess = self.sessions.get_session(sid)
            if not sess:
                raise ValueError(f"Session not found: {sid}")
            return {"contents": [{"uri": uri, "mimeType": "application/json", "text": to_json(sess.model)}]}

        if uri.startswith("ontology://examples/"):
            parts = uri.split("/")
            if len(parts) < 4:
                raise ValueError(f"Invalid resource URI: {uri}")
            stem = parts[3]
            if ".." in stem or "/" in stem or "\\" in stem:
                raise PermissionError(f"Access denied: invalid stem '{stem}'")
            rel_candidate = Path("examples") / f"{stem}.dialog"
            try:
                safe_f = self._resolve_safe_path(str(rel_candidate))
            except PermissionError:
                safe_f = None
            if safe_f and safe_f.is_file():
                f = safe_f
            else:
                pkg_f = Path(__file__).resolve().parent.parent.parent.parent / "examples" / f"{stem}.dialog"
                if pkg_f.is_file():
                    f = pkg_f
                else:
                    raise ValueError(f"Example not found: {stem}")
            return {"contents": [{"uri": uri, "mimeType": "text/plain", "text": f.read_text(encoding="utf-8")}]}

        raise ValueError(f"Unknown resource URI: {uri}")
