def finalize_node(state):
    return {"final_output": state["code"]}

def failure_node(state):
    feedback=state["test_feedback"]
    message=f"Test failed: {feedback}"
    return {"final_output": message}