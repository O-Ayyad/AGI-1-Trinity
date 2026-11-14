def route_after_test(state):
    if(state["test_result"]):
        return "finish"
    elif(state["test_result"]==False and state["retry_count"]<state["retry_limit"]):
        return "retry"
    else:
        return "failed"