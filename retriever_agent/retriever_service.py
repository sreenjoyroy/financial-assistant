from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
from sentence_transformers import SentenceTransformer
import faiss
import numpy as np
import logging
import os
from uuid import uuid4

# -----------------------------
# Logging Setup
# -----------------------------
LOG_FILE = os.getenv("LOG_FILE", "../logs/retriever_logs.json")
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format='%(asctime)s %(message)s')

# -----------------------------
# FastAPI Init
# -----------------------------
app = FastAPI(title="Retriever Agent - FAISS Service")

# -----------------------------
# Embedding + FAISS Setup
# -----------------------------
embedder = SentenceTransformer('all-MiniLM-L6-v2')
dimension = embedder.get_sentence_embedding_dimension()
index = faiss.IndexFlatL2(dimension)
doc_store = []

# -----------------------------
# Request Schemas
# -----------------------------
class IndexDocsRequest(BaseModel):
    documents: List[str]

class RetrieveDocsRequest(BaseModel):
    query: str
    top_k: int = 3

# -----------------------------
# Indexing Endpoint
# -----------------------------
@app.post("/index-docs")
def index_docs(request: IndexDocsRequest):
    try:
        embeddings = embedder.encode(request.documents, convert_to_numpy=True)
        index.add(embeddings)
        doc_store.extend(request.documents)
        logging.info(f"Indexed {len(request.documents)} documents.")
        return {"status": "success", "indexed_docs": len(request.documents)}
    except Exception as e:
        logging.error(f"Indexing failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Indexing failed.")

# -----------------------------
# Retrieval Endpoint
# -----------------------------
@app.post("/retrieve")
def retrieve_docs(request: RetrieveDocsRequest):
    try:
        query_embedding = embedder.encode([request.query], convert_to_numpy=True)
        if index.ntotal == 0:
            raise HTTPException(status_code=404, detail="No documents indexed yet.")

        D, I = index.search(query_embedding, request.top_k)
        results = [doc_store[i] for i in I[0] if i < len(doc_store)]

        logging.info(f"Retrieved {len(results)} documents for query: {request.query}")
        return {
            "status": "success",
            "query": request.query,
            "chunks": results
        }
    except Exception as e:
        logging.error(f"Retrieval failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve documents.")

# -----------------------------
# Health Check
# -----------------------------
@app.get("/health")
async def health_check():
    return {"status": "ok"}
