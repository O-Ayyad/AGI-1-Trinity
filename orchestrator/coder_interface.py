def prepare_coder_input(state):
    if(state["retry_count"]==0):
        return {"original_task": state["original_task"], "plan": state["plan"]}
    else:
        return {"original_task": state["original_task"], "plan": state["plan"], "code":state["code"], "test_feedback": state["test_feedback"]}