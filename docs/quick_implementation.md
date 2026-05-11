# Quick Implementation Guide

This guide demonstrates how to quickly implement the entire **Legal Adaptive Routing Framework** in a single, cohesive script. This is the recommended approach for integrating the framework into your own web applications, Discord bots, or CLI tools.

It covers the complete pipeline: **Triage → Router → Retrieval → Generation → Safety Audit**, as well as the initialization of the `FrameworkConfig`.

---

## Complete Implementation Script

Create a file named `app.py` or similar, and use the following template to instantly deploy a fully functional legal assistant.

```python
import os
from dotenv import load_dotenv

# 1. Import Framework Configuration and Module Facades
from src.adaptive_routing.config import FrameworkConfig
from src.adaptive_routing import (
    TriageModule, 
    SemanticRouterModule, 
    LegalRetrievalModule, 
    SafetyAuditModule
)

# Load your OpenRouter API key from .env
load_dotenv()

def main():
    print("--- Agapay Legal AI Initializing ---")
    
    # 2. (Optional) Pragmatic Configuration Override
    # You can customize thresholds, models, and temperatures at runtime.
    FrameworkConfig._update_settings_(
        general_strictness=0.75,
        router_temp=0.1,
        triage_model="google/gemma-4-26b-a4b-it"
    )
    
    # 3. Initialize all framework components
    triage = TriageModule()
    router = SemanticRouterModule()
    retrieval = LegalRetrievalModule(
        index_path="localfiles/legal-basis/combined_index.faiss",
        chunks_path="localfiles/legal-basis/combined_index.json"
    )
    audit = SafetyAuditModule()
    
    print("System Ready. Type 'exit' to quit.\n")

    # 4. Interactive Chat Loop
    while True:
        query = input("User: ")
        if not query.strip() or query.lower() in ["exit", "quit"]:
            break
            
        # ==========================================
        # STAGE 1: Triage (Linguistic Normalization)
        # ==========================================
        triage_data = triage._process_request_(query)
        norm_text = triage_data.get("normalized_text", query)
        lang = triage_data.get("detected_language", "Unknown")
        
        # ==========================================
        # STAGE 2: Routing (Intent Classification)
        # ==========================================
        classification = router._process_routing_(norm_text, threshold=0.1)
        route = classification.get("route", "General-LLM")
        
        # ==========================================
        # STAGE 3: Retrieval (Signal-Guided RAG)
        # ==========================================
        context = None
        if route != "Casual-LLM" and classification.get("search_signals"):
            ret_data = retrieval._process_retrieval_(norm_text, classification["search_signals"])
            chunks = ret_data.get("retrieved_chunks", [])
            # Combine the top 3 chunks for context
            context = "\n\n".join([c.get("chunk", "") for c in chunks[:3]]) if chunks else None

        # ==========================================
        # STAGE 4: Generation (Context-Aware LLM)
        # ==========================================
        # Note: We pass 'detected_language' so the generator replies in the user's origin language!
        gen_data = router._generate_conversation_(
            classification=classification,
            messages=[{"role": "user", "content": norm_text}],
            context=context,
            detected_language=lang
        )
        response_text = gen_data.get("response_text", "No response generated.")
        
        # ==========================================
        # STAGE 5: Safety Audit (Compliance Check)
        # ==========================================
        audit_data = audit._run_audit_(norm_text, response_text, route)
        if audit_data.get("verdict") != "COMPLIANT":
            # If the response violates safety/quality standards, override it with a safeguard message
            response_text = audit._build_safeguard_message_()

        # Output the final response
        print(f"\nAgapay [{route}]: {response_text}\n")


if __name__ == "__main__":
    main()
```

## Highlights of this Implementation

- **Configuration Control**: Notice how `FrameworkConfig._update_settings_()` is called immediately after imports. This ensures all modules initialize with your preferred models and strictness levels.
- **Language Persistence**: In Stage 4, `detected_language=lang` is explicitly passed to the generator. This guarantees that even though the internal RAG process happens in formal English, the final response is dynamically adapted back into the user's original language (e.g., Tagalog, Taglish).
- **Safety Fallbacks**: Stage 5 intercepts harmful or hallucinated outputs and swaps them out with the framework's built-in safeguard apology, ensuring your end-users are never exposed to low-quality legal advice.

---

<div align="center">
  <a href="safety_audit_module.md">⏮️ Previous: Safety Audit</a> |
  <a href="documentation.md">🔙 Back to Main Documentation</a>
</div>
