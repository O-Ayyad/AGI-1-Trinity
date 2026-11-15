def finalize_node(state):
    return {"final_output": state["code"]}


def failure_node(state):
    return {"final_output": f"Test failed: {state['test_feedback']}"}
