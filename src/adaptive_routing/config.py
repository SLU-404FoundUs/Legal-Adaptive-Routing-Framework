## Saint Louis University
## Team 404FoundUs
## @file src/adaptive_routing/config.py
## @project_ LLM Legal Adaptive Routing Framework
## @desc_ Centralized configuration for OpenRouter parameters and security.
## @deps os, dotenv

import os
from dotenv import load_dotenv

load_dotenv()

class FrameworkConfig:
    """
    @class FrameworkConfig
    @desc_ Manages global AI hyperparameters and credential retrieval for gemma 3n superior for its fast and language handling.
    """
    ## @const_ Global configuration constants
    _API_KEY = os.getenv("OPENROUTER_API_KEY")
    _DEFAULT_MODEL = "google/gemma-3-4b-it:free"
    _TEMPERATURE = 0.3
    _MAX_TOKENS = 1500
    _USE_SYSTEM_ROLE = False

    @classmethod
    def _update_settings_(cls, **kwargs):
        """
        @func_ _update_settings_
        @params kwargs: Dict of hyperparameter overrides.
        @logic_ Dynamically updates class attributes if they exist.
        """
        ## @iter_ kwargs: iterating over provided settings to update config
        for key, value in kwargs.items():
            attr_name = f"_{key.upper()}"
            if hasattr(cls, attr_name):
                setattr(cls, attr_name, value)
