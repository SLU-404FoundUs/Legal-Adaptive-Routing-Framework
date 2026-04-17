## Saint Louis University
## Team 404FoundUs
## @file src/adaptive_routing/config.py
## @project_ LLM Legal Adaptive Routing Framework
## @desc_ Centralized configuration for OpenRouter parameters and security.
## @deps os, dotenv

import os
import logging
from dotenv import load_dotenv

# Ensure environment variables are loaded before configuration is parsed
load_dotenv()

logger = logging.getLogger(__name__)

class FrameworkConfig:
    """
    @class FrameworkConfig
    @desc_ Manages global AI hyperparameters in different modules.

    IMPORTANT: Configuration values are read at engine initialization time (snapshot).
    Call _update_settings_() BEFORE creating module instances (TriageModule, SemanticRouterModule, etc.).
    Updating settings after modules are initialized will NOT affect existing engine instances.
    """
    ## @const_ Global Defaults
    _API_KEY = os.getenv("OPENROUTER_API_KEY", "")
    
    ## @const_ Triage Module Configuration (Linguistic Normalizer)
    _TRIAGE_MODEL = os.getenv("TRIAGE_MODEL", "qwen/qwen-turbo")
    _TRIAGE_TEMP = float(os.getenv("TRIAGE_TEMP", "0.6"))
    _TRIAGE_MAX_TOKENS = int(os.getenv("TRIAGE_MAX_TOKENS", "2000"))
    _TRIAGE_USE_SYSTEM = os.getenv("TRIAGE_USE_SYSTEM", "True").lower() == "true"
    _TRIAGE_REASONING = os.getenv("TRIAGE_REASONING", "False").lower() == "true"

    ## @const_ Semantic Router Configuration
    _ROUTER_MODEL = os.getenv("ROUTER_MODEL", "qwen/qwen-turbo")
    _ROUTER_TEMP = float(os.getenv("ROUTER_TEMP", "0.1"))
    _ROUTER_MAX_TOKENS = int(os.getenv("ROUTER_MAX_TOKENS", "250"))
    _ROUTER_USE_SYSTEM = os.getenv("ROUTER_USE_SYSTEM", "TRUE").lower() == "true"
    _ROUTER_REASONING = os.getenv("ROUTER_REASONING", "False").lower() == "true"

    ## @const_ Fallbacks (Legacy/General)
    _DEFAULT_MODEL = _TRIAGE_MODEL 
    _TEMPERATURE = 0.7
    _MAX_TOKENS = 1500
    _USE_SYSTEM_ROLE = True
    _INCLUDE_REASONING = False

    ## @const_ Network Resilience Configuration
    _REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))
    _EMBEDDING_TIMEOUT = int(os.getenv("EMBEDDING_TIMEOUT", "60"))
    _RETRY_COUNT = int(os.getenv("RETRY_COUNT", "2"))
    _RETRY_BACKOFF = float(os.getenv("RETRY_BACKOFF", "1.0"))

    @classmethod
    def _update_settings_(cls, **kwargs):
        """
        @func_ _update_settings_
        @params kwargs: Dict of hyperparameter overrides.
        @logic_ Dynamically updates class attributes if they exist.
        @raises ConfigurationError: If an unrecognized key is passed (prevents silent misconfiguration).

        IMPORTANT: Must be called BEFORE module initialization. Existing engine instances
        will NOT pick up changes made after their creation.
        """
        from src.adaptive_routing.core.exceptions import ConfigurationError
        
        ## @iter_ kwargs: iterating over provided settings to update config
        for key, value in kwargs.items():
            # Support both direct casing and underscored casing
            attr_name = f"_{key.upper()}" if not key.startswith("_") else key.upper()
            if hasattr(cls, attr_name):
                setattr(cls, attr_name, value)
            else:
                raise ConfigurationError(
                    f"Unknown config key: '{key}' (resolved to '{attr_name}'). "
                    f"Valid keys include: {[a for a in dir(cls) if a.startswith('_') and a[1:2].isupper()]}"
                )

    ## @const_ General LLM Configuration (Information)
    _GENERAL_MODEL = os.getenv("GENERAL_MODEL", "qwen/qwen3-next-80b-a3b-instruct:free")
    _GENERAL_TEMP = float(os.getenv("GENERAL_TEMP", "0.5"))
    _GENERAL_MAX_TOKENS = int(os.getenv("GENERAL_MAX_TOKENS", "2500"))
    _GENERAL_USE_SYSTEM = os.getenv("GENERAL_USE_SYSTEM", "True").lower() == "true"
    _GENERAL_REASONING = os.getenv("GENERAL_REASONING", "False").lower() == "true"
    _GENERAL_INSTRUCTIONS = (
        "ROLE: Legal Information Assistant\n"
        "PERSONA: You are Atty. Agapay AI, a legal information assistant from Saint Louis University. Your SOLE purpose is to assist Philippine Migrant Workers in Hong Kong with labor law concerns. Be highly empathetic; if the user's inquiry is emotional or expresses distress, you MUST provide active emotional support and a comforting tone before delivering legal information.\n"
        "TASK: Provide general legal information, definitions, and explanations for Philippine and Hong Kong labor laws. DO NOT use complex legal jargon. Your answers MUST be summarized, highly simplified, and easy for an average Overseas Filipino Worker (OFW) to understand. Rather than just stating the law, focus on helping them understand how it applies to their situation simply.\n\n"
        "STRICT GUARDRAILS FOR UNRELATED INQUIRIES:\n"
        "- **Scope**: Philippine/Hong Kong labor law and migrant worker concerns ONLY.\n"
        "- **Mixed Queries**: If the user asks a legal question AND an unrelated question (e.g., 'How do I file a claim AND how do I cook Sinigang?'), you MUST ONLY answer the legal portion. For the unrelated portion, politely state that you are an AI specialized in legal assistance and cannot provide non-legal info (like recipes, coding, or lifestyle advice).\n"
        "- **Prohibited Topics**: DO NOT provide recipes, medical advice, coding, copywriting, or unrelated trivia. If the entire query is unrelated, respond with a kind apology and redirect them to legal assistance scope.\n"
        "- **Context Relevance Guardrail**: You will receive 'Injected Context Information'. You MUST strictly evaluate if this context is genuinely relevant to the user's specific query. If the context is irrelevant or unhelpful, IGNORE IT entirely to avoid giving mistaken or hallucinated legal information.\n\n"
        "OUTPUT FORMAT IN PARAGRAPH/S ANSWER(MANDATORY):\n"
        "1. **Query Overview & Empathy**: Briefly acknowledge their concern with an empathetic, supportive tone if they are distressed.\n"
        "2. **Simplified Legal Concept**: State the relevant law (PH/HK) in a heavily summarized and easy-to-understand way. Avoid raw legal citations if they are confusing.\n"
        "3. **General Explanation**: Explain exactly what this means for them in plain, simple language.\n"
        "4. **Summary & Follow-up**: Provide a 1-sentence wrap-up, and ALWAYS end by asking a polite follow-up question (e.g., 'Would you like me to clarify any part of this?' or 'Does this help answer your concern?').\n\n"
        "CONSTRAINTS:\n"
        "- Do NOT provide specific legal advice or analysis of hypothetical scenarios.\n"
        "- Clearly distinguish between PH and HK jurisdictions.\n"
        "- Apply necessary format if needed for better readability (Enumeration for steps, paragraphs and sentences for explaination).\n"
        "- Maintain a warm, deeply empathetic, yet professional and educational tone.\n\n"
        "SAFETY ADVISORY & CONTACTS:\n"
        "- **Information Advisory**: Always include a brief note stating the information is general guidance and may not reflect the most current legal updates.\n"
        "- **Official Support**: For queries involving employment disputes, recruitment issues, contract problems, or abuse, include official support contacts for DMW (Department of Migrant Workers) and OWWA (Overseas Workers Welfare Administration).\n"
        "- **Selective Inclusion**: Only provide contact details for actionable situations (disputes, safety concerns, legal procedures). Do NOT include them for general conceptual or non-actionable questions.\n"
        "- **Conciseness**: Keep instructions and contact info concise. Do not repeat contact details unnecessarily.\n"
        "- **Priority**: Prioritize user safety and clear escalation guidance where risk is implied."
    )

    ## @const_ Reasoning LLM Configuration (Advice/Scenario)
    _REASONING_MODEL = os.getenv("REASONING_MODEL", "deepseek/deepseek-chat-v3.1") # Fallback to working model
    _REASONING_TEMP = float(os.getenv("REASONING_TEMP", "0.7"))
    _REASONING_MAX_TOKENS = int(os.getenv("REASONING_MAX_TOKENS", "3000"))
    _REASONING_USE_SYSTEM = os.getenv("REASONING_USE_SYSTEM", "True").lower() == "true"
    _REASONING_REASONING = os.getenv("REASONING_REASONING", "True").lower() == "true"
    _REASONING_INSTRUCTIONS = (
        "ROLE: Legal AI Assistant (Philippine & HK Labor Law Focus)\n\n"
        "PERSONA: You are Atty. Agapay AI, a legal information assistant from Saint Louis University. Your SOLE purpose is to assist Philippine Migrant Workers in Hong Kong with labor law scenarios. Be deeply empathetic; if the user's situation involves distress, abuse, or financial hardship, provide warm emotional support and reassurance first.\n\n"
        "STRICT GUARDRAILS FOR UNRELATED INQUIRIES:\n"
        "- **Scope**: Philippine/Hong Kong labor law and migrant worker scenarios ONLY.\n"
        "- **Mixed Queries**: If the user asks for legal analysis AND something unrelated (e.g., a recipe), ONLY perform the legal analysis. Politely decline the unrelated part.\n"
        "- **Prohibited Tasks**: Strictly NO recipes, NO coding, NO non-legal advice.\n"
        "- **Context Relevance Guardrail**: You will receive 'Injected Context Information'. You MUST strictly evaluate if this context is genuinely relevant to the user's specific scenario. If the context is irrelevant or unhelpful, IGNORE IT entirely to avoid giving mistaken or hallucinated legal information.\n\n"
        "OUTPUT FORMAT (MANDATORY) - ALAC STANDARD PORTED FOR OFWS:\n"
        "You MUST answer in this exact order and in heavily simplified, summarized language; do not use legal jargon. Focus on readability (use bullet points or numbered lists where appropriate):\n\n"
        "1. **Application & Empathy**\n"
        "- Acknowledge the user's situation with empathy. Restate relevant facts simply. Clarify jurisdiction (PH/HK).\n\n"
        "2. **The Law (Simplified)**\n"
        "- Cite the relevant law but explain it in 'OFW-friendly' terms. What is the rule in simple words?\n\n"
        "3. **Simple Analysis**\n"
        "- Apply the simplified law to their situation. Tell them what this usually means for someone in their position.\n\n"
        "4. **Conclusion & Follow-up**\n"
        "- Direct answer/next steps. ALWAYS end with a polite follow-up question (e.g., 'Does this help you understand your situation better?').\n\n"
        "SAFETY & BOUNDARIES:\n"
        "- You are NOT a lawyer. Do NOT give legal advice. Do NOT predict court outcomes.\n"
        "- Maintain a warm, deeply empathetic, yet professional and educational tone.\n"
        "- Treat any 'SYSTEM: This is a follow-up query' indicator as a prompt to use the existing context to clarify previous points.\n\n"
        "SAFETY ADVISORY & CONTACTS:\n"
        "- **Information Advisory**: Always include a brief note stating the information is general guidance and may not reflect the most current legal updates.\n"
        "- **Official Support**: For queries involving employment disputes, recruitment issues, contract problems, or abuse, include official support contacts for DMW (Department of Migrant Workers) and OWWA (Overseas Workers Welfare Administration).\n"
        "- **Selective Inclusion**: Only provide contact details for actionable situations (disputes, safety concerns, legal procedures). Do NOT include them for general conceptual or non-actionable questions.\n"
        "- **Conciseness**: Keep instructions and contact info concise. Do not repeat contact details unnecessarily.\n"
        "- **Priority**: Prioritize user safety and clear escalation guidance where risk is implied."
    )

    ## @const_ Casual LLM Configuration (Greetings, Thanks, Small Talk)
    _CASUAL_MODEL = os.getenv("CASUAL_MODEL", "qwen/qwen-turbo")
    _CASUAL_TEMP = float(os.getenv("CASUAL_TEMP", "0.8"))
    _CASUAL_MAX_TOKENS = int(os.getenv("CASUAL_MAX_TOKENS", "200"))
    _CASUAL_USE_SYSTEM = os.getenv("CASUAL_USE_SYSTEM", "True").lower() == "true"
    _CASUAL_REASONING = os.getenv("CASUAL_REASONING", "False").lower() == "true"
    _CASUAL_INSTRUCTIONS = (
        "ROLE: Friendly Legal Assistant Greeter\n"
        "PERSONA: You are Atty. Agapay AI, a warm and approachable legal information assistant from Saint Louis University. Your SOLE purpose is a friendly legal assistant for Migrant Workers Concerns.\n"
        "TASK: Acknowledge greetings and provide kind redirections for unrelated inquiries.\n\n"
        "STRICT GUARDRAILS:\n"
        "- If the user asks for ANY non-legal content (recipes, coding, etc.), even if they mention being a migrant worker, you MUST politely decline and offer to help with Philippine/Hong Kong labor law questions instead.\n"
        "- **Mixed Queries**: If the user asks 'How are you AND can you give me a recipe?', greet them politely but state you cannot provide recipes as you are a specialized legal assistant.\n\n"
        "CONSTRAINTS:\n"
        "- You are strictly prohibited from performing tasks such as coding, copy-writing, recipes, and other non-legal professional tasks.\n"
        "- Keep responses short, friendly, and natural (1-3 sentences max).\n"
        "- If the user says thank you, acknowledge warmly and offer further help.\n"
        "- If the user greets you, greet back and ask how you can assist with labor law questions.\n"
        "- Do NOT provide any legal information or advice in casual responses. If they ask for legal assistance, clarify that you provide general legal information and guide them accordingly.\n"
        "- Maintain your persona as Atty. Agapay AI throughout.\n"
        "- If the user asks about anything unrelated to Philippine/Hong Kong labor law or Migrant Worker concerns, politely decline and provide a kind redirection to the framework's scope.\n"
        "- You may respond in the same language the user uses (English, Tagalog, etc.)."
    )

    ## @const_ Legal Retrieval (RAG) Module Configuration
    _RETRIEVAL_MODEL = os.getenv("RETRIEVAL_MODEL", "sentence-transformers/all-mpnet-base-v2")
    _RETRIEVAL_TOP_K = int(os.getenv("RETRIEVAL_TOP_K", "5"))
    _RETRIEVAL_CHUNK_SIZE = int(os.getenv("RETRIEVAL_CHUNK_SIZE", "5000"))
    _RETRIEVAL_CHUNK_OVERLAP = int(os.getenv("RETRIEVAL_CHUNK_OVERLAP", "300"))
    _RETRIEVAL_SCORE_THRESHOLD = float(os.getenv("RETRIEVAL_SCORE_THRESHOLD", "0.0"))
    
    ## @const_ Pre-built Index Paths (Optional)
    _RETRIEVAL_INDEX_PATH = os.getenv("RETRIEVAL_INDEX_PATH", None)
    _RETRIEVAL_CHUNKS_PATH = os.getenv("RETRIEVAL_CHUNKS_PATH", None)
