def retry_node(state):
    return {"retry_count": state["retry_count"] + 1}
