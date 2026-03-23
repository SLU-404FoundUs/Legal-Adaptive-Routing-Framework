# Core Engine & Exceptions Reference

> **Files**: `src/adaptive_routing/core/engine.py`, `src/adaptive_routing/core/exceptions.py`

The **Core Engine** is the foundational networking layer of the framework. It handles all communication with the OpenRouter API, including authentication, payload construction, multimodal support, and structured error handling.

---

## Table of Contents

- [LLMRequestEngine](#llmrequestengine)
  - [Constructor](#constructor)
  - [Methods](#methods)
    - [_get_completion_()](#_get_completion_)
    - [_get_chat_completion_()](#_get_chat_completion_)
    - [_encode_image_()](#_encode_image_)
  - [System Role Behavior](#system-role-behavior)
  - [Reasoning Mode](#reasoning-mode)
- [Exception Hierarchy](#exception-hierarchy)
  - [AdaptiveRoutingError (Base)](#adaptiveroutingerror-base)
  - [AuthenticationError](#authenticationerror)
  - [ConfigurationError](#configurationerror)
  - [ModelNotFoundError](#modelnotfounderror)
  - [APIConnectionError](#apiconnectionerror)
  - [InvalidInputError](#invalidinputerror)
  - [APIResponseError](#apiresponseerror)
- [Error Handling Patterns](#error-handling-patterns)
- [Customization Guide](#customization-guide)

---

## LLMRequestEngine

**Import**: `from src.adaptive_routing.core.engine import LLMRequestEngine`

The unified interface for all OpenRouter API completions. Used internally by all modules; can also be used directly for custom LLM workflows.

### Constructor

```python
LLMRequestEngine(
    api_key: str = None,
    model: str = None,
    temperature: float = None,
    max_tokens: int = None,
    use_system_role: bool = None,
    include_reasoning: bool = None
)
```

| Parameter | Type | Default | Description |
|:---|:---|:---|:---|
| `api_key` | `str` | `FrameworkConfig._API_KEY` | OpenRouter API key. Raises `AuthenticationError` if missing. |
| `model` | `str` | `FrameworkConfig._DEFAULT_MODEL` | OpenRouter model identifier (e.g., `"google/gemma-3-12b-it:free"`). |
| `temperature` | `float` | `FrameworkConfig._TEMPERATURE` (0.7) | Controls randomness. Range: `0.0` to `2.0`. Raises `InvalidInputError` if out of range. |
| `max_tokens` | `int` | `FrameworkConfig._MAX_TOKENS` (1500) | Maximum response length. Must be positive. |
| `use_system_role` | `bool` | `FrameworkConfig._USE_SYSTEM_ROLE` (True) | If `True`, system instructions are sent as a `system` role message. If `False`, they are prepended to the user prompt. |
| `include_reasoning` | `bool` | `FrameworkConfig._INCLUDE_REASONING` (False) | If `True`, requests chain-of-thought reasoning from the model and wraps it in `<reasoning>` tags. |

**Validation on construction:**
- `api_key` must be a non-empty string → raises `AuthenticationError`
- `model` must be a non-empty string → raises `InvalidInputError`
- `temperature` must be in `[0.0, 2.0]` → raises `InvalidInputError`
- `max_tokens` must be `> 0` → raises `InvalidInputError`

**Example:**

```python
from src.adaptive_routing.core.engine import LLMRequestEngine

engine = LLMRequestEngine(
    api_key="sk-or-v1-your-key",
    model="google/gemma-3-12b-it:free",
    temperature=0.5,
    max_tokens=1000
)
```

---

### Methods

#### `_get_completion_()`

```python
def _get_completion_(self, prompt: str, sys_message: str, images: list = None) -> str
```

The primary method for single-turn LLM completions.

| Parameter | Type | Required | Description |
|:---|:---|:---|:---|
| `prompt` | `str` | Yes | The user's input prompt |
| `sys_message` | `str` | Yes | System instruction (role/persona) |
| `images` | `list[str]` | No | List of image file paths or URLs for multimodal input |

**Returns**: `str` — The LLM's response text. If `include_reasoning` is `True` and reasoning is available, the response includes `<reasoning>` tags followed by the content.

**Response format with reasoning enabled:**

```
<reasoning>
Step-by-step analysis of the query...
</reasoning>

The final answer content here.
```

**Example — Text-only completion:**

```python
response = engine._get_completion_(
    prompt="What are the rights of domestic workers in Hong Kong?",
    sys_message="You are a legal information assistant specializing in labor law."
)
print(response)
```

**Example — Multimodal (with image):**

```python
response = engine._get_completion_(
    prompt="Describe all the legal provisions shown in this contract:",
    sys_message="You are a contract analysis assistant.",
    images=["/path/to/contract_photo.jpg"]
)
```

**Example — Multimodal (with URL):**

```python
response = engine._get_completion_(
    prompt="Analyze this legal document:",
    sys_message="You are a legal document analyzer.",
    images=["https://example.com/document.png"]
)
```

**Exceptions raised:**
- `AuthenticationError` — Invalid API key (HTTP 401)
- `ModelNotFoundError` — Invalid model or endpoint (HTTP 404)
- `APIResponseError` — Non-200 responses, insufficient credits (HTTP 402), or malformed response JSON
- `APIConnectionError` — Network failures, timeouts (30s default), or other request errors

---

#### `_get_chat_completion_()`

```python
def _get_chat_completion_(self, messages: list[dict]) -> str
```

For multi-turn conversational completions. Accepts a full conversation history.

| Parameter | Type | Required | Description |
|:---|:---|:---|:---|
| `messages` | `list[dict]` | Yes | List of message dicts with `role` and `content` keys |

**Message format:**

```python
messages = [
    {"role": "system", "content": "You are a legal assistant."},
    {"role": "user", "content": "What is the Labor Code?"},
    {"role": "assistant", "content": "The Labor Code is a comprehensive set of laws..."},
    {"role": "user", "content": "How does it apply to overseas workers?"}
]
```

**Returns**: `str` — The LLM's response text.

**System role handling**: If `use_system_role` is `False`, system messages are merged into the first user message automatically.

**Example:**

```python
response = engine._get_chat_completion_([
    {"role": "system", "content": "ROLE: Philippine Labor Law Expert"},
    {"role": "user", "content": "What are the grounds for illegal dismissal?"},
])
print(response)
```

---

#### `_encode_image_()`

```python
def _encode_image_(self, image_source: str) -> dict
```

Internal helper method for encoding images into API-compatible payloads.

| Parameter | Type | Description |
|:---|:---|:---|
| `image_source` | `str` | A **file path** or an **HTTP(S) URL** to an image |

**Behavior:**
- **URL inputs** (`http://` or `https://`): Returns the URL as-is in the API payload
- **File path inputs**: Base64-encodes the image file content with auto-detected MIME type

**Returns**: `dict` — A JSON-compatible image payload in the format:

```python
{"type": "image_url", "image_url": {"url": "..."}}
```

**Supported image formats**: JPEG, PNG, GIF, WebP, BMP (any format detectable by `mimetypes`)

**Exceptions:**
- `InvalidInputError` — File not found at the specified path

---

### System Role Behavior

The `use_system_role` parameter controls how system instructions are delivered to the LLM:

| `use_system_role` | Behavior |
|:---|:---|
| `True` (default) | System message is sent as a separate `{"role": "system"}` message in the API payload |
| `False` | System message is **prepended** to the user's prompt as a combined `{"role": "user"}` message |

**When to use `False`:**
- Some models on OpenRouter don't support the `system` role natively
- The Router module uses `False` by default since its model (`gemma-3-12b-it`) works better with instructions in the user prompt

---

### Reasoning Mode

When `include_reasoning` is `True`:

1. The API request includes `"include_reasoning": true` in the payload
2. If the model returns a `reasoning` field in its response, it is wrapped in `<reasoning>` tags and prepended to the content
3. If no reasoning is returned, only the content is returned as normal

**Response with reasoning:**

```
<reasoning>
The user is asking about a specific employment situation involving contract termination.
This falls under the Hong Kong Employment Ordinance, Chapter 57...
</reasoning>

Based on the Employment Ordinance...
```

---

## Exception Hierarchy

All framework exceptions inherit from `AdaptiveRoutingError`, allowing you to catch all framework errors with a single handler.

```
AdaptiveRoutingError (Base)
├── AuthenticationError
├── ConfigurationError
├── ModelNotFoundError
├── APIConnectionError
├── InvalidInputError
└── APIResponseError
```

**Import**: `from src.adaptive_routing.core.exceptions import <ExceptionClass>`

### AdaptiveRoutingError (Base)

Base exception for all errors in the Adaptive Routing Framework. Catch this to handle any framework error generically.

### AuthenticationError

Raised when API keys are missing or invalid.

**Trigger conditions:**
- No API key provided in constructor argument **and** no `OPENROUTER_API_KEY` environment variable
- OpenRouter returns HTTP 401 (invalid key)

### ConfigurationError

Raised when essential configuration is missing.

### ModelNotFoundError

Raised when the specified model is invalid or unavailable.

**Trigger conditions:**
- OpenRouter returns HTTP 404 (model not found or endpoint invalid)

### APIConnectionError

Raised when the API request fails due to network issues or timeouts.

**Trigger conditions:**
- Network connection failure
- Request timeout (30 seconds)
- Any unexpected `RequestException`

### InvalidInputError

Raised when input parameters are out of valid range.

**Trigger conditions:**
- `temperature` outside `[0.0, 2.0]`
- `max_tokens <= 0`
- Invalid model string (empty or non-string)
- Empty text passed to chunking
- Image file not found

### APIResponseError

Raised when the API returns an error response (non-200 status).

**Additional attributes:**

| Attribute | Type | Description |
|:---|:---|:---|
| `status_code` | `int` or `None` | HTTP status code from the failed response |
| `response_body` | `str` or `dict` or `None` | Raw response payload for debugging |

**Trigger conditions:**
- HTTP error responses (402 insufficient credits, 5xx server errors, etc.)
- Missing or empty `choices` in the response JSON
- JSON decode failure on the response

---

## Error Handling Patterns

### Pattern 1: Catch All Framework Errors

```python
from src.adaptive_routing.core.engine import LLMRequestEngine
from src.adaptive_routing.core.exceptions import AdaptiveRoutingError

try:
    engine = LLMRequestEngine()
    result = engine._get_completion_("Legal question", "System prompt")
except AdaptiveRoutingError as e:
    print(f"Framework error: {e}")
```

### Pattern 2: Granular Error Handling

```python
from src.adaptive_routing.core.exceptions import (
    AuthenticationError,
    ModelNotFoundError,
    APIConnectionError,
    APIResponseError,
    InvalidInputError
)

try:
    engine = LLMRequestEngine(api_key="sk-or-v1-xxx")
    result = engine._get_completion_("Query", "Instructions")

except AuthenticationError:
    print("Check your API key in .env")

except ModelNotFoundError as e:
    print(f"Model unavailable: {e}")

except APIConnectionError:
    print("Network issue — check your connection")

except APIResponseError as e:
    print(f"API error (HTTP {e.status_code}): {e}")
    if e.response_body:
        print(f"Response body: {e.response_body}")

except InvalidInputError as e:
    print(f"Bad input: {e}")
```

### Pattern 3: Retry on Transient Errors

```python
import time
from src.adaptive_routing.core.exceptions import APIConnectionError, APIResponseError

def resilient_completion(engine, prompt, sys_message, retries=3):
    for attempt in range(retries):
        try:
            return engine._get_completion_(prompt, sys_message)
        except APIConnectionError:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
                continue
            raise
        except APIResponseError as e:
            if e.status_code and e.status_code >= 500:
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)
                    continue
            raise
```

---

## Customization Guide

### Creating a Standalone Engine

For workflows outside the standard pipeline (e.g., custom prompts, different models):

```python
from src.adaptive_routing.core.engine import LLMRequestEngine

# Summarization engine with low temperature
summarizer = LLMRequestEngine(
    model="google/gemma-3-12b-it:free",
    temperature=0.2,
    max_tokens=500,
    use_system_role=True
)

summary = summarizer._get_completion_(
    prompt="Summarize this legal provision: ...",
    sys_message="You are a legal document summarizer."
)
```

### Using a Custom Engine in Modules

Every module accepts a pre-configured `engine` or `handler` parameter. This lets you override the default engine without touching `FrameworkConfig`:

```python
from src.adaptive_routing.core.engine import LLMRequestEngine
from src.adaptive_routing.modules.triage import TriageModule

custom_engine = LLMRequestEngine(
    api_key="sk-or-v1-custom-key",
    model="openai/gpt-4o:free",
    temperature=0.3,
    max_tokens=2000,
    use_system_role=True,
    include_reasoning=True
)

triage = TriageModule(engine=custom_engine)
result = triage._process_request_("User query here")
```

### Multimodal Workflow (Images)

```python
engine = LLMRequestEngine(
    model="google/gemma-3-12b-it:free",
    use_system_role=True
)

# Local file
response = engine._get_completion_(
    prompt="What legal clauses are visible in this contract?",
    sys_message="Legal contract analyzer.",
    images=["/path/to/contract.jpg"]
)

# Multiple images (local + URL)
response = engine._get_completion_(
    prompt="Compare these two documents:",
    sys_message="Document comparison assistant.",
    images=[
        "/path/to/doc1.png",
        "https://example.com/doc2.png"
    ]
)
```
