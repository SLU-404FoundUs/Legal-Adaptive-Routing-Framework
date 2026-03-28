"""
Saint Louis University : Team 404FoundUs
@file_ legal_generation.py
@project_ LLM Legal Adaptive Routing Framework
@desc_ Generates responses using the specific LLM (Casual vs. General vs. Reasoning) based on classification.
@deps_ src.adaptive_routing.core.engine, src.adaptive_routing.config
"""

from src.adaptive_routing.core.engine import LLMRequestEngine
from src.adaptive_routing.config import FrameworkConfig

class LegalGenerator:
    """
    @class_ LegalGenerator
    @desc_ Handles response generation by dispatching to the appropriate LLM engine based on route.
    """

    def __init__(self, api_key=None, general_engine=None, reasoning_engine=None, casual_engine=None):
        self._api_key = api_key
        
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

        self._casual_engine = casual_engine or LLMRequestEngine(
            api_key=api_key,
            model=FrameworkConfig._CASUAL_MODEL,
            temperature=FrameworkConfig._CASUAL_TEMP,
            max_tokens=FrameworkConfig._CASUAL_MAX_TOKENS,
            use_system_role=FrameworkConfig._CASUAL_USE_SYSTEM,
            include_reasoning=FrameworkConfig._CASUAL_REASONING
        )

    def _dispatch_(self, query: str, route: str) -> str:
        """
        @func_ _dispatch_ (@params query, route)
        @params query : (str) The user query.
        @params route : (str) "Casual-LLM", "General-LLM", or "Reasoning-LLM".
        @return_ str : The LLM response.
        """
        if route == "Casual-LLM":
            system_prompt = FrameworkConfig._CASUAL_INSTRUCTIONS
            return self._casual_engine._get_completion_(query, system_prompt)
        elif route == "Reasoning-LLM":
            system_prompt = FrameworkConfig._REASONING_INSTRUCTIONS
            return self._reasoning_engine._get_completion_(query, system_prompt)
        else:
            ## @logic_ Default to General for "General-LLM" or fallback
            system_prompt = FrameworkConfig._GENERAL_INSTRUCTIONS
            return self._general_engine._get_completion_(query, system_prompt)

    def _dispatch_conversation_(self, messages: list, route: str) -> str:
        """
        @func_ _dispatch_conversation_ (@params messages, route)
        @params messages : (list[dict]) Full conversation history.
        @params route : (str) "Casual-LLM", "General-LLM", or "Reasoning-LLM".
        @return_ str : The LLM response.
        """
        if route == "Casual-LLM":
            return self._casual_engine._get_chat_completion_(messages)
        elif route == "Reasoning-LLM":
            return self._reasoning_engine._get_chat_completion_(messages)
        else:
            return self._general_engine._get_chat_completion_(messages)
