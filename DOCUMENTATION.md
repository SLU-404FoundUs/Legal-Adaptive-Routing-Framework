# Legal Adaptive Routing Framework Documentation

## Overview
The **LLM Legal Adaptive Routing Framework** is a modular system designed to process legal queries through a multi-stage pipeline:
1.  **Triage (Normalization)**: Standardizes user input and detects language.
2.  **Semantic Routing**: Classifies the query to determine the appropriate processing pathway (General Information vs. Legal Reasoning).
3.  **Legal Generation**: Generates a response using the selected LLM and prompt strategy.

## Configuration
The framework is configured via `src/adaptive_routing/config.py`. It uses environment variables with default fallbacks.

### FrameworkConfig Class
**File**: `src/adaptive_routing/config.py`
**Description**: Manages global AI hyperparameters and system instructions.

#### Core Settings
| Constant | Env Variable | Default | Description |
| :--- | :--- | :--- | :--- |
| `_API_KEY` | `OPENROUTER_API_KEY` | `""` | OpenRouter API Key. |
| `_DEFAULT_MODEL` | `TRIAGE_MODEL` | `qwen/qwen3-4b:free` | Default fallback model. |

#### Triage Module Settings
| Constant | Env Variable | Default | Description |
| :--- | :--- | :--- | :--- |
| `_TRIAGE_MODEL` | `TRIAGE_MODEL` | `qwen/qwen3-4b:free` | Model for normalization. |
| `_TRIAGE_TEMP` | `TRIAGE_TEMP` | `0.6` | Temperature for creativity. |
| `_TRIAGE_MAX_TOKENS` | `TRIAGE_MAX_TOKENS` | `1500` | Max tokens for response. |

#### Semantic Router Settings
| Constant | Env Variable | Default | Description |
| :--- | :--- | :--- | :--- |
| `_ROUTER_MODEL` | `ROUTER_MODEL` | `google/gemma-3-4b-it:free` | Model for routing classification. |
| `_ROUTER_TEMP` | `ROUTER_TEMP` | `0.0` | Zero temperature for deterministic routing. |

#### Legal Generation Settings
| Constant | Env Variable | Default | Description |
| :--- | :--- | :--- | :--- |
| `_GENERAL_MODEL` | `GENERAL_MODEL` | `google/gemma-3-27b-it:free` | Model for general info queries. |
| `_REASONING_MODEL` | `REASONING_MODEL` | `google/gemma-3-4b-it:free` | Model for complex reasoning. |

---

## Modules

### 1. Triage Module
**File**: `src/adaptive_routing/modules/triage.py`
**Class**: `TriageModule`
**Description**: Orchestrates linguistic normalization and language detection.

#### Functions

##### `_process_request_(self, input_text: str, image_path: str = None) -> dict`
-   **Logic**:
    1.  Calls `LinguisticNormalizer` to normalize the input text.
    2.  Parses the output to extract the normalized text and detected language using Regex (`<Detected Raw Language: ...>`).
    3.  Updates the `LanguageStateDetector` state.
-   **Return Value**:
    ```python
    {
        "input_text": str,
        "normalized_text": str,
        "detected_language": str,
        "timestamp": datetime
    }
    ```

---

### 2. Semantic Router Module
**File**: `src/adaptive_routing/modules/router.py`
**Class**: `SemanticRouterModule`
**Description**: Coordinates Logic Classification and Legal Generation.

#### Functions

##### `_process_routing_(self, normalized_text: str) -> dict`
-   **Logic**:
    1.  Calls `RoutingClassifier` to determine the route (e.g., `PATHWAY_1` for General, `PATHWAY_3` for Reasoning).
    2.  If the route is valid and not `PATHWAY_2` (Ambiguous), calls `LegalGenerator`.
    3.  Combines classification metadata and generated response.
-   **Return Value**:
    ```python
    {
        "classification": {
            "route": str,       # e.g., "PATHWAY_1"
            "confidence": float,
            "reasoning": str
        },
        "response_text": str    # The final AI-generated answer
    }
    ```

---

### 3. Core Engine
**File**: `src/adaptive_routing/core/engine.py`
**Class**: `LLMRequestEngine`
**Description**: Unified interface for OpenRouter API completions.

#### Functions

##### `_get_completion_(self, prompt: str, sys_message: str, images: list = None) -> str`
-   **Logic**:
    1.  Constructs the API payload with `model`, `temperature`, `max_tokens`.
    2.  Handles System Role: If `_use_system_role` is False, prepends system message to user prompt.
    3.  Handles Images: Encodes images to base64 or passes URLs.
    4.  Sends HTTP POST request to OpenRouter.
    5.  Parses response and handles errors (401, 404, 500, etc.).
-   **Return Value**: The generated text content (str).
-   **Exceptions**: `AuthenticationError`, `ModelNotFoundError`, `APIConnectionError`, `APIResponseError`.

##### `_encode_image_(self, image_source: str) -> dict`
-   **Logic**:
    -   If URL: returns `{"type": "image_url", ...}`.
    -   If Local File: Reads file, encodes to base64, returns data URI.
-   **Return Value**: Dictionary compatible with OpenAI/OpenRouter vision API.

---

## Error Handling
**File**: `src/adaptive_routing/core/exceptions.py`

Custom exceptions are defined to handle specific failure modes:
-   `AuthenticationError`: API key issues.
-   `ModelNotFoundError`: Invalid model name.
-   `APIConnectionError`: Network/Timeout issues.
-   `InvalidInputError`: Bad parameters (e.g., negative max_tokens).
-   `APIResponseError`: Upstream API errors.

## Usage Example (main.py)

```python
from src.adaptive_routing import FrameworkConfig, TriageModule, SemanticRouterModule

# 1. Update Config
FrameworkConfig._update_settings_(api_key="your-key")

# 2. Initialize
triage = TriageModule()
router = SemanticRouterModule()

# 3. Process
input_text = "I received a notice of termination."
triaged_data = triage._process_request_(input_text)
normalized_text = triaged_data.get("normalized_text")

if normalized_text:
    result = router._process_routing_(normalized_text)
    print(result['response_text'])
```
