## Saint Louis University
## Team 404FoundUs
## @file src/adaptive_routing/modules/triage.py
## @project_ LLM Legal Adaptive Routing Framework
## @desc_ Facade module that orchestrates Linguistic Normalization and Language Detection.
## @deps src.adaptive_routing.modules.linguistic, src.adaptive_routing.modules.detector, src.adaptive_routing.core.engine

from src.adaptive_routing.modules.linguistic import LinguisticNormalizer
from src.adaptive_routing.modules.detector import LanguageStateDetector
from src.adaptive_routing.core.engine import LLMRequestEngine
import re

class TriageModule:
    """
    @class TriageModule
    @desc_ Acts as the main entry point for linguistic processing. Coordinates the Normalizer and Detector.
    @attr_ _normalizer : (LinguisticNormalizer) The component responsible for text standardization.
    @attr_ _detector : (LanguageStateDetector) The component responsible for state management.
    """
    def __init__(self, api_key=None):
        self._engine = LLMRequestEngine(api_key=api_key)
        self._normalizer = LinguisticNormalizer(self._engine)
        self._detector = LanguageStateDetector()

    def _process_request_(self, input_text: str, image_path: str = None):
        """
        @func_ _process_request_
        @params input_text: (str) Raw user input.
        @params image_path: (str) Optional path to image.
        @return_ dict: State dictionary with normalized text and language.
        @desc_ Orchestrates the normalization call, parses the combined output, and updates the detector state.
        """
        # 1. Get combined output from Normalizer (efficiency: 1 API call)
        raw_output = self._normalizer._normalize_text_(input_text, image_path)

        # 2. Parse the output to separate text and language
        # Expecting format: "... normalized text ... <Detected Raw Language: [Lang]>"
        normalized_text = raw_output
        detected_language = "Unknown"

        ## @logic_ Regex to find the language tag at the end of the string
        match = re.search(r"<Detected Raw Language:\s*(.+?)>$", raw_output, re.IGNORECASE)
        if match:
            detected_language = match.group(1).strip()
            # Remove the tag from the normalized text
            normalized_text = raw_output[:match.start()].strip()
        
        # 3. Update State
        self._detector._update_state_(input_text, normalized_text, detected_language)

        return self._detector._get_state_()
