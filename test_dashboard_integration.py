import asyncio
import uuid
from httpx import ASGITransport, AsyncClient
from unittest.mock import patch, AsyncMock

from app.main import app
from app.core.database import init_db


async def run_dashboard_integration_test():
    print("=== LEVORIFY DASHBOARD & BACKEND INTEGRATION TEST ===")

    await init_db()
    print("[1/7] Database initialized.")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Verify /dashboard HTML page route
        r_dash = await client.get("/dashboard")
        assert r_dash.status_code == 200, f"Failed to get dashboard: {r_dash.status_code}"
        assert "Levorify OS | Sovereign Merchant Dashboard" in r_dash.text
        assert "BYOK Vault" in r_dash.text
        print("[2/7] Dashboard HTML serving PASS: 200 OK.")

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
        print(f"[3/7] Node Registration PASS: Created user for {test_email}.")

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
        print(f"[4/7] Dashboard /auth/token Login PASS: Issued JWT length {len(access_token)}.")

        # 4. Profile verification /auth/me for header display
        r_me = await client.get("/api/v1/auth/me", headers=auth_headers)
        assert r_me.status_code == 200
        assert r_me.json()["email"] == test_email
        print(f"[5/7] Profile Retrieval PASS: Display identity {r_me.json()['email']}.")

        # 5. Key configuration & status
        # Mock Gemini verification so we don't need a live outbound network call in offline test
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
            print(f"[6/7] BYOK Vault /keys/configure PASS: Vaulted hint {masked}.")

            r_status = await client.get("/api/v1/keys/status?provider=gemini", headers=auth_headers)
            assert r_status.status_code == 200
            assert r_status.json()["has_key"] is True
            assert r_status.json()["masked_key"] == masked
            print(f"[6b/7] BYOK Vault /keys/status PASS: Verified active key presence.")

        # 6. Tool execution dispatch
        with patch("app.services.gemini_service.gemini_service.generate_d2c_content", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = {
                "result": "RTO Risk: LOW (12%). Order telemetry shows verified urban delivery zone. Recommend auto-dispatch.",
                "model": "gemini-1.5-flash",
                "latency_ms": 142.5,
                "total_tokens": 128
            }

            r_tool = await client.post(
                "/api/v1/tools/execute",
                headers=auth_headers,
                json={
                    "tool_name": "rto_shield",
                    "prompt": "Order value ₹3,850, PIN 110025, COD order"
                }
            )
            assert r_tool.status_code == 200, f"Tool execution failed: {r_tool.text}"
            res_json = r_tool.json()
            assert res_json["status"] == "success"
            assert "RTO Risk: LOW" in res_json["result"]
            print(f"[7/7] Autonomous Engine /tools/execute PASS: Received inference response.")

    print("\n>>> ALL DASHBOARD INTEGRATION CHECKS PASSED WITH 100% SUCCESS! <<<")


if __name__ == "__main__":
    asyncio.run(run_dashboard_integration_test())
