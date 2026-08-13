from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.router import api_router
from app.settings import settings

app = FastAPI(
    title="未来のPRネタを作り出すAI",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

# フロントは S3 に置き CloudFront が同一オリジンに束ねるので, 本番では CORS を通らない。
# 開発時だけ Vite (5173) から直接叩くため許可する
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(api_router)
