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

## Modules & Usage

### 1. Triage Module (`src.adaptive_routing.modules.triage`)
The primary entry point for developers. It handles language detection and normalization in a single efficient step.

**Usage:**
```python
from src.adaptive_routing.modules.triage import TriageModule

# Initialize (loads API key from .env automatically)
triage = TriageModule()

input_text = "Yung ano kasi, I was terminated without notice."
result = triage._process_request_(input_text)

print(f"Language: {result['detected_language']}") # Output: Taglish
print(f"Normalized: {result['normalized_text']}") # Output: I was terminated without notice.
```

### 2. Linguistic Normalizer (`src.adaptive_routing.modules.linguistic`)
Handles the transformation of raw input into standardized English, strictly following legal objectivity standards.

- **Constraints**:
    - Converts subjective ("I feel") to objective ("Alleged").
    - Retains Latin legal terms (e.g., *void ab initio*).
    - Removes formatting noise and emotional hyperbole.

**Usage:**
```python
from src.adaptive_routing.core.engine import LLMRequestEngine
from src.adaptive_routing.modules.linguistic import LinguisticNormalizer

engine = LLMRequestEngine()
normalizer = LinguisticNormalizer(engine)

raw_output = normalizer._normalize_text_("Example text")
```

### 3. LLM Request Engine (`src.adaptive_routing.core.engine`)
The core abstraction for interacting with the OpenRouter API. Handles authentication, retries, and error mapping.

**Usage:**
```python
from src.adaptive_routing.core.engine import LLMRequestEngine

engine = LLMRequestEngine(temperature=0.3)
response = engine._get_completion_("Explain res ipsa loquitur", "You are a legal scholar.")
```

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

### Adding New Modules
1. Place new logic modules in `src/adaptive_routing/modules/`.
2. Ensure dependency on `LLMRequestEngine` for any AI operations.
3. Update `main.py` if necessary to demonstrate capabilities.

---
**Note**: This framework relies on `python-dotenv` for security. Never commit your `.env` file.
