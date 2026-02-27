# API Reference — aumai-error-taxonomy

Complete reference for all public classes, functions, and Pydantic models.

All symbols are importable from the top-level package:

```python
from aumai_error_taxonomy import (
    # Registry and lookup
    ERROR_REGISTRY,
    lookup_error,
    errors_by_category,
    classify_exception,
    create_error_response,
    # Exceptions
    UnknownErrorCode,
    AgentErrorException,
    # Models
    AgentError,
    ErrorCategory,
    ErrorRegistry,
)
```

---

## Models (`aumai_error_taxonomy.models`)

### `ErrorCategory`

```python
class ErrorCategory(str, Enum):
    model = "model"           # 1xx
    tool = "tool"             # 2xx
    security = "security"     # 3xx
    resource = "resource"     # 4xx
    orchestration = "orchestration"  # 5xx
    data = "data"             # 6xx
```

Enumeration of the six top-level error categories. The numeric range convention mirrors HTTP status codes: the first digit identifies the category.

Being a `str` enum, values compare equal to their string equivalents:

```python
from aumai_error_taxonomy import ErrorCategory

cat = ErrorCategory.security
print(cat == "security")    # True
print(cat.value)            # "security"
```

---

### `AgentError`

```python
class AgentError(BaseModel):
    code: int
    category: ErrorCategory
    name: str
    description: str
    retryable: bool
    severity: str
```

The canonical definition of a single agent error. Instances are stored in `ERROR_REGISTRY` and returned by `lookup_error()` and `classify_exception()`.

#### Fields

| Field | Type | Description |
|---|---|---|
| `code` | `int` | Numeric error code (e.g. `101`, `304`). Must be a positive integer. |
| `category` | `ErrorCategory` | The top-level error category. |
| `name` | `str` | Short, snake_case machine-readable identifier (e.g. `"model_timeout"`). |
| `description` | `str` | Human-readable explanation of when and why this error occurs. |
| `retryable` | `bool` | `True` if the failed operation can safely be retried without human intervention. |
| `severity` | `str` | Operational severity. Must be one of: `"critical"`, `"high"`, `"medium"`, `"low"`. |

#### Validators

- `severity` must be one of `{"critical", "high", "medium", "low"}`. Other values raise `pydantic.ValidationError`.
- `code` must be a positive integer (> 0). Zero or negative values raise `pydantic.ValidationError`.

#### Example

```python
from aumai_error_taxonomy import lookup_error

error = lookup_error(304)
print(error.code)          # 304
print(error.category)      # ErrorCategory.security
print(error.name)          # "injection_detected"
print(error.description)   # "A prompt or command injection attempt was detected and blocked."
print(error.severity)      # "critical"
print(error.retryable)     # False

# Serialise to dict
data = error.model_dump()
```

---

### `ErrorRegistry`

```python
class ErrorRegistry(BaseModel):
    errors: dict[int, AgentError] = {}

    def register(self, error: AgentError) -> None: ...
    def get(self, code: int) -> AgentError | None: ...
    def by_category(self, category: ErrorCategory) -> list[AgentError]: ...
```

A Pydantic-backed container for a set of `AgentError` definitions. Use this when you need a custom registry separate from the built-in `ERROR_REGISTRY`.

#### Fields

| Field | Type | Description |
|---|---|---|
| `errors` | `dict[int, AgentError]` | Mapping of numeric error code to `AgentError` definition. |

#### Methods

---

##### `ErrorRegistry.register(error)`

Add or replace an error in this registry.

**Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `error` | `AgentError` | The error definition to register. Overwrites any existing entry for the same code. |

**Returns:** `None`

---

##### `ErrorRegistry.get(code)`

Return the `AgentError` for `code`, or `None` if not found.

**Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `code` | `int` | The numeric error code to look up. |

**Returns:** `AgentError | None`

---

##### `ErrorRegistry.by_category(category)`

Return all errors in this registry belonging to `category`.

**Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `category` | `ErrorCategory` | The category to filter by. |

**Returns:** `list[AgentError]` — unsorted; order matches insertion order.

#### Example

```python
from aumai_error_taxonomy import AgentError, ErrorCategory, ErrorRegistry

# Build a custom registry for application-specific errors
registry = ErrorRegistry()
registry.register(AgentError(
    code=701,
    category=ErrorCategory.data,
    name="invalid_order_state",
    description="The order is in a state that does not permit this operation.",
    retryable=False,
    severity="medium",
))

error = registry.get(701)
print(error.name)  # "invalid_order_state"

data_errors = registry.by_category(ErrorCategory.data)
print(len(data_errors))  # 1
```

---

## Module-Level Registry (`aumai_error_taxonomy.core`)

### `ERROR_REGISTRY`

```python
ERROR_REGISTRY: Final[dict[int, AgentError]]
```

The built-in registry containing all 30 pre-defined error codes, built at module import time. This is a plain Python `dict` keyed by integer error code.

```python
from aumai_error_taxonomy import ERROR_REGISTRY

print(len(ERROR_REGISTRY))  # 30

# Iterate all errors
for code, error in sorted(ERROR_REGISTRY.items()):
    print(f"{code:4d}  {error.name}")

# Direct access by code
error = ERROR_REGISTRY[103]
print(error.name)   # "model_timeout"
```

---

## Functions (`aumai_error_taxonomy.core`)

### `lookup_error(code)`

```python
def lookup_error(code: int) -> AgentError: ...
```

Return the `AgentError` for `code` from `ERROR_REGISTRY`.

**Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `code` | `int` | The numeric error code to look up. |

**Returns:** `AgentError`

**Raises:** `UnknownErrorCode` (subclass of `KeyError`) when `code` is not present in the registry.

**Example:**

```python
from aumai_error_taxonomy import lookup_error, UnknownErrorCode

try:
    error = lookup_error(103)
    print(error.name)   # "model_timeout"
except UnknownErrorCode as exc:
    print(f"Not found: {exc}")
```

---

### `errors_by_category(category)`

```python
def errors_by_category(category: ErrorCategory) -> list[AgentError]: ...
```

Return all errors in `ERROR_REGISTRY` belonging to `category`, sorted by code ascending.

**Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `category` | `ErrorCategory` | The category to filter by. |

**Returns:** `list[AgentError]` — sorted by `code` ascending.

**Example:**

```python
from aumai_error_taxonomy import errors_by_category, ErrorCategory

model_errors = errors_by_category(ErrorCategory.model)
for err in model_errors:
    print(f"  {err.code}: {err.name} (retryable={err.retryable})")
# 101: model_not_found (retryable=False)
# 102: model_context_overflow (retryable=False)
# 103: model_timeout (retryable=True)
# ...
```

---

### `classify_exception(exc)`

```python
def classify_exception(exc: BaseException) -> AgentError: ...
```

Map a Python exception instance to the closest `AgentError`.

**Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `exc` | `BaseException` | The exception instance to classify. |

**Returns:** `AgentError` — the closest match from `ERROR_REGISTRY`.

**Fallback behaviour:** If no mapping exists for the exception's type, returns error 601 (`data_schema_violation`) as the most neutral generic error.

**Exception mapping table** (ordered most-specific first):

| Python Exception | Error Code | Error Name |
|---|---|---|
| `TimeoutError` | 103 | `model_timeout` |
| `ConnectionRefusedError` | 404 | `network_unreachable` |
| `ConnectionResetError` | 404 | `network_unreachable` |
| `ConnectionError` | 404 | `network_unreachable` |
| `socket.timeout` | 103 | `model_timeout` |
| `urllib.error.URLError` | 404 | `network_unreachable` |
| `PermissionError` | 302 | `permission_denied` |
| `FileNotFoundError` | 602 | `data_not_found` |
| `MemoryError` | 401 | `resource_exhausted` |
| `RecursionError` | 501 | `max_iterations_exceeded` |
| `UnicodeDecodeError` | 605 | `encoding_error` |
| `UnicodeEncodeError` | 605 | `encoding_error` |
| `ValueError` | 601 | `data_schema_violation` |
| `KeyError` | 602 | `data_not_found` |
| `TypeError` | 203 | `tool_input_validation_error` |
| `OSError` | 405 | `disk_write_error` |
| *(any other)* | 601 | `data_schema_violation` |

**Example:**

```python
from aumai_error_taxonomy import classify_exception

exc = PermissionError("access denied to /etc/passwd")
error = classify_exception(exc)
print(error.code)     # 302
print(error.name)     # "permission_denied"
print(error.severity) # "critical"
```

---

### `create_error_response(error, details)`

```python
def create_error_response(
    error: AgentError,
    details: str | None = None,
) -> dict[str, object]: ...
```

Return a standardised, JSON-serialisable error response dict.

**Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `error` | `AgentError` | required | The error definition to include in the response. |
| `details` | `str \| None` | `None` | Optional free-text detail string (e.g. exception message, stack trace excerpt). |

**Returns:** `dict[str, object]` with the structure:

```json
{
  "error": {
    "code": 103,
    "name": "model_timeout",
    "category": "model",
    "description": "The model did not respond within the allowed time limit.",
    "severity": "high",
    "retryable": true,
    "details": "No response after 30 seconds",
    "timestamp": "2026-02-27T10:00:00.000000+00:00"
  }
}
```

The `timestamp` field is a UTC ISO 8601 string generated at call time.

**Example:**

```python
from aumai_error_taxonomy import lookup_error, create_error_response
import json

error = lookup_error(304)
response = create_error_response(error, details="Injected payload detected in user input")
print(json.dumps(response, indent=2))
```

---

## Exception Classes

### `UnknownErrorCode`

```python
class UnknownErrorCode(KeyError): ...
```

Raised by `lookup_error()` when the requested code is not in `ERROR_REGISTRY`.

```python
from aumai_error_taxonomy import lookup_error, UnknownErrorCode

try:
    lookup_error(9999)
except UnknownErrorCode as exc:
    print(exc)  # "No error registered for code 9999"
```

---

### `AgentErrorException`

```python
class AgentErrorException(Exception):
    def __init__(self, error: AgentError, details: str | None = None) -> None: ...

    error: AgentError
    details: str | None
```

A raise-able Python exception that carries a fully-typed `AgentError` and optional details string. Useful when you want to propagate structured error metadata through a call stack.

**Constructor parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `error` | `AgentError` | required | The structured error definition. |
| `details` | `str \| None` | `None` | Optional free-text detail string. |

**Attributes:**

| Attribute | Type | Description |
|---|---|---|
| `error` | `AgentError` | The structured error definition passed at construction. |
| `details` | `str \| None` | The optional detail string. |

The exception message is formatted as `"[{code}] {name}: {description}"`. If `details` is provided, it is appended: `"[{code}] {name}: {description} — {details}"`.

**Example:**

```python
from aumai_error_taxonomy import lookup_error, AgentErrorException

def process_data(payload: dict) -> None:
    if "id" not in payload:
        raise AgentErrorException(
            lookup_error(606),   # missing_required_field
            details="Field 'id' is required in the data payload",
        )

try:
    process_data({})
except AgentErrorException as exc:
    print(exc.error.code)      # 606
    print(exc.error.name)      # "missing_required_field"
    print(exc.error.retryable) # False
    print(exc.details)         # "Field 'id' is required in the data payload"
    print(str(exc))            # "[606] missing_required_field: A required field is absent... — Field 'id'..."
```

---

## Package Version

```python
import aumai_error_taxonomy
print(aumai_error_taxonomy.__version__)  # "0.1.0"
```

---

## Complete Import Map

```python
# Registry constant
from aumai_error_taxonomy import ERROR_REGISTRY      # dict[int, AgentError], 30 entries

# Functions
from aumai_error_taxonomy import lookup_error        # int -> AgentError (raises UnknownErrorCode)
from aumai_error_taxonomy import errors_by_category  # ErrorCategory -> list[AgentError]
from aumai_error_taxonomy import classify_exception  # BaseException -> AgentError
from aumai_error_taxonomy import create_error_response  # AgentError -> dict

# Exception classes
from aumai_error_taxonomy import UnknownErrorCode    # KeyError subclass
from aumai_error_taxonomy import AgentErrorException # Exception subclass with .error and .details

# Models
from aumai_error_taxonomy import AgentError          # Single error definition
from aumai_error_taxonomy import ErrorCategory       # Enum: model/tool/security/resource/orchestration/data
from aumai_error_taxonomy import ErrorRegistry       # Custom registry container
```
