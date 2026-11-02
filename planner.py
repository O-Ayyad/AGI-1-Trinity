

def extract_requirements(prompt):
    requirements = prompt.split(".")

    requirements = [
        requirements.strip()
        for requirements in requirements
        if requirements.strip()
    ]
    return requirements

def create_tasks(requirements, dependencies):
    tasks=[]
    next_id = 1
    for requirement in requirements:
        task_id = next_id
        task = {
            "id": task_id,
            "description": requirement,
            "depends_on":dependencies.get(task_id,[])
        }
        tasks.append(task)
        next_id +=1
    return tasks

def create_plan(prompt):
    requirements = extract_requirements(prompt)
    print(requirements)
    tasks = create_tasks(requirements, {})

    if not tasks:
            return {"plan": "Planning failed.No tasks were created"}

    for task in tasks:
        task_id = task["id"]

        if task_id == 1:
            task["depends_on"] = []
        else:
            task["depends_on"] = [task_id-1]
    
    plan_response = "PLANNER AGENT - TASK PLAN\n"
    plan_response += "=" * 30 + "\n\n"

    for task in tasks:
        plan_response += f"Task {task['id']}: {task['description']}\n"
        plan_response += f"- Dependencies:  {task['depends_on']}\n"
    
    return {"plan": plan_response}

def planner_agent(prompt):
    return create_plan(prompt)


if __name__ == "__main__":
    plan = planner_agent("Build a to-do app. Users can add tasks. Users can delete tasks. ")
    print(plan["plan"])
