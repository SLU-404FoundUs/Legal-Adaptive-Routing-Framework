## Saint Louis University
## Team 404FoundUs
## @file src/adaptive_routing/modules/retrieval.py
## @project_ LLM Legal Adaptive Routing Framework
## @desc_ Orchestrator module that coordinates Legal RAG retrieval: embed, search, rerank.
## @deps src.adaptive_routing.modules.legal_retrieval.embedding, src.adaptive_routing.modules.legal_retrieval.retriever, src.adaptive_routing.modules.legal_retrieval.ranker, src.adaptive_routing.config, logging

from src.adaptive_routing.modules.legal_retrieval.embedding import EmbeddingManager
from src.adaptive_routing.modules.legal_retrieval.retriever import LegalRetriever
from src.adaptive_routing.modules.legal_retrieval.ranker import LegalRanker
from src.adaptive_routing.config import FrameworkConfig
from src.adaptive_routing.modules.legal_retrieval.utils import legal_indexing
import os
import json
import logging

logger = logging.getLogger(__name__)

class LegalRetrievalModule:
    """
    @class LegalRetrievalModule
    @desc_ Facade/Orchestrator that manages the full RAG pipeline: Ingest -> Search -> Rerank.
           Integrates a two-stage cascade architecture:
           Stage 1: Hybrid FAISS+BM25 search via EmbeddingManager/LegalRetriever
           Stage 2: Soft-Boosting Coarse Ranker + Precision Reranker via LegalRanker
    @attr_ _embedding_manager : (EmbeddingManager) Component for document indexing and vector search.
    @attr_ _retriever : (LegalRetriever) Component that queries the index for relevant context.
    @attr_ _ranker : (LegalRanker) Component that performs two-stage cascade reranking.
    """
    def __init__(self, api_key=None, embedding_manager=None, retriever=None, ranker=None, index_path=None, chunks_path=None):
        ## @logic_ Initialize embedding manager with Retrieval-specific configuration if not provided
        self._embedding_manager = embedding_manager or EmbeddingManager(
            api_key=api_key,
            model=FrameworkConfig._RETRIEVAL_MODEL,
            chunk_size=FrameworkConfig._RETRIEVAL_CHUNK_SIZE,
            chunk_overlap=FrameworkConfig._RETRIEVAL_CHUNK_OVERLAP
        )

        ## @logic_ Initialize retriever with filtering capabilities
        self._retriever = retriever or LegalRetriever(self._embedding_manager)

        ## @logic_ Initialize ranker for two-stage cascade reranking
        self._ranker = ranker or LegalRanker()
        
        ## @logic_ Auto-load FAISS index if specified in settings
        target_index = index_path or FrameworkConfig._RETRIEVAL_INDEX_PATH
        target_chunks = chunks_path or FrameworkConfig._RETRIEVAL_CHUNKS_PATH
        
        if target_index and target_chunks:
            if os.path.exists(target_index) and os.path.exists(target_chunks):
                self._load_index_(target_index, target_chunks)
            else:
                logger.warning(f"Index or chunk file not found at {target_index} / {target_chunks}.")

    def _ingest_documents_(self, documents: list):
        """
        @func_ _ingest_documents_
        @params documents : (list[str]) Raw legal document texts to add.
        @returns None
        @desc_ Embeds and indexes the provided documents into the FAISS vector store.
        """
        self._embedding_manager._add_documents_(documents, bypass_chunking=True)

    def _process_retrieval_(self, query: str, signals: list = None, top_k: int = None) -> dict:
        """
        @func_ _process_retrieval_
        @params query : (str) The user's legal question.
        @params signals : (list, optional) A list of keyword phrases from the Semantic Router.
        @params top_k : (int, optional) Number of context chunks to retrieve.
        @returns (dict) Contains 'query', 'retrieved_chunks', 'combined_query',
                 'dominant_corpus', and 'reranked_best'.
        @desc_ Main entry point — retrieves relevant context chunks from the index,
               applies two-stage cascade reranking (Soft-Boost + Precision Reranker),
               and returns the enriched result.
        """
        ## @logic_ Combine original query with search signals for enhanced retrieval
        search_query = query
        if signals and isinstance(signals, list):
            valid_signals = [str(s).strip() for s in signals if s]
            if valid_signals:
                search_query = f"{query} {' '.join(valid_signals)}"
        
        ## @logic_ Stage 1: Hybrid FAISS+BM25 search (existing pipeline)
        retrieved_chunks = self._retriever._retrieve_context_(search_query, top_k=top_k)
        
        ## @logic_ Stage 2: Two-stage cascade reranking via LegalRanker
        dominant_corpus = None
        reranked_best = None

        if retrieved_chunks:
            try:
                ## @logic_ Group retrieved chunks by corpus source for multi-corpus evaluation
                faiss_results_dict = self._group_by_corpus_(retrieved_chunks)

                ## @logic_ Stage 2a: Soft-Boosting Coarse Ranker
                boosted_pool, classifier_status = self._ranker._retrieval_classifier_(
                    query=search_query,
                    faiss_results_dict=faiss_results_dict
                )

                if classifier_status == "PASS" and boosted_pool:
                    ## @logic_ Identify the dominant corpus from boosted results
                    dominant_corpus = boosted_pool[0]["source"]

                    ## @logic_ Stage 2b: Precision Reranker on top-N candidates
                    best_chunk, rerank_status = self._ranker._rerank_selection_(
                        query=search_query,
                        boosted_pool=boosted_pool
                    )

                    if rerank_status == "PASS" and best_chunk:
                        reranked_best = best_chunk

                    ## @logic_ Replace retrieved_chunks with reranked order, preserving metadata
                    retrieved_chunks = self._merge_reranked_(retrieved_chunks, boosted_pool)

                elif classifier_status == "DOMAIN_REFUSAL":
                    logger.info("Domain refusal from coarse ranker — returning raw FAISS results.")

            except Exception as e:
                ## @logic_ Graceful fallback: if reranking fails, return original FAISS results
                logger.warning(f"Reranking cascade failed, using raw FAISS results: {e}")

        return {
            "query": query,
            "combined_query": search_query,
            "retrieved_chunks": retrieved_chunks,
            "dominant_corpus": dominant_corpus,
            "reranked_best": reranked_best
        }

    def _group_by_corpus_(self, retrieved_chunks):
        """
        @func_ _group_by_corpus_
        @params retrieved_chunks : (list[dict]) Results from LegalRetriever.
        @returns (dict) Mapping of corpus_name -> list of chunk texts.
        @desc_ Groups retrieved chunks by their corpus origin using metadata jurisdiction.
               Falls back to 'Unknown' if no jurisdiction metadata is present.
        """
        corpus_groups = {}
        for chunk_data in retrieved_chunks:
            metadata = chunk_data.get("metadata", {})
            ## @logic_ Derive corpus name from jurisdiction metadata (set during indexing)
            corpus_name = metadata.get("jurisdiction", "Unknown")
            if corpus_name not in corpus_groups:
                corpus_groups[corpus_name] = []
            corpus_groups[corpus_name].append(chunk_data.get("chunk", ""))
        
        return corpus_groups

    def _merge_reranked_(self, original_chunks, boosted_pool):
        """
        @func_ _merge_reranked_
        @params original_chunks : (list[dict]) Original retriever results with full metadata.
        @params boosted_pool : (list[dict]) Reranked results from the coarse ranker.
        @returns (list[dict]) Reordered chunks with boosted scores and source attribution.
        @desc_ Merges the reranked ordering back with original metadata, preserving the
               enriched score and adding 'source' attribution for each chunk.
        """
        ## @logic_ Build a lookup from chunk text to original metadata
        metadata_lookup = {}
        for chunk_data in original_chunks:
            chunk_text = chunk_data.get("chunk", "")
            if chunk_text not in metadata_lookup:
                metadata_lookup[chunk_text] = chunk_data.get("metadata", {})

        ## @logic_ Rebuild the results list in reranked order
        merged = []
        for item in boosted_pool:
            chunk_text = item["chunk"]
            merged.append({
                "chunk": chunk_text,
                "metadata": metadata_lookup.get(chunk_text, {}),
                "score": item["score"],
                "source": item["source"]
            })

        return merged

    def _save_index_(self, index_path: str, chunks_path: str):
        """
        @func_ _save_index_
        @params index_path : (str) File path for the FAISS index binary.
        @params chunks_path : (str) File path for the chunk metadata JSON.
        @desc_ Persists the current FAISS index and text chunks to disk.
        """
        self._embedding_manager._save_index_(index_path, chunks_path)

    def _load_index_(self, index_path: str, chunks_path: str):
        """
        @func_ _load_index_
        @params index_path : (str) File path of the saved FAISS index.
        @params chunks_path : (str) File path of the saved chunk metadata JSON.
        @desc_ Loads a previously persisted index and chunks from disk.
        """
        self._embedding_manager._load_index_(index_path, chunks_path)

    def build_and_save_index(self, corpus_dir: str, output_dir: str, index_prefix: str) -> str:
        """
        @func_ build_and_save_index
        @params corpus_dir : (str) Path to the directory containing JSON corpus files.
        @params output_dir : (str) Directory where index will be saved.
        @params index_prefix : (str) Prefix for the output files.
        @returns (str) Path to the created FAISS index file.
        @desc_ Utility function that delegates to rebuild_index to crawl and persist a FAISS store.
        """
        return legal_indexing.rebuild_index(
            corpus_dir=corpus_dir,
            output_dir=output_dir,
            index_prefix=index_prefix
        )
