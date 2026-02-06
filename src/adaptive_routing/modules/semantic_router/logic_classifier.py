"""
Saint Louis University : Team 404FoundUs
@file_ logic_classifier.py
@project_ LLM Legal Adaptive Routing Framework
@desc_ Semantic router for classifying legal queries into Information or Advice pathways using Gemma 4B.
@deps_ src.adaptive_routing.core.engine, src.adaptive_routing.config, json, re
"""

import json
import re
from src.adaptive_routing.core.engine import LLMRequestEngine
from src.adaptive_routing.config import FrameworkConfig

class RoutingClassifier:
    """
    @class_ RoutingClassifier
    @desc_ Analyzes user queries to route them to either General/Info (General-LLM) or Advice/Scenario (Reasoning-LLM).
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

        self._system_prompt = system_prompt or (
            "ROLE: Legal Query Router\n"
            "TASK: Analyze the USER QUERY and decide between two LLMs.\n"
            "\n"
            "General-LLM:\n"
            "- General legal information\n"
            "- Definitions, explanations, rights overview\n"
            "- Simple Q&A\n"
            "- No personalized advice\n"
            "- No complex scenario or dispute\n"
            "\n"
            "Reasoning-LLM:\n"
            "- Describes a real or hypothetical situation\n"
            "- Asks what action to take\n"
            "- Involves disputes, violations, contracts, termination, abuse, or legal risk\n"
            "- Requires legal interpretation and structured reasoning\n"
            "\n"
            "Constraints:\n"
            "- Strictly adhere to the ROLE and TASK above\n"
            "- The router must return structured JSON only\n"
            "- No markdown allowed in output\n"
            "- Do NOT answer the question\n"
            "\n"
            "JSON Schema:\n"
            "{\n"
            '  "route": "General-LLM" | "Reasoning-LLM",\n'
            '  "confidence": float,\n'
            '  "trigger_signals": [list of short strings]\n'
            "}"
        )

    def _route_query_(self, query: str) -> dict:
        """
        @func_ _route_query_ (@params query)
        @params query : (str) The user's input query (normalized text).
        @return_ dict : The structured routing decision.
        @logic_ Calls the LLM and parses the JSON response.
        """
        try:
            raw_response = self._handler._get_completion_(query, self._system_prompt)
            return self._parse_json_(raw_response)
        except Exception as e:
            # Fail-safe: Assume PATHWAY_2 (Human/Complex) if routing fails
            return {
                "route": "PATHWAY_2",
                "confidence": 0.0,
                "trigger_signals": ["Routing Error", str(e)]
            }

    def _parse_json_(self, text: str) -> dict:
        """
        @func_ _parse_json_ (@params text)
        @params text : (str) Raw LLM output.
        @return_ dict : Parsed JSON object.
        @logic_ Removes markdown code blocks and whitespace before parsing.
        """
        # Strip markdown code blocks (```json ... ```)
        cleaned_text = re.sub(r"```json\s*", "", text, flags=re.IGNORECASE)
        cleaned_text = re.sub(r"```", "", cleaned_text)
        cleaned_text = cleaned_text.strip()
        
        try:
            return json.loads(cleaned_text)
        except json.JSONDecodeError:
            return {
                "route": "PATHWAY_2",
                "confidence": 0.0,
                "trigger_signals": ["JSON Parsing Failed", text[:50]]
            }
