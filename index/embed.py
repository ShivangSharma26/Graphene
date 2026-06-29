import os
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
import uuid

# In a real scenario, use Voyage AI for embeddings.
# Here we mock it for demonstration.
QDRANT_URL = os.getenv("QDRANT_URL", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))

def embed_code(ast_facts: list, collection_name="graphene_codebase"):
    """
    Generates embeddings for code snippets (functions, classes) and stores them in Qdrant.
    """
    client = QdrantClient(url=QDRANT_URL, port=QDRANT_PORT)
    
    # Always recreate the collection cleanly for a new repository
    try:
        client.delete_collection(collection_name=collection_name)
    except Exception:
        pass
        
    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
    )

    points = []
    for fact in ast_facts:
        if fact["type"] in ["Function", "Class"]:
            # Mock embedding (1536 dims) - normally you'd call an embedding API
            vector = [0.0] * 1536
            
            points.append(PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload={
                    "name": fact["name"],
                    "type": fact["type"],
                    "file": fact["file"]
                }
            ))

    if points:
        client.upsert(
            collection_name=collection_name,
            points=points
        )
