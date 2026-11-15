import json
import os
import subprocess

import anthropic

from agents import local_client
from agents.config import BACKENDS, DEFAULT_MODEL


def generate_plan(system_prompt, user_prompt, backend="api"):
    if backend not in BACKENDS:
        raise ValueError(f"backend must be one of {', '.join(BACKENDS)}, got {backend!r}")
    if backend == "local":
        text = local_client.complete(system_prompt, user_prompt)
    else:
        model = os.environ.get("CLAUDE_MODEL", DEFAULT_MODEL)
        run = _run_subscription if backend == "subscription" else _run_api
        text = run(model, system_prompt, user_prompt)
    return _parse_plan(text)


def _run_api(model, system_prompt, user_prompt):
    response = anthropic.Anthropic().messages.create(
        model=model,
        max_tokens=4096,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    if response.stop_reason != "end_turn":
        raise ValueError(f"Planner did not finish: {response.stop_reason}")
    return "\n".join(block.text for block in response.content if block.type == "text").strip()


def _run_subscription(model, system_prompt, user_prompt):
    result = subprocess.run(
        ["claude", "-p", "--model", model, "--system-prompt", system_prompt, "--tools", ""],
        input=user_prompt,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"claude CLI failed: {result.stderr.strip() or result.stdout.strip()}")
    return result.stdout.strip()


def _parse_plan(text):
    if text.startswith("```") and text.endswith("```"):
        text = "\n".join(text.splitlines()[1:-1])
    elif "{" in text and "}" in text:
        text = text[text.index("{") : text.rindex("}") + 1]

    try:
        plan = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError("Planner returned invalid JSON.") from error

    if not isinstance(plan, dict) or not isinstance(plan.get("tasks"), list):
        raise ValueError("Planner must return an object with a tasks list.")
    return plan
