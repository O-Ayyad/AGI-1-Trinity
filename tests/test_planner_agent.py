import os
import unittest
from types import SimpleNamespace
from unittest import mock

from agents.planner_agent import planner_agent, validate_plan


def task(task_id, depends_on=(), assigned_to="coder"):
    return {
        "id": task_id,
        "description": f"Task {task_id}",
        "assigned_to": assigned_to,
        "depends_on": list(depends_on),
    }


def api_response(text, stop_reason="end_turn"):
    return SimpleNamespace(
        stop_reason=stop_reason, content=[SimpleNamespace(type="text", text=text)]
    )


class PlannerAgentTests(unittest.TestCase):
    def test_api_plan_reaches_planner_output(self):
        response = api_response(
            '{"tasks": [{"id": 1, "description": "Write a greeting function", '
            '"assigned_to": "coder", "depends_on": []}]}'
        )
        with mock.patch.dict(os.environ, {"CLAUDE_MODEL": "test-model"}):
            with mock.patch("agents.ai_client.anthropic.Anthropic") as client:
                client.return_value.messages.create.return_value = response
                result = planner_agent("Create a greeting.")

        self.assertIn("Write a greeting function", result["plan"])
        request = client.return_value.messages.create.call_args.kwargs
        self.assertEqual(request["model"], "test-model")
        self.assertEqual(
            request["messages"],
            [{"role": "user", "content": "Create a greeting."}],
        )

    def test_fenced_json_and_multiple_text_blocks(self):
        response = SimpleNamespace(
            stop_reason="end_turn",
            content=[
                SimpleNamespace(
                    type="text",
                    text='```json\n{"tasks": [{"id": 1, "description": "A", '
                    '"assigned_to": "tester", "depends_on": []}]}\n```',
                )
            ],
        )
        with mock.patch("agents.ai_client.anthropic.Anthropic") as client:
            client.return_value.messages.create.return_value = response
            result = planner_agent("Test it.")

        self.assertIn("Assigned to: tester", result["plan"])

    def test_subscription_backend_uses_claude_cli(self):
        completed = SimpleNamespace(
            returncode=0,
            stdout='{"tasks": [{"id": 1, "description": "A", "assigned_to": "coder", "depends_on": []}]}',
            stderr="",
        )
        with mock.patch("agents.ai_client.subprocess.run", return_value=completed) as run:
            result = planner_agent("Plan it.", backend="subscription")

        self.assertIn("Task 1: A", result["plan"])
        self.assertEqual(run.call_args.args[0][:2], ["claude", "-p"])
        self.assertEqual(run.call_args.kwargs["input"], "Plan it.")

    def test_subscription_failure_raises(self):
        completed = SimpleNamespace(returncode=1, stdout="", stderr="not logged in")
        with mock.patch("agents.ai_client.subprocess.run", return_value=completed):
            with self.assertRaisesRegex(RuntimeError, "not logged in"):
                planner_agent("Plan it.", backend="subscription")

    def test_unknown_backend_rejected(self):
        with self.assertRaisesRegex(ValueError, "backend must be one of"):
            planner_agent("Plan it.", backend="nope")

    def test_incomplete_response_raises(self):
        with mock.patch("agents.ai_client.anthropic.Anthropic") as client:
            client.return_value.messages.create.return_value = api_response("{}", "max_tokens")
            with self.assertRaisesRegex(ValueError, "did not finish"):
                planner_agent("Plan it.")

    def test_invalid_json_raises(self):
        with mock.patch("agents.ai_client.anthropic.Anthropic") as client:
            client.return_value.messages.create.return_value = api_response("not json")
            with self.assertRaisesRegex(ValueError, "invalid JSON"):
                planner_agent("Plan it.")

    def test_blank_prompt_fails_without_calling_claude(self):
        with mock.patch("agents.ai_client.anthropic.Anthropic") as client:
            result = planner_agent("   ")

        client.assert_not_called()
        self.assertIn("Invalid request", result["plan"])

    def test_empty_task_list_reports_failure(self):
        with mock.patch("agents.ai_client.anthropic.Anthropic") as client:
            client.return_value.messages.create.return_value = api_response('{"tasks": []}')
            result = planner_agent("Plan it.")

        self.assertIn("No tasks were created", result["plan"])


class ValidatePlanTests(unittest.TestCase):
    def test_valid_plan(self):
        self.assertTrue(validate_plan([task(1), task(2, [1], "tester")]))

    def test_missing_fields(self):
        with self.assertRaisesRegex(ValueError, "missing required fields"):
            validate_plan([{"id": 1}])

    def test_invalid_agent(self):
        with self.assertRaisesRegex(ValueError, "Invalid agent"):
            validate_plan([task(1, assigned_to="planner")])

    def test_duplicate_ids(self):
        with self.assertRaisesRegex(ValueError, "Duplicate task ID"):
            validate_plan([task(1), task(1)])

    def test_self_dependency(self):
        with self.assertRaisesRegex(ValueError, "cannot depend on itself"):
            validate_plan([task(1, [1])])

    def test_missing_dependency(self):
        with self.assertRaisesRegex(ValueError, "nonexistent task 9"):
            validate_plan([task(1, [9])])

    def test_circular_dependency(self):
        with self.assertRaisesRegex(ValueError, "Circular dependency"):
            validate_plan([task(1, [2]), task(2, [1])])


if __name__ == "__main__":
    unittest.main()
