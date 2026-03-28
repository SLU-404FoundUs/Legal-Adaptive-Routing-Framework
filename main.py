import os
from dotenv import load_dotenv
from src.adaptive_routing import (
    FrameworkConfig, 
    TriageModule, 
    SemanticRouterModule, 
    LegalRetrievalModule
)

# 1. Setup Environment and Configuration
load_dotenv()
FrameworkConfig._update_settings_(
    api_key=os.getenv("OPENROUTER_API_KEY", ""),
    triage_model="z-ai/glm-4.5-air:free",
    router_model="z-ai/glm-4.5-air:free",
    general_model="z-ai/glm-4.5-air:free",
    reasoning_model="z-ai/glm-4.5-air:free",
    casual_model="z-ai/glm-4.5-air:free"
)

# 2. Initialize Core Modules
print("[System] Initializing Adaptive Routing Framework...")
triage = TriageModule()
router = SemanticRouterModule()
retrieval = LegalRetrievalModule(
    index_path="localfiles/legal-basis/combined_index.faiss",
    chunks_path="localfiles/legal-basis/combined_index.json"
)

# 3. Initialize Conversation History
history = []

print("\n--- Legal Assistant Ready ---")
print("Type 'exit' to quit.\n")

while True:
    user_input = input("User: ")
    if user_input.lower() in ['exit', 'quit']:
        break

    # Stage 1: Triage (Normalization)
    triage_result = triage._process_request_(user_input)
    normalized_text = triage_result["normalized_text"]
    print(f"[Triage] Language: {triage_result['detected_language']} | Normalized: {normalized_text}")

    # Stage 2: Classification Only
    classification = router._process_routing_(normalized_text)
    route = classification.get("route", "General-LLM")
    print(f"[Router] Route: {route} | Confidence: {classification.get('confidence', 0.0)}")

    # Stage 3: RAG Retrieval (skip for Casual)
    context_str = None
    if route != "Casual-LLM":
        retrieval_output = retrieval._process_retrieval_(normalized_text)
        chunks = retrieval_output.get("retrieved_chunks", [])
        if chunks:
            context_str = "\n\n".join([c.get("chunk", "") for c in chunks[:3]])
            print(f"[RAG] Retrieved {len(chunks[:3])} relevant legal sources.")

    # Stage 4: Generation (Multi-Turn with confidence threshold)
    result = router._generate_conversation_(
        classification=classification,
        messages=history,
        context=context_str,
        limits=0.6
    )

    response = result["response_text"]

    # Update history for next turn
    history.append({"role": "user", "content": normalized_text})
    history.append({"role": "assistant", "content": response})

    # Output
    accepted = "✓ Accepted" if result["accepted"] else "✗ Rejected"
    print(f"[Status] {accepted}")
    print(f"\nAssistant: {response}\n")
    print("-" * 60 + "\n")
