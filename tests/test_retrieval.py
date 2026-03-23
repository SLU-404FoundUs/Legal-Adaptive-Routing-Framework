import os
import sys
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Ensure the root directory is on the path so `src` can be resolved
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.adaptive_routing.modules.retrieval import LegalRetrievalModule

def main():
    """
    Demonstrates the complete lifecycle of the LegalRetrievalModule:
    1. Building an index from a raw JSON folder.
    2. Loading the built index into a fresh application instance.
    3. Running a vector search query.
    """
    
    print("==================================================")
    print(" STEP 1: Building and Saving the FAISS Index")
    print("==================================================")
    
    # Initialize an empty retriever
    builder_module = LegalRetrievalModule()
    
    # Generate the index from the HK legal corpus
    output_directory = "./Faiss"
    print("Crawling 'legal-corpus/HK', parsing texts, and generating embeddings...")
    
    try:
        saved_faiss_path = builder_module.build_and_save_index(
            corpus_dir="legal-corpus/HK",
            output_dir=output_directory,
            index_prefix="hk_test_index"
        )
        print(f"✅ Successfully built and saved index at: {saved_faiss_path}\n")
    except ValueError as e:
        print(f"❌ Failed to build index: {e}")
        return


#     print("==================================================")
#     print(" STEP 2: Loading the Pre-built FAISS Index")
#     print("==================================================")
    
#     # Simulate a fresh application startup that auto-loads the index natively!
#     # (In production, you can configure these paths in .env instead of passing them)
#     loaded_module = LegalRetrievalModule(
#         index_path="./test_indexes/hk_test_index.faiss",
#         chunks_path="./test_indexes/hk_test_index.json"
#     )
#     print("✅ Successfully initialized retriever with the saved FAISS index.\n")


#     print("==================================================")
#     print(" STEP 3: Querying the FAISS Index")
#     print("==================================================")
    
#     sample_query = "What are the rules regarding the commencement of maternity leave?"
#     print(f"QUERY: '{sample_query}'\n")
    
#     # Fetch top 2 context results relevant to the query
#     results = loaded_module._process_retrieval_(sample_query, top_k=2)
    
#     retrieved_chunks = results.get("retrieved_chunks", [])
#     if not retrieved_chunks:
#         print("No matches discovered.")
        
#     for idx, item in enumerate(retrieved_chunks, 1):
#         score = item.get("score", "N/A")
#         text = item.get("chunk", "N/A")
        
#         # We trunk the display text to 200 chars so it's clean and readable
#         preview = text[:200].replace('\n', ' ') + "..." if len(text) > 200 else text.replace('\n', ' ')
        
#         print(f"Match #{idx} | Relevance Score (Distance): {score:.4f}")
#         print(f"Context: {preview}\n")
#         print("-" * 50)


if __name__ == "__main__":
    main()
