## Saint Louis University
## Team 404FoundUs
## @file ./main.py
## @project_ LLM Legal Adaptive Routing Framework
## @desc_ Main driver script to demonstrate the Triage Module functionality.
## @deps src.adaptive_routing.modules.triage, os

import os
import datetime
from dotenv import load_dotenv
from src.adaptive_routing import FrameworkConfig, TriageModule, SemanticRouterModule
from src.adaptive_routing.modules.semantic_router.logic_classifier import RoutingClassifier

load_dotenv()

class DualLogger:
    """Helper to log output to both console and file."""
    def __init__(self, filename="tests/run_logs.txt"):
        self.filename = filename
        
        # Ensure directory exists
        log_dir = os.path.dirname(self.filename)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)

        # Ensure log file exists or append separator
        with open(self.filename, "a", encoding="utf-8") as f:
            f.write(f"\n\n{'='*60}\n")
            f.write(f"RUN STARTED: {datetime.datetime.now()}\n")
            f.write(f"{'='*60}\n")

    def log(self, message="", end="\n"):
        """Print to console and append to file."""
        print(message, end=end)
        with open(self.filename, "a", encoding="utf-8") as f:
            f.write(f"{message}{end}")

    def section(self, title):
        """Log a section header."""
        self.log(f"\n{'-'*40}")
        self.log(f" {title}")
        self.log(f"{'-'*40}")

def main():
    """
    @func_ main
    @desc_ Entry point for testing with logging enabled.
    """
    logger = DualLogger()

    custom_system_prompt = (
        "ROLE: Prank the user say blah blah blah\n"
        "TASK: annoy the user"
    )

    FrameworkConfig._update_settings_(
        # --- Authentication ---
        api_key=os.getenv("OPENROUTER_API_KEY", ""),

        #--- Triage Module (Normalization) ---
        triage_model="google/gemma-3-4b-it:free",
        triage_temp=0.4,
        triage_max_tokens=1500,
        triage_use_system=False,
        triage_reasoning=False,

        # # --- Semantic Router (Classification) ---
        # router_model="google/gemma-3-4b-it:free",
        # router_temp=0.0,
        # router_max_tokens=1000,
        # router_use_system=False,
        # router_reasoning=False,

        # # --- Legal Generator: General Information ---
        # general_model="google/gemma-3-4b-it:free",
        # general_temp=0.5,
        # general_max_tokens=1000,
        # general_use_system=False,
        # general_reasoning=False,

        # # --- Legal Generator: Reasoning/Advice ---
        # reasoning_model="qwen/qwen3-4b:free",
        # reasoning_temp=0.7,
        # reasoning_max_tokens=2000,
        # reasoning_use_system=True,
        # reasoning_reasoning=True,
        # REASONING_INSTRUCTIONS=custom_system_prompt


        # # --- Fallbacks ---
        # default_model="qwen/qwen3-4b:free",
        # temperature=0.7,
        # max_tokens=1500
        
        # Override for testing purposes as per user request
        # REASONING_INSTRUCTIONS=custom_system_prompt
    )
    
    logger.log(">>> Configuration loaded.")
    
    # --- Initialization ---
    try:
        triage = TriageModule()
        router = SemanticRouterModule()
        
        input_text = "I want to file a case against my neighbor."

        logger.section("STEP 1: TRIAGE (Normalization)")
        logger.log(f"Input Query: \"{input_text}\"")
        
        triaged_data = triage._process_request_(input_text)
        normalized_text = triaged_data.get("normalized_text")
        detected_language = triaged_data.get("detected_language")

        logger.log(f"Detected Language: {detected_language}")
        logger.log(f"Normalized Text:   {normalized_text}")

        # --- Routing ---
        if normalized_text:
            logger.section("STEP 2: SEMANTIC ROUTING")
            
            # Note: _process_routing_ returns a dict with 'classification' and 'response_text'
            routing_output = router._process_routing_(normalized_text)
            
            classification = routing_output.get("classification", {})
            route = classification.get("route", "Unknown")
            confidence = classification.get("confidence", 0.0)
            
            logger.log(f"Selected Route: {route}")
            logger.log(f"Confidence:     {confidence}")
            
            response_text = routing_output.get("response_text")
            
            logger.section("STEP 3: GENERATED RESPONSE")
            logger.log(response_text if response_text else "(No response generated)")
            
        else:
            logger.log("[!] Scaling failed: No normalized text returned.")

    except Exception as e:
        logger.log(f"\n[!] CRITICAL ERROR: {str(e)}")
        import traceback
        with open(logger.filename, "a") as f:
            f.write(traceback.format_exc())

if __name__ == "__main__":
    main()
