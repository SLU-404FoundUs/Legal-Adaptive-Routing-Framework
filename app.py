import os
import json
import time
import uuid
from flask import Flask, render_template, request, Response, stream_with_context
from dotenv import load_dotenv
from src.adaptive_routing import FrameworkConfig, TriageModule, SemanticRouterModule
load_dotenv()



app = Flask(__name__)

# --- Configuration ---
FrameworkConfig._update_settings_(
        # --- Authentication ---
        api_key=os.getenv("OPENROUTER_API_KEY", ""),

        #--- Triage Module (Normalization) ---
        triage_model="qwen/qwen3-4b:free",
        triage_temp=0.4,
        triage_max_tokens=1500,
        triage_use_system=True,
        triage_reasoning=False,

        # --- Semantic Router (Classification) ---
        router_model="qwen/qwen3-4b:free",
        router_temp=0.0,
        router_max_tokens=1000,
        router_use_system=True,
        router_reasoning=False,

        # --- Legal Generator: General Information ---
        general_model="qwen/qwen3-4b:free",
        general_temp=0.6,
        general_max_tokens=1000,
        general_use_system=True,
        general_reasoning=False,

        # --- Legal Generator: Reasoning/Advice ---
        reasoning_model="qwen/qwen3-4b:free",
        reasoning_temp=0.7,
        reasoning_max_tokens=2000,
        reasoning_use_system=True,
        reasoning_reasoning=True,
    )

# Initialize Modules
try:
    triage_module = TriageModule()
    router_module = SemanticRouterModule()
    print(">>> Modules initialized successfully.")
except Exception as e:
    print(f">>> Error initializing modules: {e}")
    triage_module = None
    router_module = None

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
        
        if session_id and session_id in SESSIONS:
            session = SESSIONS[session_id]
            route = session["route"]
            history = session["history"]
            
            yield json.dumps({"type": "meta", "sessionId": session_id}) + "\n"
            yield json.dumps({"type": "step", "content": f"Resuming session ({route})..."}) + "\n"
            
            try:
                history.append({"role": "user", "content": user_input})
                yield json.dumps({"type": "step", "content": "Generating response..."}) + "\n"
                response_text = router_module._generator._dispatch_conversation_(history, route)
                history.append({"role": "assistant", "content": response_text})
                yield json.dumps({"type": "result", "content": response_text}) + "\n"
                
            except Exception as e:
                yield json.dumps({"type": "error", "content": f"Session Error: {str(e)}"}) + "\n"
                print(f"Error processing session request: {e}")
                
        else:
            new_session_id = str(uuid.uuid4())
            yield json.dumps({"type": "meta", "sessionId": new_session_id}) + "\n"
            
            # 1. Start Triage
            yield json.dumps({"type": "step", "content": "Initializing Triage..."}) + "\n"
            
            try:
                # --- Triage Step ---
                yield json.dumps({"type": "step", "content": "Normalizing input and detecting language..."}) + "\n"
                
                triaged_data = triage_module._process_request_(user_input)
                normalized_text = triaged_data.get("normalized_text", "")
                detected_language = triaged_data.get("detected_language", "Unknown")
                
                yield json.dumps({
                    "type": "data", 
                    "title": "Triage Result",
                    "data": {
                        "Language": detected_language,
                        "Normalized Text": normalized_text
                    }
                }) + "\n"

                # --- Routing Step ---
                if normalized_text:
                    yield json.dumps({"type": "step", "content": "Routing query to appropriate model..."}) + "\n"
                    
                    routing_output = router_module._process_routing_(normalized_text)
                    classification = routing_output.get("classification", {})
                    route = classification.get("route", "Unknown")
                    confidence = classification.get("confidence", 0.0)
                    response_text = routing_output.get("response_text")
                    
                    yield json.dumps({
                        "type": "data",
                        "title": "Routing Result",
                        "data": {
                            "Route": route,
                            "Confidence": confidence
                        }
                    }) + "\n"

                    # --- Session Initialization & Generation ---
                    if response_text:
                        system_prompt = FrameworkConfig._GENERAL_INSTRUCTIONS
                        if route == "Reasoning-LLM":
                            system_prompt = FrameworkConfig._REASONING_INSTRUCTIONS
                        history = [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": normalized_text}
                        ]
                        
                        history.append({"role": "assistant", "content": response_text})
                        
                        # Save Session
                        SESSIONS[new_session_id] = {
                            "route": route,
                            "history": history
                        }

                        yield json.dumps({"type": "step", "content": "Generating response..."}) + "\n"
                        yield json.dumps({"type": "result", "content": response_text}) + "\n"
                    else:
                         yield json.dumps({"type": "error", "content": "No response generated."}) + "\n"
                else:
                    yield json.dumps({"type": "error", "content": "Normalization failed. Input text unclear."}) + "\n"

            except Exception as e:
                yield json.dumps({"type": "error", "content": f"Server Error: {str(e)}"}) + "\n"
                print(f"Error processing request: {e}")

    return Response(stream_with_context(generate()), mimetype='application/x-ndjson')

if __name__ == '__main__':
    app.run(debug=True, port=5220)
