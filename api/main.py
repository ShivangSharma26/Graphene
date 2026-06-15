import os
from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
import uuid

# Assuming Celery is configured in workers.tasks
from workers.tasks import process_repository

app = FastAPI(
    title="Graphene API",
    description="Multi-Agent Code Intelligence Platform",
    version="0.1.0"
)

class IngestRequest(BaseModel):
    repo_url: str
    branch: str = "main"

class QueryRequest(BaseModel):
    query: str

@app.post("/ingest")
async def ingest_repo(request: IngestRequest):
    """
    Kicks off an asynchronous Celery task to clone, parse, and index the repository.
    """
    job_id = str(uuid.uuid4())
    # Send the job to Celery
    process_repository.delay(job_id, request.repo_url, request.branch)
    
    return {
        "message": "Repository ingestion started.",
        "job_id": job_id,
        "status": "processing"
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
    # Placeholder for checking Postgres or Redis for actual status
    return {"job_id": job_id, "status": "processing"}
