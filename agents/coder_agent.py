from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from agents.tool_layer import TOOL_DEFINITIONS, ToolError, ToolLayer

BACKENDS = ("api", "subscription")
DEFAULT_MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-5-5")
DEFAULT_EFFORT = os.environ.get("CODER_EFFORT", "high")
DEFAULT_WORKDIR = os.environ.get("CODER_WORKDIR", "/workspace")
MAX_TOOL_TURNS = int(os.environ.get("CODER_MAX_TURNS", "25"))
FALLBACK_BETA = "server-side-fallback-2026-07-01"
TOOL_NAMES = [tool["name"] for tool in TOOL_DEFINITIONS]
REPO_ROOT = Path(__file__).resolve().parent.parent

SYSTEM_PROMPT = """\
You are the Coder Agent in a multi-agent system. You carry out the user's task by producing \
code, documentation, or file changes in a working directory using only the tools provided: \
read_file, write_file, edit_file and execute_code. All paths are relative to the working \
directory, and you cannot reach anything outside it.

Write the deliverable to files rather than only describing it. When you write code, run it \
with execute_code to check it works, and fix what fails. Stay within the scope of the task \
and the plan. Earlier conversation turns are past interactions from this user, for context.

When you finish, reply with a short summary: what you made or changed, which files, and how \
to run it."""


@dataclass(frozen=True)
class Interaction:
    #One past prompt response pair from database.

    prompt: str
    response: str | None = None


@dataclass(frozen=True)
class Plan:
    request: str
    steps: list[str]
    context: list[Interaction] = field(default_factory=list)


@dataclass(frozen=True)
class Output:
    plan: Plan
    summary: str
    files: dict[str, str]  # relative path to file contents

    @property
    def code(self) -> str:
        if not self.files:
            return self.summary
        return "\n\n".join(f"# --- {path} ---\n{content}" for path, content in self.files.items())


class CoderError(RuntimeError):
    pass


def plan_from_request(request: str, context: list[Interaction] | None = None) -> Plan:
    # This will not exist after planner agent integration
    return Plan(request=request, steps=[request], context=list(context or []))


class CoderAgent:
    def __init__(
        self,
        workdir: str | os.PathLike = DEFAULT_WORKDIR,
        backend: str = "api",
        model: str = DEFAULT_MODEL,
        effort: str = DEFAULT_EFFORT,
        max_turns: int = MAX_TOOL_TURNS,

    ) -> None:
        
        if backend not in BACKENDS:
            raise ValueError(f"backend must be one of {', '.join(BACKENDS)}, got {backend!r}")
        
        self.tools = ToolLayer(workdir)
        self.backend = backend
        self.model = model
        self.effort = effort
        self.max_turns = max_turns

    def generate_solution(self, plan: Plan) -> Output:
        return self._run(plan, _task_message(plan))

    def revise_solution(self, feedback: str, previous_output: Output) -> Output:
        message = (
            f"{_task_message(previous_output.plan)}\n\n"
            "Your previous attempt failed testing. Revise it to address this feedback:\n"
            f"{feedback}\n\n"
            f"Your previous summary was:\n{previous_output.summary}\n\n"
            "Files from the previous attempt: "
            + (", ".join(previous_output.files) or "none")
            + ". Read them from the working directory before changing them."
        )
        return self._run(previous_output.plan, message)

    def __call__(self, coder_input: dict) -> dict:

        # Adapter for the orchestrator run_coder takes its coder_input dict and returns {"code": str}

        plan = Plan(request=coder_input["original_task"], steps=[coder_input["plan"]])
        if "test_feedback" in coder_input:
            previous = Output(plan=plan, summary=coder_input.get("code", ""), files={})
            return {"code": self.revise_solution(coder_input["test_feedback"], previous).code}
        return {"code": self.generate_solution(plan).code}

    def _run(self, plan: Plan, message: str) -> Output:
        before = self.tools.snapshot()
        if self.backend == "subscription":
            summary = self._run_subscription(plan.context, message)
        else:
            summary = self._run_api(plan.context, message)
        after = self.tools.snapshot()
        changed = sorted(path for path, mtime in after.items() if before.get(path) != mtime)
        files = {}
        for path in changed:
            try:
                files[path] = self.tools.read_file(path)
            except ToolError as exc:
                files[path] = f"({exc})"
        return Output(plan=plan, summary=summary, files=files)

    def _run_api(self, context: list[Interaction], message: str) -> str:
        import anthropic

        client = anthropic.Anthropic()
        messages = _history_messages(context) + [{"role": "user", "content": message}]
        extra = {} if "haiku" in self.model else {"betas": [FALLBACK_BETA], "fallbacks": "default"}

        for _ in range(self.max_turns):
            response = client.beta.messages.create(
                model=self.model,
                max_tokens=16000,
                output_config={"effort": self.effort},
                system=SYSTEM_PROMPT,
                tools=TOOL_DEFINITIONS,
                messages=messages,
                **extra,
            )
            if response.stop_reason == "refusal":
                category = response.stop_details.category if response.stop_details else None
                raise CoderError(f"Claude declined the request (category: {category}).")
            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "max_tokens":
                raise CoderError("Response hit max_tokens before the task finished.")
            if response.stop_reason == "pause_turn":
                continue
            if response.stop_reason != "tool_use":
                return _text_of(response.content)

            results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                try:
                    results.append(_tool_result(block.id, self.tools.dispatch(block.name, block.input)))
                except ToolError as exc:
                    results.append(_tool_result(block.id, str(exc), is_error=True))
            messages.append({"role": "user", "content": results})

        raise CoderError(f"Stopped after {self.max_turns} tool turns without finishing.")

    def _run_subscription(self, context: list[Interaction], message: str) -> str:
        mcp_config = {
            "mcpServers": {
                "coder_tools": {
                    "command": sys.executable,
                    "args": ["-m", "agents.coder_mcp", str(self.tools.workdir)],
                    "env": {"PYTHONPATH": str(REPO_ROOT)},
                }
            }
        }
        allowed = ",".join(f"mcp__coder_tools__{name}" for name in TOOL_NAMES)
        result = subprocess.run(
            [
                "claude", "-p",
                "--model", self.model,
                "--system-prompt", SYSTEM_PROMPT,
                "--tools", "",
                "--mcp-config", json.dumps(mcp_config),
                "--strict-mcp-config",
                "--allowedTools", allowed,
            ],
            input=_history_text(context) + message,
            capture_output=True,
            text=True,
            cwd=self.tools.workdir,
        )
        if result.returncode != 0:
            raise CoderError(f"claude CLI failed: {result.stderr.strip() or result.stdout.strip()}")
        return result.stdout.strip()


def _task_message(plan: Plan) -> str:
    steps = "\n".join(f"{i}. {step}" for i, step in enumerate(plan.steps, 1))
    return f"Task:\n{plan.request}\n\nPlan:\n{steps}"


def _history_messages(context: list[Interaction]) -> list[dict]:
    messages = []
    for item in context:
        messages.append({"role": "user", "content": item.prompt})
        messages.append({"role": "assistant", "content": item.response or "(no response recorded)"})
    return messages


def _history_text(context: list[Interaction]) -> str:
    if not context:
        return ""
    lines = ["Past interactions, oldest first:"]
    for item in context:
        lines.append(f"User: {item.prompt}")
        lines.append(f"Assistant: {item.response or '(no response recorded)'}")
    return "\n".join(lines) + "\n\n"


def _tool_result(tool_use_id: str, content: str, is_error: bool = False) -> dict:
    result = {"type": "tool_result", "tool_use_id": tool_use_id, "content": content}
    if is_error:
        result["is_error"] = True
    return result


def _text_of(content) -> str:
    return "\n".join(block.text.strip() for block in content if block.type == "text").strip()
