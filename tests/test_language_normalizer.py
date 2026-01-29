## Saint Louis University
## Team 404FoundUs
## @file tests/test_framework.py
## @project_ LLM Legal Adaptive Routing Framework
## @desc_ Driver script to test the framework initialization and linguistic normalization.
## @deps src.adaptive_routing.core.engine, src.adaptive_routing.modules.linguistic, os

import os
from src.adaptive_routing.core.engine import LLMRequestEngine
from src.adaptive_routing.modules.linguistic import LinguisticNormalizer

def main():
    """
    @func_ main
    @desc_ Entry point for testing the framework.
    """
    print("Initializing Framework...")
    print("\n--- Test 1: Language Normalizer) ---")
    engine_standard = LLMRequestEngine() 
    normalizer_standard = LinguisticNormalizer(engine_standard)
    
    test_input = "Yung ano kasi, yung Special Power of Attorney (SPA) na pinirmahan ni Papa bago siya nawala, feeling ko void ab initio talaga yun kasi hindi naman siya mentally fit nung time na 'yun. Ngayon, yung mga tenants doon sa Baguio property, ayaw pa rin umalis kahit binigyan na namin ng Notice to Vacate last month. Ang tigas talaga ng mukha, parang may backer sa City Hall kaya kampante sila. Pwede ba natin silang kasuhan ng Unlawful Detainer? Kasi parang may clear breach of contract na rin dito eh. Pakisuri naman po kung anong routing ang dapat dito."
    print(f"Input: {test_input}")
    result_standard = normalizer_standard._normalize_text_(test_input)
    print("\n")
    print(f"Normalized Output: {result_standard}")


    



if __name__ == "__main__":
    main()
