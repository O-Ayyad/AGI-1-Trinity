from graph import app
initial_state={
    "original_task": "Print Hello World",
    "plan":"",
    "code":'print("Hello World")',
    "test_result": False,
    "test_feedback": "SyntaxError on line 5",
    "retry_count":1,
    "retry_limit":3,
    "final_output": ""
}

result=app.invoke(initial_state)
print(result["retry_count"])