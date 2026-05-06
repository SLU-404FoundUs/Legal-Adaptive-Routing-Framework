## Saint Louis University
## Team 404FoundUs
## @file src/adaptive_routing/modules/legal_retrieval/ranker.py
## @project_ LLM Legal Adaptive Routing Framework
## @desc_ Two-stage cascade: Soft-Boosting Coarse Ranker → Precision Reranker for multi-corpus legal RAG.
## @deps src.adaptive_routing.core.reranker, src.adaptive_routing.config, logging

import logging
from src.adaptive_routing.core.reranker import RerankEngine
from src.adaptive_routing.config import FrameworkConfig

logger = logging.getLogger(__name__)

class LegalRanker:
    """
    @class LegalRanker
    @desc_ Implements a two-stage cascade for multi-corpus legal retrieval:
           Stage 1 (Retrieval Layer)  — Soft-Boosting Coarse Ranker: Evaluates chunks across
           corpora, identifies the dominant corpus, and applies a configurable score multiplier
           to above-mean chunks from that corpus.
           Stage 2 (Selection Layer) — Precision Reranker: Deep token-level comparison on the
           top-N boosted candidates to surface the exact statutory provision.
    @attr_ _rerank_engine : (RerankEngine) API client for OpenRouter /api/v1/rerank calls.
    """
    def __init__(self, rerank_engine=None):
        ## @logic_ Initialize rerank engine with Retrieval-specific configuration if not provided
        self._rerank_engine = rerank_engine or RerankEngine(
            model=FrameworkConfig._RETRIEVAL_RERANK_MODEL
        )

    def _retrieval_classifier_(self, query, faiss_results_dict):
        """
        @func_ _retrieval_classifier_
        @params query : (str) The user's legal question.
        @params faiss_results_dict : (dict) Mapping of corpus_name -> list of chunk texts.
        @returns (tuple) (sorted_pool: list[dict], status: str)
                 sorted_pool items: {'chunk': str, 'score': float, 'source': str}
                 status: 'PASS' or 'DOMAIN_REFUSAL'
        @desc_ Stage 1 — Soft-Boosting Coarse Ranker. Evaluates all chunks across corpora via
               the reranker, identifies the dominant corpus, and applies a BOOST_FACTOR multiplier
               exclusively to above-mean chunks from that corpus. This prevents Knowledge Blackouts
               by maintaining cross-domain visibility while remaining corpus-first.
        """
        if not faiss_results_dict:
            logger.warning("No FAISS results provided for retrieval classification.")
            return [], "DOMAIN_REFUSAL"

        ## @logic_ Collect all documents and track corpus membership
        all_documents = []
        chunk_corpus_map = []  # Parallel list tracking (corpus_name, chunk_text)

        for corpus_name, chunks in faiss_results_dict.items():
            if not chunks:
                continue
            for chunk_text in chunks:
                all_documents.append(chunk_text)
                chunk_corpus_map.append((corpus_name, chunk_text))

        if not all_documents:
            logger.warning("All corpora returned empty chunk lists.")
            return [], "DOMAIN_REFUSAL"

        ## @logic_ Coarse-rank all chunks against the query via reranker API
        rerank_results = self._rerank_engine._rerank_(
            query=query,
            documents=all_documents
        )

        ## @logic_ Build scored chunk list with corpus attribution
        all_scored_chunks = []
        corpus_max_scores = {}

        for result in rerank_results:
            idx = result["index"]
            score = result["relevance_score"]
            corpus_name, chunk_text = chunk_corpus_map[idx]

            all_scored_chunks.append({
                "chunk": chunk_text,
                "score": score,
                "source": corpus_name
            })

            ## @logic_ Track the maximum score per corpus for dominance detection
            if corpus_name not in corpus_max_scores or score > corpus_max_scores[corpus_name]:
                corpus_max_scores[corpus_name] = score

        if not all_scored_chunks:
            return [], "DOMAIN_REFUSAL"

        ## @logic_ Identify the dominant corpus (highest max-score across all corpora)
        dominant_corpus = max(corpus_max_scores, key=corpus_max_scores.get)
        logger.info(
            f"Dominant corpus identified: '{dominant_corpus}' "
            f"(max_score={corpus_max_scores[dominant_corpus]:.4f})"
        )

        ## @logic_ Soft-Boost: Apply BOOST_FACTOR only to above-mean chunks from dominant corpus
        boost_factor = FrameworkConfig._RETRIEVAL_BOOST_FACTOR
        dominant_items = [
            item["score"] for item in all_scored_chunks
            if item["source"] == dominant_corpus
        ]
        dominant_mean = sum(dominant_items) / max(1, len(dominant_items))

        for item in all_scored_chunks:
            if item["source"] == dominant_corpus and item["score"] > dominant_mean:
                item["score"] *= boost_factor

        ## @logic_ Global re-sort by boosted score
        sorted_pool = sorted(all_scored_chunks, key=lambda x: x["score"], reverse=True)

        ## @logic_ Domain confidence check — refuse if top score is below threshold
        domain_confidence = FrameworkConfig._RETRIEVAL_DOMAIN_CONFIDENCE
        if sorted_pool[0]["score"] < domain_confidence:
            logger.info(
                f"DOMAIN_REFUSAL: Top score {sorted_pool[0]['score']:.4f} "
                f"below confidence threshold {domain_confidence}."
            )
            return [], "DOMAIN_REFUSAL"

        return sorted_pool, "PASS"

    def _rerank_selection_(self, query, boosted_pool):
        """
        @func_ _rerank_selection_
        @params query : (str) The user's legal question.
        @params boosted_pool : (list[dict]) Sorted output from _retrieval_classifier_.
        @returns (tuple) (best_chunk: str | None, status: str)
                 status: 'PASS' or 'DOMAIN_REFUSAL'
        @desc_ Stage 2 — Precision Reranker. Deep token-level comparison on the top-N candidates
               from the boosted pool. Solves the Precision Gap by ensuring the generation model
               is grounded in the exact statutory provision, not a thematically adjacent one.
        """
        if not boosted_pool:
            logger.warning("Empty boosted pool passed to precision reranker.")
            return None, "DOMAIN_REFUSAL"

        ## @logic_ Extract top-N candidates for precision reranking
        top_n = FrameworkConfig._RETRIEVAL_RERANK_TOP_N
        top_candidates = [item["chunk"] for item in boosted_pool[:top_n]]

        ## @logic_ Precision rerank via reranker API (higher-precision pass on smaller set)
        rerank_results = self._rerank_engine._rerank_(
            query=query,
            documents=top_candidates,
            top_n=1
        )

        if not rerank_results:
            logger.warning("Precision reranker returned no results.")
            return None, "DOMAIN_REFUSAL"

        ## @logic_ Select the highest-scoring candidate
        best = rerank_results[0]
        best_chunk = best["text"]
        logger.info(
            f"Precision reranker selected chunk at original index {best['index']} "
            f"(relevance_score={best['relevance_score']:.4f})"
        )

        return best_chunk, "PASS"
