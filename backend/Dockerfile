# syntax=docker/dockerfile:1

# =============================================================================
# Stage 1: フロントエンドのビルド
# =============================================================================
# frontend/ は backend/ の外にあるので, compose の additional_contexts で `frontend`
# という名前のコンテキストとして渡す (リポジトリ全体を context にすると data/ の
# DuckDB 700MB 超まで転送されるため)
FROM oven/bun:1.3-slim AS frontend-builder

WORKDIR /build

# 依存だけ先に入れてレイヤをキャッシュする. src の変更で install をやり直さない
COPY --from=frontend package.json bun.lock ./
RUN bun install --frozen-lockfile

COPY --from=frontend . .

# vite と tsc は devDependencies にあるため build には全依存が要る.
# node_modules はこのステージに閉じ, runtime へは dist だけを持ち込む
RUN bun run build

# =============================================================================
# Stage 2: Python 依存のビルド
# =============================================================================
FROM python:3.13-slim-bookworm AS python-builder

COPY --from=ghcr.io/astral-sh/uv:0.11.14 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app/backend

COPY pyproject.toml uv.lock ./

# dev/etl/test グループを全て外す. etl の duckdb は数百MB あり API は使わない
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-default-groups

# =============================================================================
# Stage 3: Runtime
# =============================================================================
FROM python:3.13-slim-bookworm AS runtime

COPY --from=ghcr.io/astral-sh/uv:0.11.14 /uv /uvx /bin/

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# HEALTHCHECK 用. これ以外に実行時の OS パッケージは要らない
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --shell /bin/bash appuser

# app/settings/paths.py の ROOT は parents[3]. /app をリポジトリ相当に置くことで
# STATIC_DIR が /app/frontend/dist に解決される
WORKDIR /app/backend

COPY --chown=appuser:appuser pyproject.toml uv.lock ./
COPY --chown=appuser:appuser --from=python-builder /app/backend/.venv ./.venv
COPY --chown=appuser:appuser app/ ./app/
COPY --chown=appuser:appuser --from=frontend-builder /build/dist /app/frontend/dist

USER appuser

# 80 は EC2 で pgAdmin が使用中. 本アプリは 8080 に載せる
EXPOSE 8080

# start-period は uv の起動 + import (langchain) を待つ余裕
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8080/api/health || exit 1

CMD ["uv", "run", "--no-sync", "fastapi", "run", "app/main.py", "--host", "0.0.0.0", "--port", "8080"]
