"""
Saint Louis University : Team 404FoundUs
@file src/adaptive_routing/modules/router.py
@project_ LLM Legal Adaptive Routing Framework
@desc_ Orchestrator module that coordinates Logic Classification and Legal Generation.
@deps_ src.adaptive_routing.modules.semantic_router.logic_classifier, src.adaptive_routing.modules.semantic_router.legal_generation
"""

from src.adaptive_routing.modules.semantic_router.logic_classifier import RoutingClassifier
from src.adaptive_routing.modules.semantic_router.legal_generation import LegalGenerator

class SemanticRouterModule:
    """
    @class_ SemanticRouterModule
    @desc_ Facade/Orchestrator that manages the pipeline: Classify -> Route -> Generate.
    @attr_ _classifier : (RoutingClassifier) Component to decide the route.
    @attr_ _generator : (LegalGenerator) Component to execute the LLM call.
    """

    def __init__(self, api_key=None, classifier=None, generator=None):
        self._classifier = classifier or RoutingClassifier(api_key)
        self._generator = generator or LegalGenerator(api_key)

    def _process_routing_(self, normalized_text: str) -> dict:
        """
        @func_ _process_routing_ (@params normalized_text)
        @params normalized_text : (str) Standardized user query.
        @return_ dict : Contains routing metadata and the final LLM response.
        @logic_ 
            1. Calls classifier to get route (General vs Reasoning).
            2. If route is valid, calls generator.
            3. Returns combined result.
        """
        ## @logic_ Classify
        classification = self._classifier._route_query_(normalized_text)
        route = classification.get('route')
        
        response_text = None
        
        ## @logic_ Generate if valid
        if route and route != "PATHWAY_2":
             response_text = self._generator._dispatch_(normalized_text, route)
        else:
             response_text = "Routing failed or ambiguous (PATHWAY_2). Manual review recommended."

        ## @logic_ Combine results
        return {
            "classification": classification,
            "response_text": response_text
        }
