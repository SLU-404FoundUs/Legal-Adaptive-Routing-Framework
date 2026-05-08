# Safety Audit Module

The **Safety Audit Layer** evaluates the safety, compliance, and quality of LLM-generated responses before they are presented to the user. It operates using a Facade/Orchestrator pattern to separate business logic from the actual LLM evaluation process.

## Architecture & Components

The module is broken down into two primary components:

### 1. `SafetyAuditModule` (Facade Orchestrator)
Located in `__init__.py`, this class acts as the single entry point for external consumers.

**Key Responsibilities:**
- **Route-Based Skip Logic:** Bypasses the audit for low-risk routes (`Casual-LLM` is automatically `COMPLIANT`).
- **Empty Response Guarding:** Instantly flags empty or whitespace-only responses as `NON_COMPLIANT`.
- **Dynamic Strictness Resolution:** Assigns strictness thresholds dynamically from `FrameworkConfig` based on the active route.
- **Safeguarding:** Provides a standardized apology message (`_build_safeguard_message_`) when the framework exhausts maximum regeneration attempts.
- **Delegation:** Passes the evaluation task to `ResponseAuditor`.

### 2. `ResponseAuditor` (Audit Engine)
Located in `response_audit.py`, this is the pure evaluation engine that interfaces directly with the Audit LLM (e.g., Gemma 3). 

**Key Responsibilities:**
- **LLM Prompting:** Constructs the audit prompt using the user's query and the generated AI response.
- **Reasoning Stripping:** Removes `<think>...</think>` tags to ensure internal reasoning artifacts don't interfere with JSON parsing.
- **JSON Parsing:** Extracts the structured payload for the `verdict` (`PASS`/`FAIL`), `confidence`, and `explanation`.
- **Conservative Fallback:** Defaults to a safe `FAIL` verdict in the event of an API failure or parsing error.

## Strictness Configuration

The audit strictness dynamically scales based on the active route, defined in `FrameworkConfig`:

| Route Name | Strictness Tier | Audit Behavior |
| :--- | :--- | :--- |
| `Casual-LLM` | `CASUAL` | Skipped entirely (Auto-Compliant) |
| `General-LLM` | `GENERAL` | Evaluated using standard audit parameters |
| `Reasoning-LLM` | `REASONING` | Evaluated using advanced/strict audit parameters |

## Operational Workflow

1. **Input Generation:** A response is generated for a user query via a designated route.
2. **Facade Entry:** `SafetyAuditModule._run_audit_()` is invoked.
3. **Pre-Checks:** Evaluates skip conditions (casual route) and structural integrity (empty response).
4. **Delegation:** `ResponseAuditor._evaluate_()` is called to perform the actual check.
5. **Deep Audit:** The auditor prompts the model, scrubs reasoning blocks, and parses the evaluation.
6. **Verdict Mapping:** The raw `PASS`/`FAIL` is mapped to a `COMPLIANT`/`NON_COMPLIANT` verdict, along with the strictness threshold.
7. **Safeguard Resolution:** If the response is `NON_COMPLIANT` and all retry attempts are exhausted, the fallback message is returned.
