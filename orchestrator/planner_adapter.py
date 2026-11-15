def run_planner(state, planner_agent):
    response = planner_agent(state["original_task"])
    if isinstance(response, dict) and isinstance(response.get("plan"), str):
        return {"plan": response["plan"]}
    raise ValueError("Invalid Planner response")
