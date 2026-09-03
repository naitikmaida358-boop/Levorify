from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class ApiKeyCreate(BaseModel):
    """
    Client submission payload to link their own Google Gemini or AI API key.
    """
    provider: str = Field(default="gemini", description="AI Provider identifier (e.g. 'gemini', 'openai')")
    api_key: str = Field(..., min_length=10, description="Raw API key from Google AI Studio / provider")


class ApiKeyResponse(BaseModel):
    """
    Safe public response schema.
    CRITICAL: Raw key is never exposed. Only masked key_hint is returned.
    """
    id: str
    provider: str
    key_hint: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ApiKeyVerifyRequest(BaseModel):
    provider: str = Field(default="gemini")
    # Optional raw key to test before saving, otherwise tests currently saved active key
    raw_key: Optional[str] = None


class ApiKeyVerifyResponse(BaseModel):
    valid: bool
    provider: str
    message: str
