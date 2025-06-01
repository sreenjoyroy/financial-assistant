from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
import logging

from sentence_transformers import SentenceTransformer, util
import torch

app = FastAPI(title="RAG-Based Semantic Analysis Agent")

logging.basicConfig(level=logging.INFO)

# Load pre-trained sentence transformer model
model = SentenceTransformer('all-MiniLM-L6-v2')

# ----------------------------
# Data Models
# ----------------------------

class AnalyzeRequest(BaseModel):
    chunks: List[str]
    query: str

class AnalyzeResponse(BaseModel):
    analysis: str
    top_chunks: List[str]

# ----------------------------
# Helper Functions
# ----------------------------

def rank_chunks_by_query_similarity(chunks: List[str], query: str, top_k: int = 3) -> List[str]:
    if not chunks:
        return []

    query_embedding = model.encode(query, convert_to_tensor=True)
    chunk_embeddings = model.encode(chunks, convert_to_tensor=True)

    # Compute cosine similarities between the query and each chunk
    cosine_scores = util.cos_sim(query_embedding, chunk_embeddings)[0]
    top_indices = torch.topk(cosine_scores, k=min(top_k, len(chunks))).indices

    # Select top-k most relevant chunks
    top_chunks = [chunks[i] for i in top_indices]
    return top_chunks

def summarize_chunks(chunks: List[str], query: str) -> str:
    if not chunks:
        return "No relevant information found to summarize."

    summary = "\n".join(f"- {chunk.strip()}" for chunk in chunks)
    return f"Based on your query: '{query}', here are the top insights:\n\n{summary}"

# ----------------------------
# Endpoint
# ----------------------------

@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(request: AnalyzeRequest):
    logging.info(f"Received analysis request for query: {request.query}")

    if not request.chunks:
        return AnalyzeResponse(
            analysis="No context available for analysis.",
            top_chunks=[]
        )

    top_chunks = rank_chunks_by_query_similarity(request.chunks, request.query, top_k=3)
    summary = summarize_chunks(top_chunks, request.query)

    return AnalyzeResponse(analysis=summary, top_chunks=top_chunks)
