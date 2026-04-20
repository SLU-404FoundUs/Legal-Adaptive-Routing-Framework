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
            include_reasoning=FrameworkConfig._ROUTER_REASONING
        )

        self._system_prompt = system_prompt or FrameworkConfig._ROUTER_INSTRUCTIONS

    def _route_query_(self, query: str) -> dict:
        """
        @func_ _route_query_
        @params query : (str) The user's input query.
        @returns (dict) The structured routing decision.
        @desc_ Calls the LLM and parses the JSON response.
        """
        ## @logic_ Snapshot current config for diagnostics
        _cfg = (
            f"[Router Config] model={FrameworkConfig._ROUTER_MODEL}, "
            f"USE_SYSTEM={FrameworkConfig._ROUTER_USE_SYSTEM}, "
            f"REASONING={FrameworkConfig._ROUTER_REASONING}"
        )

        try:
            raw_response = self._handler._get_completion_(query, self._system_prompt)

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

            return self._parse_json_(raw_response)
        except Exception as e:
            error_msg = f"Routing classification failed: {e}. {_cfg}"
            logger.error(error_msg)
            return {
                "route": None,
                "confidence": 0.0,
                "search_signals": ["Routing Error", str(e)],
                "error": error_msg
            }

    def _parse_json_(self, text: str) -> dict:
        """
        @func_ _parse_json_
        @params text : (str) Raw LLM output.
        @returns (dict) Parsed JSON object.
        @desc_ Removes markdown code blocks and whitespace before parsing.
        """
        if not isinstance(text, str):
            text = str(text) if text is not None else ""
            
        ## @logic_ Strip markdown code blocks (```json ... ```)
        cleaned_text = re.sub(r"```json\s*", "", text, flags=re.IGNORECASE)
        cleaned_text = re.sub(r"```", "", cleaned_text)
        cleaned_text = cleaned_text.strip()
        
        try:
            return json.loads(cleaned_text)
        except json.JSONDecodeError:
            preview = repr(text[:200]) if text else "(empty)"
            error_msg = f"Failed to parse router output as JSON. Raw output: {preview}"
            logger.warning(error_msg)
            return {
                "route": None,
                "confidence": 0.0,
                "search_signals": ["JSON Parsing Failed"],
                "error": error_msg
            }
