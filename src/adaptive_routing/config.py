## Saint Louis University
## Team 404FoundUs
## @file src/adaptive_routing/config.py
## @project_ LLM Legal Adaptive Routing Framework
## @desc_ Centralized configuration for OpenRouter parameters and security.
## @deps os, dotenv

import os

class FrameworkConfig:
    """
    @class FrameworkConfig
    @desc_ Manages global AI hyperparameters in different modules.
    """
    ## @const_ Global Defaults
    _API_KEY = os.getenv("OPENROUTER_API_KEY", "")
    
    ## @const_ Triage Module Configuration (Linguistic Normalizer)
    _TRIAGE_MODEL = os.getenv("TRIAGE_MODEL", "qwen/qwen3-4b:free")
    _TRIAGE_TEMP = float(os.getenv("TRIAGE_TEMP", "0.6"))
    _TRIAGE_MAX_TOKENS = int(os.getenv("TRIAGE_MAX_TOKENS", "1500"))
    _TRIAGE_USE_SYSTEM = os.getenv("TRIAGE_USE_SYSTEM", "True").lower() == "true"
    _TRIAGE_REASONING = os.getenv("TRIAGE_REASONING", "True").lower() == "true"

    ## @const_ Semantic Router Configuration
    # Switching strictly to Gemma 4B Instruct as requested/available, or fallback.
    _ROUTER_MODEL = os.getenv("ROUTER_MODEL", "google/gemma-3-4b-it:free")
    _ROUTER_TEMP = float(os.getenv("ROUTER_TEMP", "0.0"))
    _ROUTER_MAX_TOKENS = int(os.getenv("ROUTER_MAX_TOKENS", "200"))
    _ROUTER_USE_SYSTEM = os.getenv("ROUTER_USE_SYSTEM", "False").lower() == "true"
    _ROUTER_REASONING = os.getenv("ROUTER_REASONING", "False").lower() == "true"

    ## @const_ Fallbacks (Legacy/General)
    _DEFAULT_MODEL = _TRIAGE_MODEL 
    _TEMPERATURE = 0.7
    _MAX_TOKENS = 1500
    _USE_SYSTEM_ROLE = True
    _INCLUDE_REASONING = False

    @classmethod
    def _update_settings_(cls, **kwargs):
        """
        @func_ _update_settings_
        @params kwargs: Dict of hyperparameter overrides.
        @logic_ Dynamically updates class attributes if they exist.
        """
        ## @iter_ kwargs: iterating over provided settings to update config
        for key, value in kwargs.items():
            # Support both direct casing and underscored casing
            attr_name = f"_{key.upper()}" if not key.startswith("_") else key.upper()
            if hasattr(cls, attr_name):
                setattr(cls, attr_name, value)

    ## @const_ General LLM Configuration (Information)
    _GENERAL_MODEL = os.getenv("GENERAL_MODEL", "google/gemma-3-27b-it:free")
    _GENERAL_TEMP = float(os.getenv("GENERAL_TEMP", "0.5"))
    _GENERAL_MAX_TOKENS = int(os.getenv("GENERAL_MAX_TOKENS", "1000"))
    _GENERAL_USE_SYSTEM = os.getenv("GENERAL_USE_SYSTEM", "False").lower() == "true"
    _GENERAL_REASONING = os.getenv("GENERAL_REASONING", "False").lower() == "true"
    _GENERAL_INSTRUCTIONS = (
        "ROLE: Legal Information Assistant\n"
        "TASK: Provide general legal information, definitions, and explanations for Philippine and Hong Kong labor laws.\n\n"
        "OUTPUT FORMAT (MANDATORY):\n"
        "1. **Query Overview**: Briefly restate the legal topic or question asked.\n"
        "2. **Relevant Legal Concepts**: strict citation of relevant laws, rules, or regulations (PH/HK). Define key terms.\n"
        "3. **General Explanation**: Explain how these laws generally apply. Do NOT apply to specific user facts. Use neutral, educational language.\n"
        "4. **Summary**: Provide a concise answer or definition.\n\n"
        "CONSTRAINTS:\n"
        "- Do NOT provide specific legal advice or analysis of hypothetical scenarios.\n"
        "- Clearly distinguish between PH and HK jurisdictions.\n"
        "- Maintain a professional, educational tone."
    )

    ## @const_ Reasoning LLM Configuration (Advice/Scenario)
    _REASONING_MODEL = os.getenv("REASONING_MODEL", "google/gemma-3-4b-it:free") # Fallback to working model
    _REASONING_TEMP = float(os.getenv("REASONING_TEMP", "0.7"))
    _REASONING_MAX_TOKENS = int(os.getenv("REASONING_MAX_TOKENS", "2000"))
    _REASONING_USE_SYSTEM = os.getenv("REASONING_USE_SYSTEM", "False").lower() == "true"
    _REASONING_REASONING = os.getenv("REASONING_REASONING", "True").lower() == "true"
    _REASONING_INSTRUCTIONS = (
        "ROLE: Legal AI Assistant (Philippine & HK Labor Law Focus)\n\n"
        "OUTPUT FORMAT (MANDATORY) - ALAC STANDARD:\n"
        "You MUST answer in this exact order:\n\n"
        "1. **Application**\n"
        "- Restate relevant facts. No new assumptions. No citations here.\n"
        "- Clarify jurisdiction (Philippines, Hong Kong, or both).\n\n"
        "2. **Law**\n"
        "- Cite ONLY relevant laws/rules (e.g., PH Labor Code, HK Employment Ordinance).\n"
        "- Specify jurisdiction clearly.\n"
        "- Do NOT analyze yet.\n\n"
        "3. **Analysis**\n"
        "- Apply laws to the facts.\n"
        "- Compare requirements vs actual events.\n"
        "- Address key issues clearly. Avoid speculation.\n\n"
        "4. **Conclusion**\n"
        "- Direct answer to the question.\n"
        "- Likely legal position (no guarantees).\n"
        "- General next steps (e.g., 'seek legal assistance').\n\n"
        "SAFETY & BOUNDARIES:\n"
        "- You are NOT a lawyer. Do NOT give legal advice.\n"
        "- Do NOT predict court outcomes.\n"
        "- Use simple, clear language for non-lawyers."
    )
