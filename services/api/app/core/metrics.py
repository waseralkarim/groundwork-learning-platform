"""Domain metrics.

RED metrics for HTTP come free from the FastAPI instrumentation. These are the
ones that answer product questions instead of infrastructure ones, and the most
valuable of them is `topic_completion_total`: a topic with many starts and few
completions is a content bug, and this is how it becomes visible rather than
being discovered a year later from a support conversation.

Instruments are created lazily and are no-ops when telemetry is off, so calling
these from request paths costs nothing in a default `docker compose up`.
"""

from __future__ import annotations

from functools import cache

from opentelemetry import metrics


@cache
def _meter() -> metrics.Meter:
    return metrics.get_meter("groundwork.api")


@cache
def _quiz_attempts() -> metrics.Counter:
    return _meter().create_counter(
        "quiz_attempts_total",
        description="Quiz attempts graded, labelled by outcome",
    )


@cache
def _topic_completions() -> metrics.Counter:
    return _meter().create_counter(
        "topic_completion_total",
        description="Topic status transitions — starts versus completions",
    )


@cache
def _ingest_duration() -> metrics.Histogram:
    return _meter().create_histogram(
        "content_ingest_duration_seconds",
        unit="s",
        description="How long a full content ingest takes",
    )


@cache
def _ingest_errors() -> metrics.Counter:
    return _meter().create_counter(
        "content_ingest_errors_total",
        description="Ingest runs that failed",
    )


@cache
def _search_queries() -> metrics.Counter:
    return _meter().create_counter(
        "search_queries_total",
        description="Searches run, labelled by whether anything matched",
    )


def record_quiz_attempt(passed: bool, topic: str) -> None:
    _quiz_attempts().add(1, {"result": "passed" if passed else "failed", "topic": topic})


def record_topic_status(status: str, topic: str) -> None:
    _topic_completions().add(1, {"status": status, "topic": topic})


def record_ingest(duration_seconds: float, *, ok: bool) -> None:
    _ingest_duration().record(duration_seconds)
    if not ok:
        _ingest_errors().add(1)


def record_search(*, found: bool) -> None:
    # A search that returns nothing is the interesting one: a run of them is
    # either a content gap or vocabulary the curriculum does not use.
    _search_queries().add(1, {"result": "hit" if found else "empty"})


__all__ = [
    "record_ingest",
    "record_quiz_attempt",
    "record_search",
    "record_topic_status",
]
