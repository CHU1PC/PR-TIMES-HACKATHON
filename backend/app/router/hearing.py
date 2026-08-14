from fastapi import APIRouter

from app.hearing import step
from app.schema import HearingResponse, HearingTurn

router = APIRouter(prefix="/api/hearing", tags=["hearing"])


@router.post("/step")
async def hearing_step(turn: HearingTurn) -> HearingResponse:
    """聞き取りを1往復進める。

    Args:
        turn: ここまでの往復と, 直前の質問への返答。

    Returns:
        更新後の履歴, 次に聞くこと, ここまでの候補。
    """
    return await step(turn.history, turn.answer)
