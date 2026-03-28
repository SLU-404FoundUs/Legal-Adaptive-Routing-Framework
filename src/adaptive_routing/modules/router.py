"""
Saint Louis University : Team 404FoundUs
@file src/adaptive_routing/modules/router.py
@project_ LLM Legal Adaptive Routing Framework
@desc_ Facade/Orchestrator that simplifies usage of the Semantic Router sub-components.
@deps_ src.adaptive_routing.modules.semantic_router.logic_classifier, src.adaptive_routing.modules.semantic_router.legal_generation, logging
"""

import logging
from src.adaptive_routing.modules.semantic_router.logic_classifier import RoutingClassifier
from src.adaptive_routing.modules.semantic_router.legal_generation import LegalGenerator

logger = logging.getLogger(__name__)

class SemanticRouterModule:
    """
    @class_ SemanticRouterModule
    @desc_ Facade that simplifies the semantic_router module into clean, separated operations:
           1. _process_routing_       — Classify the user's intent (Casual / General / Reasoning).
           2. _generate_response_     — Single-turn generation using the classified route.
           3. _generate_conversation_ — Multi-turn generation using the classified route.
    @attr_ _classifier : (RoutingClassifier) Component that determines the route.
    @attr_ _generator  : (LegalGenerator) Component that dispatches to the appropriate LLM engine.
    """

    def __init__(self, api_key=None, classifier=None, generator=None):
        self._classifier = classifier or RoutingClassifier(api_key)
        self._generator = generator or LegalGenerator(api_key)

    ## ── Method 1: Classification ──────────────────────────────────────────

    def _process_routing_(self, normalized_text: str) -> dict:
        """
        @func_ _process_routing_ (@params normalized_text)
        @params normalized_text : (str) Standardized user query from TirageModule.
        @return_ dict : Classification result containing route, confidence, and trigger_signals.
        @logic_
            Delegates to RoutingClassifier._route_query_() and returns the raw
            classification dictionary. Does NOT generate a response.
        """
        return self._classifier._route_query_(normalized_text)

    ## ── Method 2: Single-Turn Generation ──────────────────────────────────

    def _generate_response_(self, classification: dict, normalized_text: str, context: str = None, limits: float = 0.6) -> dict:
        """
        @func_ _generate_response_ (@params classification, normalized_text, context, limits)
        @params classification  : (dict) Output from _process_routing_ containing route and confidence.
        @params normalized_text : (str) The user's normalized query.
        @params context         : (str, optional) RAG-retrieved legal context to augment the query.
        @params limits          : (float) Minimum acceptable confidence level (0.0–1.0). Default: 0.6 (60%).
                                  If the classifier's confidence falls below this threshold, the route
                                  is rejected and a clarification prompt is returned instead.
        @return_ dict : Contains 'classification', 'accepted' (bool), and 'response_text'.
        @logic_
            1. Validates the classification confidence against the developer-defined limits.
            2. If rejected, returns a clarification prompt without calling the LLM.
            3. If accepted, constructs the augmented query (with context if provided) and
               dispatches to the appropriate engine via LegalGenerator._dispatch_().
        """
        route = classification.get("route")
        confidence = classification.get("confidence", 0.0)

        ## @logic_ Reject if classification itself had an error
        if classification.get("error"):
            logger.warning(f"Classification error detected: {classification['error']}")
            return {
                "classification": classification,
                "accepted": False,
                "response_text": "I encountered a technical issue while processing your query. Please try again."
            }

        ## @logic_ Reject if confidence is below the developer-defined threshold
        if confidence < limits:
            logger.info(f"Confidence {confidence:.2f} below threshold {limits:.2f} for route '{route}'. Rejecting.")
            return {
                "classification": classification,
                "accepted": False,
                "response_text": "I'm not confident enough in my understanding of your query. Could you please clarify or provide more details?"
            }

        ## @logic_ Build the query payload
        query = self._build_augmented_query_(normalized_text, context, route)

        ## @logic_ Dispatch to the appropriate LLM engine
        response_text = self._generator._dispatch_(query, route)

        return {
            "classification": classification,
            "accepted": True,
            "response_text": response_text
        }

    ## ── Method 3: Multi-Turn Generation ───────────────────────────────────

    def _generate_conversation_(self, classification: dict, messages: list, context: str = None, limits: float = 0.6) -> dict:
        """
        @func_ _generate_conversation_ (@params classification, messages, context, limits)
        @params classification : (dict) Output from _process_routing_ containing route and confidence.
        @params messages       : (list[dict]) Full conversation history [{role, content}, ...].
        @params context        : (str, optional) RAG-retrieved legal context to inject into the latest user message.
        @params limits         : (float) Minimum acceptable confidence level (0.0–1.0). Default: 0.6 (60%).
        @return_ dict : Contains 'classification', 'accepted' (bool), and 'response_text'.
        @logic_
            1. Validates the classification confidence against the developer-defined limits.
            2. If rejected, returns a clarification prompt without calling the LLM.
            3. If accepted, injects context into the last user message (if provided),
               sets the correct system prompt, and dispatches the full conversation
               history via LegalGenerator._dispatch_conversation_().
        """
        route = classification.get("route")
        confidence = classification.get("confidence", 0.0)

        ## @logic_ Reject if classification itself had an error
        if classification.get("error"):
            logger.warning(f"Classification error detected: {classification['error']}")
            return {
                "classification": classification,
                "accepted": False,
                "response_text": "I encountered a technical issue while processing your query. Please try again."
            }

        ## @logic_ Reject if confidence is below the developer-defined threshold
        if confidence < limits:
            logger.info(f"Confidence {confidence:.2f} below threshold {limits:.2f} for route '{route}'. Rejecting.")
            return {
                "classification": classification,
                "accepted": False,
                "response_text": "I'm not confident enough in my understanding of your query. Could you please clarify or provide more details?"
            }

        ## @logic_ Inject context into the conversation if provided and route is not Casual
        if context and route != "Casual-LLM" and messages:
            last_user_msg = None
            for msg in reversed(messages):
                if msg.get("role") == "user":
                    last_user_msg = msg
                    break
            if last_user_msg:
                last_user_msg["content"] = self._build_augmented_query_(last_user_msg["content"], context, route)

        ## @logic_ Dispatch the full conversation to the appropriate LLM engine
        response_text = self._generator._dispatch_conversation_(messages, route)

        return {
            "classification": classification,
            "accepted": True,
            "response_text": response_text
        }

    ## ── Internal Helper ───────────────────────────────────────────────────

    def _build_augmented_query_(self, normalized_text: str, context: str, route: str) -> str:
        """
        @func_ _build_augmented_query_ (@params normalized_text, context, route)
        @desc_ Constructs the final query string, optionally wrapping RAG context with delimiters.
               Casual routes skip context injection entirely.
        @return_ str : The final query to send to the LLM.
        """
        if not context or route == "Casual-LLM":
            return normalized_text

        return (
            f"{normalized_text}\n\n"
            f"[RETRIEVED CONTEXT — Use if relevant to the query above]\n"
            f"{context}\n"
            f"[END CONTEXT]\n\n"
            f"Use the retrieved context to support your answer with specific legal references where applicable."
        )
