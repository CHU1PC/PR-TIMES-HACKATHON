from fastapi import APIRouter

from app.proposal import propose
from app.schema.proposal import ProposalRequest, ProposalResponse

router = APIRouter(prefix="/api/proposal", tags=["proposal"])


@router.post("")
async def proposal(request: ProposalRequest) -> ProposalResponse:
    """壁打ちが済んだ予定に対し, 事例を引いて足せる行動を提案する。

    Args:
        request: 壁打ちで埋めたイベント内容。

    Returns:
        提案3件と, 根拠にした事例。
    """
    return await propose(request.draft)
