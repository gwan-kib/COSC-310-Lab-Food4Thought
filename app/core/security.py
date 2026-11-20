"""Hash Food4Thought passwords and create sign-in tokens as decided in AUTH_DESIGN.md.
Passwords are stored only as Argon2id hashes (pwdlib); tokens are random and stored
only as SHA-256 digests, so neither data file holds a usable credential.
"""

import hashlib
import secrets
from functools import lru_cache

from pwdlib import PasswordHash

_hasher = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


class UnusablePasswordHashError(Exception):
    """A stored hash is damaged or in an unknown format (a storage problem, not a wrong password)."""


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password, password_hash)
    except Exception as exc:  # pwdlib raises several types for malformed hashes
        raise UnusablePasswordHashError(str(exc)) from exc


@lru_cache(maxsize=1)
def _dummy_hash() -> str:
    return _hasher.hash("food4thought-dummy-password")


def verify_against_dummy(password: str) -> None:
    """Spend the same hashing work for an unknown email, so timing does not reveal it."""
    _hasher.verify(password, _dummy_hash())


def new_token() -> str:
    return secrets.token_urlsafe(32)


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
