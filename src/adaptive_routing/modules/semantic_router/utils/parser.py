## Saint Louis University
## Team 404FoundUs
## @file src/adaptive_routing/modules/semantic_router/utils/parser.py
## @desc_ Utility functions for parsing structured LLM responses in the Router module.

import json
import re
import logging

logger = logging.getLogger(__name__)

def parse_router_json(text: str) -> dict:
    """
    @func parse_router_json
    @params text : (str) Raw LLM output.
    @returns (dict) Parsed JSON routing decision.
    @desc_ Strips reasoning blocks and markdown before parsing JSON.
    """
    if not text:
        return {"error": "Empty input"}

    ## @logic_ Remove <think>...</think> blocks first to avoid JSON interference
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()

    ## @logic_ Strip markdown code blocks (```json ... ```)
    cleaned_text = re.sub(r"```json\s*", "", text, flags=re.IGNORECASE)
    cleaned_text = re.sub(r"```", "", cleaned_text)
    cleaned_text = cleaned_text.strip()
    
    try:
        return json.loads(cleaned_text)
    except json.JSONDecodeError:
        ## @logic_ Fallback to regex extraction if JSON is truncated or malformed
        logger.warning("JSON parsing failed. Attempting strict regex fallback extraction...")
        
        fallback_result = {
            "route": None,
            "confidence": 0.0,
            "search_signals": None
        }
        
        route_match = re.search(r'"route"\s*:\s*"([^"]+)"', cleaned_text)
        if route_match:
            fallback_result["route"] = route_match.group(1)
            
        conf_match = re.search(r'"confidence"\s*:\s*([\d\.]+)', cleaned_text)
        if conf_match:
            try:
                fallback_result["confidence"] = float(conf_match.group(1))
            except ValueError:
                pass
                
        if fallback_result["route"]:
            logger.info(f"Regex fallback successful: extracted route='{fallback_result['route']}'")
            return fallback_result

        preview = repr(text[:200]) if text else "(empty)"
        logger.error(f"Failed to parse router output as JSON and regex fallback failed. Raw output: {preview}")
        return {
            "route": None,
            "confidence": 0.0,
            "search_signals": ["JSON Parsing Failed"],
            "error": "Failed to parse structured response"
        }
