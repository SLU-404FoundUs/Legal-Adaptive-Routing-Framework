## Saint Louis University
## Team 404FoundUs
## @file src/adaptive_routing/modules/triage.py
## @project_ LLM Legal Adaptive Routing Framework
## @desc_ Facade module that orchestrates Linguistic Normalization and Language Detection.
## @deps src.adaptive_routing.modules.multihead_classifier.linguistic, src.adaptive_routing.core.engine, logging

from src.adaptive_routing.modules.multihead_classifier.linguistic import LinguisticNormalizer
from src.adaptive_routing.modules.multihead_classifier.utils.cleaner import strip_llm_artifacts
from src.adaptive_routing.core.engine import LLMRequestEngine
from src.adaptive_routing.config import FrameworkConfig
import re
import logging

logger = logging.getLogger(__name__)

class TriageModule:
    """
    @class TriageModule
    @desc_ Acts as the main entry point for linguistic processing. Coordinates the Normalizer 
           and returns a stateless result dict.
    @attr_ _normalizer : (LinguisticNormalizer) The component responsible for text standardization.
    """
    def __init__(self, api_key=None, engine=None, normalizer=None):
        ## @logic_ Initialize engine with Triage-specific configuration if not provided
        self._engine = engine or LLMRequestEngine(
            api_key=api_key,
            model=FrameworkConfig._TRIAGE_MODEL,
            temperature=FrameworkConfig._TRIAGE_TEMP,
            max_tokens=FrameworkConfig._TRIAGE_MAX_TOKENS,
            use_system_role=FrameworkConfig._TRIAGE_USE_SYSTEM,
            include_reasoning=FrameworkConfig._TRIAGE_REASONING,
            reasoning_effort=FrameworkConfig._TRIAGE_REASONING_EFFORT
        )
        self._normalizer = normalizer or LinguisticNormalizer(self._engine)

    def _process_request_(self, input_text: str, image_path: str = None, system_instructions: str = None):
        """
        @func_ _process_request_
        @params input_text : (str) Raw user input.
        @params image_path : (str) Optional path to image.
        @params system_instructions : (str) Optional override for system instructions.
        @returns (dict) State dictionary with normalized text and language.
        @desc_ Orchestrates the normalization call, parses the combined output,
               and returns a result dict directly.
        """
        raw_output = self._normalizer._normalize_text_(input_text, image_path, system_instructions=system_instructions)
        
        ## @logic_ Strip common LLM artifacts (like <think> tags) using utility
        cleaned_output = strip_llm_artifacts(raw_output)
        
        normalized_text = cleaned_output
        detected_language = "Unknown"

        ## @logic_ Robust regex to find the language tag even if trailing characters exist
        ## Look for the tag anywhere near the end, capturing the content inside brackets
        match = re.search(r"<Detected Raw Language:\s*([^>]+)>", cleaned_output, re.IGNORECASE)
        if match:
            detected_language = match.group(1).strip()
            # Clean up normalized text by removing the tag and everything after it
            normalized_text = cleaned_output[:match.start()].strip()
        else:
            ## @logic_ Fallback: try alternate tag formats [Detected Language: ...]
            alt_match = re.search(r"\[Detected (?:Raw )?Language:\s*([^\]]+)\]", cleaned_output, re.IGNORECASE)
            if alt_match:
                detected_language = alt_match.group(1).strip()
                normalized_text = cleaned_output[:alt_match.start()].strip()
            else:
                logger.warning(f"Language tag not found in normalizer output. First 100 chars: {cleaned_output[:100]}")

        return {
            "original_prompt": input_text,
            "detected_language": detected_language,
            "normalized_text": normalized_text,
            "raw_output": raw_output
        }
