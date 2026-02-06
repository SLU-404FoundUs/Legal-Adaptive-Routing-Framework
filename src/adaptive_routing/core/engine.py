"""
Saint Louis University : Team 404FoundUs
@file src/adaptive_routing/core/engine.py
@project_ LLM Legal Adaptive Routing Framework
@desc_ Handler for OpenRouter API requests with robust error management.
@deps_ requests, json, src.adaptive_routing.config, src.adaptive_routing.core.exceptions
"""

import requests
import json
from src.adaptive_routing.config import FrameworkConfig
from src.adaptive_routing.core.exceptions import (
    AuthenticationError,
    ModelNotFoundError,
    APIConnectionError,
    InvalidInputError,
    APIResponseError
)

class LLMRequestEngine:
    """
    @class_ LLMRequestEngine
    @desc_ Provides a unified interface for OpenRouter completions.
    @attr_ _api_key : (str) Credential for the OpenRouter API.
    @attr_ _model : (str) The specific LLM model to target.
    @attr_ _temperature : (float) Controls randomness of output.
    @attr_ _max_tokens : (int) Limit on response length.
    @attr_ _use_system_role : (bool) Toggle for system prompt support.
    """
    def __init__(self, api_key=None, model=None, temperature=None, max_tokens=None, use_system_role=None, include_reasoning=None):
        self._url = "https://openrouter.ai/api/v1/chat/completions"
        
        ## @Logic_ Determine system role usage: Argument > Config > Default(True)
        if use_system_role is not None:
            self._use_system_role = use_system_role
        else:
            self._use_system_role = getattr(FrameworkConfig, '_USE_SYSTEM_ROLE', True)
        
        ## @Logic_ Determine reasoning usage
        if include_reasoning is not None:
            self._include_reasoning = include_reasoning
        else:
            self._include_reasoning = getattr(FrameworkConfig, '_INCLUDE_REASONING', False)
        
        ## @logic_ API Key Validation from argument or config
        self._api_key = api_key or FrameworkConfig._API_KEY
        if not self._api_key:
            raise AuthenticationError("API Key is missing. Please provide it in init or set OPENROUTER_API_KEY environment variable.")

        ## @logic_ Model Validation (Basic check, deeper check happens at API calling)
        self._model = model or FrameworkConfig._DEFAULT_MODEL
        if not self._model or not isinstance(self._model, str):
             raise InvalidInputError(f"Invalid model specified: {self._model}")

        ## @logic_ Parameter Validation for temperature and max_tokens
        self._temperature = temperature if temperature is not None else FrameworkConfig._TEMPERATURE
        if not (0 <= self._temperature <= 2.0):
             raise InvalidInputError(f"Temperature must be between 0.0 and 2.0, got {self._temperature}")

        self._max_tokens = max_tokens if max_tokens is not None else FrameworkConfig._MAX_TOKENS
        if self._max_tokens <= 0:
            raise InvalidInputError(f"max_tokens must be positive, got {self._max_tokens}")


    def _encode_image_(self, image_source):
        """
        @func_ _encode_image_ (@params image_source)
        @params image_source : (str) Path to image file or URL.
        @return_ dict : JSON-compatiable image payload.
        @desc_ Helper to encode image from path or return URL as is
        """
        import base64
        import mimetypes
        import os

        ## @logic_ specific check if it is a url
        if image_source.startswith(('http://', 'https://')):
             return {"type": "image_url", "image_url": {"url": image_source}}
        
        if not os.path.exists(image_source):
             raise InvalidInputError(f"Image file not found: {image_source}")
             
        mime_type, _ = mimetypes.guess_type(image_source)
        if not mime_type:
             mime_type = "image/jpeg"
             
        with open(image_source, "rb") as image_file:
            base64_image = base64.b64encode(image_file.read()).decode('utf-8')
            
        return {
            "type": "image_url", 
            "image_url": {
                "url": f"data:{mime_type};base64,{base64_image}"
            }
        }


    def _get_completion_(self, prompt, sys_message, images=None):
        """
        @func_ _get_completion_ (@params prompt, sys_message, images)
        @params prompt : (str) The user's input prompt.
        @params sys_message : (str) System instruction (role).
        @params images : (list[str]) Optional list of image paths/URLs.
        @return_ str : The AI's response text.
        @err_ Raises AuthenticationError, ModelNotFoundError, APIConnectionError, APIResponseError
        """
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/404FoundUs", 
            "X-Title": "LLM Legal Adaptive Routing Framework" 
        }

        user_content = prompt

        ## @logic_ If system role is not supported, we merge instructions into user prompt
        if not self._use_system_role:
             user_content = f"{sys_message}\n\n{prompt}"

        if images:

            text_payload = user_content if not self._use_system_role else prompt
            
            user_content = [{"type": "text", "text": text_payload}]
            ## @iter_ images: encoding each image for the payload
            for img in images:
                user_content.append(self._encode_image_(img))

        messages = []
        ## @logic_ Add system role only if enabled
        if self._use_system_role:
            messages.append({"role": "system", "content": sys_message})
        
        messages.append({"role": "user", "content": user_content})

        payload = {
            "model": self._model,
            "messages": messages,
            "temperature": self._temperature,
            "max_tokens": self._max_tokens,
            "include_reasoning": self._include_reasoning
        }
        

        try:
            response = requests.post(self._url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            

            response_json = response.json()
            if 'choices' in response_json and len(response_json['choices']) > 0:
                message = response_json['choices'][0]['message']
                content = message.get('content', '')
                
                reasoning = message.get('reasoning', None)
                if self._include_reasoning and reasoning:
                    return f"<reasoning>\n{reasoning}\n</reasoning>\n\n{content}"
                
                return content
            else:
                raise APIResponseError("Invalid response format from API: 'choices' field missing or empty.", response_body=response_json)

        except requests.exceptions.HTTPError as e:
            error_msg = f"HTTP Error {e.response.status_code}: {e.response.text}"
            if e.response.status_code == 401:
                raise AuthenticationError(f"Invalid API Key provided. Details: {e.response.text}") from e
            elif e.response.status_code == 404:
                raise ModelNotFoundError(f"Model '{self._model}' not found or API endpoint invalid. Details: {e.response.text}") from e
            elif e.response.status_code == 402: # Payment required
                 raise APIResponseError(f"Insufficient credits. Details: {e.response.text}", status_code=402) from e
            else:
                raise APIResponseError(error_msg, status_code=e.response.status_code, response_body=e.response.text) from e
        
        except requests.exceptions.ConnectionError as e:
            raise APIConnectionError(f"Failed to connect to OpenRouter API. Check your internet connection. Details: {str(e)}") from e
        
        except requests.exceptions.Timeout as e:
             raise APIConnectionError(f"Request timed out after 30 seconds. Details: {str(e)}") from e
             
        except requests.exceptions.RequestException as e:
            raise APIConnectionError(f"An unexpected API error occurred: {str(e)}") from e
        except json.JSONDecodeError as e:
             raise APIResponseError(f"Failed to decode API response JSON. Details: {str(e)}") from e
