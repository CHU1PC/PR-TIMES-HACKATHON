from fastapi import APIRouter

from app.schema import SparringResponse, SparringTurn
from app.sparring import step

router = APIRouter(prefix="/api/sparring", tags=["sparring"])


@router.post("/step")
async def sparring_step(turn: SparringTurn) -> SparringResponse:
    """壁打ちを1往復進める。

    Args:
        turn: いま分かっている内容と, 直前の質問への返答。

    Returns:
        更新後の内容と次に聞くこと。
    """
    return await step(turn.draft, turn.reply)
