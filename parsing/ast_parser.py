import os
from tree_sitter import Language, Parser
import tree_sitter_python

# Initialize Tree-sitter for Python
PY_LANGUAGE = Language(tree_sitter_python.language(), "python")

parser = Parser()
parser.set_language(PY_LANGUAGE)

def parse_directory(repo_path: str) -> list:
    """
    Walks the repository, parses all supported files into ASTs, 
    and extracts facts (functions, classes, calls).
    """
    ast_facts = []
    
    for root, _, files in os.walk(repo_path):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                ast_facts.extend(_parse_python_file(file_path, repo_path))
                
    return ast_facts

def _parse_python_file(file_path: str, repo_root: str) -> list:
    """
    Parses a single Python file and returns extracted relationships.
    """
    rel_path = os.path.relpath(file_path, repo_root).replace('\\', '/')
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            source_code = f.read()
    except Exception:
        # Skip unreadable files
        return []
        
    tree = parser.parse(bytes(source_code, "utf8"))
    
    facts = []
    
    # Query for functions and classes and calls
    query = PY_LANGUAGE.query("""
        (function_definition name: (identifier) @function.name)
        (class_definition name: (identifier) @class.name)
        (call function: [(identifier) @call.name (attribute attribute: (identifier) @call.name)])
    """)
    
    captures = query.captures(tree.root_node)
    
    for node, capture_name in captures:
        name = source_code[node.start_byte:node.end_byte]
        
        if capture_name == "function.name":
            facts.append({
                "type": "Function",
                "name": name,
                "file": rel_path,
                "relationship": "DEFINED_IN"
            })
        elif capture_name == "class.name":
            facts.append({
                "type": "Class",
                "name": name,
                "file": rel_path,
                "relationship": "DEFINED_IN"
            })
        elif capture_name == "call.name":
            facts.append({
                "type": "Call",
                "target": name,
                "caller_file": rel_path,
                "relationship": "CALLS"
            })
            
    return facts
