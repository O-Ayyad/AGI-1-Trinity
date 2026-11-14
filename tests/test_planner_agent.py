import os
import unittest
from types import SimpleNamespace
from unittest import mock

from planner import planner_agent

class PlannerAgentTests(unittest.TestCase):
    def test_api_plan_reaches_planner_output(self):
        response=SimpleNamespace(
            stop_reason="end_turn",
            content=[
                SimpleNamespace(
                    type="text",
                    text=(
                        '{"tasks": [{"id": 1, '
                        '"description": "Write a greeting function", '
                        '"assigned_to": "coder", "depends_on": []}]}'
                    )
                )
            ],
        )
        with mock.patch.dict(os.environ, {"CLAUDE_MODEL": "test-model"}):
            with mock.patch("ai_client.anthropic.Anthropic") as client:
                client.return_value.messages.create.return_value=response
                result= planner_agent("Create a greeting.")

        self.assertIn("Write a greeting function", result["plan"])
        request= client.return_value.messages.create.call_args.kwargs
        self.assertEqual(request["model"], "test-model")
        self.assertEqual(
            request["messages"],
            [{"role": "user", "content": "Create a greeting."}],
        )

if __name__ == "main":
    unittest.main()