# Legal Adaptive Routing Framework (LARF)

<div align="center">

### Saint Louis University | Team 404FoundUs

**An Agentic AI Framework for Processing Philippine Legal Queries**

[Documentation](docs/DOCUMENTATION.md) • [Report Bug](issues) • [Request Feature](issues)

</div>

## 📖 Overview

The **Legal Adaptive Routing Framework (LARF)** is a specialized Python framework designed to bridge the gap between informal user queries (often in Taglish) and formal legal reasoning.

It uses a multi-stage **Agentic Pipeline** to:
1.  **Normalize**: Translate linguistic variations (Taglish/Tagalog) into standard legal English.
2.  **Classify**: Intelligently route queries to the correct domain (General Info vs. Complex Reasoning).
3.  **Generate**: Produce legally grounded responses using specialized LLMs.

---

## 🏗️ Project Structure

The codebase is organized into modular components for scalability.

```text
LegalAdaptiveRoutingFramework/
├── src/
│   └── adaptive_routing/
│       ├── config.py           # Global Configuration
│       ├── core/               # Low-level Engine
│       │   ├── engine.py       # OpenRouter API Handler
│       │   └── exceptions.py   # Custom Errors
│       └── modules/
│           ├── multihead_classifier/   # Triage Components
│           │   ├── detector.py
│           │   └── linguistic.py
│           ├── semantic_router/        # Routing Components
│           │   ├── legal_generation.py
│           │   └── logic_classifier.py
│           ├── router.py       # Router Facade
│           └── triage.py       # Triage Facade
├── tests/                      # Unit Tests
├── docs/                       # Documentation
├── main.py                     # CLI Driver Script
├── requirements.txt            # Python Dependencies
└── .env                        # Secrets (Excluded from Git)
```

---

## ⚡ Quick Start

### Prerequisites
-   Python 3.10+
-   [OpenRouter](https://openrouter.ai/) API Key

### Installation

1.  **Clone the repository**
    ```bash
    git clone https://github.com/SLU-404FoundUs/Legal-Adaptive-Routing-Framework.git
    cd Legal-Adaptive-Routing-Framework
    ```

2.  **Install dependencies**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Setup Environment**
    Create a `.env` file in the root directory:
    ```env
    OPENROUTER_API_KEY=your_api_key_here
    # Optional Overrides
    TRIAGE_MODEL=google/gemma-3-4b-it:free
    ```

### Usage

Run the main driver script to see the pipeline in action:

```bash
python main.py
```

Or import the modules into your own application:

```python
from src.adaptive_routing import TriageModule, SemanticRouterModule

# 1. Initialize Modules
triage = TriageModule()
router = SemanticRouterModule()

# 2. Process Input (Taglish -> English)
input_text = "Tinanggal ako sa trabaho ng walang notice."
result = triage._process_request_(input_text)
normalized_text = result['normalized_text'] 
# Output: "I was terminated from my job without notice."

# 3. Route & Generate Legal Response
if normalized_text:
    response = router._process_routing_(normalized_text)
    print(f"Advice: {response['response_text']}")
```

---

## 📚 Documentation

For detailed API references, configuration options, and architectural diagrams, please refer to the **[Full Documentation](docs/DOCUMENTATION.md)**.

---

## 🤝 Contribution

Contributions are welcome! Please ensure that you follow the **Technical Documentation Standards** when adding new modules.

1.  Fork the Project
2.  Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3.  Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4.  Push to the Branch (`git push origin feature/AmazingFeature`)
5.  Open a Pull Request

