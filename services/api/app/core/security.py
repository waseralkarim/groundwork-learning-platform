"""Password hashing and session tokens.

Two rules govern everything in this file:

1. **Never store anything that can be replayed.** Passwords are hashed with
   Argon2id; session tokens are stored as SHA-256 digests. Read access to the
   database must not let anyone log in as anybody.
2. **Never compare secrets with `==`.** Timing differences in string comparison
   are a real oracle. Lookups happen by digest, and verification uses
   constant-time primitives.
"""

from __future__ import annotations

import contextlib
import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

# OWASP's second recommended Argon2id configuration (2024): 19 MiB, 2 passes,
# 1 degree of parallelism. Tuned to be uncomfortable for an attacker with GPUs
# and unnoticeable for a single interactive login.
#
# Raising these later is safe: `needs_rehash` detects the old parameters and the
# hash is upgraded transparently on the user's next successful login.
_hasher = PasswordHasher(
    time_cost=2,
    memory_cost=19456,
    parallelism=1,
    hash_len=32,
    salt_len=16,
)

SESSION_TOKEN_BYTES = 32  # 256 bits


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        return _hasher.verify(stored_hash, password)
    except (VerifyMismatchError, InvalidHashError, ValueError):
        return False


def password_needs_rehash(stored_hash: str) -> bool:
    try:
        return _hasher.check_needs_rehash(stored_hash)
    except (InvalidHashError, ValueError):
        return False


def generate_session_token() -> str:
    """A fresh opaque token. Returned to the client once and never stored."""
    return secrets.token_urlsafe(SESSION_TOKEN_BYTES)


def hash_session_token(token: str) -> str:
    """The digest we actually store and look up by.

    SHA-256 rather than Argon2: the token is 256 bits of CSPRNG output, so it is
    not guessable and needs no key-stretching. Stretching it would only make
    every authenticated request slow.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def tokens_equal(a: str, b: str) -> bool:
    return hmac.compare_digest(a, b)


# A pre-computed hash of a random password. Verifying against it when a user
# does not exist keeps login timing indistinguishable between "no such account"
# and "wrong password" — otherwise the endpoint is an account enumeration oracle.
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(32))


def waste_time_like_a_real_verification() -> None:
    """Deliberate constant-time padding for the unknown-user path."""
    # The verification is expected to fail — burning the time is the point.
    with contextlib.suppress(Exception):
        _hasher.verify(_DUMMY_HASH, "not the password")
