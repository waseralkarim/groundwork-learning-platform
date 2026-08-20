"""Internal service-to-service endpoints.

**Not reachable from a browser.** `infra/caddy/Caddyfile` returns 404 for
`/api/v1/internal/*` before the request reaches this service, and
`scripts/assert-no-privileged.sh` asserts that rule is still there. Defence in
depth: even if the edge rule were removed, nothing here is useful without also
being on the internal network.

This exists for exactly one reason: the lab broker needs a step's verification
checks, and the learner must not have them. Serving them on the public lab
endpoint would put the answer key in the browser, which is the failure this
whole design is arranged to avoid.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import Db
from app.models.curriculum import Lab, Topic

router = APIRouter(prefix="/internal", tags=["internal"], include_in_schema=False)


@router.get("/topics/{topic_slug}/labs/{lab_slug}/steps/{step_id}/checks")
async def step_checks(topic_slug: str, lab_slug: str, step_id: str, db: Db) -> list[dict]:
    topic_id = await db.scalar(select(Topic.id).where(Topic.slug == topic_slug))
    if topic_id is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="topic not found")

    lab = await db.scalar(select(Lab).where(Lab.topic_id == topic_id, Lab.slug == lab_slug))
    if lab is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="lab not found")

    for step in lab.spec.get("steps", []):
        if step.get("id") == step_id:
            return step.get("verify", [])

    raise HTTPException(status.HTTP_404_NOT_FOUND, detail="step not found")


@router.get("/topics/{topic_slug}/labs/{lab_slug}/spec")
async def lab_spec(topic_slug: str, lab_slug: str, db: Db) -> dict:
    """The full lab definition, including the solution. Broker-only."""
    topic_id = await db.scalar(select(Topic.id).where(Topic.slug == topic_slug))
    if topic_id is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="topic not found")

    lab = await db.scalar(select(Lab).where(Lab.topic_id == topic_id, Lab.slug == lab_slug))
    if lab is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="lab not found")

    return {
        "slug": lab.slug,
        "image": lab.image,
        "tier": lab.tier,
        "duration_minutes": lab.duration_minutes,
        "spec": lab.spec,
    }
