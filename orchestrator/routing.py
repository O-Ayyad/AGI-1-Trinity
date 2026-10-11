def route_after_test(state):
    if(state["test_result"]):
        return "finish"
    elif(state["test_result"]==False and state["retry_count"]<state["retry_limit"]):
        return "retry"
    else:
        return "failed"  

state={
        "test_result": True,
        "retry_count":0,
        "retry_limit":3
    }
print(route_after_test(state))