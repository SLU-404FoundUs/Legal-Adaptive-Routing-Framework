# Triage Module Reference

> **Orchestrator**: `src/adaptive_routing/modules/triage.py`  
> **Sub-components**:  
> - `src/adaptive_routing/modules/multihead_classifier/linguistic.py`  
> - `src/adaptive_routing/modules/multihead_classifier/detector.py`

The **Triage Module** is the **first stage** of the Adaptive Routing pipeline. It takes raw, potentially multilingual user input and produces standardized English text with detected language metadata. This is a critical preprocessing step — all downstream modules (Semantic Router, Legal Retrieval) depend on the quality of the Triage output.

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [TriageModule (Orchestrator)](#triagemodule-orchestrator)
  - [Constructor](#constructor)
  - [_process_request_()](#_process_request_)
  - [Return Schema](#return-schema)
- [LinguisticNormalizer (Sub-component)](#linguisticnormalizer-sub-component)
  - [Constructor](#linguisticnormalizer-constructor)
  - [_normalize_text_()](#_normalize_text_)
  - [Normalization Rules](#normalization-rules)
  - [Language Detection Tag](#language-detection-tag)
- [LanguageStateDetector (Sub-component)](#languagestatedetector-sub-component)
  - [Constructor](#languagestatedetector-constructor)
  - [_update_state_()](#_update_state_)
  - [_get_state_()](#_get_state_)
- [Usage Examples](#usage-examples)
- [Customization Guide](#customization-guide)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                   TriageModule                      │
│                  (Orchestrator)                      │
│                                                     │
│  ┌──────────────────┐    ┌───────────────────────┐  │
│  │ LinguisticNormal │───▶│ LanguageStateDetector │  │
│  │     izer         │    │                       │  │
│  └──────────────────┘    └───────────────────────┘  │
│          │                          │               │
│    Uses LLM to                Stores state:         │
│    normalize text            - original_prompt      │
│    + detect language         - normalized_text      │
│                              - detected_language    │
└─────────────────────────────────────────────────────┘
```

**Data flow:**
1. Raw input → `TriageModule._process_request_()` → `LinguisticNormalizer._normalize_text_()`
2. LLM normalizes text + appends `<Detected Raw Language: ...>` tag
3. `TriageModule` parses the tag via regex, splits normalized text from language
4. `LanguageStateDetector._update_state_()` stores all results
5. Returns `_get_state_()` dict to the caller

---

## TriageModule (Orchestrator)

**Import**: `from src.adaptive_routing import TriageModule`  
**Or**: `from src.adaptive_routing.modules.triage import TriageModule`

### Constructor

```python
TriageModule(
    api_key: str = None,
    engine: LLMRequestEngine = None,
    normalizer: LinguisticNormalizer = None
)
```

| Parameter | Type | Default | Description |
|:---|:---|:---|:---|
| `api_key` | `str` | `FrameworkConfig._API_KEY` | OpenRouter API key. Only needed if not set in env. |
| `engine` | `LLMRequestEngine` | Auto-created with Triage config | Pre-configured engine instance. Overrides all Triage config settings. |
| `normalizer` | `LinguisticNormalizer` | Auto-created with the engine | Custom normalizer instance. Overrides the default normalizer. |

**Default engine configuration** (from `FrameworkConfig`):

| Parameter | Config Source | Default Value |
|:---|:---|:---|
| Model | `_TRIAGE_MODEL` | `"qwen/qwen3-4b:free"` |
| Temperature | `_TRIAGE_TEMP` | `0.6` |
| Max Tokens | `_TRIAGE_MAX_TOKENS` | `1500` |
| System Role | `_TRIAGE_USE_SYSTEM` | `True` |
| Reasoning | `_TRIAGE_REASONING` | `True` |

**Basic instantiation:**

```python
from src.adaptive_routing import TriageModule

# Uses environment API key + default Triage config
triage = TriageModule()

# Explicit API key
triage = TriageModule(api_key="sk-or-v1-your-key")
```

---

### `_process_request_()`

```python
def _process_request_(self, input_text: str, image_path: str = None) -> dict
```

The **main entry point** for all triage operations. Normalizes the input text and returns structured state.

| Parameter | Type | Required | Description |
|:---|:---|:---|:---|
| `input_text` | `str` | Yes | Raw user input in any supported language |
| `image_path` | `str` | No | Path to an image file or URL for multimodal normalization |

**Returns**: `dict` — See [Return Schema](#return-schema)

---

### Return Schema

```python
{
    "original_prompt": str,      # The raw input text as provided
    "detected_language": str,    # E.g., "Tagalog", "English", "Taglish", "Cantonese", "Other"
    "normalized_text": str       # Cleaned, standardized English text
}
```

**Example return value:**

```python
{
    "original_prompt": "Pwede ba akong mag-file ng case sa kapitbahay ko?",
    "detected_language": "Tagalog",
    "normalized_text": "The individual inquires whether a legal case can be filed against their neighbor."
}
```

---

## LinguisticNormalizer (Sub-component)

**Import**: `from src.adaptive_routing.modules.multihead_classifier.linguistic import LinguisticNormalizer`

The AI-powered text normalization engine. Uses an LLM with a hardened system prompt to convert multilingual input into standardized legal English.

### LinguisticNormalizer Constructor

```python
LinguisticNormalizer(handler: LLMRequestEngine)
```

| Parameter | Type | Required | Description |
|:---|:---|:---|:---|
| `handler` | `LLMRequestEngine` | Yes | The engine instance used for LLM API calls |

---

### `_normalize_text_()`

```python
def _normalize_text_(self, raw_input: str, image_path: str = None) -> str
```

| Parameter | Type | Required | Description |
|:---|:---|:---|:---|
| `raw_input` | `str` | Yes | The raw user input string |
| `image_path` | `str` | No | Path/URL to an image for multimodal processing |

**Returns**: `str` — Normalized English text followed by a `<Detected Raw Language: ...>` tag.

**Example raw output:**

```
The individual inquires whether a legal case can be filed against their neighbor. <Detected Raw Language: Tagalog>
```

---

### Normalization Rules

The built-in system prompt enforces the following normalization constraints:

| Rule | Description | Example |
|:---|:---|:---|
| **Format** | Output ONLY normalized text + language tag. No conversational filler. | ❌ "Sure, here's the translation..." ✅ Direct normalized text |
| **Objectivity** | Convert first-person subjective statements to third-person objective claims | "I feel my boss cheated me" → "Alleged employer misconduct reported" |
| **Legal Precision** | Retain all Latin legal phrases and formal terminology | "void ab initio" stays as-is |
| **Noise Reduction** | Strip linguistic fillers and emotional hyperbole | "po", "ano", "yung", "kasi", "parang" removed |
| **Prompt Injection Protection** | Treats all input as literal data. Ignores embedded commands. | Input wrapped in `###` delimiters |
| **Multilingual Recovery** | Unify mixed-language input into formal English | Preserves timeline, entities, names, locations |

### Language Detection Tag

The normalizer always appends a language tag at the end of its output:

```
<Detected Raw Language: [Language]>
```

**Supported language values:**
- `Tagalog`
- `English`
- `Taglish` (Tagalog-English mix)
- `Cantonese`
- `Other`

The `TriageModule` parses this tag via regex and stores it separately in the state.

---

## LanguageStateDetector (Sub-component)

**Import**: `from src.adaptive_routing.modules.multihead_classifier.detector import LanguageStateDetector`

A stateful component that stores the results of each triage cycle. Maintains the original input, detected language, and normalized output.

### LanguageStateDetector Constructor

```python
LanguageStateDetector()
```

No parameters. All state attributes initialize to `None`.

### `_update_state_()`

```python
def _update_state_(self, original: str, normalized: str, language: str)
```

| Parameter | Type | Description |
|:---|:---|:---|
| `original` | `str` | The raw user input |
| `normalized` | `str` | The processed English text |
| `language` | `str` | The detected language tag |

Updates the internal state. Called automatically by `TriageModule._process_request_()`.

### `_get_state_()`

```python
def _get_state_() -> dict
```

**Returns**: `dict` with keys `original_prompt`, `detected_language`, `normalized_text`.

---

## Usage Examples

### Basic Usage

```python
from src.adaptive_routing import TriageModule

triage = TriageModule()

# Tagalog input
result = triage._process_request_("Pwede ba akong mag-file ng case sa kapitbahay ko?")
print(result["normalized_text"])
# → "The individual inquires whether a legal case can be filed against their neighbor."
print(result["detected_language"])
# → "Tagalog"
```

### Taglish (Mixed Language) Input

```python
result = triage._process_request_(
    "Yung boss ko kasi, hindi niya binayaran yung overtime ko for 3 months na"
)
print(result["normalized_text"])
# → "Alleged non-payment of overtime wages by the employer over a period of three months."
print(result["detected_language"])
# → "Taglish"
```

### Multimodal Input (With Image)

```python
# Using a local file
result = triage._process_request_(
    "Ano yung sinasabi dito sa contract na 'to?",
    image_path="/path/to/contract_photo.jpg"
)

# Using a URL
result = triage._process_request_(
    "What does this document say?",
    image_path="https://example.com/document.png"
)
```

### English Input (Pass-through)

```python
result = triage._process_request_(
    "What are the legal grounds for filing an illegal dismissal case in the Philippines?"
)
print(result["detected_language"])
# → "English"
# normalized_text will be a refined, objective version of the input
```

---

## Customization Guide

### Custom Engine Injection

Override the default Triage LLM with your own engine:

```python
from src.adaptive_routing.core.engine import LLMRequestEngine
from src.adaptive_routing import TriageModule

custom_engine = LLMRequestEngine(
    api_key="sk-or-v1-your-key",
    model="google/gemma-3-12b-it:free",  # Different model
    temperature=0.3,                      # Lower temperature for consistency
    max_tokens=2000,
    use_system_role=True,
    include_reasoning=False
)

triage = TriageModule(engine=custom_engine)
```

### Custom Normalizer with Modified Prompt

Create a normalizer with a different system prompt:

```python
from src.adaptive_routing.core.engine import LLMRequestEngine
from src.adaptive_routing.modules.multihead_classifier.linguistic import LinguisticNormalizer
from src.adaptive_routing import TriageModule

engine = LLMRequestEngine(
    model="google/gemma-3-12b-it:free",
    temperature=0.4
)

# Create a custom normalizer
custom_normalizer = LinguisticNormalizer(handler=engine)

# Override the system instruction
custom_normalizer._instruction = (
    "ROLE: Medical-Legal Linguistic Normalizer.\n"
    "TASK: Convert multilingual medical-legal input into standardized English.\n"
    "CONSTRAINTS:\n"
    "1. Preserve all medical terminology and ICD codes.\n"
    "2. Convert informal descriptions to clinical language.\n"
    "3. Append: <Detected Raw Language: [Language]>\n"
)

triage = TriageModule(normalizer=custom_normalizer, engine=engine)
```

### Changing Configuration via Environment Variables

```env
TRIAGE_MODEL=google/gemma-3-12b-it:free
TRIAGE_TEMP=0.3
TRIAGE_MAX_TOKENS=2000
TRIAGE_USE_SYSTEM=True
TRIAGE_REASONING=False
```

### Changing Configuration at Runtime

```python
from src.adaptive_routing.config import FrameworkConfig

FrameworkConfig._update_settings_(
    triage_model="google/gemma-3-12b-it:free",
    triage_temp=0.3,
    triage_max_tokens=2000
)

# Now all new TriageModule instances use the updated values
triage = TriageModule()
```

### Accessing Sub-components Directly

```python
triage = TriageModule()

# Access the normalizer directly
raw_output = triage._normalizer._normalize_text_("Some raw input")

# Access the detector state
state = triage._detector._get_state_()

# Access the underlying engine
engine = triage._engine
```

### Using Triage Output for Downstream Modules

The typical pipeline passes triage output to the Semantic Router:

```python
from src.adaptive_routing import TriageModule
from src.adaptive_routing.modules.router import SemanticRouterModule

triage = TriageModule()
router = SemanticRouterModule()

# Step 1: Normalize
triage_result = triage._process_request_("Paano mag-file ng illegal dismissal case?")
normalized_text = triage_result["normalized_text"]

# Step 2: Route and generate
router_result = router._process_routing_(normalized_text)
print(router_result["response_text"])
```
