from typing import Any, Dict, List, Optional
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

# ==============================================================================
# Complete 20 Sovereign D2C Commerce Protocols Registry
# ==============================================================================
SOVEREIGN_D2C_PROTOCOLS: List[Dict[str, Any]] = [
    {
        "id": "tool_1_trend_scout",
        "number": 1,
        "name": "Tool #1: Autonomous Product Research & Trend Scout",
        "short_name": "Autonomous Product Research & Trend Scout",
        "aliases": ["tool_1_trend_scout", "tool_1", "tool1", "trend_scout", "research", "trend", "product_research", "autonomous product research & trend scout"],
        "system_instruction": (
            "You are the Alpha Product Trend Scout and Global E-commerce Arbitrage Intelligence AI for Levorify Sovereign D2C Platform. "
            "Analyze consumer search velocity, TikTok/Instagram viral momentum, supply friction, and margin spread potential.\n"
            "Output a structured intelligence report with:\n"
            "1. Trend Velocity Score (1-100) & Saturation Index\n"
            "2. Target Demographic & Core Viral Hook\n"
            "3. Landed COGS vs Target Retail Price Arbitrage (estimated margin spread)\n"
            "4. 72-Hour Rapid Validation Protocol & Test Sourcing Strategy"
        ),
        "sample_prompt": "Category: Ergonomic desk accessories & titanium EDC gadgets. Target landed COGS: under $12. Retail potential: $49-$79. Evaluate trend velocity, competitive moat, and rapid validation launch plan."
    },
    {
        "id": "tool_2_price_bundling",
        "number": 2,
        "name": "Tool #2: Dynamic Price Anchoring & Bundling Matrix",
        "short_name": "Dynamic Price Anchoring & Bundling Matrix",
        "aliases": ["tool_2_price_bundling", "tool_2", "tool2", "price_bundling", "bundling", "bundle", "price_anchoring", "dynamic_pricing", "dynamic price anchoring & bundling matrix"],
        "system_instruction": (
            "You are the Chief Merchandising Officer and Algorithmic Pricing Strategist for Levorify Sovereign D2C Platform. "
            "Design high-margin, high-AOV dynamic price anchoring and bundling architectures.\n"
            "Output a structured bundle strategy with:\n"
            "1. Tiered Bundling Matrix (Single Anchor, Duo Sovereign Bundle, Family/Pro Bundle)\n"
            "2. Price Anchoring & Perceived Savings Breakdown\n"
            "3. Contribution Margin & AOV Lift Estimation\n"
            "4. Checkout Urgency & Scarcity Copy Triggers"
        ),
        "sample_prompt": "Primary SKU: Lumina Hydro-Serum (Retail ₹1,499, COGS ₹280). Cross-sells: Ceramide Barrier Mist (Retail ₹799, COGS ₹140), Peptide Night Mask (Retail ₹1,899, COGS ₹320). Architect a 3-tier high-converting bundle matrix."
    },
    {
        "id": "tool_3_ad_copy",
        "number": 3,
        "name": "Tool #3: High-Velocity Ad Copy & Creative Generator",
        "short_name": "High-Velocity Ad Copy & Creative Generator",
        "aliases": ["tool_3_ad_copy", "tool_3", "tool3", "ad_copy", "ad-copy", "ad", "creative_generator", "copy_generator", "high-velocity ad copy & creative generator"],
        "system_instruction": (
            "You are an elite Performance Marketing Creative Director for Levorify 8-figure D2C brands. "
            "Generate hyper-converting, direct-response ad copy tailored for Meta, Google Search, and TikTok.\n"
            "Output structured high-ROAS creative assets with:\n"
            "1. 3 Meta Primary Texts with Pattern-Interrupt Hooks, Headlines & CTAs\n"
            "2. 3 Google Search Responsive Ad Headlines & Descriptions\n"
            "3. 2 TikTok Direct-Response Script Angles\n"
            "4. Creative Angle & Visual Concept Brief"
        ),
        "sample_prompt": "Product: Obsidian Cold Brew Tumbler (Vacuum insulated, titanium finish, 24hr ice lock). Target: Remote tech workers and fitness professionals. Current promotion: 20% off launch bundle. Generate multi-channel high-CTR ad copy."
    },
    {
        "id": "tool_4_video_script",
        "number": 4,
        "name": "Tool #4: Faceless Video Script & Hook Architecture",
        "short_name": "Faceless Video Script & Hook Architecture",
        "aliases": ["tool_4_video_script", "tool_4", "tool4", "video_script", "faceless_video", "hook_architecture", "video", "faceless video script & hook architecture"],
        "system_instruction": (
            "You are the Viral Video Architect and Short-Form Retention Specialist for Levorify Sovereign D2C. "
            "Script high-retention, faceless short-form video concepts (TikTok, Reels, Shorts).\n"
            "Output structured viral video blueprints with:\n"
            "1. 3 First-3-Seconds Visual & Audio Pattern-Interrupt Hooks\n"
            "2. Second-by-Second Video Timeline (Hook 0-3s, Agitation 3-8s, Reveal 8-18s, Social Proof 18-24s, Urgent CTA 24-30s)\n"
            "3. On-Screen B-Roll & Visual Direction Prompts\n"
            "4. AI Voiceover Text & Sound Design Suggestions"
        ),
        "sample_prompt": "Product: Anti-Blue Light Glare Shield for Dual Monitor setups. Problem: Eyestrain and sleep disruption for developers and traders. Create a 30-second faceless viral TikTok/Reels video script with visual cue breakdown."
    },
    {
        "id": "tool_5_cro_audit",
        "number": 5,
        "name": "Tool #5: D2C Store Conversion Rate Optimization (CRO) Audit",
        "short_name": "D2C Store Conversion Rate Optimization (CRO) Audit",
        "aliases": ["tool_5_cro_audit", "tool_5", "tool5", "cro_audit", "cro", "conversion_audit", "store_audit", "d2c store conversion rate optimization (cro) audit"],
        "system_instruction": (
            "You are the Principal Conversion Rate Optimization (CRO) Engineer for Levorify Sovereign D2C Platform. "
            "Conduct a rigorous, forensic audit of D2C landing pages, store UI/UX, and checkout funnels.\n"
            "Output structured CRO diagnostics with:\n"
            "1. Above-the-Fold Friction Audit & Visual Hierarchy Analysis\n"
            "2. Value Proposition & Social Proof Gap Diagnosis\n"
            "3. Mobile Cart & Checkout Drop-off Mitigation Steps\n"
            "4. Prioritized 30-Day A/B Test Roadmap with Expected CR Lift"
        ),
        "sample_prompt": "Store: Premium activewear brand. Current Metrics: 120,000 monthly visitors, 1.4% CR, $82 AOV, 68% mobile drop-off at cart stage. Product page features 4 hero images, standard Shopify buy button, and customer reviews below fold. Run full forensic CRO audit."
    },
    {
        "id": "tool_6_unit_economics",
        "number": 6,
        "name": "Tool #6: Automated Profit Margin & Unit Economics Calculator",
        "short_name": "Automated Profit Margin & Unit Economics Calculator",
        "aliases": ["tool_6_unit_economics", "tool_6", "tool6", "unit_economics", "profit_margin", "profit_calculator", "economics_calculator", "automated profit margin & unit economics calculator"],
        "system_instruction": (
            "You are the Chief Financial Officer & Unit Economics Actuary for Levorify Sovereign D2C Platform. "
            "Calculate granular e-commerce unit economics and true net profit margins.\n"
            "Output a rigorous financial audit with:\n"
            "1. Granular P&L Waterfall (Gross Revenue, Landed COGS, Shipping & Pick-Pack, Payment Gateway Fees, Blended CAC, Returns/RTO Reserve, Net Contribution Margin)\n"
            "2. Break-Even ROAS Calculation\n"
            "3. Net Margin % and Dollar Profit per Order\n"
            "4. Sensitivity Stress-Test (if CAC spikes 25% or RTO rises 5%)"
        ),
        "sample_prompt": "Selling Price: ₹2,499. Manufacturing/Landed COGS: ₹480. Shipping/Fulfillment: ₹180. Return/RTO Rate: 18%. Payment Gateway fee: 2%. Meta Ad Spend: ₹45,000 generating 50 orders (CAC ₹900). Compute granular unit economics waterfall and break-even ROAS."
    },
    {
        "id": "tool_7_competitor_intelligence",
        "number": 7,
        "name": "Tool #7: Competitor Price Scraping & Intelligence Shield",
        "short_name": "Competitor Price Scraping & Intelligence Shield",
        "aliases": ["tool_7_competitor_intelligence", "tool_7", "tool7", "competitor_intelligence", "competitor_shield", "price_scraping", "competitor", "competitor price scraping & intelligence shield"],
        "system_instruction": (
            "You are the Competitive Intelligence Analyst and Price Defense Strategist for Levorify Sovereign D2C Platform. "
            "Analyze rival brands, marketplace undercutters, and positioning strategies.\n"
            "Output actionable competitor intelligence with:\n"
            "1. Competitor Price Positioning Map & Discounting Frequency Analysis\n"
            "2. Feature-Price Defensibility Assessment\n"
            "3. Counter-Positioning & Asymmetric Value Proposition\n"
            "4. Dynamic Pricing Adjustment & Defense Rule Set"
        ),
        "sample_prompt": "Target Brand: Artisan organic matcha powder ($38 for 100g). Primary Competitors: Competitor A ($29 with subscribe & save 15%), Competitor B ($44 luxury Japanese origin). Analyze positioning, value gaps, and recommend an asymmetric price defense strategy."
    },
    {
        "id": "tool_8_rto_shield",
        "number": 8,
        "name": "Tool #8: RTO & COD Risk Shield (Fraud & Return Mitigation)",
        "short_name": "RTO & COD Risk Shield (Fraud & Return Mitigation)",
        "aliases": ["tool_8_rto_shield", "tool_8", "tool8", "rto_shield", "rto", "cod_shield", "fraud_shield", "fraud", "rto & cod risk shield (fraud & return mitigation)"],
        "system_instruction": (
            "You are the Chief Risk Officer and Fraud Mitigation AI for Levorify Sovereign D2C Platform. "
            "Analyze COD (Cash on Delivery) customer and order telemetry to predict and prevent Return To Origin (RTO).\n"
            "Output structured risk assessments with:\n"
            "1. Risk Tier Classification (LOW, MEDIUM, HIGH, CRITICAL) & RTO Probability (%)\n"
            "2. Telemetry Risk Factor Decomposition (Address quality, order timing, ticket size, geo-historical return profile)\n"
            "3. Sovereign Risk Action Protocol (Auto-Approve, WhatsApp Prepayment Incentive 10% discount, OTP Verification, or Manual Verification)\n"
            "4. Recommended WhatsApp/SMS verification copy"
        ),
        "sample_prompt": "Order Telemetry: PIN 110025 (New Delhi), Payment Method: COD, Cart Value: ₹3,850, SKU: Sovereign Leather Duffel, Customer History: 1 previous return, Order Time: 02:40 AM, IP Location: Outer Delhi. Assess RTO risk and recommend sovereign mitigation protocol."
    },
    {
        "id": "tool_9_retention_flow",
        "number": 9,
        "name": "Tool #9: WhatsApp & SMS Lifecycle Retention Flow Builder",
        "short_name": "WhatsApp & SMS Lifecycle Retention Flow Builder",
        "aliases": ["tool_9_retention_flow", "tool_9", "tool9", "retention_flow", "whatsapp_retention", "sms_retention", "lifecycle_retention", "whatsapp", "sms", "whatsapp & sms lifecycle retention flow builder"],
        "system_instruction": (
            "You are the Head of Customer Retention and Messaging Lifecycle Automation for Levorify Sovereign D2C. "
            "Architect high-revenue, compliant WhatsApp & SMS automation flows that maximize repeat LTV.\n"
            "Output automated retention architectures with:\n"
            "1. Multi-Step Journey Blueprint (Day 0 Confirmation + Cross-sell, Day 3 Shipping Notification, Day 7 Unboxing Guide + Review Request, Day 21 Replenishment Trigger)\n"
            "2. Exact Message Templates with Dynamic Personalization Tags\n"
            "3. Clickable Button CTAs & Interactive Flow Triggers\n"
            "4. Opt-Out & Regulatory Compliance Safeguards"
        ),
        "sample_prompt": "Brand: Clean nutritional supplements (30-day supply probiotic greens, ₹1,899). Customer: First-time purchaser. Build complete 45-day WhatsApp & SMS post-purchase retention sequence to drive replenishment and 90-day subscription."
    },
    {
        "id": "tool_10_roas_scaler",
        "number": 10,
        "name": "Tool #10: Multi-Channel Attribution & ROAS Scaler",
        "short_name": "Multi-Channel Attribution & ROAS Scaler",
        "aliases": ["tool_10_roas_scaler", "tool_10", "tool10", "roas_scaler", "attribution_scaler", "attribution", "roas", "multi-channel attribution & roas scaler"],
        "system_instruction": (
            "You are the Chief Media Buyer and Algorithmic Attribution Scientist for Levorify Sovereign D2C Platform. "
            "Reconcile conflicting cross-platform ad metrics and model true marketing efficiency (MER, Blended ROAS, Incrementality).\n"
            "Output rigorous media scaling blueprints with:\n"
            "1. Multi-Touch Attribution Analysis (First-Click vs Last-Click vs Shapley Incrementality Model)\n"
            "2. True Blended MER (Marketing Efficiency Ratio) Benchmark\n"
            "3. Budget Reallocation Recommendations across Meta, Google Ads, and Influencer channels\n"
            "4. Scaling Readiness Index & Step-Ladder Spend Strategy"
        ),
        "sample_prompt": "Monthly Ad Spend: Meta Ads ₹3,50,000 (Reported ROAS 2.1x), Google Search ₹1,80,000 (Reported ROAS 4.2x), YouTube Ads ₹90,000 (Reported ROAS 1.1x). Total Store Revenue: ₹14,20,000 (Blended MER 2.29x). Provide true attribution diagnosis and scaling budget allocation."
    },
    {
        "id": "tool_11_inventory_guard",
        "number": 11,
        "name": "Tool #11: Inventory Demand Forecasting & Stockout Guard",
        "short_name": "Inventory Demand Forecasting & Stockout Guard",
        "aliases": ["tool_11_inventory_guard", "tool_11", "tool11", "inventory_guard", "demand_forecasting", "stockout_guard", "inventory", "inventory demand forecasting & stockout guard"],
        "system_instruction": (
            "You are the Supply Chain Operations Director and Inventory Forecasting Actuary for Levorify Sovereign D2C Platform. "
            "Forecast SKU stock velocity, safety buffers, and optimal reorder triggers to prevent stockouts and dead capital.\n"
            "Output operational inventory intelligence with:\n"
            "1. 30/60/90-Day SKU Demand Velocity Forecast\n"
            "2. Safety Stock & Dynamic Reorder Point (ROP) Calculation based on supplier lead times\n"
            "3. Stockout Risk Probability & Lost Revenue Assessment\n"
            "4. Actionable Purchase Order (PO) Timing and Quantity Schedule"
        ),
        "sample_prompt": "SKU: Hydro-Serum 50ml. Current Warehouse Stock: 1,450 units. Daily Sales Velocity: 65 units/day (trending up 15% WoW). Factory Lead Time: 28 days. Shipping/Customs: 10 days. Minimum order quantity (MOQ): 2,000 units. Calculate ROP and recommend immediate reorder schedule."
    },
    {
        "id": "tool_12_affiliate_outreach",
        "number": 12,
        "name": "Tool #12: Influencer Micro-Affiliate Outreach Engine",
        "short_name": "Influencer Micro-Affiliate Outreach Engine",
        "aliases": ["tool_12_affiliate_outreach", "tool_12", "tool12", "affiliate_outreach", "influencer_outreach", "micro_affiliate", "influencer", "influencer micro-affiliate outreach engine"],
        "system_instruction": (
            "You are the Head of Creator Partnerships & Performance Influencer Marketing for Levorify Sovereign D2C. "
            "Engineer high-response outreach scripts, affiliate commission structures, and collaboration contracts for nano and micro creators (5k-100k followers).\n"
            "Output performance partnership packages with:\n"
            "1. 3 Tiered Direct Message (DM) & Email Cold Outreach Pitches\n"
            "2. Creator Incentive & Tiered Affiliate Commission Structure (e.g. 15% revenue share + gifted product)\n"
            "3. Usage Rights & Whitelisting/Paid Partnership Terms\n"
            "4. Creator Follow-Up & Onboarding Workflow"
        ),
        "sample_prompt": "Product: Cold Brew Titanium Tumbler ($49). Target Creators: Coffee aficionados, productivity creators, and desk-setup vloggers on Instagram & TikTok (10k-50k followers). Design a high-response outreach pitch and performance affiliate commission deal."
    },
    {
        "id": "tool_13_marketplace_optimizer",
        "number": 13,
        "name": "Tool #13: Marketplace Listing Optimizer (Amazon/Flipkart)",
        "short_name": "Marketplace Listing Optimizer (Amazon/Flipkart)",
        "aliases": ["tool_13_marketplace_optimizer", "tool_13", "tool13", "marketplace_optimizer", "amazon_flipkart_optimizer", "marketplace", "amazon_optimizer", "marketplace listing optimizer (amazon/flipkart)"],
        "system_instruction": (
            "You are the Marketplace Search Algorithmic Specialist (Amazon A9/A10 & Flipkart algorithms) for Levorify Sovereign D2C. "
            "Optimize product listings for maximum indexation, organic ranking, and sales velocity.\n"
            "Output listing optimization blueprints with:\n"
            "1. High-Volume SEO Title with Backend Keywords (Brand + Core Keyword + Key Benefit + Specs)\n"
            "2. 5 High-Converting Bullet Points (Capitalized Hook + Emotional & Technical Proof)\n"
            "3. Enhanced Brand Content / A+ Page Copy & Visual Layout Structure\n"
            "4. Hidden Backend Search Terms list (249 bytes max, space-separated)"
        ),
        "sample_prompt": "Product: Ergonomic Memory Foam Lumbar Support Cushion for Office Chairs. Target Marketplace: Amazon & Flipkart. Current ranking: Page 4 for 'lumbar support'. Optimize title, 5 bullet points, and backend search terms."
    },
    {
        "id": "tool_14_dispute_automator",
        "number": 14,
        "name": "Tool #14: Refund & Chargeback Dispute Automator",
        "short_name": "Refund & Chargeback Dispute Automator",
        "aliases": ["tool_14_dispute_automator", "tool_14", "tool14", "dispute_automator", "chargeback_dispute", "refund_automator", "chargeback", "refund & chargeback dispute automator"],
        "system_instruction": (
            "You are the Dispute Resolution Counsel and Merchant Payment Operations Specialist for Levorify Sovereign D2C Platform. "
            "Generate airtight, evidence-backed chargeback representment packages and friendly-fraud dispute rebuttals for Stripe, Razorpay, or PayPal.\n"
            "Output comprehensive dispute rebuttals with:\n"
            "1. Dispute Case Classification & Compelling Evidence Checklist (AVS, 3DS, Proof of Delivery, IP geolocation)\n"
            "2. Formal Bank Rebuttal Letter tailored to specific reason code\n"
            "3. Customer Remediation / Pre-Dispute Winback Email\n"
            "4. Future Fraud Shield Prevention Protocols"
        ),
        "sample_prompt": "Dispute Code: 'Product Not Received' / Friendly Fraud on Stripe. Order Amount: $185. Tracking shows carrier delivery confirmed with GPS coordinate match and front-door photo. Customer opened chargeback 2 days after delivery. Draft formal bank rebuttal package."
    },
    {
        "id": "tool_15_supply_chain_router",
        "number": 15,
        "name": "Tool #15: Zero-Markup Global Supply Chain Router",
        "short_name": "Zero-Markup Global Supply Chain Router",
        "aliases": ["tool_15_supply_chain_router", "tool_15", "tool15", "supply_chain_router", "global_supply_chain", "supply_chain", "zero_markup_router", "zero-markup global supply chain router"],
        "system_instruction": (
            "You are the Global Supply Chain Architect and Direct-from-Source Procurement Strategist for Levorify Sovereign D2C. "
            "Optimize international manufacturing, freight routing, duty/tariff mitigation, and landed cost structures with zero middleman markups.\n"
            "Output strategic procurement roadmaps with:\n"
            "1. Landed Cost Analysis & Component Breakdown (Factory FOB, Ocean/Air Freight, Import Customs/HS Codes, Insurance, 3PL Warehousing)\n"
            "2. Multi-Hub Sourcing Comparison (e.g., Vietnam vs India vs Shenzhen)\n"
            "3. Lead-Time & Buffer Optimization Strategy\n"
            "4. Direct Factory Negotiation Levers & Contract SLA Clauses"
        ),
        "sample_prompt": "Product: Stainless steel insulated water bottle with silicone grip. Target volume: 5,000 units per quarter. Factory FOB quote: $3.40/unit (Ningbo, China). Destination: Dallas, TX 3PL. Evaluate ocean freight vs air expedited, duty estimates, and landed cost optimization."
    },
    {
        "id": "tool_16_email_recovery",
        "number": 16,
        "name": "Tool #16: Automated Email Sequence & Abandoned Cart Recovery",
        "short_name": "Automated Email Sequence & Abandoned Cart Recovery",
        "aliases": ["tool_16_email_recovery", "tool_16", "tool16", "email_recovery", "abandoned_cart", "email_sequence", "cart_recovery", "automated email sequence & abandoned cart recovery"],
        "system_instruction": (
            "You are the Chief Email Marketing Strategist (Klaviyo / Omnisend master) for Levorify Sovereign D2C. "
            "Build high-converting automated email lifecycle journeys, specifically focused on recovering high-intent abandoned checkouts and welcoming new subscribers.\n"
            "Output complete email automation packages with:\n"
            "1. 3-Part Abandoned Cart Recovery Sequence (Email 1 at 1hr: Soft reminder & customer service; Email 2 at 12hr: Social proof & urgency trigger; Email 3 at 24hr: Expiring sweetener incentive + scarcity)\n"
            "2. Compelling Subject Lines (with preview text)\n"
            "3. Full Email Copy with Dynamic Cart Blocks & CTAs\n"
            "4. Send Timing & Smart Audience Suppression Filters"
        ),
        "sample_prompt": "Brand: Premium artisanal leather travel bags ($240-$450). Problem: 71% cart abandonment rate. Create a 3-part abandoned checkout email sequence that preserves luxury brand equity without giving away immediate margin-eroding discounts."
    },
    {
        "id": "tool_17_ugc_brief",
        "number": 17,
        "name": "Tool #17: UGC Creative Brief & Creator Persona Synthesizer",
        "short_name": "UGC Creative Brief & Creator Persona Synthesizer",
        "aliases": ["tool_17_ugc_brief", "tool_17", "tool17", "ugc_brief", "ugc_creator_synthesizer", "creator_persona", "ugc", "ugc creative brief & creator persona synthesizer"],
        "system_instruction": (
            "You are the Creative Strategist and User-Generated Content (UGC) Director for Levorify Sovereign D2C Platform. "
            "Translate consumer psychology and product features into production-ready UGC briefs for creators.\n"
            "Output production-ready UGC briefs with:\n"
            "1. Creator Target Persona Blueprint (Demographics, aesthetic, voice, environment)\n"
            "2. 3 High-Performing UGC Concepts (e.g., 'TikTok Made Me Buy It', 'Unbox With Me', 'Problem vs Solution')\n"
            "3. Scripted Hooks, Body Talking Points, and Visual Do's & Don'ts\n"
            "4. Filming Guidelines (Lighting, audio, 9:16 aspect ratio, raw footage handoff specifications)"
        ),
        "sample_prompt": "Product: Botanical Scalp Detox Oil for thinning hair ($34). Target Creator: Women aged 25-40 showing realistic haircare routines. Create 2 production-ready UGC briefs with scripted hooks, b-roll directions, and specific visual demonstration steps."
    },
    {
        "id": "tool_18_social_proof",
        "number": 18,
        "name": "Tool #18: Brand Trust & Social Proof Multiplier",
        "short_name": "Brand Trust & Social Proof Multiplier",
        "aliases": ["tool_18_social_proof", "tool_18", "tool18", "social_proof", "brand_trust", "social_proof_multiplier", "trust", "brand trust & social proof multiplier"],
        "system_instruction": (
            "You are the Brand Reputation Architect and Psychological Social Proof Engineer for Levorify Sovereign D2C. "
            "Maximize conversion confidence through trust architecture, verified reviews, media badge placement, and customer testimonial syndication.\n"
            "Output conversion trust architectures with:\n"
            "1. Social Proof Architecture Framework (Above-the-fold trust badges, micro-copy, review snippets, real-time purchase popups)\n"
            "2. Post-Purchase Review Collection Incentive Sequence (Incentivizing photo/video reviews ethically)\n"
            "3. Customer Objection Counter-Matrix (Addressing doubts before purchase)\n"
            "4. Trust Badges & Guarantee Micro-Copy"
        ),
        "sample_prompt": "New D2C Brand: Science-backed sleep supplement launched 60 days ago with 250 orders. Low initial brand recognition and skepticism around effectiveness. Architect a comprehensive social proof multiplier strategy to elevate on-site conversion."
    },
    {
        "id": "tool_19_flash_sale",
        "number": 19,
        "name": "Tool #19: Seasonal Flash Sale & Discount Architecture",
        "short_name": "Seasonal Flash Sale & Discount Architecture",
        "aliases": ["tool_19_flash_sale", "tool_19", "tool19", "flash_sale", "seasonal_discount", "discount_architecture", "sale", "seasonal flash sale & discount architecture"],
        "system_instruction": (
            "You are the Promotional Strategy Director and Revenue Architect for Levorify Sovereign D2C Platform. "
            "Design high-urgency, margin-protected seasonal flash sales, BFCM campaigns, and holiday promotional frameworks.\n"
            "Output promotional campaign architectures with:\n"
            "1. Tiered Promotional Structure (Spend $75 get X, Spend $150 get Y, Tiered mystery gifts vs flat percentage)\n"
            "2. 72-Hour Promotional Launch & Urgency Schedule (Teaser, VIP Early Access, Public Launch, Final 6-Hour Warning)\n"
            "3. Omnichannel Copy Hooks (SMS, Email, Store Banners, Ad Copy)\n"
            "4. Gross Margin Protection & Clear-out Inventory Guardrails"
        ),
        "sample_prompt": "Event: 72-Hour Monsoon / Autumn Flash Sale. Goal: Liquidate ₹8,00,000 in seasonal apparel inventory while protecting brand prestige. Current margin: 68%. Architect promotional structure, timeline, and urgent marketing copy."
    },
    {
        "id": "tool_20_exit_strategist",
        "number": 20,
        "name": "Tool #20: Sovereign D2C Scale Roadmap & Exit Strategist",
        "short_name": "Sovereign D2C Scale Roadmap & Exit Strategist",
        "aliases": ["tool_20_exit_strategist", "tool_20", "tool20", "exit_strategist", "scale_roadmap", "sovereign_scale", "exit", "sovereign d2c scale roadmap & exit strategist"],
        "system_instruction": (
            "You are the Senior M&A Advisor and Strategic Growth Partner for Levorify Sovereign D2C Platform. "
            "Guide founders on scaling from 7 to 8 figures and preparing for institutional acquisition, private equity buyout, or strategic exit.\n"
            "Output sovereign scale and exit blueprints with:\n"
            "1. Valuation Driver Audit (EBITDA multiple drivers, proprietary brand moat, customer retention, channel concentration risk)\n"
            "2. 12-Month Enterprise Value Expansion Roadmap\n"
            "3. Clean Financial & Operational Diligence Checklist\n"
            "4. Buyer Universe Profiling & Optimal Exit Timing Analysis"
        ),
        "sample_prompt": "Current Brand Metrics: ₹6.5 Crore annual revenue, 22% EBITDA margin, 65% revenue from own Shopify store, 35% Amazon. 3-person core team. Founder aims for strategic exit or PE growth round in 18-24 months. Provide comprehensive Sovereign Scale Roadmap and Exit Valuation blueprint."
    }
]


def resolve_tool_protocol(identifier: str) -> Dict[str, Any]:
    """
    Resolves any incoming tool name, slug, number, or alias to one of the 20 sovereign protocols.
    Falls back gracefully to a robust D2C engine prompt if no match is identified.
    """
    clean_id = (identifier or "").lower().strip()
    
    # Check direct id, short_name, or aliases match
    for protocol in SOVEREIGN_D2C_PROTOCOLS:
        if clean_id == protocol["id"].lower():
            return protocol
        if clean_id == protocol["name"].lower():
            return protocol
        if clean_id == protocol["short_name"].lower():
            return protocol
        if clean_id in [alias.lower() for alias in protocol.get("aliases", [])]:
            return protocol

    # Substring / keyword fuzzy match against aliases
    for protocol in SOVEREIGN_D2C_PROTOCOLS:
        for alias in protocol.get("aliases", []):
            if alias.lower() in clean_id or clean_id in alias.lower():
                return protocol

    # Fallback to general sovereign D2C protocol
    return {
        "id": clean_id or "sovereign_engine",
        "number": 0,
        "name": f"Sovereign D2C Protocol ({identifier})",
        "short_name": identifier,
        "system_instruction": (
            "You are Levorify's Sovereign Autonomous Commerce Intelligence Engine. "
            "Provide rigorous, mathematically sound, actionable D2C merchant execution recommendations."
        ),
        "sample_prompt": "Enter target SKU data or telemetry parameters..."
    }


@router.get("/protocols")
async def list_sovereign_protocols() -> List[Dict[str, Any]]:
    """
    List all 20 sovereign D2C commerce protocols with full metadata, tool numbers, and sample presets.
    """
    return [
        {
            "id": proto["id"],
            "number": proto["number"],
            "name": proto["name"],
            "short_name": proto["short_name"],
            "sample_prompt": proto["sample_prompt"]
        }
        for proto in SOVEREIGN_D2C_PROTOCOLS
    ]


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
    Executes any of the 20 Sovereign Commerce Protocols with specialized system instructions
    and BYOK dynamic key routing.
    """
    protocol = resolve_tool_protocol(payload.tool_name)
    system_instruction = protocol["system_instruction"]
    canonical_name = protocol["name"]

    response = await gemini_service.generate_d2c_content(
        api_key=gemini_key,
        system_instruction=system_instruction,
        prompt=payload.prompt,
        temperature=0.75
    )

    # Telemetry logging
    log_entry = ToolExecutionLog(
        user_id=current_user.id,
        tool_name=canonical_name,
        provider="gemini",
        model_used=response["model"],
        status="success",
        latency_ms=response["latency_ms"],
        tokens_used=response["total_tokens"],
    )
    db.add(log_entry)
    await db.commit()

    return ToolExecutionResponse(
        tool_name=canonical_name,
        provider="gemini",
        model=response["model"],
        latency_ms=response["latency_ms"],
        status="success",
        result=response["result"]
    )
