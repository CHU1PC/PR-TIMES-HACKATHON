from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.router import api_router
from app.settings import STATIC_DIR, settings

app = FastAPI(
    title="未来のPRネタを作り出すAI",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(api_router)

# 本番は Vite のビルド成果物を同一オリジンで配信する。開発時は dist が無いので何もしない
if STATIC_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str) -> FileResponse:
        """API 以外は index.html を返す。クライアント側でルーティングする。

        Args:
            path: リクエストされたパス。

        Returns:
            実在するファイル, または index.html。
        """
        target = STATIC_DIR / path
        if path and target.is_file():
            return FileResponse(target)
        return FileResponse(STATIC_DIR / "index.html")
