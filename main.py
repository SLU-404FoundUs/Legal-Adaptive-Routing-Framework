import os
from dotenv import load_dotenv
from src.adaptive_routing import TriageModule, SemanticRouterModule, LegalRetrievalModule, SafetyAuditModule

# Load environment variables
load_dotenv()

def main():
    print("--- Legal Adaptive Routing Framework ---")
    print("Initializing components...")
    
    triage = TriageModule()
    router = SemanticRouterModule()
    retrieval = LegalRetrievalModule(
        index_path="localfiles/legal-basis/combined_index.faiss",
        chunks_path="localfiles/legal-basis/combined_index.json"
    )
    audit = SafetyAuditModule()
    
    print("Ready. Type 'exit' to quit.\n")

    while True:
        query = input("User: ")
        if not query.strip() or query.lower() in ["exit", "quit"]:
            break
            
        # 1. Triage
        triage_data = triage._process_request_(query)
        norm_text = triage_data.get("normalized_text", query)
        lang = triage_data.get("detected_language", "Unknown")
        
        # 2. Routing
        classification = router._process_routing_(norm_text, threshold=0.1)
        route = classification.get("route", "General-LLM")
        
        # 3. Retrieval
        context = None
        if route != "Casual-LLM" and classification.get("search_signals"):
            ret_data = retrieval._process_retrieval_(norm_text, classification["search_signals"])
            chunks = ret_data.get("retrieved_chunks", [])
            context = "\n\n".join([c.get("chunk", "") for c in chunks[:3]]) if chunks else None

        # 4. Generation
        gen_data = router._generate_conversation_(
            classification=classification,
            messages=[{"role": "user", "content": norm_text}],
            context=context,
            detected_language=lang
        )
        response_text = gen_data.get("response_text", "No response generated.")
        
        # 5. Safety Audit
        audit_data = audit._run_audit_(norm_text, response_text, route)
        if audit_data.get("verdict") != "COMPLIANT":
            response_text = audit._build_safeguard_message_()

        print(f"\nAI [{route}]: {response_text}\n")

if __name__ == "__main__":
    main()
