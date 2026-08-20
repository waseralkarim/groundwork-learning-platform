"""Content schema — the single source of truth for what curriculum may look like.

These Pydantic models validate every YAML file under `content/`, and JSON Schema
for editor autocomplete is *generated* from them (`task content:schemas`). There
is deliberately no hand-maintained second copy to drift out of sync.

Anything the linter enforces that cannot be expressed as a type lives in
`linter.py`; anything that can be expressed as a type lives here, because a type
error is a better error message than a lint rule.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SLUG_RE = r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
ID_RE = r"^[a-z0-9]+(?:[.-][a-z0-9]+)*$"

Slug = Annotated[str, Field(pattern=SLUG_RE, min_length=2, max_length=80)]
ContentId = Annotated[str, Field(pattern=ID_RE, min_length=3, max_length=120)]


class Level(StrEnum):
    """The difficulty ladder. See docs/architecture/01-vision-and-principles.md."""

    L1 = "L1"  # Beginner    — can explain what it is and why it exists
    L2 = "L2"  # Intermediate — can use it correctly
    L3 = "L3"  # Advanced     — can troubleshoot and automate it
    L4 = "L4"  # Expert       — can run it in production
    L5 = "L5"  # Architect    — can design with it and defend the trade-offs


class Mode(StrEnum):
    """The five learning modes."""

    EXPLAIN = "explain"
    SHOW = "show"
    DO = "do"
    BREAK = "break"
    DESIGN = "design"


# Measurable verbs only. "Understand" is not assessable and is rejected at lint
# time — this list is the enforcement mechanism for that rule.
MEASURABLE_VERBS = frozenset(
    {
        "explain",
        "describe",
        "identify",
        "list",
        "define",
        "compare",
        "distinguish",
        "classify",
        "calculate",
        "estimate",
        "predict",
        "interpret",
        # Both produce an artefact you can mark: an ordered path through a
        # mechanism, and a number taken from a real machine.
        "trace",
        "measure",
        "analyse",
        "diagnose",
        "troubleshoot",
        "configure",
        "build",
        "write",
        "automate",
        "design",
        "evaluate",
        "justify",
    }
)

BANNED_VERBS = frozenset({"understand", "know", "learn", "appreciate", "be-aware", "grasp"})


class StrictModel(BaseModel):
    """Unknown keys are errors, not silently ignored typos."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# --------------------------------------------------------------------- objectives


class Objective(StrictModel):
    id: str = Field(pattern=r"^OBJ-[A-Za-z0-9.]+$")
    level: Level
    verb: str
    statement: str = Field(min_length=15, max_length=400)
    assessed_by: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def verb_must_be_measurable(self) -> Objective:
        verb = self.verb.lower()
        if verb in BANNED_VERBS:
            raise ValueError(
                f"objective {self.id}: '{verb}' is not assessable. "
                f"Use a measurable verb: {', '.join(sorted(MEASURABLE_VERBS))}"
            )
        if verb not in MEASURABLE_VERBS:
            raise ValueError(f"objective {self.id}: '{verb}' is not in the approved verb list")
        return self


class Term(StrictModel):
    term: str = Field(min_length=2, max_length=80)
    definition: str = Field(min_length=10, max_length=600)


# ------------------------------------------------------------------------ topic


class Prerequisite(StrictModel):
    topic: ContentId
    hardness: Literal["required", "recommended"] = "required"


class Topic(StrictModel):
    id: ContentId
    slug: Slug
    title: str = Field(min_length=4, max_length=140)
    summary: str = Field(min_length=20, max_length=400)
    order: int = Field(ge=1)
    levels: list[Level] = Field(min_length=1)
    estimated_minutes: int = Field(ge=5, le=240)
    status: Literal["draft", "published", "retired"] = "published"

    prerequisites: list[Prerequisite] = Field(default_factory=list)
    objectives: list[Objective] = Field(min_length=1)
    terminology: list[Term] = Field(default_factory=list)
    tags: list[Slug] = Field(default_factory=list)

    # Forward references let a later topic call back to this one explicitly,
    # which is how the curriculum stays a web rather than a list.
    foreshadows: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def objective_ids_unique(self) -> Topic:
        seen = [o.id for o in self.objectives]
        duplicates = {i for i in seen if seen.count(i) > 1}
        if duplicates:
            raise ValueError(f"duplicate objective ids: {sorted(duplicates)}")
        return self


class Module(StrictModel):
    id: ContentId
    slug: Slug
    title: str = Field(min_length=4, max_length=140)
    summary: str = Field(min_length=20, max_length=400)
    order: int = Field(ge=1)


class Course(StrictModel):
    id: ContentId
    slug: Slug
    code: str = Field(pattern=r"^[A-H]\d{2}$")
    title: str = Field(min_length=4, max_length=140)
    summary: str = Field(min_length=20, max_length=600)
    track: str = Field(min_length=2, max_length=60)
    levels: list[Level] = Field(min_length=1)
    estimated_hours: int = Field(ge=1, le=200)
    order: int = Field(ge=1)


class PathCourse(StrictModel):
    course: ContentId
    order: int = Field(ge=1)


class LearningPath(StrictModel):
    id: ContentId
    slug: Slug
    title: str = Field(min_length=4, max_length=140)
    summary: str = Field(min_length=20, max_length=600)
    courses: list[PathCourse] = Field(min_length=1)


# ------------------------------------------------------------------------- quiz


class QuizOption(StrictModel):
    id: str = Field(pattern=r"^[a-z]$")
    text: str = Field(min_length=1, max_length=400)
    correct: bool = False
    # Why a learner might pick this and what misconception it reveals. Wrong
    # answers have to teach, otherwise the quiz is just a filter.
    note: str | None = Field(default=None, max_length=500)


class QuizQuestion(StrictModel):
    id: str = Field(pattern=r"^q\d+$")
    type: Literal["single_choice", "multi_choice", "ordering", "fill_command"]
    level: Level
    objectives: list[str] = Field(min_length=1)
    stem: str = Field(min_length=10, max_length=1200)
    options: list[QuizOption] = Field(min_length=2, max_length=8)
    explanation: str = Field(min_length=20, max_length=1500)

    @model_validator(mode="after")
    def correct_answer_count_matches_type(self) -> QuizQuestion:
        correct = [o for o in self.options if o.correct]
        if self.type == "single_choice" and len(correct) != 1:
            raise ValueError(f"{self.id}: single_choice needs exactly 1 correct option")
        if self.type == "multi_choice" and len(correct) < 2:
            raise ValueError(f"{self.id}: multi_choice needs at least 2 correct options")
        if self.type in ("ordering", "fill_command") and not correct:
            raise ValueError(f"{self.id}: needs at least 1 correct option")

        ids = [o.id for o in self.options]
        if len(set(ids)) != len(ids):
            raise ValueError(f"{self.id}: duplicate option ids")
        return self


class Quiz(StrictModel):
    id: ContentId
    topic: ContentId
    pass_score: int = Field(ge=50, le=100, default=70)
    questions: list[QuizQuestion] = Field(min_length=3)

    @model_validator(mode="after")
    def question_ids_unique(self) -> Quiz:
        ids = [q.id for q in self.questions]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate question ids")
        return self


# -------------------------------------------------------------------------- lab


class Check(StrictModel):
    """A verification step, executed inside the lab by `labcheck`.

    Closed vocabulary on purpose. Content authors describe *what* must be true;
    they never supply shell that we would then have to run somewhere.
    """

    type: Literal[
        "file_exists",
        "file_matches",
        "file_mode",
        "command_output",
        "command_exit",
        "command_ran",
        "process_running",
        "port_listening",
        "http_check",
    ]
    path: str | None = None
    pattern: str | None = None
    command: str | None = None
    equals: str | None = None
    equals_command: str | None = None
    exit_code: int | None = None
    port: int | None = None
    url: str | None = None
    status: int | None = None
    mode: str | None = None
    describe: str = Field(min_length=5, max_length=200)

    @model_validator(mode="after")
    def required_fields_per_type(self) -> Check:
        needs: dict[str, tuple[str, ...]] = {
            "file_exists": ("path",),
            "file_matches": ("path", "pattern"),
            "file_mode": ("path", "mode"),
            "command_output": ("command",),
            "command_exit": ("command", "exit_code"),
            "command_ran": ("pattern",),
            "process_running": ("pattern",),
            "port_listening": ("port",),
            "http_check": ("url",),
        }
        for field in needs[self.type]:
            if getattr(self, field) is None:
                raise ValueError(f"check type '{self.type}' requires '{field}'")

        has_comparison = self.equals or self.pattern or self.equals_command
        if self.type == "command_output" and not has_comparison:
            raise ValueError("command_output needs one of: equals, pattern, equals_command")
        if self.type == "file_matches" and self.pattern:
            try:
                re.compile(self.pattern)
            except re.error as exc:
                raise ValueError(f"invalid regex in check: {exc}") from exc
        return self


class LabStep(StrictModel):
    id: str = Field(pattern=r"^s\d+$")
    instruction: str = Field(min_length=10, max_length=1500)
    hint: str | None = Field(default=None, max_length=800)
    verify: list[Check] = Field(default_factory=list)
    # What a learner following the instruction would actually type. Not shown to
    # anyone — `scripts/walk-labs.py` runs it in a real lab container and then
    # asserts the step's own checks pass.
    #
    # This is the only way to test whether a lab *teaches*, as opposed to
    # whether it parses. Three real bugs in the first eight labs — a wrong path,
    # a demonstration that demonstrated nothing, and an instruction that needed
    # a capability the sandbox drops — all passed their checks while failing the
    # learner, and all were found by doing exactly this by hand.
    walkthrough: str | None = Field(default=None, max_length=4000)


class Lab(StrictModel):
    id: ContentId
    topic: ContentId
    title: str = Field(min_length=5, max_length=140)
    type: Literal["guided", "challenge", "troubleshooting"]
    # Isolation tier required — see docs/architecture/06-lab-architecture.md
    tier: Literal[1, 2, 3, 4]
    image: str = Field(min_length=3, max_length=120)
    duration_minutes: int = Field(ge=5, le=180)
    # Writable space, in MiB. Only set it when the lab's teaching depends on the
    # size — a lab that fills a filesystem to produce ENOSPC needs a small one,
    # because the default tmpfs is larger than the memory limit and the OOM
    # killer arrives before the filesystem is full.
    disk_mb: int | None = Field(default=None, ge=16, le=4096)
    objectives: list[str] = Field(min_length=1)
    intro: str = Field(min_length=20, max_length=2000)
    setup: list[str] = Field(default_factory=list)
    steps: list[LabStep] = Field(min_length=1)
    solution: str = Field(min_length=30)

    @model_validator(mode="after")
    def at_least_one_check(self) -> Lab:
        if not any(step.verify for step in self.steps):
            raise ValueError(f"{self.id}: a lab with no verification is not a lab")
        return self


# -------------------------------------------------------------------- exercises


class Exercise(StrictModel):
    id: str = Field(pattern=r"^e\d+$")
    title: str = Field(min_length=5, max_length=140)
    level: Level
    objectives: list[str] = Field(min_length=1)
    kind: Literal["ordering", "short_answer", "calculation", "interpretation"]
    prompt: str = Field(min_length=20)
    answer: str = Field(min_length=10)
    explanation: str = Field(min_length=20)


class ExerciseSet(StrictModel):
    topic: ContentId
    exercises: list[Exercise] = Field(min_length=1)


# --------------------------------------------------------------- troubleshooting


class Artifact(StrictModel):
    """Evidence handed to the learner. This is all they get up front."""

    type: Literal["command_output", "log", "metric", "config", "diagram"]
    label: str = Field(min_length=3, max_length=120)
    # Short output is legitimate evidence — `uname -m` returning one word can be
    # the whole diagnosis.
    content: str = Field(min_length=3)


class TroubleshootingScenario(StrictModel):
    id: ContentId
    topic: ContentId
    title: str = Field(min_length=5, max_length=160)
    level: Level
    objectives: list[str] = Field(min_length=1)
    # `progressive` means the API refuses to serve root_cause until the learner
    # has submitted a hypothesis. Handing over the answer immediately is the
    # failure mode of every troubleshooting tutorial on the internet.
    reveal_policy: Literal["progressive", "immediate"] = "progressive"
    situation: str = Field(min_length=30)
    symptoms: list[str] = Field(min_length=1)
    artifacts: list[Artifact] = Field(min_length=1)
    diagnostic_questions: list[str] = Field(min_length=1)
    hints: list[str] = Field(default_factory=list)
    root_cause: str = Field(min_length=30)
    method: str = Field(min_length=50)
    resolution: str = Field(min_length=20)


# --------------------------------------------------------------------- interview


class InterviewQuestion(StrictModel):
    id: str = Field(pattern=r"^i\d+$")
    level: Level
    question: str = Field(min_length=10)
    model_answer: str = Field(min_length=40)
    # What separates a real answer from a memorised one.
    signal: str = Field(min_length=20)
    follow_ups: list[str] = Field(default_factory=list)


class InterviewSet(StrictModel):
    topic: ContentId
    questions: list[InterviewQuestion] = Field(min_length=1)


# -------------------------------------------------------------------- assessment


class AssessmentPart(StrictModel):
    id: str = Field(pattern=r"^[A-Z]$")
    title: str = Field(min_length=5, max_length=140)
    kind: Literal["explain", "diagnose", "reason", "practical"]
    objectives: list[str] = Field(min_length=1)
    prompt: str = Field(min_length=30)
    rubric: list[str] = Field(min_length=2)
    model_answer: str = Field(min_length=50)
    common_failures: list[str] = Field(default_factory=list)


class Assessment(StrictModel):
    id: ContentId
    topic: ContentId
    pass_score: int = Field(ge=50, le=100, default=70)
    parts: list[AssessmentPart] = Field(min_length=1)


# ------------------------------------------------------------------- projects


class RubricCriterion(StrictModel):
    """One thing a project is judged on.

    `evidence` is what makes self-review worth doing: the learner has to point
    at something in their own work, not just award themselves a number. A rubric
    without it collects opinions.
    """

    id: str = Field(pattern=r"^r\d+$")
    criterion: str = Field(min_length=10, max_length=300)
    # What a strong answer looks like. Written so a learner can mark themselves
    # honestly without a reviewer present.
    excellent: str = Field(min_length=20, max_length=600)
    adequate: str = Field(min_length=20, max_length=600)
    inadequate: str = Field(min_length=20, max_length=600)
    evidence: str = Field(
        min_length=10,
        max_length=300,
        description="What the learner must point at to justify their score",
    )
    weight: int = Field(default=1, ge=1, le=5)


class Project(StrictModel):
    """A piece of work that spans topics.

    Deliberately not nested under a course: a project's whole purpose is to make
    a learner combine things they met separately, so it references the topics it
    requires rather than living inside one of them.

    There is no automated grading here and there is not going to be. What a
    project produces — a repository, a running system, a written design — cannot
    be checked by the platform, and pretending otherwise would be worse than
    admitting it. The rubric is a structure for honest self-review, and the
    honesty is the learner's contribution.
    """

    id: ContentId
    slug: Slug
    title: str = Field(min_length=5, max_length=140)
    level: Level
    # Topics whose objectives this project exercises. The API refuses to serve
    # the brief until they are complete, for the same reason prerequisites gate
    # a topic: attempting this early teaches frustration, not the subject.
    requires_topics: list[ContentId] = Field(min_length=1)
    estimated_hours: int = Field(ge=1, le=40)
    summary: str = Field(min_length=20, max_length=400)
    brief: str = Field(min_length=100)
    # Constraints are what make it a project rather than a tutorial: they remove
    # the option of solving it the way the lessons did.
    constraints: list[str] = Field(default_factory=list)
    deliverables: list[str] = Field(min_length=1)
    rubric: list[RubricCriterion] = Field(min_length=2)
    # Deliberately last in the file and last in the learner's process: things
    # worth doing after the work is finished, not instead of finishing it.
    going_further: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def rubric_ids_unique(self) -> Project:
        ids = [criterion.id for criterion in self.rubric]
        if len(set(ids)) != len(ids):
            raise ValueError(f"{self.id}: duplicate rubric criterion ids")
        return self


# ------------------------------------------------------------------------ lesson


class LessonFrontmatter(StrictModel):
    topic: ContentId
    section: str = Field(pattern=SLUG_RE)
    title: str = Field(min_length=4, max_length=160)
    order: int = Field(ge=1)
    mode: Mode = Mode.EXPLAIN
