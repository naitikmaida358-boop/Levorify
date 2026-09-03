# Levorify Sovereign D2C Platform — Backend Engine

> **Domain:** [levorify.com](https://levorify.com)  
> **Role:** Sovereign 20-in-1 Direct-to-Consumer (D2C) Commerce Platform Backend  
> **Tech Stack:** FastAPI (Async), SQLAlchemy 2.0 (Async), PostgreSQL / SQLite, JWT, BYOK Fernet Vault, Google Gemini REST Engine

---

## 1. Architectural Highlights

1. **Modular Architecture**:
   - `app/core/`: Configuration via Pydantic `BaseSettings`, asymmetric/symmetric security routines, and async database engine.
   - `app/models/`: SQLAlchemy 2.0 modern declarative models (`User`, `UserApiKey`, `ToolExecutionLog`).
   - `app/schemas/`: Robust Pydantic v2 schemas for request validation, responses, and token management.
   - `app/services/`: High-performance asynchronous AI service dispatching directly to Google Gemini.
   - `app/api/v1/`: Versioned modular route endpoints (`/auth`, `/keys`, `/tools`).

2. **Bring Your Own Key (BYOK) Zero-Server-Cost Architecture**:
   - Merchants configure their own free or paid Google Gemini API key via `POST /api/v1/keys`.
   - Keys are **symmetrically encrypted at rest** using **Fernet (AES-128-CBC + HMAC-SHA256)** via cluster secret `BYOK_ENCRYPTION_KEY`.
   - Raw keys are **never stored in plaintext** and **never returned over the wire** (only masked hints like `AIza...9xQ` are exposed).
   - Tool execution endpoints dynamically fetch, decrypt, and inject the merchant's key at runtime, ensuring **$0 LLM inference cost** for Levorify's server infrastructure.

3. **Database Dual-Mode Flexibility**:
   - Pre-configured for high-concurrency production PostgreSQL via `asyncpg`.
   - Built-in zero-config developer fallback to `sqlite+aiosqlite` so you can test immediately without waiting for a PostgreSQL container.

---

## 2. Getting Started

### Step 1: Create and Activate a Virtual Environment

```bash
cd C:\Users\natik\.gemini\antigravity-ide\scratch\levorify
python -m venv venv

# Windows PowerShell:
.\venv\Scripts\Activate.ps1

# Or Windows Command Prompt:
.\venv\Scripts\activate.bat
```

### Step 2: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 3: Configure Environment Variables

```bash
copy .env.example .env
```

### Step 4: Run the Development Server

```bash
uvicorn app.main:app --reload --port 8000
```

Once running:
- **Sovereign Merchant OS Dashboard**: [http://localhost:8000/dashboard](http://localhost:8000/dashboard)
- **Sovereign Landing Experience**: [http://localhost:8000/](http://localhost:8000/) or [http://localhost:8000/landing](http://localhost:8000/landing)
- **Interactive OpenAPI Documentation (Swagger UI)**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc Documentation**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **Health Check Probe**: [http://localhost:8000/health](http://localhost:8000/health)

---

## 3. Endpoints Overview

| Method | Path | Description | Auth Required |
| :--- | :--- | :--- | :--- |
| `GET`  | `/dashboard` | Sovereign Merchant OS Console Frontend | No |
| `GET`  | `/landing` / `/` | Sovereign D2C Platform Landing Page | No |
| `POST` | `/api/v1/auth/register` | Register new D2C merchant node | No |
| `POST` | `/api/v1/auth/token` | Standard OAuth2 Form Login (used by Dashboard) | No |
| `POST` | `/api/v1/auth/login` | JSON-based authentication | No |
| `GET`  | `/api/v1/auth/me` | Fetch authenticated merchant node profile | Yes (Bearer) |
| `POST` | `/api/v1/keys/configure` | Dashboard endpoint to link & encrypt BYOK key | Yes (Bearer) |
| `GET`  | `/api/v1/keys/status` | Telemetry probe for active BYOK key | Yes (Bearer) |
| `POST` | `/api/v1/keys` | Standard REST link/update encrypted Gemini key | Yes (Bearer) |
| `GET`  | `/api/v1/keys` | List linked API keys (safely masked) | Yes (Bearer) |
| `DELETE`| `/api/v1/keys/{provider}` | Revoke linked key | Yes (Bearer) |
| `POST` | `/api/v1/keys/verify` | Live verification probe of Gemini key | Yes (Bearer) |
| `POST` | `/api/v1/tools/execute` | Unified autonomous engine dispatch (RTO, Bundling, Scout, etc.) | Yes (Bearer + BYOK) |
| `POST` | `/api/v1/tools/product-description` | Generate high-converting D2C product copy | Yes (Bearer + BYOK) |
| `POST` | `/api/v1/tools/ad-copy` | Generate high-ROAS multi-platform ad angles | Yes (Bearer + BYOK) |
| `GET`  | `/api/v1/tools/history` | Audit log of past AI tool executions | Yes (Bearer) |

