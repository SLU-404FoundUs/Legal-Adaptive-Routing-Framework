## Saint Louis University
## Team 404FoundUs
## @file src/adaptive_routing/modules/router.py
## @project_ LLM Legal Adaptive Routing Framework
## @desc_ Facade/Orchestrator that simplifies usage of the Semantic Router sub-components.
## @deps src.adaptive_routing.modules.semantic_router.logic_classifier, src.adaptive_routing.modules.semantic_router.legal_generation, logging

import logging
import time
from src.adaptive_routing.modules.semantic_router.logic_classifier import RoutingClassifier
from src.adaptive_routing.modules.semantic_router.legal_generation import LegalGenerator

logger = logging.getLogger(__name__)

class SemanticRouterModule:
    """
    @class SemanticRouterModule
    @desc_ Facade that simplifies the semantic_router module into clean operations.
    @attr_ _classifier : (RoutingClassifier) Component that determines the route.
    @attr_ _generator : (LegalGenerator) Component that dispatches to the appropriate LLM engine.
    """
    def __init__(self, api_key=None, classifier=None, generator=None):
        self._classifier = classifier or RoutingClassifier(api_key)
        self._generator = generator or LegalGenerator(api_key)

    def _process_routing_(self, normalized_text: str, history: list = None, threshold: float = None, persistence_level: int = 3, system_instructions: str = None) -> dict:
        """
        @func_ _process_routing_
        @params normalized_text : (str) Standardized user query.
        @params history : (list, optional) Previous conversation turns.
        @params threshold : (float, optional) Confidence threshold (0.0 to 1.0).
        @params persistence_level : (int) Number of attempts to reach acceptable threshold.
        @params system_instructions : (str, optional) Override for routing instructions.
        @returns (dict) Classification result containing route, confidence, and signals.
        @desc_ Delegates to RoutingClassifier._route_query_() with optional retry logic and history context.
        """
        if threshold is None:
            return self._classifier._route_query_(normalized_text, history=history, system_instructions=system_instructions)
            
        ## @iter_ persistence_level : Retrying classification if confidence is low
        for attempt in range(persistence_level):
            classification = self._classifier._route_query_(normalized_text, history=history, system_instructions=system_instructions)
            confidence = classification.get("confidence", 0.0)
            
            if confidence >= threshold:
                return classification

            logger.info(f"Persistence attempt {attempt + 1}/{persistence_level}: Confidence {confidence:.2f} below threshold {threshold}.")
            
            if attempt < persistence_level - 1:
                time.sleep(1)
            
        return {
            "error": "LLMEngine failed to acknowledge the input.",
            "route": None,
            "confidence": 0.0
        }

    def _generate_response_(self, classification: dict, normalized_text: str, context: str = None, is_follow_up: bool = False, detected_language: str = "Unknown") -> dict:
        """
        @func_ _generate_response_
        @params classification : (dict) Output from _process_routing_.
        @params normalized_text : (str) The user's normalized query.
        @params context : (str, optional) RAG-retrieved legal context.
        @params is_follow_up : (bool) Whether this is a follow-up query.
        @params detected_language : (str) Origin language detected by triage.
        @returns (dict) Contains 'classification', 'accepted', and 'response_text'.
        @desc_ Single-turn generation using the classified route.
        """
        route = classification.get("route")

        ## @logic_ Reject if classification itself had an error
        if classification.get("error"):
            logger.warning(f"Classification error detected: {classification['error']}")
            response_msg = classification["error"] if classification["error"] == "LLMEngine failed to acknowledge the input." else "I encountered a technical issue while processing your query."
            return {
                "classification": classification,
                "accepted": False,
                "response_text": response_msg
            }

        ## @logic_ Build the query payload and dispatch
        query = self._build_augmented_query_(normalized_text, context, route, is_follow_up=is_follow_up)
        response_text = self._generator._dispatch_(query, route, detected_language=detected_language)

        return {
            "classification": classification,
            "accepted": True,
            "response_text": response_text
        }

    def _generate_conversation_(self, classification: dict, messages: list, context: str = None, is_follow_up: bool = False, detected_language: str = "Unknown") -> dict:
        """
        @func_ _generate_conversation_
        @params classification : (dict) Output from _process_routing_.
        @params messages : (list[dict]) Full conversation history.
        @params context : (str, optional) RAG-retrieved legal context.
        @params is_follow_up : (bool) Whether this is a follow-up query.
        @params detected_language : (str) Origin language detected by triage.
        @returns (dict) Contains 'classification', 'accepted', and 'response_text'.
        @desc_ Multi-turn generation using the classified route and history.
        """
        route = classification.get("route")

        ## @logic_ Reject if classification itself had an error
        if classification.get("error"):
            logger.warning(f"Classification error detected: {classification['error']}")
            response_msg = classification["error"] if classification["error"] == "LLMEngine failed to acknowledge the input." else "I encountered a technical issue while processing your query."
            return {
                "classification": classification,
                "accepted": False,
                "response_text": response_msg
            }

        ## @logic_ Inject context into the conversation if provided and route is not Casual
        if context and route != "Casual-LLM" and messages:
            last_user_msg = None
            ## @iter_ reversed(messages) : Finding the last user message to inject context
            for msg in reversed(messages):
                if msg.get("role") == "user":
                    last_user_msg = msg
                    break
            if last_user_msg:
                last_user_msg["content"] = self._build_augmented_query_(last_user_msg["content"], context, route, is_follow_up=is_follow_up)

        response_text = self._generator._dispatch_conversation_(messages, route, detected_language=detected_language)

        return {
            "classification": classification,
            "accepted": True,
            "response_text": response_text
        }

    def _build_augmented_query_(self, normalized_text: str, context: str, route: str, is_follow_up: bool = False) -> str:
        """
        @func_ _build_augmented_query_
        @params normalized_text : (str) Raw normalized text.
        @params context : (str) RAG context.
        @params route : (str) Target LLM route.
        @params is_follow_up : (bool) Follow-up flag.
        @returns (str) The final query to send to the LLM.
        @desc_ Constructs the final query string with context delimiters.
        """
        if not context or route == "Casual-LLM":
            return normalized_text

        follow_up_hint = "\n[SYSTEM: This is a follow-up query. Use the provided legal context.]" if is_follow_up else ""

        return (
            f"{normalized_text}{follow_up_hint}\n\n"
            f"[MANDATORY LEGAL CONTEXT — Ground your response in the following provision]\n"
            f"{context}\n"
            f"[END CONTEXT]\n\n"
            f"CONSTRAINT: Base your response on the context above. If the context does not "
            f"contain sufficient information to answer the query, state that explicitly rather "
            f"than generating information from other sources."
        )
