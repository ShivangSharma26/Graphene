from typing import TypedDict, Annotated, Sequence
import operator
import os
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langchain_groq import ChatGroq
from agents.specialists import architecture_agent, impact_agent, dead_code_agent

# Define the state for the LangGraph
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    next_agent: str

def planner_node(state: AgentState):
    """
    Uses Groq LLM to read the user's query and decide which specialist to route to.
    """
    messages = state['messages']
    user_query = messages[-1].content
    
    llm = ChatGroq(model_name="llama-3.3-70b-versatile", temperature=0)
    
    prompt = f"""You are a routing agent for a codebase analysis tool.
Read the user's query and decide which of the following three agents should handle it:
1. 'dead_code': If they ask about unused, orphaned, or dead code.
2. 'impact': If they ask what breaks, blast radius, or impact of changing something.
3. 'architecture': If they ask about architecture, structure, or anything else (like 'where is X used').

User Query: "{user_query}"

Respond with ONLY ONE word: 'dead_code', 'impact', or 'architecture'."""

    response = llm.invoke([HumanMessage(content=prompt)])
    next_agent = response.content.strip().lower()
    
    # Fallback validation
    if next_agent not in ["dead_code", "impact", "architecture"]:
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
