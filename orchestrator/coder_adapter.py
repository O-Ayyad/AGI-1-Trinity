def prepare_coder_input(state):
    if state["retry_count"] == 0:
        return {"original_task": state["original_task"], "plan": state["plan"]}
    return {
        "original_task": state["original_task"],
        "plan": state["plan"],
        "code": state["code"],
        "test_feedback": state["test_feedback"],
    }


def run_coder(state, coder_agent):
    response = coder_agent(prepare_coder_input(state))
    if isinstance(response, dict) and isinstance(response.get("code"), str):
        return {"code": response["code"]}
    raise ValueError("Invalid Coder response")
