## Saint Louis University
## Team 404FoundUs
## @file src/adaptive_routing/modules/semantic_router/logic_classifier.py
## @project_ LLM Legal Adaptive Routing Framework
## @desc_ Semantic router for classifying legal queries into Information or Advice pathways.
## @deps src.adaptive_routing.core.engine, src.adaptive_routing.config, json, re, logging

import json
import re
import logging
from src.adaptive_routing.core.engine import LLMRequestEngine
from src.adaptive_routing.config import FrameworkConfig
from src.adaptive_routing.modules.semantic_router.utils.parser import parse_router_json

logger = logging.getLogger(__name__)

class RoutingClassifier:
    """
    @class RoutingClassifier
    @desc_ Analyzes user queries to route them to Casual, General/Info, or Advice/Scenario.
    @attr_ _handler : (LLMRequestEngine) Interaction engine for AI requests.
    @attr_ _system_prompt : (str) The instruction set for the routing reasoning.
    """
    def __init__(self, api_key=None, handler=None, system_prompt=None):
        self._handler = handler or LLMRequestEngine(
            api_key=api_key,
            model=FrameworkConfig._ROUTER_MODEL,
            temperature=FrameworkConfig._ROUTER_TEMP,
            max_tokens=FrameworkConfig._ROUTER_MAX_TOKENS, 
            use_system_role=FrameworkConfig._ROUTER_USE_SYSTEM,
            include_reasoning=FrameworkConfig._ROUTER_REASONING,
            reasoning_effort=FrameworkConfig._ROUTER_REASONING_EFFORT
        )

        self._system_prompt = system_prompt or FrameworkConfig._ROUTER_INSTRUCTIONS

    def _route_query_(self, query: str, history: list = None, system_instructions: str = None) -> dict:
        """
        @func_ _route_query_
        @params query : (str) The user's input query.
        @params history : (list, optional) Previous conversation turns.
        @params system_instructions : (str, optional) Override for routing instructions.
        @returns (dict) The structured routing decision.
        @desc_ Calls the LLM and parses the JSON response, optionally with history.
        """
        ## @logic_ Instruction precedence: Override > Instance > Default
        instructions = system_instructions or self._system_prompt

        ## @logic_ Snapshot current config for diagnostics
        _cfg = (
            f"[Router Config] model={FrameworkConfig._ROUTER_MODEL}, "
            f"USE_SYSTEM={FrameworkConfig._ROUTER_USE_SYSTEM}, "
            f"REASONING={FrameworkConfig._ROUTER_REASONING}"
        )

        try:
            if history:
                ## @logic_ Combine history into a single prompt to prevent persona drift
                history_text = "[CONVERSATION HISTORY]\n"
                for msg in history:
                    role_str = "USER" if msg.get("role") == "user" else "ASSISTANT"
                    history_text += f"{role_str}: {msg.get('content', '')}\n"
                
                combined_query = f"{history_text}\n[CURRENT QUERY]\n{query}"
                raw_response = self._handler._get_completion_(combined_query, instructions)
            else:
                ## @logic_ Single-turn fallback
                raw_response = self._handler._get_completion_(query, instructions)

            ## @logic_ Guard: Detect empty/null responses
            if not raw_response or not str(raw_response).strip():
                error_msg = f"Router LLM returned an empty response. {_cfg}"
                logger.error(error_msg)
                return {
                    "route": None,
                    "confidence": 0.0,
                    "search_signals": ["Empty LLM Response"],
                    "error": error_msg
                }

            ## @logic_ Delegate parsing to utility (handles <think> tags)
            return parse_router_json(raw_response)
        except Exception as e:
            error_msg = f"Routing classification failed: {e}. {_cfg}"
            logger.error(error_msg)
            return {
                "route": None,
                "confidence": 0.0,
                "search_signals": ["Routing Error", str(e)],
                "error": error_msg
            }
