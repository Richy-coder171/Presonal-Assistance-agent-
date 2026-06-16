from __future__ import annotations

import base64
import hashlib
import os
from typing import Any

from cryptography.fernet import Fernet, InvalidToken


ENCRYPTED_PREFIX = "enc:v1:"
TOKEN_FIELDS = {"access_token", "refresh_token", "id_token"}
_DEV_KEY_MATERIAL = "personal-assistant-agent-local-development-token-key"


class TokenCipher:
    def __init__(self, key: str | None = None) -> None:
        material = key or os.getenv("TOKEN_ENCRYPTION_KEY", "") or _DEV_KEY_MATERIAL
        self._fernet = Fernet(_normalize_key(material))

    def encrypt(self, value: str) -> str:
        if value.startswith(ENCRYPTED_PREFIX):
            return value
        token = self._fernet.encrypt(value.encode("utf-8")).decode("utf-8")
        return f"{ENCRYPTED_PREFIX}{token}"

    def decrypt(self, value: str) -> str:
        if not value.startswith(ENCRYPTED_PREFIX):
            return value
        encrypted = value[len(ENCRYPTED_PREFIX):].encode("utf-8")
        try:
            return self._fernet.decrypt(encrypted).decode("utf-8")
        except InvalidToken:
            return ""


def encrypt_token_payload(payload: dict[str, Any], key: str | None = None) -> dict[str, Any]:
    cipher = TokenCipher(key)
    encrypted = dict(payload)
    for field in TOKEN_FIELDS:
        value = encrypted.get(field)
        if value:
            encrypted[field] = cipher.encrypt(str(value))
    return encrypted


def decrypt_token_payload(payload: dict[str, Any], key: str | None = None) -> dict[str, Any]:
    cipher = TokenCipher(key)
    decrypted = dict(payload)
    for field in TOKEN_FIELDS:
        value = decrypted.get(field)
        if isinstance(value, str):
            decrypted[field] = cipher.decrypt(value)
    return decrypted


def _normalize_key(material: str) -> bytes:
    encoded = material.encode("utf-8")
    try:
        Fernet(encoded)
        return encoded
    except (ValueError, TypeError):
        digest = hashlib.sha256(encoded).digest()
        return base64.urlsafe_b64encode(digest)
