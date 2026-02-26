"""CLI entry point for aumai-error-taxonomy."""

from __future__ import annotations

import json
import sys

import click

from aumai_error_taxonomy.core import (
    UnknownErrorCode,
    classify_exception,
    create_error_response,
    errors_by_category,
    lookup_error,
)
from aumai_error_taxonomy.models import AgentError, ErrorCategory

_CATEGORY_COLOURS: dict[str, str] = {
    "model": "cyan",
    "tool": "blue",
    "security": "red",
    "resource": "yellow",
    "orchestration": "magenta",
    "data": "green",
}

_SEVERITY_COLOURS: dict[str, str] = {
    "critical": "red",
    "high": "yellow",
    "medium": "cyan",
    "low": "white",
}


def _format_error_row(error: AgentError) -> str:
    """Return a one-line summary for *error*."""
    cat_colour = _CATEGORY_COLOURS.get(error.category.value, "white")
    sev_colour = _SEVERITY_COLOURS.get(error.severity, "white")
    retry_label = "retry" if error.retryable else "no-retry"
    return (
        click.style(f"{error.code:>4}", fg="white", bold=True)
        + "  "
        + click.style(f"{error.category.value:<15}", fg=cat_colour)
        + click.style(f"{error.severity:<10}", fg=sev_colour)
        + click.style(f"[{retry_label}]", fg="white")
        + f"  {error.name}"
    )


@click.group()
@click.version_option()
def main() -> None:
    """AumAI ErrorTaxonomy CLI — browse and inspect agent error codes."""


@main.command("list")
@click.option(
    "--category",
    "-c",
    type=click.Choice(
        [cat.value for cat in ErrorCategory], case_sensitive=False
    ),
    default=None,
    help="Filter by error category.",
)
@click.option("--json", "output_json", is_flag=True, default=False, help="Output as JSON.")
def list_command(category: str | None, output_json: bool) -> None:
    """List all registered error codes, optionally filtered by category."""
    from aumai_error_taxonomy.core import ERROR_REGISTRY

    errors = sorted(ERROR_REGISTRY.values(), key=lambda e: e.code)
    if category:
        cat_enum = ErrorCategory(category.lower())
        errors = [e for e in errors if e.category == cat_enum]

    if output_json:
        data = [e.model_dump() for e in errors]
        click.echo(json.dumps(data, indent=2))
        return

    if not errors:
        click.echo("No errors found for the given filter.")
        return

    click.echo(
        click.style(f"{'CODE':>4}  {'CATEGORY':<15}{'SEVERITY':<10}{'RETRY':<12}NAME", bold=True)
    )
    click.echo("-" * 70)
    for error in errors:
        click.echo(_format_error_row(error))


@main.command("lookup")
@click.argument("code", type=int)
@click.option("--json", "output_json", is_flag=True, default=False, help="Output as JSON.")
def lookup_command(code: int, output_json: bool) -> None:
    """Look up a specific error by its numeric code."""
    try:
        error = lookup_error(code)
    except UnknownErrorCode:
        click.echo(f"Error: no error registered for code {code}", err=True)
        sys.exit(1)

    if output_json:
        click.echo(json.dumps(create_error_response(error), indent=2))
        return

    cat_colour = _CATEGORY_COLOURS.get(error.category.value, "white")
    sev_colour = _SEVERITY_COLOURS.get(error.severity, "white")
    click.echo(click.style(f"Error {error.code}: {error.name}", bold=True))
    click.echo(f"  Category  : {click.style(error.category.value, fg=cat_colour)}")
    click.echo(f"  Severity  : {click.style(error.severity, fg=sev_colour)}")
    click.echo(f"  Retryable : {error.retryable}")
    click.echo(f"  Description:\n    {error.description}")


@main.command("classify")
@click.argument("exception_name", metavar="EXCEPTION_NAME")
@click.option("--json", "output_json", is_flag=True, default=False, help="Output as JSON.")
def classify_command(exception_name: str, output_json: bool) -> None:
    """Classify an exception type name to the closest agent error.

    Example: aumai-error-taxonomy classify TimeoutError
    """
    # Resolve name to an actual exception class if possible.
    exc_class = _resolve_exception(exception_name)
    if exc_class is None:
        click.echo(
            f"Warning: could not resolve '{exception_name}' to a known exception; "
            "using generic ValueError.",
            err=True,
        )
        exc_instance: BaseException = ValueError(exception_name)
    else:
        exc_instance = exc_class(exception_name)

    error = classify_exception(exc_instance)

    if output_json:
        click.echo(json.dumps(create_error_response(error), indent=2))
        return

    click.echo(
        f"'{exception_name}' maps to "
        + click.style(f"[{error.code}] {error.name}", bold=True)
        + f" ({error.category.value})"
    )
    click.echo(f"  {error.description}")


def _resolve_exception(name: str) -> type[BaseException] | None:
    """Try to resolve an exception type name from Python builtins."""
    candidate = __builtins__  # type: ignore[assignment]
    if isinstance(candidate, dict):
        obj = candidate.get(name)
    else:
        obj = getattr(candidate, name, None)
    if obj is not None and isinstance(obj, type) and issubclass(obj, BaseException):
        return obj
    return None


if __name__ == "__main__":
    main()
