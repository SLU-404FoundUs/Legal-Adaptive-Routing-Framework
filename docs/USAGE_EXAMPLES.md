# Legal Adaptive Routing Framework — Usage Examples

This guide provides centralized, copy-pasteable snippets for using the framework, ranging from basic module interactions to advanced custom configurations.

## Table of Contents
1. [Configuration Examples](#configuration-examples)
2. [Triage Module Examples](#triage-module-examples)
3. [Semantic Router Examples](#semantic-router-examples)
4. [Legal Retrieval (RAG) Examples](#legal-retrieval-rag-examples)
5. [End-to-End Advanced Pipeline Example](#end-to-end-advanced-pipeline-example)
6. [Core Engine Errors & Resilience](#core-engine-errors--resilience)

---

## Configuration Examples

The framework uses a centralized configuration object `FrameworkConfig`. You can manipulate these at runtime to change module behavior dynamically, or define them in your `.env` file. These configurations map precisely to `config.py`.

### 1. Basic Environment Setup (`.env`)
Create a `.env` file in your project root to handle static configurations:
```env
OPENROUTER_API_KEY=sk-or-v1-my-api-key
TRIAGE_MODEL=qwen/qwen-turbo
ROUTER_TEMP=0.0
```

### 2. Runtime Global Configuration Override
Modify configurations at runtime. **Important:** Call this before initializing your module objects, as existing objects will not pick up retroactive config updates.
```python
from src.adaptive_routing import FrameworkConfig

FrameworkConfig._update_settings_(
    triage_model="google/gemma-3-12b-it:free",
    triage_temp=0.3,          # Lower temperature for consistency
    triage_max_tokens=2000,
    router_temp=0.0,          # 0.0 is best for deterministic routing
    retrieval_top_k=8,        # Fetch more context chunks
    retrieval_chunk_size=1024 # Optimize chunk parameters
)
```

---

## Triage Module Examples
The Triage Module normalizes raw, mixed-language input (Taglish/Cantonese) into formal English.

### 1. Basic Translation and Normalization
```python
from src.adaptive_routing import TriageModule

triage = TriageModule()

# Taglish input
result = triage._process_request_(
    "Yung boss ko kasi, hindi niya binayaran yung overtime ko for 3 months na."
)

print(f"Normalized: {result['normalized_text']}")
# -> "Alleged non-payment of overtime wages by the employer over a period of three months."
print(f"Original Language: {result['detected_language']}")
# -> "Taglish"
```

### 2. Multimodal Normalization (Image Input)
```python
# Using a local file
result_local = triage._process_request_(
    "Ano yung sinasabi dito sa contract na 'to?",
    image_path="/path/to/contract_photo.jpg"
)

# Using an HTTP URL
result_remote = triage._process_request_(
    "What does this document say?",
    image_path="https://example.com/document.png"
)
```

### 3. Advanced: Custom Triage LLM Engine Injection
If you need isolated configuration for a single module instance without affecting the global `FrameworkConfig`.
```python
from src.adaptive_routing.core.engine import LLMRequestEngine
from src.adaptive_routing import TriageModule

custom_engine = LLMRequestEngine(
    api_key="sk-or-v1-custom-key",
    model="deepseek/deepseek-r1:free",
    temperature=0.1,
    max_tokens=2000,
    use_system_role=False,
    include_reasoning=True
)

triage = TriageModule(engine=custom_engine)
```

---

## Semantic Router Examples
The Router dictates whether to handle the query playfully (Casual), provide direct info (General), or perform a detailed case analysis (Reasoning).

### 1. Basic Routing Classification
Get a route classification without executing an LLM response pipeline.
```python
from src.adaptive_routing.modules.semantic_router.logic_classifier import RoutingClassifier

classifier = RoutingClassifier()
classification = classifier._route_query_("What are my rights as an OFW in HK?")

print(classification['route'])           # -> "General-LLM"
print(classification['confidence'])      # -> 0.95
print(classification['trigger_signals']) # -> ["rights overview", "general information"]
```

### 2. Single-Turn Generation
Processes the classification and delegates generation to the correct underlying LLM model.
```python
from src.adaptive_routing import SemanticRouterModule

router = SemanticRouterModule()

normalized_text = "The individual asks about the definition of illegal dismissal."

# Attempt classification with a confidence threshold
classification_data = router._process_routing_(normalized_text, threshold=0.8)

# Output generation
response_data = router._generate_response_(classification_data, normalized_text)

print(response_data['response_text'])
```

### 3. Advanced Conversation / Multi-turn Support
Track interactions iteratively across a conversational session.
```python
from src.adaptive_routing.modules.semantic_router.legal_generation import LegalGenerator
from src.adaptive_routing.config import FrameworkConfig

generator = LegalGenerator()

messages = [
    {"role": "system", "content": FrameworkConfig._GENERAL_INSTRUCTIONS},
    {"role": "user", "content": "What is the minimum wage in Hong Kong?"},
]

# Provide context history + current response tracking
response_1 = generator._dispatch_conversation_(messages, "General-LLM")
messages.append({"role": "assistant", "content": response_1})

# Next Follow-up
messages.append({"role": "user", "content": "How does it compare to the Philippines?"})
response_2 = generator._dispatch_conversation_(messages, "General-LLM")
```

---

## Legal Retrieval (RAG) Examples
Store, search, and augment queries with context derived from FAISS-indexed legal files.

### 1. Incremental Document Ingestion and Simple Search
```python
from src.adaptive_routing import LegalRetrievalModule

retriever = LegalRetrievalModule()

docs = [
    "Article 279 of the Philippine Labor Code states...",
    "Section 31I of the Hong Kong Employment Ordinance observes..."
]

# Chunk & Embed into FAISS Vector Store
retriever._ingest_documents_(docs)

results = retriever._process_retrieval_("Can I be fired without a stated cause?", top_k=2)

for item in results["retrieved_chunks"]:
    print(f"Similarity Score (L2 Dist): {item['score']:.4f}")
    print(f"Document Text: {item['chunk'][:100]}...\n")
```

### 2. Persisting and Auto-Loading a Vector Index
```python
from src.adaptive_routing import LegalRetrievalModule

retriever = LegalRetrievalModule()

# Read corpus directory and output binary maps natively
faiss_path = retriever.build_and_save_index(
    corpus_dir="legal-corpus/PH",
    output_dir="Faiss",
    index_prefix="ph_index"
)
print(f"Saved: {faiss_path}")
```
To auto-load an index on component boot, refer to explicit environment setups:
```env
RETRIEVAL_INDEX_PATH=Faiss/ph_index.faiss
RETRIEVAL_CHUNKS_PATH=Faiss/ph_index.json
```
or inject them during initialization:
```python
retriever = LegalRetrievalModule(
    index_path="Faiss/ph_index.faiss",
    chunks_path="Faiss/ph_index.json"
)
```

---

## End-to-End Advanced Pipeline Example
This ties together linguistic normalization, complex dual-index RAG lookup, intent classification, and an ultimate, strictly-grounded response.

```python
from src.adaptive_routing import TriageModule, SemanticRouterModule, LegalRetrievalModule

# 1. Init modules
triage = TriageModule()
router = SemanticRouterModule()

# 2. Boot parallel RAG retrievers per jurisdiction
hk_retriever = LegalRetrievalModule(
    index_path="Faiss/hk_index.faiss",
    chunks_path="Faiss/hk_index.json"
)
ph_retriever = LegalRetrievalModule(
    index_path="Faiss/ph_index.faiss",
    chunks_path="Faiss/ph_index.json"
)

# 3. Triage
user_query = "Pinalayas ako ng amo ko sa HK, pwede ba i-demand ko na pauwiin or bayaran nyo the rest nang contract?"
triage_result = triage._process_request_(user_query)
normalized = triage_result["normalized_text"]

# 4. Route Calculation
route_result = router._process_routing_(normalized, threshold=0.8)

# 5. RAG Collection Multi-Index
hk_chunks = hk_retriever._process_retrieval_(normalized, top_k=3)["retrieved_chunks"]
ph_chunks = ph_retriever._process_retrieval_(normalized, top_k=2)["retrieved_chunks"]

context_assembly = (
    "HONG KONG JURISPRUDENCE:\n" + "\n".join([f"- {c['chunk']}" for c in hk_chunks]) + "\n\n"
    "PHILIPPINE JURISPRUDENCE:\n" + "\n".join([f"- {c['chunk']}" for c in ph_chunks])
)

# 6. Final Trigger Sequence
final_output = router._generate_response_(route_result, normalized, context=context_assembly)

print(final_output["response_text"])
```

---

## Core Engine Errors & Resilience
Handling errors efficiently with the central API engine wrapper.

### 1. Robust Exponent Backoff Pattern
Wrap simple engine calls in resilient decorators for production stability.
```python
import time
from src.adaptive_routing.core.engine import LLMRequestEngine
from src.adaptive_routing.core.exceptions import APIConnectionError, APIResponseError

engine = LLMRequestEngine()

def resilient_completion(prompt, sys_message, retries=3):
    for attempt in range(retries):
        try:
            return engine._get_completion_(prompt, sys_message)
        except APIConnectionError:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)  # 1s, 2s, 4s...
                continue
            raise
        except APIResponseError as e:
            # Only retry on 5xx server errors
            if e.status_code and e.status_code >= 500 and attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise

print(resilient_completion("Explain unlawful dismissal.", "You are a legal bot."))
```
