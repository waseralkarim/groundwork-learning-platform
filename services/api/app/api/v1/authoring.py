"""Authoring: see the state of the curriculum without a terminal.

Every topic in this platform was written by editing YAML and Markdown in a
checkout and running `python -m app.content.cli lint` in a container. That works
and it means an author needs a clone, Docker, and the CLI before they can find
out whether what they wrote is valid.

This module closes the *feedback* half of that gap without touching the
authoring half, and the distinction is deliberate.

**Content stays in files.** These endpoints read the content tree and report on
it. None of them writes content. A UI that wrote curriculum into the database
would destroy the two properties the content model exists for — it would be
unversioned, and it would bypass the linter, the lab walker and code review. The
edit loop remains: change a file, look here, see what the linter says.

**`require_admin` finally does something.** The role has existed since accounts
were added and was enforced on no endpoint, which made it a claim rather than a
control. Every route here is admin-only, and there is a test asserting a
non-admin gets 403.

**Ingest is the one mutation, and it is safe to repeat.** Content keys are
deterministic UUIDv5, so ingesting the same tree twice produces the same rows.
It refuses to run at all when the content is invalid, which is the same
guarantee the CLI gives — the database can never contain content that would not
pass a lint.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import AdminUser, Db, verify_origin
from app.content.cli import _git_sha
from app.content.ingest import ingest
from app.content.linter import lint
from app.content.loader import ContentTree, LoadedTopic, load_content
from app.core.config import get_settings

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/authoring", tags=["authoring"])
protected = APIRouter(
    prefix="/authoring",
    tags=["authoring"],
    dependencies=[Depends(verify_origin)],
)


def _load() -> ContentTree:
    return load_content(Path(get_settings().content_dir))


# The Definition of Done, as the linter applies it. Kept as data rather than
# duplicated logic so that a rule change shows up here too — if these fall out
# of step with `linter.check_done`, the test that compares them fails.
REQUIRED = ("lessons", "quiz", "assessment", "labs")
RECOMMENDED = ("exercises", "interview")


def _done_state(topic: LoadedTopic) -> dict[str, Any]:
    """What a topic has, what it is missing, and whether that blocks a build.

    Draft topics are exempt from the whole checklist, exactly as the linter
    exempts them — a draft is allowed to be incomplete, which is what draft
    means.
    """
    present = {
        "lessons": len(topic.lessons),
        "labs": len(topic.labs),
        "troubleshooting": len(topic.troubleshooting),
        "quiz": len(topic.quiz.questions) if topic.quiz else 0,
        "exercises": len(topic.exercises.exercises) if topic.exercises else 0,
        "interview": len(topic.interview.questions) if topic.interview else 0,
        "assessment": len(topic.assessment.parts) if topic.assessment else 0,
    }

    if topic.topic.status == "draft":
        return {"present": present, "missing": [], "warnings": [], "blocking": False}

    missing = [name for name in REQUIRED if not present[name]]
    warnings = [name for name in RECOMMENDED if not present[name]]

    # Troubleshooting becomes required once a topic claims L3 or above, because
    # that is the level at which diagnosis is the skill being taught.
    advanced = sorted({"L3", "L4", "L5"} & {lv.value for lv in topic.topic.levels})
    if advanced and not present["troubleshooting"]:
        missing.append("troubleshooting")

    return {
        "present": present,
        "missing": missing,
        "warnings": warnings,
        "blocking": bool(missing),
    }


@router.get("/inventory")
async def inventory(_: AdminUser) -> dict[str, Any]:
    """The whole curriculum, with each topic's Definition-of-Done state.

    This is the view that does not exist anywhere else. `lint` tells you what is
    wrong; this tells you what is *there*, which is the question an author
    actually has when picking up work.
    """
    tree = _load()

    courses = []
    for course in tree.courses:
        modules = []
        for module in course.modules:
            topics = []
            for topic in module.topics:
                topics.append(
                    {
                        "id": topic.topic.id,
                        "slug": topic.topic.slug,
                        "title": topic.topic.title,
                        "status": topic.topic.status,
                        "levels": [lv.value for lv in topic.topic.levels],
                        "objectives": len(topic.topic.objectives),
                        "done": _done_state(topic),
                    }
                )
            modules.append(
                {
                    "id": module.module.id,
                    "slug": module.module.slug,
                    "title": module.module.title,
                    "order": module.module.order,
                    "topics": topics,
                }
            )
        courses.append(
            {
                "id": course.course.id,
                "code": course.course.code,
                "slug": course.course.slug,
                "title": course.course.title,
                "order": course.course.order,
                "modules": modules,
            }
        )

    courses.sort(key=lambda c: c["order"])
    all_topics = tree.all_topics()

    return {
        "courses": courses,
        "projects": [
            {"id": p.id, "slug": p.slug, "title": p.title, "level": p.level.value}
            for p in tree.projects
        ],
        "totals": {
            "courses": len(tree.courses),
            "modules": sum(len(c.modules) for c in tree.courses),
            "topics": len(all_topics),
            "lessons": sum(len(t.lessons) for t in all_topics),
            "labs": sum(len(t.labs) for t in all_topics),
            "projects": len(tree.projects),
            "incomplete": sum(1 for t in all_topics if _done_state(t)["blocking"]),
        },
    }


@router.get("/lint")
async def lint_content(_: AdminUser) -> dict[str, Any]:
    """Run the same checks the CLI runs, and return them as data.

    Parse errors are separated from lint findings because they mean different
    things: a parse error is a file that could not be read at all, so everything
    that references it will also be reported as missing. Reading them in that
    order saves chasing symptoms.
    """
    tree = _load()
    findings = lint(tree)

    errors = [f for f in findings if f.severity == "error"]
    warnings = [f for f in findings if f.severity == "warning"]

    return {
        "ok": not tree.errors and not errors,
        "parse_errors": [
            {"where": str(e.path), "message": e.message} for e in tree.errors
        ],
        "errors": [
            {"rule": f.rule, "where": f.where, "message": f.message} for f in errors
        ],
        "warnings": [
            {"rule": f.rule, "where": f.where, "message": f.message} for f in warnings
        ],
        "counts": {
            "parse_errors": len(tree.errors),
            "errors": len(errors),
            "warnings": len(warnings),
        },
    }


@protected.post("/ingest", status_code=status.HTTP_200_OK)
async def ingest_content(user: AdminUser, db: Db) -> dict[str, Any]:
    """Re-read the content tree into the database.

    Refuses on invalid content, so this endpoint cannot put the platform into a
    state the CLI would not have allowed. Idempotent by construction: content
    keys are deterministic UUIDv5 over the content id, so the same tree ingests
    to the same rows however many times it runs.
    """
    root = Path(get_settings().content_dir)
    tree = _load()
    findings = lint(tree)
    blocking = [f for f in findings if f.severity == "error"]

    if tree.errors or blocking:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={
                "message": "Refusing to ingest invalid content",
                "parse_errors": len(tree.errors),
                "errors": len(blocking),
            },
        )

    # `ingest` commits internally — it has to, because it writes a content
    # version row that later steps reference.
    result = await ingest(db, tree, _git_sha(root))

    log.info("content_ingested_via_api", actor=user.email, summary=result.summary())
    return {"summary": result.summary(), "version_id": result.version_id}
