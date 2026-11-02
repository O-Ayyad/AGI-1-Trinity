def combine_context(previous_context, original_task):
    full_context = previous_context + [original_task]
    return " ".join(full_context)
def create_context_plan(previous_context, original_task, planner_agent):
    full_prompt = combine_context(previous_context, original_task)
    return planner_agent(full_prompt)