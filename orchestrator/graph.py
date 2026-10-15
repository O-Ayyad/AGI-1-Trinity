from langgraph.graph import StateGraph, START, END
from .state import OrchestratorState
from .finalize import finalize_node, failure_node
from .routing import route_after_test
from .retry import retry_node
from .planner_adapter import run_planner
from .coder_adapter import run_coder
from .tester_adapter import run_tester

"""
Coordinates the Planner, Coder, and Tester agents using LangGraph. Handles conditional routing, retries, and task completion.
"""

def build_orchestrator(planner_agent,coder_agent, tester_agent):

    """ The agents are provided as functions so they can be replaced without changing the graph."""
    def planner_node(state):
        return run_planner(state, planner_agent)
    def coder_node(state):
        return run_coder(state, coder_agent)
    def tester_node(state):
        return run_tester(state,tester_agent)

    workflow=StateGraph(OrchestratorState)
    workflow.add_node("finalize", finalize_node)
    workflow.add_node("failure", failure_node)
    workflow.add_node("retry",retry_node)
    workflow.add_node("planner", planner_node)
    workflow.add_node("coder", coder_node)
    workflow.add_node("tester", tester_node)

    workflow.add_edge(START,"planner")
    workflow.add_edge("planner", "coder")
    workflow.add_edge("coder", "tester")
    workflow.add_edge("retry", "coder")
    workflow.add_edge("finalize", END)
    workflow.add_edge("failure", END)

    workflow.add_conditional_edges("tester",
                               route_after_test,
                               {"finish": "finalize",
                                "failed": "failure",
                                "retry": "retry"})
    return workflow.compile()
