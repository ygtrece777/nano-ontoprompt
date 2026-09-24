"""Encrypt persisted credentials with a stable operator-provided Fernet key."""
from cryptography.fernet import Fernet

from app.config import settings


def _get_fernet() -> Fernet:
    if not settings.encryption_key:
        raise RuntimeError("ENCRYPTION_KEY must be configured before storing credentials")
    return Fernet(settings.encryption_key.encode())


def encrypt(plaintext: str) -> str:
    if not plaintext:
        return ""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    if not ciphertext:
        return ""
    return _get_fernet().decrypt(ciphertext.encode()).decode()
