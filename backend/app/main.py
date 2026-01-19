from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.api.auth_routes import router as auth_router, admin_router
from app.core.settings import settings

app = FastAPI(title=settings.app_name, version=settings.version)

# CORS 中间件必须在添加路由之前配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(auth_router)
app.include_router(admin_router)


@app.on_event("startup")
async def startup_event():
    """Initialize database and ensure admin user exists."""
    from app.services.auth import ensure_admin_exists
    ensure_admin_exists()
