import sys
import os
import shutil

# Ensure we can import from our local modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ingestion.clone import clone_repo
from parsing.ast_parser import parse_directory
from graph.builder import build_graph
from index.embed import embed_code

def main():
    repo_url = "https://github.com/psf/requests.git"
    branch = "main"
    
    print("=== Graphene Pipeline Test ===")
    
    # 1. Clone
    print(f"\n1. Cloning {repo_url}...")
    try:
        repo_path = clone_repo(repo_url, branch)
        print(f"Successfully cloned to: {repo_path}")
    except Exception as e:
        print(f"Clone failed: {e}")
        return
        
    # 2. Parse
    print("\n2. Parsing AST...")
    try:
        ast_facts = parse_directory(repo_path)
        print(f"Successfully extracted {len(ast_facts)} facts (functions, classes, calls).")
        # Print a sample
        if ast_facts:
            print(f"Sample fact: {ast_facts[0]}")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Parsing failed: {e}")
        return
        
    # 3. Graph Build
    print("\n3. Building Knowledge Graph in Neo4j...")
    try:
        build_graph(ast_facts)
        print("Graph built successfully.")
    except Exception as e:
        print(f"Graph building failed: {e}")
        return
        
    # 4. Embed
    print("\n4. Embedding Code into Qdrant...")
    try:
        embed_code(ast_facts)
        print("Embeddings stored successfully.")
    except Exception as e:
        print(f"Embedding failed: {e}")
        return
        
    print("\n=== Pipeline Test Complete ===")
    
    # Cleanup (optional)
    # shutil.rmtree(repo_path)

if __name__ == "__main__":
    main()
