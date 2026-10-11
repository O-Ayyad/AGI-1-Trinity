from graph import app
initial_state={
    "original_task": "Print Hello World",
    "plan":"",
    "code":'print("Hello World")',
    "test_result": True,
    "test_feedback": "",
    "retry_count":0,
    "retry_limit":3,
    "final_output": ""
}

result=app.invoke(initial_state)
print(result["final_output"])