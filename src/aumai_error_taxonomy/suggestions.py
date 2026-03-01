"""LLM-powered recovery suggestions for classified agent errors."""

from __future__ import annotations

import json
import logging
from typing import Any

from aumai_llm_core import LLMClient, ModelConfig, MockProvider
from aumai_llm_core.models import CompletionRequest, Message
from pydantic import BaseModel, Field

from aumai_error_taxonomy.models import AgentError, ErrorCategory

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Output model
# ---------------------------------------------------------------------------


class RecoverySuggestion(BaseModel):
    """Structured recovery suggestion for a classified agent error.

    Attributes:
        suggestion: One-sentence summary of the recommended remediation.
        confidence: Confidence level of the suggestion: ``"high"``, ``"medium"``,
            or ``"low"``.
        steps: Ordered list of concrete remediation steps the operator should
            take.
        references: Optional list of reference strings (doc URLs, KB articles,
            etc.) the operator may consult.
    """

    suggestion: str = Field(description="One-sentence summary of the recommended remediation.")
    confidence: str = Field(description="Confidence level: high, medium, or low.")
    steps: list[str] = Field(description="Ordered remediation steps.", default_factory=list)
    references: list[str] = Field(description="Optional reference links.", default_factory=list)


# ---------------------------------------------------------------------------
# Static fallback suggestions (no LLM required)
# ---------------------------------------------------------------------------

_STATIC_SUGGESTIONS: dict[int, RecoverySuggestion] = {
    # Model errors
    101: RecoverySuggestion(
        suggestion="Verify the model identifier and ensure the provider has it available.",
        confidence="high",
        steps=[
            "Check that the model_id matches an active model in the provider dashboard.",
            "Update the model configuration to a currently available model.",
            "Confirm the account has access to the requested model tier.",
        ],
        references=["https://docs.aumai.dev/errors/101"],
    ),
    102: RecoverySuggestion(
        suggestion="Reduce the input size or enable context-window chunking.",
        confidence="high",
        steps=[
            "Measure the token count of the prompt before sending.",
            "Truncate or summarise historical context to fit within the limit.",
            "Consider using a model with a larger context window.",
        ],
        references=["https://docs.aumai.dev/errors/102"],
    ),
    103: RecoverySuggestion(
        suggestion="Retry the request with an exponential back-off strategy.",
        confidence="high",
        steps=[
            "Wait at least 2 seconds before the first retry.",
            "Use exponential back-off with jitter for subsequent retries.",
            "Set a maximum retry budget (e.g., 3 attempts).",
            "Alert if retries are exhausted without success.",
        ],
        references=["https://docs.aumai.dev/errors/103"],
    ),
    104: RecoverySuggestion(
        suggestion="Back off and retry after the rate-limit reset window expires.",
        confidence="high",
        steps=[
            "Inspect the Retry-After header in the provider response.",
            "Implement token-bucket or leaky-bucket rate limiting client-side.",
            "Consider distributing load across multiple API keys if permitted.",
        ],
        references=["https://docs.aumai.dev/errors/104"],
    ),
    105: RecoverySuggestion(
        suggestion="Retry with a clearer prompt that enforces the expected output schema.",
        confidence="medium",
        steps=[
            "Add a JSON schema or structured-output instruction to the system prompt.",
            "Enable provider-level JSON mode if available.",
            "Validate the output against the schema and retry if parsing fails.",
        ],
        references=["https://docs.aumai.dev/errors/105"],
    ),
    # Tool errors
    201: RecoverySuggestion(
        suggestion="Register the missing tool before invoking the agent.",
        confidence="high",
        steps=[
            "Check the tool registry for the expected tool name.",
            "Ensure the tool package is installed and imported.",
            "Restart the agent after registering the missing tool.",
        ],
        references=["https://docs.aumai.dev/errors/201"],
    ),
    202: RecoverySuggestion(
        suggestion="Wrap the tool in defensive error handling and retry.",
        confidence="medium",
        steps=[
            "Add try/except inside the tool implementation.",
            "Log the full stack trace for post-mortem analysis.",
            "Retry the tool invocation if the error is transient.",
        ],
        references=["https://docs.aumai.dev/errors/202"],
    ),
    203: RecoverySuggestion(
        suggestion="Fix the input schema and validate arguments before tool invocation.",
        confidence="high",
        steps=[
            "Review the tool's input schema documentation.",
            "Add Pydantic validation at the call site.",
            "Return a structured error to the agent so it can self-correct.",
        ],
        references=["https://docs.aumai.dev/errors/203"],
    ),
    # Security errors
    301: RecoverySuggestion(
        suggestion="Refresh or reissue credentials and re-authenticate.",
        confidence="high",
        steps=[
            "Check credential expiry timestamps.",
            "Rotate the API key or JWT token.",
            "Verify that environment variables are correctly injected.",
        ],
        references=["https://docs.aumai.dev/errors/301"],
    ),
    302: RecoverySuggestion(
        suggestion="Grant the required permissions to the agent's identity.",
        confidence="high",
        steps=[
            "Review the IAM or RBAC policy for the agent role.",
            "Add the required permission or scope.",
            "Avoid granting blanket admin permissions; use least-privilege.",
        ],
        references=["https://docs.aumai.dev/errors/302"],
    ),
    # Resource errors
    401: RecoverySuggestion(
        suggestion="Reduce memory usage or increase the resource limit.",
        confidence="medium",
        steps=[
            "Profile memory usage to identify the largest allocations.",
            "Process data in smaller batches.",
            "Increase container/VM memory limits if the workload requires it.",
        ],
        references=["https://docs.aumai.dev/errors/401"],
    ),
    404: RecoverySuggestion(
        suggestion="Check network connectivity and retry with back-off.",
        confidence="high",
        steps=[
            "Ping the target endpoint to verify reachability.",
            "Review firewall and VPC routing rules.",
            "Implement retry logic with exponential back-off.",
        ],
        references=["https://docs.aumai.dev/errors/404"],
    ),
    # Orchestration errors
    501: RecoverySuggestion(
        suggestion="Increase the iteration budget or redesign the task decomposition.",
        confidence="medium",
        steps=[
            "Analyse the agent's reasoning trace to find the loop.",
            "Increase max_iterations if the task is legitimately complex.",
            "Add a termination condition to the agent's planning step.",
        ],
        references=["https://docs.aumai.dev/errors/501"],
    ),
    # Data errors
    601: RecoverySuggestion(
        suggestion="Validate the data against the expected schema before processing.",
        confidence="high",
        steps=[
            "Add a Pydantic validation step at the data ingestion boundary.",
            "Log the invalid payload for debugging.",
            "Return a structured error to the upstream caller.",
        ],
        references=["https://docs.aumai.dev/errors/601"],
    ),
    604: RecoverySuggestion(
        suggestion="Redact or remove PII before passing data to the agent.",
        confidence="high",
        steps=[
            "Run a PII detection scan on all input data.",
            "Replace detected PII with placeholder tokens.",
            "Review data handling policies and update consent records.",
        ],
        references=["https://docs.aumai.dev/errors/604"],
    ),
}

_CATEGORY_STATIC_SUGGESTIONS: dict[ErrorCategory, RecoverySuggestion] = {
    ErrorCategory.model: RecoverySuggestion(
        suggestion="Investigate the model provider configuration and retry.",
        confidence="low",
        steps=[
            "Review the model configuration for the failing agent.",
            "Check the provider status page for outages.",
            "Retry the operation after verifying the configuration.",
        ],
    ),
    ErrorCategory.tool: RecoverySuggestion(
        suggestion="Inspect the tool registry and fix the failing tool.",
        confidence="low",
        steps=[
            "List all registered tools and verify the expected tool is present.",
            "Review the tool's error logs for root-cause details.",
            "Fix the tool implementation and redeploy.",
        ],
    ),
    ErrorCategory.security: RecoverySuggestion(
        suggestion="Review the agent's security policy and credentials.",
        confidence="low",
        steps=[
            "Audit the agent's permissions and role assignments.",
            "Rotate all credentials involved in the failing operation.",
            "Escalate to the security team if a breach is suspected.",
        ],
    ),
    ErrorCategory.resource: RecoverySuggestion(
        suggestion="Free resources or scale the agent's environment.",
        confidence="low",
        steps=[
            "Profile the agent's resource consumption.",
            "Reduce batch sizes to lower peak resource usage.",
            "Scale up the agent's compute allocation.",
        ],
    ),
    ErrorCategory.orchestration: RecoverySuggestion(
        suggestion="Simplify the agent's task graph and add loop guards.",
        confidence="low",
        steps=[
            "Visualise the task dependency graph.",
            "Add explicit termination conditions to all loops.",
            "Limit the maximum depth of recursive sub-task calls.",
        ],
    ),
    ErrorCategory.data: RecoverySuggestion(
        suggestion="Validate data at all system boundaries.",
        confidence="low",
        steps=[
            "Add schema validation at the data ingestion point.",
            "Log raw payloads for inspection.",
            "Sanitise and normalise inputs before processing.",
        ],
    ),
}


# ---------------------------------------------------------------------------
# System prompt template
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are an expert AI agent reliability engineer. "
    "Given a classified agent error code and optional context, produce a "
    "structured JSON recovery suggestion with the following fields:\n"
    "- suggestion: (string) one-sentence remediation summary\n"
    "- confidence: (string) one of: high, medium, low\n"
    "- steps: (array of strings) ordered remediation steps\n"
    "- references: (array of strings) optional reference links\n"
    "Respond with a valid JSON object only. Do not include markdown fences."
)


# ---------------------------------------------------------------------------
# RecoverySuggester
# ---------------------------------------------------------------------------


class RecoverySuggester:
    """Generate recovery suggestions for classified agent errors via LLM.

    By default uses :class:`~aumai_llm_core.MockProvider` so no real API
    calls are made.  Pass a custom :class:`~aumai_llm_core.LLMClient` for
    production usage.

    Args:
        client: An :class:`~aumai_llm_core.LLMClient` to use.  Defaults to a
            client backed by :class:`~aumai_llm_core.MockProvider`.

    Example::

        suggester = RecoverySuggester()
        suggestion = await suggester.suggest(error_code=103, context="model timed out")
        print(suggestion.suggestion)
    """

    def __init__(self, client: LLMClient | None = None) -> None:
        if client is None:
            mock_response = json.dumps(
                {
                    "suggestion": "Retry the operation using exponential back-off.",
                    "confidence": "medium",
                    "steps": [
                        "Wait before retrying.",
                        "Implement back-off logic.",
                        "Alert if retries are exhausted.",
                    ],
                    "references": [],
                }
            )
            mock_provider = MockProvider(responses=[mock_response])
            config = ModelConfig(provider="mock", model_id="mock-model")
            client = LLMClient(config)
            # Monkey-patch the internal provider so the mock is used directly.
            client._provider = mock_provider  # type: ignore[attr-defined]
        self._client = client

    @property
    def client(self) -> LLMClient:
        """The underlying :class:`~aumai_llm_core.LLMClient`."""
        return self._client

    # ------------------------------------------------------------------
    # Primary API
    # ------------------------------------------------------------------

    async def suggest(
        self,
        error_code: int,
        context: str = "",
        agent_id: str = "",
    ) -> RecoverySuggestion:
        """Generate a :class:`RecoverySuggestion` for *error_code*.

        Attempts to call the configured LLM.  Falls back to the built-in
        static suggestion table when the LLM call fails or returns
        unparseable output.

        Args:
            error_code: Numeric error code from the taxonomy.
            context: Optional human-readable context from the failing agent.
            agent_id: Optional agent identifier (included in the LLM prompt).

        Returns:
            A :class:`RecoverySuggestion` with actionable remediation advice.
        """
        try:
            return await self._suggest_via_llm(
                error_code=error_code,
                context=context,
                agent_id=agent_id,
            )
        except Exception as exc:
            logger.warning(
                "LLM suggestion failed for error code %d: %s. "
                "Falling back to static suggestion.",
                error_code,
                exc,
            )
            return self._static_suggestion(error_code)

    async def suggest_for_error(
        self,
        error: AgentError,
        context: str = "",
        agent_id: str = "",
    ) -> RecoverySuggestion:
        """Generate a suggestion given a full :class:`AgentError` instance.

        Args:
            error: The classified :class:`~aumai_error_taxonomy.models.AgentError`.
            context: Optional human-readable context.
            agent_id: Optional agent identifier.

        Returns:
            A :class:`RecoverySuggestion`.
        """
        return await self.suggest(
            error_code=error.code,
            context=context,
            agent_id=agent_id,
        )

    def suggest_static(self, error_code: int) -> RecoverySuggestion:
        """Return the static (non-LLM) suggestion for *error_code*.

        This is a synchronous convenience method that never calls the LLM.

        Args:
            error_code: Numeric error code from the taxonomy.

        Returns:
            A :class:`RecoverySuggestion` from the built-in static table.
        """
        return self._static_suggestion(error_code)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _suggest_via_llm(
        self,
        error_code: int,
        context: str,
        agent_id: str,
    ) -> RecoverySuggestion:
        """Ask the LLM for a recovery suggestion and parse the response.

        Args:
            error_code: Numeric error code.
            context: Optional context string.
            agent_id: Optional agent identifier.

        Returns:
            Parsed :class:`RecoverySuggestion`.

        Raises:
            Exception: If the LLM call fails or the response cannot be parsed.
        """
        user_content = self._build_user_prompt(
            error_code=error_code,
            context=context,
            agent_id=agent_id,
        )
        messages: list[Message] = [
            Message(role="system", content=_SYSTEM_PROMPT),
            Message(role="user", content=user_content),
        ]
        request = CompletionRequest(messages=messages)
        response = await self._client.complete(request)
        return self._parse_response(response.content)

    def _build_user_prompt(
        self,
        error_code: int,
        context: str,
        agent_id: str,
    ) -> str:
        """Construct the user-facing LLM prompt.

        Args:
            error_code: Numeric error code.
            context: Optional context string.
            agent_id: Optional agent identifier.

        Returns:
            Formatted prompt string.
        """
        parts: list[str] = [f"Agent error code: {error_code}"]
        if agent_id:
            parts.append(f"Agent ID: {agent_id}")
        if context:
            parts.append(f"Context: {context}")
        parts.append(
            "Please provide a structured JSON recovery suggestion for this error."
        )
        return "\n".join(parts)

    def _parse_response(self, content: str) -> RecoverySuggestion:
        """Parse LLM response text into a :class:`RecoverySuggestion`.

        Strips markdown code fences if present before parsing JSON.

        Args:
            content: Raw text from the LLM.

        Returns:
            Validated :class:`RecoverySuggestion`.

        Raises:
            ValueError: If the content cannot be parsed as JSON or validated.
        """
        stripped = content.strip()
        if stripped.startswith("```"):
            lines = stripped.splitlines()
            # Drop first and last fence lines.
            stripped = "\n".join(lines[1:-1]).strip()
        data: Any = json.loads(stripped)
        if not isinstance(data, dict):
            raise ValueError(f"Expected a JSON object, got {type(data).__name__}")
        # Normalise confidence to one of the allowed values.
        raw_confidence = str(data.get("confidence", "low")).lower()
        if raw_confidence not in {"high", "medium", "low"}:
            raw_confidence = "low"
        data["confidence"] = raw_confidence
        return RecoverySuggestion.model_validate(data)

    def _static_suggestion(self, error_code: int) -> RecoverySuggestion:
        """Return a static suggestion for *error_code*.

        Falls back through:
        1. Per-code static table.
        2. Per-category static table (if the code is in the global registry).
        3. Generic fallback.

        Args:
            error_code: Numeric error code from the taxonomy.

        Returns:
            :class:`RecoverySuggestion`.
        """
        if error_code in _STATIC_SUGGESTIONS:
            return _STATIC_SUGGESTIONS[error_code]

        from aumai_error_taxonomy.core import ERROR_REGISTRY

        error = ERROR_REGISTRY.get(error_code)
        if error is not None and error.category in _CATEGORY_STATIC_SUGGESTIONS:
            return _CATEGORY_STATIC_SUGGESTIONS[error.category]

        return RecoverySuggestion(
            suggestion="Review the agent logs and consult the AumAI error taxonomy documentation.",
            confidence="low",
            steps=[
                "Inspect the agent's structured error response for details.",
                "Cross-reference the error code with the AumAI error taxonomy.",
                "Escalate to the engineering team if the issue persists.",
            ],
            references=["https://docs.aumai.dev/errors"],
        )


__all__ = [
    "RecoverySuggestion",
    "RecoverySuggester",
]
