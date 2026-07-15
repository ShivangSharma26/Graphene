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
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        results = []
        with driver.session() as session:
            records = session.run(cypher, params or {})
            for record in records:
                results.append(record.data())
        driver.close()
        return results
    except Exception as e:
        print(f"Neo4j query error: {e}")
        return []

def _qdrant_fetch(limit: int = 20):
    """Fetches code entities from Qdrant with their payloads."""
    try:
        client = QdrantClient(url=QDRANT_URL, port=QDRANT_PORT, check_compatibility=False)
        results, _ = client.scroll(
            collection_name=QDRANT_COLLECTION,
            limit=limit,
            with_payload=True
        )
        return [p.payload for p in results]
    except Exception:
        return []

def _read_repo_files(repo_path: str, max_files: int = 30) -> str:
    """
    Directly reads source files from the cloned repo directory.
    This is the THIRD context source beyond Neo4j and Qdrant.
    Returns a formatted string of file contents.
    """
    if not repo_path or not os.path.exists(repo_path):
        return ""
    
    source_extensions = {'.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.go', '.rs', '.rb', '.php'}
    ignore_dirs = {'.git', 'node_modules', 'venv', 'env', '__pycache__', 'dist', 'build', '.next'}
    
    file_contents = []
    file_count = 0
    
    for root, dirs, files in os.walk(repo_path, topdown=True):
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        for file in sorted(files):
            ext = os.path.splitext(file)[1].lower()
            if ext not in source_extensions:
                continue
            if file_count >= max_files:
                break
            
            file_path = os.path.join(root, file)
            rel_path = os.path.relpath(file_path, repo_path).replace('\\', '/')
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                # Truncate very large files heavily to avoid token limits
                if len(content) > 800:
                    content = content[:800] + "\n# ... file truncated ..."
                file_contents.append(f"=== FILE: {rel_path} ===\n{content}")
                file_count += 1
            except Exception:
                continue
    
    return "\n\n".join(file_contents)

# ── Shared LLM Setup ──────────────────────────────────────────────────

def _get_llm():
    return ChatGroq(model_name="llama-3.1-8b-instant", temperature=0)

# ── Build Comprehensive Context ──────────────────────────────────────

def _build_full_context(repo_path: str = None) -> str:
    """
    Builds a comprehensive context document from ALL three sources:
    1. Neo4j Knowledge Graph (structure + relationships)
    2. Qdrant Vector Store (code payloads)
    3. Raw file reading (actual source code)
    """
    context_parts = []
    
    # --- Source 1: Neo4j Knowledge Graph ---
    # Get file structure
    files = _neo4j_query("MATCH (f:File) RETURN f.name AS name, f.language AS language, f.line_count AS lines ORDER BY f.name")
    if files:
        file_tree = "\n".join([f"  {f['name']} ({f.get('language', '?')}, {f.get('lines', 0)} lines)" for f in files])
        context_parts.append(f"## FILE STRUCTURE (from Knowledge Graph)\n{file_tree}")
    
    # Get all functions with their code
    functions = _neo4j_query("""
        MATCH (fn:Function) 
        RETURN fn.name AS name, fn.file AS file, fn.code AS code, fn.start_line AS start_line
        ORDER BY fn.file, fn.start_line
    """)
    if functions:
        func_list = []
        for fn in functions[:8]:  # Limit to 8 functions to save tokens
            code = fn.get('code', '')
            if code:
                func_list.append(f"### {fn['name']} (in {fn['file']})\n```python\n{code[:400]}\n```")
            else:
                func_list.append(f"- {fn['name']} (in {fn['file']})")
        context_parts.append(f"## FUNCTIONS (showing {min(len(functions), 8)} of {len(functions)})\n" + "\n\n".join(func_list))
    
    # Get all classes with their code
    classes = _neo4j_query("""
        MATCH (c:Class) 
        RETURN c.name AS name, c.file AS file, c.code AS code
        ORDER BY c.file
    """)
    if classes:
        class_list = []
        for cls in classes[:3]: # Limit to 3 classes to save tokens
            code = cls.get('code', '')
            if code:
                class_list.append(f"### class {cls['name']} (in {cls['file']})\n```python\n{code[:400]}\n```")
            else:
                class_list.append(f"- class {cls['name']} (in {cls['file']})")
        context_parts.append(f"## CLASSES (showing {min(len(classes), 3)} of {len(classes)})\n" + "\n\n".join(class_list))
    
    # Get relationships
    calls = _neo4j_query("""
        MATCH (caller)-[:CALLS]->(target:Function) 
        RETURN caller.name AS caller, target.name AS target, labels(caller)[0] AS caller_type
        LIMIT 25
    """)
    if calls:
        call_list = "\n".join([f"  {c['caller']} ({c.get('caller_type', '?')}) → calls → {c['target']}" for c in calls])
        context_parts.append(f"## CALL RELATIONSHIPS (Top 25)\n{call_list}")
    
    # Get imports
    imports = _neo4j_query("""
        MATCH (f:File)-[:IMPORTS]->(imp:Import) 
        RETURN f.name AS file, imp.text AS import_text
        ORDER BY f.name LIMIT 20
    """)
    if imports:
        import_list = "\n".join([f"  {imp['file']}: {imp['import_text']}" for imp in imports])
        context_parts.append(f"## IMPORT DEPENDENCIES (Top 20)\n{import_list}")
    
    # Get node counts for summary
    counts = _neo4j_query("MATCH (n) RETURN labels(n)[0] AS type, count(n) AS count")
    if counts:
        count_str = ", ".join([f"{c['type']}: {c['count']}" for c in counts])
        context_parts.insert(0, f"## CODEBASE SUMMARY\nNode counts: {count_str}")
    
    # --- Source 2: Qdrant payloads (if available) ---
    qdrant_data = _qdrant_fetch(limit=10)
    if qdrant_data:
        qdrant_list = []
        for item in qdrant_data:
            code = item.get('code', '')
            if code:
                qdrant_list.append(f"- {item.get('name', '?')} ({item.get('type', '?')}) in {item.get('file', '?')}")
        if qdrant_list:
            context_parts.append(f"## VECTOR INDEX ENTITIES\n" + "\n".join(qdrant_list))
    
    # --- Source 3: Raw file reading (the most important!) ---
    if repo_path:
        raw_files = _read_repo_files(repo_path, max_files=2) # Reduced max files to 2 to save tokens
        if raw_files:
            context_parts.append(f"## RAW SOURCE CODE (Top 2 Files)\n{raw_files}")
    
    return "\n\n".join(context_parts)


# ── Specialist Agent 1: Architecture ──────────────────────────────────

def architecture_agent(state):
    user_query = state["messages"][-1].content
    repo_path = state.get("repo_path")
    llm = _get_llm()

    context = _build_full_context(repo_path)

    sys_prompt = """You are an expert Staff Software Engineer analyzing a codebase.
You have been given REAL source code, function definitions, class definitions, import dependencies, and call relationships extracted from the actual repository.

Your job is to analyze this ACTUAL CODE and answer the user's question with extreme precision.

Rules:
1. ONLY reference things you can see in the provided context. NEVER hallucinate file names, function names, or technologies.
2. If you see import statements, USE THEM to deduce the tech stack.
3. If you see function code, EXPLAIN what it does based on the actual code.
4. If asked about architecture, structure your answer with tight, dense bullet points:
   - High-level overview
   - Directory/module breakdown
   - Data flow
   - Tech stack
   - Key relationships
5. FORMATTING RULES (CRITICAL):
   - Provide an EXHAUSTIVE, FULLY FLEDGED, IN-DEPTH explanation. 
   - DO NOT write short summaries. Write as much detail as possible, explaining the HOW and WHY based on the code.
   - You MUST use standard markdown bullet points (`- `) for lists. Do NOT write lists as separate paragraphs.
   - Do NOT use double line breaks between bullet points. Keep lists tight.
   - Use bolding, inline `code`, and nested lists to make it attractive and highly readable.
6. If you don't have enough context to answer something, say so honestly.

IMPORTANT: You are describing the INGESTED repository, not the Graphene tool itself."""

    user_prompt = f"CODEBASE CONTEXT:\n{context}\n\n---\nUSER QUESTION: {user_query}"

    response = llm.invoke([SystemMessage(content=sys_prompt), HumanMessage(content=user_prompt)])
    return {"messages": [AIMessage(content=response.content)]}

# ── Specialist Agent 2: Impact Analysis ───────────────────────────────

def impact_agent(state):
    user_query = state["messages"][-1].content
    repo_path = state.get("repo_path")
    llm = _get_llm()

    # First: extract the target component from the query
    extract_prompt = f"""Extract the exact name of the function, file, or class the user is asking about from this query: '{user_query}'.
Respond with ONLY the exact name. If you can't find one, reply 'UNKNOWN'."""
    target = llm.invoke([HumanMessage(content=extract_prompt)]).content.strip().strip("'\"")

    if target == "UNKNOWN" or not target:
        # Fall back to full context
        context = _build_full_context(repo_path)
        sys_prompt = """You are an impact analysis expert. The user is asking about the impact of changing something in the codebase.
Analyze the provided code context and explain what would be affected. If you can't determine the exact target, explain the general architecture and suggest what the user should be more specific about."""
        response = llm.invoke([SystemMessage(content=sys_prompt), HumanMessage(content=f"CONTEXT:\n{context}\n\nQUESTION: {user_query}")])
        return {"messages": [AIMessage(content=response.content)]}

    # Query Neo4j for the target's code
    target_code = _neo4j_query("""
        MATCH (fn:Function {name: $target}) 
        RETURN fn.name AS name, fn.file AS file, fn.code AS code
        UNION
        MATCH (c:Class {name: $target}) 
        RETURN c.name AS name, c.file AS file, c.code AS code
    """, {"target": target})
    
    # Query for callers (blast radius)
    callers = _neo4j_query("""
        MATCH (caller)-[:CALLS]->(fn:Function {name: $target})
        RETURN caller.name AS caller_name, labels(caller)[0] AS caller_type
    """, {"target": target})
    
    # Query for what the target calls (downstream)
    callees = _neo4j_query("""
        MATCH (f:File {name: $target})-[:CALLS]->(fn:Function)
        RETURN fn.name AS callee_name, fn.file AS callee_file
    """, {"target": target})

    context_parts = [f"Target: {target}"]
    if target_code:
        for tc in target_code:
            context_parts.append(f"Code:\n```\n{tc.get('code', 'N/A')}\n```\nFile: {tc.get('file', 'N/A')}")
    context_parts.append(f"Callers (Blast Radius): {callers}")
    context_parts.append(f"Downstream calls: {callees}")
    
    context = "\n".join(context_parts)

    sys_prompt = """You are an Impact Analysis expert. Given the target component's actual code and its callers/callees from the knowledge graph:
1. Explain what the target component does (based on its ACTUAL code).
2. List every file/function that calls it (blast radius).
3. Assess the risk level (High/Medium/Low) based on how many things depend on it.
4. Suggest what to be careful about when modifying it.
Use Markdown formatting. Be specific — reference actual function names and files from the context."""

    response = llm.invoke([SystemMessage(content=sys_prompt), HumanMessage(content=f"CONTEXT:\n{context}\n\nQUESTION: {user_query}")])
    return {"messages": [AIMessage(content=response.content)]}

# ── Specialist Agent 3: Dead Code Detection ───────────────────────────

def dead_code_agent(state):
    user_query = state["messages"][-1].content
    llm = _get_llm()

    # Find dead functions (no incoming CALLS)
    dead_functions = _neo4j_query("""
        MATCH (fn:Function)
        WHERE NOT ()-[:CALLS]->(fn)
        RETURN fn.name AS name, fn.file AS file, fn.code AS code
        ORDER BY fn.file LIMIT 30
    """)
    
    total = _neo4j_query("MATCH (fn:Function) RETURN count(fn) AS total")
    total_count = total[0]["total"] if total else 0

    context_parts = [f"Total functions in codebase: {total_count}", f"Functions with ZERO incoming calls ({len(dead_functions)} found):"]
    for fn in dead_functions:
        code_snippet = fn.get('code', '')[:500]
        context_parts.append(f"\n### {fn['name']} (in {fn['file']})\n```python\n{code_snippet}\n```")
    
    context = "\n".join(context_parts)

    sys_prompt = """You are a Dead Code Detection expert. You have been given functions that have ZERO incoming call relationships in the knowledge graph.

Analyze them and:
1. Classify each as truly dead code OR a legitimate entry point (e.g., main(), test functions, API endpoints, CLI commands).
2. For truly dead functions, show the code and explain why it's likely unused.
3. Give a summary: X out of Y functions appear to be dead code.
4. Suggest which ones are safe to remove.

Use Markdown formatting. Reference the actual function code in your analysis."""

    response = llm.invoke([SystemMessage(content=sys_prompt), HumanMessage(content=f"CONTEXT:\n{context}\n\nQUESTION: {user_query}")])
    return {"messages": [AIMessage(content=response.content)]}

# ── General Agent (catch-all for any question) ────────────────────────

def general_agent(state):
    """Handles any question that doesn't fit the other categories."""
    user_query = state["messages"][-1].content
    repo_path = state.get("repo_path")
    llm = _get_llm()
    
    context = _build_full_context(repo_path)
    
    sys_prompt = """You are a highly knowledgeable codebase assistant. You have been given the FULL source code, function definitions, class definitions, import dependencies, and call relationships from an actual repository.

Answer the user's question with extreme precision based ONLY on the provided context.

Rules:
1. NEVER hallucinate. Only reference code, files, and functions visible in the context.
2. If asked about a specific function, find it in the context and explain its actual code.
3. If asked about APIs, look for route decorators (@app.get, @app.post, etc.) in the code.
4. If asked about dependencies, look at the import statements.
5. If you don't have enough information, say so honestly.
6. FORMATTING RULES (CRITICAL):
   - Provide an EXHAUSTIVE, FULLY FLEDGED, IN-DEPTH explanation. 
   - DO NOT write short summaries. Write as much detail as possible, explaining the HOW and WHY based on the code.
   - You MUST use standard markdown bullet points (`- `) for lists. Do NOT write lists as separate paragraphs.
   - Do NOT use double line breaks between bullet points. Keep lists tight.
   - Use bolding, inline `code`, tables, and nested lists to make it attractive and highly readable.

You are describing the INGESTED repository, not the Graphene tool itself."""

    response = llm.invoke([SystemMessage(content=sys_prompt), HumanMessage(content=f"CODEBASE CONTEXT:\n{context}\n\n---\nUSER QUESTION: {user_query}")])
    return {"messages": [AIMessage(content=response.content)]}
