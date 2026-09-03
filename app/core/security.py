import base64
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import os
from typing import Any, Optional, Union
import jwt
from cryptography.fernet import Fernet, InvalidToken
from app.core.config import settings

# ---------------------------------------------------------------------------
# Password Hashing Layer (Native bcrypt with PBKDF2 fallback)
# ---------------------------------------------------------------------------
try:
    import bcrypt
    _HAS_BCRYPT = True
except ImportError:
    _HAS_BCRYPT = False


def _hash_pbkdf2(password: str, salt: Optional[bytes] = None) -> str:
    """Standard library PBKDF2-HMAC-SHA256 password hash fallback."""
    if not salt:
        salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
    salt_b64 = base64.b64encode(salt).decode("ascii")
    key_b64 = base64.b64encode(key).decode("ascii")
    return f"$pbkdf2$100000${salt_b64}${key_b64}"


def _verify_pbkdf2(password: str, hashed_password: str) -> bool:
    try:
        parts = hashed_password.split("$")
        iterations = int(parts[2])
        salt = base64.b64decode(parts[3].encode("ascii"))
        expected_key = base64.b64decode(parts[4].encode("ascii"))
        computed_key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(computed_key, expected_key)
    except Exception:
        return False


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against its bcrypt or PBKDF2 hash."""
    if hashed_password.startswith("$pbkdf2$"):
        return _verify_pbkdf2(plain_password, hashed_password)

    if _HAS_BCRYPT:
        try:
            return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
        except Exception:
            return False

    return False


def get_password_hash(password: str) -> str:
    """Generate a cryptographic hash of a plaintext password."""
    if _HAS_BCRYPT:
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")
    return _hash_pbkdf2(password)


# ---------------------------------------------------------------------------
# JWT Sovereign Tokens
# ---------------------------------------------------------------------------

def create_access_token(subject: Union[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Generate an encoded JWT access token with standard claims.
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "iat": datetime.now(timezone.utc),
        "iss": "levorify-auth"
    }
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> dict:
    """
    Decode and validate a JWT access token.
    Raises jwt.PyJWTError on failure.
    """
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])


# ---------------------------------------------------------------------------
# BYOK (Bring Your Own Key) Symmetric Cryptographic Vault
# ---------------------------------------------------------------------------

def _get_fernet_cipher() -> Fernet:
    """Initialize Fernet cipher using configured master cluster key."""
    raw_key = settings.BYOK_ENCRYPTION_KEY.encode()
    try:
        return Fernet(raw_key)
    except Exception:
        # Fallback if key is standard 32-char string, encode into urlsafe base64
        padded = base64.urlsafe_b64encode(raw_key[:32].ljust(32, b'0'))
        return Fernet(padded)


def encrypt_api_key(raw_key: str) -> str:
    """
    Symmetrically encrypt user's Gemini/AI API key before persisting into DB.
    """
    cipher = _get_fernet_cipher()
    encrypted_bytes = cipher.encrypt(raw_key.strip().encode("utf-8"))
    return encrypted_bytes.decode("utf-8")


def decrypt_api_key(encrypted_key: str) -> str:
    """
    Decrypt user's stored encrypted API key for dynamic runtime injection.
    """
    cipher = _get_fernet_cipher()
    try:
        decrypted_bytes = cipher.decrypt(encrypted_key.strip().encode("utf-8"))
        return decrypted_bytes.decode("utf-8")
    except InvalidToken:
        raise ValueError("Failed to decrypt BYOK API key: cryptographic token invalid or key mismatch.")


def mask_api_key(raw_key: str) -> str:
    """
    Generate a safe display hint for user UI (e.g. AIza...4x9Q) without exposing secret.
    """
    clean = raw_key.strip()
    if len(clean) <= 8:
        return "****" + clean[-2:] if len(clean) >= 2 else "****"
    return f"{clean[:4]}...{clean[-4:]}"
