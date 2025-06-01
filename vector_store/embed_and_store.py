import os
import faiss
import numpy as np
from typing import List, Tuple
from sentence_transformers import SentenceTransformer
import pickle

class VectorStore:
    """
    A simple vector store that embeds documents and stores them in a FAISS index,
    supporting similarity search and persistence.
    """

    def __init__(self, 
                 embedding_model_name: str = "all-MiniLM-L6-v2",
                 index_path: str = "vector_store/faiss.index",
                 metadata_path: str = "vector_store/metadata.pkl"):
        """
        Initialize the vector store.

        Args:
            embedding_model_name (str): Name of the sentence-transformers model to use.
            index_path (str): File path to save/load the FAISS index.
            metadata_path (str): File path to save/load the document metadata.
        """
        self.embedding_model = SentenceTransformer(embedding_model_name)
        self.index_path = index_path
        self.metadata_path = metadata_path

        # Initialize empty structures
        self.index = None
        self.metadata = []

        # Load index and metadata if available
        self._load()

    def _load(self):
        """Load index and metadata from disk if they exist."""
        if os.path.exists(self.index_path) and os.path.exists(self.metadata_path):
            try:
                self.index = faiss.read_index(self.index_path)
                with open(self.metadata_path, "rb") as f:
                    self.metadata = pickle.load(f)
                print(f"Loaded FAISS index and metadata from disk. Num vectors: {self.index.ntotal}")
            except Exception as e:
                print(f"Failed to load vector store: {e}")
                self.index = None
                self.metadata = []
        else:
            # Initialize a new index
            self.index = None
            self.metadata = []

    def _save(self):
        """Save index and metadata to disk."""
        if self.index:
            faiss.write_index(self.index, self.index_path)
            with open(self.metadata_path, "wb") as f:
                pickle.dump(self.metadata, f)
            print(f"Saved FAISS index and metadata to disk. Num vectors: {self.index.ntotal}")

    def add_documents(self, docs: List[str], metadatas: List[dict] = None):
        """
        Add documents to the vector store.

        Args:
            docs (List[str]): List of document texts to embed and add.
            metadatas (List[dict], optional): List of metadata dicts corresponding to docs.
        """
        if not docs:
            raise ValueError("No documents provided to add.")

        # Embed documents
        embeddings = self.embedding_model.encode(docs, convert_to_numpy=True, normalize_embeddings=True)

        # Initialize FAISS index if not present
        dim = embeddings.shape[1]
        if self.index is None:
            self.index = faiss.IndexFlatIP(dim)  # Using Inner Product (cosine similarity after normalization)

        # Add embeddings to index
        self.index.add(embeddings)

        # Store metadata
        if metadatas is None:
            metadatas = [{}] * len(docs)
        self.metadata.extend(metadatas)

        # Save updated index and metadata
        self._save()

    def query(self, query_text: str, top_k: int = 5) -> List[Tuple[str, float]]:
        """
        Query the vector store with a text string and return top_k matching documents.

        Args:
            query_text (str): The query text to embed and search.
            top_k (int): Number of top results to return.

        Returns:
            List[Tuple[str, float]]: List of (document_text, similarity_score) tuples.
        """
        if self.index is None or self.index.ntotal == 0:
            print("Vector store is empty. Add documents before querying.")
            return []

        # Embed query
        query_emb = self.embedding_model.encode([query_text], convert_to_numpy=True, normalize_embeddings=True)

        # Search index
        D, I = self.index.search(query_emb, top_k)

        results = []
        for score, idx in zip(D[0], I[0]):
            if idx < len(self.metadata):
                doc_meta = self.metadata[idx]
                doc_text = doc_meta.get("text", "") if "text" in doc_meta else ""
                # Fallback: if no text stored in metadata, just empty string
                results.append((doc_text, float(score)))
            else:
                results.append(("", float(score)))

        return results

    def add_texts_with_metadata(self, docs: List[str]):
        """
        Add documents with text stored in metadata for retrieval.

        Args:
            docs (List[str]): List of document texts to add.
        """
        metadatas = [{"text": d} for d in docs]
        self.add_documents(docs, metadatas)


if __name__ == "__main__":
    # Example usage
    store = VectorStore()

    # Add sample docs
    sample_docs = [
        "Taiwan Semiconductor Manufacturing Company reported earnings beat of 4%.",
        "Samsung Electronics missed earnings estimates by 2%.",
        "Asia tech stocks are currently seeing neutral market sentiment with caution due to rising yields."
    ]

    store.add_texts_with_metadata(sample_docs)

    query = "Earnings surprises in Asia tech stocks"
    results = store.query(query, top_k=3)

    print("Query results:")
    for doc, score in results:
        print(f"Score: {score:.4f} - Text: {doc}")
