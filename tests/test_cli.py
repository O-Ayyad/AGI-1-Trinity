import os
import tempfile
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


class PromptFileTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.prompt = os.path.join(self.tmp.name, "prompt.txt")
        self.result = os.path.join(self.tmp.name, "result.txt")
        self.db = os.path.join(self.tmp.name, "context.db")

    def run_main(self, text):
        with open(self.prompt, "w", encoding="utf-8") as handle:
            handle.write(text)
        argv = [
            "cli.py",
            "--prompt-file",
            self.prompt,
            "--result-file",
            self.result,
            "--db",
            self.db,
            "--agent",
            "ack",
        ]
        with mock.patch("sys.argv", argv):
            return cli.main()

    def test_prompt_file_is_read_and_result_file_written(self):
        with mock.patch("cli.claude_response", return_value="done") as respond:
            status = self.run_main("line one\nline two\n")

        self.assertEqual(status, 0)
        respond.assert_called_once_with("line one\nline two", cli.DEFAULT_BACKEND)
        with open(self.result, encoding="utf-8") as handle:
            self.assertEqual(handle.read(), "done")

    def test_failure_returns_nonzero_and_writes_no_result(self):
        with mock.patch("cli.claude_response", side_effect=RuntimeError("boom")):
            status = self.run_main("hello")

        self.assertEqual(status, 1)
        self.assertFalse(os.path.exists(self.result))

    def test_empty_prompt_file_is_rejected(self):
        with self.assertRaises(SystemExit):
            self.run_main("   \n")


if __name__ == "__main__":
    unittest.main()
