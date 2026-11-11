


from ai_client import generate_plan

PLANNER_SYSTEM_PROMPT = """
You are the Planner Agent in a multi-agent software development system.

The agent is to break down complex user requests into smaller, actionable tasks.It will assign coding tasks
to the coder and testing tasks to the tester. It will identify task dependencies
and avoid circular dependencies. 

It returns only valid JSON with the following fields:id, description, assigned_to, depends_on.

The planner agent uses the format: {"tasks": [...]}

"""

def validate_plan(tasks):
     required_fields = {
          "id",
          "description",
          "assigned_to",
          "depends_on"
     }
     for task in tasks: 
          missing_fields = required_fields - task.keys()

          if missing_fields:
               raise ValueError(
               f"Task is missing required fields: {missing_fields}"
          )
     valid_agents = {"coder", "tester"}

     for task in tasks:
          if task["assigned_to"] not in valid_agents:
               raise ValueError(
                    f"Invalid agent: {task['assigned_to']}"
               )

     task_ids = set()

     for task in tasks:
        task_id = task["id"]

        if task_id in task_ids:
               raise ValueError(f"Duplicate task ID: {task_id}")
        task_ids.add(task_id)

     for task in tasks:
         for dependency in task["depends_on"]:
              
              if dependency == task["id"]:
                   raise ValueError(
                        f"Task {task['id']} cannot depend on itself "
                   )
              if dependency not in task_ids:
                   raise ValueError(
                        f"Task {task['id']} depends on"
                        f"nonexistent task {dependency}"

                   )
          
     dependency_map = {
          task["id"] : task["depends_on"]
          for task in tasks
    }
     visited = set()
     visiting = set()

     def check_cycle(task_id):
        if task_id in visiting:
             raise ValueError(
                  f"Circular dependency detected"
             )
        if task_id in visited:
            return
        visiting.add(task_id)
        for dependency in dependency_map[task_id]:
             check_cycle(dependency)
        visiting.remove(task_id)
        visited.add(task_id)

     for task_id in dependency_map:
         check_cycle(task_id)
            
     return True


def create_plan(prompt):
    if not isinstance(prompt, str) or not prompt.strip():
        return {"plan": "Planning has failed. Invalid request."}

    response = generate_plan(
         system_prompt= PLANNER_SYSTEM_PROMPT,
         user_prompt=prompt)
    tasks = response["tasks"]
    

    if not tasks:
            return {"plan": "Planning failed.No tasks were created"}

    validate_plan(tasks)
    
    plan_response = "PLANNER AGENT - TASK PLAN\n"
    plan_response += "=" * 30 + "\n\n"

    for task in tasks:
        plan_response += f"Task {task['id']}: {task['description']}\n"
        plan_response += f"- Assigned to: {task['assigned_to']}\n"
        plan_response += f"- Dependencies:  {task['depends_on']}\n"
        
    
    return {"plan": plan_response}

def planner_agent(prompt):
    return create_plan(prompt)


if __name__ == "__main__":
    plan = planner_agent("Build a to-do app")
    print(plan["plan"])