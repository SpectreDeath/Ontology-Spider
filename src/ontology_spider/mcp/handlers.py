"""Tool call dispatchers and sandbox guards for the Ontology-Spider MCP server."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from ontology_spider.dialog import DialogAssertion, parse_dialog
from ontology_spider.engine import Session
from ontology_spider.export import to_dialog, to_dot, to_html, to_json
from ontology_spider.model import OntologyModel
from ontology_spider.reasoning.base import ReasonerResult
from ontology_spider.seam import load_imported_model

if TYPE_CHECKING:
    from ontology_spider.mcp.server import MCPServer

MUTATING_TOOLS = frozenset({
    "assert_triple",
    "declare_entity",
    "retract",
    "retract_turn",
    "run_dialog",
    "focus",
    "constrain",
    "session_save",
    "session_restore",
})


def _handle_global_tool(server: MCPServer, name: str, args: dict[str, Any]) -> dict[str, Any] | None:
    """Handle tools that do not require an existing active session_id."""
    if name == "session_open":
        if len(server.sessions.list_sessions()) >= server.max_sessions:
            raise ValueError(f"Session cap exceeded: maximum {server.max_sessions} active sessions allowed.")
        sid = args.get("session_id") or f"sess_{len(server.sessions.list_sessions()) + 1}"
        reasoner = server._get_reasoner()
        model_path = args.get("model_path")
        if model_path:
            resolved = server._resolve_safe_path(model_path)
            model = load_imported_model(resolved, base_dir=server.root_dir, allowed_root=server.root_dir)
            if len(model.assertions) > server.max_assertions_per_session:
                raise ValueError(
                    f"Assertion cap exceeded: loaded model has {len(model.assertions)} assertions "
                    f"(cap: {server.max_assertions_per_session})."
                )
        else:
            model = OntologyModel(uri=args.get("uri") or f"urn:mcp:{sid}")
        session = server.sessions.open_session(
            sid, model,
            reasoner=reasoner,
            base_dir=server.root_dir, allowed_root=server.root_dir,
            timeout_seconds=server.timeout_seconds, max_inferences=server.max_inferences,
        )
        server.dialogue_managers[sid] = session.traversal
        return {"content": [{"type": "text", "text": f"Session '{sid}' opened."}], "sessionId": sid}

    if name == "session_close":
        sid = args["session_id"]
        server.sessions.close_session(sid)
        server.dialogue_managers.pop(sid, None)
        return {"content": [{"type": "text", "text": f"Session '{sid}' closed."}]}

    if name == "session_list":
        sids = server.sessions.list_sessions()
        return {"content": [{"type": "text", "text": json.dumps(sids, indent=2)}], "sessions": sids}

    if name == "session_restore":
        if len(server.sessions.list_sessions()) >= server.max_sessions:
            raise ValueError(f"Session cap exceeded: maximum {server.max_sessions} active sessions allowed.")
        resolved = server._resolve_safe_path(args["path"])
        if not resolved.is_file():
            raise FileNotFoundError(f"Saved session file not found: {args['path']}")
        data = json.loads(resolved.read_text(encoding="utf-8"))
        assertions_count = len(data.get("model", {}).get("assertions", []))
        if assertions_count > server.max_assertions_per_session:
            raise ValueError(
                f"Assertion cap exceeded: saved session has {assertions_count} assertions "
                f"(cap: {server.max_assertions_per_session})."
            )
        restored = Session.from_dict(
            data,
            session_id=args.get("session_id"),
            reasoner=server._get_reasoner(),
            base_dir=server.root_dir, allowed_root=server.root_dir,
            timeout_seconds=server.timeout_seconds, max_inferences=server.max_inferences,
        )
        server.sessions.register_session(restored)
        server.dialogue_managers[restored.session_id] = restored.traversal
        return {
            "content": [{"type": "text", "text": f"Restored session '{restored.session_id}' from {args['path']}."}],
            "sessionId": restored.session_id,
        }

    if name == "engine_info":
        active_reasoner = server._get_reasoner()
        active_backend = active_reasoner.name if active_reasoner else server.engine.active_backend_name
        info = {
            "active_backend": active_backend,
            "backends": server.engine.available_backends,
            "read_only": server.read_only,
            "root_dir": str(server.root_dir),
            "max_sessions": server.max_sessions,
            "max_assertions_per_session": server.max_assertions_per_session,
            "timeout_seconds": server.timeout_seconds,
            "max_inferences": server.max_inferences,
        }
        return {"content": [{"type": "text", "text": json.dumps(info, indent=2)}]}

    return None


def _handle_mutation_tool(
    server: MCPServer,
    session: Session,
    mgr: Any,
    sid: str,
    name: str,
    args: dict[str, Any],
) -> dict[str, Any] | None:
    """Handle session mutation, file import, and persistence tools."""
    if name == "model_load":
        resolved = server._resolve_safe_path(args["path"])
        loaded = load_imported_model(resolved, base_dir=server.root_dir, allowed_root=server.root_dir)
        if len(session.model.assertions) + len(loaded.assertions) > server.max_assertions_per_session:
            raise ValueError(
                f"Assertion cap exceeded: session has {len(session.model.assertions)} assertions, "
                f"loading {len(loaded.assertions)} would exceed cap of {server.max_assertions_per_session}."
            )
        for ent in loaded.entities.values():
            session.model.upsert_entity(ent.id, name=ent.name, attributes=ent.attributes)
        for asrt in loaded.assertions.values():
            session.model.add_assertion(
                asrt.relation,
                asrt.provenance,
                assertion_id=asrt.assertion_id,
                attributes=asrt.attributes,
            )
        return {"content": [{"type": "text", "text": f"Loaded model from {args['path']} into session '{sid}'."}]}

    if name == "assert_triple":
        if len(session.model.assertions) >= server.max_assertions_per_session:
            raise ValueError(f"Assertion cap exceeded: maximum {server.max_assertions_per_session} assertions allowed per session.")
        asrt = session.assert_triple(
            args["subject"],
            args["predicate"],
            args["object"],
            source="mcp",
            attributes=args.get("attributes"),
        )
        return {
            "content": [{"type": "text", "text": f"Asserted: ({args['subject']} {args['predicate']} {args['object']}) [{asrt.assertion_id}]"}],
            "assertion_id": asrt.assertion_id,
            "turn_id": asrt.provenance.turn_id,
        }

    if name == "declare_entity":
        ent = session.declare_entity(args["entity_id"], **args.get("attributes", {}))
        return {"content": [{"type": "text", "text": f"Declared entity: {ent.id}"}]}

    if name == "retract":
        removed = session.retract_assertion(args["assertion_id"])
        text = f"Retracted assertion {args['assertion_id']}" if removed else f"Assertion not found: {args['assertion_id']}"
        return {"content": [{"type": "text", "text": text}], "retracted": removed}

    if name == "retract_turn":
        retracted = session.retract_by_turn(args["turn_id"])
        ids = [a.assertion_id for a in retracted]
        return {
            "content": [{"type": "text", "text": f"Retracted {len(ids)} assertion(s) from turn '{args['turn_id']}'."}],
            "retracted_count": len(ids),
            "retracted_ids": ids,
        }

    if name == "session_save":
        resolved = server._resolve_safe_path(args["path"])
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(json.dumps(session.to_dict(), indent=2), encoding="utf-8")
        return {"content": [{"type": "text", "text": f"Saved session '{sid}' to {args['path']}."}], "path": args["path"]}

    if name == "run_dialog":
        doc = parse_dialog(f"dialog {session.model.uri}\n{args['dialog_text']}")
        pending_assertions = sum(1 for s in doc.statements if isinstance(s, DialogAssertion))
        if len(session.model.assertions) + pending_assertions > server.max_assertions_per_session:
            raise ValueError(f"Assertion cap exceeded: maximum {server.max_assertions_per_session} assertions allowed per session.")
        res = session.run_dialog(args["dialog_text"])
        if len(session.model.assertions) > server.max_assertions_per_session:
            raise ValueError(f"Assertion cap exceeded: maximum {server.max_assertions_per_session} assertions allowed per session.")
        if session.last_query_result is not None:
            mgr.session.last_query_result = ReasonerResult(
                query_goal=session.last_query_result.query_text,
                answers=session.last_query_result.raw_answers,
            )
        return {"content": [{"type": "text", "text": res.summary}]}

    return None


def dispatch_tool_call(server: MCPServer, name: str | None, args: dict[str, Any]) -> dict[str, Any]:
    """Validate permissions and dispatch an MCP tools/call request."""
    if not name:
        raise ValueError("Tool name is required")
    if server.read_only and name in MUTATING_TOOLS:
        raise PermissionError(f"Server is running in read-only mode. Tool '{name}' is forbidden.")

    global_result = _handle_global_tool(server, name, args)
    if global_result is not None:
        return global_result

    sid = args.get("session_id")
    if not sid:
        raise ValueError("session_id is required")
    found_session = server.sessions.get_session(sid)
    if not found_session:
        raise ValueError(f"Session not found: {sid}")
    mgr = server.dialogue_managers.setdefault(sid, found_session.traversal)

    mutation_result = _handle_mutation_tool(server, found_session, mgr, sid, name, args)
    if mutation_result is not None:
        return mutation_result

    if name == "query":
        q_res = mgr.query(args["query"])
        return {
            "content": [{"type": "text", "text": q_res.summary_text}],
            "answers": [ans.to_dict() if hasattr(ans, "to_dict") else {"value": str(ans)} for ans in q_res.answers],
        }
    if name == "explain":
        return {"content": [{"type": "text", "text": mgr.explain()}]}
    if name == "validate":
        violations = server.validator.validate(found_session.model)
        return {
            "content": [{"type": "text", "text": f"Validation found {len(violations)} violation(s)."}],
            "violations": [v.to_dict() for v in violations],
        }
    if name == "export":
        fmt = args["format"]
        exporters: dict[str, Callable[[OntologyModel], str]] = {
            "json": to_json,
            "dialog": to_dialog,
            "dot": to_dot,
            "html": to_html,
        }
        exporter = exporters.get(fmt)
        if exporter is None:
            raise ValueError(f"Unknown format: {fmt}")
        return {"content": [{"type": "text", "text": exporter(found_session.model)}], "format": fmt}
    if name == "focus":
        return {"content": [{"type": "text", "text": mgr.set_focus(args["entity_id"], args.get("constraints"))}]}
    if name == "constrain":
        return {"content": [{"type": "text", "text": mgr.change_constraint(args["key"], args["value"])}]}
    if name == "where_am_i":
        return {"content": [{"type": "text", "text": mgr.where_am_i()}]}

    raise ValueError(f"Unknown tool: {name}")
