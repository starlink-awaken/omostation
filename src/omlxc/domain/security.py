"""Pure canonical credential and Keychain boundary rules."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import cast

_KEYCHAIN_IDENTIFIER = r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}"
_KEYCHAIN_REFERENCE = re.compile(rf"^keychain://{_KEYCHAIN_IDENTIFIER}/{_KEYCHAIN_IDENTIFIER}$")
_URL_AUTH = re.compile(r"(?i)[a-z][a-z0-9+.-]*://[^/@\s]+@")
_CREDENTIAL_WORDS = frozenset(
    {
        "authorization",
        "credential",
        "key",
        "passwd",
        "password",
        "secret",
        "token",
    }
)
_CREDENTIAL_COMPOUNDS = frozenset(
    {
        "accesstoken",
        "apikey",
        "apitoken",
        "authtoken",
        "bearertoken",
        "clientsecret",
        "privatekey",
        "refreshtoken",
    }
)
_PLURAL_CREDENTIAL_WORDS = {
    "credentials": "credential",
    "keys": "key",
    "passwords": "password",
    "secrets": "secret",
    "tokens": "token",
}
_CREDENTIAL_SUFFIXES = ("ref", "value")


class CredentialPolicyError(Exception):
    """Safe credential-boundary failure that Pydantic must not wrap with raw input."""


def canonical_key_words(key: str) -> tuple[str, ...]:
    separated_acronyms = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", key)
    separated_words = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", separated_acronyms)
    return tuple(
        part for part in re.sub(r"[^A-Za-z0-9]+", "_", separated_words).lower().split("_") if part
    )


def is_credential_key(key: str) -> bool:
    words = canonical_key_words(key)
    normalized_words = tuple(_PLURAL_CREDENTIAL_WORDS.get(word, word) for word in words)
    joined = "".join(normalized_words)
    if len(normalized_words) == 1 and joined in _CREDENTIAL_WORDS:
        return True
    if joined in _CREDENTIAL_COMPOUNDS:
        return True
    if joined.endswith("s") and joined[:-1] in _CREDENTIAL_COMPOUNDS:
        return True
    return any(
        joined.endswith(suffix)
        and joined[: -len(suffix)] in (_CREDENTIAL_WORDS | _CREDENTIAL_COMPOUNDS)
        for suffix in _CREDENTIAL_SUFFIXES
    )


def is_keychain_reference(value: str) -> bool:
    return _KEYCHAIN_REFERENCE.fullmatch(value) is not None


def has_embedded_url_auth(value: str) -> bool:
    return _URL_AUTH.search(value) is not None


def validate_keychain_only(value: object, *, key: str | None = None) -> None:
    """Reject recursively nested plaintext authentication material."""
    if (
        key is not None
        and is_credential_key(key)
        and not (isinstance(value, str) and is_keychain_reference(value))
    ):
        raise CredentialPolicyError(
            "plaintext authentication material must use a valid Keychain reference"
        )
    if isinstance(value, str) and has_embedded_url_auth(value):
        raise CredentialPolicyError(
            "address authentication material must use a valid Keychain reference"
        )
    if isinstance(value, Mapping):
        mapping = cast(Mapping[object, object], value)
        for child_key, child in mapping.items():
            validate_keychain_only(child, key=str(child_key))
    elif isinstance(value, (list, tuple)):
        sequence = cast(list[object] | tuple[object, ...], value)
        for child in sequence:
            validate_keychain_only(child)
