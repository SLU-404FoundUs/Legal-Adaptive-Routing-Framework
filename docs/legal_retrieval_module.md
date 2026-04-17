# Legal Retrieval Module Reference (RAG)

> **Orchestrator**: `src/adaptive_routing/modules/retrieval.py`  
> **Sub-components**:  
> - `src/adaptive_routing/modules/legal_retrieval/embedding.py`  
> - `src/adaptive_routing/modules/legal_retrieval/retriever.py`

The **Legal Retrieval Module** implements the **Retrieval-Augmented Generation (RAG)** pipeline. It ingests legal documents, converts them into vector embeddings, stores them in a FAISS index, and retrieves the most semantically relevant chunks for any given query. This module is essential for grounding LLM responses in actual legal text.

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [LegalRetrievalModule (Orchestrator)](#legalretrievalmodule-orchestrator)
  - [Constructor](#constructor)
  - [_ingest_documents_()](#_ingest_documents_)
  - [_process_retrieval_()](#_process_retrieval_)
  - [Signal-Guided Retrieval](#signal-guided-retrieval)
  - [Context Reuse](#context-reuse)
  - [_save_index_()](#_save_index_)
  - [_load_index_()](#_load_index_)
  - [build_and_save_index()](#build_and_save_index)
- [EmbeddingManager (Sub-component)](#embeddingmanager-sub-component)
  - [Constructor](#embeddingmanager-constructor)
  - [_chunk_text_()](#_chunk_text_)
  - [_get_embeddings_()](#_get_embeddings_)
  - [_add_documents_()](#_add_documents_)
  - [_search_()](#_search_)
  - [_save_index_() / _load_index_()](#embeddingmanager-save--load)
- [LegalRetriever (Sub-component)](#legalretriever-sub-component)
  - [Constructor](#legalretriever-constructor)
  - [_retrieve_context_()](#_retrieve_context_)
- [JSON Corpus Format](#json-corpus-format)
- [Developer Utilities (utils)](#developer-utilities-utils)
  - [legal_indexing Module](#legal_indexing-module)
  - [Rebuilding the Index](#rebuilding-the-index)
  - [Sync Validation](#sync-validation)
- [Usage Examples](#usage-examples)
- [Customization Guide](#customization-guide)

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────┐
│                  LegalRetrievalModule                        │
│                     (Orchestrator)                           │
│                                                              │
│  ┌────────────────────────┐    ┌──────────────────────────┐  │
│  │   EmbeddingManager     │    │    LegalRetriever        │  │
│  │                        │    │                          │  │
│  │  - Text chunking       │    │  - Context retrieval     │  │
│  │  - Embedding via API   │◀───│  - Delegates to          │  │
│  │  - FAISS index mgmt    │    │    EmbeddingManager      │  │
│  │  - Save/load index     │    │    ._search_()           │  │
│  └────────────────────────┘    └──────────────────────────┘  │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │               Hybrid Vector & BM25 Store               │  │
│  │         (IndexFlatL2 Core + BM25 Keyword Index)        │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

**Data flow — Ingestion:**
1. Raw documents → `_ingest_documents_()` → `EmbeddingManager._add_documents_()`
2. (Optional) Documents bypass chunk fragmentation entirely to preserve JSON integrity, or are split via `_chunk_text_()`
3. Content is sent to OpenRouter `/embeddings` endpoint → `_get_embeddings_()`
4. Embeddings added to FAISS `IndexFlatL2` index

**Data flow — Retrieval:**
1. Query → `_process_retrieval_()` → `LegalRetriever._retrieve_context_()`
2. Signal-Guided Search: If search signals (keywords) are provided by the Semantic Router, they are combined with the query.
3. Hybrid Search: FAISS nearest-neighbor search + BM25 keyword search → results combined via Reciprocal Rank Fusion (RRF)
4. Context Reuse: If the user query is a follow-up (no new signals), the system can reuse the last retrieved context.
5. Results are deduplicated and parent context is injected if available

---

## LegalRetrievalModule (Orchestrator)

**Import**: `from src.adaptive_routing import LegalRetrievalModule`  
**Or**: `from src.adaptive_routing.modules.retrieval import LegalRetrievalModule`

### Constructor

```python
LegalRetrievalModule(
    api_key: str = None,
    embedding_manager: EmbeddingManager = None,
    retriever: LegalRetriever = None,
    index_path: str = None,
    chunks_path: str = None
)
```

| Parameter | Type | Default | Description |
|:---|:---|:---|:---|
| `api_key` | `str` | `FrameworkConfig._API_KEY` | OpenRouter API key for embedding generation |
| `embedding_manager` | `EmbeddingManager` | Auto-created with Retrieval config | Custom embedding manager instance |
| `retriever` | `LegalRetriever` | Auto-created with the embedding manager | Custom retriever instance |
| `index_path` | `str` | `FrameworkConfig._RETRIEVAL_INDEX_PATH` | Path to a pre-built `.faiss` index file |
| `chunks_path` | `str` | `FrameworkConfig._RETRIEVAL_CHUNKS_PATH` | Path to linked `.json` chunks file |

**Auto-loading behavior**: If `index_path` and `chunks_path` are provided (via arguments or `FrameworkConfig`), the module automatically loads the pre-built index at initialization. If the files don't exist, a warning is printed and the module starts with an empty index.

**Default embedding configuration** (from `FrameworkConfig`):

| Parameter | Config Source | Default Value |
|:---|:---|:---|
| Model | `_RETRIEVAL_MODEL` | `"sentence-transformers/all-minilm-l6-v2"` |
| Chunk Size | `_RETRIEVAL_CHUNK_SIZE` | `15000` characters |
| Chunk Overlap | `_RETRIEVAL_CHUNK_OVERLAP` | `0` characters |
| Top K | `_RETRIEVAL_TOP_K` | `5` results |

**Basic instantiation:**

```python
from src.adaptive_routing import LegalRetrievalModule

# Empty index — ready to ingest documents
retriever = LegalRetrievalModule()

# Auto-load pre-built index
retriever = LegalRetrievalModule(
    index_path="Faiss/hk_index.faiss",
    chunks_path="Faiss/hk_index.json"
)
```

---

### `_ingest_documents_()`

```python
def _ingest_documents_(self, documents: list[str])
```

Chunks, embeds, and indexes documents into the FAISS vector store.

| Parameter | Type | Required | Description |
|:---|:---|:---|:---|
| `documents` | `list[str]` | Yes | Raw legal document texts to add to the knowledge base |

**Returns**: `None`

**Example:**

```python
docs = [
    "Article 279 of the Philippine Labor Code provides that...",
    "The Hong Kong Employment Ordinance, Cap. 57, states that..."
]
retriever._ingest_documents_(docs)
```

---

### `_process_retrieval_()`

```python
def _process_retrieval_(self, query: str, signals: list = None, top_k: int = None) -> dict
```

The **main entry point** for retrieval. Returns the most relevant document chunks for a given query.

| Parameter | Type | Required | Description |
|:---|:---|:---|:---|
| `query` | `str` | Yes | The user's legal question |
| `signals` | `list` | No | Keyword phrases from the Semantic Router to guide search. |
| `top_k` | `int` | No | Override for number of chunks to retrieve (default: `FrameworkConfig._RETRIEVAL_TOP_K`) |

**Returns**: `dict`

```python
{
    "query": str,                      # The original query string
    "retrieved_chunks": [              # List of relevant chunks, ranked by similarity
        {
            "chunk": str,              # The raw text chunk or parent context from the index
            "metadata": dict,          # Dictionary tracking jurisdiction, title, source_file, category, and parent_context
            "score": float             # RRF (Reciprocal Rank Fusion) score (higher = more similar)
        },
        ...
    ]
}
```

**Understanding scores**: The `score` value is an RRF (Reciprocal Rank Fusion) score combining FAISS L2 distance and BM25 relevance ranking. **Higher scores indicate higher semantic and keyword similarity.**

| Score Range | Interpretation |
|:---|:---|
| `> 0.03` | High similarity |
| `0.015 – 0.03` | Moderate similarity |
| `< 0.015` | Low similarity |

> **Note**: Score thresholds depend on the retrieval algorithm parameters. The system automatically bypasses explicit cosine similarity thresholds when RRF scoring is detected to preserve optimal hybrid results. 
> 
> **Parent Context Injection**: During retrieval, if a chunk contains a `parent_context` metadata key, the retriever will automatically deduplicate results and inject the broader contiguous parent text as the retrieval chunk, rather than just the isolated line.

---

### Signal-Guided Retrieval

When the `SemanticRouterModule` identifies specific legal entities or actions, it generates **Search Signals**. These are concise keywords that are appended to the user's query before performing the hybrid search. This significantly improves RAG precision by grounding the search in confirmed legal concepts.

### Context Reuse

For follow-up questions where no new legal signals are detected (e.g., "Tell me more about the first point"), the framework reuses the `last_rag_context` stored in the session state. This avoids redundant API calls and ensures continuity in the legal analysis.

---

### `_save_index_()`

```python
def _save_index_(self, index_path: str, chunks_path: str)
```

Persists the current FAISS index and text chunks to disk.

| Parameter | Type | Required | Description |
|:---|:---|:---|:---|
| `index_path` | `str` | Yes | File path for the FAISS index binary (e.g., `"Faiss/my_index.faiss"`) |
| `chunks_path` | `str` | Yes | File path for the chunk metadata JSON (e.g., `"Faiss/my_index.json"`) |

**Example:**

```python
retriever._save_index_("Faiss/ph_index.faiss", "Faiss/ph_index.json")
```

---

### `_load_index_()`

```python
def _load_index_(self, index_path: str, chunks_path: str)
```

Loads a previously persisted FAISS index and chunks from disk.

| Parameter | Type | Required | Description |
|:---|:---|:---|:---|
| `index_path` | `str` | Yes | Path to the saved `.faiss` file |
| `chunks_path` | `str` | Yes | Path to the saved `.json` chunks file |

**Behavior**: Replaces the current in-memory index with the loaded one.

---

### `build_and_save_index()`

```python
def build_and_save_index(self, corpus_dir: str, output_dir: str, index_prefix: str) -> str
```

A **utility method** that delegates to `legal_indexing.rebuild_index` to efficiently crawl a directory of JSON corpus files, validate them, generate embeddings with a progress bar, and save the resulting hybrid FAISS + BM25 index.

| Parameter | Type | Required | Description |
|:---|:---|:---|:---|
| `corpus_dir` | `str` | Yes | Path to directory containing JSON corpus files |
| `output_dir` | `str` | Yes | Directory where `.faiss` and `.json` output files are saved |
| `index_prefix` | `str` | Yes | Prefix for output files (e.g., `"hk_index"` → `hk_index.faiss`, `hk_index.json`) |

**Returns**: `str` — Absolute path to the generated `.faiss` file

**Behavior:**
Delegates entirely to `legal_indexing.rebuild_index`. For full details on the rebuilt logic, see the Developer Utilities section below.

**Example:**

```python
retriever = LegalRetrievalModule()

# Build index from Philippine labor law corpus
faiss_path = retriever.build_and_save_index(
    corpus_dir="legal-corpus/PH",
    output_dir="Faiss",
    index_prefix="ph_index"
)
print(f"Index saved to: {faiss_path}")
# → "Index saved to: Faiss/ph_index.faiss"
```

---

## EmbeddingManager (Sub-component)

**Import**: `from src.adaptive_routing.modules.legal_retrieval.embedding import EmbeddingManager`

Handles all document processing: chunking, embedding generation via the OpenRouter API, and FAISS + BM25 index management.

### EmbeddingManager Constructor

```python
EmbeddingManager(
    api_key: str = None,
    model: str = None,
    chunk_size: int = None,
    chunk_overlap: int = None
)
```

| Parameter | Type | Default | Description |
|:---|:---|:---|:---|
| `api_key` | `str` | `FrameworkConfig._API_KEY` | OpenRouter API key |
| `model` | `str` | `FrameworkConfig._RETRIEVAL_MODEL` | Embedding model identifier |
| `chunk_size` | `int` | `FrameworkConfig._RETRIEVAL_CHUNK_SIZE` (15000) | Max characters per chunk |
| `chunk_overlap` | `int` | `FrameworkConfig._RETRIEVAL_CHUNK_OVERLAP` (0) | Character overlap between chunks |

**Internal state:**

| Attribute | Type | Description |
|:---|:---|:---|
| `_index` | `faiss.IndexFlatL2` or `None` | The FAISS vector index |
| `_chunks` | `list[dict]` | Stored payload dicts containing `{"text": str, "metadata": dict}` aligned with vectors |
| `_dimension` | `int` or `None` | Embedding vector dimension, set on first embed |

---

### `_chunk_text_()`

```python
def _chunk_text_(self, text: str) -> list[str]
```

Splits a document into overlapping character-level chunks.

| Parameter | Type | Description |
|:---|:---|:---|
| `text` | `str` | Raw document text (must be non-empty) |

**Returns**: `list[str]` — List of text chunks

**Chunking algorithm:**
- Start at position 0
- Take `chunk_size` characters
- Advance by `chunk_size - chunk_overlap` characters
- Repeat until end of text

**Example** with `chunk_size=10, chunk_overlap=3`:

```
Text:    "ABCDEFGHIJKLMNOPQRST" (20 chars)
Chunk 1: "ABCDEFGHIJ" (0-10)
Chunk 2: "HIJKLMNOPQ" (7-17)
Chunk 3: "OPQRST"     (14-20)
```

**Raises**: `InvalidInputError` if text is empty or whitespace-only.

---

### `_get_embeddings_()`

```python
def _get_embeddings_(self, texts: list[str]) -> np.ndarray
```

Calls the OpenRouter `/embeddings` endpoint to generate vector embeddings.

| Parameter | Type | Description |
|:---|:---|:---|
| `texts` | `list[str]` | List of text strings to embed |

**Returns**: `np.ndarray` — Matrix of shape `(len(texts), dimension)`, dtype `float32`

**API endpoint used**: `https://openrouter.ai/api/v1/embeddings`

**Exceptions:**
- `AuthenticationError` — Invalid API key (HTTP 401)
- `APIResponseError` — Missing `data` field, other HTTP errors
- `APIConnectionError` — Network failure

---

### `_add_documents_()`

```python
def _add_documents_(self, documents: list[str], bypass_chunking: bool = False)
```

Chunks each document (or bypasses chunking), generates embeddings, and adds them to the FAISS index.

| Parameter | Type | Description |
|:---|:---|:---|
| `documents` | `list[dict]` / `list[str]` | Documents (dicts containing content and metadata, or plain strings) |
| `bypass_chunking` | `bool` | If True, preserves each document individually rather than fragmentation |

**Behavior:**
- On first call, initializes the FAISS `IndexFlatL2` using the embedding dimension
- On subsequent calls, adds to the existing index
- Text chunks are stored in `_chunks` aligned with their index vectors

**Raises**: `InvalidInputError` if no chunks are generated.

---

### `_search_()`

```python
def _search_(self, query: str, top_k: int = None) -> list[dict]
```

Embeds the query and retrieves the nearest chunks from the FAISS index.

| Parameter | Type | Default | Description |
|:---|:---|:---|:---|
| `query` | `str` | — | Search query string |
| `top_k` | `int` | `FrameworkConfig._RETRIEVAL_TOP_K` (5) | Number of results |

**Returns**: `list[dict]` — Each dict contains `{"chunk": str, "metadata": dict, "score": float}`

**Behavior:**
- Returns empty list if no index exists or index is empty
- Uses Reciprocal Rank Fusion (RRF) to combine semantic text search (FAISS) and lexical keyword search (BM25)
- Results sorted by RRF score (descending — most similar first)

---

### EmbeddingManager Save / Load

```python
def _save_index_(self, index_path: str, chunks_path: str)
def _load_index_(self, index_path: str, chunks_path: str)
```

**Save**: Writes the FAISS index binary and chunk metadata JSON to disk.  
**Load**: Reads them back, replacing the current in-memory state.

**Raises**: `InvalidInputError` on save if no index exists.

---

## LegalRetriever (Sub-component)

**Import**: `from src.adaptive_routing.modules.legal_retrieval.retriever import LegalRetriever`

A thin wrapper around `EmbeddingManager._search_()` that provides a clean retrieval interface.

### LegalRetriever Constructor

```python
LegalRetriever(embedding_manager: EmbeddingManager)
```

| Parameter | Type | Required | Description |
|:---|:---|:---|:---|
| `embedding_manager` | `EmbeddingManager` | Yes | The embedding manager to use for search |

### `_retrieve_context_()`

```python
def _retrieve_context_(self, query: str, top_k: int = None) -> list[dict]
```

| Parameter | Type | Default | Description |
|:---|:---|:---|:---|
| `query` | `str` | — | The user's legal question |
| `top_k` | `int` | `FrameworkConfig._RETRIEVAL_TOP_K` | Number of chunks to retrieve |

**Returns**: `list[dict]` — List of `{"chunk": str, "score": float}` dicts

---

## JSON Corpus Format

The `build_and_save_index()` method expects JSON files with this structure:

```json
{
    "jurisdiction": "Philippines",
    "title": "Labor Code - Article 279: Security of Tenure",
    "content": "In cases of regular employment, the employer shall not terminate...",
    "is_repealed": false
}
```

| Field | Type | Required | Description |
|:---|:---|:---|:---|
| `jurisdiction` | `str` | Yes | Legal jurisdiction (e.g., `"Philippines"`, `"Hong Kong"`) |
| `title` | `str` | Yes | Title of the legal provision |
| `content` | `str` | Yes | Full text content of the legal document |
| `is_repealed` | `bool` | No | If `true`, the document is skipped during indexing |

**Formatted output**: Rather than text concatenation, documents are retained natively via JSON serialization:

```json
{
  "jurisdiction": "Philippines",
  "title": "Labor Code - Article 279: Security of Tenure",
  "content": "In cases of regular employment...",
  "is_repealed": false
}
```

**Directory structure supported:**

```
legal-corpus/
├── PH/
│   ├── labor_code_art279.json
│   ├── labor_code_art280.json
│   └── subfolder/
│       └── special_laws.json
└── HK/
    ├── employment_ordinance_s31.json
    └── employment_ordinance_s32.json
```

The method searches **recursively** — nested subdirectories are fully supported.

---

## Developer Utilities (utils)

Located at `src/adaptive_routing/modules/legal_retrieval/utils/`, this package provides helpers for maintaining the knowledge base and importing custom data.

### legal_indexing Module

The `legal_indexing.py` module contains several future-proof functions for developers:

#### `ingest_custom_dataset()`
Allows developers to import a list of dictionaries directly into the RAG index.
```python
from src.adaptive_routing.modules.legal_retrieval.utils import legal_indexing

data = [
    {"jurisdiction": "PH", "title": "Custom Doc", "content": "Legal text..."},
    ...
]
legal_indexing.ingest_custom_dataset(retrieval_module, data)
```

#### `verify_index_integrity()`
Compares the files in `legal-corpus/` with the currently loaded index to detect if any new files have been added but not yet indexed.
```python
sync_info = legal_indexing.verify_index_integrity("legal-corpus", "localfiles/legal-basis/combined_index.json")
print(f"Synced: {sync_info['is_synced']}")
print(f"Missing docs: {sync_info['missing_count']}")
```

### Rebuilding the Index

To ensure all new datasets (like **DMW** or **IRRRA**) are included, use the `rebuild_index` function or the CLI command:

**Via Python:**
```python
from src.adaptive_routing.modules.legal_retrieval.utils import legal_indexing
legal_indexing.rebuild_index("legal-corpus", "localfiles/legal-basis")
```

**Via CLI:**
```bash
python CLI.py
# Inside CLI:
👤 ❯ -reindex
```

### Sync Validation

The framework now checks for synchronization on startup in both CLI and Web modes. A warning will appear if the vector store is behind the local corpus files.

---

## Usage Examples

### Simple Retrieval (Pure RAG)

The most basic setup — ingest documents and retrieve relevant chunks:

```python
from src.adaptive_routing import LegalRetrievalModule

retriever = LegalRetrievalModule()

# Ingest raw legal texts
docs = [
    "Article 279 of the Philippine Labor Code provides that in cases of regular employment, the employer shall not terminate the services of an employee except for a just cause or when authorized by the Labor Code.",
    "The Hong Kong Employment Ordinance, Section 31I, states that an employee may claim severance payment if continuously employed for not less than 24 months."
]
retriever._ingest_documents_(docs)

# Retrieve relevant context
results = retriever._process_retrieval_("Can an employee be fired without cause?", top_k=2)

for item in results["retrieved_chunks"]:
    print(f"Score: {item['score']:.4f}")
    print(f"Text: {item['chunk'][:100]}...")
    print()
```

### Building an Index from a Corpus Directory

```python
from src.adaptive_routing import LegalRetrievalModule

retriever = LegalRetrievalModule()

# Build and save from JSON corpus
faiss_path = retriever.build_and_save_index(
    corpus_dir="legal-corpus/HK",
    output_dir="Faiss",
    index_prefix="hk_index"
)
print(f"Index built and saved to: {faiss_path}")
```

### Loading a Pre-built Index

```python
# Method 1: Load via constructor
retriever = LegalRetrievalModule(
    index_path="Faiss/hk_index.faiss",
    chunks_path="Faiss/hk_index.json"
)

# Method 2: Load via environment variables
# .env: RETRIEVAL_INDEX_PATH=Faiss/hk_index.faiss
#        RETRIEVAL_CHUNKS_PATH=Faiss/hk_index.json
retriever = LegalRetrievalModule()  # Auto-loads from config

# Method 3: Load manually
retriever = LegalRetrievalModule()
retriever._load_index_("Faiss/hk_index.faiss", "Faiss/hk_index.json")
```

### Intermediate RAG (Retrieval + Manual Generation)

Retrieve context and manually pass it to the LLM for grounded responses:

```python
from src.adaptive_routing import LegalRetrievalModule
from src.adaptive_routing.modules.semantic_router.legal_generation import LegalGenerator

retriever = LegalRetrievalModule(
    index_path="Faiss/hk_index.faiss",
    chunks_path="Faiss/hk_index.json"
)
generator = LegalGenerator()

# Step 1: Retrieve context
query = "What are the eviction protocols for tenants?"
retrieval_data = retriever._process_retrieval_(query, top_k=3)
chunks = retrieval_data.get("retrieved_chunks", [])

# Step 2: Build augmented query
context_str = "\n".join([f"- {c['chunk']}" for c in chunks])
augmented_query = f"CONTEXT:\n{context_str}\n\nUSER QUERY:\n{query}"

# Step 3: Generate grounded response
response = generator._dispatch_(augmented_query, "General-LLM")
print(response)
```

### Complex Multi-Index RAG (Full Pipeline)

Multi-jurisdictional retrieval with triage and routing:

```python
from src.adaptive_routing import TriageModule, SemanticRouterModule, LegalRetrievalModule
from src.adaptive_routing.modules.semantic_router.legal_generation import LegalGenerator

# Initialize modules
triage = TriageModule()
router_classifier = SemanticRouterModule()

# Load jurisdiction-specific indices
hk_retriever = LegalRetrievalModule(
    index_path="Faiss/hk_index.faiss",
    chunks_path="Faiss/hk_index.json"
)
ph_retriever = LegalRetrievalModule(
    index_path="Faiss/ph_index.faiss",
    chunks_path="Faiss/ph_index.json"
)
generator = LegalGenerator()

# Step 1: Normalize
user_query = "Pinalayas ako ng amo ko sa Hong Kong kahit may contract pa ako"
triage_result = triage._process_request_(user_query)
normalized = triage_result["normalized_text"]

# Step 2: Classify route
route_result = router_classifier._process_routing_(normalized)
route = route_result["classification"]["route"]

# Step 3: Multi-index retrieval
hk_chunks = hk_retriever._process_retrieval_(normalized, top_k=3)["retrieved_chunks"]
ph_chunks = ph_retriever._process_retrieval_(normalized, top_k=3)["retrieved_chunks"]

# Step 4: Build augmented context
hk_context = "\n".join([f"[HK] {c['chunk']}" for c in hk_chunks])
ph_context = "\n".join([f"[PH] {c['chunk']}" for c in ph_chunks])
augmented_query = (
    f"HONG KONG LAW CONTEXT:\n{hk_context}\n\n"
    f"PHILIPPINE LAW CONTEXT:\n{ph_context}\n\n"
    f"QUERY:\n{normalized}"
)

# Step 5: Generate with appropriate LLM
response = generator._dispatch_(augmented_query, route)
print(response)
```

### Saving and Re-loading an Index

```python
retriever = LegalRetrievalModule()

# Ingest multiple batches
retriever._ingest_documents_(batch_1)
retriever._ingest_documents_(batch_2)  # Additively indexed

# Persist
retriever._save_index_("Faiss/combined_index.faiss", "Faiss/combined_index.json")

# Later, in a new session
retriever2 = LegalRetrievalModule(
    index_path="Faiss/combined_index.faiss",
    chunks_path="Faiss/combined_index.json"
)
results = retriever2._process_retrieval_("Query here")
```

---

## Customization Guide

### Custom Chunk Size and Overlap

Adjust for your document characteristics:

```python
from src.adaptive_routing.modules.legal_retrieval.embedding import EmbeddingManager
from src.adaptive_routing import LegalRetrievalModule

# Larger chunks with more overlap for long, dense legal texts
custom_manager = EmbeddingManager(
    chunk_size=1024,      # 1024 characters per chunk
    chunk_overlap=200     # 200-character overlap
)

retriever = LegalRetrievalModule(embedding_manager=custom_manager)
```

**Sizing guidelines:**

The framework defaults to **1-to-1 document-level chunking** (`15000` size, `0` overlap). This intentionally maps exactly one JSON corpus file to one vector so laws aren't cut in half.

If your corpus features giant un-split documents, adjust it back down:

| Document Type | Recommended Chunk Size | Recommended Overlap |
|:---|:---|:---|
| Modular JSON (Default) | 15000+ | 0 |
| Short statutes/articles | 256–512 | 32–64 |
| Long legal texts | 512–1024 | 64–200 |
| Very dense contracts | 1024–2048 | 200–400 |

### Custom Embedding Model

```python
from src.adaptive_routing.modules.legal_retrieval.embedding import EmbeddingManager
from src.adaptive_routing import LegalRetrievalModule

custom_manager = EmbeddingManager(
    model="openai/text-embedding-3-small"  # Different embedding model
)

retriever = LegalRetrievalModule(embedding_manager=custom_manager)
```

### Custom top_k Per Query

```python
retriever = LegalRetrievalModule()

# Retrieve more chunks for comprehensive context
results = retriever._process_retrieval_("Complex legal question", top_k=10)

# Retrieve fewer for precision
results = retriever._process_retrieval_("Simple definition", top_k=2)
```

### Global top_k Configuration

```env
RETRIEVAL_TOP_K=8
```

Or at runtime:

```python
from src.adaptive_routing.config import FrameworkConfig
FrameworkConfig._RETRIEVAL_TOP_K = 8
```

### Pre-built Index via Environment

```env
RETRIEVAL_INDEX_PATH=Faiss/production_index.faiss
RETRIEVAL_CHUNKS_PATH=Faiss/production_index.json
```

All `LegalRetrievalModule()` instances will automatically load this index without any constructor arguments.

### Incremental Document Ingestion

Documents can be ingested in multiple batches — each call adds to the existing index:

```python
retriever = LegalRetrievalModule()

# First batch
retriever._ingest_documents_(philippine_labor_docs)

# Second batch — additively indexed
retriever._ingest_documents_(hong_kong_employment_docs)

# Third batch
retriever._ingest_documents_(additional_docs)

# All documents are searchable
results = retriever._process_retrieval_("Search across all documents")
```

### Accessing Sub-components Directly

```python
retriever = LegalRetrievalModule()

# Access the EmbeddingManager for direct operations
chunks = retriever._embedding_manager._chunk_text_("Some long document text...")
embeddings = retriever._embedding_manager._get_embeddings_(["text1", "text2"])

# Access the LegalRetriever
context = retriever._retriever._retrieve_context_("query", top_k=3)

# Check index statistics
if retriever._embedding_manager._index is not None:
    total_vectors = retriever._embedding_manager._index.ntotal
    dimension = retriever._embedding_manager._dimension
    total_chunks = len(retriever._embedding_manager._chunks)
    print(f"Index: {total_vectors} vectors, {dimension}D, {total_chunks} chunks")
```

### Building Multiple Jurisdiction Indices

```python
from src.adaptive_routing import LegalRetrievalModule

# Build separate indices for different jurisdictions
retriever = LegalRetrievalModule()

# Hong Kong index
hk_path = retriever.build_and_save_index(
    corpus_dir="legal-corpus/HK",
    output_dir="Faiss",
    index_prefix="hk_index"
)

# Philippine index (new retriever to reset state)
retriever2 = LegalRetrievalModule()
ph_path = retriever2.build_and_save_index(
    corpus_dir="legal-corpus/PH",
    output_dir="Faiss",
    index_prefix="ph_index"
)

# Use them separately at query time
hk_module = LegalRetrievalModule(
    index_path="Faiss/hk_index.faiss",
    chunks_path="Faiss/hk_index.json"
)
ph_module = LegalRetrievalModule(
    index_path="Faiss/ph_index.faiss",
    chunks_path="Faiss/ph_index.json"
)
```
