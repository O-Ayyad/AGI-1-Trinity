from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal


TestStatus = Literal["PASS", "FAIL"]
OutputType = Literal["code", "documentation"]


@dataclass(frozen=True)
class TestResult:
    """Result returned by the Tester Agent after evaluating Coder output."""

    status: TestStatus
    feedback: str
    retry_count: int


@dataclass(frozen=True)
class TesterAgentInput:
    """Information the Tester Agent needs from shared state."""

    coder_output: str
    requirements: list[str]
    generated_plan: list[str]
    retry_count: int = 0
    output_type: OutputType = "documentation"


class TesterAgent:
    """Evaluates Coder Agent output against task requirements."""

    def __init__(self, max_retries: int = 3) -> None:
        self.max_retries = max_retries

    def evaluate_output(self, agent_input: TesterAgentInput) -> TestResult:
        """Return PASS or FAIL with feedback for the Orchestrator."""
        if agent_input.retry_count >= self.max_retries:
            return TestResult(
                status="FAIL",
                feedback="Retry limit reached. The workflow should stop and return a failure status.",
                retry_count=agent_input.retry_count,
            )

        if not agent_input.coder_output.strip():
            return TestResult(
                status="FAIL",
                feedback="The Coder Agent did not produce any output.",
                retry_count=agent_input.retry_count,
            )

        missing_requirements = self._find_missing_requirements(
            agent_input.coder_output,
            agent_input.requirements,
        )
        if missing_requirements:
            return TestResult(
                status="FAIL",
                feedback="The output is missing these requirements: "
                + "; ".join(missing_requirements),
                retry_count=agent_input.retry_count,
            )

        if agent_input.output_type == "code":
            return self._evaluate_python_code(agent_input)

        return TestResult(
            status="PASS",
            feedback="The output satisfies the recorded requirements.",
            retry_count=agent_input.retry_count,
        )

    def _find_missing_requirements(
        self,
        coder_output: str,
        requirements: Iterable[str],
    ) -> list[str]:
        """Simple requirement check for prototype documentation outputs."""
        normalized_output = coder_output.lower()
        missing: list[str] = []

        for requirement in requirements:
            normalized_requirement = requirement.strip().lower()
            if normalized_requirement and normalized_requirement not in normalized_output:
                missing.append(requirement)

        return missing

    def _evaluate_python_code(self, agent_input: TesterAgentInput) -> TestResult:
        """Run generated Python code in a temporary file for basic validation."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            code_path = Path(tmp_dir) / "candidate.py"
            code_path.write_text(agent_input.coder_output, encoding="utf-8")

            completed = subprocess.run(
                ["python3", str(code_path)],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )

        if completed.returncode != 0:
            return TestResult(
                status="FAIL",
                feedback=(
                    "The generated code failed during execution. "
                    f"Error: {completed.stderr.strip() or completed.stdout.strip()}"
                ),
                retry_count=agent_input.retry_count,
            )

        return TestResult(
            status="PASS",
            feedback="The generated code executed successfully and satisfies the recorded requirements.",
            retry_count=agent_input.retry_count,
        )

