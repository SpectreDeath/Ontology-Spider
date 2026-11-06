import io
import json
import unittest
from pathlib import Path

from ontology_spider.mcp.server import MCPServer
from ontology_spider.mcp.transport import StdioTransport


class FakeStreamTransport(StdioTransport):
    def __init__(self, in_text: str = ""):
        self.in_stream = io.StringIO(in_text)
        self.out_stream = io.StringIO()

    def get_output_messages(self) -> list[dict]:
        output = self.out_stream.getvalue().encode("utf-8")
        messages = []
        pos = 0
        while pos < len(output):
            idx = output.find(b"Content-Length:", pos)
            if idx == -1:
                break
            sep_idx = output.find(b"\r\n\r\n", idx)
            if sep_idx == -1:
                break
            header = output[idx:sep_idx].decode("utf-8")
            length = int(header.split(":", 1)[1].strip())
            body_start = sep_idx + 4
            body = output[body_start : body_start + length].decode("utf-8")
            messages.append(json.loads(body))
            pos = body_start + length
        return messages


class TestMCPServer(unittest.TestCase):
    def _run_sequence(self, messages: list[dict], read_only: bool = False, root_dir: Path | None = None) -> list[dict]:
        raw_in = "".join(f"Content-Length: {len(json.dumps(m).encode('utf-8'))}\r\n\r\n{json.dumps(m)}" for m in messages)
        transport = FakeStreamTransport(raw_in)
        server = MCPServer(transport=transport, read_only=read_only, root_dir=root_dir)
        server.run()
        return transport.get_output_messages()

    def test_initialize_and_ping(self):
        msgs = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
            {"jsonrpc": "2.0", "id": 2, "method": "ping", "params": {}},
        ]
        responses = self._run_sequence(msgs)
        self.assertEqual(len(responses), 2)
        self.assertEqual(responses[0]["id"], 1)
        self.assertEqual(responses[0]["result"]["serverInfo"]["name"], "ontology-spider")
        self.assertEqual(responses[1]["id"], 2)
        self.assertEqual(responses[1]["result"], {})

    def test_tools_list(self):
        msgs = [
            {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        ]
        responses = self._run_sequence(msgs)
        tools = responses[0]["result"]["tools"]
        tool_names = {t["name"] for t in tools}
        expected = {
            "session_open",
            "session_close",
            "session_list",
            "model_load",
            "assert_triple",
            "declare_entity",
            "retract",
            "run_dialog",
            "query",
            "explain",
            "validate",
            "export",
            "focus",
            "constrain",
            "where_am_i",
            "engine_info",
        }
        self.assertTrue(expected.issubset(tool_names))

    def test_lifecycle_and_traversal(self):
        msgs = [
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "session_open", "arguments": {"session_id": "test_s1"}},
            },
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "assert_triple",
                    "arguments": {
                        "session_id": "test_s1",
                        "subject": "cat",
                        "predicate": "subclass_of",
                        "object": "mammal",
                    },
                },
            },
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "assert_triple",
                    "arguments": {
                        "session_id": "test_s1",
                        "subject": "felix",
                        "predicate": "instance_of",
                        "object": "cat",
                    },
                },
            },
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "query",
                    "arguments": {"session_id": "test_s1", "query": "query what is felix?"},
                },
            },
            {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {"name": "explain", "arguments": {"session_id": "test_s1"}},
            },
            {
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tools/call",
                "params": {"name": "validate", "arguments": {"session_id": "test_s1"}},
            },
            {
                "jsonrpc": "2.0",
                "id": 7,
                "method": "tools/call",
                "params": {"name": "export", "arguments": {"session_id": "test_s1", "format": "dialog"}},
            },
        ]
        responses = self._run_sequence(msgs)
        self.assertEqual(len(responses), 7)
        self.assertIn("felix", responses[3]["result"]["content"][0]["text"])
        self.assertIn("Path:", responses[4]["result"]["content"][0]["text"])
        self.assertEqual(len(responses[5]["result"]["violations"]), 0)
        self.assertIn("assert felix instance_of cat", responses[6]["result"]["content"][0]["text"])

    def test_read_only_protection(self):
        msgs = [
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "session_open", "arguments": {"session_id": "test_ro"}},
            },
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "assert_triple",
                    "arguments": {
                        "session_id": "test_ro",
                        "subject": "a",
                        "predicate": "b",
                        "object": "c",
                    },
                },
            },
        ]
        responses = self._run_sequence(msgs, read_only=True)
        self.assertEqual(len(responses), 2)
        self.assertIn("error", responses[1])
        self.assertIn("read-only mode", responses[1]["error"]["message"])

    def test_sandbox_path_boundary(self):
        msgs = [
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "session_open", "arguments": {"session_id": "test_sb"}},
            },
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "model_load",
                    "arguments": {"session_id": "test_sb", "path": "../../outside.dialog"},
                },
            },
        ]
        responses = self._run_sequence(msgs)
        self.assertEqual(len(responses), 2)
        self.assertIn("error", responses[1])
        self.assertIn("Access denied", responses[1]["error"]["message"])

    def test_full_mcp_tools_and_resources(self):
        msgs = [
            # Open session with model_path
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": {"name": "session_open", "arguments": {"session_id": "s_full", "model_path": "examples/tutorial.dialog"}},
            },
            # Session list
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "session_list", "arguments": {}},
            },
            # Engine info
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "engine_info", "arguments": {}},
            },
            # Declare entity
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {"name": "declare_entity", "arguments": {"session_id": "s_full", "entity_id": "garfield", "attributes": {"color": "orange"}}},
            },
            # Run dialog
            {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {"name": "run_dialog", "arguments": {"session_id": "s_full", "dialog_text": "assert garfield instance_of cat"}},
            },
            # Focus & Constrain & Where am I
            {
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tools/call",
                "params": {"name": "focus", "arguments": {"session_id": "s_full", "entity_id": "garfield", "constraints": {"color": "orange"}}},
            },
            {
                "jsonrpc": "2.0",
                "id": 7,
                "method": "tools/call",
                "params": {"name": "constrain", "arguments": {"session_id": "s_full", "key": "color", "value": "orange"}},
            },
            {
                "jsonrpc": "2.0",
                "id": 8,
                "method": "tools/call",
                "params": {"name": "where_am_i", "arguments": {"session_id": "s_full"}},
            },
            # Export json, dot, html
            {
                "jsonrpc": "2.0",
                "id": 9,
                "method": "tools/call",
                "params": {"name": "export", "arguments": {"session_id": "s_full", "format": "json"}},
            },
            {
                "jsonrpc": "2.0",
                "id": 10,
                "method": "tools/call",
                "params": {"name": "export", "arguments": {"session_id": "s_full", "format": "dot"}},
            },
            {
                "jsonrpc": "2.0",
                "id": 11,
                "method": "tools/call",
                "params": {"name": "export", "arguments": {"session_id": "s_full", "format": "html"}},
            },
            # Resources list & read
            {
                "jsonrpc": "2.0",
                "id": 12,
                "method": "resources/list",
                "params": {},
            },
            {
                "jsonrpc": "2.0",
                "id": 13,
                "method": "resources/read",
                "params": {"uri": "ontology://docs/language-reference"},
            },
            {
                "jsonrpc": "2.0",
                "id": 14,
                "method": "resources/read",
                "params": {"uri": "ontology://session/s_full/model.json"},
            },
            {
                "jsonrpc": "2.0",
                "id": 15,
                "method": "resources/read",
                "params": {"uri": "ontology://examples/tutorial"},
            },
            # Model load and Retract and Session close
            {
                "jsonrpc": "2.0",
                "id": 16,
                "method": "tools/call",
                "params": {"name": "model_load", "arguments": {"session_id": "s_full", "path": "examples/drones.dialog"}},
            },
            {
                "jsonrpc": "2.0",
                "id": 17,
                "method": "tools/call",
                "params": {"name": "retract", "arguments": {"session_id": "s_full", "assertion_id": "nonexistent"}},
            },
            {
                "jsonrpc": "2.0",
                "id": 18,
                "method": "tools/call",
                "params": {"name": "session_close", "arguments": {"session_id": "s_full"}},
            },
            # Unknown method error
            {
                "jsonrpc": "2.0",
                "id": 19,
                "method": "unknown/method",
                "params": {},
            },
        ]
        responses = self._run_sequence(msgs)
        self.assertEqual(len(responses), 19)
        self.assertIn("s_full", responses[1]["result"]["sessions"])
        self.assertIn("active_backend", responses[2]["result"]["content"][0]["text"])
        self.assertIn("garfield", responses[3]["result"]["content"][0]["text"])
        self.assertIn("Asserted", responses[4]["result"]["content"][0]["text"])
        self.assertIn("Focused", responses[5]["result"]["content"][0]["text"])
        self.assertIn("Traversal Stack", responses[7]["result"]["content"][0]["text"])
        self.assertIn("digraph", responses[9]["result"]["content"][0]["text"])
        self.assertIn("<html", responses[10]["result"]["content"][0]["text"].lower())
        self.assertTrue(len(responses[11]["result"]["resources"]) >= 3)
        self.assertIn("error", responses[18])

    def test_newline_delimited_transport_and_cli_main(self):
        from ontology_spider.mcp.__main__ import main as mcp_main
        from unittest.mock import patch

        raw_in = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping", "params": {}}) + "\n"
        transport = FakeStreamTransport(raw_in)
        server = MCPServer(transport=transport)
        server.run()
        self.assertEqual(len(transport.get_output_messages()), 1)

        with patch("sys.stdin", io.StringIO("")), patch("sys.stdout", io.StringIO()):
            rc = mcp_main(["--read-only"])
            self.assertEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
