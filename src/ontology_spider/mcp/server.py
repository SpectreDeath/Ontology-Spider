"""Stdio JSON-RPC 2.0 Model Context Protocol (MCP) server for Ontology-Spider.

Exposes ontology management, elicitation, conversational traversal, and reasoning
tools and resources without external dependencies.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ontology_spider.engine import Engine
from ontology_spider.export import to_dialog, to_dot, to_html, to_json
from ontology_spider.mcp.transport import StdioTransport
from ontology_spider.model import OntologyModel
from ontology_spider.seam import DialogModelSource
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

        # Method registry
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
            loaded = DialogModelSource(resolved).load()
            reasoner = self._get_reasoner()
            session = self.sessions.open_session(
                "default",
                loaded,
                reasoner=reasoner,
                timeout_seconds=self.timeout_seconds,
                max_inferences=self.max_inferences,
            )
            self.dialogue_managers["default"] = session.traversal

    def _get_reasoner(self) -> Any | None:
        if self.backend == "python":
            from ontology_spider.reasoning.python_backend import PythonReasoner
            return PythonReasoner()
        elif self.backend == "prolog":
            from ontology_spider.prolog.reasoner import PrologReasoner
            return PrologReasoner()
        return None

    def _resolve_safe_path(self, path_str: str) -> Path:
        """Resolve path and verify it stays within root_dir sandbox."""
        p = (self.root_dir / path_str).resolve()
        try:
            p.relative_to(self.root_dir)
        except ValueError:
            raise PermissionError(f"Access denied: path '{path_str}' is outside root '{self.root_dir}'")
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
                    self.transport.write_message({
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "result": result,
                    })
            except Exception as e:
                if msg_id is not None and msg_id in self._cancelled_requests:
                    self._cancelled_requests.discard(msg_id)
                    continue
                if msg_id is not None:
                    code = -32000
                    if isinstance(e, PermissionError):
                        code = -32001
                    self.transport.write_message({
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "error": {"code": code, "message": str(e)},
                    })

    def _handle_initialize(self, params: dict[str, Any]) -> dict[str, Any]:
        return {
            "protocolVersion": "2024-11-05",
            "serverInfo": {
                "name": "ontology-spider",
                "version": "0.1.0",
            },
            "capabilities": {
                "tools": {},
                "resources": {},
            },
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
        tools = [
            {
                "name": "session_open",
                "description": "Open a new ontology session with an optional URI or model path.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string", "description": "Optional custom session ID."},
                        "uri": {"type": "string", "description": "Ontology URI (default: urn:mcp:default)."},
                        "model_path": {"type": "string", "description": "Relative path to .dialog file to load."},
                    },
                },
            },
            {
                "name": "session_close",
                "description": "Close an active ontology session.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string"},
                    },
                    "required": ["session_id"],
                },
            },
            {
                "name": "session_list",
                "description": "List all currently open sessions and active frames.",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "model_load",
                "description": "Load an ontology file into a session.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string"},
                        "path": {"type": "string", "description": "File path relative to server root."},
                    },
                    "required": ["session_id", "path"],
                },
            },
            {
                "name": "assert_triple",
                "description": "Assert a triple (subject predicate object) into a session.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string"},
                        "subject": {"type": "string"},
                        "predicate": {"type": "string"},
                        "object": {"type": "string"},
                        "attributes": {"type": "object", "description": "Optional assertion attributes."},
                    },
                    "required": ["session_id", "subject", "predicate", "object"],
                },
            },
            {
                "name": "declare_entity",
                "description": "Declare an entity with optional attributes.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string"},
                        "entity_id": {"type": "string"},
                        "attributes": {"type": "object"},
                    },
                    "required": ["session_id", "entity_id"],
                },
            },
            {
                "name": "retract",
                "description": "Retract an assertion by assertion_id from a session.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string"},
                        "assertion_id": {"type": "string"},
                    },
                    "required": ["session_id", "assertion_id"],
                },
            },
            {
                "name": "run_dialog",
                "description": "Run a multi-statement dialog script against a session.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string"},
                        "dialog_text": {"type": "string"},
                    },
                    "required": ["session_id", "dialog_text"],
                },
            },
            {
                "name": "query",
                "description": "Execute an ontological query (lookup, ancestors, transitive, recommend).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string"},
                        "query": {"type": "string", "description": "e.g. 'query what is felix?' or 'query recommend delivery_drone'"},
                    },
                    "required": ["session_id", "query"],
                },
            },
            {
                "name": "explain",
                "description": "Explain how answers to the last query were derived.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string"},
                    },
                    "required": ["session_id"],
                },
            },
            {
                "name": "validate",
                "description": "Validate session ontology for cycles and constraint violations.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string"},
                    },
                    "required": ["session_id"],
                },
            },
            {
                "name": "export",
                "description": "Export session ontology to json, dialog, dot, or html.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string"},
                        "format": {"type": "string", "enum": ["json", "dialog", "dot", "html"]},
                    },
                    "required": ["session_id", "format"],
                },
            },
            {
                "name": "focus",
                "description": "Push conversational subdialogue frame focusing on an entity.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string"},
                        "entity_id": {"type": "string"},
                        "constraints": {"type": "object"},
                    },
                    "required": ["session_id", "entity_id"],
                },
            },
            {
                "name": "constrain",
                "description": "Update active constraint in conversational frame.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string"},
                        "key": {"type": "string"},
                        "value": {"type": "string"},
                    },
                    "required": ["session_id", "key", "value"],
                },
            },
            {
                "name": "where_am_i",
                "description": "Inspect conversational frame stack and active focus/constraints.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string"},
                    },
                    "required": ["session_id"],
                },
            },
            {
                "name": "engine_info",
                "description": "Return reasoner backend availability, version, and performance info.",
                "inputSchema": {"type": "object", "properties": {}},
            },
        ]
        return {"tools": tools}

    def _handle_tools_call(self, params: dict[str, Any]) -> dict[str, Any]:
        name = params.get("name")
        args = params.get("arguments", {})

        mutating_tools = {"assert_triple", "declare_entity", "retract", "run_dialog", "focus", "constrain"}
        if self.read_only and name in mutating_tools:
            raise PermissionError(f"Server is running in read-only mode. Tool '{name}' is forbidden.")

        if name == "session_open":
            if len(self.sessions.list_sessions()) >= self.max_sessions:
                raise ValueError(f"Session cap exceeded: maximum {self.max_sessions} active sessions allowed.")
            sid = args.get("session_id") or f"sess_{len(self.sessions.list_sessions()) + 1}"
            model_path = args.get("model_path")
            reasoner = self._get_reasoner()
            if model_path:
                resolved = self._resolve_safe_path(model_path)
                model = DialogModelSource(resolved).load()
                if len(model.assertions) > self.max_assertions_per_session:
                    raise ValueError(f"Assertion cap exceeded: loaded model has {len(model.assertions)} assertions (cap: {self.max_assertions_per_session}).")
                session = self.sessions.open_session(
                    sid,
                    model,
                    reasoner=reasoner,
                    timeout_seconds=self.timeout_seconds,
                    max_inferences=self.max_inferences,
                )
            else:
                uri = args.get("uri") or f"urn:mcp:{sid}"
                session = self.sessions.open_session(
                    sid,
                    OntologyModel(uri=uri),
                    reasoner=reasoner,
                    timeout_seconds=self.timeout_seconds,
                    max_inferences=self.max_inferences,
                )
            self.dialogue_managers[sid] = session.traversal
            return {"content": [{"type": "text", "text": f"Session '{sid}' opened."}], "sessionId": sid}

        elif name == "session_close":
            sid = args["session_id"]
            self.sessions.close_session(sid)
            self.dialogue_managers.pop(sid, None)
            return {"content": [{"type": "text", "text": f"Session '{sid}' closed."}]}

        elif name == "session_list":
            sids = self.sessions.list_sessions()
            return {"content": [{"type": "text", "text": json.dumps(sids, indent=2)}], "sessions": sids}

        elif name == "engine_info":
            active_reasoner = self._get_reasoner()
            active_backend = active_reasoner.name if active_reasoner else self.engine.active_backend_name
            info = {
                "active_backend": active_backend,
                "backends": self.engine.available_backends,
                "read_only": self.read_only,
                "root_dir": str(self.root_dir),
                "max_sessions": self.max_sessions,
                "max_assertions_per_session": self.max_assertions_per_session,
                "timeout_seconds": self.timeout_seconds,
                "max_inferences": self.max_inferences,
            }
            return {"content": [{"type": "text", "text": json.dumps(info, indent=2)}]}

        sid = args.get("session_id")
        if not sid:
            raise ValueError("session_id is required")

        found_session = self.sessions.get_session(sid)
        if not found_session:
            raise ValueError(f"Session not found: {sid}")
        session = found_session
        mgr = self.dialogue_managers.setdefault(sid, session.traversal)

        if name == "model_load":
            resolved = self._resolve_safe_path(args["path"])
            loaded = DialogModelSource(resolved).load()
            if len(session.model.assertions) + len(loaded.assertions) > self.max_assertions_per_session:
                raise ValueError(
                    f"Assertion cap exceeded: session has {len(session.model.assertions)} assertions, "
                    f"loading {len(loaded.assertions)} would exceed cap of {self.max_assertions_per_session}."
                )
            for ent in loaded.entities.values():
                session.model.upsert_entity(ent.id, **dict(ent.attributes))
            for asrt in loaded.assertions.values():
                session.model.add_assertion(asrt.relation, asrt.provenance, **dict(asrt.attributes))
            return {"content": [{"type": "text", "text": f"Loaded model from {args['path']} into session '{sid}'."}]}

        elif name == "assert_triple":
            if len(session.model.assertions) >= self.max_assertions_per_session:
                raise ValueError(f"Assertion cap exceeded: maximum {self.max_assertions_per_session} assertions allowed per session.")
            asrt = session.assert_triple(
                args["subject"],
                args["predicate"],
                args["object"],
                source="mcp",
                **args.get("attributes", {}),
            )
            return {"content": [{"type": "text", "text": f"Asserted: ({args['subject']} {args['predicate']} {args['object']}) [{asrt.assertion_id}]"}]}

        elif name == "declare_entity":
            ent = session.declare_entity(args["entity_id"], **args.get("attributes", {}))
            return {"content": [{"type": "text", "text": f"Declared entity: {ent.id}"}]}

        elif name == "retract":
            session.retract_assertion(args["assertion_id"])
            return {"content": [{"type": "text", "text": f"Retracted assertion {args['assertion_id']}"}]}

        elif name == "run_dialog":
            if len(session.model.assertions) >= self.max_assertions_per_session:
                raise ValueError(f"Assertion cap exceeded: maximum {self.max_assertions_per_session} assertions allowed per session.")
            res = session.run_dialog(args["dialog_text"])
            if len(session.model.assertions) > self.max_assertions_per_session:
                raise ValueError(f"Assertion cap exceeded: maximum {self.max_assertions_per_session} assertions allowed per session.")
            return {"content": [{"type": "text", "text": res.summary}]}

        elif name == "query":
            q_res = mgr.query(args["query"])
            return {
                "content": [{"type": "text", "text": q_res.summary_text}],
                "answers": [ans.to_dict() if hasattr(ans, "to_dict") else {"value": str(ans)} for ans in q_res.answers],
            }

        elif name == "explain":
            exp_text = mgr.explain()
            return {"content": [{"type": "text", "text": exp_text}]}

        elif name == "validate":
            violations = self.validator.validate(session.model)
            v_dicts = [v.to_dict() for v in violations]
            return {
                "content": [{"type": "text", "text": f"Validation found {len(violations)} violation(s)."}],
                "violations": v_dicts,
            }

        elif name == "export":
            fmt = args["format"]
            if fmt == "json":
                out = to_json(session.model)
            elif fmt == "dialog":
                out = to_dialog(session.model)
            elif fmt == "dot":
                out = to_dot(session.model)
            elif fmt == "html":
                out = to_html(session.model)
            else:
                raise ValueError(f"Unknown format: {fmt}")
            return {"content": [{"type": "text", "text": out}], "format": fmt}

        elif name == "focus":
            msg = mgr.set_focus(args["entity_id"], args.get("constraints"))
            return {"content": [{"type": "text", "text": msg}]}

        elif name == "constrain":
            msg = mgr.change_constraint(args["key"], args["value"])
            return {"content": [{"type": "text", "text": msg}]}

        elif name == "where_am_i":
            msg = mgr.where_am_i()
            return {"content": [{"type": "text", "text": msg}]}

        else:
            raise ValueError(f"Unknown tool: {name}")

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
