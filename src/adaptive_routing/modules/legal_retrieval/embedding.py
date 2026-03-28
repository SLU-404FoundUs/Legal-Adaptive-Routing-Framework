"""
Saint Louis University : Team 404FoundUs
@file_ embedding.py
@project_ LLM Legal Adaptive Routing Framework
@desc_ Manages document embeddings via OpenRouter and FAISS vector index for legal RAG retrieval.
@deps_ requests, json, numpy, faiss, re, logging, src.adaptive_routing.config, src.adaptive_routing.core.exceptions
"""

import json
import re
from src.adaptive_routing.core.engine import LLMRequestEngine
import numpy as np
import faiss
import logging
from src.adaptive_routing.config import FrameworkConfig
from src.adaptive_routing.core.exceptions import (
    AuthenticationError,
    APIConnectionError,
    APIResponseError,
    InvalidInputError
)

logger = logging.getLogger(__name__)


class EmbeddingManager:
    """
    @class_ EmbeddingManager
    @desc_ Handles document chunking, embedding generation via OpenRouter, and FAISS index management.
    @attr_ _api_key : (str) OpenRouter API credential.
    @attr_ _model : (str) Embedding model identifier on OpenRouter.
    @attr_ _chunk_size : (int) Maximum characters per document chunk.
    @attr_ _chunk_overlap : (int) Character overlap between adjacent chunks.
    @attr_ _index : (faiss.IndexFlatL2) The FAISS vector index.
    @attr_ _chunks : (list[str]) Stored text chunks aligned with index vectors.
    @attr_ _dimension : (int|None) Embedding vector dimension, set on first embed.
    """

    def __init__(self, api_key=None, model=None, chunk_size=None, chunk_overlap=None):
        ## @logic_ Resolve API key from argument or config
        self._api_key = api_key or FrameworkConfig._API_KEY
        if not self._api_key:
            raise AuthenticationError(
                "API Key is missing. Please provide it in init or set OPENROUTER_API_KEY environment variable."
            )

        self._model = model or FrameworkConfig._RETRIEVAL_MODEL
        self._chunk_size = chunk_size if chunk_size is not None else FrameworkConfig._RETRIEVAL_CHUNK_SIZE
        self._chunk_overlap = chunk_overlap if chunk_overlap is not None else FrameworkConfig._RETRIEVAL_CHUNK_OVERLAP
        
        ## @logic_ Core Engine for API Access
        self._engine = LLMRequestEngine(api_key=self._api_key, model=self._model)
        self._engine._url = "https://openrouter.ai/api/v1/embeddings"

        ## @logic_ Index and metadata storage
        self._index = None
        self._chunks = []
        self._dimension = None

    # ------------------------------------------------------------------
    # Chunking (Sentence-Boundary Aware)
    # ------------------------------------------------------------------
    def _chunk_text_(self, text: str) -> list:
        """
        @func_ _chunk_text_ (@params text)
        @params text : (str) Raw document text.
        @return_ list[str] : List of text chunks split at sentence boundaries.
        @desc_ Splits a document into overlapping chunks at sentence boundaries,
               preserving semantic coherence. Falls back to character-level splitting
               for text without clear sentence delimiters.
        """
        if not text or not text.strip():
            raise InvalidInputError("Cannot chunk empty text.")

        ## @logic_ Split text into sentences at sentence-ending punctuation
        sentences = re.split(r'(?<=[.!?;])\s+', text)
        
        ## @logic_ If the text has no sentence boundaries, fall back to paragraph/newline splitting
        if len(sentences) <= 1 and len(text) > self._chunk_size:
            sentences = re.split(r'\n\s*\n', text)
        
        ## @logic_ If still a single massive block, use character-level splitting as last resort
        if len(sentences) <= 1 and len(text) > self._chunk_size:
            sentences = [text[i:i+500] for i in range(0, len(text), 500)]

        chunks = []
        current_chunk = ""

        for sentence in sentences:
            ## @logic_ If adding this sentence exceeds chunk_size, finalize current chunk
            if len(current_chunk) + len(sentence) > self._chunk_size and current_chunk:
                chunks.append(current_chunk.strip())
                ## @logic_ Overlap: keep the last N chars of the previous chunk for continuity
                if self._chunk_overlap > 0:
                    current_chunk = current_chunk[-self._chunk_overlap:] + " " + sentence
                else:
                    current_chunk = sentence
            else:
                current_chunk = (current_chunk + " " + sentence) if current_chunk else sentence

        ## @logic_ Don't forget the remaining text
        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        return chunks

    # ------------------------------------------------------------------
    # Embedding via OpenRouter
    # ------------------------------------------------------------------
    def _get_embeddings_(self, texts: list) -> np.ndarray:
        """
        @func_ _get_embeddings_ (@params texts)
        @params texts : (list[str]) List of text strings to embed.
        @return_ np.ndarray : Matrix of shape (len(texts), dimension).
        @desc_ Calls the OpenRouter /embeddings endpoint for the configured model using the core engine.
        """
        payload = {
            "model": self._model,
            "input": texts
        }

        response_json = self._engine._call_api_(
            payload=payload, 
            timeout=FrameworkConfig._EMBEDDING_TIMEOUT
        )

        if "data" not in response_json or len(response_json["data"]) == 0:
            raise APIResponseError(
                "Invalid embedding response: 'data' field missing or empty.",
                response_body=response_json
            )

        ## @logic_ Sort by index to preserve order, then stack into numpy array
        sorted_data = sorted(response_json["data"], key=lambda x: x["index"])
        embeddings = np.array([item["embedding"] for item in sorted_data], dtype=np.float32)
        return embeddings

    # ------------------------------------------------------------------
    # Index Management
    # ------------------------------------------------------------------
    def _add_documents_(self, documents: list, bypass_chunking: bool = False):
        """
        @func_ _add_documents_ (@params documents, bypass_chunking)
        @params documents : (list[str]) Raw document texts to chunk, embed, and index.
        @params bypass_chunking : (bool) If True, treats the input text as a single cohesive chunk without splitting.
        @desc_ Embeds text and adds them to the FAISS index. Skips chunking if bypassed.
        """
        all_chunks = []
        chunk_metadatas = []
        for doc in documents:
            if isinstance(doc, dict):
                text = doc.get("content", "")
                meta = doc.get("metadata", {})
            else:
                text = doc
                meta = {}
                
            if bypass_chunking:
                chunks = [text]
            else:
                chunks = self._chunk_text_(text)
                
            all_chunks.extend(chunks)
            chunk_metadatas.extend([meta] * len(chunks))

        if not all_chunks:
            raise InvalidInputError("No chunks generated from provided documents.")

        logger.info(f"Embedding {len(all_chunks)} chunks from {len(documents)} documents...")

        # Batch requests to support large corpora and avoid API limits
        batch_size = 100
        all_embeddings = []
        for i in range(0, len(all_chunks), batch_size):
            batch = all_chunks[i:i + batch_size]
            batch_emb = self._get_embeddings_(batch)
            all_embeddings.append(batch_emb)
            
        embeddings = np.vstack(all_embeddings)

        ## @logic_ Initialize FAISS index on first call using embedding dimension
        if self._index is None:
            self._dimension = embeddings.shape[1]
            self._index = faiss.IndexFlatL2(self._dimension)

        self._index.add(embeddings)
        self._chunks.extend([{"text": c, "metadata": m} for c, m in zip(all_chunks, chunk_metadatas)])
        logger.info(f"Index now contains {self._index.ntotal} vectors.")

    def _search_(self, query: str, top_k: int = None) -> list:
        """
        @func_ _search_ (@params query, top_k)
        @params query : (str) The search query.
        @params top_k : (int) Number of results to return (defaults to config).
        @return_ list[dict] : List of {chunk, score, metadata} dicts ranked by relevance.
        @desc_ Embeds the query and retrieves the nearest chunks from the FAISS index.
                Scores are normalized to 0-1 similarity (higher = more relevant).
        """
        if self._index is None or self._index.ntotal == 0:
            return []

        top_k = top_k if top_k is not None else FrameworkConfig._RETRIEVAL_TOP_K
        ## @logic_ Clamp top_k to available vectors
        top_k = min(top_k, self._index.ntotal)

        query_embedding = self._get_embeddings_([query])
        distances, indices = self._index.search(query_embedding, top_k)

        results = []
        for i, idx in enumerate(indices[0]):
            if idx < len(self._chunks):
                ## @logic_ Convert L2 distance to similarity score (higher = better)
                ## Formula: similarity = 1 / (1 + distance)
                ## Range: (0, 1] where 1.0 = exact match
                raw_distance = float(distances[0][i])
                similarity_score = 1.0 / (1.0 + raw_distance)
                
                chunk_data = self._chunks[idx]
                if isinstance(chunk_data, dict):
                    results.append({
                        "chunk": chunk_data["text"],
                        "metadata": chunk_data["metadata"],
                        "score": similarity_score
                    })
                else:
                    results.append({
                        "chunk": chunk_data,
                        "metadata": {},
                        "score": similarity_score
                    })

        return results

    def _save_index_(self, index_path: str, chunks_path: str):
        """
        @func_ _save_index_ (@params index_path, chunks_path)
        @params index_path : (str) File path to save the FAISS index.
        @params chunks_path : (str) File path to save the chunk metadata (JSON).
        @desc_ Persists the FAISS index and its associated text chunks to disk.
        """
        if self._index is None:
            raise InvalidInputError("No index to save. Add documents first.")

        faiss.write_index(self._index, index_path)
        with open(chunks_path, "w", encoding="utf-8") as f:
            json.dump(self._chunks, f, ensure_ascii=False)
        logger.info(f"Saved FAISS index ({self._index.ntotal} vectors) to {index_path}")

    def _load_index_(self, index_path: str, chunks_path: str):
        """
        @func_ _load_index_ (@params index_path, chunks_path)
        @params index_path : (str) File path of the saved FAISS index.
        @params chunks_path : (str) File path of the saved chunk metadata (JSON).
        @desc_ Loads a previously persisted FAISS index and its text chunks from disk.
        """
        self._index = faiss.read_index(index_path)
        self._dimension = self._index.d

        with open(chunks_path, "r", encoding="utf-8") as f:
            self._chunks = json.load(f)
        logger.info(f"Loaded FAISS index ({self._index.ntotal} vectors) from {index_path}")
