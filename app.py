import os
import json
import time
import uuid
from flask import Flask, render_template, request, Response, stream_with_context
from dotenv import load_dotenv
from src.adaptive_routing import FrameworkConfig, TriageModule, SemanticRouterModule, LegalRetrievalModule
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
        # --- Authentication ---
        api_key=os.getenv("OPENROUTER_API_KEY", ""),

        #--- Triage Module (Normalization) ---
        triage_model="z-ai/glm-4.5-air:free",
        triage_temp=0.4,
        triage_max_tokens=1500,
        triage_use_system=True,
        triage_reasoning=False,

        # --- Semantic Router (Classification) ---
        router_model="z-ai/glm-4.5-air:free",
        router_temp=0.0,
        router_max_tokens=1000,
        router_use_system=True,
        router_reasoning=False,

        # --- Legal Generator: General Information ---
        general_model="z-ai/glm-4.5-air:free",
        general_temp=0.6,
        general_max_tokens=1000,
        general_use_system=True,
        general_reasoning=False,

        # --- Legal Generator: Reasoning/Advice ---
        reasoning_model="nvidia/nemotron-3-nano-30b-a3b:free",
        reasoning_temp=0.7,
        reasoning_max_tokens=2000,
        reasoning_use_system=True,
        reasoning_reasoning=False,

        # --- Casual Conversation (Greetings, Thanks, Small Talk) ---
        casual_model="liquid/lfm-2.5-1.2b-instruct:free",
        casual_temp=0.8,
        casual_max_tokens=200,
        casual_use_system=True,
        casual_reasoning=False,
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
except Exception as e:
    print(f">>> Error initializing modules: {e}")
    triage_module = None
    router_module = None
    retrieval_module = None

# In-memory session storage
# Format: { "session_id": { "route": "...", "history": [...] } }
SESSIONS = {}

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
                SESSIONS[session_id] = {"history": []}
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
                    "Language": detected_language,
                    "Normalized Text": normalized_text
                }
            }) + "\n"

            if not normalized_text:
                yield json.dumps({"type": "error", "content": "Normalization failed. Input text unclear."}) + "\n"
                return

            # 3. Classification Step (with persistence for rate-limits)
            yield json.dumps({"type": "step", "content": "Routing query to appropriate model..."}) + "\n"
            classification = {"route": "General-LLM", "confidence": 0.0, "trigger_signals": []}
            
            if router_module:
                for attempt in range(1, MAX_RETRIES + 1):
                    try:
                        classification = router_module._process_routing_(normalized_text)
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
            
            yield json.dumps({
                "type": "data",
                "title": "Routing Result",
                "data": {
                    "Route": route,
                    "Confidence": confidence
                }
            }) + "\n"

            # 4. RAG Retrieval (skip for Casual routes)
            context_str = None
            if route != "Casual-LLM":
                yield json.dumps({"type": "step", "content": "Retrieving relevant legal context..."}) + "\n"
                
                if retrieval_module:
                    try:
                        retrieval_output = retrieval_module._process_retrieval_(normalized_text)
                        retrieved_chunks = retrieval_output.get("retrieved_chunks", [])
                        
                        if retrieved_chunks:
                            yield json.dumps({
                                "type": "rag_context",
                                "title": "Legal Sources Retrieved",
                                "chunks": [{
                                    "text": chunk.get("chunk", ""), 
                                    "metadata": chunk.get("metadata", {}), 
                                    "score": float(chunk.get("score", 0.0))
                                } for chunk in retrieved_chunks[:3]]
                            }) + "\n"
                            context_str = "\n".join([c.get("chunk", "") for c in retrieved_chunks])
                        else:
                            yield json.dumps({"type": "step", "content": "No relevant context found..."}) + "\n"
                    except Exception as rag_err:
                        print(f"RAG retrieval error: {rag_err}")
                        yield json.dumps({"type": "step", "content": "Retrieval omitted (fallback applied)..."}) + "\n"
            else:
                yield json.dumps({"type": "step", "content": "Casual conversation detected — skipping legal retrieval..."}) + "\n"

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
                            limits=0.6
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

if __name__ == '__main__':
    app.run(debug=True, port=5220)
