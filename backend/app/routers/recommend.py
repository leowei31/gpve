"""POST /api/recommend — free-form vibe in, 5 ranked recommendations out (REQ-002)."""
from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from app.pipeline.recommend import VibeResponse, recommend

router = APIRouter()


class VibeRequest(BaseModel):
    vibe: str = Field(min_length=1, max_length=500, description="The free-form vibe to match.")


@router.post("/recommend", response_model=VibeResponse)
async def post_recommend(body: VibeRequest, request: Request) -> VibeResponse:
    s = request.app.state
    return await recommend(
        pool=s.pool, gemini=s.gemini, reputation=s.reputation, vibe=body.vibe,
        w_vibe=s.settings.w_vibe, w_metrics=s.settings.w_metrics, w_web=s.settings.w_web,
    )
