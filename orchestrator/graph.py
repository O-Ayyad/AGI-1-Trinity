from langgraph.graph import StateGraph, START, END
from state import OrchestratorState
from finalize import finalize_node

workflow=StateGraph(OrchestratorState)
workflow.add_node("finalize", finalize_node)
workflow.add_edge(START, "finalize")
workflow.add_edge("finalize", END)

app=workflow.compile()
