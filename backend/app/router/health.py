from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
def health() -> dict[str, bool]:
    """疎通確認。DB にも LLM にも触らない。

    Returns:
        {"ok": True}。到達性の確認だけに使う。
    """
    return {"ok": True}
