from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from cryptography.fernet import Fernet, InvalidToken


def encrypt_token(token: str, key: str, destination: Path) -> None:
    if not token.strip():
        raise ValueError("Instagram token cannot be empty")
    destination.parent.mkdir(parents=True, exist_ok=True)
    cipher = Fernet(key.encode("utf-8"))
    destination.write_bytes(cipher.encrypt(token.strip().encode("utf-8")))


def decrypt_token(key: str, source: Path) -> str:
    if not key:
        raise RuntimeError("TOKEN_ENCRYPTION_KEY is missing")
    if not source.exists():
        raise RuntimeError("Encrypted Instagram token file is missing; run tools/bootstrap_token.py")
    try:
        return Fernet(key.encode("utf-8")).decrypt(source.read_bytes()).decode("utf-8")
    except (InvalidToken, ValueError) as exc:
        raise RuntimeError("Encrypted token could not be opened; check TOKEN_ENCRYPTION_KEY") from exc


def load_access_token(settings) -> str:
    if settings.direct_access_token:
        return settings.direct_access_token.strip()
    return decrypt_token(settings.token_encryption_key, settings.state_dir / "instagram_token.enc")


def _read_meta(path: Path) -> dict:
    if not path.exists():
        return {"last_refreshed_at": None}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_meta(path: Path, refreshed_at: datetime, expires_in: int | None = None) -> None:
    data = {"last_refreshed_at": refreshed_at.isoformat(), "expires_in_seconds": expires_in}
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def token_refresh_due(meta_path: Path, after_days: int = 35) -> bool:
    value = _read_meta(meta_path).get("last_refreshed_at")
    if not value:
        return False
    refreshed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return datetime.now(timezone.utc) - refreshed >= timedelta(days=after_days)


def refresh_encrypted_token(settings, force: bool = False) -> bool:
    """Refresh a long-lived Instagram Login token and persist only ciphertext."""
    token_path = settings.state_dir / "instagram_token.enc"
    meta_path = settings.state_dir / "token_meta.json"
    if settings.direct_access_token:
        return False
    if not force and not token_refresh_due(meta_path):
        return False
    current = decrypt_token(settings.token_encryption_key, token_path)
    response = requests.get(
        "https://graph.instagram.com/refresh_access_token",
        params={"grant_type": "ig_refresh_token", "access_token": current},
        timeout=45,
    )
    if not response.ok:
        message = response.json().get("error", {}).get("message", response.text[:300])
        raise RuntimeError(f"Instagram token refresh failed: {message}")
    payload = response.json()
    new_token = payload["access_token"]
    encrypt_token(new_token, settings.token_encryption_key, token_path)
    _write_meta(meta_path, datetime.now(timezone.utc), payload.get("expires_in"))
    return True

