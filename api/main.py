import os
import json
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import uvicorn
import uuid
from neo4j import GraphDatabase
from qdrant_client import QdrantClient
from api.db import add_recent_search
import jwt
from dotenv import load_dotenv

# Load environment variables first
load_dotenv()

# In-memory state
job_statuses = {}
# Store the repo path so agents can read raw files
current_repo_path = {"path": None}

app = FastAPI(
    title="Graphene API",
    description="Multi-Agent Code Intelligence Platform",
    version="0.1.0"
)

# Import routers
from api.auth import router as auth_router, JWT_SECRET, JWT_ALGORITHM
app.include_router(auth_router, prefix="/api/auth", tags=["Auth"])

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class IngestRequest(BaseModel):
    repo_url: str
    branch: str = "main"
    token: Optional[str] = None

class QueryRequest(BaseModel):
    query: str

def process_repo_task(job_id: str, repo_url: str, branch: str):
    job_statuses[job_id] = "STARTED"
    try:
        from ingestion.clone import clone_repo
        repo_path = clone_repo(repo_url, branch)
        current_repo_path["path"] = repo_path
        
        from parsing.ast_parser import parse_directory
        ast_data = parse_directory(repo_path)
        
        from graph.builder import build_graph
        build_graph(ast_data, repo_path)
        
        from index.embed import embed_code
        embed_code(ast_data)
        
        job_statuses[job_id] = "SUCCESS"
        print(f"[{job_id}] Ingestion complete! {len(ast_data)} facts extracted.")
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Ingestion Error: {e}")
        job_statuses[job_id] = "FAILURE"

@app.post("/api/ingest")
async def ingest_repo(request: IngestRequest, background_tasks: BackgroundTasks):
    # Authenticate user if token provided
    github_id = None
    if request.token:
        try:
            payload = jwt.decode(request.token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            github_id = payload.get("sub")
        except:
            pass

    active_jobs = [jid for jid, status in job_statuses.items() if status in ["PENDING", "STARTED"]]
    
    if active_jobs:
        # Idempotent return for React Strict Mode double-firing
        return {
            "message": "Attached to existing ingestion task.",
            "job_id": active_jobs[0],
            "status": "PENDING"
        }
    
    job_id = str(uuid.uuid4())
    job_statuses[job_id] = "PENDING"
    
    # Log recent search
    if github_id:
        add_recent_search(github_id, request.repo_url)

    background_tasks.add_task(process_repo_task, job_id, request.repo_url, request.branch)
    return {
        "message": "Repository ingestion started.",
        "job_id": job_id,
        "status": "PENDING"
    }

@app.post("/api/query")
async def query_codebase(request: QueryRequest):
    from agents.planner import run_query
    repo_path = current_repo_path.get("path")
    response = run_query(request.query, repo_path)
    return {
        "query": request.query,
        "response": response
    }

@app.get("/api/status/{job_id}")
async def get_status(job_id: str):
    status = job_statuses.get(job_id, "UNKNOWN")
    return {"job_id": job_id, "status": status}

@app.get("/api/graph-data")
async def get_graph_data():
    URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    USER = os.getenv("NEO4J_USER", "neo4j")
    PASSWORD = os.getenv("NEO4J_PASSWORD", "graphene_password")
    
    driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
    nodes = []
    links = []
    
    with driver.session() as session:
        # Get all nodes
        records = session.run("""
            MATCH (n) 
            RETURN elementId(n) as id, coalesce(n.name, n.text) as name, labels(n)[0] as group 
            LIMIT 300
        """)
        node_ids = set()
        for r in records:
            nodes.append({"id": str(r["id"]), "name": r["name"], "group": r["group"]})
            node_ids.add(str(r["id"]))
            
        # Get edges between known nodes
        records = session.run("""
            MATCH (n)-[r]->(m) 
            RETURN elementId(n) as source, elementId(m) as target, type(r) as type 
            LIMIT 600
        """)
        for r in records:
            source = str(r["source"])
            target = str(r["target"])
            if source in node_ids and target in node_ids:
                links.append({"source": source, "target": target, "type": r["type"]})
                
    driver.close()
    return {"nodes": nodes, "links": links}

# ── File Explorer APIs ────────────────────────────────────────────────

@app.get("/api/files")
async def get_file_tree():
    """Returns the directory structure of the currently ingested repository."""
    repo_path = current_repo_path.get("path")
    if not repo_path or not os.path.exists(repo_path):
        raise HTTPException(status_code=404, detail="No repository currently ingested.")

    def build_tree(path):
        tree = []
        ignore_dirs = {'.git', 'node_modules', 'venv', 'env', '__pycache__', 'dist', 'build', '.next'}
        try:
            entries = sorted(os.scandir(path), key=lambda e: (not e.is_dir(), e.name.lower()))
            for entry in entries:
                if entry.name in ignore_dirs:
                    continue
                node = {
                    "name": entry.name,
                    "path": os.path.relpath(entry.path, repo_path).replace('\\', '/'),
                    "type": "directory" if entry.is_dir() else "file"
                }
                if entry.is_dir():
                    node["children"] = build_tree(entry.path)
                tree.append(node)
        except Exception:
            pass
        return tree

    return {"tree": build_tree(repo_path)}

@app.get("/api/files/content")
async def get_file_content(file_path: str):
    """Returns the raw content of a specific file."""
    repo_path = current_repo_path.get("path")
    if not repo_path or not os.path.exists(repo_path):
        raise HTTPException(status_code=404, detail="No repository currently ingested.")

    # Prevent directory traversal attacks (Windows compatible)
    target_path = os.path.abspath(os.path.join(repo_path, file_path))
    repo_abs_path = os.path.abspath(repo_path)
    if not os.path.commonpath([repo_abs_path, target_path]) == repo_abs_path:
        raise HTTPException(status_code=403, detail="Access denied.")

    if not os.path.isfile(target_path):
        raise HTTPException(status_code=404, detail="File not found.")

    try:
        with open(target_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        return {"content": content, "path": file_path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

