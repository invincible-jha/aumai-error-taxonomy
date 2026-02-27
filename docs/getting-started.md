# Getting Started with aumai-error-taxonomy

This guide takes you from a fresh Python environment to using standardised agent error codes in your own agent code.

---

## Prerequisites

- Python 3.11 or later
- `pip` (comes with Python)

Verify:

```bash
python --version
# Python 3.11.x or later
```

---

## Installation

### From PyPI (recommended)

```bash
pip install aumai-error-taxonomy
```

Verify:

```bash
aumai-error-taxonomy --version
# aumai-error-taxonomy, version 0.1.0
```

### From source

```bash
git clone https://github.com/aumai/aumai-error-taxonomy.git
cd aumai-error-taxonomy
pip install .
```

### Development mode

```bash
git clone https://github.com/aumai/aumai-error-taxonomy.git
cd aumai-error-taxonomy
pip install -e ".[dev]"
```

---

## Your First Error Lookup

### Step 1 — Browse available codes

```bash
aumai-error-taxonomy list
```

You will see a colour-coded table:

```
CODE  CATEGORY       SEVERITY  RETRY       NAME
----------------------------------------------------------------------
 101  model          high      [no-retry]  model_not_found
 102  model          medium    [no-retry]  model_context_overflow
 103  model          high      [retry]     model_timeout
...
 304  security       critical  [no-retry]  injection_detected
 305  security       critical  [no-retry]  sandbox_escape_attempt
...
```

### Step 2 — Filter by category

```bash
aumai-error-taxonomy list --category security
```

### Step 3 — Look up a specific code

```bash
aumai-error-taxonomy lookup 304
```

Output:

```
Error 304: injection_detected
  Category  : security
  Severity  : critical
  Retryable : False
  Description:
    A prompt or command injection attempt was detected and blocked.
```

### Step 4 — Classify a Python exception

```bash
aumai-error-taxonomy classify TimeoutError
```

Output:

```
'TimeoutError' maps to [103] model_timeout (model)
  The model did not respond within the allowed time limit.
```

### Step 5 — Use in Python

```python
from aumai_error_taxonomy import lookup_error, classify_exception

# Direct lookup
error = lookup_error(103)
print(error.name)       # "model_timeout"
print(error.retryable)  # True

# Exception classification
try:
    raise TimeoutError("no response in 30s")
except TimeoutError as exc:
    agent_error = classify_exception(exc)
    print(agent_error.code)  # 103
```

---

## Common Patterns

### Pattern 1 — Retry controller

A retry controller needs two pieces of information: is this error retryable, and how severe is it? Both are available on `AgentError`:

```python
import time
from aumai_error_taxonomy import classify_exception, AgentErrorException, lookup_error

MAX_RETRIES = 3

def call_with_retry(func: callable, *args: object) -> object:
    """Call func, retrying on retryable agent errors."""
    last_error: AgentErrorException | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return func(*args)
        except Exception as exc:
            agent_error = classify_exception(exc)
            last_error = AgentErrorException(agent_error, details=str(exc))
            if not agent_error.retryable:
                raise last_error from exc
            if attempt < MAX_RETRIES:
                wait_seconds = 2 ** attempt  # exponential backoff
                print(f"Attempt {attempt} failed with [{agent_error.code}] "
                      f"{agent_error.name}. Retrying in {wait_seconds}s...")
                time.sleep(wait_seconds)
    raise last_error  # type: ignore[misc]
```

---

### Pattern 2 — Structured error response in a FastAPI handler

Use `create_error_response()` to build consistent JSON error payloads in your API:

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from aumai_error_taxonomy import classify_exception, create_error_response

app = FastAPI()

@app.exception_handler(Exception)
async def agent_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Map any unhandled exception to a structured agent error response."""
    agent_error = classify_exception(exc)
    response_body = create_error_response(agent_error, details=str(exc))

    # Map severity to HTTP status codes
    status_map = {
        "critical": 403,
        "high": 500,
        "medium": 422,
        "low": 400,
    }
    status_code = status_map.get(agent_error.severity, 500)
    return JSONResponse(status_code=status_code, content=response_body)
```

---

### Pattern 3 — Alerting severity routing

Route alerts to different channels based on error severity:

```python
from aumai_error_taxonomy import classify_exception, ErrorCategory

def handle_agent_failure(exc: Exception) -> None:
    """Route agent failures to the correct alerting channel."""
    error = classify_exception(exc)

    if error.severity == "critical":
        # Page on-call immediately
        send_pagerduty_alert(
            title=f"[CRITICAL] Agent error {error.code}: {error.name}",
            body=error.description,
        )
    elif error.severity == "high":
        # Post to #incidents Slack channel
        send_slack_message(
            channel="#incidents",
            text=f"[HIGH] Agent error {error.code}: {error.name}",
        )
    else:
        # Log to error tracking (Sentry, PostHog, etc.)
        log_error_to_tracker(error)

    # Special handling for security category — always alert regardless of severity
    if error.category == ErrorCategory.security:
        notify_security_team(error)
```

---

### Pattern 4 — Wrapping known error codes with AgentErrorException

When your agent code detects a specific condition, raise `AgentErrorException` with the matching code instead of a generic exception:

```python
from aumai_error_taxonomy import lookup_error, AgentErrorException

def classify_ticket(ticket_text: str) -> str:
    """Classify a support ticket. Raises AgentErrorException on policy violations."""
    # Check for PII before processing
    if contains_pii(ticket_text):
        raise AgentErrorException(
            lookup_error(604),   # pii_detected
            details=f"Ticket text contains PII in fields: email, phone",
        )

    # Check iteration budget
    if iteration_count > MAX_ITERATIONS:
        raise AgentErrorException(
            lookup_error(501),   # max_iterations_exceeded
            details=f"Exceeded {MAX_ITERATIONS} classification attempts",
        )

    return run_classifier(ticket_text)
```

---

### Pattern 5 — Browse the registry programmatically

Build dashboards or documentation directly from the registry:

```python
from aumai_error_taxonomy import ERROR_REGISTRY, ErrorCategory, errors_by_category

# Count errors by category
for category in ErrorCategory:
    errors = errors_by_category(category)
    retryable_count = sum(1 for e in errors if e.retryable)
    print(f"{category.value:15s}: {len(errors):2d} codes, {retryable_count} retryable")

# Find all non-retryable, critical errors (these need immediate human attention)
critical_non_retryable = [
    e for e in ERROR_REGISTRY.values()
    if e.severity == "critical" and not e.retryable
]
print(f"\nCritical non-retryable errors ({len(critical_non_retryable)}):")
for err in sorted(critical_non_retryable, key=lambda e: e.code):
    print(f"  [{err.code}] {err.name}: {err.description}")
```

---

## Troubleshooting FAQ

**Q: `classify_exception` returns error 601 for my custom exception**

601 (`data_schema_violation`) is the fallback when no mapping exists. The mapping table covers Python built-in exceptions only. If you have a custom exception, either map it explicitly in your code or subclass a built-in exception that has a natural mapping (e.g. subclass `TimeoutError` for timeout conditions).

---

**Q: I want to add my own error codes**

Use `ErrorRegistry` directly:

```python
from aumai_error_taxonomy import AgentError, ErrorCategory, ErrorRegistry

registry = ErrorRegistry()
registry.register(AgentError(
    code=701,
    category=ErrorCategory.data,
    name="my_custom_error",
    description="A custom error for my application.",
    retryable=False,
    severity="medium",
))
custom_error = registry.get(701)
```

Note: this creates a local registry that is separate from the built-in `ERROR_REGISTRY`. The `lookup_error()` function and CLI always use the built-in registry.

---

**Q: How does `classify_exception` handle exception inheritance?**

The mapping list is ordered most-specific first. `ConnectionRefusedError` and `ConnectionResetError` are listed before `ConnectionError` because they are subclasses of it. If you have a deeply nested exception hierarchy, the first matching `isinstance()` check wins. Always verify the returned error code makes sense for your exception.

---

**Q: The `--json` flag on `lookup` outputs an `error` wrapper — is that intentional?**

Yes. `lookup --json` calls `create_error_response()` internally, which wraps the error in a top-level `"error"` key and adds a UTC `"timestamp"`. This matches the format you would send to a client or log to a structured logging system. If you only want the raw error fields, use `errors_by_category()` or the `ERROR_REGISTRY` in Python.

---

**Q: Can I use this with Python 3.10?**

The package requires Python 3.11 or later. The `3.11+` requirement exists because `tomllib` (used by hatchling build) is a standard library module from 3.11, and the type annotation style used throughout the codebase targets 3.11+.

---

## Next Steps

- Read the [API Reference](api-reference.md) for complete class and method documentation
- See the [examples/quickstart.py](../examples/quickstart.py) for runnable demo code
- Integrate with [aumai-policycompiler](https://github.com/aumai/aumai-policycompiler) to raise `policy_violation` (303) errors from compiled policy enforcement
