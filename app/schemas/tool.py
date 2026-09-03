from datetime import datetime, timezone
from typing import Any, List, Optional
from pydantic import BaseModel, Field


class ProductDescriptionRequest(BaseModel):
    product_name: str = Field(..., example="Aura Lumina Hydro-Serum")
    category: str = Field(..., example="Luxury Skincare & Cosmetics")
    features: List[str] = Field(
        ...,
        example=[
            "Triple-molecule hyaluronic acid",
            "Sustainably sourced botanical squalane",
            "72-hour moisture barrier lock",
            "Dermatologist approved for sensitive skin"
        ]
    )
    target_audience: Optional[str] = Field(
        default="Discerning millennial & Gen-Z professionals seeking clinical-grade minimalism",
        example="High-income skincare enthusiasts aged 24-40"
    )
    tone: Optional[str] = Field(
        default="High-Converting Sovereign Luxury",
        example="Editorial, authoritative, sensorial, conversion-focused"
    )
    brand_voice: Optional[str] = Field(
        default="Levorify Sovereign Clean Aesthetic",
        example="Minimalist, modern, scientifically credible"
    )


class AdCopyRequest(BaseModel):
    product_name: str = Field(..., example="Aura Lumina Hydro-Serum")
    campaign_objective: str = Field(default="Conversions", example="Direct ROAS Scaling / Flash Sale")
    platforms: List[str] = Field(default=["Meta", "Google", "TikTok"])
    discount_or_offer: Optional[str] = Field(default="20% off launch bundle with code SOVEREIGN20")
    target_persona: Optional[str] = Field(default="D2C luxury consumers fatigued by synthetic formulations")


class ToolGenericExecuteRequest(BaseModel):
    tool_name: str = Field(..., example="rto_shield", description="Identifier of the sovereign tool module to run")
    prompt: str = Field(..., example="Order value ₹3,499 to COD pin 110001 with 2 previous returns. Assess RTO risk.", description="Telemetry parameters or merchant prompt")
    parameters: Optional[dict] = Field(default=None, description="Optional extra execution parameters")


class ToolExecutionResponse(BaseModel):
    tool_name: str
    provider: str
    model: str
    latency_ms: float
    status: str = "success"
    result: Any
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

