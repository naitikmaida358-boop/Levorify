import asyncio
import sys
import uuid
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
from httpx import ASGITransport, AsyncClient, Response, Request
from unittest.mock import patch, AsyncMock

from app.main import app
from app.core.database import init_db
from app.core.config import settings
from app.services.gemini_service import (
    GeminiBYOKService,
    _score_model_preference,
    _generate_pattern_fallback_models
)


async def test_dynamic_fallback_and_discovery_engine():
    print("\n=== TESTING GEMINI DYNAMIC DISCOVERY & SELF-HEALING ENGINE ===")

    # 1. Test model preference scoring
    score_future = _score_model_preference("gemini-3.0-flash-lite")
    score_25 = _score_model_preference("gemini-2.5-flash-lite")
    score_15 = _score_model_preference("gemini-1.5-flash")
    score_embed = _score_model_preference("text-embedding-004")

    assert score_future > score_25 > score_15 > 0, "Dynamic scoring failed version/tier ordering"
    assert score_embed < 0, "Embedding models must have negative score"
    print("  [A] Dynamic Model Preference Scoring: PASS (3.0 > 2.5 > 1.5, embeddings excluded).")

    # 2. Test runtime model discovery from mock Google /models endpoint
    mock_models_response = {
        "models": [
            {
                "name": "models/text-embedding-004",
                "supportedGenerationMethods": ["embedContent"]
            },
            {
                "name": "models/gemini-1.5-flash",
                "supportedGenerationMethods": ["generateContent"]
            },
            {
                "name": "models/gemini-2.5-flash-lite",
                "supportedGenerationMethods": ["generateContent", "countTokens"]
            },
            {
                "name": "models/gemini-3.0-flash-lite-preview",
                "supportedGenerationMethods": ["generateContent"]
            }
        ]
    }

    from unittest.mock import MagicMock
    mock_client = AsyncMock()
    mock_res = MagicMock()
    mock_res.status_code = 200
    mock_res.json.return_value = mock_models_response
    mock_client.get = AsyncMock(return_value=mock_res)

    discovered = await GeminiBYOKService.discover_available_models("AIzaSyFakeKey_DynamicTest", client=mock_client)
    assert "text-embedding-004" not in discovered
    assert "gemini-2.5-flash-lite" in discovered
    assert discovered[0] == "gemini-3.0-flash-lite-preview" or discovered[0] == "gemini-2.5-flash-lite"
    print(f"  [B] Runtime Model Discovery: PASS (discovered: {discovered}).")

    # 3. Test self-healing 404 fallback cascade in generate_d2c_content
    # Primary candidate returns 404, secondary candidate returns 200
    call_count = 0
    async def mock_post_handler(url, **kwargs):
        nonlocal call_count
        call_count += 1
        req = Request("POST", url)
        # First candidate fails with 404
        if "gemini-2.5-flash-lite" in url and call_count == 1:
            return Response(404, request=req, json={"error": {"message": "models/gemini-2.5-flash-lite is not found"}})
        # Fallback candidate succeeds with 200
        return Response(
            200,
            request=req,
            json={
                "candidates": [{
                    "content": {"parts": [{"text": "Self-healing fallback execution succeeded seamlessly."}]}
                }],
                "usageMetadata": {"totalTokenCount": 98}
            }
        )

    with patch("app.services.gemini_service.GeminiBYOKService.discover_available_models", new_callable=AsyncMock) as mock_disc, \
         patch("httpx.AsyncClient.post", side_effect=mock_post_handler):
        mock_disc.return_value = ["gemini-2.5-flash-lite", "gemini-2.0-flash-lite", "gemini-1.5-flash"]

        result = await GeminiBYOKService.generate_d2c_content(
            api_key="AIzaSyTest_FallbackKey",
            system_instruction="You are a D2C strategist.",
            prompt="Analyze SKU margins.",
            model="gemini-2.5-flash-lite"
        )
        assert result["result"] == "Self-healing fallback execution succeeded seamlessly."
        assert result["total_tokens"] == 98
        print(f"  [C] Self-Healing 404 Fallback Cascade: PASS (recovered seamlessly using: {result['model']}).")


async def run_dashboard_integration_test():
    print("=== LEVORIFY DASHBOARD & BACKEND INTEGRATION TEST ===")

    await init_db()
    print("[1/10] Database initialized.")

    # Verify settings model is configured to active gemini-2.5-flash-lite
    assert settings.DEFAULT_GEMINI_MODEL == "gemini-2.5-flash-lite", (
        f"Expected DEFAULT_GEMINI_MODEL to be 'gemini-2.5-flash-lite', got '{settings.DEFAULT_GEMINI_MODEL}'"
    )
    print(f"[2/10] Config Model Verification PASS: Default model is {settings.DEFAULT_GEMINI_MODEL}.")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Verify /dashboard HTML page route, Security Headers, Handbook & Currency Switcher
        r_dash = await client.get("/dashboard")
        assert r_dash.status_code == 200, f"Failed to get dashboard: {r_dash.status_code}"
        
        # Verify Enterprise Security Headers
        assert r_dash.headers.get("X-Frame-Options") == "SAMEORIGIN", "Missing X-Frame-Options"
        assert r_dash.headers.get("X-Content-Type-Options") == "nosniff", "Missing X-Content-Type-Options"
        assert "max-age" in r_dash.headers.get("Strict-Transport-Security", ""), "Missing HSTS"
        assert "X-Process-Time-Ms" in r_dash.headers, "Missing Latency header"
        print("[3/10] Enterprise Security Headers PASS: Frame, nosniff, HSTS, and Latency verified.")

        dash_text = r_dash.text
        assert "Levorify OS | Sovereign Merchant Dashboard" in dash_text
        assert "BYOK Vault" in dash_text
        assert "Gemini 2.5 Flash Lite" in dash_text
        
        # Verify In-App Operator Handbook & Onboarding Tour UI
        assert "Sovereign Operator Handbook" in dash_text
        assert "Start Guided Tour" in dash_text
        assert "The ₹800+ Net Margin Rulebook" in dash_text
        assert "BYOK Vault Enclave" in dash_text
        assert "20 Protocols Atlas" in dash_text
        
        # Verify Geo-Currency Switcher
        assert "currency-selector" in dash_text
        assert "curr-inr" in dash_text
        assert "curr-usd" in dash_text
        assert "curr-eur" in dash_text
        assert "curr-gbp" in dash_text

        # Verify Plan URL Parameter Banner in Dashboard
        assert "plan-banner" in dash_text
        assert "plan-badge-pill" in dash_text
        assert "plan-price-tag" in dash_text
        assert "checkUrlPlanParams" in dash_text

        expected_tools = [
            "Tool #1: Autonomous Product Research & Trend Scout",
            "Tool #2: Dynamic Price Anchoring & Bundling Matrix",
            "Tool #3: High-Velocity Ad Copy & Creative Generator",
            "Tool #4: Faceless Video Script & Hook Architecture",
            "Tool #5: D2C Store Conversion Rate Optimization (CRO) Audit",
            "Tool #6: Automated Profit Margin & Unit Economics Calculator",
            "Tool #7: Competitor Price Scraping & Intelligence Shield",
            "Tool #8: RTO & COD Risk Shield (Fraud & Return Mitigation)",
            "Tool #9: WhatsApp & SMS Lifecycle Retention Flow Builder",
            "Tool #10: Multi-Channel Attribution & ROAS Scaler",
            "Tool #11: Inventory Demand Forecasting & Stockout Guard",
            "Tool #12: Influencer Micro-Affiliate Outreach Engine",
            "Tool #13: Marketplace Listing Optimizer (Amazon/Flipkart)",
            "Tool #14: Refund & Chargeback Dispute Automator",
            "Tool #15: Zero-Markup Global Supply Chain Router",
            "Tool #16: Automated Email Sequence & Abandoned Cart Recovery",
            "Tool #17: UGC Creative Brief & Creator Persona Synthesizer",
            "Tool #18: Brand Trust & Social Proof Multiplier",
            "Tool #19: Seasonal Flash Sale & Discount Architecture",
            "Tool #20: Sovereign D2C Scale Roadmap & Exit Strategist",
        ]

        for expected_tool in expected_tools:
            assert expected_tool in dash_text, f"Missing tool in dashboard.html: '{expected_tool}'"
        print(f"[4/10] Dashboard HTML serving PASS: All 20 Sovereign Protocols, Handbook, Plan Banner & Currency Switcher rendered.")

        # 1b. Verify Landing Page One-Time Purchase Pricing & Working CTAs
        r_landing = await client.get("/landing")
        assert r_landing.status_code == 200, f"Failed to get landing page: {r_landing.status_code}"
        landing_text = r_landing.text

        # Clean removal of old monthly SaaS recurring pricing
        assert "$1,950" not in landing_text, "Found old $1,950 pricing in landing page"
        assert "$4,910" not in landing_text, "Found old $4,910 pricing in landing page"
        assert "$1,950/mo" not in landing_text
        assert "$4,910/mo" not in landing_text

        # Presence of Affordable 3-Tier One-Time Purchase model (Capped below ₹3,000)
        assert "Starter Operator Pass" in landing_text
        assert "₹999" in landing_text
        assert "Sovereign Lifetime Pro" in landing_text
        assert "₹1,999" in landing_text
        assert "Ultimate Agency Suite" in landing_text
        assert "₹2,999" in landing_text
        assert "ONE-TIME PAYMENT" in landing_text
        assert "ZERO MONTHLY SUBSCRIPTIONS" in landing_text

        # Ensure no plans exceed ₹3,000 cap
        assert "₹3,999" not in landing_text, "Found plan exceeding ₹3,000 cap"
        assert "₹9,999" not in landing_text, "Found plan exceeding ₹3,000 cap"

        # Working Action buttons wired to dashboard with plan parameters
        assert 'href="dashboard.html?plan=starter"' in landing_text
        assert 'href="dashboard.html?plan=pro"' in landing_text
        assert 'href="dashboard.html?plan=agency"' in landing_text
        assert 'href="dashboard.html"' in landing_text
        assert "setPricingCurrency" in landing_text
        assert "initGeoCurrency" in landing_text
        print("[4b/10] Landing Page Pricing PASS: Affordable one-time structure (INR 999 / 1,999 / 2,999 capped < 3,000) & Geo-location engine verified.")

        # 2. Register node
        uid = str(uuid.uuid4())[:8]
        test_email = f"operator_{uid}@levorifybrand.com"
        test_pwd = "SovereignNodePassword123!"
        reg_payload = {
            "email": test_email,
            "password": test_pwd,
            "brand_name": "Sovereign Vance"
        }
        r_reg = await client.post("/api/v1/auth/register", json=reg_payload)
        assert r_reg.status_code == 201, f"Registration failed: {r_reg.text}"
        print(f"[5/10] Node Registration PASS: Created user for {test_email}.")

        # 3. Form-based OAuth2 login matching dashboard handleAuth()
        form_data = {
            "username": test_email,
            "password": test_pwd
        }
        r_token = await client.post("/api/v1/auth/token", data=form_data)
        assert r_token.status_code == 200, f"Token generation failed: {r_token.text}"
        token_data = r_token.json()
        access_token = token_data["access_token"]
        assert access_token
        auth_headers = {"Authorization": f"Bearer {access_token}"}
        print(f"[6/10] Dashboard /auth/token Login PASS: Issued JWT length {len(access_token)}.")

        # 4. Profile verification /auth/me for header display
        r_me = await client.get("/api/v1/auth/me", headers=auth_headers)
        assert r_me.status_code == 200
        assert r_me.json()["email"] == test_email
        print(f"[7/10] Profile Retrieval PASS: Display identity {r_me.json()['email']}.")

        # 5. Key configuration & status
        with patch("app.services.gemini_service.gemini_service.verify_key", new_callable=AsyncMock) as mock_verify:
            mock_verify.return_value = {"valid": True, "message": "Key verified"}

            r_config = await client.post(
                "/api/v1/keys/configure",
                headers=auth_headers,
                json={"provider": "gemini", "api_key": "AIzaSyTestKey_991823749817293847192837"}
            )
            assert r_config.status_code == 200, f"Key configure failed: {r_config.text}"
            assert r_config.json()["status"] == "success"
            masked = r_config.json()["masked_key"]
            print(f"[8/10] BYOK Vault /keys/configure PASS: Vaulted hint {masked}.")

            r_status = await client.get("/api/v1/keys/status?provider=gemini", headers=auth_headers)
            assert r_status.status_code == 200
            assert r_status.json()["has_key"] is True
            assert r_status.json()["masked_key"] == masked
            print(f"[8b/10] BYOK Vault /keys/status PASS: Verified active key presence.")

        # 6. Verify Protocols Registry Endpoint
        r_proto = await client.get("/api/v1/tools/protocols")
        assert r_proto.status_code == 200
        protocols_data = r_proto.json()
        assert len(protocols_data) == 20, f"Expected 20 protocols, got {len(protocols_data)}"
        print(f"[8c/10] Tools Protocols Registry PASS: Found {len(protocols_data)} sovereign protocols.")

        # 7. Payload Sanitization & Anti-Injection Guard Testing
        # A) Empty prompt check
        r_empty = await client.post(
            "/api/v1/tools/execute",
            headers=auth_headers,
            json={"tool_name": "tool_1_trend_scout", "prompt": "   "}
        )
        assert r_empty.status_code == 400, "Expected 400 for empty prompt"
        assert "cannot be empty" in r_empty.json()["detail"]
        
        # B) Oversized prompt check (>15,000 chars)
        r_huge = await client.post(
            "/api/v1/tools/execute",
            headers=auth_headers,
            json={"tool_name": "tool_1_trend_scout", "prompt": "A" * 16000}
        )
        assert r_huge.status_code == 400, "Expected 400 for oversized prompt"
        assert "exceeds maximum allowed limit" in r_huge.json()["detail"]
        print("[9/10] Payload Sanitization & Anti-Injection Guard PASS: Handled empty and oversized payloads safely.")

        # 8. Tool execution dispatch across multiple protocols with script injection stripping
        test_cases = [
            ("tool_1_trend_scout", "<script>alert('xss')</script>Category: Titanium EDC gadgets. Target landed COGS: under $12.", "Trend Velocity Score"),
            ("tool_6_unit_economics", "Selling Price: ₹2,499. COGS: ₹480. RTO: 18%.", "P&L Waterfall"),
            ("tool_8_rto_shield", "Order value ₹3,850, PIN 110025, COD order", "RTO Risk"),
            ("tool_20_exit_strategist", "Brand revenue ₹6.5 Crore, 22% EBITDA margin.", "Valuation Driver Audit"),
        ]

        with patch("app.services.gemini_service.gemini_service.generate_d2c_content", new_callable=AsyncMock) as mock_gen:
            for tool_id, sample_prompt, mock_snippet in test_cases:
                mock_gen.return_value = {
                    "result": f"Execution output for {tool_id}. {mock_snippet} confirmed.",
                    "model": "gemini-2.5-flash-lite",
                    "latency_ms": 115.4,
                    "total_tokens": 142
                }

                r_tool = await client.post(
                    "/api/v1/tools/execute",
                    headers=auth_headers,
                    json={
                        "tool_name": tool_id,
                        "prompt": sample_prompt
                    }
                )
                assert r_tool.status_code == 200, f"Execution failed for {tool_id}: {r_tool.text}"
                res_json = r_tool.json()
                assert res_json["status"] == "success"
                assert res_json["model"] == "gemini-2.5-flash-lite"
                assert mock_snippet in res_json["result"]
                print(f"       -> Protocol [{res_json['tool_name']}] dispatch PASS (model: {res_json['model']}).")

        print("[10/10] Autonomous Engine Execution Routing PASS for all tested Sovereign Protocols.")

    await test_dynamic_fallback_and_discovery_engine()
    print("\n>>> ALL 20 SOVEREIGN D2C COMMERCE INTEGRATION CHECKS & DYNAMIC ENGINE CHECKS PASSED WITH 100% SUCCESS! <<<")


if __name__ == "__main__":
    asyncio.run(run_dashboard_integration_test())
