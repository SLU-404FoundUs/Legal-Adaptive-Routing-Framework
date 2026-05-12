## Saint Louis University
## Team 404FoundUs
## @file WEB.py
## @project_ LLM Legal Adaptive Routing Framework
## @desc_ AI Studio web interface (Flask) for the Legal Adaptive Routing Framework.
## @deps os, json, time, uuid, datetime, logging, queue, threading, flask, dotenv, src.adaptive_routing

import os
import json
import time
import uuid
import logging
import queue
import threading
from datetime import datetime
from flask import Flask, render_template, request, Response, stream_with_context, send_file, jsonify
from dotenv import load_dotenv
from src.adaptive_routing import FrameworkConfig, TriageModule, SemanticRouterModule, LegalRetrievalModule, SafetyAuditModule
from src.adaptive_routing.modules.legal_retrieval.utils import legal_indexing
import platform

def get_config_dir():
    home = os.path.expanduser("~")
    if platform.system() == "Windows":
        return os.path.join(home, "AppData", "Local", "LARF")
    elif platform.system() == "Darwin":
        return os.path.join(home, "Library", "Application Support", "LARF")
    else:
        return os.path.join(home, ".config", "LARF")

CONFIG_DIR = get_config_dir()
os.makedirs(CONFIG_DIR, exist_ok=True)
ENV_FILE = os.path.join(CONFIG_DIR, "config.env")

# Fallback for development (local .env), but override with the global config.env
load_dotenv(dotenv_path=".env")
load_dotenv(dotenv_path=ENV_FILE, override=True)

# --- Log Capture for SSE Streaming ---
class QueueLogHandler(logging.Handler):
    """Custom logging handler that pushes log records into a thread-safe queue
    for real-time streaming to the browser via SSE."""
    def __init__(self):
        super().__init__()
        self.log_queue = queue.Queue(maxsize=2000)
        self.formatter = logging.Formatter('[%(asctime)s] %(levelname)s — %(name)s — %(message)s', datefmt='%H:%M:%S')
    
    def emit(self, record):
        try:
            msg = self.format(record)
            if self.log_queue.full():
                try:
                    self.log_queue.get_nowait()
                except queue.Empty:
                    pass
            self.log_queue.put_nowait({
                "timestamp": datetime.now().strftime('%H:%M:%S'),
                "level": record.levelname,
                "message": msg
            })
        except Exception:
            self.handleError(record)

# Install global log handler
log_handler = QueueLogHandler()
log_handler.setLevel(logging.DEBUG)

# Attach to root logger to capture all library output
root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)
root_logger.addHandler(log_handler)

# Also capture print-style output via a custom logger
app_logger = logging.getLogger("agapay.studio")
app_logger.setLevel(logging.DEBUG)

# --- Retry Configuration ---
MAX_RETRIES = 5
BASE_DELAY = 2  # seconds

def _is_rate_limited_(error):
    """Check if an exception is a 429 rate-limit error."""
    err_str = str(error).lower()
    return "429" in err_str or "rate" in err_str or "rate-limited" in err_str or "too many requests" in err_str

import sys
if getattr(sys, 'frozen', False):
    template_folder = os.path.join(sys._MEIPASS, 'templates')
    static_folder = os.path.join(sys._MEIPASS, 'static')
    app = Flask(__name__, template_folder=template_folder, static_folder=static_folder)
else:
    app = Flask(__name__)

# --- Directories ---
CONVERSATIONS_DIR = os.path.join(CONFIG_DIR, "localfiles", "conversations")
os.makedirs(CONVERSATIONS_DIR, exist_ok=True)

# --- Configuration ---
FrameworkConfig._update_settings_(
        api_key=os.getenv("OPENROUTER_API_KEY", "")
    )

# Initialize Modules
triage_module = None
router_module = None
retrieval_module = None
safety_audit = None

def initialize_ai_modules(status_callback=None):
    global triage_module, router_module, retrieval_module, safety_audit
    try:
        if status_callback: status_callback("Initializing Triage Module...")
        triage_module = TriageModule()
        if status_callback: status_callback("Initializing Router Module...")
        router_module = SemanticRouterModule()
        if status_callback: status_callback("Initializing Retrieval Module...")
        retrieval_module = LegalRetrievalModule()
        
        # Check and Build Initial FAISS Index if missing
        index_dir = os.path.join(CONFIG_DIR, "localfiles", "legal-basis")
        index_file = os.path.join(index_dir, "combined_index.faiss")
        chunks_file = os.path.join(index_dir, "combined_index.json")
        corpus_path = os.path.join(CONFIG_DIR, "legal-corpus")
        
        if os.path.exists(index_file) and os.path.exists(chunks_file):
            app_logger.info("Loading existing FAISS index...")
            if status_callback: status_callback("Loading FAISS Index...")
            retrieval_module._load_index_(index_file, chunks_file)
        else:
            if not os.path.exists(corpus_path):
                msg = f"Missing 'legal-corpus' folder. Please place it inside: {CONFIG_DIR}"
                app_logger.warning(msg)
                if status_callback: status_callback(f"⚠️ {msg}")
                raise Exception("legal-corpus directory not found.")
                
            app_logger.info("Building initial FAISS index for all jurisdictions (this may take a while)...")
            if status_callback: status_callback("Building FAISS Index (This may take several minutes)...")
            os.makedirs(index_dir, exist_ok=True)
            retrieval_module.build_and_save_index(
                corpus_dir=corpus_path,
                output_dir=index_dir,
                index_prefix="combined_index"
            )
            app_logger.info("FAISS index built and saved successfully.")
            
        # Initialize Safety Audit Module
        if status_callback: status_callback("Initializing Safety Audit Module...")
        if FrameworkConfig._VERIFICATION_ENABLED:
            try:
                safety_audit = SafetyAuditModule()
                app_logger.info(f"Safety Audit Module loaded — persistence={FrameworkConfig._VERIFICATION_PERSISTENCE}")
            except Exception as audit_init_err:
                app_logger.warning(f"Safety Audit Module failed to initialize (non-fatal): {audit_init_err}")
        else:
            app_logger.info("Safety Audit Module is disabled via VERIFICATION_ENABLED=False.")

        app_logger.info("Modules initialized successfully.")
        
        # Check sync status on startup
        if status_callback: status_callback("Verifying Index Integrity...")
        sync_info = legal_indexing.verify_index_integrity(
            corpus_dir=corpus_path,
            chunks_path=chunks_file
        )
        if not sync_info["is_synced"]:
            app_logger.warning(f"Index is out of sync. {sync_info['missing_count']} documents missing.")
        else:
            app_logger.info("Index is fully synced with corpus.")

    except Exception as e:
        app_logger.error(f"Error initializing modules: {e}")
        if status_callback: status_callback(f"Error initializing modules: {e}")


# In-memory session storage
# Format: { "session_id": { "route": "...", "history": [...] } }
SESSIONS = {}

# =============================================
# Core Routes
# =============================================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/sync-status', methods=['GET'])
def get_sync_status():
    """Check if the vector index is up to date with the legal corpus."""
    try:
        index_dir = os.path.join(os.getcwd(), "localfiles", "legal-basis")
        chunks_file = os.path.join(index_dir, "combined_index.json")
        
        logging.info(f"Sync status requested. Checking integrity: {chunks_file}")
        sync_info = legal_indexing.verify_index_integrity(
            corpus_dir="legal-corpus",
            chunks_path=chunks_file
        )
        logging.info(f"Sync status result: {sync_info['is_synced']} ({sync_info['corpus_count']} docs)")
        return jsonify(sync_info)
    except Exception as e:
        logging.error(f"Sync status error: {str(e)}")
        return jsonify({"error": str(e)}), 500

# =============================================
# Chat API
# =============================================

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
                            app_logger.warning(f"Triage rate-limited (attempt {attempt}/{MAX_RETRIES}), retrying in {delay}s...")
                            yield json.dumps({"type": "step", "content": f"Rate-limited — retrying triage ({attempt}/{MAX_RETRIES})..."}) + "\n"
                            time.sleep(delay)
                        else:
                            app_logger.error(f"Triage failed after {attempt} attempt(s): {triage_err}")
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
                # Pass recent history (last 5 turns) for context-aware routing
                routing_history = history[-5:] if history else None
                
                for attempt in range(1, MAX_RETRIES + 1):
                    try:
                        classification = router_module._process_routing_(
                            normalized_text, 
                            history=routing_history,
                            threshold=0.1
                        )
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
                            app_logger.warning(f"Classification rate-limited (attempt {attempt}/{MAX_RETRIES}), retrying in {delay}s...")
                            yield json.dumps({"type": "step", "content": f"Rate-limited — retrying classification ({attempt}/{MAX_RETRIES})..."}) + "\n"
                            time.sleep(delay)
                        else:
                            app_logger.error(f"Classification failed after {attempt} attempt(s): {classify_err}")
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
                    yield json.dumps({"type": "step", "content": "Retrieving context via Hybrid Search (BM25 + Semantic) → Cascade Reranking..."}) + "\n"
                    
                    if retrieval_module:
                        try:
                            retrieval_output = retrieval_module._process_retrieval_(normalized_text, signals=signals)
                            retrieved_chunks = retrieval_output.get("retrieved_chunks", [])
                            dominant_corpus = retrieval_output.get("dominant_corpus")
                            reranked_best = retrieval_output.get("reranked_best")
                            
                            if retrieved_chunks:
                                # Surface reranking cascade metadata
                                if dominant_corpus:
                                    yield json.dumps({"type": "step", "content": f"Reranker dominant corpus: {dominant_corpus}"}) + "\n"
                                
                                yield json.dumps({
                                    "type": "rag_context",
                                    "title": "Legal Sources Retrieved",
                                    "chunks": [{
                                        "text": chunk.get("chunk", ""), 
                                        "metadata": chunk.get("metadata", {}), 
                                        "score": float(chunk.get("score", 0.0)),
                                        "source": chunk.get("source", "Unknown")
                                    } for chunk in retrieved_chunks[:5]]
                                }) + "\n"
                                context_str = "\n".join([c.get("chunk", "") for c in retrieved_chunks])
                                SESSIONS[session_id]["last_rag_context"] = context_str
                            else:
                                yield json.dumps({"type": "step", "content": "No relevant context found..."}) + "\n"
                                SESSIONS[session_id]["last_rag_context"] = None
                                context_str = None
                        except Exception as rag_err:
                            app_logger.error(f"RAG retrieval error: {rag_err}")
                            yield json.dumps({"type": "step", "content": "Retrieval omitted (fallback applied)..."}) + "\n"
                else:
                    if context_str:
                        yield json.dumps({"type": "step", "content": "Follow-up detected — Reusing previous legal context."}) + "\n"
                    else:
                        yield json.dumps({"type": "step", "content": "Follow-up detected — No previous context available."}) + "\n"
            else:
                yield json.dumps({"type": "step", "content": "Casual conversation detected — skipping legal retrieval..."}) + "\n"
                context_str = None

            # 5. Generation + Adherence Audit Loop
            yield json.dumps({"type": "step", "content": "Generating response..."}) + "\n"
            
            # Add the user's clean message to history before generation
            history.append({"role": "user", "content": normalized_text})
            
            response_text = ""
            audit_passed = False
            persistence_limit = FrameworkConfig._VERIFICATION_PERSISTENCE if safety_audit else 1
            is_follow_up = (signals is None and route != "Casual-LLM")

            for audit_attempt in range(1, persistence_limit + 1):
                # 5a. Generate (with existing rate-limit retries)
                if router_module:
                    for attempt in range(1, MAX_RETRIES + 1):
                        try:
                            result = router_module._generate_conversation_(
                                classification=classification,
                                messages=history,
                                context=context_str,
                                is_follow_up=is_follow_up,
                                detected_language=detected_language
                            )
                            response_text = result.get("response_text", "")
                            accepted = result.get("accepted", False)
                            
                            if not accepted:
                                yield json.dumps({"type": "step", "content": "Confidence below threshold — requesting clarification..."}) + "\n"
                            break
                        except Exception as gen_err:
                            if _is_rate_limited_(gen_err) and attempt < MAX_RETRIES:
                                delay = BASE_DELAY * attempt
                                app_logger.warning(f"Generation rate-limited (attempt {attempt}/{MAX_RETRIES}), retrying in {delay}s...")
                                yield json.dumps({"type": "step", "content": f"Rate-limited — retrying generation ({attempt}/{MAX_RETRIES})..."}) + "\n"
                                time.sleep(delay)
                            else:
                                app_logger.error(f"Generation failed after {attempt} attempt(s): {gen_err}")
                                response_text = "I am currently unable to process your query due to a technical error. Please try again."
                                break
                else:
                    response_text = "I am currently unable to process your query due to a technical error."

                # 5b. Safety Audit (skip for Casual routes or if audit module disabled)
                if not safety_audit or route == "Casual-LLM" or not response_text:
                    audit_passed = True
                    break

                yield json.dumps({"type": "step", "content": f"Running safety audit (attempt {audit_attempt}/{persistence_limit})..."}) + "\n"
                
                audit_result = safety_audit._run_audit_(
                    normalized_query=normalized_text,
                    response_text=response_text,
                    route=route,
                    history=history[-5:] if history else None
                )
                
                # Resolve strictness label for the frontend
                strictness_val = audit_result.get("strictness", 0.50)
                if strictness_val < 0.40:
                    strictness_label = "LOW"
                elif strictness_val >= 0.60:
                    strictness_label = "HIGH"
                else:
                    strictness_label = "MEDIUM"
                
                # Stream audit metadata to frontend
                yield json.dumps({
                    "type": "verification",
                    "attempt": audit_attempt,
                    "persistence": persistence_limit,
                    "verdict": audit_result.get("verdict"),
                    "confidence": audit_result.get("confidence"),
                    "explanation": audit_result.get("explanation"),
                    "strictness": strictness_val,
                    "strictness_label": strictness_label,
                    "route": audit_result.get("route")
                }) + "\n"
                
                if audit_result.get("verdict") == "COMPLIANT":
                    audit_passed = True
                    break
                else:
                    # Remove failed response from history before regeneration
                    if history and history[-1].get("role") == "assistant":
                        history.pop()
                    
                    if audit_attempt < persistence_limit:
                        app_logger.warning(
                            f"Safety audit NON_COMPLIANT (attempt {audit_attempt}/{persistence_limit}, "
                            f"confidence={audit_result.get('confidence')}) — regenerating..."
                        )
                        yield json.dumps({"type": "step", "content": f"Response did not meet safety standards — regenerating ({audit_attempt}/{persistence_limit})..."}) + "\n"
                    else:
                        app_logger.warning(
                            f"Safety audit exhausted all {persistence_limit} attempts. Applying safeguard."
                        )
                        yield json.dumps({"type": "step", "content": "All generation attempts exhausted — applying safeguard..."}) + "\n"

            # 6. Finalize response
            if audit_passed and response_text:
                history.append({"role": "assistant", "content": response_text})
                SESSIONS[session_id]["route"] = route
                yield json.dumps({"type": "result", "content": response_text, "route": route}) + "\n"
            elif not audit_passed and safety_audit:
                safeguard_msg = safety_audit._build_safeguard_message_()
                history.append({"role": "assistant", "content": safeguard_msg})
                SESSIONS[session_id]["route"] = route
                yield json.dumps({"type": "result", "content": safeguard_msg, "route": route}) + "\n"
            elif response_text:
                history.append({"role": "assistant", "content": response_text})
                SESSIONS[session_id]["route"] = route
                yield json.dumps({"type": "result", "content": response_text, "route": route}) + "\n"
            else:
                yield json.dumps({"type": "error", "content": "No response generated."}) + "\n"

        except Exception as e:
            yield json.dumps({"type": "error", "content": f"Server Error: {str(e)}"}) + "\n"
            app_logger.error(f"Error processing request: {e}")

    return Response(stream_with_context(generate()), mimetype='application/x-ndjson')

# =============================================
# Conversation Persistence API
# =============================================

@app.route('/api/chat/save', methods=['POST'])
def save_conversation():
    """Save current chat session to a JSON file."""
    data = request.json
    session_id = data.get('sessionId')
    messages = data.get('messages', [])
    title = data.get('title', 'Untitled Conversation')
    
    if not messages:
        return jsonify({"error": "No messages to save"}), 400
    
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    filename = f"{timestamp}.json"
    filepath = os.path.join(CONVERSATIONS_DIR, filename)
    
    conversation_data = {
        "session_id": session_id or str(uuid.uuid4()),
        "title": title,
        "timestamp": datetime.now().isoformat(),
        "message_count": len(messages),
        "messages": messages
    }
    
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(conversation_data, f, indent=2, ensure_ascii=False)
        app_logger.info(f"Conversation saved: {filename}")
        return jsonify({"status": "success", "filename": filename, "path": filepath})
    except Exception as e:
        app_logger.error(f"Failed to save conversation: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/chat/list', methods=['GET'])
def list_conversations():
    """List all saved conversation files."""
    try:
        files = []
        for f in sorted(os.listdir(CONVERSATIONS_DIR), reverse=True):
            if f.endswith('.json'):
                filepath = os.path.join(CONVERSATIONS_DIR, f)
                try:
                    with open(filepath, 'r', encoding='utf-8') as fh:
                        data = json.load(fh)
                    files.append({
                        "filename": f,
                        "title": data.get("title", "Untitled"),
                        "timestamp": data.get("timestamp", ""),
                        "message_count": data.get("message_count", 0)
                    })
                except Exception:
                    files.append({"filename": f, "title": f, "timestamp": "", "message_count": 0})
        return jsonify(files)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/chat/load', methods=['POST'])
def load_conversation():
    """Load a conversation from a JSON file."""
    # Support both filename-based and file-upload loading
    if request.content_type and 'multipart/form-data' in request.content_type:
        # File upload
        file = request.files.get('file')
        if not file:
            return jsonify({"error": "No file provided"}), 400
        try:
            data = json.load(file)
            return jsonify(data)
        except Exception as e:
            return jsonify({"error": f"Invalid JSON file: {str(e)}"}), 400
    else:
        # Filename-based
        data = request.json
        filename = data.get('filename')
        if not filename:
            return jsonify({"error": "No filename provided"}), 400
        
        filepath = os.path.join(CONVERSATIONS_DIR, filename)
        if not os.path.exists(filepath):
            return jsonify({"error": "File not found"}), 404
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                conversation = json.load(f)
            return jsonify(conversation)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

@app.route('/api/chat/delete', methods=['POST'])
def delete_conversation():
    """Delete a saved conversation JSON file."""
    data = request.json
    filename = data.get('filename')
    if not filename:
        return jsonify({"error": "No filename provided"}), 400
    
    filepath = os.path.join(CONVERSATIONS_DIR, filename)
    if not os.path.exists(filepath):
        return jsonify({"error": "File not found"}), 404
        
    try:
        os.remove(filepath)
        app_logger.info(f"Conversation deleted: {filename}")
        return jsonify({"status": "success"})
    except Exception as e:
        app_logger.error(f"Failed to delete conversation: {e}")
        return jsonify({"error": str(e)}), 500

# =============================================
# Configuration API
# =============================================

@app.route('/api/config', methods=['GET'])
def get_config():
    return json.dumps({
        "api_key": FrameworkConfig._API_KEY or "",
        
        "triage_model": FrameworkConfig._TRIAGE_MODEL,
        "triage_temp": FrameworkConfig._TRIAGE_TEMP,
        "triage_max_tokens": FrameworkConfig._TRIAGE_MAX_TOKENS,
        "triage_use_system": FrameworkConfig._TRIAGE_USE_SYSTEM,
        "triage_reasoning": FrameworkConfig._TRIAGE_REASONING,
        "triage_reasoning_effort": FrameworkConfig._TRIAGE_REASONING_EFFORT,
        "triage_instructions": FrameworkConfig._TRIAGE_INSTRUCTIONS,
        
        "router_model": FrameworkConfig._ROUTER_MODEL,
        "router_temp": FrameworkConfig._ROUTER_TEMP,
        "router_max_tokens": FrameworkConfig._ROUTER_MAX_TOKENS,
        "router_use_system": FrameworkConfig._ROUTER_USE_SYSTEM,
        "router_reasoning": FrameworkConfig._ROUTER_REASONING,
        "router_instructions": FrameworkConfig._ROUTER_INSTRUCTIONS,
        
        "general_model": FrameworkConfig._GENERAL_MODEL,
        "general_temp": FrameworkConfig._GENERAL_TEMP,
        "general_max_tokens": FrameworkConfig._GENERAL_MAX_TOKENS,
        "general_use_system": FrameworkConfig._GENERAL_USE_SYSTEM,
        "general_reasoning": FrameworkConfig._GENERAL_REASONING,
        "general_reasoning_effort": FrameworkConfig._GENERAL_REASONING_EFFORT,
        "general_instructions": FrameworkConfig._GENERAL_INSTRUCTIONS,
        
        "reasoning_model": FrameworkConfig._REASONING_MODEL,
        "reasoning_temp": FrameworkConfig._REASONING_TEMP,
        "reasoning_max_tokens": FrameworkConfig._REASONING_MAX_TOKENS,
        "reasoning_use_system": FrameworkConfig._REASONING_USE_SYSTEM,
        "reasoning_reasoning": FrameworkConfig._REASONING_REASONING,
        "reasoning_reasoning_effort": FrameworkConfig._REASONING_REASONING_EFFORT,
        "reasoning_instructions": FrameworkConfig._REASONING_INSTRUCTIONS,
        
        "casual_model": FrameworkConfig._CASUAL_MODEL,
        "casual_temp": FrameworkConfig._CASUAL_TEMP,
        "casual_max_tokens": FrameworkConfig._CASUAL_MAX_TOKENS,
        "casual_use_system": FrameworkConfig._CASUAL_USE_SYSTEM,
        "casual_reasoning": FrameworkConfig._CASUAL_REASONING,
        "casual_reasoning_effort": FrameworkConfig._CASUAL_REASONING_EFFORT,
        "casual_instructions": FrameworkConfig._CASUAL_INSTRUCTIONS,

        "verification_enabled": FrameworkConfig._VERIFICATION_ENABLED,
        "verification_strictness_casual": FrameworkConfig._VERIFICATION_STRICTNESS_CASUAL,
        "verification_strictness_general": FrameworkConfig._VERIFICATION_STRICTNESS_GENERAL,
        "verification_strictness_reasoning": FrameworkConfig._VERIFICATION_STRICTNESS_REASONING,
        "verification_deep_audit_temp": FrameworkConfig._VERIFICATION_DEEP_AUDIT_TEMP,
        "verification_reasoning": FrameworkConfig._VERIFICATION_REASONING,
        "verification_reasoning_effort": FrameworkConfig._VERIFICATION_REASONING_EFFORT,
        "verification_instructions": FrameworkConfig._VERIFICATION_INSTRUCTIONS,
    })

@app.route('/api/config', methods=['POST'])
def save_config():
    global triage_module, router_module, retrieval_module, safety_audit
    data = request.json
    
    try:
        # Update active memory immediately
        FrameworkConfig._update_settings_(
            api_key=data.get('api_key', FrameworkConfig._API_KEY),
            
            triage_model=data.get('triage_model', FrameworkConfig._TRIAGE_MODEL),
            triage_temp=float(data.get('triage_temp', FrameworkConfig._TRIAGE_TEMP)),
            triage_max_tokens=int(data.get('triage_max_tokens', FrameworkConfig._TRIAGE_MAX_TOKENS)),
            triage_use_system=data.get('triage_use_system', FrameworkConfig._TRIAGE_USE_SYSTEM),
            triage_reasoning=data.get('triage_reasoning', FrameworkConfig._TRIAGE_REASONING),
            triage_reasoning_effort=data.get('triage_reasoning_effort', FrameworkConfig._TRIAGE_REASONING_EFFORT),
            triage_instructions=data.get('triage_instructions', FrameworkConfig._TRIAGE_INSTRUCTIONS),
            
            router_model=data.get('router_model', FrameworkConfig._ROUTER_MODEL),
            router_temp=float(data.get('router_temp', FrameworkConfig._ROUTER_TEMP)),
            router_max_tokens=int(data.get('router_max_tokens', FrameworkConfig._ROUTER_MAX_TOKENS)),
            router_use_system=data.get('router_use_system', FrameworkConfig._ROUTER_USE_SYSTEM),
            router_reasoning=data.get('router_reasoning', FrameworkConfig._ROUTER_REASONING),
            router_reasoning_effort=data.get('router_reasoning_effort', FrameworkConfig._ROUTER_REASONING_EFFORT),
            router_instructions=data.get('router_instructions', FrameworkConfig._ROUTER_INSTRUCTIONS),
            
            general_model=data.get('general_model', FrameworkConfig._GENERAL_MODEL),
            general_temp=float(data.get('general_temp', FrameworkConfig._GENERAL_TEMP)),
            general_max_tokens=int(data.get('general_max_tokens', FrameworkConfig._GENERAL_MAX_TOKENS)),
            general_use_system=data.get('general_use_system', FrameworkConfig._GENERAL_USE_SYSTEM),
            general_reasoning=data.get('general_reasoning', FrameworkConfig._GENERAL_REASONING),
            general_reasoning_effort=data.get('general_reasoning_effort', FrameworkConfig._GENERAL_REASONING_EFFORT),
            general_instructions=data.get('general_instructions', FrameworkConfig._GENERAL_INSTRUCTIONS),
            
            reasoning_model=data.get('reasoning_model', FrameworkConfig._REASONING_MODEL),
            reasoning_temp=float(data.get('reasoning_temp', FrameworkConfig._REASONING_TEMP)),
            reasoning_max_tokens=int(data.get('reasoning_max_tokens', FrameworkConfig._REASONING_MAX_TOKENS)),
            reasoning_use_system=data.get('reasoning_use_system', FrameworkConfig._REASONING_USE_SYSTEM),
            reasoning_reasoning=data.get('reasoning_reasoning', FrameworkConfig._REASONING_REASONING),
            reasoning_reasoning_effort=data.get('reasoning_reasoning_effort', FrameworkConfig._REASONING_REASONING_EFFORT),
            reasoning_instructions=data.get('reasoning_instructions', FrameworkConfig._REASONING_INSTRUCTIONS),
            
            casual_model=data.get('casual_model', FrameworkConfig._CASUAL_MODEL),
            casual_temp=float(data.get('casual_temp', FrameworkConfig._CASUAL_TEMP)),
            casual_max_tokens=int(data.get('casual_max_tokens', FrameworkConfig._CASUAL_MAX_TOKENS)),
            casual_use_system=data.get('casual_use_system', FrameworkConfig._CASUAL_USE_SYSTEM),
            casual_reasoning=data.get('casual_reasoning', FrameworkConfig._CASUAL_REASONING),
            casual_reasoning_effort=data.get('casual_reasoning_effort', FrameworkConfig._CASUAL_REASONING_EFFORT),
            casual_instructions=data.get('casual_instructions', FrameworkConfig._CASUAL_INSTRUCTIONS),

            verification_enabled=data.get('verification_enabled', FrameworkConfig._VERIFICATION_ENABLED),
            verification_strictness_casual=float(data.get('verification_strictness_casual', FrameworkConfig._VERIFICATION_STRICTNESS_CASUAL)),
            verification_strictness_general=float(data.get('verification_strictness_general', FrameworkConfig._VERIFICATION_STRICTNESS_GENERAL)),
            verification_strictness_reasoning=float(data.get('verification_strictness_reasoning', FrameworkConfig._VERIFICATION_STRICTNESS_REASONING)),
            verification_deep_audit_temp=float(data.get('verification_deep_audit_temp', FrameworkConfig._VERIFICATION_DEEP_AUDIT_TEMP)),
            verification_reasoning=data.get('verification_reasoning', FrameworkConfig._VERIFICATION_REASONING),
            verification_reasoning_effort=data.get('verification_reasoning_effort', FrameworkConfig._VERIFICATION_REASONING_EFFORT),
            verification_instructions=data.get('verification_instructions', FrameworkConfig._VERIFICATION_INSTRUCTIONS),
        )
        
        from dotenv import set_key
        env_file = ENV_FILE
        
        # Save standard properties to env
        set_key(env_file, "OPENROUTER_API_KEY", FrameworkConfig._API_KEY or "")
        
        set_key(env_file, "TRIAGE_MODEL", FrameworkConfig._TRIAGE_MODEL)
        set_key(env_file, "TRIAGE_TEMP", str(FrameworkConfig._TRIAGE_TEMP))
        set_key(env_file, "TRIAGE_MAX_TOKENS", str(FrameworkConfig._TRIAGE_MAX_TOKENS))
        set_key(env_file, "TRIAGE_USE_SYSTEM", str(FrameworkConfig._TRIAGE_USE_SYSTEM))
        set_key(env_file, "TRIAGE_REASONING", str(FrameworkConfig._TRIAGE_REASONING))
        set_key(env_file, "TRIAGE_REASONING_EFFORT", FrameworkConfig._TRIAGE_REASONING_EFFORT)
        set_key(env_file, "TRIAGE_INSTRUCTIONS", FrameworkConfig._TRIAGE_INSTRUCTIONS)
        
        set_key(env_file, "ROUTER_MODEL", FrameworkConfig._ROUTER_MODEL)
        set_key(env_file, "ROUTER_TEMP", str(FrameworkConfig._ROUTER_TEMP))
        set_key(env_file, "ROUTER_MAX_TOKENS", str(FrameworkConfig._ROUTER_MAX_TOKENS))
        set_key(env_file, "ROUTER_USE_SYSTEM", str(FrameworkConfig._ROUTER_USE_SYSTEM))
        set_key(env_file, "ROUTER_REASONING", str(FrameworkConfig._ROUTER_REASONING))
        set_key(env_file, "ROUTER_REASONING_EFFORT", FrameworkConfig._ROUTER_REASONING_EFFORT)
        set_key(env_file, "ROUTER_INSTRUCTIONS", FrameworkConfig._ROUTER_INSTRUCTIONS)
        
        set_key(env_file, "GENERAL_MODEL", FrameworkConfig._GENERAL_MODEL)
        set_key(env_file, "GENERAL_TEMP", str(FrameworkConfig._GENERAL_TEMP))
        set_key(env_file, "GENERAL_MAX_TOKENS", str(FrameworkConfig._GENERAL_MAX_TOKENS))
        set_key(env_file, "GENERAL_USE_SYSTEM", str(FrameworkConfig._GENERAL_USE_SYSTEM))
        set_key(env_file, "GENERAL_REASONING", str(FrameworkConfig._GENERAL_REASONING))
        set_key(env_file, "GENERAL_REASONING_EFFORT", FrameworkConfig._GENERAL_REASONING_EFFORT)
        set_key(env_file, "GENERAL_INSTRUCTIONS", FrameworkConfig._GENERAL_INSTRUCTIONS)
        
        set_key(env_file, "REASONING_MODEL", FrameworkConfig._REASONING_MODEL)
        set_key(env_file, "REASONING_TEMP", str(FrameworkConfig._REASONING_TEMP))
        set_key(env_file, "REASONING_MAX_TOKENS", str(FrameworkConfig._REASONING_MAX_TOKENS))
        set_key(env_file, "REASONING_USE_SYSTEM", str(FrameworkConfig._REASONING_USE_SYSTEM))
        set_key(env_file, "REASONING_REASONING", str(FrameworkConfig._REASONING_REASONING))
        set_key(env_file, "REASONING_REASONING_EFFORT", FrameworkConfig._REASONING_REASONING_EFFORT)
        set_key(env_file, "REASONING_INSTRUCTIONS", FrameworkConfig._REASONING_INSTRUCTIONS)
        
        set_key(env_file, "CASUAL_MODEL", FrameworkConfig._CASUAL_MODEL)
        set_key(env_file, "CASUAL_TEMP", str(FrameworkConfig._CASUAL_TEMP))
        set_key(env_file, "CASUAL_MAX_TOKENS", str(FrameworkConfig._CASUAL_MAX_TOKENS))
        set_key(env_file, "CASUAL_USE_SYSTEM", str(FrameworkConfig._CASUAL_USE_SYSTEM))
        set_key(env_file, "CASUAL_REASONING", str(FrameworkConfig._CASUAL_REASONING))
        set_key(env_file, "CASUAL_REASONING_EFFORT", FrameworkConfig._CASUAL_REASONING_EFFORT)
        set_key(env_file, "CASUAL_INSTRUCTIONS", FrameworkConfig._CASUAL_INSTRUCTIONS)
        
        set_key(env_file, "VERIFICATION_ENABLED", str(FrameworkConfig._VERIFICATION_ENABLED))
        set_key(env_file, "VERIFICATION_STRICTNESS_CASUAL", str(FrameworkConfig._VERIFICATION_STRICTNESS_CASUAL))
        set_key(env_file, "VERIFICATION_STRICTNESS_GENERAL", str(FrameworkConfig._VERIFICATION_STRICTNESS_GENERAL))
        set_key(env_file, "VERIFICATION_STRICTNESS_REASONING", str(FrameworkConfig._VERIFICATION_STRICTNESS_REASONING))
        set_key(env_file, "VERIFICATION_DEEP_AUDIT_TEMP", str(FrameworkConfig._VERIFICATION_DEEP_AUDIT_TEMP))
        set_key(env_file, "VERIFICATION_REASONING", str(FrameworkConfig._VERIFICATION_REASONING))
        set_key(env_file, "VERIFICATION_REASONING_EFFORT", FrameworkConfig._VERIFICATION_REASONING_EFFORT)
        set_key(env_file, "VERIFICATION_INSTRUCTIONS", FrameworkConfig._VERIFICATION_INSTRUCTIONS)
        
        # Re-initialize modules to pick up changes immediately
        triage_module = TriageModule()
        router_module = SemanticRouterModule()
        
        # Retrieval module reload (re-use existing index if possible to avoid rebuild delay)
        index_dir = os.path.join(os.getcwd(), "localfiles", "legal-basis")
        index_file = os.path.join(index_dir, "combined_index.faiss")
        chunks_file = os.path.join(index_dir, "combined_index.json")
        
        retrieval_module = LegalRetrievalModule()
        if os.path.exists(index_file) and os.path.exists(chunks_file):
            retrieval_module._load_index_(index_file, chunks_file)
        
        # Re-initialize Safety Audit Module with new settings
        if FrameworkConfig._VERIFICATION_ENABLED:
            try:
                safety_audit = SafetyAuditModule()
                app_logger.info("Safety Audit Module re-initialized with updated config.")
            except Exception as audit_reinit_err:
                app_logger.warning(f"Safety Audit Module re-init failed (non-fatal): {audit_reinit_err}")
                safety_audit = None
        else:
            safety_audit = None
            
        app_logger.info("Configuration updated, saved to .env, and modules re-initialized.")
        return json.dumps({"status": "success", "message": "Configuration updated successfully."})
        
    except Exception as e:
        app_logger.error(f"Error saving configuration: {e}")
        return json.dumps({"status": "error", "message": str(e)}), 500

@app.route('/api/config/export', methods=['GET'])
def export_config():
    """Export current configuration as a downloadable .config file."""
    config_data = {
        "framework": "Legal-Adaptive-Routing-Framework",
        "version": "1.0",
        "exported_at": datetime.now().isoformat(),
        "config": {
            "triage": {
                "model": FrameworkConfig._TRIAGE_MODEL,
                "temp": FrameworkConfig._TRIAGE_TEMP,
                "max_tokens": FrameworkConfig._TRIAGE_MAX_TOKENS,
                "use_system": FrameworkConfig._TRIAGE_USE_SYSTEM,
                "reasoning": FrameworkConfig._TRIAGE_REASONING,
                "reasoning_effort": FrameworkConfig._TRIAGE_REASONING_EFFORT,
                "instructions": FrameworkConfig._TRIAGE_INSTRUCTIONS,
            },
            "router": {
                "model": FrameworkConfig._ROUTER_MODEL,
                "temp": FrameworkConfig._ROUTER_TEMP,
                "max_tokens": FrameworkConfig._ROUTER_MAX_TOKENS,
                "use_system": FrameworkConfig._ROUTER_USE_SYSTEM,
                "reasoning": FrameworkConfig._ROUTER_REASONING,
                "reasoning_effort": FrameworkConfig._ROUTER_REASONING_EFFORT,
                "instructions": FrameworkConfig._ROUTER_INSTRUCTIONS,
            },
            "general": {
                "model": FrameworkConfig._GENERAL_MODEL,
                "temp": FrameworkConfig._GENERAL_TEMP,
                "max_tokens": FrameworkConfig._GENERAL_MAX_TOKENS,
                "use_system": FrameworkConfig._GENERAL_USE_SYSTEM,
                "reasoning": FrameworkConfig._GENERAL_REASONING,
                "reasoning_effort": FrameworkConfig._GENERAL_REASONING_EFFORT,
                "instructions": FrameworkConfig._GENERAL_INSTRUCTIONS,
            },
            "reasoning": {
                "model": FrameworkConfig._REASONING_MODEL,
                "temp": FrameworkConfig._REASONING_TEMP,
                "max_tokens": FrameworkConfig._REASONING_MAX_TOKENS,
                "use_system": FrameworkConfig._REASONING_USE_SYSTEM,
                "reasoning": FrameworkConfig._REASONING_REASONING,
                "reasoning_effort": FrameworkConfig._REASONING_REASONING_EFFORT,
                "instructions": FrameworkConfig._REASONING_INSTRUCTIONS,
            },
            "casual": {
                "model": FrameworkConfig._CASUAL_MODEL,
                "temp": FrameworkConfig._CASUAL_TEMP,
                "max_tokens": FrameworkConfig._CASUAL_MAX_TOKENS,
                "use_system": FrameworkConfig._CASUAL_USE_SYSTEM,
                "reasoning": FrameworkConfig._CASUAL_REASONING,
                "reasoning_effort": FrameworkConfig._CASUAL_REASONING_EFFORT,
                "instructions": FrameworkConfig._CASUAL_INSTRUCTIONS,
            }
        }
    }
    
    timestamp = datetime.now().strftime('%Y-%m-%d')
    filename = f"agapay_config_{timestamp}.config"
    filepath = os.path.join(os.getcwd(), "localfiles", filename)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(config_data, f, indent=2, ensure_ascii=False)
    
    app_logger.info(f"Configuration exported: {filename}")
    return send_file(filepath, as_attachment=True, download_name=filename, mimetype='application/json')

@app.route('/api/debug/config', methods=['GET'])
def debug_config():
    """Diagnostic endpoint to verify shared configuration state."""
    from src.adaptive_routing.modules.triage import FrameworkConfig as TriageFC
    from src.adaptive_routing.modules.router import FrameworkConfig as RouterFC
    from src.adaptive_routing.modules.semantic_router.legal_generation import FrameworkConfig as GenFC
    
    return jsonify({
        "web_config_id": id(FrameworkConfig),
        "triage_config_id": id(TriageFC),
        "router_config_id": id(RouterFC),
        "generation_config_id": id(GenFC),
        "ids_match": len({id(FrameworkConfig), id(TriageFC), id(RouterFC), id(GenFC)}) == 1,
        "current_reasoning_instructions": FrameworkConfig._REASONING_INSTRUCTIONS[:100] + "...",
        "env_reasoning_instructions": os.getenv("REASONING_INSTRUCTIONS", "NOT SET")[:100] + "..."
    })

@app.route('/api/config/import', methods=['POST'])
def import_config():
    """Import configuration from a .config file."""
    file = request.files.get('file')
    if not file:
        return jsonify({"error": "No file provided"}), 400
    
    try:
        config_data = json.load(file)
        cfg = config_data.get("config", {})
        
        update_kwargs = {}
        
        # Map nested config structure to flat kwargs
        module_map = {
            "triage": ["model", "temp", "max_tokens", "use_system", "reasoning", "instructions"],
            "router": ["model", "temp", "max_tokens", "use_system", "reasoning", "instructions"],
            "general": ["model", "temp", "max_tokens", "use_system", "reasoning", "instructions"],
            "reasoning": ["model", "temp", "max_tokens", "use_system", "reasoning", "instructions"],
            "casual": ["model", "temp", "max_tokens", "use_system", "reasoning", "instructions"],
        }
        
        for module, fields in module_map.items():
            if module in cfg:
                for field in fields:
                    if field in cfg[module]:
                        key = f"{module}_{field}"
                        val = cfg[module][field]
                        # Type coerce
                        if field == "temp":
                            val = float(val)
                        elif field == "max_tokens":
                            val = int(val)
                        elif field in ("use_system", "reasoning"):
                            val = bool(val)
                        update_kwargs[key] = val
        
        if update_kwargs:
            FrameworkConfig._update_settings_(**update_kwargs)
            app_logger.info(f"Configuration imported: {len(update_kwargs)} settings applied")
        
        return jsonify({"status": "success", "applied": len(update_kwargs)})
    except Exception as e:
        app_logger.error(f"Config import failed: {e}")
        return jsonify({"error": str(e)}), 400

# =============================================
# Live Logs SSE Endpoint
# =============================================

@app.route('/api/logs', methods=['GET'])
def stream_logs():
    """SSE endpoint that streams log output to the browser in real-time."""
    def generate():
        yield "data: {\"type\":\"connected\",\"message\":\"Log stream connected\"}\n\n"
        while True:
            try:
                log_entry = log_handler.log_queue.get(timeout=2)
                yield f"data: {json.dumps(log_entry)}\n\n"
            except queue.Empty:
                # Send heartbeat to keep connection alive
                yield ": heartbeat\n\n"
    
    return Response(stream_with_context(generate()), mimetype='text/event-stream', headers={
        'Cache-Control': 'no-cache',
        'X-Accel-Buffering': 'no'
    })

# =============================================
# Module Test Page
# =============================================

VALID_TEST_MODULES = {"triage", "router", "general", "reasoning", "casual", "retrieval"}

@app.route('/test/<module_name>')
def test_module_page(module_name):
    """Serve the dedicated per-module test harness page."""
    if module_name not in VALID_TEST_MODULES:
        return "Unknown module", 404
    return render_template('test.html', module=module_name)

# =============================================
# Individual Module Test API Endpoints
# =============================================

@app.route('/api/test/triage', methods=['POST'])
def api_test_triage():
    """Test the Triage Module: normalizes raw multilingual input."""
    data = request.json
    raw_input = data.get('raw_input', '').strip()
    system_instructions = data.get('system_instructions', None)
    temperature = data.get('temperature', None)
    max_tokens = data.get('max_tokens', None)
    reasoning_effort = data.get('reasoning_effort', None)
    model = data.get('model', None)

    if not raw_input:
        return jsonify({"error": "raw_input is required"}), 400
    if not triage_module:
        return jsonify({"error": "Triage module is not initialized"}), 500
    try:
        if temperature is not None or max_tokens is not None or reasoning_effort is not None or model is not None:
            from src.adaptive_routing.core.engine import LLMRequestEngine
            from src.adaptive_routing.modules.triage import TriageModule
            from src.adaptive_routing.modules.multihead_classifier.linguistic import LinguisticNormalizer
            
            engine = LLMRequestEngine(
                api_key=FrameworkConfig._API_KEY,
                model=model if model is not None else FrameworkConfig._TRIAGE_MODEL,
                temperature=float(temperature) if temperature is not None else FrameworkConfig._TRIAGE_TEMP,
                max_tokens=int(max_tokens) if max_tokens is not None else FrameworkConfig._TRIAGE_MAX_TOKENS,
                use_system_role=FrameworkConfig._TRIAGE_USE_SYSTEM,
                include_reasoning=FrameworkConfig._TRIAGE_REASONING,
                reasoning_effort=reasoning_effort if reasoning_effort is not None else FrameworkConfig._TRIAGE_REASONING_EFFORT
            )
            normalizer = LinguisticNormalizer(engine=engine)
            test_triage_module = TriageModule(engine=engine, normalizer=normalizer)
            result = test_triage_module._process_request_(raw_input, system_instructions=system_instructions)
            result["model_used"] = engine._model
        else:
            result = triage_module._process_request_(raw_input, system_instructions=system_instructions)
            result["model_used"] = triage_module._engine._model
        return jsonify(result)
    except Exception as e:
        app_logger.error(f"[Test/Triage] Error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/test/router', methods=['POST'])
def api_test_router():
    """Test the Router Module: classifies normalized text into a route."""
    data = request.json
    normalized_text = data.get('normalized_text', '').strip()
    threshold = float(data.get('threshold', 0.1))
    model = data.get('model', None)
    system_instructions = data.get('system_instructions', None)

    if not normalized_text:
        return jsonify({"error": "normalized_text is required"}), 400
    if not router_module:
        return jsonify({"error": "Router module is not initialized"}), 500
    try:
        if model is not None or system_instructions is not None:
            from src.adaptive_routing.core.engine import LLMRequestEngine
            from src.adaptive_routing.modules.semantic_router.logic_classifier import RoutingClassifier
            from src.adaptive_routing.modules.router import SemanticRouterModule
            
            engine = LLMRequestEngine(
                api_key=FrameworkConfig._API_KEY,
                model=model if model else FrameworkConfig._ROUTER_MODEL,
                temperature=FrameworkConfig._ROUTER_TEMP,
                max_tokens=FrameworkConfig._ROUTER_MAX_TOKENS,
                use_system_role=FrameworkConfig._ROUTER_USE_SYSTEM,
                include_reasoning=FrameworkConfig._ROUTER_REASONING,
                reasoning_effort=FrameworkConfig._ROUTER_REASONING_EFFORT
            )
            classifier = RoutingClassifier(handler=engine, system_prompt=system_instructions)
            test_router_module = SemanticRouterModule(classifier=classifier)
            result = test_router_module._process_routing_(normalized_text, threshold=threshold)
            if hasattr(test_router_module, '_classifier') and hasattr(test_router_module._classifier, '_handler'):
                result['model_used'] = test_router_module._classifier._handler._model
        else:
            result = router_module._process_routing_(normalized_text, threshold=threshold)
            if hasattr(router_module, '_classifier') and hasattr(router_module._classifier, '_handler'):
                result['model_used'] = router_module._classifier._handler._model
        return jsonify(result)
    except Exception as e:
        app_logger.error(f"[Test/Router] Error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/test/retrieval', methods=['POST'])
def api_test_retrieval():
    """Test the Legal Retrieval Module: returns RAG chunks for a query."""
    data = request.json
    query = data.get('query', '').strip()
    signals_raw = data.get('signals', '')
    top_k = int(data.get('top_k', 5))
    if not query:
        return jsonify({"error": "query is required"}), 400
    if not retrieval_module:
        return jsonify({"error": "Retrieval module is not initialized"}), 500
    try:
        signals = [s.strip() for s in signals_raw.split(',') if s.strip()] if signals_raw else None
        result = retrieval_module._process_retrieval_(query, signals=signals, top_k=top_k)
        chunks = result.get("retrieved_chunks", [])
        return jsonify({
            "query": result.get("query", query),
            "combined_query": result.get("combined_query", query),
            "chunk_count": len(chunks),
            "dominant_corpus": result.get("dominant_corpus"),
            "reranked_best": result.get("reranked_best"),
            "model_used": retrieval_module._embedding_manager._model if hasattr(retrieval_module, '_embedding_manager') else 'Unknown Embedding Model',
            "rerank_model": FrameworkConfig._RETRIEVAL_RERANK_MODEL,
            "chunks": [
                {
                    "text": c.get("chunk", ""),
                    "metadata": c.get("metadata", {}),
                    "score": float(c.get("score", 0.0)),
                    "source": c.get("source", "Unknown")
                }
                for c in chunks
            ]
        })
    except Exception as e:
        app_logger.error(f"[Test/Retrieval] Error: {e}")
        return jsonify({"error": str(e)}), 500


def _stream_llm_test(module_name, system_instructions, user_message, rag_context=None, temperature=None, max_tokens=None, reasoning_effort=None, model=None):
    """
    Shared generator for LLM module test streaming.
    Temporarily overrides FrameworkConfig instructions, creates a fresh
    SemanticRouterModule instance, runs generation, and restores config.
    """
    route_map = {
        "general": "General-LLM",
        "reasoning": "Reasoning-LLM",
        "casual": "Casual-LLM",
    }
    instr_attr_map = {
        "general": "_GENERAL_INSTRUCTIONS",
        "reasoning": "_REASONING_INSTRUCTIONS",
        "casual": "_CASUAL_INSTRUCTIONS",
    }
    from src.adaptive_routing.core.engine import LLMRequestEngine
    from src.adaptive_routing.modules.semantic_router.legal_generation import LegalGenerator
    from src.adaptive_routing.modules.semantic_router.logic_classifier import RoutingClassifier

    # Map module types to their config prefixes in FrameworkConfig
    config_prefix_map = {
        "general": "GENERAL",
        "reasoning": "REASONING",
        "casual": "CASUAL",
    }
    
    prefix = config_prefix_map.get(module_name)
    route = route_map.get(module_name, "General-LLM")
    prefix = route.split("-")[0].upper()

    try:
        yield json.dumps({"type": "step", "content": f"Initializing isolated {module_name.capitalize()} LLM engine..."}) + "\n"

        # 1. Build an isolated engine using current config + user-specific overrides
        # We fetch current snapshot values from FrameworkConfig
        engine = LLMRequestEngine(
            api_key=FrameworkConfig._API_KEY,
            model=model if model is not None else getattr(FrameworkConfig, f"_{prefix}_MODEL"),
            temperature=float(temperature) if temperature is not None else getattr(FrameworkConfig, f"_{prefix}_TEMP"),
            max_tokens=int(max_tokens) if max_tokens is not None else getattr(FrameworkConfig, f"_{prefix}_MAX_TOKENS"),
            use_system_role=getattr(FrameworkConfig, f"_{prefix}_USE_SYSTEM"),
            include_reasoning=getattr(FrameworkConfig, f"_{prefix}_REASONING"),
            reasoning_effort=reasoning_effort if reasoning_effort is not None else getattr(FrameworkConfig, f"_{prefix}_REASONING_EFFORT", "medium")
        )

        # 2. Use the system instructions provided in the test UI, or fall back to config
        active_instructions = system_instructions if system_instructions is not None else getattr(FrameworkConfig, f"_{prefix}_INSTRUCTIONS")

        # 3. Create an isolated generator for this test run
        # We inject our specific engine into the appropriate slot
        engine_kwargs = {f"{module_name}_engine": engine}
        test_generator = LegalGenerator(api_key=FrameworkConfig._API_KEY, **engine_kwargs)
        
        # 4. Create an isolated module instance with the test generator
        test_router_mod = SemanticRouterModule(generator=test_generator)

        yield json.dumps({"type": "step", "content": "Sending request to isolated module..."}) + "\n"

        classification = {"route": route, "confidence": 1.0, "search_signals": None}
        messages = [{"role": "user", "content": user_message}]

        # Unified generation logic for all routes
        # We prepare the final content (optionally with RAG context)
        final_user_content = user_message
        if rag_context and route != "Casual-LLM":
            # Inject context into the user message using the framework's builder logic
            final_user_content = test_router_mod._build_augmented_query_(user_message, rag_context, route)
        
        # We call the engine directly with the isolated instructions
        # This bypasses the global FrameworkConfig fallback in LegalGenerator
        response_text = engine._get_chat_completion_([
            {"role": "system", "content": active_instructions},
            {"role": "user", "content": final_user_content}
        ])

        yield json.dumps({"type": "result", "content": response_text, "route": route, "model_used": engine._model}) + "\n"

    except Exception as e:
        app_logger.error(f"[Test/{module_name}] Error: {e}")
        yield json.dumps({"type": "error", "content": str(e)}) + "\n"


@app.route('/api/test/general', methods=['POST'])
def api_test_general():
    """Test the General LLM module with optional custom instructions and RAG context."""
    data = request.json
    user_message = data.get('user_message', '').strip()
    system_instructions = data.get('system_instructions', None)
    rag_context = data.get('rag_context', None)
    temperature = data.get('temperature', None)
    max_tokens = data.get('max_tokens', None)
    reasoning_effort = data.get('reasoning_effort', None)
    model = data.get('model', None)
    
    if not user_message:
        return Response(json.dumps({"type": "error", "content": "user_message is required"}) + "\n",
                        mimetype='application/x-ndjson', status=400)
    return Response(
        stream_with_context(_stream_llm_test("general", system_instructions, user_message, rag_context, temperature, max_tokens, reasoning_effort, model)),
        mimetype='application/x-ndjson'
    )


@app.route('/api/test/reasoning', methods=['POST'])
def api_test_reasoning():
    """Test the Reasoning LLM module with optional custom instructions and RAG context."""
    data = request.json
    user_message = data.get('user_message', '').strip()
    system_instructions = data.get('system_instructions', None)
    rag_context = data.get('rag_context', None)
    temperature = data.get('temperature', None)
    max_tokens = data.get('max_tokens', None)
    reasoning_effort = data.get('reasoning_effort', None)
    model = data.get('model', None)

    if not user_message:
        return Response(json.dumps({"type": "error", "content": "user_message is required"}) + "\n",
                        mimetype='application/x-ndjson', status=400)
    return Response(
        stream_with_context(_stream_llm_test("reasoning", system_instructions, user_message, rag_context, temperature, max_tokens, reasoning_effort, model)),
        mimetype='application/x-ndjson'
    )


@app.route('/api/test/casual', methods=['POST'])
def api_test_casual():
    """Test the Casual LLM module with optional custom instructions and no RAG context."""
    data = request.json
    user_message = data.get('user_message', '').strip()
    system_instructions = data.get('system_instructions', None)
    temperature = data.get('temperature', None)
    max_tokens = data.get('max_tokens', None)
    reasoning_effort = data.get('reasoning_effort', None)
    model = data.get('model', None)

    if not user_message:
        return Response(json.dumps({"type": "error", "content": "user_message is required"}) + "\n",
                        mimetype='application/x-ndjson', status=400)
    return Response(
        stream_with_context(_stream_llm_test("casual", system_instructions, user_message, None, temperature, max_tokens, reasoning_effort, model)),
        mimetype='application/x-ndjson'
    )


if __name__ == '__main__':
    import threading
    import webbrowser
    import tkinter as tk
    from tkinter import ttk
    import sys

    def get_ip():
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # This doesn't need to be reachable
            s.connect(('10.255.255.255', 1))
            IP = s.getsockname()[0]
        except Exception:
            IP = '127.0.0.1'
        finally:
            s.close()
        return IP

    local_ip = get_ip()
    port = 5220
    
    # --- Setup Tkinter GUI ---
    root = tk.Tk()
    root.title("Agapay Studio Server")
    root.geometry("450x300")
    
    # Modern Minimalistic Styling
    BG_COLOR = "#0D1117"
    TEXT_COLOR = "#C9D1D9"
    ACCENT_COLOR = "#58A6FF"
    MUTED_COLOR = "#8B949E"
    FONT_FAMILY = "Helvetica Neue"
    
    root.configure(bg=BG_COLOR)
    root.eval('tk::PlaceWindow . center')
    
    # Header
    header = tk.Label(root, text="AGAPAY STUDIO", font=(FONT_FAMILY, 20, "bold"), bg=BG_COLOR, fg="#FFFFFF")
    header.pack(pady=(30, 5))
    
    # Status display
    status_var = tk.StringVar()
    status_var.set("Starting up...")
    status_label = tk.Label(root, textvariable=status_var, font=(FONT_FAMILY, 11), bg=BG_COLOR, fg=MUTED_COLOR)
    status_label.pack(pady=(0, 20))

    local_url = f"http://127.0.0.1:{port}"
    network_url = f"http://{local_ip}:{port}"
    
    def open_browser(url):
        webbrowser.open(url)
        
    frame = tk.Frame(root, bg=BG_COLOR)
    frame.pack(pady=10)
    
    # Local IP display
    tk.Label(frame, text="LOCAL", font=(FONT_FAMILY, 11, "bold"), bg=BG_COLOR, fg=MUTED_COLOR).grid(row=0, column=0, sticky="e", padx=(10, 15), pady=8)
    local_link = tk.Label(frame, text=local_url, font=(FONT_FAMILY, 12), bg=BG_COLOR, fg=ACCENT_COLOR, cursor="hand2")
    local_link.grid(row=0, column=1, sticky="w", padx=10, pady=8)
    local_link.bind("<Button-1>", lambda e: open_browser(local_url))
    
    # Network IP display
    tk.Label(frame, text="NETWORK", font=(FONT_FAMILY, 11, "bold"), bg=BG_COLOR, fg=MUTED_COLOR).grid(row=1, column=0, sticky="e", padx=(10, 15), pady=8)
    network_link = tk.Label(frame, text=network_url, font=(FONT_FAMILY, 12), bg=BG_COLOR, fg=ACCENT_COLOR, cursor="hand2")
    network_link.grid(row=1, column=1, sticky="w", padx=10, pady=8)
    network_link.bind("<Button-1>", lambda e: open_browser(network_url))
    
    def stop_server():
        root.destroy()
        sys.exit(0)
        
    # Custom modern flat button using Label for cross-platform consistency
    def on_enter(e):
        btn_label.config(bg='#F85149', fg='#FFFFFF')
    def on_leave(e):
        btn_label.config(bg='#21262D', fg=TEXT_COLOR)

    btn_label = tk.Label(root, text="STOP SERVER", font=(FONT_FAMILY, 11, "bold"), 
                         bg="#21262D", fg=TEXT_COLOR, padx=20, pady=10, cursor="hand2")
    btn_label.pack(pady=25)
    btn_label.bind("<Enter>", on_enter)
    btn_label.bind("<Leave>", on_leave)
    btn_label.bind("<Button-1>", lambda e: stop_server())
    
    def update_status(message):
        root.after(0, lambda: status_var.set(message))

    # Run Flask in a background thread to allow Tkinter to use the main thread
    def run_flask():
        # Initialize AI modules here so it doesn't block Tkinter UI
        initialize_ai_modules(status_callback=update_status)
        update_status("Server Running! ✅")
        # Important: reloader must be disabled when running in a background thread
        app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()

    # Handle window close button (X)
    root.protocol("WM_DELETE_WINDOW", stop_server)
    
    root.mainloop()

