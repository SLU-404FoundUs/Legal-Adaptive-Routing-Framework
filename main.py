import os
import glob
from dotenv import load_dotenv

from src.adaptive_routing import FrameworkConfig, TriageModule, LegalRetrievalModule
from src.adaptive_routing.modules.semantic_router.logic_classifier import RoutingClassifier
from src.adaptive_routing.modules.semantic_router.legal_generation import LegalGenerator

load_dotenv()

def main():
    # 1. Configuration Setup
    custom_system_prompt = (
        "ROLE: Legal Query Router\n"
        "TASK: Analyze the USER QUERY and decide between two LLMs.\n"
        "\n"
        "General-LLM:\n"
        "- General legal information\n"
        "- Definitions, explanations, rights overview\n"
        "- Simple Q&A\n"
        "- No personalized advice\n"
        "- No complex scenario or dispute\n"
        "\n"
        "Reasoning-LLM:\n"
        "- Describes a real or hypothetical situation\n"
        "- Asks what action to take\n"
        "- Involves disputes, violations, contracts, termination, abuse, or legal risk\n"
        "- Requires legal interpretation and structured reasoning\n"
        "\n"
        "Constraints:\n"
        "- Strictly adhere to the ROLE and TASK above\n"
        "- The router must return structured JSON only\n"
        "- No markdown allowed in output\n"
        "- Do NOT answer the question\n"
        "\n"
        "JSON Schema:\n"
        "{\n"
        '  "route": "General-LLM" | "Reasoning-LLM",\n'
        '  "confidence": float,\n'
        '  "trigger_signals": [list of short strings]\n'
        "}"
    )

    FrameworkConfig._update_settings_(
        # --- Authentication ---
        api_key=os.getenv("OPENROUTER_API_KEY", ""),

        # --- Triage Module (Normalization) ---
        triage_model="qwen/qwen3-4b:free",
        triage_temp=0.6,
        triage_max_tokens=1500,
        triage_use_system=True,
        triage_reasoning=True,

        # --- Semantic Router (Classification) ---
        router_model="google/gemma-3-12b-it:free",
        router_temp=0.0,
        router_max_tokens=200,
        router_use_system=False,
        router_reasoning=False,

        # --- Legal Generator: General Information ---
        general_model="google/gemma-3-12b-it:free",
        general_temp=0.5,
        general_max_tokens=1000,
        general_use_system=False,
        general_reasoning=False,

        # --- Legal Generator: Reasoning/Advice ---
        reasoning_model="google/gemma-3-12b-it:free",
        reasoning_temp=0.7,
        reasoning_max_tokens=2000,
        reasoning_use_system=False,
        reasoning_reasoning=True,

        # --- Legal Retrieval (RAG) Module ---
        retrieval_model="sentence-transformers/all-minilm-l6-v2",
        retrieval_top_k=5,
        retrieval_chunk_size=512,
        retrieval_chunk_overlap=64,
        
        # Override for testing purposes as per user request
        # REASONING_INSTRUCTIONS=custom_system_prompt
    )

    # 2. Instantiate Components
    triage = TriageModule()
    classifier = RoutingClassifier()
    
    hk_retriever = LegalRetrievalModule()
    ph_retriever = LegalRetrievalModule()
    generator = LegalGenerator()
    
    # Helper logic to build or load separate indices
    def setup_index(retriever_instance, corpus_path, index_prefix):
        faiss_path = f"{index_prefix}.faiss"
        json_path = f"{index_prefix}.json"
        
        # Check if index is already built
        if os.path.exists(faiss_path) and os.path.exists(json_path):
            print(f"Loading {index_prefix} index directly...")
            retriever_instance._load_index_(faiss_path, json_path)
            return

        print(f"Building {index_prefix} index from {corpus_path}...")
        txt_files = glob.glob(os.path.join(corpus_path, "*.txt"))
        docs = []
        for file_path in txt_files:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                if content.strip():
                    docs.append(content)
                
        if docs:
            retriever_instance._ingest_documents_(docs)
            retriever_instance._save_index_(faiss_path, json_path)
            print(f"Saved {index_prefix} index successfully.")
        else:
            print(f"Warning: No text files found in {corpus_path}. Index will be empty.")

    # Load/Build from the respective subfolders inside legal-corpus
    setup_index(hk_retriever, "legal-corpus/HK", "hk_index")
    setup_index(ph_retriever, "legal-corpus/PH", "ph_index")
    
    # 3. Input
    input_text = "I want to file a case against my neighbor."
    print(f"--- INPUT QUERY ---\n{input_text}\n")

    # 4. Step 1: Triage (Normalization & State Detection)
    triaged_data = triage._process_request_(input_text)
    normalized_text = triaged_data.get("normalized_text", "")
    print(f"--- 1. TRIAGE OUTPUT ---\n{normalized_text}\n")

    # 5. Step 2: Semantic Router Classifier
    classification = classifier._route_query_(normalized_text)
    route = classification.get("route", "Unknown")
    print(f"--- 2. ROUTE CLASSIFICATION ---\nRoute: {route}\n")

    # 6. Step 3 & 4: Retrieval and Generation (If Applicable)
    if route in ["General-LLM", "Reasoning-LLM"]:
        # Retrieval Step: Query from BOTH indices separately
        hk_data = hk_retriever._process_retrieval_(normalized_text)
        ph_data = ph_retriever._process_retrieval_(normalized_text)
        
        hk_chunks = hk_data.get("retrieved_chunks", [])
        ph_chunks = ph_data.get("retrieved_chunks", [])
        
        print(f"--- 3. RETRIEVAL OUTPUT ---")
        print(f"Found {len(hk_chunks)} chunks for HK and {len(ph_chunks)} chunks for PH.\n")
        
        # Build Augmented Prompt mapping them distinctly
        context_str = "[HONG KONG LEGAL CONTEXT]\n"
        if hk_chunks:
            context_str += "\n".join([f"- {c['chunk']}" for c in hk_chunks])
        else:
            context_str += "- No relevant HK laws found."
            
        context_str += "\n\n[PHILIPPINES LEGAL CONTEXT]\n"
        if ph_chunks:
            context_str += "\n".join([f"- {c['chunk']}" for c in ph_chunks])
        else:
            context_str += "- No relevant PH laws found."
            
        augmented_query = f"CONTEXT:\n{context_str}\n\nUSER QUERY:\n{normalized_text}"
            
        # Generation Step
        response_text = generator._dispatch_(augmented_query, route)
        print(f"--- 4. GENERATED RESPONSE ({route}) ---\n{response_text}\n")
        
    else:
        # Fallback / Invalid Path (e.g. PATHWAY_2)
        print("--- 3. FALLBACK PATHWAY ---")
        print("Hi There. Can you please clarify your inquiry or provide specific details.")


if __name__ == "__main__":
    main()
