import unittest
from unittest import mock

import cli


class WorkflowResponseTests(unittest.TestCase):
    def test_workflow_passes_backend_to_every_agent(self):
        planner = mock.Mock(return_value={"plan": "Make hello.py"})
        coder = mock.Mock(return_value={"code": "print('hi')"})
        tester = mock.Mock(return_value={"test_result": True, "test_feedback": "ok"})

        with mock.patch("agents.planner_agent.planner_agent", planner), mock.patch(
            "agents.coder_agent.CoderAgent", return_value=coder
        ) as coder_cls, mock.patch(
            "agents.tester_agent.TesterAgent", return_value=tester
        ) as tester_cls:
            output = cli.workflow_response("say hi", "subscription")

        self.assertEqual(output, "print('hi')")
        planner.assert_called_once_with("say hi", backend="subscription")
        coder_cls.assert_called_once_with(backend="subscription")
        tester_cls.assert_called_once_with(backend="subscription")


if __name__ == "__main__":
    unittest.main()
