"""
Saint Louis University : Team 404FoundUs
@file_ embedding.py
@project_ LLM Legal Adaptive Routing Framework
@desc_ Manages document embeddings via OpenRouter and FAISS vector index for legal RAG retrieval.
@deps_ requests, json, numpy, faiss, src.adaptive_routing.config, src.adaptive_routing.core.exceptions
"""

import requests
import json
import numpy as np
import faiss
from src.adaptive_routing.config import FrameworkConfig
from src.adaptive_routing.core.exceptions import (
    AuthenticationError,
    APIConnectionError,
    APIResponseError,
    InvalidInputError
)


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
        self._url = "https://openrouter.ai/api/v1/embeddings"

        ## @logic_ Index and metadata storage
        self._index = None
        self._chunks = []
        self._dimension = None

    # ------------------------------------------------------------------
    # Chunking
    # ------------------------------------------------------------------
    def _chunk_text_(self, text: str) -> list:
        """
        @func_ _chunk_text_ (@params text)
        @params text : (str) Raw document text.
        @return_ list[str] : List of text chunks.
        @desc_ Splits a document into overlapping character-level chunks.
        """
        if not text or not text.strip():
            raise InvalidInputError("Cannot chunk empty text.")

        chunks = []
        start = 0
        text_len = len(text)

        while start < text_len:
            end = min(start + self._chunk_size, text_len)
            chunks.append(text[start:end])
            ## @logic_ Advance by (chunk_size - overlap) to create overlap window
            start += self._chunk_size - self._chunk_overlap
            if start >= text_len:
                break

        return chunks

    # ------------------------------------------------------------------
    # Embedding via OpenRouter
    # ------------------------------------------------------------------
    def _get_embeddings_(self, texts: list) -> np.ndarray:
        """
        @func_ _get_embeddings_ (@params texts)
        @params texts : (list[str]) List of text strings to embed.
        @return_ np.ndarray : Matrix of shape (len(texts), dimension).
        @desc_ Calls the OpenRouter /embeddings endpoint for the configured model.
        """
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/404FoundUs",
            "X-Title": "LLM Legal Adaptive Routing Framework"
        }

        payload = {
            "model": self._model,
            "input": texts
        }

        try:
            response = requests.post(self._url, headers=headers, json=payload, timeout=60)
            response.raise_for_status()

            response_json = response.json()
            if "data" not in response_json or len(response_json["data"]) == 0:
                raise APIResponseError(
                    "Invalid embedding response: 'data' field missing or empty.",
                    response_body=response_json
                )

            ## @logic_ Sort by index to preserve order, then stack into numpy array
            sorted_data = sorted(response_json["data"], key=lambda x: x["index"])
            embeddings = np.array([item["embedding"] for item in sorted_data], dtype=np.float32)
            return embeddings

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 401:
                raise AuthenticationError(
                    f"Invalid API Key. Details: {e.response.text}"
                ) from e
            raise APIResponseError(
                f"Embedding request failed ({e.response.status_code}): {e.response.text}",
                status_code=e.response.status_code
            ) from e
        except requests.exceptions.RequestException as e:
            raise APIConnectionError(
                f"Failed to connect to OpenRouter embeddings API: {str(e)}"
            ) from e

    # ------------------------------------------------------------------
    # Index Management
    # ------------------------------------------------------------------
    def _add_documents_(self, documents: list):
        """
        @func_ _add_documents_ (@params documents)
        @params documents : (list[str]) Raw document texts to chunk, embed, and index.
        @desc_ Chunks each document, generates embeddings, and adds them to the FAISS index.
        """
        all_chunks = []
        for doc in documents:
            all_chunks.extend(self._chunk_text_(doc))

        if not all_chunks:
            raise InvalidInputError("No chunks generated from provided documents.")

        embeddings = self._get_embeddings_(all_chunks)

        ## @logic_ Initialize FAISS index on first call using embedding dimension
        if self._index is None:
            self._dimension = embeddings.shape[1]
            self._index = faiss.IndexFlatL2(self._dimension)

        self._index.add(embeddings)
        self._chunks.extend(all_chunks)

    def _search_(self, query: str, top_k: int = None) -> list:
        """
        @func_ _search_ (@params query, top_k)
        @params query : (str) The search query.
        @params top_k : (int) Number of results to return (defaults to config).
        @return_ list[dict] : List of {chunk, score} dicts ranked by relevance.
        @desc_ Embeds the query and retrieves the nearest chunks from the FAISS index.
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
                results.append({
                    "chunk": self._chunks[idx],
                    "score": float(distances[0][i])
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
