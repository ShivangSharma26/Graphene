import os
from celery import Celery

# Redis is used as the message broker for Celery
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "graphene_worker",
    broker=redis_url,
    backend=redis_url
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)

@celery_app.task(bind=True, name="process_repository")
def process_repository(self, job_id: str, repo_url: str, branch: str):
    """
    Background task to process a repository.
    """
    try:
        print(f"[{job_id}] Starting ingestion for {repo_url} on branch {branch}...")
        self.update_state(state='STARTED', meta={'step': 'cloning'})
        
        # 1. Clone Repo
        from ingestion.clone import clone_repo
        repo_path = clone_repo(repo_url, branch)
        
        self.update_state(state='PROCESSING', meta={'step': 'parsing'})
        # 2. Parse AST
        from parsing.ast_parser import parse_directory
        ast_data = parse_directory(repo_path)
        
        self.update_state(state='PROCESSING', meta={'step': 'graph'})
        # 3. Build Graph
        from graph.builder import build_graph
        build_graph(ast_data)
        
        self.update_state(state='PROCESSING', meta={'step': 'embedding'})
        # 4. Embed to Vector DB
        from index.embed import embed_code
        embed_code(ast_data)
        
        print(f"[{job_id}] Ingestion complete!")
        return {"status": "success", "job_id": job_id, "repo": repo_url}
        
    except Exception as e:
        print(f"[{job_id}] Error during ingestion: {str(e)}")
        raise e
