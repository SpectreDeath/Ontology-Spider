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
        output = self.out_stream.getvalue()
        messages = []
        pos = 0
        while pos < len(output):
            idx = output.find("Content-Length:", pos)
            if idx == -1:
                break
            sep_idx = output.find("\r\n\r\n", idx)
            if sep_idx == -1:
                break
            header = output[idx:sep_idx]
            length = int(header.split(":", 1)[1].strip())
            body_start = sep_idx + 4
            body = output[body_start : body_start + length]
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


if __name__ == "__main__":
    unittest.main()
