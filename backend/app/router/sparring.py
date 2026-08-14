from fastapi import APIRouter, Depends

from app.dependencies import get_current_user
from app.schema import SparringForm, SparringResponse, SparringTurn
from app.sparring import fill_all, step

# OpenAI を呼ぶのでログイン必須。デモログインでも通る
router = APIRouter(prefix="/api/sparring", tags=["sparring"], dependencies=[Depends(get_current_user)])


@router.post("/step")
async def sparring_step(turn: SparringTurn) -> SparringResponse:
    """壁打ちを1往復進める。

    Args:
        turn: いま分かっている内容と, 直前の質問への返答。

    Returns:
        更新後の内容と次に聞くこと。
    """
    return await step(turn.draft, turn.reply)


@router.post("/fill")
async def sparring_fill(form: SparringForm) -> SparringResponse:
    """フォームの答えをまとめて反映する。粗くて読み取れなかった項目だけ聞き直す。

    Args:
        form: いま分かっている内容と, スロットごとの答え。

    Returns:
        更新後の内容と, あれば聞き直す質問。
    """
    return await step(await fill_all(form.draft, form.answers), "")
