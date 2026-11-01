"""Criptografia autenticada para credenciais (API keys)."""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings


def _fernet() -> Fernet:
    secret = get_settings().secret_key
    if not secret:
        raise RuntimeError("LOKI_SECRET_KEY não configurado")
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_secret(value: str | None) -> bytes | None:
    if not value:
        return None
    return _fernet().encrypt(value.encode("utf-8"))


def decrypt_secret(blob: bytes | None) -> str | None:
    if not blob:
        return None
    try:
        return _fernet().decrypt(bytes(blob)).decode("utf-8")
    except InvalidToken:
        return None


def mask_secret(value: str | None) -> str:
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return value[:3] + "…" + value[-2:]
