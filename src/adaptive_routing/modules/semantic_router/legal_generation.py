"""
Saint Louis University : Team 404FoundUs
@file_ legal_generation.py
@project_ LLM Legal Adaptive Routing Framework
@desc_ Generates legal responses using the specific LLM (General vs. Reasoning) based on classification.
@deps_ src.adaptive_routing.core.engine, src.adaptive_routing.config
"""

from src.adaptive_routing.core.engine import LLMRequestEngine
from src.adaptive_routing.config import FrameworkConfig

class LegalGenerator:
    """
    @class_ LegalGenerator
    @desc_ Handles the generation of legal content by dispatching to the specific LLM.
    """

    def __init__(self, api_key=None, general_engine=None, reasoning_engine=None):
        self._api_key = api_key
        # Initialize engines lazily or upfront? Upfront is finer for now since we have distinct configs.
        
        self._general_engine = general_engine or LLMRequestEngine(
            api_key=api_key,
            model=FrameworkConfig._GENERAL_MODEL,
            temperature=FrameworkConfig._GENERAL_TEMP,
            max_tokens=FrameworkConfig._GENERAL_MAX_TOKENS,
            use_system_role=FrameworkConfig._GENERAL_USE_SYSTEM,
            include_reasoning=FrameworkConfig._GENERAL_REASONING
        )

        self._reasoning_engine = reasoning_engine or LLMRequestEngine(
            api_key=api_key,
            model=FrameworkConfig._REASONING_MODEL,
            temperature=FrameworkConfig._REASONING_TEMP,
            max_tokens=FrameworkConfig._REASONING_MAX_TOKENS,
            use_system_role=FrameworkConfig._REASONING_USE_SYSTEM,
            include_reasoning=FrameworkConfig._REASONING_REASONING
        )

    def _dispatch_(self, query: str, route: str) -> str:
        """
        @func_ _dispatch_ (@params query, route)
        @params query : (str) The user query.
        @params route : (str) "General-LLM" or "Reasoning-LLM".
        @return_ str : The LLM response.
        """
        if route == "Reasoning-LLM":
            system_prompt = FrameworkConfig._REASONING_INSTRUCTIONS
            return self._reasoning_engine._get_completion_(query, system_prompt)
        else:
            ## @logic_ Default to General for "General-LLM" or fallback
            system_prompt = FrameworkConfig._GENERAL_INSTRUCTIONS
            return self._general_engine._get_completion_(query, system_prompt)
