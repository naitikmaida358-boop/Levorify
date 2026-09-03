from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_active_user
from app.core.database import get_db
from app.core.security import encrypt_api_key, mask_api_key
from app.models.api_key import UserApiKey
from app.models.user import User
from app.schemas.api_key import (
    ApiKeyCreate,
    ApiKeyResponse,
    ApiKeyVerifyRequest,
    ApiKeyVerifyResponse,
)
from app.services.gemini_service import gemini_service

router = APIRouter()


@router.post("", response_model=ApiKeyResponse, status_code=status.HTTP_201_CREATED)
async def store_or_update_byok_key(
    key_in: ApiKeyCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Link or rotate a user-owned AI API key (BYOK).
    Symmetrically encrypts the raw key with Fernet before database persistence.
    """
    clean_provider = key_in.provider.lower().strip()
    raw_key = key_in.api_key.strip()

    # Verify key against Google Gemini if provider is gemini
    if clean_provider == "gemini":
        verification = await gemini_service.verify_key(raw_key)
        if not verification["valid"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Validation failed for Google Gemini API key: {verification['message']}"
            )

    encrypted_key = encrypt_api_key(raw_key)
    hint = mask_api_key(raw_key)

    # Upsert: check if key for this provider already exists for this user
    stmt = select(UserApiKey).where(
        UserApiKey.user_id == current_user.id,
        UserApiKey.provider == clean_provider
    )
    res = await db.execute(stmt)
    existing_key = res.scalar_one_or_none()

    if existing_key:
        existing_key.encrypted_key = encrypted_key
        existing_key.key_hint = hint
        existing_key.is_active = True
        key_record = existing_key
    else:
        key_record = UserApiKey(
            user_id=current_user.id,
            provider=clean_provider,
            encrypted_key=encrypted_key,
            key_hint=hint,
            is_active=True
        )
        db.add(key_record)

    await db.commit()
    await db.refresh(key_record)
    return key_record


@router.get("", response_model=List[ApiKeyResponse])
async def list_linked_keys(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    List all BYOK AI keys linked to this merchant account.
    Returns masked key hints (raw keys are never returned).
    """
    stmt = select(UserApiKey).where(UserApiKey.user_id == current_user.id)
    res = await db.execute(stmt)
    return res.scalars().all()


@router.delete("/{provider}", status_code=status.HTTP_200_OK)
async def revoke_key(
    provider: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Revoke/remove a stored BYOK key for a given provider.
    """
    clean_provider = provider.lower().strip()
    stmt = delete(UserApiKey).where(
        UserApiKey.user_id == current_user.id,
        UserApiKey.provider == clean_provider
    )
    result = await db.execute(stmt)
    await db.commit()

    if result.rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No key found for provider '{clean_provider}'."
        )

    return {"status": "success", "message": f"Revoked key for provider '{clean_provider}'."}


@router.post("/verify", response_model=ApiKeyVerifyResponse)
async def verify_key(
    payload: ApiKeyVerifyRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Test connectivity of a key.
    If raw_key is provided, tests that key. Otherwise tests the currently saved key.
    """
    target_key = payload.raw_key
    clean_provider = payload.provider.lower().strip()

    if not target_key:
        stmt = select(UserApiKey).where(
            UserApiKey.user_id == current_user.id,
            UserApiKey.provider == clean_provider,
            UserApiKey.is_active.is_(True)
        )
        res = await db.execute(stmt)
        record = res.scalar_one_or_none()
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No active key registered for provider '{clean_provider}' to verify."
            )
        from app.core.security import decrypt_api_key
        target_key = decrypt_api_key(record.encrypted_key)

    if clean_provider == "gemini":
        result = await gemini_service.verify_key(target_key)
        return ApiKeyVerifyResponse(
            valid=result["valid"],
            provider="gemini",
            message=result["message"]
        )

    return ApiKeyVerifyResponse(
        valid=False,
        provider=clean_provider,
        message=f"Live verification probe not implemented for provider '{clean_provider}'."
    )


@router.post("/configure", status_code=status.HTTP_200_OK)
async def configure_key(
    key_in: ApiKeyCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Dashboard convenience endpoint to link and symmetrically encrypt BYOK AI key.
    """
    record = await store_or_update_byok_key(key_in=key_in, current_user=current_user, db=db)
    return {
        "status": "success",
        "provider": record.provider,
        "masked_key": record.key_hint,
        "message": f"Successfully encrypted and vaulted {record.provider} key."
    }


@router.get("/status")
async def get_key_status(
    provider: str = "gemini",
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Dashboard telemetry probe checking whether operator has an active vaulted BYOK key.
    """
    stmt = select(UserApiKey).where(
        UserApiKey.user_id == current_user.id,
        UserApiKey.provider == provider.lower().strip(),
        UserApiKey.is_active.is_(True)
    )
    res = await db.execute(stmt)
    key_record = res.scalar_one_or_none()
    if key_record:
        return {
            "has_key": True,
            "provider": key_record.provider,
            "masked_key": key_record.key_hint
        }
    return {
        "has_key": False,
        "provider": provider,
        "masked_key": None
    }

