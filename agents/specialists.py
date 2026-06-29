import os
from neo4j import GraphDatabase
from qdrant_client import QdrantClient
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_groq import ChatGroq

# ── Database Connections ──────────────────────────────────────────────

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "graphene_password")

QDRANT_URL = os.getenv("QDRANT_URL", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
QDRANT_COLLECTION = "graphene_codebase"

def _neo4j_query(cypher: str, params: dict = None):
    """Executes a Cypher query against Neo4j and returns the results."""
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    results = []
    with driver.session() as session:
        records = session.run(cypher, params or {})
        for record in records:
            results.append(record.data())
    driver.close()
    return results

def _qdrant_search(query_text: str, limit: int = 5):
    """Searches Qdrant for semantically similar code entities."""
    # Note: Since the original mock didn't use real embeddings, we'll just pull a sample for now
    # to feed context to the LLM. If we wanted true semantic search, we'd embed query_text here.
    client = QdrantClient(url=QDRANT_URL, port=QDRANT_PORT)
    try:
        results, _ = client.scroll(
            collection_name=QDRANT_COLLECTION,
            limit=limit,
            with_payload=True
        )
        return [
            {"name": p.payload.get("name"), "type": p.payload.get("type"), "file": p.payload.get("file")}
            for p in results
        ]
    except Exception:
        return []

# ── Shared LLM Setup ──────────────────────────────────────────────────

def _get_llm():
    return ChatGroq(model_name="llama-3.3-70b-versatile", temperature=0)

# ── Specialist Agent 1: Architecture ──────────────────────────────────

def architecture_agent(state):
    user_query = state["messages"][-1].content
    llm = _get_llm()

    # To deduce true architecture, the LLM needs the directory structure and main files
    files = _neo4j_query("MATCH (f:File) RETURN f.name AS file")
    file_paths = [f['file'] for f in files] if files else []
    
    # Also get high-level node counts just for scale reference
    counts = _neo4j_query("MATCH (n) RETURN labels(n)[0] AS type, count(n) AS count")
    
    qdrant_context = _qdrant_search(user_query, limit=5)

    sys_prompt = """You are an expert Staff Software Engineer.
Your job is to deeply analyze the provided file paths and structural context to deduce the TRUE SYSTEM ARCHITECTURE of the INGESTED codebase. Do NOT describe Graphene itself; describe the repository that was just analyzed.

You MUST format your output beautifully using Markdown, matching this exact structure:

### 1. System Architecture — [Core Concept]
Explain the high-level flow of the system based on the files provided.
[INSERT A TEXT-BASED ASCII/MARKDOWN ARCHITECTURE DIAGRAM SHOWING THE FLOW]

### 2. The Core Components
Break down the system into logical phases, tiers, or modules based on the directories you see.

### 3. Tech Stack — What, Why & Why Not
Create a Markdown table with columns: | Part | We Used | Why (and why not the alternative) |.
Deduce the tech stack strictly based on the file names and structure provided. Do NOT assume any technologies (like FastAPI, Neo4j, React, etc.) unless they are explicitly evident in the provided file paths or context.

Do NOT output generic summaries. DEDUCE the actual architecture of the provided codebase!"""

    context = f"Total Files/Nodes: {counts}\nFile Structure: {file_paths}\nQdrant Context: {qdrant_context}"
    user_prompt = f"Context:\n{context}\n\nUser Question: {user_query}"

    response = llm.invoke([SystemMessage(content=sys_prompt), HumanMessage(content=user_prompt)])
    return {"messages": [AIMessage(content=response.content)]}

# ── Specialist Agent 2: Impact Analysis ───────────────────────────────

def impact_agent(state):
    user_query = state["messages"][-1].content
    llm = _get_llm()

    # Extract target using LLM instead of regex
    extract_prompt = f"Extract the name of the function, file, or class the user wants to change from this query: '{user_query}'. Respond with ONLY the exact name. If none found, reply 'UNKNOWN'."
    target = llm.invoke([HumanMessage(content=extract_prompt)]).content.strip()

    if target == "UNKNOWN" or not target:
        return {"messages": [AIMessage(content="I couldn't identify exactly what function or file you want to check the impact for. Please specify a name!")]}

    # Query Neo4j for callers
    callers = _neo4j_query("""
        MATCH (f)-[:CALLS]->(func:Function {name: $target})
        RETURN f.name AS caller_file
    """, {"target": target})
    
    # Query Qdrant for related concepts
    related = _qdrant_search(target, limit=3)

    sys_prompt = """You are the 'Impact Agent' for Graphene. Your job is to analyze 'Blast Radius'.
Given the user's question and the graph DB context, explain what files will break if they change the target component.
Use Markdown. Use a warning tone if the impact is high."""

    context = f"Target: {target}\nFiles that call this target (Blast Radius): {callers}\nRelated context: {related}"
    user_prompt = f"Context:\n{context}\n\nUser Question: {user_query}"

    response = llm.invoke([SystemMessage(content=sys_prompt), HumanMessage(content=user_prompt)])
    return {"messages": [AIMessage(content=response.content)]}

# ── Specialist Agent 3: Dead Code Detection ───────────────────────────

def dead_code_agent(state):
    user_query = state["messages"][-1].content
    llm = _get_llm()

    # Find dead functions in Neo4j
    dead_functions = _neo4j_query("""
        MATCH (f:Function)
        WHERE NOT ()-[:CALLS]->(f)
        RETURN f.name AS name, f.file AS file
        ORDER BY f.file LIMIT 30
    """)
    
    total = _neo4j_query("MATCH (f:Function) RETURN count(f) AS total")
    total_count = total[0]["total"] if total else 0

    sys_prompt = """You are the 'Dead Code Agent' for Graphene.
You analyze orphaned code that has no incoming callers.
Summarize the dead code findings based on the graph DB context. 
Format clearly with Markdown."""

    context = f"Total Functions: {total_count}\nDead Functions (Sample): {dead_functions}"
    user_prompt = f"Context:\n{context}\n\nUser Question: {user_query}"

    response = llm.invoke([SystemMessage(content=sys_prompt), HumanMessage(content=user_prompt)])
    return {"messages": [AIMessage(content=response.content)]}
