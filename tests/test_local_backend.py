import json
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

import cli
import httpx
from agents import config, local_client
from agents.coder_agent import CoderAgent, CoderError, plan_from_request
from agents.planner_agent import planner_agent
from agents.tester_agent import TesterAgent
from agents.tool_layer import TOOL_DEFINITIONS


def completion(content="", tool_calls=None, finish_reason="stop"):
    message = {"role": "assistant", "content": content}
    if tool_calls:
        message["tool_calls"] = tool_calls
    return {"choices": [{"message": message, "finish_reason": finish_reason}]}


def tool_call(call_id, name, arguments):
    return {
        "id": call_id,
        "type": "function",
        "function": {
            "name": name,
            "arguments": arguments if isinstance(arguments, str) else json.dumps(arguments),
        },
    }


def fake_post(*payloads):
    queue = list(payloads)
    calls = []

    def post(url, json=None, headers=None, timeout=None):
        calls.append({"url": url, "json": json, "headers": headers, "timeout": timeout})
        payload = queue.pop(0)
        if isinstance(payload, Exception):
            raise payload
        return SimpleNamespace(
            status_code=200,
            text="",
            raise_for_status=lambda: None,
            json=lambda: payload,
        )

    return mock.patch("agents.local_client.httpx.post", side_effect=post), calls


class LocalClientTests(unittest.TestCase):
    def test_chat_posts_openai_payload_to_configured_server(self):
        patch, calls = fake_post(completion("hi"))
        with patch, mock.patch.object(config, "LOCAL_BASE_URL", "http://box:8080/v1/"):
            with mock.patch.object(config, "LOCAL_API_KEY", "secret"):
                text = local_client.complete("be brief", "hello", model="qwen")

        self.assertEqual(text, "hi")
        self.assertEqual(calls[0]["url"], "http://box:8080/v1/chat/completions")
        self.assertEqual(calls[0]["headers"]["Authorization"], "Bearer secret")
        self.assertEqual(calls[0]["json"]["model"], "qwen")
        self.assertEqual(
            calls[0]["json"]["messages"],
            [{"role": "system", "content": "be brief"}, {"role": "user", "content": "hello"}],
        )

    def test_default_model_comes_from_config(self):
        patch, calls = fake_post(completion("hi"))
        with patch, mock.patch.object(config, "LOCAL_MODEL", "llama-test"):
            local_client.complete("s", "u")

        self.assertEqual(calls[0]["json"]["model"], "llama-test")
        self.assertNotIn("Authorization", calls[0]["headers"])

    def test_unreachable_server_raises_clear_error(self):
        patch, _ = fake_post(httpx.ConnectError("refused"))
        with patch, self.assertRaisesRegex(local_client.LocalModelError, "Could not reach"):
            local_client.complete("s", "u")

    def test_http_error_includes_status_and_body(self):
        response = httpx.Response(
            404, text="model not found", request=httpx.Request("POST", "http://x")
        )
        error = httpx.HTTPStatusError("bad", request=response.request, response=response)
        patch, _ = fake_post(error)
        with patch, self.assertRaisesRegex(local_client.LocalModelError, "404: model not found"):
            local_client.complete("s", "u")

    def test_malformed_response_raises(self):
        patch, _ = fake_post({"unexpected": True})
        with patch, self.assertRaisesRegex(local_client.LocalModelError, "unexpected response"):
            local_client.complete("s", "u")

    def test_openai_tools_conversion(self):
        tools = local_client.openai_tools(TOOL_DEFINITIONS)

        self.assertEqual(
            [t["function"]["name"] for t in tools], [t["name"] for t in TOOL_DEFINITIONS]
        )
        self.assertTrue(all(t["type"] == "function" for t in tools))
        self.assertEqual(tools[0]["function"]["parameters"], TOOL_DEFINITIONS[0]["input_schema"])


class LocalAgentTests(unittest.TestCase):
    def test_planner_uses_local_server_and_tolerates_extra_text(self):
        text = (
            'Here is the plan: {"tasks": [{"id": 1, "description": "Write it", '
            '"assigned_to": "coder", "depends_on": []}]} Hope that helps.'
        )
        patch, calls = fake_post(completion(text))
        with patch:
            result = planner_agent("Build it", backend="local")

        self.assertIn("Task 1: Write it", result["plan"])
        self.assertEqual(calls[0]["json"]["messages"][1]["content"], "Build it")

    def test_tester_uses_local_server_and_model(self):
        verdict = '{"test_result": true, "test_feedback": "Looks right."}'
        patch, calls = fake_post(completion(verdict))
        with patch, mock.patch.object(config, "LOCAL_MODEL", "tester-model"):
            tester = TesterAgent(backend="local")
            result = tester({"original_task": "t", "plan": "p", "code": "print(1)"})

        self.assertEqual(result, {"test_result": True, "test_feedback": "Looks right."})
        self.assertEqual(tester.model, "tester-model")
        self.assertEqual(calls[0]["json"]["model"], "tester-model")

    def test_cli_ack_uses_local_server(self):
        patch, _ = fake_post(completion("I am Claude and will not act."))
        with patch:
            self.assertEqual(cli.claude_response("hello", "local"), "I am Claude and will not act.")


class LocalCoderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.agent = CoderAgent(workdir=self.tmp.name, backend="local", model="coder-model")

    def test_tool_loop_writes_files_and_returns_summary(self):
        patch, calls = fake_post(
            completion(
                tool_calls=[
                    tool_call("c1", "write_file", {"path": "hello.py", "content": "print('hi')"})
                ]
            ),
            completion(tool_calls=[tool_call("c2", "execute_code", {"code": "print(2+2)"})]),
            completion("Created hello.py."),
        )
        with patch:
            output = self.agent.__call__({"original_task": "make hello", "plan": "write hello.py"})

        self.assertIn("hello.py", output["code"])
        self.assertIn("print('hi')", output["code"])
        self.assertEqual(len(calls), 3)
        self.assertEqual(calls[0]["json"]["model"], "coder-model")
        self.assertEqual(calls[0]["json"]["messages"][0]["role"], "system")
        self.assertEqual(calls[0]["json"]["tools"][0]["type"], "function")
        tool_messages = [m for m in calls[2]["json"]["messages"] if m["role"] == "tool"]
        self.assertEqual([m["tool_call_id"] for m in tool_messages], ["c1", "c2"])
        self.assertIn("exit code 0", tool_messages[1]["content"])

    def test_tool_errors_are_returned_to_the_model(self):
        patch, calls = fake_post(
            completion(tool_calls=[tool_call("c1", "read_file", {"path": "../secret"})]),
            completion(tool_calls=[tool_call("c2", "read_file", "not json")]),
            completion(tool_calls=[tool_call("c3", "read_file", "[1]")]),
            completion("Gave up."),
        )
        with patch:
            output = self.agent.generate_solution(
                __import__("agents.coder_agent", fromlist=["plan_from_request"]).plan_from_request(
                    "x"
                )
            )

        tool_messages = [m["content"] for m in calls[3]["json"]["messages"] if m["role"] == "tool"]
        self.assertIn("outside the working directory", tool_messages[0])
        self.assertTrue(tool_messages[1])
        self.assertIn("JSON object", tool_messages[2])
        self.assertEqual(output.summary, "Gave up.")

    def test_tool_arguments_may_already_be_objects(self):
        call = tool_call("c1", "write_file", {})
        call["function"]["arguments"] = {"path": "a.txt", "content": "A"}
        patch, _ = fake_post(completion(tool_calls=[call]), completion("Done."))
        with patch:
            output = self.agent.__call__({"original_task": "t", "plan": "p"})

        self.assertIn("a.txt", output["code"])

    def test_length_finish_reason_raises(self):
        patch, _ = fake_post(completion("partial", finish_reason="length"))
        with patch, self.assertRaisesRegex(CoderError, "max_tokens"):
            self.agent.__call__({"original_task": "t", "plan": "p"})

    def test_turn_limit_raises(self):
        agent = CoderAgent(workdir=self.tmp.name, backend="local", max_turns=2)
        looping = completion(tool_calls=[tool_call("c", "execute_code", {"code": "pass"})])
        patch, _ = fake_post(looping, looping)
        with patch, self.assertRaisesRegex(CoderError, "2 tool turns"):
            agent.__call__({"original_task": "t", "plan": "p"})

    def test_default_model_is_the_local_model(self):
        with mock.patch.object(config, "LOCAL_MODEL", "my-local"):
            agent = CoderAgent(workdir=self.tmp.name, backend="local")

        self.assertEqual(agent.model, "my-local")


if __name__ == "__main__":
    unittest.main()
