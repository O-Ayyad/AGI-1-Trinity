def prepare_tester_input(state):
    return {"original_task": state["original_task"], "code": state["code"]}

def run_tester(state, tester_agent):
    tester_input=prepare_tester_input(state)
    response=tester_agent(tester_input)
    if (isinstance(response,dict) and "test_result" in response and isinstance(response["test_result"],bool) and "test_feedback" in response and isinstance(response["test_feedback"],str)):
        return {"test_result": response["test_result"], "test_feedback": response["test_feedback"]}
    else:
        raise ValueError ("Invalid Tester response")