"""Test configuration.

Settings are environment-driven and fail closed, so the test run has to supply
them explicitly. That is the correct trade: it means a missing production secret
can never be silently papered over by a default.
"""

from __future__ import annotations

import os

_TEST_ENV = {
    "GROUNDWORK_ENV": "test",
    "LOG_LEVEL": "WARNING",
    "SECRET_KEY": "test-secret-key-not-used-for-anything-real",
    "POSTGRES_USER": "groundwork",
    "POSTGRES_PASSWORD": "groundwork",
    "POSTGRES_DB": "groundwork_test",
    "POSTGRES_HOST": "localhost",
    "POSTGRES_PORT": "5432",
    "VALKEY_HOST": "localhost",
    "VALKEY_PORT": "6379",
}

for key, value in _TEST_ENV.items():
    os.environ.setdefault(key, value)
