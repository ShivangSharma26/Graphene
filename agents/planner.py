from typing import TypedDict, Annotated, Sequence
import operator
import os
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langchain_groq import ChatGroq
from agents.specialists import architecture_agent, impact_agent, dead_code_agent, general_agent

# Define the state for the LangGraph
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    next_agent: str
    repo_path: str  # Pass repo path through the state so agents can read files

def planner_node(state: AgentState):
    """
    Uses Groq LLM to read the user's query and intelligently route to the right specialist.
    """
    messages = state['messages']
    user_query = messages[-1].content
    
    llm = ChatGroq(model_name="llama-3.3-70b-versatile", temperature=0)
    
    prompt = f"""You are a routing agent for a codebase analysis tool.
Read the user's query and decide which of the following four agents should handle it:

1. 'dead_code': Questions about unused, orphaned, or dead code. Example: "Show dead code", "Find unused functions"
2. 'impact': Questions about what breaks if something changes, blast radius, dependencies. Example: "What happens if I change X?", "What depends on Y?"
3. 'architecture': Questions about system architecture, structure, tech stack, or high-level design. Example: "What's the architecture?", "How is the project structured?"
4. 'general': ANY OTHER question about the codebase — specific functions, files, APIs, logic, how things work, where something is used, etc. Example: "What does function X do?", "Where is auth handled?", "List all API endpoints"

User Query: "{user_query}"

Respond with ONLY ONE word: 'dead_code', 'impact', 'architecture', or 'general'."""

    response = llm.invoke([HumanMessage(content=prompt)])
    next_agent = response.content.strip().lower().strip("'\"")
    
    # Fallback validation
    if next_agent not in ["dead_code", "impact", "architecture", "general"]:
        next_agent = "general"
        
    return {"next_agent": next_agent}

# Define the graph
workflow = StateGraph(AgentState)

workflow.add_node("planner", planner_node)
workflow.add_node("architecture", architecture_agent)
workflow.add_node("impact", impact_agent)
workflow.add_node("dead_code", dead_code_agent)
workflow.add_node("general", general_agent)

workflow.set_entry_point("planner")

# Conditional routing based on the planner's decision
workflow.add_conditional_edges(
    "planner",
    lambda x: x["next_agent"],
    {
        "architecture": "architecture",
        "impact": "impact",
        "dead_code": "dead_code",
        "general": "general"
    }
)

workflow.add_edge("architecture", END)
workflow.add_edge("impact", END)
workflow.add_edge("dead_code", END)
workflow.add_edge("general", END)

app = workflow.compile()

def run_query(query: str, repo_path: str = None):
    """
    Entry point to run a query through the LangGraph agents.
    Passes repo_path so agents can read actual source files.
    """
    inputs = {
        "messages": [HumanMessage(content=query)],
        "repo_path": repo_path or ""
    }
    result = app.invoke(inputs)
    return result["messages"][-1].content
