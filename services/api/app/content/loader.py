"""Loads the content tree from disk into validated objects.

Knows the directory layout; knows nothing about the database. Parse errors are
collected rather than raised so one bad file does not hide the other nine.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TypeVar

import yaml
from pydantic import BaseModel, ValidationError

from app.content.schema import (
    Assessment,
    Course,
    ExerciseSet,
    Lab,
    LearningPath,
    LessonFrontmatter,
    Module,
    Project,
    Quiz,
    Topic,
    TroubleshootingScenario,
)

M = TypeVar("M", bound=BaseModel)

FRONTMATTER_DELIMITER = "---"

# :::diagram{src=./foo.mmd caption="..."} — resolved at load time, not render time.
DIAGRAM_RE = re.compile(r"^:::diagram(?:\{(?P<attrs>[^}]*)\})?\s*$", re.MULTILINE)


@dataclass
class ContentError:
    path: Path
    message: str

    def __str__(self) -> str:
        return f"{self.path}: {self.message}"


@dataclass
class Lesson:
    frontmatter: LessonFrontmatter
    body: str
    source: Path


@dataclass
class LoadedTopic:
    topic: Topic
    module_id: str
    lessons: list[Lesson] = field(default_factory=list)
    labs: list[Lab] = field(default_factory=list)
    quiz: Quiz | None = None
    exercises: ExerciseSet | None = None
    troubleshooting: list[TroubleshootingScenario] = field(default_factory=list)
    interview: Any = None
    assessment: Assessment | None = None
    source: Path | None = None


@dataclass
class LoadedModule:
    module: Module
    course_id: str
    topics: list[LoadedTopic] = field(default_factory=list)


@dataclass
class LoadedCourse:
    course: Course
    modules: list[LoadedModule] = field(default_factory=list)


@dataclass
class ContentTree:
    paths: list[LearningPath] = field(default_factory=list)
    courses: list[LoadedCourse] = field(default_factory=list)
    projects: list[Project] = field(default_factory=list)
    errors: list[ContentError] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def all_topics(self) -> list[LoadedTopic]:
        return [t for c in self.courses for m in c.modules for t in m.topics]


def split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Split `---\\nyaml\\n---\\nbody` into its two halves."""
    if not text.lstrip().startswith(FRONTMATTER_DELIMITER):
        raise ValueError("file has no YAML frontmatter block")

    stripped = text.lstrip()
    parts = stripped.split(FRONTMATTER_DELIMITER, 2)
    if len(parts) < 3:
        raise ValueError("frontmatter block is not terminated by a second '---'")

    data = yaml.safe_load(parts[1]) or {}
    if not isinstance(data, dict):
        raise ValueError("frontmatter must be a mapping")
    return data, parts[2].lstrip("\n")


class ContentLoader:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.errors: list[ContentError] = []

    # ---------------------------------------------------------------- helpers

    def _read_yaml(self, path: Path, model: type[M]) -> M | None:
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            self.errors.append(ContentError(path, f"invalid YAML: {exc}"))
            return None
        except OSError as exc:
            self.errors.append(ContentError(path, f"unreadable: {exc}"))
            return None

        if raw is None:
            self.errors.append(ContentError(path, "file is empty"))
            return None

        try:
            return model.model_validate(raw)
        except ValidationError as exc:
            for error in exc.errors():
                location = ".".join(str(p) for p in error["loc"]) or "(root)"
                self.errors.append(ContentError(path, f"{location}: {error['msg']}"))
            return None

    def _read_yaml_dir(self, directory: Path, model: type[M]) -> list[M]:
        if not directory.is_dir():
            return []
        loaded: list[M] = []
        for path in sorted(directory.glob("*.yaml")):
            item = self._read_yaml(path, model)
            if item is not None:
                loaded.append(item)
        return loaded

    def _inline_diagrams(self, body: str, source: Path) -> str:
        """Replace `:::diagram{src=... caption=...}` with the diagram's source.

        Diagrams live in their own `.mmd` files so they are reviewable in a pull
        request and reusable across topics. The frontend should not have to make
        a second request per diagram to render a page, so they are inlined here,
        once, at load time.
        """

        def replace(match: re.Match[str]) -> str:
            attrs = match.group("attrs") or ""
            src_match = re.search(r"src=([^\s}]+)", attrs)
            caption_match = re.search(r'caption="([^"]*)"', attrs)
            if not src_match:
                self.errors.append(ContentError(source, ":::diagram is missing src="))
                return match.group(0)

            diagram_path = (source.parent / src_match.group(1)).resolve()
            try:
                diagram = diagram_path.read_text(encoding="utf-8").strip()
            except OSError:
                self.errors.append(
                    ContentError(source, f":::diagram src not found: {src_match.group(1)}")
                )
                return match.group(0)

            caption = caption_match.group(1) if caption_match else ""
            fence = f"```mermaid\n{diagram}\n```"
            return f"{fence}\n\n:::caption\n{caption}\n:::" if caption else fence

        return DIAGRAM_RE.sub(replace, body)

    def _read_lessons(self, directory: Path) -> list[Lesson]:
        if not directory.is_dir():
            return []
        lessons: list[Lesson] = []
        for path in sorted(directory.glob("*.md")):
            try:
                data, body = split_frontmatter(path.read_text(encoding="utf-8"))
            except (ValueError, OSError) as exc:
                self.errors.append(ContentError(path, str(exc)))
                continue

            try:
                frontmatter = LessonFrontmatter.model_validate(data)
            except ValidationError as exc:
                for error in exc.errors():
                    location = ".".join(str(p) for p in error["loc"]) or "(root)"
                    self.errors.append(
                        ContentError(path, f"frontmatter {location}: {error['msg']}")
                    )
                continue

            if not body.strip():
                self.errors.append(ContentError(path, "lesson body is empty"))
                continue

            body = self._inline_diagrams(body, path)
            lessons.append(Lesson(frontmatter=frontmatter, body=body, source=path))

        return sorted(lessons, key=lambda item: item.frontmatter.order)

    # ------------------------------------------------------------------- load

    def load(self) -> ContentTree:
        self.errors = []
        tree = ContentTree()

        if not self.root.is_dir():
            self.errors.append(ContentError(self.root, "content directory does not exist"))
            tree.errors = self.errors
            return tree

        tree.paths = self._read_yaml_dir(self.root / "paths", LearningPath)
        # Projects sit beside courses rather than inside one: a project exists to
        # make a learner combine things they met separately.
        tree.projects = self._read_yaml_dir(self.root / "projects", Project)

        courses_dir = self.root / "courses"
        if courses_dir.is_dir():
            for course_dir in sorted(p for p in courses_dir.iterdir() if p.is_dir()):
                loaded = self._load_course(course_dir)
                if loaded is not None:
                    tree.courses.append(loaded)

        tree.errors = self.errors
        return tree

    def _load_course(self, course_dir: Path) -> LoadedCourse | None:
        course = self._read_yaml(course_dir / "course.yaml", Course)
        if course is None:
            return None

        loaded = LoadedCourse(course=course)
        modules_dir = course_dir / "modules"
        if modules_dir.is_dir():
            for module_dir in sorted(p for p in modules_dir.iterdir() if p.is_dir()):
                module = self._load_module(module_dir, course.id)
                if module is not None:
                    loaded.modules.append(module)

        loaded.modules.sort(key=lambda m: m.module.order)
        return loaded

    def _load_module(self, module_dir: Path, course_id: str) -> LoadedModule | None:
        module = self._read_yaml(module_dir / "module.yaml", Module)
        if module is None:
            return None

        loaded = LoadedModule(module=module, course_id=course_id)
        topics_dir = module_dir / "topics"
        if topics_dir.is_dir():
            for topic_dir in sorted(p for p in topics_dir.iterdir() if p.is_dir()):
                topic = self._load_topic(topic_dir, module.id)
                if topic is not None:
                    loaded.topics.append(topic)

        loaded.topics.sort(key=lambda t: t.topic.order)
        return loaded

    def _load_topic(self, topic_dir: Path, module_id: str) -> LoadedTopic | None:
        from app.content.schema import InterviewSet

        topic = self._read_yaml(topic_dir / "topic.yaml", Topic)
        if topic is None:
            return None

        loaded = LoadedTopic(topic=topic, module_id=module_id, source=topic_dir)
        loaded.lessons = self._read_lessons(topic_dir / "lessons")
        loaded.labs = self._read_yaml_dir(topic_dir / "labs", Lab)
        loaded.troubleshooting = self._read_yaml_dir(
            topic_dir / "troubleshooting", TroubleshootingScenario
        )

        optional: list[tuple[str, type[BaseModel], str]] = [
            ("quiz.yaml", Quiz, "quiz"),
            ("exercises.yaml", ExerciseSet, "exercises"),
            ("interview.yaml", InterviewSet, "interview"),
            ("assessment.yaml", Assessment, "assessment"),
        ]
        for filename, model, attribute in optional:
            path = topic_dir / filename
            if path.is_file():
                setattr(loaded, attribute, self._read_yaml(path, model))

        return loaded


def load_content(root: Path | str) -> ContentTree:
    return ContentLoader(Path(root)).load()
