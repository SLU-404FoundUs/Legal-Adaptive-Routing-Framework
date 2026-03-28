# Legal Adaptive Routing Framework — Documentation

> **Saint Louis University — Team 404FoundUs**  
> **Project**: LLM Legal Adaptive Routing Framework  
> **Purpose**: An AI-powered multi-stage pipeline for processing OFW legal queries across Philippine and Hong Kong jurisdictions.

---

## Overview

The **Legal Adaptive Routing Framework** is a modular system that processes legal queries through three intelligent stages:

1. **Linguistic Normalization** — Converts multilingual input (Tagalog, Taglish, Cantonese, etc.) into standardized legal English
2. **Semantic Routing** — Classifies queries by complexity and intent, routing to the appropriate LLM
3. **Legal Retrieval (RAG)** — Retrieves relevant legal provisions from a FAISS vector store to ground LLM responses in actual law

The framework communicates with LLMs through the **OpenRouter API** and uses **FAISS** for efficient vector similarity search.

---

## Architecture Diagram

```mermaid
flowchart TD
    subgraph Input
        User["👤 User Input<br/>(Tagalog / Taglish / English / Cantonese)"]
    end

    subgraph Triage["🔤 Triage Module"]
        direction TB
        LN["LinguisticNormalizer<br/><i>Multilingual → English</i>"]
        LD["LanguageStateDetector<br/><i>Stores state</i>"]
        LN --> LD
    end

    subgraph Router["🔀 Semantic Router Module"]
        direction TB
        RC["RoutingClassifier<br/><i>Intent classification</i>"]
        LG["LegalGenerator<br/><i>Dual-engine dispatch</i>"]
        RC --> LG
    end

    subgraph RAG["📚 Legal Retrieval Module"]
        direction TB
        EM["EmbeddingManager<br/><i>Embed + Index (JSON bypass)</i>"]
        LR["LegalRetriever<br/><i>Similarity search</i>"]
        FAISS["FAISS Vector Store<br/><i>HK & PH indices</i>"]
        EM --> FAISS
        LR --> FAISS
    end

    subgraph Generation["⚖️ Response Generation"]
        CASUAL["Casual-LLM<br/><i>Greetings / Small Talk</i>"]
        GEN["General-LLM<br/><i>Info / Definitions</i>"]
        REAS["Reasoning-LLM<br/><i>Case Analysis (ALAC)</i>"]
    end

    subgraph Core["⚙️ Core Engine"]
        ENGINE["LLMRequestEngine<br/><i>OpenRouter API</i>"]
        CONFIG["FrameworkConfig<br/><i>Centralized Settings</i>"]
    end

    User --> Triage
    Triage -->|Normalized English| Router
    Router -->|Route + Query| RAG
    RAG -->|Augmented Context| Generation
    CASUAL --> Response["📄 Legal Response"]
    GEN --> Response
    REAS --> Response

    ENGINE -.->|Powers| LN
    ENGINE -.->|Powers| RC
    ENGINE -.->|Powers| GEN
    ENGINE -.->|Powers| REAS
    CONFIG -.->|Configures| ENGINE
```

---

## Pipeline Flow

```
User Input (any language)
    │
    ▼
┌──────────────────────────────────────────┐
│  Stage 1: TRIAGE MODULE                  │
│  • LinguisticNormalizer normalizes text   │
│  • LanguageStateDetector stores state     │
│  Output: {normalized_text, language}      │
└──────────────┬───────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────┐
│  Stage 2: SEMANTIC ROUTER MODULE         │
│  • RoutingClassifier classifies intent   │
│  • Routes to General-LLM or Reasoning   │
│  Output: {route, confidence, signals}    │
└──────────────┬───────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────┐
│  Stage 3: LEGAL RETRIEVAL (RAG)          │
│  • Retrieves relevant law provisions     │
│  • FAISS vector similarity search        │
│  Output: {retrieved_chunks + scores}     │
└──────────────┬───────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────┐
│  Stage 4: RESPONSE GENERATION            │
│  • General-LLM → Info format             │
│  • Reasoning-LLM → ALAC format           │
│  Output: Grounded legal response         │
└──────────────────────────────────────────┘
```

---

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

**Required packages:**
- `requests` — HTTP client for OpenRouter API
- `python-dotenv` — Environment variable management
- `faiss-cpu==1.7.4` — Vector similarity search
- `numpy<2` — Numerical operations

### 2. Set Up Environment

Create a `.env` file at the project root:

```env
OPENROUTER_API_KEY=sk-or-v1-your-api-key-here
```

### 3. Basic Usage

```python
from src.adaptive_routing import TriageModule, SemanticRouterModule, LegalRetrievalModule

# Initialize modules
triage = TriageModule()
router = SemanticRouterModule()

# Process a query through the full pipeline
triage_result = triage._process_request_("Pwede ba akong mag-file ng case?")
normalized = triage_result["normalized_text"]

router_result = router._process_routing_(normalized)
print(router_result["response_text"])
```

---

## Module Documentation

Each module has its own comprehensive documentation with API reference, usage examples, and customization guides:

| # | Module | Documentation | Description |
|:---|:---|:---|:---|
| 1 | **Configuration** | [configuration.md](configuration.md) | `FrameworkConfig` — all settings, env variables, runtime overrides |
| 2 | **Core Engine** | [core_engine.md](core_engine.md) | `LLMRequestEngine` — API interface, multimodal support, exception hierarchy |
| 3 | **Triage Module** | [triage_module.md](triage_module.md) | `TriageModule` — linguistic normalization, language detection, state management |
| 4 | **Semantic Router** | [semantic_router_module.md](semantic_router_module.md) | `SemanticRouterModule` — intent classification, dual-engine response generation |
| 5 | **Legal Retrieval (RAG)** | [legal_retrieval_module.md](legal_retrieval_module.md) | `LegalRetrievalModule` — document ingestion, FAISS indexing, context retrieval |

---

## Directory Structure

```
src/
└── adaptive_routing/
    ├── __init__.py                          # Public exports: TriageModule, SemanticRouterModule,
    │                                        #   LegalRetrievalModule, FrameworkConfig
    ├── config.py                            # Centralized configuration hub
    │                                        #   → docs/configuration.md
    │
    ├── core/                                # Foundation layer
    │   ├── engine.py                        # LLMRequestEngine: OpenRouter API interface
    │   └── exceptions.py                    # Custom exception hierarchy
    │                                        #   → docs/core_engine.md
    │
    └── modules/                             # Feature modules
        │
        ├── triage.py                        # TriageModule (Orchestrator)
        ├── multihead_classifier/            # Triage sub-components
        │   ├── linguistic.py                #   LinguisticNormalizer
        │   └── detector.py                  #   LanguageStateDetector
        │                                    #   → docs/triage_module.md
        │
        ├── router.py                        # SemanticRouterModule (Orchestrator)
        ├── semantic_router/                 # Router sub-components
        │   ├── logic_classifier.py          #   RoutingClassifier
        │   └── legal_generation.py          #   LegalGenerator
        │                                    #   → docs/semantic_router_module.md
        │
        ├── retrieval.py                     # LegalRetrievalModule (Orchestrator)
        └── legal_retrieval/                 # RAG sub-components
            ├── embedding.py                 #   EmbeddingManager (chunking + FAISS)
            └── retriever.py                 #   LegalRetriever (context search)
                                             #   → docs/legal_retrieval_module.md
```

---

## Public API Summary

The framework exports **4 main classes** from `src.adaptive_routing`:

```python
from src.adaptive_routing import (
    TriageModule,           # Stage 1: Linguistic normalization
    SemanticRouterModule,   # Stage 2: Intent classification + generation
    LegalRetrievalModule,   # Stage 3: RAG retrieval
    FrameworkConfig          # Configuration management
)
```

### Key Methods at a Glance

| Module | Method | Purpose |
|:---|:---|:---|
| `TriageModule` | `_process_request_(text, image?)` | Normalize multilingual input → English |
| `SemanticRouterModule` | `_process_routing_(text, threshold?, persistence_level?)` | Classify intent → returns `{route, confidence, trigger_signals}` |
| `SemanticRouterModule` | `_generate_response_(classification, text, context?)` | Single-turn generation with confidence gate |
| `SemanticRouterModule` | `_generate_conversation_(classification, messages, context?)` | Multi-turn generation with confidence gate |
| `LegalRetrievalModule` | `_process_retrieval_(query, top_k?)` | Retrieve relevant legal text chunks |
| `LegalRetrievalModule` | `_ingest_documents_(docs)` | Add documents to the vector store |
| `LegalRetrievalModule` | `build_and_save_index(dir, out, prefix)` | Build FAISS index from JSON corpus |
| `LegalRetrievalModule` | `_save_index_(index, chunks)` | Persist index to disk |
| `LegalRetrievalModule` | `_load_index_(index, chunks)` | Load saved index |
| `FrameworkConfig` | `_update_settings_(**kwargs)` | Runtime configuration override |

---

## Environment Variables Reference

| Variable | Module | Default | Description |
|:---|:---|:---|:---|
| `OPENROUTER_API_KEY` | All | *(required)* | OpenRouter API credential |
| `TRIAGE_MODEL` | Triage | `qwen/qwen3-4b:free` | Normalization LLM |
| `TRIAGE_TEMP` | Triage | `0.6` | Temperature |
| `TRIAGE_MAX_TOKENS` | Triage | `1500` | Max tokens |
| `ROUTER_MODEL` | Router | `google/gemma-3-12b-it:free` | Classification LLM |
| `ROUTER_TEMP` | Router | `0.0` | Temperature |
| `GENERAL_MODEL` | Generation | `google/gemma-3-12b-it:free` | General info LLM |
| `GENERAL_TEMP` | Generation | `0.5` | Temperature |
| `REASONING_MODEL` | Generation | `google/gemma-3-12b-it:free` | Reasoning LLM |
| `REASONING_TEMP` | Generation | `0.7` | Temperature |
| `CASUAL_MODEL` | Generation | `google/gemma-3-12b-it:free` | Casual / small-talk LLM |
| `CASUAL_TEMP` | Generation | `0.8` | Temperature |
| `CASUAL_MAX_TOKENS` | Generation | `200` | Max tokens |
| `RETRIEVAL_MODEL` | RAG | `sentence-transformers/all-minilm-l6-v2` | Embedding model |
| `RETRIEVAL_TOP_K` | RAG | `5` | Chunks to retrieve |
| `RETRIEVAL_CHUNK_SIZE` | RAG | `5000` | Characters per chunk |
| `RETRIEVAL_INDEX_PATH` | RAG | `None` | Pre-built FAISS index path |
| `RETRIEVAL_CHUNKS_PATH` | RAG | `None` | Pre-built chunks JSON path |

> For the complete configuration reference with all parameters, see [configuration.md](configuration.md).
