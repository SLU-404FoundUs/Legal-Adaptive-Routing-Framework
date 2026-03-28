"""
Saint Louis University : Team 404FoundUs
@file_ retriever.py
@project_ LLM Legal Adaptive Routing Framework
@desc_ RAG retriever that queries the FAISS vector search index with relevance filtering and metadata support.
@deps_ src.adaptive_routing.modules.legal_retrieval.embedding, src.adaptive_routing.config, logging
"""

import logging
from src.adaptive_routing.modules.legal_retrieval.embedding import EmbeddingManager
from src.adaptive_routing.config import FrameworkConfig

logger = logging.getLogger(__name__)


class LegalRetriever:
    """
    @class_ LegalRetriever
    @desc_ Retrieves relevant legal text chunks from the vector index with quality filtering.
    @attr_ _embedding_manager : (EmbeddingManager) Handles vector search over indexed documents.
    """

    def __init__(self, embedding_manager: EmbeddingManager):
        self._embedding_manager = embedding_manager

    def _retrieve_context_(self, query: str, top_k: int = None, score_threshold: float = None, jurisdiction: str = None) -> list:
        """
        @func_ _retrieve_context_ (@params query, top_k, score_threshold, jurisdiction)
        @params query : (str) The user's legal question.
        @params top_k : (int) Optional override for number of chunks to retrieve.
        @params score_threshold : (float) Minimum similarity score to include (0.0-1.0, higher = more relevant).
        @params jurisdiction : (str) Optional jurisdiction filter (e.g., "HK", "PH").
        @return_ list[dict] : Filtered list of context matches, each containing 'chunk', 'score', and 'metadata'.
        @logic_ Searches the FAISS index, applies score threshold filtering, and optionally filters by jurisdiction.
        """
        search_results = self._embedding_manager._search_(query, top_k=top_k)
        
        ## @logic_ Apply relevance threshold filtering
        threshold = score_threshold if score_threshold is not None else FrameworkConfig._RETRIEVAL_SCORE_THRESHOLD
        if threshold > 0.0:
            before_count = len(search_results)
            search_results = [r for r in search_results if r["score"] >= threshold]
            filtered_count = before_count - len(search_results)
            if filtered_count > 0:
                logger.info(f"Filtered {filtered_count} results below score threshold {threshold:.3f}")

        ## @logic_ Apply jurisdiction metadata filter if specified
        if jurisdiction:
            search_results = [
                r for r in search_results 
                if r.get("metadata", {}).get("jurisdiction", "").upper() == jurisdiction.upper()
            ]

        return search_results
