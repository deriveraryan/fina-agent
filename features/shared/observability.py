import os
import sys
import time
import functools
import traceback
from datetime import datetime
from contextlib import contextmanager
from typing import Any, Callable, Generator, Optional
from firebase_functions import logger

# Configurable performance thresholds (in seconds)
DEFAULT_MUTATION_BUDGET = 2.0
DEFAULT_AGENT_BUDGET = 8.0

# Configurable token budgets
DEFAULT_PROMPT_TOKEN_BUDGET = 40000
DEFAULT_CANDIDATE_TOKEN_BUDGET = 4000


class BackendObservability:
    """
    A comprehensive backend telemetry and observability utility.
    Provides structured, contextual logging across trace, info, warning, and error severity levels.
    Enforces trace correlation via Conversation IDs and manages performance/cost budgets.
    """

    @staticmethod
    def _log_to_stderr(severity: str, message: str) -> None:
        """
        Write log message to sys.stderr with timestamp and severity.
        """
        timestamp = datetime.now().isoformat()
        sys.stderr.write(f"{timestamp} [{severity}] {message}\n")
        sys.stderr.flush()

    @staticmethod
    def _format_message(message: str, conversation_id: Optional[str] = None, **kwargs: Any) -> str:
        """
        Formated log string with unified correlation prefixes and structured context tags.
        """
        context_tags = [f"{k}={v}" for k, v in kwargs.items()]
        tag_suffix = f" | {', '.join(context_tags)}" if context_tags else ""
        if conversation_id:
            return f"[Conv: {conversation_id}] {message}{tag_suffix}"
        return f"{message}{tag_suffix}"

    @staticmethod
    def trace(message: str, conversation_id: Optional[str] = None, **kwargs: Any) -> None:
        """
        Log a highly granular trace-level message (maps to GCP DEBUG severity).
        """
        formatted = BackendObservability._format_message(message, conversation_id, **kwargs)
        if os.environ.get("FINA_AGENT_CLI_MODE") == "1":
            BackendObservability._log_to_stderr("DEBUG", formatted)
        else:
            logger.debug(formatted)

    @staticmethod
    def info(message: str, conversation_id: Optional[str] = None, **kwargs: Any) -> None:
        """
        Log an info-level message indicating normal, successful backend operations.
        """
        formatted = BackendObservability._format_message(message, conversation_id, **kwargs)
        if os.environ.get("FINA_AGENT_CLI_MODE") == "1":
            BackendObservability._log_to_stderr("INFO", formatted)
        else:
            logger.info(formatted)

    @staticmethod
    def warning(message: str, conversation_id: Optional[str] = None, **kwargs: Any) -> None:
        """
        Log a warning-level message indicating potential degradation, latency delays, or high resource usage.
        """
        formatted = BackendObservability._format_message(message, conversation_id, **kwargs)
        if os.environ.get("FINA_AGENT_CLI_MODE") == "1":
            BackendObservability._log_to_stderr("WARN", formatted)
        else:
            logger.warn(formatted)

    @staticmethod
    def error(
        message: str,
        conversation_id: Optional[str] = None,
        exception: Optional[Exception] = None,
        **kwargs: Any,
    ) -> None:
        """
        Log an error-level message capturing exception boundaries, tracebacks, and contextual details.
        """
        trace_str = ""
        if exception:
            trace_str = f"\nException Type: {type(exception).__name__}\nDetails: {str(exception)}\nTraceback:\n"
            trace_str += "".join(
                traceback.format_exception(type(exception), exception, exception.__traceback__)
            )

        formatted = BackendObservability._format_message(message, conversation_id, **kwargs)
        if os.environ.get("FINA_AGENT_CLI_MODE") == "1":
            BackendObservability._log_to_stderr("ERROR", f"{formatted}{trace_str}")
        else:
            logger.error(f"{formatted}{trace_str}")

    @staticmethod
    def fatal(
        message: str,
        conversation_id: Optional[str] = None,
        exception: Optional[Exception] = None,
        **kwargs: Any,
    ) -> None:
        """
        Log a critical fatal-level system event (unhandled failure, loop prevention trigger, etc.).
        Utilizes Cloud Logging CRITICAL severity to support immediate operational paging alerts.
        """
        trace_str = ""
        if exception:
            trace_str = f"\nException: {type(exception).__name__}: {str(exception)}\n"
            trace_str += "".join(
                traceback.format_exception(type(exception), exception, exception.__traceback__)
            )

        formatted = BackendObservability._format_message(message, conversation_id, **kwargs)
        if os.environ.get("FINA_AGENT_CLI_MODE") == "1":
            BackendObservability._log_to_stderr("FATAL", f"🚨 CRITICAL FATAL: {formatted}{trace_str}")
        else:
            logger.write({"severity": "CRITICAL", "message": f"🚨 CRITICAL FATAL: {formatted}{trace_str}"})



@contextmanager
def trace_performance(
    trace_name: str, conversation_id: Optional[str] = None, budget: float = DEFAULT_MUTATION_BUDGET
) -> Generator[None, None, None]:
    """
    A contextual performance timer. Tracks elapsed operation duration, logs completion,
    and automatically raises warnings if execution exceeds pre-allocated budget thresholds.
    """
    start_time = time.perf_counter()
    BackendObservability.trace(f"⏱️ Starting performance trace: '{trace_name}'", conversation_id)
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start_time
        if elapsed > budget:
            BackendObservability.warning(
                f"⏱️ SLA VIOLATION: Trace '{trace_name}' took {elapsed:.3f}s, exceeding budget of {budget:.1f}s",
                conversation_id,
                latency_seconds=f"{elapsed:.3f}",
                budget_seconds=f"{budget:.1f}",
            )
        else:
            BackendObservability.info(
                f"⏱️ Performance Trace '{trace_name}' completed in {elapsed:.3f}s",
                conversation_id,
                latency_seconds=f"{elapsed:.3f}",
            )


def performance_decorator(
    trace_name: str, budget: float = DEFAULT_MUTATION_BUDGET
) -> Callable[..., Any]:
    """
    Function decorator for tracing method latency performance.
    Automatically extracts 'conversation_id' from named arguments if available.
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            conversation_id = kwargs.get("conversation_id")
            with trace_performance(trace_name, conversation_id, budget):
                return await func(*args, **kwargs)

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            conversation_id = kwargs.get("conversation_id")
            with trace_performance(trace_name, conversation_id, budget):
                return func(*args, **kwargs)

        import asyncio

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

    return decorator


def audit_token_budget(
    conversation_id: str,
    prompt_tokens: int,
    candidate_tokens: int,
    prompt_budget: int = DEFAULT_PROMPT_TOKEN_BUDGET,
    candidate_budget: int = DEFAULT_CANDIDATE_TOKEN_BUDGET,
) -> None:
    """
    Inspects agent token utilization. Audits prompt and candidate sizes,
    issuing warning alarms if usage exceeds 80% of defined cost caps.
    """
    total = prompt_tokens + candidate_tokens

    prompt_pct = (prompt_tokens / prompt_budget * 100) if prompt_budget > 0 else 0.0
    candidate_pct = (candidate_tokens / candidate_budget * 100) if candidate_budget > 0 else 0.0

    BackendObservability.info(
        f"Token usage audit: Prompt={prompt_tokens} ({prompt_pct:.1f}%), "
        f"Candidate={candidate_tokens} ({candidate_pct:.1f}%), Total={total}",
        conversation_id,
    )

    if prompt_tokens > (prompt_budget * 0.8):
        BackendObservability.warning(
            f"⚠️ HIGH COST WARN: Prompt token usage ({prompt_tokens}) is at {prompt_pct:.1f}% of budget ({prompt_budget})",
            conversation_id,
            tokens=prompt_tokens,
            limit=prompt_budget,
        )

    if candidate_tokens > (candidate_budget * 0.8):
        BackendObservability.warning(
            f"⚠️ HIGH COST WARN: Candidate token usage ({candidate_tokens}) is at {candidate_pct:.1f}% of budget ({candidate_budget})",
            conversation_id,
            tokens=candidate_tokens,
            limit=candidate_budget,
        )
