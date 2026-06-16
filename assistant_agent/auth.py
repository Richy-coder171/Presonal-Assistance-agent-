from __future__ import annotations

import hashlib
import hmac
import os
from dataclasses import dataclass

from .config import Settings


SESSION_USER_KEY = "user_email"


@dataclass(frozen=True)
class AuthResult:
    ok: bool
    message: str = ""


def verify_login(settings: Settings, email: str, password: str) -> AuthResult:
    admin_email = (settings.admin_email or "").strip().lower()
    if not admin_email:
        return AuthResult(False, "ADMIN_EMAIL is not configured.")
    if email.strip().lower() != admin_email:
        return AuthResult(False, "Invalid email or password.")
    if settings.admin_password_hash:
        if _verify_password_hash(password, settings.admin_password_hash):
            return AuthResult(True)
        return AuthResult(False, "Invalid email or password.")
    if settings.admin_password:
        if hmac.compare_digest(password, settings.admin_password):
            return AuthResult(True)
        return AuthResult(False, "Invalid email or password.")
    return AuthResult(False, "ADMIN_PASSWORD_HASH or ADMIN_PASSWORD is required.")


def hash_password(password: str, salt: str | None = None) -> str:
    salt_value = salt or os.urandom(16).hex()
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt_value.encode("utf-8"),
        260_000,
    ).hex()
    return f"pbkdf2_sha256${salt_value}${digest}"


def session_secret(settings: Settings) -> str:
    return (
        settings.session_secret
        or settings.token_encryption_key
        or "personal-assistant-agent-local-session-secret"
    )


def _verify_password_hash(password: str, stored: str) -> bool:
    try:
        algorithm, salt, digest = stored.split("$", 2)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    expected = hash_password(password, salt).split("$", 2)[2]
    return hmac.compare_digest(expected, digest)
