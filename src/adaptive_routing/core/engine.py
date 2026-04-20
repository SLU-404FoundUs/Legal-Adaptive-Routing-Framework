## Saint Louis University
## Team 404FoundUs
## @file src/adaptive_routing/core/engine.py
## @project_ LLM Legal Adaptive Routing Framework
## @desc_ Handler for OpenRouter API requests with robust error management.
## @deps requests, json, time, logging, src.adaptive_routing.config, src.adaptive_routing.core.exceptions

import requests
import json
import time
import logging
from src.adaptive_routing.config import FrameworkConfig
from src.adaptive_routing.core.exceptions import (
    AuthenticationError,
    ModelNotFoundError,
    APIConnectionError,
    InvalidInputError,
    APIResponseError
)

logger = logging.getLogger(__name__)

class LLMRequestEngine:
    """
    @class LLMRequestEngine
    @desc_ Provides a unified interface for OpenRouter completions.
    @attr_ _api_key : (str) Credential for the OpenRouter API.
    @attr_ _model : (str) The specific LLM model to target.
    @attr_ _temperature : (float) Controls randomness of output.
    @attr_ _max_tokens : (int) Limit on response length.
    @attr_ _use_system_role : (bool) Toggle for system prompt support.
    @attr_ _include_reasoning : (bool) Toggle for reasoning field inclusion.
    """
    def __init__(self, api_key=None, model=None, temperature=None, max_tokens=None, use_system_role=None, include_reasoning=None):
        self._url = "https://openrouter.ai/api/v1/chat/completions"
        
        ## @logic_ Determine system role usage: Argument > Config > Default(True)
        if use_system_role is not None:
            self._use_system_role = use_system_role
        else:
            self._use_system_role = getattr(FrameworkConfig, '_USE_SYSTEM_ROLE', True)
        
        ## @logic_ Determine reasoning usage
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

    def _build_headers_(self):
        """
        @func_ _build_headers_
        @returns (dict) HTTP headers for OpenRouter API requests.
        @desc_ Centralized header construction used by all API methods.
        """
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/404FoundUs", 
            "X-Title": "LLM Legal Adaptive Routing Framework" 
        }

    def _parse_response_(self, response_json):
        """
        @func_ _parse_response_
        @params response_json : (dict) The parsed JSON from the API response.
        @returns (str) The AI's response text, with optional reasoning prefix.
        @desc_ Unified response parsing for both completion and chat completion methods.
        """
        if 'choices' in response_json and len(response_json['choices']) > 0:
            message = response_json['choices'][0]['message']
            
            # Extract content, ensuring it's at least an empty string if null
            content = message.get('content') or ""
            
            # Extract reasoning from multiple possible fields (OpenRouter / OpenAI / O1)
            reasoning = message.get('reasoning') or message.get('reasoning_content')
            
            # Check for reasoning_details (list of dicts) used by some providers
            if not reasoning and 'reasoning_details' in message:
                details = message['reasoning_details']
                if isinstance(details, list) and len(details) > 0:
                    # Collect all summary/text parts from reasoning details
                    parts = []
                    for part in details:
                        if isinstance(part, dict) and 'summary' in part:
                            parts.append(part['summary'])
                        elif isinstance(part, dict) and 'data' in part and not part.get('type') == 'reasoning.encrypted':
                             parts.append(part['data'])
                    if parts:
                        reasoning = "\n".join(parts)

            # If user wants reasoning and we found some, prepend it
            if self._include_reasoning and reasoning:
                return f"<reasoning>\n{reasoning}\n</reasoning>\n\n{content}"
            
            # Fallback if content is null but we have reasoning (indicates reasoning took all tokens)
            if not content and reasoning:
                return f"[REASONING ONLY - NO CONTENT GENERATED]\n\n{reasoning}"
            
            # Final fallback if absolutely nothing was generated
            if not content:
                content = "The model returned an empty response (and no reasoning could be extracted). Please try increasing the MAX_TOKENS setting or check your API credits."
            
            return content
        else:
            raise APIResponseError(
                "Invalid response format from API: 'choices' field missing or empty.", 
                response_body=response_json
            )

    def _handle_request_error_(self, error, context="API request"):
        """
        @func_ _handle_request_error_
        @params error : (Exception) The caught exception.
        @params context : (str) Description of the operation for error messages.
        @desc_ Unified error handler that maps HTTP status codes to framework exceptions.
        """
        if isinstance(error, requests.exceptions.HTTPError):
            status_code = error.response.status_code
            detail = error.response.text
            if status_code == 401:
                raise AuthenticationError(
                    f"Invalid API Key provided. Details: {detail}"
                ) from error
            elif status_code == 404:
                raise ModelNotFoundError(
                    f"Model '{self._model}' not found or API endpoint invalid. Details: {detail}"
                ) from error
            elif status_code == 402:
                raise APIResponseError(
                    f"Insufficient credits. Details: {detail}", 
                    status_code=402
                ) from error
            else:
                raise APIResponseError(
                    f"HTTP Error {status_code}: {detail}", 
                    status_code=status_code, 
                    response_body=detail
                ) from error
        
        elif isinstance(error, requests.exceptions.ConnectionError):
            raise APIConnectionError(
                f"{context} failed: Could not connect to OpenRouter API. Check your internet connection. Details: {str(error)}"
            ) from error
        
        elif isinstance(error, requests.exceptions.Timeout):
            raise APIConnectionError(
                f"{context} timed out after {FrameworkConfig._REQUEST_TIMEOUT} seconds. Details: {str(error)}"
            ) from error
             
        elif isinstance(error, requests.exceptions.RequestException):
            raise APIConnectionError(
                f"{context} failed unexpectedly: {str(error)}"
            ) from error

        elif isinstance(error, json.JSONDecodeError):
            raise APIResponseError(
                f"Failed to decode API response JSON. Details: {str(error)}"
            ) from error

    def _call_api_(self, payload, timeout=None):
        """
        @func_ _call_api_
        @params payload : (dict) The JSON request payload.
        @params timeout : (int) Request timeout in seconds.
        @returns (dict) Parsed JSON response from the API.
        @desc_ Executes an API call with retry logic and unified error handling.
        """
        headers = self._build_headers_()
        timeout = timeout or FrameworkConfig._REQUEST_TIMEOUT
        retries = FrameworkConfig._RETRY_COUNT
        backoff = FrameworkConfig._RETRY_BACKOFF

        last_error = None
        ## @iter_ range : Retrying the API call based on backoff logic
        for attempt in range(1 + retries):
            try:
                response = requests.post(self._url, headers=headers, json=payload, timeout=timeout)
                response.raise_for_status()
                return response.json()
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                last_error = e
                if attempt < retries:
                    wait_time = backoff * (2 ** attempt)
                    logger.warning(f"API request attempt {attempt + 1} failed ({type(e).__name__}). Retrying in {wait_time:.1f}s...")
                    time.sleep(wait_time)
                    continue
                self._handle_request_error_(e, context="Completion")
            except (requests.exceptions.HTTPError, requests.exceptions.RequestException, json.JSONDecodeError) as e:
                ## @logic_ Non-retryable errors (auth, model not found, etc.) — fail immediately
                self._handle_request_error_(e, context="Completion")

        if last_error:
            self._handle_request_error_(last_error, context="Completion")

    def _encode_image_(self, image_source):
        """
        @func_ _encode_image_
        @params image_source : (str) Path to image file or URL.
        @returns (dict) JSON-compatiable image payload.
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
        @func_ _get_completion_
        @params prompt : (str) The user's input prompt.
        @params sys_message : (str) System instruction (role).
        @params images : (list) Optional list of image paths/URLs.
        @returns (str) The AI's response text.
        @raises AuthenticationError, ModelNotFoundError, APIConnectionError, APIResponseError
        @desc_ Standard completion request for a single turn.
        """
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

        response_json = self._call_api_(payload)
        return self._parse_response_(response_json)

    def _get_chat_completion_(self, messages: list) -> str:
        """
        @func_ _get_chat_completion_
        @params messages : (list) List of message dicts (role, content).
        @returns (str) The AI's response text.
        @desc_ Direct interface for passing full conversation history.
        """
        final_messages = []
        if not self._use_system_role:
            ## @logic_ Merge system messages into the first user message
            system_content = ""
            for msg in messages:
                if msg["role"] == "system":
                    system_content += msg["content"] + "\n\n"
                else:
                    if msg["role"] == "user" and system_content:
                        final_messages.append({"role": "user", "content": system_content + msg["content"]})
                        system_content = "" 
                    else:
                        final_messages.append(msg)
            
            if system_content:
                final_messages.insert(0, {"role": "user", "content": system_content.strip()})
        else:
            final_messages = messages

        payload = {
            "model": self._model,
            "messages": final_messages,
            "temperature": self._temperature,
            "max_tokens": self._max_tokens,
            "include_reasoning": self._include_reasoning
        }

        response_json = self._call_api_(payload)
        return self._parse_response_(response_json)
