## Saint Louis University
## Team 404FoundUs
## @file WEB.py
## @project_ LLM Legal Adaptive Routing Framework
## @desc_ Web interface (Flask) for the Legal Adaptive Routing Framework.
## @deps os, json, time, uuid, flask, dotenv, src.adaptive_routing

import os
import json
import time
import uuid
from flask import Flask, render_template, request, Response, stream_with_context
from dotenv import load_dotenv
from src.adaptive_routing import FrameworkConfig, TriageModule, SemanticRouterModule, LegalRetrievalModule
from src.adaptive_routing.modules.legal_retrieval.utils import legal_indexing
load_dotenv()

# --- Retry Configuration ---
MAX_RETRIES = 5
BASE_DELAY = 2  # seconds

def _is_rate_limited_(error):
    """Check if an exception is a 429 rate-limit error."""
    err_str = str(error).lower()
    return "429" in err_str or "rate" in err_str or "rate-limited" in err_str or "too many requests" in err_str



app = Flask(__name__)

# --- Configuration ---
FrameworkConfig._update_settings_(
        api_key=os.getenv("OPENROUTER_API_KEY", "")
    )

# Initialize Modules
try:
    triage_module = TriageModule()
    router_module = SemanticRouterModule()
    retrieval_module = LegalRetrievalModule()
    
    # Check and Build Initial FAISS Index if missing
    index_dir = os.path.join(os.getcwd(), "localfiles", "legal-basis")
    index_file = os.path.join(index_dir, "combined_index.faiss")
    chunks_file = os.path.join(index_dir, "combined_index.json")
    
    if os.path.exists(index_file) and os.path.exists(chunks_file):
        print(">>> Loading existing FAISS index...")
        retrieval_module._load_index_(index_file, chunks_file)
    else:
        print(">>> Building initial FAISS index for all jurisdictions (this may take a while)...")
        os.makedirs(index_dir, exist_ok=True)
        retrieval_module.build_and_save_index(
            corpus_dir="legal-corpus",
            output_dir=index_dir,
            index_prefix="combined_index"
        )
        print(">>> FAISS index built and saved successfully.")
        
    print(">>> Modules initialized successfully.")
    
    # Check sync status on startup
    sync_info = legal_indexing.verify_index_integrity(
        corpus_dir="legal-corpus",
        chunks_path=chunks_file
    )
    if not sync_info["is_synced"]:
        print(f">>> WARNING: Index is out of sync. {sync_info['missing_count']} documents missing.")
    else:
        print(">>> Index is fully synced with corpus.")

except Exception as e:
    print(f">>> Error initializing modules: {e}")
    triage_module = None
    router_module = None
    retrieval_module = None

# In-memory session storage
# Format: { "session_id": { "route": "...", "history": [...] } }
SESSIONS = {}

@app.route('/api/sync-status', methods=['GET'])
def get_sync_status():
    """Check if the vector index is up to date with the legal corpus."""
    try:
        index_dir = os.path.join(os.getcwd(), "localfiles", "legal-basis")
        chunks_file = os.path.join(index_dir, "combined_index.json")
        
        sync_info = legal_indexing.verify_index_integrity(
            corpus_dir="legal-corpus",
            chunks_path=chunks_file
        )
        return json.dumps(sync_info)
    except Exception as e:
        return json.dumps({"error": str(e)}), 500

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    user_input = data.get('message', '')
    session_id = data.get('sessionId')

    if not user_input:
        return Response("Message is required", status=400)

    def generate():
        nonlocal session_id
        
        try:
            # 1. Session Retrieval
            is_new_session = False
            if not session_id or session_id not in SESSIONS:
                session_id = str(uuid.uuid4())
                SESSIONS[session_id] = {
                    "history": [],
                    "last_rag_context": None
                }
                is_new_session = True
                
            history = SESSIONS[session_id]["history"]
            
            yield json.dumps({"type": "meta", "sessionId": session_id}) + "\n"
            if not is_new_session:
                yield json.dumps({"type": "step", "content": "Resuming session..."}) + "\n"

            # 2. Triage Step (with persistence for rate-limits)
            yield json.dumps({"type": "step", "content": "Normalizing input and detecting language..."}) + "\n"
            normalized_text = user_input
            detected_language = "Unknown"
            
            if triage_module:
                for attempt in range(1, MAX_RETRIES + 1):
                    try:
                        triaged_data = triage_module._process_request_(user_input)
                        if triaged_data and triaged_data.get("normalized_text"):
                            normalized_text = triaged_data.get("normalized_text", user_input)
                        detected_language = triaged_data.get("detected_language", "Unknown")
                        break
                    except Exception as triage_err:
                        if _is_rate_limited_(triage_err) and attempt < MAX_RETRIES:
                            delay = BASE_DELAY * attempt
                            print(f"Triage rate-limited (attempt {attempt}/{MAX_RETRIES}), retrying in {delay}s...")
                            yield json.dumps({"type": "step", "content": f"Rate-limited — retrying triage ({attempt}/{MAX_RETRIES})..."}) + "\n"
                            time.sleep(delay)
                        else:
                            print(f"Triage failed after {attempt} attempt(s): {triage_err}")
                            yield json.dumps({"type": "step", "content": "Triage failed — using raw input as fallback..."}) + "\n"
                            break
            
            yield json.dumps({
                "type": "data", 
                "title": "Triage Result",
                "data": {
                    "Original Input": user_input,
                    "Detected Language": detected_language,
                    "Normalized English": normalized_text
                }
            }) + "\n"

            if not normalized_text:
                yield json.dumps({"type": "error", "content": "Normalization failed. Input text unclear."}) + "\n"
                return

            # 3. Classification Step (with persistence for rate-limits)
            yield json.dumps({"type": "step", "content": "Routing query to appropriate model..."}) + "\n"
            classification = {"route": "General-LLM", "confidence": 0.0, "search_signals": None}
            
            if router_module:
                for attempt in range(1, MAX_RETRIES + 1):
                    try:
                        classification = router_module._process_routing_(normalized_text, threshold=0.1)
                        if classification.get("error") == "LLMEngine failed to acknowledge the input.":
                            yield json.dumps({"type": "step", "content": "Confidence below threshold — falling back to Casual conversation..."}) + "\n"
                            classification = {
                                "route": "Casual-LLM",
                                "confidence": 1.0,
                                "search_signals": None
                            }
                        break
                    except Exception as classify_err:
                        if _is_rate_limited_(classify_err) and attempt < MAX_RETRIES:
                            delay = BASE_DELAY * attempt
                            print(f"Classification rate-limited (attempt {attempt}/{MAX_RETRIES}), retrying in {delay}s...")
                            yield json.dumps({"type": "step", "content": f"Rate-limited — retrying classification ({attempt}/{MAX_RETRIES})..."}) + "\n"
                            time.sleep(delay)
                        else:
                            print(f"Classification failed after {attempt} attempt(s): {classify_err}")
                            break
            
            route = classification.get("route") or "General-LLM"
            confidence = classification.get("confidence", 0.0)
            signals = classification.get("search_signals")
            
            yield json.dumps({
                "type": "data",
                "title": "Routing Result",
                "data": {
                    "Selected Route": route,
                    "Confidence Score": confidence,
                    "Search Signals": signals
                }
            }) + "\n"

            # 4. RAG Retrieval (skip for Casual routes)
            context_str = SESSIONS[session_id].get("last_rag_context")

            if route != "Casual-LLM":
                if signals is not None:
                    yield json.dumps({"type": "step", "content": "Retrieving context via Hybrid Search (BM25 + Semantic)..."}) + "\n"
                    
                    if retrieval_module:
                        try:
                            retrieval_output = retrieval_module._process_retrieval_(normalized_text, signals=signals)
                            retrieved_chunks = retrieval_output.get("retrieved_chunks", [])
                            
                            if retrieved_chunks:
                                yield json.dumps({
                                    "type": "rag_context",
                                    "title": "Legal Sources Retrieved",
                                    "chunks": [{
                                        "text": chunk.get("chunk", ""), 
                                        "metadata": chunk.get("metadata", {}), 
                                        "score": float(chunk.get("score", 0.0))
                                    } for chunk in retrieved_chunks[:5]]
                                }) + "\n"
                                context_str = "\n".join([c.get("chunk", "") for c in retrieved_chunks])
                                SESSIONS[session_id]["last_rag_context"] = context_str
                            else:
                                yield json.dumps({"type": "step", "content": "No relevant context found..."}) + "\n"
                                SESSIONS[session_id]["last_rag_context"] = None
                                context_str = None
                        except Exception as rag_err:
                            print(f"RAG retrieval error: {rag_err}")
                            yield json.dumps({"type": "step", "content": "Retrieval omitted (fallback applied)..."}) + "\n"
                else:
                    if context_str:
                        yield json.dumps({"type": "step", "content": "Follow-up detected — Reusing previous legal context."}) + "\n"
                    else:
                        yield json.dumps({"type": "step", "content": "Follow-up detected — No previous context available."}) + "\n"
            else:
                yield json.dumps({"type": "step", "content": "Casual conversation detected — skipping legal retrieval..."}) + "\n"
                context_str = None

            # 5. Generation Step (with persistence for rate-limits)
            yield json.dumps({"type": "step", "content": "Generating response..."}) + "\n"
            
            # Add the user's clean message to history before generation
            history.append({"role": "user", "content": normalized_text})
            
            response_text = ""
            if router_module:
                for attempt in range(1, MAX_RETRIES + 1):
                    try:
                        result = router_module._generate_conversation_(
                            classification=classification,
                            messages=history,
                            context=context_str,
                            is_follow_up=(signals is None and route != "Casual-LLM")
                        )
                        response_text = result.get("response_text", "")
                        accepted = result.get("accepted", False)
                        
                        if not accepted:
                            yield json.dumps({"type": "step", "content": "Confidence below threshold — requesting clarification..."}) + "\n"
                        break
                    except Exception as gen_err:
                        if _is_rate_limited_(gen_err) and attempt < MAX_RETRIES:
                            delay = BASE_DELAY * attempt
                            print(f"Generation rate-limited (attempt {attempt}/{MAX_RETRIES}), retrying in {delay}s...")
                            yield json.dumps({"type": "step", "content": f"Rate-limited — retrying generation ({attempt}/{MAX_RETRIES})..."}) + "\n"
                            time.sleep(delay)
                        else:
                            print(f"Generation failed after {attempt} attempt(s): {gen_err}")
                            response_text = "I am currently unable to process your query due to a technical error. Please try again."
                            break
            else:
                response_text = "I am currently unable to process your query due to a technical error."

            # 6. Finalize response
            if response_text:
                history.append({"role": "assistant", "content": response_text})
                SESSIONS[session_id]["route"] = route
                yield json.dumps({"type": "result", "content": response_text}) + "\n"
            else:
                yield json.dumps({"type": "error", "content": "No response generated."}) + "\n"

        except Exception as e:
            yield json.dumps({"type": "error", "content": f"Server Error: {str(e)}"}) + "\n"
            print(f"Error processing request: {e}")

    return Response(stream_with_context(generate()), mimetype='application/x-ndjson')

@app.route('/api/config', methods=['GET'])
def get_config():
    return json.dumps({
        "api_key": FrameworkConfig._API_KEY or "",
        
        "triage_model": FrameworkConfig._TRIAGE_MODEL,
        "triage_temp": FrameworkConfig._TRIAGE_TEMP,
        "triage_max_tokens": FrameworkConfig._TRIAGE_MAX_TOKENS,
        "triage_use_system": FrameworkConfig._TRIAGE_USE_SYSTEM,
        "triage_reasoning": FrameworkConfig._TRIAGE_REASONING,
        
        "router_model": FrameworkConfig._ROUTER_MODEL,
        "router_temp": FrameworkConfig._ROUTER_TEMP,
        "router_max_tokens": FrameworkConfig._ROUTER_MAX_TOKENS,
        "router_use_system": FrameworkConfig._ROUTER_USE_SYSTEM,
        "router_reasoning": FrameworkConfig._ROUTER_REASONING,
        
        "general_model": FrameworkConfig._GENERAL_MODEL,
        "general_temp": FrameworkConfig._GENERAL_TEMP,
        "general_max_tokens": FrameworkConfig._GENERAL_MAX_TOKENS,
        "general_use_system": FrameworkConfig._GENERAL_USE_SYSTEM,
        "general_reasoning": FrameworkConfig._GENERAL_REASONING,
        "general_instructions": FrameworkConfig._GENERAL_INSTRUCTIONS,
        
        "reasoning_model": FrameworkConfig._REASONING_MODEL,
        "reasoning_temp": FrameworkConfig._REASONING_TEMP,
        "reasoning_max_tokens": FrameworkConfig._REASONING_MAX_TOKENS,
        "reasoning_use_system": FrameworkConfig._REASONING_USE_SYSTEM,
        "reasoning_reasoning": FrameworkConfig._REASONING_REASONING,
        "reasoning_instructions": FrameworkConfig._REASONING_INSTRUCTIONS,
        
        "casual_model": FrameworkConfig._CASUAL_MODEL,
        "casual_temp": FrameworkConfig._CASUAL_TEMP,
        "casual_max_tokens": FrameworkConfig._CASUAL_MAX_TOKENS,
        "casual_use_system": FrameworkConfig._CASUAL_USE_SYSTEM,
        "casual_reasoning": FrameworkConfig._CASUAL_REASONING,
        "casual_instructions": FrameworkConfig._CASUAL_INSTRUCTIONS,
        "triage_instructions": FrameworkConfig._TRIAGE_INSTRUCTIONS,
    })

@app.route('/api/config', methods=['POST'])
def save_config():
    data = request.json
    
    # Update active memory immediately
    FrameworkConfig._update_settings_(
        api_key=data.get('api_key', FrameworkConfig._API_KEY),
        
        triage_model=data.get('triage_model', FrameworkConfig._TRIAGE_MODEL),
        triage_temp=float(data.get('triage_temp', FrameworkConfig._TRIAGE_TEMP)),
        triage_max_tokens=int(data.get('triage_max_tokens', FrameworkConfig._TRIAGE_MAX_TOKENS)),
        triage_use_system=bool(data.get('triage_use_system', FrameworkConfig._TRIAGE_USE_SYSTEM)),
        triage_reasoning=bool(data.get('triage_reasoning', FrameworkConfig._TRIAGE_REASONING)),
        
        router_model=data.get('router_model', FrameworkConfig._ROUTER_MODEL),
        router_temp=float(data.get('router_temp', FrameworkConfig._ROUTER_TEMP)),
        router_max_tokens=int(data.get('router_max_tokens', FrameworkConfig._ROUTER_MAX_TOKENS)),
        router_use_system=bool(data.get('router_use_system', FrameworkConfig._ROUTER_USE_SYSTEM)),
        router_reasoning=bool(data.get('router_reasoning', FrameworkConfig._ROUTER_REASONING)),
        
        general_model=data.get('general_model', FrameworkConfig._GENERAL_MODEL),
        general_temp=float(data.get('general_temp', FrameworkConfig._GENERAL_TEMP)),
        general_max_tokens=int(data.get('general_max_tokens', FrameworkConfig._GENERAL_MAX_TOKENS)),
        general_use_system=bool(data.get('general_use_system', FrameworkConfig._GENERAL_USE_SYSTEM)),
        general_reasoning=bool(data.get('general_reasoning', FrameworkConfig._GENERAL_REASONING)),
        general_instructions=data.get('general_instructions', FrameworkConfig._GENERAL_INSTRUCTIONS),
        
        reasoning_model=data.get('reasoning_model', FrameworkConfig._REASONING_MODEL),
        reasoning_temp=float(data.get('reasoning_temp', FrameworkConfig._REASONING_TEMP)),
        reasoning_max_tokens=int(data.get('reasoning_max_tokens', FrameworkConfig._REASONING_MAX_TOKENS)),
        reasoning_use_system=bool(data.get('reasoning_use_system', FrameworkConfig._REASONING_USE_SYSTEM)),
        reasoning_reasoning=bool(data.get('reasoning_reasoning', FrameworkConfig._REASONING_REASONING)),
        reasoning_instructions=data.get('reasoning_instructions', FrameworkConfig._REASONING_INSTRUCTIONS),
        
        casual_model=data.get('casual_model', FrameworkConfig._CASUAL_MODEL),
        casual_temp=float(data.get('casual_temp', FrameworkConfig._CASUAL_TEMP)),
        casual_max_tokens=int(data.get('casual_max_tokens', FrameworkConfig._CASUAL_MAX_TOKENS)),
        casual_use_system=bool(data.get('casual_use_system', FrameworkConfig._CASUAL_USE_SYSTEM)),
        casual_reasoning=bool(data.get('casual_reasoning', FrameworkConfig._CASUAL_REASONING)),
        casual_instructions=data.get('casual_instructions', FrameworkConfig._CASUAL_INSTRUCTIONS),
        triage_instructions=data.get('triage_instructions', FrameworkConfig._TRIAGE_INSTRUCTIONS),
    )
    
    from dotenv import set_key
    import os
    env_file = os.path.join(os.getcwd(), ".env")
    
    # Save standard properties to env
    set_key(env_file, "OPENROUTER_API_KEY", FrameworkConfig._API_KEY or "")
    
    set_key(env_file, "TRIAGE_MODEL", FrameworkConfig._TRIAGE_MODEL)
    set_key(env_file, "TRIAGE_TEMP", str(FrameworkConfig._TRIAGE_TEMP))
    set_key(env_file, "TRIAGE_MAX_TOKENS", str(FrameworkConfig._TRIAGE_MAX_TOKENS))
    set_key(env_file, "TRIAGE_USE_SYSTEM", str(FrameworkConfig._TRIAGE_USE_SYSTEM))
    set_key(env_file, "TRIAGE_REASONING", str(FrameworkConfig._TRIAGE_REASONING))
    
    set_key(env_file, "ROUTER_MODEL", FrameworkConfig._ROUTER_MODEL)
    set_key(env_file, "ROUTER_TEMP", str(FrameworkConfig._ROUTER_TEMP))
    set_key(env_file, "ROUTER_MAX_TOKENS", str(FrameworkConfig._ROUTER_MAX_TOKENS))
    set_key(env_file, "ROUTER_USE_SYSTEM", str(FrameworkConfig._ROUTER_USE_SYSTEM))
    set_key(env_file, "ROUTER_REASONING", str(FrameworkConfig._ROUTER_REASONING))
    
    set_key(env_file, "GENERAL_MODEL", FrameworkConfig._GENERAL_MODEL)
    set_key(env_file, "GENERAL_TEMP", str(FrameworkConfig._GENERAL_TEMP))
    set_key(env_file, "GENERAL_MAX_TOKENS", str(FrameworkConfig._GENERAL_MAX_TOKENS))
    set_key(env_file, "GENERAL_USE_SYSTEM", str(FrameworkConfig._GENERAL_USE_SYSTEM))
    set_key(env_file, "GENERAL_REASONING", str(FrameworkConfig._GENERAL_REASONING))
    # Multiline instructions are hard to safely set_key dynamically depending on shell, but we can try representing them with single line escaping,
    # or just rely on memory for this session. It's safer to not persist giant multi-line system prompts via dotenv set_key to avoid corrupting .env files.
    
    set_key(env_file, "REASONING_MODEL", FrameworkConfig._REASONING_MODEL)
    set_key(env_file, "REASONING_TEMP", str(FrameworkConfig._REASONING_TEMP))
    set_key(env_file, "REASONING_MAX_TOKENS", str(FrameworkConfig._REASONING_MAX_TOKENS))
    set_key(env_file, "REASONING_USE_SYSTEM", str(FrameworkConfig._REASONING_USE_SYSTEM))
    set_key(env_file, "REASONING_REASONING", str(FrameworkConfig._REASONING_REASONING))
    
    set_key(env_file, "CASUAL_MODEL", FrameworkConfig._CASUAL_MODEL)
    set_key(env_file, "CASUAL_TEMP", str(FrameworkConfig._CASUAL_TEMP))
    set_key(env_file, "CASUAL_MAX_TOKENS", str(FrameworkConfig._CASUAL_MAX_TOKENS))
    set_key(env_file, "CASUAL_USE_SYSTEM", str(FrameworkConfig._CASUAL_USE_SYSTEM))
    set_key(env_file, "CASUAL_REASONING", str(FrameworkConfig._CASUAL_REASONING))
    
    return json.dumps({"status": "success", "message": "Configuration updated successfully."})

if __name__ == '__main__':
    app.run(debug=True, port=5220)
