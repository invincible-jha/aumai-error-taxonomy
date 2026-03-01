"""AumAI ErrorTaxonomy — standardised agent error codes and classification."""

from aumai_error_taxonomy.async_core import AsyncErrorRegistry
from aumai_error_taxonomy.core import (
    ERROR_REGISTRY,
    AgentErrorException,
    UnknownErrorCode,
    classify_exception,
    create_error_response,
    errors_by_category,
    lookup_error,
)
from aumai_error_taxonomy.models import AgentError, ErrorCategory, ErrorRegistry
from aumai_error_taxonomy.store import ErrorOccurrence, ErrorStore
from aumai_error_taxonomy.suggestions import RecoverySuggestion, RecoverySuggester

__version__ = "0.1.0"

__all__ = [
    # Core (sync)
    "ERROR_REGISTRY",
    "AgentErrorException",
    "UnknownErrorCode",
    "classify_exception",
    "create_error_response",
    "errors_by_category",
    "lookup_error",
    # Models
    "AgentError",
    "ErrorCategory",
    "ErrorRegistry",
    # Async API
    "AsyncErrorRegistry",
    # Persistence
    "ErrorOccurrence",
    "ErrorStore",
    # LLM-powered suggestions
    "RecoverySuggestion",
    "RecoverySuggester",
]
