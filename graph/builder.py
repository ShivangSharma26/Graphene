import os
from neo4j import GraphDatabase

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "graphene_password")

def get_driver():
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

def build_graph(ast_facts: list, repo_path: str = None):
    """
    Takes the AST facts and creates a rich knowledge graph in Neo4j.
    Stores: File nodes (with content), Function nodes (with code), Class nodes (with code),
    and relationships: DEFINED_IN, CALLS, IMPORTS_FILE.
    """
    driver = get_driver()
    
    with driver.session() as session:
        # Wipe the database before adding new repo facts
        session.run("MATCH (n) DETACH DELETE n")
        
        # --- Pass 1: Create File nodes ---
        file_facts = [f for f in ast_facts if f["type"] == "File"]
        for fact in file_facts:
            session.run("""
                CREATE (f:File {
                    name: $name, 
                    content: $content, 
                    language: $language,
                    line_count: $line_count
                })
            """, 
                name=fact["name"], 
                content=fact.get("content", ""),
                language=fact.get("language", "Unknown"),
                line_count=fact.get("line_count", 0)
            )
        
        # --- Pass 2: Create Function nodes with code ---
        func_facts = [f for f in ast_facts if f["type"] == "Function"]
        for fact in func_facts:
            session.run("""
                MERGE (fn:Function {name: $name, file: $file})
                ON CREATE SET fn.code = $code, fn.start_line = $start_line, fn.end_line = $end_line
            """,
                name=fact["name"], 
                file=fact["file"],
                code=fact.get("code", ""),
                start_line=fact.get("start_line", 0),
                end_line=fact.get("end_line", 0)
            )
            # Link function to its file
            session.run("""
                MATCH (fn:Function {name: $name, file: $file})
                MATCH (f:File {name: $file})
                MERGE (fn)-[:DEFINED_IN]->(f)
            """, name=fact["name"], file=fact["file"])
        
        # --- Pass 3: Create Class nodes with code ---
        class_facts = [f for f in ast_facts if f["type"] == "Class"]
        for fact in class_facts:
            session.run("""
                MERGE (c:Class {name: $name, file: $file})
                ON CREATE SET c.code = $code, c.start_line = $start_line, c.end_line = $end_line
            """,
                name=fact["name"],
                file=fact["file"],
                code=fact.get("code", ""),
                start_line=fact.get("start_line", 0),
                end_line=fact.get("end_line", 0)
            )
            # Link class to its file
            session.run("""
                MATCH (c:Class {name: $name, file: $file})
                MATCH (f:File {name: $file})
                MERGE (c)-[:DEFINED_IN]->(f)
            """, name=fact["name"], file=fact["file"])
        
        # --- Pass 4: Create CALLS relationships ---
        call_facts = [f for f in ast_facts if f["type"] == "Call"]
        for fact in call_facts:
            # Link the caller file to the target function
            session.run("""
                MATCH (caller:File {name: $caller_file})
                MATCH (target:Function {name: $target})
                MERGE (caller)-[:CALLS]->(target)
            """, caller_file=fact["caller_file"], target=fact["target"])
        
        # --- Pass 5: Create FileDependency relationships (IMPORTS_FILE) ---
        file_deps = [f for f in ast_facts if f["type"] == "FileDependency"]
        for fact in file_deps:
            session.run("""
                MATCH (source:File {name: $source_file})
                MATCH (target:File {name: $target_file})
                MERGE (source)-[:IMPORTS_FILE]->(target)
            """, source_file=fact["source_file"], target_file=fact["target_file"])
            
        # Note: We completely skip processing "ThirdPartyImport" facts here 
        # to prevent external dependencies (like 'import torch') from cluttering the graph.
        third_party = [f for f in ast_facts if f["type"] == "ThirdPartyImport"]
    
    driver.close()
    print(f"Graph built: {len(file_facts)} files, {len(func_facts)} functions, {len(class_facts)} classes, {len(call_facts)} calls, {len(file_deps)} file-dependencies, {len(third_party)} third-party imports ignored visually.")
