"""
ProductMind AI — AI & LLM Domain Exceptions
Defines standardized exception hierarchy for AI providers, client lifecycle,
model execution, and schema parsing failures.
"""


class AIServiceException(Exception):
    """Base exception for all AI and LLM service failures."""

    def __init__(self, message: str, provider: str = "unknown", original_exception: Exception = None):
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.original_exception = original_exception

    def __str__(self) -> str:
        return f"[{self.provider.upper()}] {self.message}"


class AIConfigurationException(AIServiceException):
    """Raised when required AI credentials or model parameters are missing or invalid."""
    pass


class AIAuthenticationException(AIServiceException):
    """Raised when provider rejects credentials (invalid API key, 401, 403)."""
    pass


class AIRateLimitException(AIServiceException):
    """Raised when provider rate limit or quota is exhausted (429)."""
    pass


class AITimeoutException(AIServiceException):
    """Raised when an AI model invocation exceeds the configured timeout."""
    pass


class AIProviderException(AIServiceException):
    """Raised when the provider model fails, is unavailable, or returns a 5xx error."""
    pass


class AISchemaValidationException(AIServiceException):
    """Raised when structured JSON output fails Pydantic schema validation."""
    pass

