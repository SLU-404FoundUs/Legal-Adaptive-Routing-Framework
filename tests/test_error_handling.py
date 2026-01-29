import unittest
from unittest.mock import patch, MagicMock
import os
import requests
from src.adaptive_routing.core.engine import LLMRequestEngine
from src.adaptive_routing.core.exceptions import (
    AuthenticationError,
    ModelNotFoundError,
    APIConnectionError,
    InvalidInputError,
    APIResponseError
)

class TestErrorHandling(unittest.TestCase):
    
    def test_missing_api_key(self):
        
        with patch('src.adaptive_routing.config.FrameworkConfig._API_KEY', None):
             with self.assertRaises(AuthenticationError):
                LLMRequestEngine(api_key=None)

    def test_invalid_temperature(self):
        with self.assertRaisesRegex(InvalidInputError, "Temperature"):
            LLMRequestEngine(api_key="test_key", temperature=2.5)

    def test_invalid_model_type(self):
        with self.assertRaisesRegex(InvalidInputError, "Invalid model"):
            LLMRequestEngine(api_key="test_key", model=123)

    @patch('requests.post')
    def test_api_authentication_error(self, mock_post):
        # Mock 401 response
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(response=mock_response)
        mock_post.return_value = mock_response

        engine = LLMRequestEngine(api_key="invalid_key")
        with self.assertRaises(AuthenticationError):
            engine._get_completion_("test", "test")

    @patch('requests.post')
    def test_model_not_found_error(self, mock_post):
        # Mock 404 response
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Model not found"
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(response=mock_response)
        mock_post.return_value = mock_response

        engine = LLMRequestEngine(api_key="test_key")
        with self.assertRaises(ModelNotFoundError):
            engine._get_completion_("test", "test")

    @patch('requests.post')
    def test_connection_error(self, mock_post):
        # Mock ConnectionError
        mock_post.side_effect = requests.exceptions.ConnectionError("Connection refused")

        engine = LLMRequestEngine(api_key="test_key")
        with self.assertRaises(APIConnectionError):
            engine._get_completion_("test", "test")
            
    @patch('requests.post')
    def test_timeout_error(self, mock_post):
        # Mock Timeout
        mock_post.side_effect = requests.exceptions.Timeout("Request timed out")

        engine = LLMRequestEngine(api_key="test_key")
        with self.assertRaises(APIConnectionError):
            engine._get_completion_("test", "test")

    @patch('requests.post')
    def test_malformed_response(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "123"}
        mock_post.return_value = mock_response

        engine = LLMRequestEngine(api_key="test_key")
        with self.assertRaisesRegex(APIResponseError, "Invalid response format"):
            engine._get_completion_("test", "test")

if __name__ == '__main__':
    unittest.main()
