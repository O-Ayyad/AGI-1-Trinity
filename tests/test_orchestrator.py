import unittest

from orchestrator.graph import build_orchestrator


def fake_planner(task):
    return {"plan": "Write Python code to complete the task"}


def fake_coder(coder_input):
    if "test_feedback" in coder_input:
        return {"code": 'print("Hello World")'}
    return {"code": 'print("Goodbye")'}


def fake_tester(tester_input):
    if tester_input["code"] == 'print("Hello World")':
        return {"test_result": True, "test_feedback": "Successful."}
    return {"test_result": False, "test_feedback": "Failed. Output is wrong."}


def always_fail_tester(tester_input):
    return {"test_result": False, "test_feedback": "Code failed testing."}


def invalid_tester(tester_input):
    return {"test_result": "False", "test_feedback": "Code failed."}


def initial_state():
    return {
        "original_task": "Print Hello World",
        "plan": "",
        "code": "",
        "test_result": False,
        "test_feedback": "",
        "retry_count": 0,
        "retry_limit": 2,
        "final_output": "",
    }


class OrchestratorTests(unittest.TestCase):
    def test_retry_with_feedback_then_pass(self):
        result = build_orchestrator(fake_planner, fake_coder, fake_tester).invoke(initial_state())

        self.assertEqual(result["plan"], "Write Python code to complete the task")
        self.assertEqual(result["retry_count"], 1)
        self.assertTrue(result["test_result"])
        self.assertEqual(result["final_output"], 'print("Hello World")')

    def test_stops_after_retry_limit(self):
        result = build_orchestrator(fake_planner, fake_coder, always_fail_tester).invoke(
            initial_state()
        )

        self.assertEqual(result["retry_count"], 2)
        self.assertFalse(result["test_result"])
        self.assertEqual(result["final_output"], "Test failed: Code failed testing.")

    def test_invalid_tester_response_raises(self):
        app = build_orchestrator(fake_planner, fake_coder, invalid_tester)

        with self.assertRaisesRegex(ValueError, "Invalid Tester response"):
            app.invoke(initial_state())

    def test_invalid_planner_response_raises(self):
        app = build_orchestrator(lambda task: {"plan": 1}, fake_coder, fake_tester)

        with self.assertRaisesRegex(ValueError, "Invalid Planner response"):
            app.invoke(initial_state())

    def test_invalid_coder_response_raises(self):
        app = build_orchestrator(fake_planner, lambda coder_input: {}, fake_tester)

        with self.assertRaisesRegex(ValueError, "Invalid Coder response"):
            app.invoke(initial_state())


if __name__ == "__main__":
    unittest.main()
