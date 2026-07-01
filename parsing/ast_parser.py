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
    and extracts facts (functions, classes, calls) WITH their full source code.
    Also creates File-level facts so we know every file in the repo.
    """
    ast_facts = []
    
    for root, _, files in os.walk(repo_path):
        for file in files:
            file_path = os.path.join(root, file)
            rel_path = os.path.relpath(file_path, repo_path).replace('\\', '/')
            
            # Skip non-source files
            ext = os.path.splitext(file)[1].lower()
            if ext not in ['.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.go', '.rs', '.rb', '.php', '.c', '.cpp', '.h']:
                continue
            
            # Read the raw file content
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    source_code = f.read()
            except Exception:
                continue
            
            # Always create a File fact with the full source content
            ast_facts.append({
                "type": "File",
                "name": rel_path,
                "content": source_code[:8000],
                "language": _detect_language(ext),
                "line_count": source_code.count('\n') + 1
            })
            
            # Only parse Python files with Tree-sitter for deeper structure
            if file.endswith('.py'):
                ast_facts.extend(_parse_python_file(source_code, rel_path, repo_path))
                
    return ast_facts

def _detect_language(ext: str) -> str:
    lang_map = {
        '.py': 'Python', '.js': 'JavaScript', '.ts': 'TypeScript',
        '.jsx': 'React/JSX', '.tsx': 'React/TSX', '.java': 'Java',
        '.go': 'Go', '.rs': 'Rust', '.rb': 'Ruby', '.php': 'PHP',
        '.c': 'C', '.cpp': 'C++', '.h': 'C/C++ Header'
    }
    return lang_map.get(ext, 'Unknown')

def _is_nested_function(node) -> bool:
    """Returns True if the function is defined inside another function."""
    parent = node.parent
    while parent:
        if parent.type == "function_definition":
            return True
        parent = parent.parent
    return False

def _resolve_module(import_stmt: str, repo_root: str) -> str | None:
    """Attempts to resolve an import string to a local file path."""
    import_stmt = import_stmt.strip()
    module_name = ""
    
    if import_stmt.startswith("from "):
        parts = import_stmt.split(" ", 2)
        if len(parts) >= 2:
            module_name = parts[1]
    elif import_stmt.startswith("import "):
        parts = import_stmt.split(" ", 1)
        if len(parts) >= 2:
            module_name = parts[1].split(",")[0].strip().split(" as ")[0]
            
    if not module_name:
        return None
        
    path = module_name.replace(".", "/")
    
    # Check if path.py exists
    if os.path.exists(os.path.join(repo_root, f"{path}.py")):
        return f"{path}.py".replace('\\', '/')
    # Check if path/__init__.py exists
    if os.path.exists(os.path.join(repo_root, path, "__init__.py")):
        return f"{path}/__init__.py".replace('\\', '/')
        
    return None

def _parse_python_file(source_code: str, rel_path: str, repo_root: str) -> list:
    """
    Parses a single Python file and returns extracted relationships.
    """
    tree = parser.parse(bytes(source_code, "utf8"))
    facts = []
    
    # 1. Extract functions (excluding nested scopes)
    func_query = PY_LANGUAGE.query("(function_definition) @function.def")
    for node, capture_name in func_query.captures(tree.root_node):
        if capture_name == "function.def":
            if _is_nested_function(node):
                continue  # Skip nested functions (closures) to prevent graph clutter
                
            name_node = node.child_by_field_name("name")
            if name_node:
                func_name = source_code[name_node.start_byte:name_node.end_byte]
                func_body = source_code[node.start_byte:node.end_byte]
                if len(func_body) > 3000:
                    func_body = func_body[:3000] + "\n# ... truncated ..."
                
                facts.append({
                    "type": "Function",
                    "name": func_name,
                    "file": rel_path,
                    "code": func_body,
                    "start_line": node.start_point[0] + 1,
                    "end_line": node.end_point[0] + 1
                })
    
    # 2. Extract classes
    class_query = PY_LANGUAGE.query("(class_definition) @class.def")
    for node, capture_name in class_query.captures(tree.root_node):
        if capture_name == "class.def":
            name_node = node.child_by_field_name("name")
            if name_node:
                class_name = source_code[name_node.start_byte:name_node.end_byte]
                class_body = source_code[node.start_byte:node.end_byte]
                if len(class_body) > 4000:
                    class_body = class_body[:4000] + "\n# ... truncated ..."
                
                facts.append({
                    "type": "Class",
                    "name": class_name,
                    "file": rel_path,
                    "code": class_body,
                    "start_line": node.start_point[0] + 1,
                    "end_line": node.end_point[0] + 1
                })
    
    # 3. Extract imports & resolve modules
    import_query = PY_LANGUAGE.query("""
        (import_statement) @import.stmt
        (import_from_statement) @import.from
    """)
    for node, capture_name in import_query.captures(tree.root_node):
        import_text = source_code[node.start_byte:node.end_byte]
        
        # Try to resolve to a local file
        resolved_file = _resolve_module(import_text, repo_root)
        
        if resolved_file:
            # Local dependency found
            facts.append({
                "type": "FileDependency",
                "source_file": rel_path,
                "target_file": resolved_file
            })
        else:
            # Third-party or unresolvable import
            facts.append({
                "type": "ThirdPartyImport",
                "text": import_text,
                "file": rel_path
            })
    
    # 4. Extract function calls
    call_query = PY_LANGUAGE.query("""
        (call function: [(identifier) @call.name (attribute attribute: (identifier) @call.name)])
    """)
    for node, capture_name in call_query.captures(tree.root_node):
        if capture_name == "call.name":
            call_name = source_code[node.start_byte:node.end_byte]
            facts.append({
                "type": "Call",
                "target": call_name,
                "caller_file": rel_path
            })
            
    return facts
