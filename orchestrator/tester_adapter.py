def prepare_tester_input(state):
    return {
        "original_task": state["original_task"],
        "plan": state["plan"],
        "code": state["code"],
        "retry_count": state["retry_count"],
        "retry_limit": state["retry_limit"],
    }


def run_tester(state, tester_agent):
    response = tester_agent(prepare_tester_input(state))
    if (
        isinstance(response, dict)
        and isinstance(response.get("test_result"), bool)
        and isinstance(response.get("test_feedback"), str)
    ):
        return {
            "test_result": response["test_result"],
            "test_feedback": response["test_feedback"],
        }
    raise ValueError("Invalid Tester response")
