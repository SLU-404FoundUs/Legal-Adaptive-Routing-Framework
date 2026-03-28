"""
Saint Louis University : Team 404FoundUs
@file_ logic_classifier.py
@project_ LLM Legal Adaptive Routing Framework
@desc_ Semantic router for classifying legal queries into Information or Advice pathways using Gemma 4B.
@deps_ src.adaptive_routing.core.engine, src.adaptive_routing.config, json, re, logging
"""

import json
import re
import logging
from src.adaptive_routing.core.engine import LLMRequestEngine
from src.adaptive_routing.config import FrameworkConfig

logger = logging.getLogger(__name__)

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
            "TASK: Analyze the USER QUERY and decide which LLM should handle it.\n"
            "\n"
            "Casual-LLM:\n"
            "- Greetings (hi, hello, good morning, kumusta)\n"
            "- Gratitude (thank you, thanks, salamat po)\n"
            "- Farewells (bye, goodbye, take care, ingat)\n"
            "- Small talk unrelated to law or legal matters\n"
            "- Single-word affirmations (ok, yes, sure, noted, sige)\n"
            "- Emotional check-ins without legal context\n"
            "- Unrelated inquiries towards migrant worker rights and legal assistance\n"
            "\n"
            "General-LLM:\n"
            "- General legal information\n"
            "- Definitions, explanations, rights overview\n"
            "- Simple Q&A about law\n"
            "- Summarize Legal Findings\n"
            "- Perform Simplifications\n"
            "- Clarify complex scenarios\n"
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
            "- When in doubt between Casual and Legal, choose the legal route\n"
            "\n"
            "JSON Schema:\n"
            "{\n"
            '  "route": "Casual-LLM" | "General-LLM" | "Reasoning-LLM",\n'
            '  "confidence": float,\n'
            '  "trigger_signals": [list of short strings]\n'
            "}"
        )

    def _route_query_(self, query: str) -> dict:
        """
        @func_ _route_query_ (@params query)
        @params query : (str) The user's input query (normalized text).
        @return_ dict : The structured routing decision. Contains 'error' key if classification failed.
        @logic_ Calls the LLM and parses the JSON response.
        """
        try:
            raw_response = self._handler._get_completion_(query, self._system_prompt)
            return self._parse_json_(raw_response)
        except Exception as e:
            ## @logic_ Return explicit error indicator instead of a fake route sentinel
            logger.error(f"Routing classification failed: {e}")
            return {
                "route": None,
                "confidence": 0.0,
                "trigger_signals": ["Routing Error", str(e)],
                "error": str(e)
            }

    def _parse_json_(self, text: str) -> dict:
        """
        @func_ _parse_json_ (@params text)
        @params text : (str) Raw LLM output.
        @return_ dict : Parsed JSON object.
        @logic_ Removes markdown code blocks and whitespace before parsing.
        """
        if not isinstance(text, str):
            text = str(text) if text is not None else ""
            
        # Strip markdown code blocks (```json ... ```)
        cleaned_text = re.sub(r"```json\s*", "", text, flags=re.IGNORECASE)
        cleaned_text = re.sub(r"```", "", cleaned_text)
        cleaned_text = cleaned_text.strip()
        
        try:
            return json.loads(cleaned_text)
        except json.JSONDecodeError:
            logger.warning(f"JSON parsing failed for router output: {text[:100]}")
            return {
                "route": None,
                "confidence": 0.0,
                "trigger_signals": ["JSON Parsing Failed", text[:50]],
                "error": "Failed to parse LLM routing output as JSON"
            }
