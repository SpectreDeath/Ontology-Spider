import io
import json
import unittest
from pathlib import Path

from ontology_spider.mcp.server import MCPServer
from ontology_spider.mcp.transport import StdioTransport
from ontology_spider.prolog.reasoner import PrologReasoner


class FakeStreamTransport(StdioTransport):
    def __init__(self, in_text: str = ""):
        self.in_stream = io.StringIO(in_text)
        self.out_stream = io.StringIO()

    def get_output_messages(self) -> list[dict]:
        output = self.out_stream.getvalue().strip()
        if not output:
            return []
        messages = []
        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith("Content-Length:"):
                continue
            try:
                messages.append(json.loads(line))
            except json.JSONDecodeError:
                pass
        return messages


class TestMCPServer(unittest.TestCase):
    def _run_sequence(
        self,
        messages: list[dict],
        read_only: bool = False,
        root_dir: Path | None = None,
        max_sessions: int = 32,
        max_assertions_per_session: int = 50_000,
        backend: str | None = None,
        preload_model_path: Path | None = None,
        timeout_seconds: float = 10.0,
        max_inferences: int = 1_000_000,
    ) -> list[dict]:
        raw_in = "\n".join(json.dumps(m) for m in messages) + "\n"
        transport = FakeStreamTransport(raw_in)
        server = MCPServer(
            transport=transport,
            read_only=read_only,
            root_dir=root_dir,
            max_sessions=max_sessions,
            max_assertions_per_session=max_assertions_per_session,
            backend=backend,
            preload_model_path=preload_model_path,
            timeout_seconds=timeout_seconds,
            max_inferences=max_inferences,
        )
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

    def test_notifications_cancelled(self):
        msgs = [
            {"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {"requestId": 42}},
            {"jsonrpc": "2.0", "id": 42, "method": "ping", "params": {}},
            {"jsonrpc": "2.0", "id": 43, "method": "ping", "params": {}},
        ]
        responses = self._run_sequence(msgs)
        # Request 42 was cancelled, so only response 43 should be emitted
        self.assertEqual(len(responses), 1)
        self.assertEqual(responses[0]["id"], 43)

    def test_session_and_assertion_caps(self):
        # Test max_sessions cap
        msgs_sessions = [
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "session_open", "arguments": {"session_id": "s1"}}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "session_open", "arguments": {"session_id": "s2"}}},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "session_open", "arguments": {"session_id": "s3"}}},
        ]
        resp_sessions = self._run_sequence(msgs_sessions, max_sessions=2)
        self.assertNotIn("error", resp_sessions[0])
        self.assertNotIn("error", resp_sessions[1])
        self.assertIn("error", resp_sessions[2])
        self.assertIn("Session cap exceeded", resp_sessions[2]["error"]["message"])

        # Test max_assertions_per_session cap
        msgs_assertions = [
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "session_open", "arguments": {"session_id": "s_cap"}}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "assert_triple", "arguments": {"session_id": "s_cap", "subject": "a", "predicate": "subclass_of", "object": "b"}}},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "assert_triple", "arguments": {"session_id": "s_cap", "subject": "b", "predicate": "subclass_of", "object": "c"}}},
            {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "assert_triple", "arguments": {"session_id": "s_cap", "subject": "c", "predicate": "subclass_of", "object": "d"}}},
        ]
        resp_assertions = self._run_sequence(msgs_assertions, max_assertions_per_session=2)
        self.assertNotIn("error", resp_assertions[0])
        self.assertNotIn("error", resp_assertions[1])
        self.assertNotIn("error", resp_assertions[2])
        self.assertIn("error", resp_assertions[3])
        self.assertIn("Assertion cap exceeded", resp_assertions[3]["error"]["message"])

    def test_preload_model_and_engine_info(self):
        msgs = [
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "query", "arguments": {"session_id": "default", "query": "query ancestors of delivery_drone"}}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "engine_info", "arguments": {}}},
        ]
        responses = self._run_sequence(msgs, preload_model_path=Path("examples/tutorial.dialog"))
        self.assertEqual(len(responses), 2)
        self.assertNotIn("error", responses[0])
        self.assertIn("aerial_vehicle", responses[0]["result"]["content"][0]["text"])
        info = json.loads(responses[1]["result"]["content"][0]["text"])
        self.assertEqual(info["max_sessions"], 32)
        self.assertEqual(info["timeout_seconds"], 10)

    def test_stdio_transport_framing(self):
        # 1. NDJSON read/write
        buf_out = io.StringIO()
        t = StdioTransport(in_stream=io.StringIO('{"msg": "hi"}\n\n{"msg": "two"}\n'), out_stream=buf_out)
        m1 = t.read_message()
        self.assertEqual(m1, {"msg": "hi"})
        m2 = t.read_message()
        self.assertEqual(m2, {"msg": "two"})
        m3 = t.read_message()
        self.assertIsNone(m3)

        t.write_message({"reply": "ok"})
        self.assertEqual(buf_out.getvalue(), '{"reply": "ok"}\n')

        # 2. Content-Length framing
        payload_str = json.dumps({"msg": "framed"})
        cl_text = f"Content-Length: {len(payload_str.encode('utf-8'))}\r\n\r\n{payload_str}"
        t_cl = StdioTransport(in_stream=io.StringIO(cl_text))
        m_cl = t_cl.read_message()
        self.assertEqual(m_cl, {"msg": "framed"})

        # 3. Invalid Content-Length
        t_bad = StdioTransport(in_stream=io.StringIO("Content-Length: not_a_num\r\n\r\n{}"))
        self.assertIsNone(t_bad.read_message())

        # 4. Incomplete Content-Length payload
        t_short = StdioTransport(in_stream=io.StringIO("Content-Length: 100\r\n\r\nshort"))
        self.assertIsNone(t_short.read_message())

    def test_mcp_python_backend_query_execution(self):
        msgs = [
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "engine_info", "arguments": {}}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "session_open", "arguments": {"session_id": "s_py"}}},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "assert_triple", "arguments": {"session_id": "s_py", "subject": "quadcopter", "predicate": "subclass_of", "object": "drone"}}},
            {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "assert_triple", "arguments": {"session_id": "s_py", "subject": "drone", "predicate": "subclass_of", "object": "aerial_vehicle"}}},
            {"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "query", "arguments": {"session_id": "s_py", "query": "query ancestors of quadcopter"}}},
        ]
        responses = self._run_sequence(msgs, backend="python")
        self.assertEqual(len(responses), 5)
        info = json.loads(responses[0]["result"]["content"][0]["text"])
        self.assertEqual(info["active_backend"], "python")
        q_text = responses[4]["result"]["content"][0]["text"]
        self.assertIn("drone", q_text)
        self.assertIn("aerial_vehicle", q_text)

    def test_mcp_query_timeout_and_inference_caps(self):
        # 1. Inference cap test with max_inferences=1
        msgs_cap = [
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "session_open", "arguments": {"session_id": "s_cap"}}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "assert_triple", "arguments": {"session_id": "s_cap", "subject": "a", "predicate": "subclass_of", "object": "b"}}},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "assert_triple", "arguments": {"session_id": "s_cap", "subject": "b", "predicate": "subclass_of", "object": "c"}}},
            {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "assert_triple", "arguments": {"session_id": "s_cap", "subject": "c", "predicate": "subclass_of", "object": "d"}}},
            {"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "query", "arguments": {"session_id": "s_cap", "query": "query ancestors of a"}}},
        ]
        responses_cap = self._run_sequence(msgs_cap, backend="python", max_inferences=1)
        self.assertIn("error", responses_cap[4])
        self.assertIn("exceeded maximum inferences limit", responses_cap[4]["error"]["message"])

        # 2. Timeout cap test with timeout_seconds=0.000001
        msgs_to = [
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "session_open", "arguments": {"session_id": "s_to"}}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "assert_triple", "arguments": {"session_id": "s_to", "subject": "x", "predicate": "subclass_of", "object": "y"}}},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "assert_triple", "arguments": {"session_id": "s_to", "subject": "y", "predicate": "subclass_of", "object": "z"}}},
            {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "query", "arguments": {"session_id": "s_to", "query": "query ancestors of x"}}},
        ]
        responses_to = self._run_sequence(msgs_to, backend="python", timeout_seconds=0.000001)
        self.assertIn("error", responses_to[3])
        self.assertIn("timeout", responses_to[3]["error"]["message"].lower())

    def test_cli_mcp_flags(self):
        from ontology_spider.cli import build_parser
        parser = build_parser()
        args = parser.parse_args([
            "mcp",
            "--timeout", "3",
            "--max-inferences", "100",
            "--max-sessions", "8",
            "--max-assertions", "500",
            "--backend", "python",
            "--read-only",
        ])
        self.assertEqual(args.timeout, 3.0)
        self.assertEqual(args.max_inferences, 100)
        self.assertEqual(args.max_sessions, 8)
        self.assertEqual(args.max_assertions, 500)
        self.assertEqual(args.backend, "python")
        self.assertTrue(args.read_only)

    @unittest.skipUnless(PrologReasoner().is_available, "swipl not installed")
    def test_mcp_prolog_backend_query_caps(self):
        root = Path(__file__).resolve().parent.parent
        # 1. Inference cap exceeded with max_inferences=2 on query
        msgs_cap = [
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "session_open", "arguments": {"session_id": "s_prolog_cap", "model_path": "examples/drones.dialog"}}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "query", "arguments": {"session_id": "s_prolog_cap", "query": "query ancestors of delivery_drone"}}},
        ]
        responses_cap = self._run_sequence(msgs_cap, backend="prolog", max_inferences=2, root_dir=root)
        self.assertIn("error", responses_cap[1])
        self.assertIn("Prolog query exceeded inference cap of 2 steps", responses_cap[1]["error"]["message"])

        # 2. Inference cap exceeded on run_dialog with max_inferences=2
        msgs_dialog_cap = [
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "session_open", "arguments": {"session_id": "s_prolog_dcap", "model_path": "examples/drones.dialog"}}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "run_dialog", "arguments": {"session_id": "s_prolog_dcap", "dialog_text": "query ancestors of delivery_drone"}}},
        ]
        responses_dialog_cap = self._run_sequence(msgs_dialog_cap, backend="prolog", max_inferences=2, root_dir=root)
        self.assertIn("error", responses_dialog_cap[1])
        self.assertIn("Prolog query exceeded inference cap of 2 steps", responses_dialog_cap[1]["error"]["message"])

        # 3. Query succeeds with normal max_inferences=100_000
        msgs_ok = [
            {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "session_open", "arguments": {"session_id": "s_prolog_ok", "model_path": "examples/drones.dialog"}}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "query", "arguments": {"session_id": "s_prolog_ok", "query": "query ancestors of delivery_drone"}}},
        ]
        responses_ok = self._run_sequence(msgs_ok, backend="prolog", max_inferences=100_000, root_dir=root)
        self.assertNotIn("error", responses_ok[1])
        self.assertIn("result", responses_ok[1])
        self.assertIn("aerial_vehicle", responses_ok[1]["result"]["content"][0]["text"])


if __name__ == "__main__":
    unittest.main()
