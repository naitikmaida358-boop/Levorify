from fastapi import APIRouter
from app.api.v1.endpoints import auth, keys, tools

api_router = APIRouter()

# Authentication & User Management
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication & Identity"])

# BYOK (Bring Your Own Key) Credentials Management
api_router.include_router(keys.router, prefix="/keys", tags=["BYOK AI Key Vault"])

# Sovereign D2C AI Tools Execution
api_router.include_router(tools.router, prefix="/tools", tags=["D2C Commerce AI Tools"])
