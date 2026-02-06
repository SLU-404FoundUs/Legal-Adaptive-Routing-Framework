"""
Saint Louis University : Team 404FoundUs
@file src/adaptive_routing/core/exceptions.py
@project_ LLM Legal Adaptive Routing Framework
@desc_ Custom exception definitions for the library.
"""

class AdaptiveRoutingError(Exception):
    """
    @class_ AdaptiveRoutingError
    @desc_ Base exception for all errors in the Adaptive Routing Framework.
    """
    pass

class AuthenticationError(AdaptiveRoutingError):
    """
    @class_ AuthenticationError
    @desc_ Raised when API keys are missing or invalid.
    """
    pass

class ConfigurationError(AdaptiveRoutingError):
    """
    @class_ ConfigurationError
    @desc_ Raised when essential configuration is missing.
    """
    pass

class ModelNotFoundError(AdaptiveRoutingError):
    """
    @class_ ModelNotFoundError
    @desc_ Raised when the specified model is invalid or unavailable.
    """
    pass

class APIConnectionError(AdaptiveRoutingError):
    """
    @class_ APIConnectionError
    @desc_ Raised when the API request fails due to network issues or timeouts.
    """
    pass

class InvalidInputError(AdaptiveRoutingError):
    """
    @class_ InvalidInputError
    @desc_ Raised when input parameters (like temperature) are out of valid range.
    """
    pass

class APIResponseError(AdaptiveRoutingError):
    """
    @class_ APIResponseError
    @desc_ Raised when the API returns an error response (non-200 status).
    """
    def __init__(self, message, status_code=None, response_body=None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body
