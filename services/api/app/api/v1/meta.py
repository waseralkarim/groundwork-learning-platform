"""Platform metadata.

Phase 0's proof that the whole chain works: browser -> proxy -> web -> api ->
postgres, with a real query at the end of it.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.db.session import get_session
from app.models.content import ContentVersion

router = APIRouter(prefix="/meta", tags=["meta"])


class PlatformInfo(BaseModel):
    name: str
    environment: str
    api_version: str
    content_versions_ingested: int
    database: str


@router.get("", response_model=PlatformInfo)
async def platform_info(
    session: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> PlatformInfo:
    count = await session.scalar(select(func.count()).select_from(ContentVersion))
    version = await session.scalar(select(func.version()))
    return PlatformInfo(
        name=settings.project_name,
        environment=settings.groundwork_env,
        api_version="v1",
        content_versions_ingested=count or 0,
        database=(version or "unknown").split(" on ")[0],
    )
