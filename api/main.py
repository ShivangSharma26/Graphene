import os
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import uuid
from neo4j import GraphDatabase
from qdrant_client import QdrantClient

# In-memory dictionary to track job statuses without needing Redis
job_statuses = {}

app = FastAPI(
    title="Graphene API",
    description="Multi-Agent Code Intelligence Platform",
    version="0.1.0"
)

# Serve Frontend
app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")

@app.get("/")
async def root():
    return FileResponse("frontend/index.html")

class IngestRequest(BaseModel):
    repo_url: str
    branch: str = "main"

class QueryRequest(BaseModel):
    query: str

def process_repo_task(job_id: str, repo_url: str, branch: str):
    job_statuses[job_id] = "STARTED"
    try:
        from ingestion.clone import clone_repo
        repo_path = clone_repo(repo_url, branch)
        
        from parsing.ast_parser import parse_directory
        ast_data = parse_directory(repo_path)
        
        from graph.builder import build_graph
        build_graph(ast_data)
        
        from index.embed import embed_code
        embed_code(ast_data)
        
        job_statuses[job_id] = "SUCCESS"
    except Exception as e:
        print(f"Ingestion Error: {e}")
        job_statuses[job_id] = "FAILURE"

@app.post("/ingest")
async def ingest_repo(request: IngestRequest, background_tasks: BackgroundTasks):
    """
    Kicks off an asynchronous background task to clone, parse, and index the repository.
    """
    job_id = str(uuid.uuid4())
    job_statuses[job_id] = "PENDING"
    
    background_tasks.add_task(process_repo_task, job_id, request.repo_url, request.branch)
    
    return {
        "message": "Repository ingestion started.",
        "job_id": job_id,
        "status": "PENDING"
    }

@app.post("/query")
async def query_codebase(request: QueryRequest):
    """
    Endpoint to query the codebase via LangGraph agents.
    """
    from agents.planner import run_query
    response = run_query(request.query)
    
    return {
        "query": request.query,
        "response": response
    }

@app.get("/status/{job_id}")
async def get_status(job_id: str):
    """
    Check the status of an ingestion job.
    """
    status = job_statuses.get(job_id, "UNKNOWN")
    return {
        "job_id": job_id, 
        "status": status
    }

@app.get("/api/graph-data")
async def get_graph_data():
    """
    Returns a sample of the Neo4j graph formatted for force-graph.js
    """
    URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    USER = os.getenv("NEO4J_USER", "neo4j")
    PASSWORD = os.getenv("NEO4J_PASSWORD", "graphene_password")
    
    driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
    nodes = []
    links = []
    
    with driver.session() as session:
        # Get nodes
        records = session.run("MATCH (n) RETURN id(n) as id, n.name as name, labels(n)[0] as group LIMIT 200")
        node_ids = set()
        for r in records:
            nodes.append({"id": str(r["id"]), "name": r["name"], "group": r["group"]})
            node_ids.add(str(r["id"]))
            
        # Get edges between known nodes
        records = session.run("MATCH (n)-[r]->(m) RETURN id(n) as source, id(m) as target, type(r) as type LIMIT 400")
        for r in records:
            source = str(r["source"])
            target = str(r["target"])
            if source in node_ids and target in node_ids:
                links.append({"source": source, "target": target, "type": r["type"]})
                
    driver.close()
    return {"nodes": nodes, "links": links}

@app.get("/api/vector-data")
async def get_vector_data():
    """
    Returns a sample of vectors from Qdrant.
    """
    try:
        QDRANT_URL = os.getenv("QDRANT_URL", "localhost")
        QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
        client = QdrantClient(url=QDRANT_URL, port=QDRANT_PORT)
        
        results, _ = client.scroll(
            collection_name="graphene_codebase",
            limit=50,
            with_payload=True
        )
        
        data = []
        for p in results:
            data.append({
                "name": p.payload.get("name"),
                "type": p.payload.get("type"),
                "file": p.payload.get("file")
            })
        return data
    except Exception as e:
        return []
