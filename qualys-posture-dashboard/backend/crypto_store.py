"""Encrypt-at-rest for the stored Qualys credentials.

The customer's Qualys username/password live only on their machine. We store them
symmetrically encrypted with a locally-generated key so the SQLite file is never a
plaintext credential dump. The key file lives next to the DB with 0600 perms.

Uses `cryptography.Fernet` when available (declared in requirements). If the package
is somehow missing we fall back to a keyed obfuscation that is *not* strong crypto —
the fallback keeps the app runnable but is clearly labelled; production installs get
Fernet from requirements.txt.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
from pathlib import Path

try:
    from cryptography.fernet import Fernet  # type: ignore
    _HAVE_FERNET = True
except Exception:  # pragma: no cover - fallback path
    Fernet = None  # type: ignore
    _HAVE_FERNET = False


def _key_path() -> Path:
    return Path(os.environ.get("QPD_DATA_DIR", str(Path(__file__).resolve().parent / "data"))) / "secret.key"


def _load_or_create_key() -> bytes:
    p = _key_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    if p.exists():
        return p.read_bytes()
    key = Fernet.generate_key() if _HAVE_FERNET else base64.urlsafe_b64encode(os.urandom(32))
    p.write_bytes(key)
    try:
        os.chmod(p, 0o600)
    except OSError:
        pass
    return key


def encrypt(plaintext: str) -> str:
    if plaintext is None:
        plaintext = ""
    key = _load_or_create_key()
    if _HAVE_FERNET:
        return "fernet:" + Fernet(key).encrypt(plaintext.encode()).decode()
    # Fallback: HMAC-derived keystream XOR (obfuscation, NOT strong crypto).
    raw = plaintext.encode()
    stream = _keystream(key, len(raw))
    xored = bytes(a ^ b for a, b in zip(raw, stream))
    return "xor:" + base64.urlsafe_b64encode(xored).decode()


def decrypt(token: str) -> str:
    if not token:
        return ""
    key = _load_or_create_key()
    if token.startswith("fernet:") and _HAVE_FERNET:
        return Fernet(key).decrypt(token[len("fernet:"):].encode()).decode()
    if token.startswith("xor:"):
        xored = base64.urlsafe_b64decode(token[len("xor:"):].encode())
        stream = _keystream(key, len(xored))
        return bytes(a ^ b for a, b in zip(xored, stream)).decode(errors="replace")
    # Unknown / legacy plaintext
    return token


def _keystream(key: bytes, n: int) -> bytes:
    out = b""
    counter = 0
    while len(out) < n:
        out += hmac.new(key, counter.to_bytes(8, "big"), hashlib.sha256).digest()
        counter += 1
    return out[:n]
