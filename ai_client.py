import json
import os 

import anthropic


def generate_plan(system_prompt, user_prompt):
    model=os.environ.get("CLAUDE_MODEL")
    if not model:
        raise ValueError("Set CLAUDE_MODEL before running the planner.")
    response=anthropic.Anthropic().messages.create(
        model=model,
        max_tokens=4096,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    if response.stop_reason != "end_turn":
        raise ValueError(
            f"Planner did not finish: {response.stop_reason}"
        )
    text= "/n".join(
        block.text
        for block in response.content
        if block.type =="text"
    ).strip()

    if text.startswith("```") and text.endswith("```"):
        text="\n".join(text.splitlines()[1:-1])

    try:
        plan=json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError("Planner returned invalid JSON.") from error

    if not isinstance(plan,dict) or not isinstance(plan.get("tasks"), list):
        raise ValueError("Planner must return an object with a tasks list.")
    return plan