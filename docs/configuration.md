# Configuration Reference — `FrameworkConfig`

> **File**: `src/adaptive_routing/config.py`  
> **Import**: `from src.adaptive_routing.config import FrameworkConfig`

The `FrameworkConfig` class is the **centralized configuration hub** for every module in the Legal Adaptive Routing Framework. All settings are resolved from **environment variables** first, falling back to **built-in defaults** when not specified.

---

## Table of Contents

- [Quick Start](#quick-start)
- [API Key](#api-key)
- [Triage Module Settings](#triage-module-settings)
- [Semantic Router Settings](#semantic-router-settings)
- [General LLM Settings](#general-llm-settings)
- [Reasoning LLM Settings](#reasoning-llm-settings)
- [Casual LLM Settings](#casual-llm-settings)
- [Legal Retrieval (RAG) Settings](#legal-retrieval-rag-settings)
- [Fallback / Legacy Settings](#fallback--legacy-settings)
- [Runtime Configuration Override](#runtime-configuration-override)
- [Customization Patterns](#customization-patterns)

---

## Quick Start

Create a `.env` file at the project root:

```env
OPENROUTER_API_KEY=sk-or-v1-your-api-key-here
```

This is the **only required** setting. All other parameters use sensible defaults out of the box.

---

## API Key

| Attribute | Env Variable | Type | Default |
|:---|:---|:---|:---|
| `_API_KEY` | `OPENROUTER_API_KEY` | `str` | `""` (empty — **must be set**) |

The API key is required for all LLM and embedding operations. It is used by every module that communicates with the OpenRouter API.

**Setting the API key:**

```python
import os
os.environ["OPENROUTER_API_KEY"] = "sk-or-v1-your-api-key-here"
```

Or via `.env` file (loaded with `python-dotenv`):

```env
OPENROUTER_API_KEY=sk-or-v1-your-api-key-here
```

---

## Triage Module Settings

Controls the **Linguistic Normalizer** — the LLM that translates Tagalog/Taglish/Cantonese input into standardized English.

| Attribute | Env Variable | Type | Default | Description |
|:---|:---|:---|:---|:---|
| `_TRIAGE_MODEL` | `TRIAGE_MODEL` | `str` | `"qwen/qwen3-4b:free"` | LLM model for text normalization |
| `_TRIAGE_TEMP` | `TRIAGE_TEMP` | `float` | `0.6` | Creativity level (0.0 = deterministic, 2.0 = max creative) |
| `_TRIAGE_MAX_TOKENS` | `TRIAGE_MAX_TOKENS` | `int` | `1500` | Maximum response length in tokens |
| `_TRIAGE_USE_SYSTEM` | `TRIAGE_USE_SYSTEM` | `bool` | `True` | Whether to use the `system` role in API requests |
| `_TRIAGE_REASONING` | `TRIAGE_REASONING` | `bool` | `True` | Whether to include chain-of-thought reasoning |

**Customization example:**

```env
TRIAGE_MODEL=google/gemma-3-12b-it:free
TRIAGE_TEMP=0.3
TRIAGE_MAX_TOKENS=2000
```

---

## Semantic Router Settings

Controls the **RoutingClassifier** — the LLM that classifies queries into `General-LLM` or `Reasoning-LLM` pathways.

| Attribute | Env Variable | Type | Default | Description |
|:---|:---|:---|:---|:---|
| `_ROUTER_MODEL` | `ROUTER_MODEL` | `str` | `"google/gemma-3-12b-it:free"` | LLM model for route classification |
| `_ROUTER_TEMP` | `ROUTER_TEMP` | `float` | `0.0` | Temperature (0.0 for deterministic routing) |
| `_ROUTER_MAX_TOKENS` | `ROUTER_MAX_TOKENS` | `int` | `200` | Max tokens (routing output is compact JSON) |
| `_ROUTER_USE_SYSTEM` | `ROUTER_USE_SYSTEM` | `bool` | `False` | System role support |
| `_ROUTER_REASONING` | `ROUTER_REASONING` | `bool` | `False` | Include reasoning in response |

> **Tip**: Keep `_ROUTER_TEMP` at `0.0` for consistent, reproducible routing decisions.

---

## General LLM Settings

Controls the **General-LLM** — used for standard legal information queries (definitions, rights overviews, simple Q&A).

| Attribute | Env Variable | Type | Default | Description |
|:---|:---|:---|:---|:---|
| `_GENERAL_MODEL` | `GENERAL_MODEL` | `str` | `"google/gemma-3-12b-it:free"` | LLM model for general responses |
| `_GENERAL_TEMP` | `GENERAL_TEMP` | `float` | `0.5` | Temperature for response variety |
| `_GENERAL_MAX_TOKENS` | `GENERAL_MAX_TOKENS` | `int` | `1000` | Max response length |
| `_GENERAL_USE_SYSTEM` | `GENERAL_USE_SYSTEM` | `bool` | `False` | System role support |
| `_GENERAL_REASONING` | `GENERAL_REASONING` | `bool` | `False` | Include reasoning output |
| `_GENERAL_INSTRUCTIONS` | — | `str` | *(see below)* | System prompt for the General-LLM |

**Default `_GENERAL_INSTRUCTIONS` behavior:**
- Persona: "Atty. Agapay AI" — a legal information assistant for OFWs
- Output format: Query Overview → Relevant Legal Concepts → General Explanation → Summary
- Constraints: No specific legal advice, distinguish PH/HK jurisdictions, simplified language

**Override the instructions at runtime:**

```python
FrameworkConfig._GENERAL_INSTRUCTIONS = (
    "ROLE: Immigration Law Specialist\n"
    "TASK: Provide general information about immigration procedures...\n"
)
```

---

## Reasoning LLM Settings

Controls the **Reasoning-LLM** — used for complex legal analysis, scenario-based reasoning, and case evaluation.

| Attribute | Env Variable | Type | Default | Description |
|:---|:---|:---|:---|:---|
| `_REASONING_MODEL` | `REASONING_MODEL` | `str` | `"google/gemma-3-12b-it:free"` | LLM model for reasoning tasks |
| `_REASONING_TEMP` | `REASONING_TEMP` | `float` | `0.7` | Higher temperature for nuanced analysis |
| `_REASONING_MAX_TOKENS` | `REASONING_MAX_TOKENS` | `int` | `2000` | Extended token limit for detailed analysis |
| `_REASONING_USE_SYSTEM` | `REASONING_USE_SYSTEM` | `bool` | `False` | System role support |
| `_REASONING_REASONING` | `REASONING_REASONING` | `bool` | `True` | Include chain-of-thought reasoning |
| `_REASONING_INSTRUCTIONS` | — | `str` | *(see below)* | System prompt for the Reasoning-LLM |

**Default `_REASONING_INSTRUCTIONS` behavior:**
- Persona: "Atty. Agapay AI" — legal assistant for OFWs
- Output format: ALAC Standard — **Application → Law → Analysis → Conclusion**
- Safety: "You are NOT a lawyer", no court outcome predictions, simplified language

---

## Casual LLM Settings

Controls the **Casual-LLM** engine — used for greetings, expressions of gratitude, farewells, and small talk.

| Attribute | Env Variable | Type | Default | Description |
|:---|:---|:---|:---|:---|
| `_CASUAL_MODEL` | `CASUAL_MODEL` | `str` | `"google/gemma-3-12b-it:free"` | LLM for small-talk responses |
| `_CASUAL_TEMP` | `CASUAL_TEMP` | `float` | `0.8` | Higher temperature for natural, varied replies |
| `_CASUAL_MAX_TOKENS` | `CASUAL_MAX_TOKENS` | `int` | `200` | Short responses — 1–3 sentences max |
| `_CASUAL_USE_SYSTEM` | `CASUAL_USE_SYSTEM` | `bool` | `True` | System role support |
| `_CASUAL_REASONING` | `CASUAL_REASONING` | `bool` | `False` | Chain-of-thought disabled |
| `_CASUAL_INSTRUCTIONS` | — | `str` | *(see below)* | Persona prompt for the Casual-LLM |

**Default `_CASUAL_INSTRUCTIONS` behavior:**
- Persona: "Atty. Agapay AI" — warm and approachable greeter
- Keeps responses to 1–3 sentences
- Does NOT provide any legal information; redirects to ask how it can assist
- May respond in the same language the user uses (English, Tagalog, etc.)

---

## Legal Retrieval (RAG) Settings

Controls the **EmbeddingManager** and **LegalRetriever** — the document embedding and FAISS vector search pipeline.

| Attribute | Env Variable | Type | Default | Description |
|:---|:---|:---|:---|:---|
| `_RETRIEVAL_MODEL` | `RETRIEVAL_MODEL` | `str` | `"sentence-transformers/all-minilm-l6-v2"` | Embedding model for vector generation |
| `_RETRIEVAL_TOP_K` | `RETRIEVAL_TOP_K` | `int` | `5` | Number of nearest chunks to retrieve |
| `_RETRIEVAL_CHUNK_SIZE` | `RETRIEVAL_CHUNK_SIZE` | `int` | `5000` | Maximum characters per document chunk |
| `_RETRIEVAL_CHUNK_OVERLAP` | `RETRIEVAL_CHUNK_OVERLAP` | `int` | `200` | Character overlap between adjacent chunks |
| `_RETRIEVAL_INDEX_PATH` | `RETRIEVAL_INDEX_PATH` | `str` | `None` | Path to a pre-built FAISS `.faiss` file |
| `_RETRIEVAL_CHUNKS_PATH` | `RETRIEVAL_CHUNKS_PATH` | `str` | `None` | Path to a pre-built chunks `.json` file |

**Pre-built index auto-loading:**

```env
RETRIEVAL_INDEX_PATH=Faiss/hk_index.faiss
RETRIEVAL_CHUNKS_PATH=Faiss/hk_index.json
```

When these are set, `LegalRetrievalModule` will automatically load the index at initialization — no manual `_load_index_()` call needed.

**Tuning chunk parameters:**

```env
# Larger chunks for more context, smaller overlap for faster indexing
RETRIEVAL_CHUNK_SIZE=1024
RETRIEVAL_CHUNK_OVERLAP=128
RETRIEVAL_TOP_K=10
```

---

## Fallback / Legacy Settings

These are global defaults used when no module-specific configuration is provided:

| Attribute | Type | Default | Description |
|:---|:---|:---|:---|
| `_DEFAULT_MODEL` | `str` | Same as `_TRIAGE_MODEL` | Fallback model for unspecified modules |
| `_TEMPERATURE` | `float` | `0.7` | Default temperature |
| `_MAX_TOKENS` | `int` | `1500` | Default max tokens |
| `_USE_SYSTEM_ROLE` | `bool` | `True` | Default system role usage |
| `_INCLUDE_REASONING` | `bool` | `False` | Default reasoning inclusion |

---

## Runtime Configuration Override

### Using `_update_settings_()`

Dynamically override any configuration parameter at runtime without modifying environment variables:

```python
from src.adaptive_routing.config import FrameworkConfig

# Override Triage model and temperature
FrameworkConfig._update_settings_(
    triage_model="google/gemma-3-12b-it:free",
    triage_temp=0.3,
    triage_max_tokens=2000
)

# Override Retrieval parameters
FrameworkConfig._update_settings_(
    retrieval_top_k=10,
    retrieval_chunk_size=1024
)
```

**How it works:**
1. Each `key` in `kwargs` is uppercased and prefixed with `_` (e.g., `triage_model` → `_TRIAGE_MODEL`)
2. If the resulting attribute name exists on `FrameworkConfig`, the value is updated
3. Non-existent keys are silently ignored

### Direct Attribute Assignment

For single-value changes, you can set class attributes directly:

```python
FrameworkConfig._TRIAGE_TEMP = 0.2
FrameworkConfig._RETRIEVAL_TOP_K = 10
```

> **Note**: Both methods modify class-level attributes. Changes apply globally to all subsequent module instantiations in the same process.

---

## Customization Patterns

### Pattern 1: Environment-Based Configuration (Recommended for Production)

```env
# .env
OPENROUTER_API_KEY=sk-or-v1-xxx
TRIAGE_MODEL=google/gemma-3-12b-it:free
ROUTER_TEMP=0.0
REASONING_MODEL=deepseek/deepseek-r1:free
RETRIEVAL_TOP_K=8
```

### Pattern 2: Programmatic Override (Development / Testing)

```python
from src.adaptive_routing.config import FrameworkConfig

# Apply all overrides at once
FrameworkConfig._update_settings_(
    triage_model="qwen/qwen3-4b:free",
    router_temp=0.0,
    general_temp=0.5,
    reasoning_temp=0.7,
    retrieval_top_k=5
)
```

### Pattern 3: Per-Module Engine Injection (Maximum Control)

Instead of modifying global config, inject a custom engine into individual modules:

```python
from src.adaptive_routing.core.engine import LLMRequestEngine
from src.adaptive_routing.modules.triage import TriageModule

# Create a custom engine with specific parameters
custom_engine = LLMRequestEngine(
    api_key="sk-or-v1-custom-key",
    model="google/gemma-3-12b-it:free",
    temperature=0.2,
    max_tokens=3000,
    use_system_role=True,
    include_reasoning=True
)

# Inject into the module
triage = TriageModule(engine=custom_engine)
```

This pattern bypasses `FrameworkConfig` entirely for that module, providing full isolation.
