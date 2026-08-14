from fastapi import APIRouter, Depends

from app.dependencies import get_current_user
from app.hearing import step
from app.schema import HearingResponse, HearingTurn

# OpenAI を呼ぶのでログイン必須。デモログインでも通る
router = APIRouter(prefix="/api/hearing", tags=["hearing"], dependencies=[Depends(get_current_user)])


@router.post("/step")
async def hearing_step(turn: HearingTurn) -> HearingResponse:
    """聞き取りを1往復進める。

    Args:
        turn: ここまでの往復と, 直前の質問への返答。

    Returns:
        更新後の履歴, 次に聞くこと, ここまでの候補。
    """
    return await step(turn.history, turn.answer)
