from langgraph.graph import StateGraph, END
from app.agents.state import AgentState
from app.agents.nodes import (
    supervisor_node,
    schema_node,
    planner_node,
    sql_node,
    explain_node,
    optimize_node,
    debug_node
)

def route_next(state: AgentState) -> str:
    """
    Decides which agent node to run next based on the state variable 'next_agent'.
    """
    next_agent = state.get("next_agent", "end")
    if next_agent == "end":
        return END
    return next_agent

# Initialize the StateGraph
workflow = StateGraph(AgentState)

# Register our agent nodes
workflow.add_node("supervisor", supervisor_node)
workflow.add_node("schema", schema_node)
workflow.add_node("planner", planner_node)
workflow.add_node("sql", sql_node)
workflow.add_node("explain", explain_node)
workflow.add_node("optimize", optimize_node)
workflow.add_node("debug", debug_node)

# Set the Supervisor as the entryway of the graph workflow
workflow.set_entry_point("supervisor")

# Configure routing edges based on the next_agent state field
workflow.add_conditional_edges("supervisor", route_next, {
    "schema": "schema",
    "explain": "explain",
    "optimize": "optimize",
    "debug": "debug",
    END: END
})

workflow.add_conditional_edges("schema", route_next, {
    "planner": "planner",
    END: END
})

workflow.add_conditional_edges("planner", route_next, {
    "sql": "sql",
    END: END
})

workflow.add_conditional_edges("sql", route_next, {
    "explain": "explain",
    END: END
})

workflow.add_conditional_edges("explain", route_next, {
    END: END
})

workflow.add_conditional_edges("optimize", route_next, {
    END: END
})

workflow.add_conditional_edges("debug", route_next, {
    END: END
})

# Compile the graph
graph = workflow.compile()
