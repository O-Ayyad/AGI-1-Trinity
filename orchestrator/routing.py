def route_after_test(state):
    if state["test_result"]:
        return "finish"
    if state["retry_count"] < state["retry_limit"]:
        return "retry"
    return "failed"
