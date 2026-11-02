from planner_context import create_context_plan
from planner import planner_agent 

previous_context = ["Build a to-do app."]
original_task = "Use Java. Do not use a database"


result = create_context_plan(
    previous_context,
    original_task,
    planner_agent
)
print(result["plan"])