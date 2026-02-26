"""Pydantic models for aumai-error-taxonomy."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, field_validator


class ErrorCategory(str, Enum):
    """Top-level error category aligned to numeric ranges."""

    model = "model"  # 1xx
    tool = "tool"  # 2xx
    security = "security"  # 3xx
    resource = "resource"  # 4xx
    orchestration = "orchestration"  # 5xx
    data = "data"  # 6xx


class AgentError(BaseModel):
    """A single standardised agent error definition."""

    code: int = Field(description="Numeric error code (e.g. 101, 201)")
    category: ErrorCategory = Field(description="High-level category for the error")
    name: str = Field(description="Short machine-readable identifier (snake_case)")
    description: str = Field(description="Human-readable explanation of the error")
    retryable: bool = Field(description="Whether the operation can safely be retried")
    severity: str = Field(description="Operational severity: critical, high, medium, low")

    @field_validator("severity")
    @classmethod
    def severity_must_be_valid(cls, value: str) -> str:
        """Restrict severity to known levels."""
        allowed = {"critical", "high", "medium", "low"}
        if value not in allowed:
            raise ValueError(f"severity must be one of {allowed}, got {value!r}")
        return value

    @field_validator("code")
    @classmethod
    def code_must_be_positive(cls, value: int) -> int:
        """Ensure code is a positive integer."""
        if value <= 0:
            raise ValueError(f"code must be a positive integer, got {value}")
        return value


class ErrorRegistry(BaseModel):
    """Container mapping numeric codes to AgentError definitions."""

    errors: dict[int, AgentError] = Field(
        default_factory=dict, description="Mapping of error code to AgentError"
    )

    def register(self, error: AgentError) -> None:
        """Add or replace an error in the registry."""
        self.errors[error.code] = error

    def get(self, code: int) -> AgentError | None:
        """Return the AgentError for *code*, or None if not found."""
        return self.errors.get(code)

    def by_category(self, category: ErrorCategory) -> list[AgentError]:
        """Return all errors belonging to *category*."""
        return [e for e in self.errors.values() if e.category == category]


__all__ = [
    "ErrorCategory",
    "AgentError",
    "ErrorRegistry",
]
