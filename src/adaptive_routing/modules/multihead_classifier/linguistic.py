## Saint Louis University
## Team 404FoundUs
## @file src/adaptive_routing/modules/multihead_classifier/linguistic.py
## @project_ LLM Legal Adaptive Routing Framework
## @desc_ Component for converting multilingual legal queries into standardized English.
## @deps src.adaptive_routing.core.engine, src.adaptive_routing.config

from src.adaptive_routing.core.engine import LLMRequestEngine
from src.adaptive_routing.config import FrameworkConfig

class LinguisticNormalizer:
    """
    @class LinguisticNormalizer
    @desc_ Handles the conversion of Tagalog, Taglish, Cantonese, and Chinese inputs 
           into formal English legal terminology using an LLM.
    @attr_ _engine : (LLMRequestEngine) The engine used for normalization completions.
    """
    def __init__(self, engine: LLMRequestEngine):
        self._engine = engine

    def _normalize_text_(self, input_text: str, image_path: str = None, system_instructions: str = None) -> str:
        """
        @func_ _normalize_text_
        @params input_text : (str) The raw user query.
        @params image_path : (str, optional) Path to a supporting image.
        @params system_instructions : (str, optional) Override system instructions for this request.
        @returns (str) The LLM's normalized English response.
        @desc_ Sends the input to the LLM with normalization instructions.
        """
        instructions = system_instructions if system_instructions is not None else FrameworkConfig._TRIAGE_INSTRUCTIONS
        images = [image_path] if image_path else None
        
        return self._engine._get_completion_(
            prompt=input_text,
            sys_message=instructions,
            images=images
        )