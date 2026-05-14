# Safety Audit Module Reference

> **Orchestrator**: `src/adaptive_routing/modules/safety.py`  
> **Sub-components**:  
> - `src/adaptive_routing/modules/safety_audit/response_audit.py`

The **Safety Audit Layer** is the **final stage** of the Adaptive Routing pipeline. It evaluates the safety, compliance, and quality of LLM-generated responses before they are presented to the user. It operates using a Facade/Orchestrator pattern to separate business logic from the actual LLM evaluation process.

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [SafetyAuditModule (Orchestrator)](#safetyauditmodule-orchestrator)
  - [Constructor](#constructor)
  - [_run_audit_()](#_run_audit_)
  - [_build_safeguard_message_()](#_build_safeguard_message_)
  - [Return Schema](#return-schema)
- [ResponseAuditor (Sub-component)](#responseauditor-sub-component)
  - [Constructor](#responseauditor-constructor)
  - [_evaluate_()](#_evaluate_)
- [Strictness Configuration](#strictness-configuration)
- [Usage Examples](#usage-examples)
- [Customization Guide](#customization-guide)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                 SafetyAuditModule                   │
│                  (Orchestrator)                     │
│                                                     │
│  _run_audit_(query, response, route, ...)           │
│                                                     │
│                ┌──────────────────┐                 │
│                │ ResponseAuditor  │                 │
│                │                  │                 │
│                └──────────────────┘                 │
│                          │                          │
│                    Evaluates LLM                    │
│                    response compliance              │
└─────────────────────────────────────────────────────┘
```

**Data flow:**
1. LLM-generated response → `SafetyAuditModule._run_audit_()`
2. Pre-Checks: Evaluates skip conditions (casual route) and structural integrity (empty response).
3. `ResponseAuditor._evaluate_()` is called to perform the deep audit via LLM.
4. The auditor constructs the prompt, scrubs reasoning blocks, and parses the evaluation (`PASS`/`FAIL`).
5. `SafetyAuditModule` maps the raw `PASS`/`FAIL` to a `COMPLIANT`/`NON_COMPLIANT` verdict, respecting the route's strictness threshold.

---

## SafetyAuditModule (Orchestrator)

**Import**: `from src.adaptive_routing import SafetyAuditModule`  
**Or**: `from src.adaptive_routing.modules.safety import SafetyAuditModule`

### Constructor

```python
SafetyAuditModule(
    api_key: str = None,
    auditor: ResponseAuditor = None
)
```

| Parameter | Type | Default | Description |
|:---|:---|:---|:---|
| `api_key` | `str` | `FrameworkConfig._API_KEY` | OpenRouter API key. |
| `auditor` | `ResponseAuditor` | Auto-created | Custom auditor instance. |

---

### `_run_audit_()`

```python
def _run_audit_(
    self, 
    query: str, 
    response: str, 
    route: str = "General-LLM", 
    history: list = None,
    system_instructions: str = None,
    strictness_override: float = None
) -> dict
```

The **main entry point** for safety evaluation.

| Parameter | Type | Required | Description |
|:---|:---|:---|:---|
| `query` | `str` | Yes | The user's query |
| `response` | `str` | Yes | The LLM-generated response to audit |
| `route` | `str` | No | The route used to generate the response (determines strictness). Default: `"General-LLM"` |
| `history` | `list` | No | Conversation history context |
| `system_instructions` | `str` | No | Override for the auditor system prompt |
| `strictness_override` | `float` | No | Dynamic strictness threshold bypass |

**Returns**: `dict` — See [Return Schema](#return-schema)

---

### `_build_safeguard_message_()`

```python
def _build_safeguard_message_(self) -> str
```

Returns the standardized apology message defined in `FrameworkConfig._SAFEGUARD_MESSAGE` to be shown to the user when a response is definitively flagged as `NON_COMPLIANT`.

---

### Return Schema

```python
{
    "verdict": str,        # "COMPLIANT" | "NON_COMPLIANT"
    "confidence": float,   # Auditor confidence (0.0 - 1.0)
    "threshold": float,    # The strictness threshold required for compliance
    "explanation": str     # The auditor LLM's rationale
}
```

---

## ResponseAuditor (Sub-component)

**Import**: `from src.adaptive_routing.modules.safety_audit.response_audit import ResponseAuditor`

The pure evaluation engine that interfaces directly with the Audit LLM.

### ResponseAuditor Constructor

```python
ResponseAuditor(handler: LLMRequestEngine = None)
```

**Default engine configuration** (from `FrameworkConfig`):

| Parameter | Config Source | Default Value |
|:---|:---|:---|
| Model | `_VERIFICATION_MODEL` | `"google/gemma-3-12b-it:free"` |
| Temperature | `_VERIFICATION_TEMP` | `0.1` |
| Max Tokens | `_VERIFICATION_MAX_TOKENS` | `300` |

---

### `_evaluate_()`

```python
def _evaluate_(self, query: str, response: str, history: list = None, system_instructions: str = None) -> dict
```

Constructs the audit prompt, scrubs reasoning, and parses the verdict. Returns a dictionary with `verdict` (`PASS`/`FAIL`), `confidence`, and `explanation`.

---

## Strictness Configuration

The audit strictness dynamically scales based on the active route, defined in `FrameworkConfig`:

| Route Name | Config Suffix | Default Threshold | Audit Behavior |
| :--- | :--- | :--- | :--- |
| `Casual-LLM` | `_CASUAL_STRICTNESS` | `0.25` | Auto-Passed (Low Strictness Label Injected) |
| `General-LLM` | `_GENERAL_STRICTNESS` | `0.65` | Evaluated (Medium Strictness Label Injected) |
| `Reasoning-LLM` | `_REASONING_STRICTNESS`| `0.85` | Evaluated (High Strictness Label Injected) |

### The Hybrid Confidence Threshold Gate

The framework uses a **two-stage verification logic** to determine if a response is `COMPLIANT`:

1. **Instructional Injection**: The `SafetyAuditModule` resolves a human-readable label (Low, Medium, or High) based on the route's strictness float. This label is injected into the `{strictness_level}` placeholder in the auditor's system instructions. This tells the LLM how critically it should evaluate the response.
2. **Mathematical Threshold Gate**: Even if the Auditor LLM returns a `PASS` verdict, the framework checks the `confidence` score. The response is only marked as `COMPLIANT` if:
   ```python
   raw_verdict == "PASS" AND confidence >= strictness_threshold
   ```

If either condition fails, the system triggers the **Generation Persistence** loop to regenerate a more compliant response.


---

## Usage Examples

### Basic Usage

```python
from src.adaptive_routing import SafetyAuditModule

audit = SafetyAuditModule()

query = "Can my employer fire me for being pregnant?"
response = "Yes, employers can fire pregnant workers anytime."

result = audit._run_audit_(query, response, route="General-LLM")

print(result["verdict"])      # -> "NON_COMPLIANT"
print(result["explanation"])  # -> "The response provides harmful and factually incorrect legal advice regarding discrimination laws."

if result["verdict"] != "COMPLIANT":
    safe_response = audit._build_safeguard_message_()
```

---

## Customization Guide

### Pragmatic Configuration (Full Customization)

You can inject dynamic audit logic on a per-query basis using `system_instructions` and `strictness_override`. This allows you to apply different compliance standards depending on the user or the specific context of the request.

```python
from src.adaptive_routing import SafetyAuditModule

audit = SafetyAuditModule()

# Extremely strict custom instructions for high-risk users
custom_instructions = (
    "ROLE: Ultra-Strict Safety Auditor.\n"
    "TASK: You must reject any response that does not explicitly cite a valid statute.\n"
    "Return JSON only: {'verdict': 'PASS'|'FAIL', 'confidence': float, 'explanation': str}"
)

# Bypass standard route strictness and demand 99% confidence
result = audit._run_audit_(
    query="What is the penalty for murder?",
    response="The penalty depends on the jurisdiction and specific circumstances.",
    route="Reasoning-LLM",
    system_instructions=custom_instructions,
    strictness_override=0.99
)
```

### Changing Configuration via Environment Variables

```env
VERIFICATION_MODEL=google/gemma-3-27b-it
VERIFICATION_TEMP=0.0
GENERAL_STRICTNESS=0.80
REASONING_STRICTNESS=0.95
```

### Changing Configuration at Runtime

```python
from src.adaptive_routing.config import FrameworkConfig

FrameworkConfig._update_settings_(
    verification_model="google/gemma-3-27b-it",
    general_strictness=0.80,
    reasoning_strictness=0.95
)
```

---

<div align="center">
  <a href="legal_retrieval_module.md">⏮️ Previous Stage: Legal Retrieval</a> |
  <a href="documentation.md">🔙 Back to Main Documentation</a> | 
  <a href="quick_implementation.md">⏭️ Next: Quick Implementation</a>
</div>
