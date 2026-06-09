import os
from neo4j import GraphDatabase

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "graphene_password")

def get_driver():
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

def build_graph(ast_facts: list):
    """
    Takes the AST facts and creates nodes and relationships in Neo4j.
    """
    driver = get_driver()
    
    with driver.session() as session:
        for fact in ast_facts:
            if fact["type"] == "Function":
                session.run(
                    "MERGE (f:Function {name: $name, file: $file})",
                    name=fact["name"], file=fact["file"]
                )
            elif fact["type"] == "Class":
                session.run(
                    "MERGE (c:Class {name: $name, file: $file})",
                    name=fact["name"], file=fact["file"]
                )
            elif fact["type"] == "Call":
                # For a call, we link the file to the target function
                # In a more advanced version, we'd link caller function to target function.
                session.run(
                    """
                    MERGE (f:File {name: $file})
                    WITH f
                    MATCH (func:Function {name: $target})
                    MERGE (f)-[:CALLS]->(func)
                    """,
                    file=fact["caller_file"], target=fact["target"]
                )
                
    driver.close()
