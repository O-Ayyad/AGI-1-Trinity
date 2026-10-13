from langgraph.graph import StateGraph, START, END
from state import OrchestratorState
from finalize import finalize_node, failure_node
from routing import route_after_test
from retry import retry_node

workflow=StateGraph(OrchestratorState)
workflow.add_node("finalize", finalize_node)
workflow.add_node("failure", failure_node)
workflow.add_node("retry",retry_node)

workflow.add_conditional_edges(START,
                               route_after_test,
                               {"finish": "finalize",
                                "failed": "failure", 
                                "retry": "retry"})
workflow.add_edge("finalize", END)
workflow.add_edge("failure", END)
workflow.add_edge("retry", END)

app=workflow.compile()
