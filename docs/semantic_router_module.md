# Semantic Router Module Reference

> **Orchestrator**: `src/adaptive_routing/modules/router.py`  
> **Sub-components**:  
> - `src/adaptive_routing/modules/semantic_router/logic_classifier.py`  
> - `src/adaptive_routing/modules/semantic_router/legal_generation.py`

The **Semantic Router Module** is the **second stage** of the Adaptive Routing pipeline. It takes normalized English text (output from the Triage Module) and performs two operations: **classifies** the query intent, then **generates** a legal response using the appropriate LLM engine.

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [SemanticRouterModule (Orchestrator)](#semanticroutermodule-orchestrator)
  - [Constructor](#constructor)
  - [_process_routing_()](#_process_routing_)
  - [Return Schema](#return-schema)
- [RoutingClassifier (Sub-component)](#routingclassifier-sub-component)
  - [Constructor](#routingclassifier-constructor)
  - [_route_query_()](#_route_query_)
  - [Classification Output Schema](#classification-output-schema)
  - [Routing Logic](#routing-logic)
  - [Fail-Safe Behavior](#fail-safe-behavior)
- [LegalGenerator (Sub-component)](#legalgenerator-sub-component)
  - [Constructor](#legalgenerator-constructor)
  - [_dispatch_()](#_dispatch_)
  - [_dispatch_conversation_()](#_dispatch_conversation_)
  - [Response Format by Route](#response-format-by-route)
- [Usage Examples](#usage-examples)
- [Customization Guide](#customization-guide)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│              SemanticRouterModule                        │
│                 (Orchestrator)                           │
│                                                         │
│  ┌───────────────────┐      ┌────────────────────────┐  │
│  │ RoutingClassifier │─────▶│   LegalGenerator       │  │
│  │                   │      │                        │  │
│  │  Outputs:         │      │  Dual Engine:          │  │
│  │  - route          │      │  - General-LLM engine  │  │
│  │  - confidence     │      │  - Reasoning-LLM engine│  │
│  │  - trigger_signals│      │                        │  │
│  └───────────────────┘      └────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

**Data flow:**
1. Normalized text → `SemanticRouterModule._process_routing_()`
2. `RoutingClassifier._route_query_()` classifies intent → returns `{route, confidence, trigger_signals}`
3. If route is valid (not `PATHWAY_2`), `LegalGenerator._dispatch_()` generates the response
4. If route is `PATHWAY_2` (ambiguous), a clarification prompt is returned
5. Combined classification + response returned to caller

---

## SemanticRouterModule (Orchestrator)

**Import**: `from src.adaptive_routing import SemanticRouterModule`  
**Or**: `from src.adaptive_routing.modules.router import SemanticRouterModule`

### Constructor

```python
SemanticRouterModule(
    api_key: str = None,
    classifier: RoutingClassifier = None,
    generator: LegalGenerator = None
)
```

| Parameter | Type | Default | Description |
|:---|:---|:---|:---|
| `api_key` | `str` | `FrameworkConfig._API_KEY` | Passed to sub-components for LLM access |
| `classifier` | `RoutingClassifier` | Auto-created | Custom classifier instance |
| `generator` | `LegalGenerator` | Auto-created | Custom generator instance |

**Basic instantiation:**

```python
from src.adaptive_routing import SemanticRouterModule

router = SemanticRouterModule()
```

---

### `_process_routing_()`

```python
def _process_routing_(self, normalized_text: str) -> dict
```

The **main entry point** for semantic routing and response generation.

| Parameter | Type | Required | Description |
|:---|:---|:---|:---|
| `normalized_text` | `str` | Yes | Standardized English query (typically output from `TriageModule`) |

**Returns**: `dict` — See [Return Schema](#return-schema)

---

### Return Schema

```python
{
    "classification": {
        "route": str,             # "General-LLM", "Reasoning-LLM", or "PATHWAY_2"
        "confidence": float,      # 0.0 to 1.0
        "trigger_signals": list   # List of short strings explaining the classification
    },
    "response_text": str          # The LLM-generated legal response (or clarification prompt)
}
```

**Example — General Information route:**

```python
{
    "classification": {
        "route": "General-LLM",
        "confidence": 0.92,
        "trigger_signals": ["definition request", "legal concept explanation"]
    },
    "response_text": "**Query Overview**: The user is asking about the concept of illegal dismissal...\n..."
}
```

**Example — Reasoning route:**

```python
{
    "classification": {
        "route": "Reasoning-LLM",
        "confidence": 0.88,
        "trigger_signals": ["specific scenario", "employment dispute", "legal action needed"]
    },
    "response_text": "**1. Application**\nThe worker alleges non-payment of overtime...\n..."
}
```

**Example — Ambiguous (PATHWAY_2):**

```python
{
    "classification": {
        "route": "PATHWAY_2",
        "confidence": 0.0,
        "trigger_signals": ["Routing Error", "..."]
    },
    "response_text": "Hi There can you please clarify your inquiry, provide specific details."
}
```

---

## RoutingClassifier (Sub-component)

**Import**: `from src.adaptive_routing.modules.semantic_router.logic_classifier import RoutingClassifier`

Analyzes the semantic intent of user queries to determine which LLM pipeline should handle the response.

### RoutingClassifier Constructor

```python
RoutingClassifier(
    api_key: str = None,
    handler: LLMRequestEngine = None,
    system_prompt: str = None
)
```

| Parameter | Type | Default | Description |
|:---|:---|:---|:---|
| `api_key` | `str` | `FrameworkConfig._API_KEY` | API key for LLM access |
| `handler` | `LLMRequestEngine` | Auto-created with Router config | Custom engine instance |
| `system_prompt` | `str` | Built-in routing prompt | Custom classification prompt |

**Default engine configuration** (from `FrameworkConfig`):

| Parameter | Config Source | Default Value |
|:---|:---|:---|
| Model | `_ROUTER_MODEL` | `"google/gemma-3-12b-it:free"` |
| Temperature | `_ROUTER_TEMP` | `0.0` |
| Max Tokens | `_ROUTER_MAX_TOKENS` | `200` |
| System Role | `_ROUTER_USE_SYSTEM` | `False` |
| Reasoning | `_ROUTER_REASONING` | `False` |

---

### `_route_query_()`

```python
def _route_query_(self, query: str) -> dict
```

| Parameter | Type | Required | Description |
|:---|:---|:---|:---|
| `query` | `str` | Yes | The normalized user query |

**Returns**: `dict` — Classification result (see below)

---

### Classification Output Schema

The classifier instructs the LLM to return structured JSON:

```python
{
    "route": "General-LLM" | "Reasoning-LLM",
    "confidence": float,           # 0.0 to 1.0
    "trigger_signals": [str, ...]  # List of short reasoning strings
}
```

**Routing criteria:**

| Route | When Used |
|:---|:---|
| `General-LLM` | General legal information, definitions, explanations, rights overview, simple Q&A, no personalized advice needed |
| `Reasoning-LLM` | Real or hypothetical situations, asks what action to take, involves disputes/violations/contracts/termination/abuse/legal risk, requires legal interpretation |

---

### Routing Logic

The built-in system prompt defines two LLM pathways:

**General-LLM criteria:**
- General legal information
- Definitions, explanations, rights overview
- Simple Q&A
- No personalized advice
- No complex scenario or dispute

**Reasoning-LLM criteria:**
- Describes a real or hypothetical situation
- Asks what action to take
- Involves disputes, violations, contracts, termination, abuse, or legal risk
- Requires legal interpretation and structured reasoning

**Additional constraints in the system prompt:**
- Returns structured JSON only (no markdown)
- Does NOT answer the question — only classifies it
- Strictly adheres to the router role

---

### Fail-Safe Behavior

If routing fails for **any reason** (API error, JSON parsing failure, etc.), the classifier returns a safe fallback:

```python
{
    "route": "PATHWAY_2",
    "confidence": 0.0,
    "trigger_signals": ["Routing Error", "<error details>"]
}
```

When `SemanticRouterModule` receives `PATHWAY_2`, it returns a clarification prompt instead of generating a response:

> *"Hi There can you please clarify your inquiry, provide specific details."*

**JSON parsing robustness**: The `_parse_json_()` method strips markdown code blocks (` ```json ... ``` `) before parsing, handling cases where the LLM wraps its JSON output.

---

## LegalGenerator (Sub-component)

**Import**: `from src.adaptive_routing.modules.semantic_router.legal_generation import LegalGenerator`

Manages **two separate LLM engines** and dispatches queries to the appropriate one based on the routing classification.

### LegalGenerator Constructor

```python
LegalGenerator(
    api_key: str = None,
    general_engine: LLMRequestEngine = None,
    reasoning_engine: LLMRequestEngine = None
)
```

| Parameter | Type | Default | Description |
|:---|:---|:---|:---|
| `api_key` | `str` | `FrameworkConfig._API_KEY` | API key for both engines |
| `general_engine` | `LLMRequestEngine` | Auto-created with General config | Custom engine for `General-LLM` route |
| `reasoning_engine` | `LLMRequestEngine` | Auto-created with Reasoning config | Custom engine for `Reasoning-LLM` route |

**Default General engine config:**

| Parameter | Config Source | Default Value |
|:---|:---|:---|
| Model | `_GENERAL_MODEL` | `"google/gemma-3-12b-it:free"` |
| Temperature | `_GENERAL_TEMP` | `0.5` |
| Max Tokens | `_GENERAL_MAX_TOKENS` | `1000` |
| System Role | `_GENERAL_USE_SYSTEM` | `False` |
| Reasoning | `_GENERAL_REASONING` | `False` |

**Default Reasoning engine config:**

| Parameter | Config Source | Default Value |
|:---|:---|:---|
| Model | `_REASONING_MODEL` | `"google/gemma-3-12b-it:free"` |
| Temperature | `_REASONING_TEMP` | `0.7` |
| Max Tokens | `_REASONING_MAX_TOKENS` | `2000` |
| System Role | `_REASONING_USE_SYSTEM` | `False` |
| Reasoning | `_REASONING_REASONING` | `True` |

---

### `_dispatch_()`

```python
def _dispatch_(self, query: str, route: str) -> str
```

Dispatches a single query to the appropriate LLM engine.

| Parameter | Type | Required | Description |
|:---|:---|:---|:---|
| `query` | `str` | Yes | The user's legal query |
| `route` | `str` | Yes | `"General-LLM"` or `"Reasoning-LLM"` |

**Returns**: `str` — The LLM's response text

**Dispatch logic:**
- `"Reasoning-LLM"` → Uses `_reasoning_engine` with `_REASONING_INSTRUCTIONS`
- Any other value (including `"General-LLM"`) → Uses `_general_engine` with `_GENERAL_INSTRUCTIONS`

---

### `_dispatch_conversation_()`

```python
def _dispatch_conversation_(self, messages: list[dict], route: str) -> str
```

For multi-turn conversation support. Dispatches a full conversation history to the appropriate engine.

| Parameter | Type | Required | Description |
|:---|:---|:---|:---|
| `messages` | `list[dict]` | Yes | Full conversation history (`[{role, content}, ...]`) |
| `route` | `str` | Yes | `"General-LLM"` or `"Reasoning-LLM"` |

**Returns**: `str` — The LLM's response text

**Example:**

```python
from src.adaptive_routing.modules.semantic_router.legal_generation import LegalGenerator

generator = LegalGenerator()

messages = [
    {"role": "system", "content": "You are a legal assistant."},
    {"role": "user", "content": "What is overtime pay?"},
    {"role": "assistant", "content": "Overtime pay is compensation for hours worked beyond..."},
    {"role": "user", "content": "How is it computed in the Philippines?"}
]

response = generator._dispatch_conversation_(messages, "General-LLM")
```

---

### Response Format by Route

**General-LLM** responses follow this format (from `_GENERAL_INSTRUCTIONS`):
1. **Query Overview** — Briefly restates the legal topic
2. **Relevant Legal Concepts** — Citations of relevant laws (PH/HK)
3. **General Explanation** — How laws generally apply
4. **Summary** — Concise answer or definition

**Reasoning-LLM** responses follow the ALAC Standard (from `_REASONING_INSTRUCTIONS`):
1. **Application** — Restates relevant facts, clarifies jurisdiction
2. **Law** — Cites relevant laws/rules (no analysis yet)
3. **Analysis** — Applies laws to facts, compares requirements vs events
4. **Conclusion** — Direct answer, likely legal position, suggested next steps

---

## Usage Examples

### Basic Routing

```python
from src.adaptive_routing import SemanticRouterModule

router = SemanticRouterModule()

# General information query
result = router._process_routing_("What is the definition of illegal dismissal?")
print(result["classification"]["route"])      # → "General-LLM"
print(result["response_text"])                # → Structured legal information

# Scenario-based query
result = router._process_routing_(
    "An employer terminated a domestic worker without 30 days notice after 2 years of service."
)
print(result["classification"]["route"])      # → "Reasoning-LLM"
print(result["response_text"])                # → ALAC-formatted legal analysis
```

### Full Pipeline (Triage → Router)

```python
from src.adaptive_routing import TriageModule, SemanticRouterModule

triage = TriageModule()
router = SemanticRouterModule()

# Step 1: Normalize the input
triage_result = triage._process_request_(
    "Pinalayas ako ng amo ko kahit wala akong kasalanan, ano pwede kong gawin?"
)

# Step 2: Route and generate
router_result = router._process_routing_(triage_result["normalized_text"])

print(f"Route: {router_result['classification']['route']}")
print(f"Confidence: {router_result['classification']['confidence']}")
print(f"Response: {router_result['response_text']}")
```

### Using the Classifier Independently

```python
from src.adaptive_routing.modules.semantic_router.logic_classifier import RoutingClassifier

classifier = RoutingClassifier()
classification = classifier._route_query_("What are my rights as an OFW?")

print(classification)
# {
#     "route": "General-LLM",
#     "confidence": 0.95,
#     "trigger_signals": ["rights overview", "general information"]
# }
```

### Using the Generator Independently

```python
from src.adaptive_routing.modules.semantic_router.legal_generation import LegalGenerator

generator = LegalGenerator()

# Direct dispatch without routing
response = generator._dispatch_(
    "What is the procedure for filing a labor complaint in Hong Kong?",
    "General-LLM"
)
print(response)
```

### Conversation Mode

```python
from src.adaptive_routing.modules.semantic_router.legal_generation import LegalGenerator
from src.adaptive_routing.config import FrameworkConfig

generator = LegalGenerator()

conversation = [
    {"role": "system", "content": FrameworkConfig._GENERAL_INSTRUCTIONS},
    {"role": "user", "content": "What is the minimum wage in Hong Kong?"},
]

# First turn
response1 = generator._dispatch_conversation_(conversation, "General-LLM")
conversation.append({"role": "assistant", "content": response1})

# Follow-up
conversation.append({"role": "user", "content": "How does it compare to the Philippines?"})
response2 = generator._dispatch_conversation_(conversation, "General-LLM")
```

---

## Customization Guide

### Custom System Prompt for Routing

Override the default routing logic with your own classification rules:

```python
from src.adaptive_routing.modules.semantic_router.logic_classifier import RoutingClassifier

custom_prompt = (
    "ROLE: Legal Query Router for Immigration Law\n"
    "TASK: Classify the query into one of two routes.\n\n"
    "General-LLM:\n"
    "- Visa requirements and processes\n"
    "- Document checklists\n"
    "- General immigration rules\n\n"
    "Reasoning-LLM:\n"
    "- Deportation scenarios\n"
    "- Visa denial appeals\n"
    "- Complex immigration disputes\n\n"
    "JSON Schema:\n"
    '{"route": "General-LLM" | "Reasoning-LLM", '
    '"confidence": float, '
    '"trigger_signals": [list]}'
)

classifier = RoutingClassifier(system_prompt=custom_prompt)
```

### Custom Engines for Different LLM Providers

```python
from src.adaptive_routing.core.engine import LLMRequestEngine
from src.adaptive_routing.modules.semantic_router.legal_generation import LegalGenerator

# High-precision general engine
general_engine = LLMRequestEngine(
    model="google/gemma-3-12b-it:free",
    temperature=0.3,
    max_tokens=1500,
    use_system_role=True
)

# Deep reasoning engine
reasoning_engine = LLMRequestEngine(
    model="deepseek/deepseek-r1:free",
    temperature=0.7,
    max_tokens=3000,
    use_system_role=False,
    include_reasoning=True
)

generator = LegalGenerator(
    general_engine=general_engine,
    reasoning_engine=reasoning_engine
)

router = SemanticRouterModule(generator=generator)
```

### Custom Classifier with Custom Engine

```python
from src.adaptive_routing.core.engine import LLMRequestEngine
from src.adaptive_routing.modules.semantic_router.logic_classifier import RoutingClassifier
from src.adaptive_routing.modules.router import SemanticRouterModule

# Ultra-deterministic routing
routing_engine = LLMRequestEngine(
    model="google/gemma-3-12b-it:free",
    temperature=0.0,
    max_tokens=300,
    use_system_role=False
)

classifier = RoutingClassifier(handler=routing_engine)
router = SemanticRouterModule(classifier=classifier)
```

### Overriding Response Instructions

Change how the General-LLM or Reasoning-LLM formats its responses:

```python
from src.adaptive_routing.config import FrameworkConfig

# Custom General-LLM instructions
FrameworkConfig._GENERAL_INSTRUCTIONS = (
    "ROLE: Employment Rights Specialist\n"
    "TASK: Provide clear, concise answers about worker rights.\n"
    "FORMAT: Use bullet points. Cite specific law sections.\n"
    "TONE: Empathetic and supportive."
)

# Custom Reasoning-LLM instructions
FrameworkConfig._REASONING_INSTRUCTIONS = (
    "ROLE: Legal Case Analyst\n"
    "TASK: Analyze employment law scenarios using IRAC method.\n"
    "FORMAT: Issue → Rule → Application → Conclusion\n"
    "SAFEGUARDS: Always recommend seeking professional legal counsel."
)
```

### Accessing Sub-components Directly

```python
router = SemanticRouterModule()

# Access the classifier
classification = router._classifier._route_query_("Some query")

# Access the generator
response = router._generator._dispatch_("Some query", "General-LLM")

# Access underlying engines
general_eng = router._generator._general_engine
reasoning_eng = router._generator._reasoning_engine
```
