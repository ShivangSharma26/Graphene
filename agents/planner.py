from typing import TypedDict, Annotated, Sequence
import operator
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, END
from agents.specialists import architecture_agent, impact_agent, dead_code_agent

# Define the state for the LangGraph
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    next_agent: str

def planner_node(state: AgentState):
    """
    Reads the user's query and decides which specialist to route to.
    """
    messages = state['messages']
    last_message = messages[-1].content.lower()
    
    # Simple routing logic
    if "architecture" in last_message or "structure" in last_message:
        next_agent = "architecture"
    elif "break" in last_message or "impact" in last_message or "change" in last_message:
        next_agent = "impact"
    elif "dead" in last_message or "unused" in last_message:
        next_agent = "dead_code"
    else:
        # Default to architecture if unclear
        next_agent = "architecture"
        
    return {"next_agent": next_agent}

# Define the graph
workflow = StateGraph(AgentState)

workflow.add_node("planner", planner_node)
workflow.add_node("architecture", architecture_agent)
workflow.add_node("impact", impact_agent)
workflow.add_node("dead_code", dead_code_agent)

workflow.set_entry_point("planner")

# Conditional routing based on the planner's decision
workflow.add_conditional_edges(
    "planner",
    lambda x: x["next_agent"],
    {
        "architecture": "architecture",
        "impact": "impact",
        "dead_code": "dead_code"
    }
)

workflow.add_edge("architecture", END)
workflow.add_edge("impact", END)
workflow.add_edge("dead_code", END)

app = workflow.compile()

def run_query(query: str):
    """
    Entry point to run a query through the LangGraph agents.
    """
    inputs = {"messages": [HumanMessage(content=query)]}
    result = app.invoke(inputs)
    return result["messages"][-1].content
