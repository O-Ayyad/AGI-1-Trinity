import unittest

from agents.tester_agent import TesterAgent, TesterAgentInput


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


if __name__ == "__main__":
    unittest.main()
