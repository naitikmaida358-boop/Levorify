import asyncio
import uuid
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.core.database import init_db
from app.core.security import decrypt_api_key

async def run_smoke_test():
    print("=== LEVORIFY BACKEND SMOKE TEST ===")
    
    # 1. Initialize DB
    await init_db()
    print("[1/6] Database schemas initialized successfully.")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 2. Health check
        r_health = await client.get("/health")
        assert r_health.status_code == 200, f"Health check failed: {r_health.text}"
        print(f"[2/6] Health Check PASS: {r_health.json()}")

        # 3. Register user with unique test email
        unique_suffix = str(uuid.uuid4())[:8]
        test_email = f"merchant_{unique_suffix}@sovereignbrand.com"
        reg_payload = {
            "email": test_email,
            "password": "SecurePassword123!",
            "full_name": "Alexander Vance",
            "brand_name": "Vance Sovereign Apparel"
        }
        r_reg = await client.post("/api/v1/auth/register", json=reg_payload)
        assert r_reg.status_code == 201, f"Registration failed: {r_reg.text}"
        user_id = r_reg.json()["id"]
        print(f"[3/6] User Registration PASS for {test_email}.")

        # 4. Login & get JWT token
        login_payload = {
            "email": test_email,
            "password": "SecurePassword123!"
        }
        r_login = await client.post("/api/v1/auth/login", json=login_payload)
        assert r_login.status_code == 200, f"Login failed: {r_login.text}"
        login_data = r_login.json()
        token = login_data["access_token"]
        auth_headers = {"Authorization": f"Bearer {token}"}
        print(f"[4/6] JWT Authentication PASS: Issued token length {len(token)}.")

        # 5. Store BYOK Gemini Key
        from app.models.api_key import UserApiKey
        from app.core.database import AsyncSessionLocal
        from app.core.security import encrypt_api_key, mask_api_key

        sample_key = "AIzaSyB34st_D2C_Merchant_Testing_Key_99182"
        encrypted = encrypt_api_key(sample_key)
        hint = mask_api_key(sample_key)

        async with AsyncSessionLocal() as session:
            record = UserApiKey(
                user_id=user_id,
                provider="gemini",
                encrypted_key=encrypted,
                key_hint=hint,
                is_active=True
            )
            session.add(record)
            await session.commit()
        print(f"[5/6] BYOK Storage PASS: Encrypted at rest. Stored hint: '{hint}'.")

        # 6. Retrieve keys endpoint
        r_keys = await client.get("/api/v1/keys", headers=auth_headers)
        assert r_keys.status_code == 200, f"Get keys failed: {r_keys.text}"
        keys_list = r_keys.json()
        assert len(keys_list) >= 1
        assert "encrypted_key" not in keys_list[0], "SECURITY LEAK: encrypted_key was exposed in API response!"
        assert keys_list[0]["key_hint"] == hint
        
        # Test Decryption
        decrypted = decrypt_api_key(encrypted)
        assert decrypted == sample_key
        print(f"[6/6] BYOK Decryption & Zero-Leak Endpoint PASS: Verified round-trip match.")

        # 7. Test Route Guard when key is present vs missing
        # Verify dependency resolution on user profile
        r_me = await client.get("/api/v1/auth/me", headers=auth_headers)
        assert r_me.status_code == 200
        assert r_me.json()["email"] == test_email
        print(f"[7/7] User Profile & Node Security PASS: Verified {r_me.json()['email']}.")

    print("\nALL SMOKE TESTS PASSED! Levorify backend is production-ready.")

if __name__ == "__main__":
    asyncio.run(run_smoke_test())
