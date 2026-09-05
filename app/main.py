import logging
import time
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from app.api.v1.api import api_router
from app.core.config import settings
from app.core.database import engine, init_db

# Configure enterprise structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
)
logger = logging.getLogger("levorify.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan context manager: handles pre-flight migrations and teardown.
    """
    logger.info("Initializing Levorify Sovereign Engine...")
    await init_db()
    logger.info("Levorify backend initialized and listening for requests.")
    yield
    logger.info("Gracefully shutting down Levorify backend connections...")
    await engine.dispose()
    logger.info("Engine pool successfully closed.")


# FastAPI Application Instance
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=(
        "Sovereign 20-in-1 D2C Commerce SaaS Infrastructure. "
        "Engineered with asynchronous high-throughput endpoints, encrypted BYOK "
        "(Bring Your Own Key) zero-cost AI tool routing, and enterprise JWT security."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

# Cross-Origin Resource Sharing (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Latency Observability & Enterprise Security Headers Middleware
@app.middleware("http")
async def security_and_observability_middleware(request: Request, call_next):
    start_time = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception as exc:
        logger.exception(f"Unhandled server exception during request {request.method} {request.url.path}: {exc}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal sovereign server error. Incident logged to secure telemetry."}
        )
    process_time = (time.perf_counter() - start_time) * 1000
    response.headers["X-Process-Time-Ms"] = f"{process_time:.2f}"
    
    # Enterprise Security Headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    
    # Cache-Busting Headers for Web/Mobile Browsers
    if request.url.path in ("/", "/dashboard", "/landing") or "text/html" in response.headers.get("content-type", ""):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    
    return response


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INDEX_PATH = os.path.join(BASE_DIR, "index.html")
DASHBOARD_PATH = os.path.join(BASE_DIR, "dashboard.html")
NO_CACHE_HEADERS = {
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0"
}


# Root, Landing, and Dashboard Probes
@app.get("/", tags=["Sovereign Interface"])
async def root(request: Request):
    """
    Root entrypoint: Renders landing page for web browsers or JSON metadata for API clients.
    """
    accept_header = request.headers.get("accept", "")
    if "text/html" in accept_header and os.path.exists(INDEX_PATH):
        return FileResponse(INDEX_PATH, media_type="text/html", headers=NO_CACHE_HEADERS)

    return {
        "platform": "Levorify Sovereign D2C Platform",
        "domain": "levorify.com",
        "status": "operational",
        "version": settings.VERSION,
        "docs": "/docs",
        "dashboard": "/dashboard",
        "api_v1": settings.API_V1_STR
    }


@app.get("/dashboard", response_class=HTMLResponse, tags=["Sovereign Interface"])
async def dashboard():
    """
    Sovereign Merchant Operating System Console (BYOK Vault + Tool Dispatch).
    """
    if os.path.exists(DASHBOARD_PATH):
        return FileResponse(DASHBOARD_PATH, media_type="text/html", headers=NO_CACHE_HEADERS)
    return HTMLResponse("<h3>Dashboard file not found.</h3>", status_code=404)


@app.get("/landing", response_class=HTMLResponse, tags=["Sovereign Interface"])
async def landing():
    """
    Sovereign D2C Platform Landing Experience.
    """
    if os.path.exists(INDEX_PATH):
        return FileResponse(INDEX_PATH, media_type="text/html", headers=NO_CACHE_HEADERS)
    return HTMLResponse("<h3>Landing page file not found.</h3>", status_code=404)


@app.get("/health", tags=["System Status"])
async def health_check():
    """Liveness and health monitoring probe."""
    return {
        "status": "healthy",
        "database_target": "postgresql" if "postgresql" in settings.DATABASE_URL else "sqlite",
        "byok_engine": "active"
    }


# Mount API V1 Router
app.include_router(api_router, prefix=settings.API_V1_STR)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
