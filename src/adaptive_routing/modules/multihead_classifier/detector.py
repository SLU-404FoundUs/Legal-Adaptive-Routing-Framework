"""
Saint Louis University : Team 404FoundUs
@file_ detector.py
@project_ LLM Legal Adaptive Routing Framework
@desc_ Module for storing state: original prompt, detected language, and normalized text.
"""

class LanguageStateDetector:
    """
    @class_ LanguageStateDetector
    @desc_ Stores the state of the linguistic processing: original input, detected language, and final normalized output.
    @attr_ _original_prompt : (str) The raw input from the user.
    @attr_ _detected_language : (str) The identified language of the input (Tagalog, English, Taglish).
    @attr_ _normalized_text : (str) The sanitized English text.
    """
    def __init__(self):
        self._original_prompt = None
        self._detected_language = None
        self._normalized_text = None

    def _update_state_(self, original: str, normalized: str, language: str):
        """
        @func_ _update_state_ (@params original, normalized, language)
        @params original : The raw input.
        @params normalized : The processed English text.
        @params language : The detected language tag.
        @desc_ Updates the internal state with the results of a triage cycle.
        """
        self._original_prompt = original
        self._normalized_text = normalized
        self._detected_language = language

    def _get_state_(self):
        """
        @func_ _get_state_
        @return_ dict : A dictionary containing the current state.
        """
        return {
            "original_prompt": self._original_prompt,
            "detected_language": self._detected_language,
            "normalized_text": self._normalized_text
        }
