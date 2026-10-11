from typing import TypedDict

class OrchestratorState(TypedDict):
    original_task:str
    plan:str
    code:str
    test_result:bool
    test_feedback:str
    retry_count:int
    retry_limit:int
    final_output:str
    