## Saint Louis University
## Team 404FoundUs
## @file main.py
## @project_ LLM Legal Adaptive Routing Framework
## @desc_ Main driver script to demonstrate the Triage Module functionality.
## @deps src.adaptive_routing.modules.triage, os

from src.adaptive_routing.modules.triage import TriageModule
import os

def main():
    """
    @func_ main
    @desc_ Entry point for testing the TriageModule.
    """
    print("\n--- Legal Adaptive Routing Framework: Triage Module Test ---\n")
    
    try:
        # Initialize Triage
        ## @logic_ instantiation relies on env variables loaded by FrameworkConfig
        triage = TriageModule()
        
        # Sample Input (Taglish)
        input_text = (
            "Ang Problem kasi is that my dad is terminated without notice sa kanyang work in hongkong "
            "Papaano kaya ito i solve pa help ano ang dapat na steps na gagawin ko"
        )
        
        print(f"Input: {input_text}\n")
        print("Processing...\n")
        
        result = triage._process_request_(input_text)
        
        print("--- Result ---")
        print(f"Original: {result.get('original_prompt')}")
        print(f"Detected Language: {result.get('detected_language')}")
        print(f"Normalized Text: {result.get('normalized_text')}")
        print("----------------\n")
        
    except Exception as e:
        print(f"\n[!] An error occurred: {e}")

if __name__ == "__main__":
    main()
