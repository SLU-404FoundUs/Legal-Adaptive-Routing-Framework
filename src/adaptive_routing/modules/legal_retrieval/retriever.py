"""
Saint Louis University : Team 404FoundUs
@file_ retriever.py
@project_ LLM Legal Adaptive Routing Framework
@desc_ RAG retriever that queries the FAISS vector search index to extract relevant context.
@deps_ src.adaptive_routing.modules.legal_retrieval.embedding, src.adaptive_routing.config
"""

from src.adaptive_routing.modules.legal_retrieval.embedding import EmbeddingManager
from src.adaptive_routing.config import FrameworkConfig


class LegalRetriever:
    """
    @class_ LegalRetriever
    @desc_ Retrieves relevant legal text chunks from the vector index.
    @attr_ _embedding_manager : (EmbeddingManager) Handles vector search over indexed documents.
    """

    def __init__(self, embedding_manager: EmbeddingManager):
        self._embedding_manager = embedding_manager

    def _retrieve_context_(self, query: str, top_k: int = None) -> list:
        """
        @func_ _retrieve_context_ (@params query, top_k)
        @params query : (str) The user's legal question.
        @params top_k : (int) Optional override for number of chunks to retrieve.
        @return_ list[dict] : List of context matches, each containing 'chunk' and 'score'.
        @logic_ Searches the FAISS index for the most relevant chunks.
        """
        search_results = self._embedding_manager._search_(query, top_k=top_k)
        return search_results
