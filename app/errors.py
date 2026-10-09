"""Typed error hierarchy. Every error maps to an HTTP status and a safe, client-facing message."""


class AppError(Exception):
    """Base class for all expected application errors."""

    status_code = 500
    error_type = "internal_error"
    public_message = "An unexpected error occurred."

    def __init__(self, detail: str | None = None):
        # `detail` is for logs only; clients receive `public_message`.
        self.detail = detail or self.public_message
        super().__init__(self.detail)


class ConfigError(AppError):
    status_code = 503
    error_type = "config_error"
    public_message = "The service is not configured correctly (check LLM environment variables)."


class InvalidRequestError(AppError):
    status_code = 400
    error_type = "invalid_request"
    public_message = "The request is invalid."

    def __init__(self, detail: str):
        super().__init__(detail)
        self.public_message = detail


class NotFoundError(AppError):
    status_code = 404
    error_type = "not_found"
    public_message = "Resource not found."


class LLMError(AppError):
    """Base class for errors coming from the LLM provider."""

    status_code = 502
    error_type = "llm_provider_error"
    public_message = "The language model provider returned an error."
    retryable = False


class LLMAuthError(LLMError):
    status_code = 502
    error_type = "llm_auth_error"
    public_message = "The language model provider rejected the credentials."


class LLMTimeoutError(LLMError):
    status_code = 504
    error_type = "llm_timeout"
    public_message = "The language model provider timed out."
    retryable = True


class LLMRateLimitError(LLMError):
    status_code = 429
    error_type = "llm_rate_limited"
    public_message = "The language model provider is rate limiting requests. Try again shortly."
    retryable = True

    def __init__(self, detail: str | None = None, retry_after: float | None = None):
        super().__init__(detail)
        self.retry_after = retry_after


class LLMProviderError(LLMError):
    """5xx or unexpected provider failure."""

    retryable = True


class MalformedOutputError(LLMError):
    status_code = 502
    error_type = "malformed_model_output"
    public_message = "The language model returned output that could not be parsed."
