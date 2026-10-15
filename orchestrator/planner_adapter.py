def run_planner(state,planner_agent):
    task=state["original_task"]
    response=planner_agent(task)
    if (isinstance(response,dict) and "plan" in response and isinstance(response["plan"],str)):
        return {"plan": response["plan"]}
    else:
        raise ValueError("Invalid Planner response")