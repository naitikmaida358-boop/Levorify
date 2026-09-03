from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_active_user, get_user_gemini_key
from app.core.database import get_db
from app.models.tool_log import ToolExecutionLog
from app.models.user import User
from app.schemas.tool import (
    AdCopyRequest,
    ProductDescriptionRequest,
    ToolExecutionResponse,
    ToolGenericExecuteRequest,
)
from app.services.gemini_service import gemini_service

router = APIRouter()


@router.post("/product-description", response_model=ToolExecutionResponse)
async def generate_product_description(
    payload: ProductDescriptionRequest,
    current_user: User = Depends(get_current_active_user),
    gemini_key: str = Depends(get_user_gemini_key),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Generate high-velocity D2C product descriptions, feature-benefit matrices, and SEO tags.
    Dynamically powered by caller's own Google Gemini key.
    """
    system_instruction = (
        "You are the Lead Conversion Copywriter and E-commerce Merchandiser for Levorify "
        "(the elite 20-in-1 Sovereign D2C Platform). Write punchy, sensorial, high-converting, "
        "and brand-aligned copy tailored for modern direct-to-consumer shoppers."
    )

    prompt = f"""
Target Product: {payload.product_name}
Category: {payload.category}
Key Features: {', '.join(payload.features)}
Target Audience: {payload.target_audience}
Tone: {payload.tone}
Brand Voice: {payload.brand_voice}

Produce a structured D2C merchandising breakdown with:
1. Hero Hook Headline (Sub-15 words, bold, irresistible)
2. Sensorial Product Story (2 crisp paragraphs focusing on outcome and elevation)
3. Feature-to-Benefit Bullet Matrix (3-4 bullets: Feature -> Immediate emotional/functional payoff)
4. SEO Title Tag & Meta Description (Optimized for search click-through rate)
5. Suggested Urgent Call-to-Action (CTA) button copy
"""

    response = await gemini_service.generate_d2c_content(
        api_key=gemini_key,
        system_instruction=system_instruction,
        prompt=prompt,
        temperature=0.75
    )

    # Telemetry logging
    log_entry = ToolExecutionLog(
        user_id=current_user.id,
        tool_name="product-description",
        provider="gemini",
        model_used=response["model"],
        status="success",
        latency_ms=response["latency_ms"],
        tokens_used=response["total_tokens"],
    )
    db.add(log_entry)
    await db.commit()

    return ToolExecutionResponse(
        tool_name="product-description",
        provider="gemini",
        model=response["model"],
        latency_ms=response["latency_ms"],
        status="success",
        result=response["result"]
    )


@router.post("/ad-copy", response_model=ToolExecutionResponse)
async def generate_ad_copy(
    payload: AdCopyRequest,
    current_user: User = Depends(get_current_active_user),
    gemini_key: str = Depends(get_user_gemini_key),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Generate omni-channel high-ROAS ad angles (Meta, Google, TikTok) using user's BYOK Gemini key.
    """
    system_instruction = (
        "You are an elite Performance Marketing Director specialized in 8-figure D2C brands. "
        "Create high-CTR paid social & search ad variations designed to drive immediate conversions."
    )

    prompt = f"""
Product: {payload.product_name}
Objective: {payload.campaign_objective}
Target Persona: {payload.target_persona}
Discount / Offer: {payload.discount_or_offer}
Requested Platforms: {', '.join(payload.platforms)}

For each platform:
- Meta (Facebook/Instagram): 2 Scroll-Stopping Hooks, Primary Ad Body, Headline, and CTA.
- Google Search: 3 High-Intent Headlines (30 chars max each) and 2 Descriptions (90 chars max).
- TikTok: 1 Organic/UGC-style 15-second hook & creator script concept.
"""

    response = await gemini_service.generate_d2c_content(
        api_key=gemini_key,
        system_instruction=system_instruction,
        prompt=prompt,
        temperature=0.8
    )

    # Telemetry logging
    log_entry = ToolExecutionLog(
        user_id=current_user.id,
        tool_name="ad-copy",
        provider="gemini",
        model_used=response["model"],
        status="success",
        latency_ms=response["latency_ms"],
        tokens_used=response["total_tokens"],
    )
    db.add(log_entry)
    await db.commit()

    return ToolExecutionResponse(
        tool_name="ad-copy",
        provider="gemini",
        model=response["model"],
        latency_ms=response["latency_ms"],
        status="success",
        result=response["result"]
    )


@router.get("/history")
async def get_tool_execution_history(
    current_user: User = Depends(get_current_active_user),
    limit: int = 20,
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    View user's historical AI tool runs, latencies, and token counts.
    """
    stmt = (
        select(ToolExecutionLog)
        .where(ToolExecutionLog.user_id == current_user.id)
        .order_by(ToolExecutionLog.created_at.desc())
        .limit(limit)
    )
    res = await db.execute(stmt)
    logs = res.scalars().all()
    return [
        {
            "id": log.id,
            "tool_name": log.tool_name,
            "provider": log.provider,
            "model_used": log.model_used,
            "status": log.status,
            "latency_ms": log.latency_ms,
            "tokens_used": log.tokens_used,
            "created_at": log.created_at
        }
        for log in logs
    ]


@router.post("/execute", response_model=ToolExecutionResponse)
async def execute_tool(
    payload: ToolGenericExecuteRequest,
    current_user: User = Depends(get_current_active_user),
    gemini_key: str = Depends(get_user_gemini_key),
    db: AsyncSession = Depends(get_db)
) -> Any:
    """
    Autonomous sovereign engine dispatcher for Levorify D2C merchants.
    Executes RTO Risk Shield, Dynamic AOV Bundling, Alpha Trend Scout, or Custom D2C modules.
    """
    tool_name = payload.tool_name.lower().strip()

    if "rto" in tool_name or tool_name == "rto_shield":
        system_instruction = (
            "You are the Chief Risk Officer and Fraud Mitigation AI for Levorify Sovereign D2C Platform. "
            "Analyze the provided COD (Cash on Delivery) customer/order telemetry or parameters. "
            "Output a structured assessment with:\n"
            "1. Risk Category (LOW, MEDIUM, HIGH)\n"
            "2. Estimated RTO Probability Score (%)\n"
            "3. Key Risk Factors & Geo-telemetry flags\n"
            "4. Immediate Sovereign Action Protocol (e.g. OTP confirmation, WhatsApp automated prepayment incentive, or manual verification)"
        )
    elif "bundle" in tool_name or tool_name == "bundling":
        system_instruction = (
            "You are the Chief Merchandising Officer and Algorithmic Pricing Strategist for Levorify. "
            "Design high-margin, high-AOV (Average Order Value) dynamic bundling architectures. "
            "Output a structured bundle strategy with:\n"
            "1. Bundle Nomenclature & Tiering (e.g., Starter, Sovereign Duo, Enterprise Suite)\n"
            "2. Anchor Product + Add-On Synergy Rationale\n"
            "3. Dynamic Pricing Model & Margin Capture % Lift\n"
            "4. Checkout Urgency Trigger & Copy Hook"
        )
    elif "research" in tool_name or "trend" in tool_name:
        system_instruction = (
            "You are the Alpha Product Trend Scout and Global E-commerce Arbitrage Intelligence AI for Levorify. "
            "Evaluate the given product niche, SKU, or trend telemetry. "
            "Output a structured intelligence brief with:\n"
            "1. Market Heat & Velocity Index (1-100)\n"
            "2. Viral Catalyst & Consumer Pain Point Mapping\n"
            "3. Margin Spread Potential (COGS vs Retail Pricing)\n"
            "4. 72-Hour Rapid Validation Protocol"
        )
    elif "product" in tool_name or "description" in tool_name:
        system_instruction = (
            "You are the Lead Conversion Copywriter and E-commerce Merchandiser for Levorify Sovereign D2C Platform. "
            "Produce structured, high-converting product merchandising copy with headline, sensorial story, feature-benefit bullets, and CTA."
        )
    elif "ad" in tool_name:
        system_instruction = (
            "You are an elite Performance Marketing Director for Levorify 8-figure D2C brands. "
            "Create high-CTR paid social & search ad variations designed to maximize ROAS."
        )
    else:
        system_instruction = (
            "You are Levorify's Sovereign Autonomous Commerce Intelligence Engine. "
            "Provide rigorous, mathematically sound, actionable D2C merchant execution recommendations."
        )

    response = await gemini_service.generate_d2c_content(
        api_key=gemini_key,
        system_instruction=system_instruction,
        prompt=payload.prompt,
        temperature=0.75
    )

    # Telemetry logging
    log_entry = ToolExecutionLog(
        user_id=current_user.id,
        tool_name=tool_name,
        provider="gemini",
        model_used=response["model"],
        status="success",
        latency_ms=response["latency_ms"],
        tokens_used=response["total_tokens"],
    )
    db.add(log_entry)
    await db.commit()

    return ToolExecutionResponse(
        tool_name=tool_name,
        provider="gemini",
        model=response["model"],
        latency_ms=response["latency_ms"],
        status="success",
        result=response["result"]
    )

