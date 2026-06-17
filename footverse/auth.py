"""Geração e validação de API keys — SPEC-008.

Chaves são geradas com `secrets.token_urlsafe(32)` (256 bits de entropia) e
armazenadas apenas como SHA-256 hex. A chave raw é retornada uma única vez ao
usuário no momento do registro; depois disso, apenas o hash existe no banco.
"""

from __future__ import annotations

import hashlib
import secrets


def generate_key() -> tuple[str, str]:
    """Retorna (raw_key, key_hash). Armazene apenas o hash."""
    raw = secrets.token_urlsafe(32)
    h = hashlib.sha256(raw.encode()).hexdigest()
    return raw, h


def hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()
