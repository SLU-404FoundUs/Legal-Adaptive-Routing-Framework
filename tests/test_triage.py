## Saint Louis University
## Team 404FoundUs
## @file tests/test_triage.py
## @project_ LLM Legal Adaptive Routing Framework
## @desc_ Test script for the TriageModule and its components.

import unittest
from unittest.mock import MagicMock, patch
from src.adaptive_routing.modules.triage import TriageModule

class TestTriageModule(unittest.TestCase):
    
    @patch('src.adaptive_routing.modules.triage.LLMRequestEngine')
    def test_triage_flow(self, MockEngine):
        """
        @func_ test_triage_flow
        @desc_ Verifies that TriageModule correctly parses the LLM output and updates state.
        """
        # Setup Mock
        mock_instance = MockEngine.return_value
        # Simulated LLM response with the language tag
        mock_instance._get_completion_.return_value = "This is the normalized English text. <Detected Raw Language: Taglish>"

        # Initialize Triage
        triage = TriageModule(api_key="dummy_key")
        
        # Test Input
        input_text = "Yung ano kasi, this is the input."
        
        # Execute
        result = triage._process_request_(input_text)
        
        # Assertions
        print("Triage Result:", result)
        
        self.assertEqual(result['original_prompt'], input_text)
        self.assertEqual(result['normalized_text'], "This is the normalized English text.")
        self.assertEqual(result['detected_language'], "Taglish")
        
        # Verify LLM call
        mock_instance._get_completion_.assert_called_once()

if __name__ == '__main__':
    unittest.main()
