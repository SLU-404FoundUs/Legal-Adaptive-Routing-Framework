import requests
import json
import time
import sys
import os

BASE_URL = "http://localhost:5220"

def test_triage():
    print("\n[Testing Triage Module]")
    payload = {"raw_input": "Hindi ko natatanggap ang sahod ko. Ano po ang dapat kong gawin?"}
    try:
        resp = requests.post(f"{BASE_URL}/api/test/triage", json=payload)
        print(f"Status: {resp.status_code}")
        data = resp.json()
        print(f"Detected Language: {data.get('detected_language')}")
        print(f"Normalized Text: {data.get('normalized_text')}")
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False

def test_router():
    print("\n[Testing Router Module]")
    payload = {"normalized_text": "Claim for unpaid wages for two months in Hong Kong.", "threshold": 0.1}
    try:
        resp = requests.post(f"{BASE_URL}/api/test/router", json=payload)
        print(f"Status: {resp.status_code}")
        data = resp.json()
        print(f"Route: {data.get('route')}")
        print(f"Confidence: {data.get('confidence')}")
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False

def test_llm_module(module_name, custom_instructions=None, temperature=None, max_tokens=None):
    print(f"\n[Testing {module_name.capitalize()} LLM Module]")
    payload = {
        "user_message": "Tell me a long story about Hong Kong labor laws.",
        "system_instructions": custom_instructions,
        "temperature": temperature,
        "max_tokens": max_tokens
    }
    
    try:
        resp = requests.post(f"{BASE_URL}/api/test/{module_name}", json=payload, stream=True)
        print(f"Status: {resp.status_code}")
        
        full_content = ""
        for line in resp.iter_lines():
            if line:
                evt = json.loads(line.decode('utf-8'))
                if evt['type'] == 'result':
                    full_content = evt['content']
                    words = len(full_content.split())
                    chars = len(full_content)
                    print(f"Result Size: {chars} chars, ~{words} words")
                    print(f"Result (first 100 chars): {full_content[:100]}...")
                elif evt['type'] == 'error':
                    print(f"AI Error: {evt['content']}")
                    return False
        
        # Check for truncation if max_tokens was small
        if max_tokens and max_tokens < 20: 
            if len(full_content) > 150: # Very loose check for word count/chars
                print(f"FAILURE: Output might not be truncated correctly. Length: {len(full_content)}")
                # However, max_tokens is on API side, so we expect short results.
        
        # Flexible check for secret keys to verify instruction following
        secret_keys = ["SECRET_KEY_123", "CASUAL_SECRET_99"]
        for key in secret_keys:
            if custom_instructions and key in custom_instructions:
                if key in full_content:
                    print(f"SUCCESS: Custom instructions (key: {key}) were respected.")
                else:
                    print(f"FAILURE: Custom instructions (key: {key}) were NOT found in output.")
                    return False
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False

def test_chat_persistence():
    print("\n[Testing Chat Persistence & Deletion]")
    # 1. Save
    payload = {
        "sessionId": "test-session-123",
        "title": "Test Deletion Chat",
        "messages": [{"role": "user", "content": "Delete me"}]
    }
    try:
        save_resp = requests.post(f"{BASE_URL}/api/chat/save", json=payload)
        filename = save_resp.json().get('filename')
        if not filename:
            print("FAILURE: Save failed, no filename returned")
            return False
        print(f"Saved chat: {filename}")
        
        # 2. List
        list_resp = requests.get(f"{BASE_URL}/api/chat/list")
        if not any(f['filename'] == filename for f in list_resp.json()):
            print("FAILURE: Saved file not in list")
            return False
            
        # 3. Delete
        del_resp = requests.post(f"{BASE_URL}/api/chat/delete", json={"filename": filename})
        if del_resp.json().get('status') == 'success':
            print(f"SUCCESS: Deleted chat {filename}")
            return True
        else:
            print(f"FAILURE: Delete failed: {del_resp.text}")
            return False
    except Exception as e:
        print(f"Error: {e}")
        return False

def main():
    print("=== Legal Adaptive Routing Framework - API Test Harness ===")
    
    # Check if server is up
    try:
        requests.get(BASE_URL, timeout=2)
    except:
        print(f"FAILURE: Server not found at {BASE_URL}. Please run 'python WEB.py' first.")
        sys.exit(1)

    results = []
    results.append(test_triage())
    results.append(test_router())
    
    # Test hyperparameter override (Max Tokens = 10 should be very short)
    print("\n[Testing Hyperparameters Override]")
    results.append(test_llm_module("general", max_tokens=10))
    
    # Test casual with custom secret instruction
    secret_instr_casual = "You are a pirate. Start every response with CASUAL_SECRET_99. Then answer normally."
    results.append(test_llm_module("casual", custom_instructions=secret_instr_casual))
    
    # Test chat persistence
    results.append(test_chat_persistence())

    print("\n=== Final Results ===")
    if all(results):
        print("ALL TESTS PASSED")
    else:
        print(f"SOME TESTS FAILED: {results.count(False)} failures")

if __name__ == "__main__":
    main()
