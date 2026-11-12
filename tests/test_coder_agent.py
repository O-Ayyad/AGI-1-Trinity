import functools
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from agents.coder_agent import CoderAgent, CoderError, Interaction, Output, plan_from_request
from agents.tool_layer import ToolError, ToolLayer


def text(value):
    return SimpleNamespace(type="text", text=value)


def tool_use(block_id, name, tool_input):
    return SimpleNamespace(type="tool_use", id=block_id, name=name, input=tool_input)


def reply(stop_reason, *content):
    return SimpleNamespace(stop_reason=stop_reason, stop_details=None, content=list(content))


def fake_client(*responses):
    queue = list(responses)

    def respond(**kwargs):
        #The agent keeps appending to the same messages list
        create.sent.append(list(kwargs["messages"]))
        return queue.pop(0)

    create = mock.Mock(side_effect=respond)
    create.sent = []
    client = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=create)))
    return mock.patch("anthropic.Anthropic", return_value=client), create


class ToolLayerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.layer = ToolLayer(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_write_read_and_edit(self):
        self.layer.write_file("pkg/hello.py", "print('hi')\n")
        self.layer.edit_file("pkg/hello.py", "hi", "hello")
        self.assertEqual(self.layer.read_file("pkg/hello.py"), "print('hello')\n")

    def test_paths_outside_workdir_are_refused(self):
        for path in ("../escape.txt", "/etc/passwd", "a/../../escape.txt"):
            with self.assertRaises(ToolError):
                self.layer.write_file(path, "x")

    def test_symlink_escape_is_refused(self):
        outside = tempfile.TemporaryDirectory()
        self.addCleanup(outside.cleanup)
        os.symlink(outside.name, Path(self.tmp.name) / "link")
        with self.assertRaises(ToolError):
            self.layer.write_file("link/evil.txt", "x")
        self.assertEqual(os.listdir(outside.name), [])

    def test_edit_requires_a_unique_match(self):
        self.layer.write_file("f.txt", "a a")
        with self.assertRaisesRegex(ToolError, "2 times"):
            self.layer.edit_file("f.txt", "a", "b")
        with self.assertRaisesRegex(ToolError, "not found"):
            self.layer.edit_file("f.txt", "z", "b")

    def test_execute_code_runs_in_workdir(self):
        self.layer.write_file("data.txt", "42")
        result = self.layer.execute_code("print(open('data.txt').read())")
        self.assertEqual((result.returncode, result.stdout.strip()), (0, "42"))

    def test_execute_code_reports_errors_and_timeouts(self):
        self.assertNotEqual(self.layer.execute_code("raise SystemExit(3)").returncode, 0)
        self.assertTrue(self.layer.execute_code("while True: pass", timeout=1).timed_out)

    def test_dispatch_rejects_missing_arguments_and_unknown_tools(self):
        with self.assertRaisesRegex(ToolError, "Missing required argument"):
            self.layer.dispatch("write_file", {"path": "x"})
        with self.assertRaisesRegex(ToolError, "Unknown tool"):
            self.layer.dispatch("rm_rf", {})


class CoderAgentTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.agent = CoderAgent(workdir=self.tmp.name, backend="api", model="claude-opus-5-5")

    def tearDown(self):
        self.tmp.cleanup()

    def test_generate_solution_runs_tools_and_reports_changed_files(self):
        patch, create = fake_client(
            reply("tool_use", text("Writing it."), tool_use("t1", "write_file", {"path": "hello.py", "content": "print('Hello World')\n"})),
            reply("tool_use", tool_use("t2", "execute_code", {"code": "import runpy; runpy.run_path('hello.py')"})),
            reply("end_turn", text("Created hello.py; run it with python hello.py.")),
        )
        history = [Interaction("earlier prompt", "earlier answer")]
        with patch:
            output = self.agent.generate_solution(plan_from_request("Print Hello World", history))

        self.assertEqual(output.summary, "Created hello.py; run it with python hello.py.")
        self.assertEqual(output.files, {"hello.py": "print('Hello World')\n"})
        self.assertIn("Hello World", output.code)

        first_messages = create.sent[0]
        self.assertEqual(first_messages[0], {"role": "user", "content": "earlier prompt"})
        self.assertEqual(first_messages[1], {"role": "assistant", "content": "earlier answer"})
        self.assertIn("Print Hello World", first_messages[2]["content"])

        exec_result = create.sent[2][-1]["content"][0]
        self.assertEqual(exec_result["tool_use_id"], "t2")
        self.assertIn("Hello World", exec_result["content"])

    def test_tool_errors_go_back_to_claude_instead_of_raising(self):
        patch, create = fake_client(
            reply("tool_use", tool_use("t1", "read_file", {"path": "../secret"})),
            reply("end_turn", text("Could not read it.")),
        )
        with patch:
            output = self.agent.generate_solution(plan_from_request("read ../secret"))
        result = create.sent[1][-1]["content"][0]
        self.assertTrue(result["is_error"])
        self.assertEqual(output.files, {})

    def test_revise_solution_sends_feedback_and_previous_output(self):
        plan = plan_from_request("Print Hello World")
        previous = Output(plan=plan, summary="Printed Goodbye.", files={"hello.py": "print('Goodbye')"})
        patch, create = fake_client(reply("end_turn", text("Fixed.")))
        with patch:
            output = self.agent.revise_solution("Output should be Hello World", previous)
        sent = create.sent[-1][-1]["content"]
        self.assertIn("Output should be Hello World", sent)
        self.assertIn("hello.py", sent)
        self.assertIs(output.plan, plan)

    def test_orchestrator_adapter_returns_code_dict(self):
        patch, _ = fake_client(
            reply("tool_use", tool_use("t1", "write_file", {"path": "a.py", "content": "x = 1\n"})),
            reply("end_turn", text("Done.")),
        )
        with patch:
            result = self.agent({"original_task": "set x", "plan": "assign x"})
        self.assertEqual(set(result), {"code"})
        self.assertIn("x = 1", result["code"])

    def test_refusal_and_turn_limit_raise(self):
        patch, _ = fake_client(reply("refusal"))
        with patch, self.assertRaisesRegex(CoderError, "declined"):
            self.agent.generate_solution(plan_from_request("x"))

        agent = CoderAgent(workdir=self.tmp.name, backend="api", max_turns=1)
        patch, _ = fake_client(reply("tool_use", tool_use("t1", "read_file", {"path": "nope"})))
        with patch, self.assertRaisesRegex(CoderError, "1 tool turns"):
            agent.generate_solution(plan_from_request("x"))

    def test_fallbacks_are_requested_except_on_haiku(self):
        patch, create = fake_client(reply("end_turn", text("ok")))
        with patch:
            self.agent.generate_solution(plan_from_request("x"))
        self.assertEqual(create.call_args.kwargs["fallbacks"], "default")

        haiku = CoderAgent(workdir=self.tmp.name, backend="api", model="claude-haiku-5-5")
        patch, create = fake_client(reply("end_turn", text("ok")))
        with patch:
            haiku.generate_solution(plan_from_request("x"))
        self.assertNotIn("fallbacks", create.call_args.kwargs)


class CliIntegrationTests(unittest.TestCase):
    def test_coder_mode_uses_and_stores_past_interactions(self):
        import cli

        with tempfile.TemporaryDirectory() as tmp:
            conn = cli.connect(os.path.join(tmp, "context.db"))
            self.addCleanup(conn.close)
            cli.store(conn, "make add.py", "Created add.py.")
            agent_in_tmp = functools.partial(CoderAgent, workdir=tmp)
            patch, create = fake_client(reply("end_turn", text("Added tests.")))
            with patch, mock.patch("agents.coder_agent.CoderAgent", agent_in_tmp), mock.patch("builtins.print"):
                cli.handle(conn, "now add tests", 10, "api", "coder")

            sent = create.sent[0]
            self.assertEqual(sent[0]["content"], "make add.py")
            self.assertEqual(sent[1]["content"], "Created add.py.")
            rows = cli.fetch_context(conn, None)
            self.assertEqual(rows[-1][1], "now add tests")
            self.assertTrue(rows[-1][3].startswith("Added tests."))

    def test_old_databases_gain_a_response_column(self):
        import cli

        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "old.db")
            old = sqlite3.connect(path)
            old.execute("CREATE TABLE prompts (id INTEGER PRIMARY KEY AUTOINCREMENT, body TEXT NOT NULL, created_at TEXT NOT NULL)")
            old.execute("INSERT INTO prompts (body, created_at) VALUES ('hi', 'now')")
            old.commit()
            old.close()
            conn = cli.connect(path)
            self.addCleanup(conn.close)
            self.assertEqual(cli.fetch_context(conn, None), [(1, "hi", "now", None)])

    def test_failed_call_still_stores_prompt(self):
        import cli

        with tempfile.TemporaryDirectory() as tmp:
            conn = cli.connect(os.path.join(tmp, "context.db"))
            self.addCleanup(conn.close)
            with mock.patch("cli.coder_response", side_effect=RuntimeError("no key")), mock.patch(
                "builtins.print"
            ):
                cli.handle(conn, "hello", 10, "api", "coder")
            [(_id, body, _created, response)] = cli.fetch_context(conn, None)
            self.assertEqual((body, response), ("hello", None))


class McpServerTests(unittest.TestCase):
    def test_server_exposes_the_four_tools(self):
        import asyncio

        from agents.coder_mcp import build_server

        with tempfile.TemporaryDirectory() as tmp:
            tools = asyncio.run(build_server(tmp).list_tools())
        self.assertEqual(
            sorted(tool.name for tool in tools),
            ["edit_file", "execute_code", "read_file", "write_file"],
        )


if __name__ == "__main__":
    unittest.main()
