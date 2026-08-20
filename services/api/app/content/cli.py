"""Content CLI.

    python -m app.content.cli lint       # parse + validate + lint, no database
    python -m app.content.cli ingest     # lint, then write to the database
    python -m app.content.cli schemas    # emit JSON Schema for editor support
    python -m app.content.cli new        # scaffold a topic

`lint` needs no database, which is what lets it run as the fast pre-commit gate
and in CI without spinning up Postgres.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
from pathlib import Path

from app.content.ingest import ingest
from app.content.linter import format_report, lint
from app.content.loader import load_content
from app.core.config import get_settings


def _git_sha(root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        return result.stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def _check(root: Path) -> tuple[bool, str, object]:
    tree = load_content(root)
    parse_errors = [str(e) for e in tree.errors]
    findings = lint(tree)
    report = format_report(parse_errors, findings, root)
    fatal = bool(parse_errors) or any(f.severity == "error" for f in findings)
    return not fatal, report, tree


def cmd_lint(args: argparse.Namespace) -> int:
    ok, report, _ = _check(Path(args.root))
    print(report)
    return 0 if ok else 1


def cmd_ingest(args: argparse.Namespace) -> int:
    root = Path(args.root)
    ok, report, tree = _check(root)
    print(report)
    if not ok:
        print("\nRefusing to ingest invalid content.", file=sys.stderr)
        return 1

    async def run() -> None:
        from app.db.session import dispose_engine, get_sessionmaker

        async with get_sessionmaker()() as session:
            result = await ingest(session, tree, _git_sha(root))
            print(f"\nIngested: {result.summary()}")
            print(f"Content version: {result.version_id}")
        await dispose_engine()

    asyncio.run(run())
    return 0


def cmd_schemas(args: argparse.Namespace) -> int:
    """Emit JSON Schema so editors can autocomplete and validate YAML inline."""
    from app.content import schema as s

    models = {
        "course": s.Course,
        "module": s.Module,
        "topic": s.Topic,
        "quiz": s.Quiz,
        "lab": s.Lab,
        "exercises": s.ExerciseSet,
        "troubleshooting": s.TroubleshootingScenario,
        "interview": s.InterviewSet,
        "assessment": s.Assessment,
        "path": s.LearningPath,
    }

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for name, model in models.items():
        target = out / f"{name}.schema.json"
        target.write_text(
            json.dumps(model.model_json_schema(), indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"wrote {target}")
    return 0


def cmd_new(args: argparse.Namespace) -> int:
    root = Path(args.root)
    topic_dir = root / "courses" / args.course / "modules" / args.module / "topics" / args.topic
    if topic_dir.exists():
        print(f"{topic_dir} already exists", file=sys.stderr)
        return 1

    (topic_dir / "lessons").mkdir(parents=True)
    (topic_dir / "labs").mkdir()
    (topic_dir / "troubleshooting").mkdir()
    print(f"Scaffolded {topic_dir}")
    print("Next: write topic.yaml, then lessons/, then labs/, then quiz.yaml.")
    print("Run `python -m app.content.cli lint` early and often.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="content", description="Groundwork content pipeline")
    parser.add_argument("--root", default=get_settings().content_dir, help="content directory")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("lint", help="validate and lint content").set_defaults(func=cmd_lint)
    sub.add_parser("ingest", help="lint, then load into the database").set_defaults(func=cmd_ingest)

    schemas = sub.add_parser("schemas", help="emit JSON Schema")
    schemas.add_argument("--out", default="/content/schemas")
    schemas.set_defaults(func=cmd_schemas)

    new = sub.add_parser("new", help="scaffold a topic directory")
    new.add_argument("--course", required=True)
    new.add_argument("--module", required=True)
    new.add_argument("--topic", required=True)
    new.set_defaults(func=cmd_new)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
