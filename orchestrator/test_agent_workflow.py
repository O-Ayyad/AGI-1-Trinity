from .graph import build_orchestrator

"""This is just a TEST"""

def fake_coder(coder_input):
    if "test_feedback" in coder_input:
        return {"code": 'print("Hello World")'}
    else:
        return {"code": 'print("Goodbye")'}

def fake_tester(tester_input):
    code=tester_input["code"]
    if code == 'print("Hello World")':
        return {"test_result": True, "test_feedback": "Successful."}
    else:
        return {"test_result": False, "test_feedback": "Failed. Output is wrong."}

def always_fail_tester(tester_input):
    return {"test_result": False, "test_feedback": "Code failed testing."}

def fake_planner(task):
    return {"plan": "Write Python code to complete the task"}

def invalid_tester(tester_input):
    return {"test_result": "False", "test_feedback": "Code failed."}

initial_state={
    "original_task": "Print Hello World",
    "plan": "Write a Python print statement",
    "code":"",
    "test_result": False,
    "test_feedback":"",
    "retry_count":0,
    "retry_limit":2,
    "final_output":""
}
app=build_orchestrator(fake_planner,fake_coder,fake_tester)
failure_app=build_orchestrator(fake_planner,fake_coder,always_fail_tester)
invalid_app=build_orchestrator(fake_planner,fake_coder,invalid_tester)

try:
    (invalid_app.invoke(initial_state))
except ValueError as error:
    assert str(error) == "Invalid Tester response"
else:
    raise AssertionError("Expected error was not raised")

failure=failure_app.invoke(initial_state)
result=app.invoke(initial_state)

assert result["retry_count"]==1
assert result["test_result"]==True
assert result["final_output"]=='print("Hello World")'

assert failure["retry_count"]==2
assert failure["test_result"]==False
assert failure["final_output"]== "Test failed: Code failed testing."

print (failure["retry_count"], failure["test_result"], failure["final_output"])
print(result["plan"])