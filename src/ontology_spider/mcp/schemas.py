"""JSONSchema tool registry for the Ontology-Spider MCP server."""

from __future__ import annotations

from typing import Any


def get_mcp_tools_schema() -> list[dict[str, Any]]:
    """Return the MCP tools/list metadata payload for all exposed tools."""
    return [
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
                "properties": {"session_id": {"type": "string"}},
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
            "name": "retract_turn",
            "description": "Retract all assertions produced during a given turn_id from a session.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                    "turn_id": {"type": "string"},
                },
                "required": ["session_id", "turn_id"],
            },
        },
        {
            "name": "session_save",
            "description": "Save a session (model, turn counter, and traversal frame stack) to a JSON file within root.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                    "path": {"type": "string", "description": "Relative file path within server root."},
                },
                "required": ["session_id", "path"],
            },
        },
        {
            "name": "session_restore",
            "description": "Restore a previously saved session from a JSON file within root.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative file path within server root."},
                    "session_id": {"type": "string", "description": "Optional override session ID."},
                },
                "required": ["path"],
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
            "description": "Execute an ontological query (lookup, ancestors, transitive, recommend, path, not, count).",
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
                "properties": {"session_id": {"type": "string"}},
                "required": ["session_id"],
            },
        },
        {
            "name": "validate",
            "description": "Validate session ontology for cycles and constraint violations.",
            "inputSchema": {
                "type": "object",
                "properties": {"session_id": {"type": "string"}},
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
                "properties": {"session_id": {"type": "string"}},
                "required": ["session_id"],
            },
        },
        {
            "name": "engine_info",
            "description": "Return reasoner backend availability, version, and performance info.",
            "inputSchema": {"type": "object", "properties": {}},
        },
    ]
