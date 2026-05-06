## Saint Louis University
## Team 404FoundUs
## @file src/adaptive_routing/core/reranker.py
## @project_ LLM Legal Adaptive Routing Framework
## @desc_ API client for OpenRouter /api/v1/rerank endpoint with retry logic.
## @deps requests, json, time, logging, src.adaptive_routing.config, src.adaptive_routing.core.exceptions

import requests
import json
import time
import logging
from src.adaptive_routing.config import FrameworkConfig
from src.adaptive_routing.core.exceptions import (
    AuthenticationError,
    APIConnectionError,
    APIResponseError,
    InvalidInputError
)

logger = logging.getLogger(__name__)

class RerankEngine:
    """
    @class RerankEngine
    @desc_ Provides a unified interface for OpenRouter /api/v1/rerank calls.
           Mirrors the LLMRequestEngine pattern but targets the rerank endpoint.
    @attr_ _api_key : (str) Credential for the OpenRouter API.
    @attr_ _model : (str) The reranker model identifier (e.g., 'cohere/rerank-4-pro').
    """
    def __init__(self, api_key=None, model=None):
        self._url = "https://openrouter.ai/api/v1/rerank"
        
        ## @logic_ API Key Validation from argument or config
        self._api_key = api_key or FrameworkConfig._API_KEY
        if not self._api_key:
            raise AuthenticationError(
                "API Key is missing. Please provide it in init or set OPENROUTER_API_KEY environment variable."
            )

        ## @logic_ Model Validation
        self._model = model or FrameworkConfig._RETRIEVAL_RERANK_MODEL
        if not self._model or not isinstance(self._model, str):
            raise InvalidInputError(f"Invalid rerank model specified: {self._model}")

    def _build_headers_(self):
        """
        @func_ _build_headers_
        @returns (dict) HTTP headers for OpenRouter API requests.
        @desc_ Centralized header construction matching LLMRequestEngine pattern.
        """
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/404FoundUs",
            "X-Title": "LLM Legal Adaptive Routing Framework"
        }

    def _call_rerank_api_(self, payload, timeout=None):
        """
        @func_ _call_rerank_api_
        @params payload : (dict) The JSON request payload.
        @params timeout : (int) Request timeout in seconds.
        @returns (dict) Parsed JSON response from the API.
        @desc_ Executes a rerank API call with retry logic and unified error handling.
        """
        headers = self._build_headers_()
        timeout = timeout or FrameworkConfig._REQUEST_TIMEOUT
        retries = FrameworkConfig._RETRY_COUNT
        backoff = FrameworkConfig._RETRY_BACKOFF

        last_error = None
        ## @iter_ range : Retrying the API call based on backoff logic
        for attempt in range(1 + retries):
            try:
                response = requests.post(self._url, headers=headers, json=payload, timeout=timeout)
                response.raise_for_status()
                return response.json()
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                last_error = e
                if attempt < retries:
                    wait_time = backoff * (2 ** attempt)
                    logger.warning(
                        f"Rerank API attempt {attempt + 1} failed ({type(e).__name__}). "
                        f"Retrying in {wait_time:.1f}s..."
                    )
                    time.sleep(wait_time)
                    continue
                self._handle_error_(e, context="Rerank")
            except (requests.exceptions.HTTPError, requests.exceptions.RequestException, json.JSONDecodeError) as e:
                ## @logic_ Non-retryable errors — fail immediately
                self._handle_error_(e, context="Rerank")

        if last_error:
            self._handle_error_(last_error, context="Rerank")

    def _handle_error_(self, error, context="Rerank API request"):
        """
        @func_ _handle_error_
        @params error : (Exception) The caught exception.
        @params context : (str) Description of the operation for error messages.
        @desc_ Maps HTTP status codes to framework exceptions, mirroring LLMRequestEngine.
        """
        if isinstance(error, requests.exceptions.HTTPError):
            status_code = error.response.status_code
            detail = error.response.text
            if status_code == 401:
                raise AuthenticationError(
                    f"Invalid API Key provided. Details: {detail}"
                ) from error
            elif status_code == 402:
                raise APIResponseError(
                    f"Insufficient credits for reranking. Details: {detail}",
                    status_code=402
                ) from error
            else:
                raise APIResponseError(
                    f"HTTP Error {status_code}: {detail}",
                    status_code=status_code,
                    response_body=detail
                ) from error

        elif isinstance(error, requests.exceptions.ConnectionError):
            raise APIConnectionError(
                f"{context} failed: Could not connect to OpenRouter API. "
                f"Check your internet connection. Details: {str(error)}"
            ) from error

        elif isinstance(error, requests.exceptions.Timeout):
            raise APIConnectionError(
                f"{context} timed out after {FrameworkConfig._REQUEST_TIMEOUT} seconds. "
                f"Details: {str(error)}"
            ) from error

        elif isinstance(error, requests.exceptions.RequestException):
            raise APIConnectionError(
                f"{context} failed unexpectedly: {str(error)}"
            ) from error

        elif isinstance(error, json.JSONDecodeError):
            raise APIResponseError(
                f"Failed to decode rerank API response JSON. Details: {str(error)}"
            ) from error

    def _rerank_(self, query, documents, top_n=None):
        """
        @func_ _rerank_
        @params query : (str) The search query to rerank documents against.
        @params documents : (list[str]) Document texts to rerank.
        @params top_n : (int, optional) Number of most relevant documents to return.
        @returns (list[dict]) Sorted results, each containing 'index', 'relevance_score', 'text'.
        @desc_ Calls the OpenRouter /api/v1/rerank endpoint and parses the response.
        """
        if not documents:
            raise InvalidInputError("Cannot rerank an empty document list.")

        payload = {
            "model": self._model,
            "query": query,
            "documents": documents,
        }
        if top_n is not None:
            payload["top_n"] = top_n

        response_json = self._call_rerank_api_(payload)

        ## @logic_ Parse rerank response into standardized format
        if "results" not in response_json or len(response_json["results"]) == 0:
            logger.warning("Rerank API returned empty results.")
            return []

        parsed_results = []
        for item in response_json["results"]:
            parsed_results.append({
                "index": item.get("index", 0),
                "relevance_score": float(item.get("relevance_score", 0.0)),
                "text": item.get("document", {}).get("text", "")
            })

        ## @logic_ Sort by relevance_score descending (API may already do this)
        parsed_results.sort(key=lambda x: x["relevance_score"], reverse=True)
        return parsed_results
