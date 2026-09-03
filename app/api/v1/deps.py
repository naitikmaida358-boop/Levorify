from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import decode_access_token, decrypt_api_key
from app.models.api_key import UserApiKey
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login"
)


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Authenticate request via JWT Bearer token and fetch User entity.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials or token expired.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = decode_access_token(token)
        user_id: str = payload.get("sub")
        if not user_id:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception

    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise credentials_exception
    
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Verify user account is active.
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account."
        )
    return current_user


async def get_user_gemini_key(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> str:
    """
    BYOK Dependency: Fetches and decrypts user's stored Google Gemini API key.
    If no active key is linked, halts execution with an actionable 400 Bad Request.
    """
    stmt = select(UserApiKey).where(
        UserApiKey.user_id == current_user.id,
        UserApiKey.provider == "gemini",
        UserApiKey.is_active.is_(True)
    )
    result = await db.execute(stmt)
    api_key_record = result.scalar_one_or_none()

    if not api_key_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "BYOK Key Required: You have not configured a Google Gemini API key yet. "
                "Please link your free Gemini key at POST /api/v1/keys to execute this D2C AI tool."
            )
        )

    try:
        decrypted_key = decrypt_api_key(api_key_record.encrypted_key)
        return decrypted_key
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Cryptographic failure resolving user BYOK key: {str(exc)}"
        )
