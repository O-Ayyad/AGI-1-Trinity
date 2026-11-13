import unittest
from unittest import mock

from agents.tester_agent import TesterAgent, TesterAgentInput, TesterError

class TesterAgentTests(unittest.TestCase):
    def test_documentation_output_passes_when_requirements_are_present(self):
        tester = TesterAgent()
        result = tester.evaluate_output(
            TesterAgentInput(
                coder_output="The Tester Agent returns PASS or FAIL with clear feedback.",
                requirements=["PASS or FAIL", "clear feedback"],
                generated_plan=["Evaluate the Coder Agent output."],
            )
        )

        self.assertEqual(result.status, "PASS")

    def test_documentation_output_fails_when_requirement_is_missing(self):
        tester = TesterAgent()
        result = tester.evaluate_output(
            TesterAgentInput(
                coder_output="The Tester Agent returns a result.",
                requirements=["retry limit"],
                generated_plan=["Check all requirements."],
            )
        )

        self.assertEqual(result.status, "FAIL")
        self.assertIn("retry limit", result.feedback)

    def test_code_output_fails_when_python_has_error(self):
        tester = TesterAgent()
        result = tester.evaluate_output(
            TesterAgentInput(
                coder_output="raise RuntimeError('broken code')",
                requirements=[],
                generated_plan=["Run code validation."],
                output_type="code",
            )
        )

        self.assertEqual(result.status, "FAIL")
        self.assertIn("failed during execution", result.feedback)

    def test_retry_limit_returns_failure(self):
        tester = TesterAgent(max_retries=2)
        result = tester.evaluate_output(
            TesterAgentInput(
                coder_output="The output exists.",
                requirements=[],
                generated_plan=[],
                retry_count=2,
            )
        )

        self.assertEqual(result.status, "FAIL")
        self.assertIn("Retry limit reached", result.feedback)

    def test_orchestrator_adapter_returns_ai_result(self):
            tester = TesterAgent(backend="api")
            response = (
                '{"test_result": true, '
                '"test_feedback": "All requirements passed."}'
            )

            with mock.patch.object(
                tester, "_run_api", return_value=response
            ) as run_api:
                result = tester(
                    {
                        "original_task": "Create a greeting function.",
                        "plan": "Implement and verify the function.",
                        "code": "def greet(): return 'hello'",
                    }
                )

            self.assertEqual(
                result,
                {
                    "test_result": True,
                    "test_feedback": "All requirements passed.",
                },
            )

            prompt = run_api.call_args.args[0]
            self.assertIn("Create a greeting function.", prompt)
            self.assertIn("Implement and verify the function.", prompt)
            self.assertIn("def greet()", prompt)

    def test_orchestrator_adapter_rejects_invalid_ai_response(self):
        tester = TesterAgent(backend="api")

        with mock.patch.object(tester, "_run_api", return_value="PASS"):
            with self.assertRaises(TesterError):
                tester(
                    {
                        "original_task": "Complete the task.",
                        "code": "solution",
                    }
                )

    def test_orchestrator_adapter_fails_empty_output_without_ai(self):
        tester = TesterAgent(backend="api")

        with mock.patch.object(tester, "_run_api") as run_api:
            result = tester(
                {
                    "original_task": "Complete the task.",
                    "code": "",
                }
            )

        self.assertFalse(result["test_result"])
        self.assertIn("did not produce", result["test_feedback"])
        run_api.assert_not_called()


    def test_final_retry_is_still_evaluated(self):
        tester= TesterAgent(backend="api")
        response='{"test_result": true, "test_feedback": "Passed."}'

        with mock.patch.object(
            tester, "_run_api", return_value=response
        ) as run_api:
            result = tester({
            "original_task": "Create a greeting.",
            "plan": "Return hello.",
            "code": "def greet(): return 'hello'",
            "retry_count": 3,
            "retry_limit": 3,
        })

        self.assertTrue(result["test_result"])
        run_api.assert_called_once()

if __name__ == "__main__":
    unittest.main()
