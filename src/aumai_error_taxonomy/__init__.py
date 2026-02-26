"""AumAI ErrorTaxonomy — standardised agent error codes and classification."""

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

__version__ = "0.1.0"

__all__ = [
    "ERROR_REGISTRY",
    "AgentErrorException",
    "UnknownErrorCode",
    "classify_exception",
    "create_error_response",
    "errors_by_category",
    "lookup_error",
    "AgentError",
    "ErrorCategory",
    "ErrorRegistry",
]
