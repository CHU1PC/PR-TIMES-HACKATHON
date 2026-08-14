from fastapi import APIRouter, Depends

from app.dependencies import get_current_user
from app.proposal import propose
from app.schema.proposal import ProposalRequest, ProposalResponse

# OpenAI を呼ぶのでログイン必須。デモログインでも通る
router = APIRouter(prefix="/api/proposal", tags=["proposal"], dependencies=[Depends(get_current_user)])


@router.post("")
async def proposal(request: ProposalRequest) -> ProposalResponse:
    """壁打ちが済んだ予定に対し, 事例を引いて足せる行動を提案する。

    Args:
        request: 壁打ちで埋めたイベント内容。

    Returns:
        提案3件と, 根拠にした事例。
    """
    return await propose(request.draft)
