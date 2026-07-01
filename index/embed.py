import os
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
import uuid
import hashlib
import struct

QDRANT_URL = os.getenv("QDRANT_URL", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))

def _simple_hash_vector(text: str, dim: int = 128) -> list:
    """
    Creates a deterministic pseudo-embedding from text using SHA-256 hash.
    Not a real semantic embedding, but ensures different texts get different vectors
    (unlike the old [0.0]*1536 which made everything identical).
    This is enough for basic nearest-neighbor retrieval without needing an external API.
    """
    # Hash the text and expand it to fill the vector dimension
    vector = []
    for i in range(dim):
        h = hashlib.sha256(f"{text}_{i}".encode()).digest()
        val = struct.unpack('f', h[:4])[0]
        # Normalize to [-1, 1] range
        val = max(-1.0, min(1.0, val / 1e30))
        vector.append(val)
    return vector

def embed_code(ast_facts: list, collection_name="graphene_codebase"):
    """
    Stores code entities in Qdrant with their full code as payload
    and hash-based vectors for basic differentiation.
    """
    client = QdrantClient(url=QDRANT_URL, port=QDRANT_PORT, timeout=60.0, check_compatibility=False)
    
    # Recreate collection for fresh repo
    try:
        client.delete_collection(collection_name=collection_name)
    except Exception:
        pass
        
    try:
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=128, distance=Distance.COSINE),
        )
    except Exception as e:
        if "already exists" in str(e).lower():
            print(f"Collection '{collection_name}' already exists. Skipping recreation.")
        else:
            raise e

    points = []
    for fact in ast_facts:
        if fact["type"] in ["Function", "Class"]:
            code_content = fact.get("code", fact.get("name", ""))
            vector = _simple_hash_vector(code_content)
            
            points.append(PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload={
                    "name": fact["name"],
                    "type": fact["type"],
                    "file": fact["file"],
                    "code": code_content[:2000]  # Store actual code in payload
                }
            ))
        elif fact["type"] == "File":
            content = fact.get("content", "")
            vector = _simple_hash_vector(content[:500])
            
            points.append(PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload={
                    "name": fact["name"],
                    "type": "File",
                    "file": fact["name"],
                    "code": content[:2000],
                    "language": fact.get("language", "Unknown")
                }
            ))

    # Batch upsert in chunks of 100
    if points:
        for i in range(0, len(points), 100):
            client.upsert(
                collection_name=collection_name,
                points=points[i:i+100]
            )
    
    print(f"Embedded {len(points)} code entities into Qdrant")
