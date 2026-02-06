# LLM Legal Adaptive Routing Framework

## Saint Louis University | Team 404FoundUs

A specialized framework designed for legal text inputs. It utilizes an adaptive routing system powered by OpenRouter LLMs to normalize linguistic variations (Taglish/Tagalog to English), detect language states, and prepare data for downstream legal processing.

## Project Structure

```
LegalAdaptiveRoutingFramework/
├── src/
│   └── adaptive_routing/
│       ├── config.py           # Centralized configuration
│       ├── core/
│       │   ├── engine.py       # LLM Request Engine (API Handler)
│       │   └── exceptions.py   # Custom Exception Classes
│       └── modules/
│           ├── linguistic.py   # Normalization Logic
│           ├── detector.py     # State Management
│           └── triage.py       # Orchestration Facade
├── tests/                      # Unit Tests
├── main.py                     # Driver Script
├── requirements.txt            # Dependencies
└── .env                        # Environment Variables (Not committed)
```

## Setup & Installation

1. **Clone the repository**:
   ```bash
   git clone <repository_url>
   cd LegalAdaptiveRoutingFramework
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment**:
   Create a `.env` file in the root directory:
   ```env
   OPENROUTER_API_KEY=your_api_key_here
   ```

## Developer Usage

### Quick Start (Main Framework)
Run the logical pipeline easily using the top-level exports.

```python
from src.adaptive_routing import TriageModule, SemanticRouterModule

# 1. Initialize Triage (Language Processing)
triage = TriageModule()
input_text = "Yung ano kasi, I was terminated without notice."
triage_result = triage._process_request_(input_text)
normalized_text = triage_result.get('normalized_text') # "I was terminated without notice."

# 2. Initialize Semantic Router (Legal Classification & Advice)
router = SemanticRouterModule()
if normalized_text:
    routing_output = router._process_routing_(normalized_text)
    print(routing_output['response_text'])
```

### Configuration (API Style)
You can configure the framework using environment variables OR by modifying the configuration object directly in your code.

**Option 1: Environment Variables (.env)**
```env
OPENROUTER_API_KEY=sk-or-v1-...
TRIAGE_MODEL=qwen/qwen-2.5-7b-instruct
TRIAGE_TEMP=0.5
```

**Option 2: Python Code Configuration**
```python
from src.adaptive_routing import FrameworkConfig

# Update API Key
FrameworkConfig._API_KEY = "sk-new-key-123"

# Update Model Parameters
FrameworkConfig._update_settings_(
    triage_model="google/gemini-2.0-flash-exp:free",
    triage_temp=0.1
)
```

### Advanced: Dependency Injection
The framework allows you to inject your own engines or prompts if you need deep customization.

```python
from src.adaptive_routing.modules.semantic_router.logic_classifier import RoutingClassifier

# Custom System Prompt
custom_prompt = "ROLE: Strict Judge. TASK: Classify this legally."

# Inject into Router
classifier = RoutingClassifier(system_prompt=custom_prompt)
# router = SemanticRouterModule(classifier=classifier) 
```

## Modules Guide

### 1. Triage Module (`src.adaptive_routing.modules.triage`)
The primary entry point for developers. It handles language detection and normalization in a single efficient step.

### 2. Linguistic Normalizer (`src.adaptive_routing.modules.linguistic`)
Handles the transformation of raw input into standardized English, strictly following legal objectivity standards.

### 3. LLM Request Engine (`src.adaptive_routing.core.engine`)
The core abstraction for interacting with the OpenRouter API. Handles authentication, retries, and error mapping.

### 4. Language State Detector (`src.adaptive_routing.modules.detector`)
A state container used by the Triage module to persist the processing context (Original vs Normalized vs Language).

## Development Guidelines

### Naming Conventions (PSAS Standards)
- **Functions**: Wrapped in underscores (e.g., `_process_request_`).
- **Global Constants**: Leading underscore + CAPS (e.g., `_DEFAULT_MODEL`).
- **Private/Protected Variables**: Leading underscore (e.g., `_api_key`).
- **Classes**: PascalCase (e.g., `TriageModule`).

### Documentation Tags
- `@file`, `@desc_`, `@func_`, `@params`, `@return_`, `@logic_`.

---
**Note**: This framework relies on `python-dotenv` for security. Never commit your `.env` file.
