"""Content linter.

Everything a JSON Schema cannot express. These rules are the enforcement
mechanism for the Definition of Done — without them, a 700-topic curriculum
drifts into inconsistency and nobody notices until a learner hits the gap.

Every rule states what it protects against, because a lint rule whose purpose is
not obvious eventually gets disabled by someone in a hurry.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from app.content.loader import ContentTree, LoadedTopic

# :::name{key=value key2="value 2"}
DIRECTIVE_RE = re.compile(r"^:::(?P<name>[a-z-]+)(?:\{(?P<attrs>[^}]*)\})?\s*$", re.MULTILINE)
FENCE_RE = re.compile(r"^```(?P<lang>[a-zA-Z0-9+-]*)", re.MULTILINE)
MD_LINK_RE = re.compile(r"\[[^\]]*\]\((?P<target>[^)]+)\)")
# Site routes the content may link to: /topics/<slug> and /learn/<slug>/<step>.
TOPIC_LINK_RE = re.compile(r"^/(?:topics|learn)/(?P<slug>[a-z0-9-]+)")

# The closed directive vocabulary. Adding one is a deliberate two-sided change:
# this set, plus a renderer component in services/web/src/content.
ALLOWED_DIRECTIVES = frozenset(
    {
        "objective",
        "terminal",
        "warning",
        "note",
        "diagram",
        "quiz",
        "lab",
        "aside",
        "callback",
        "checkpoint",
        # Interactive. `try` opens a real shell inline; `predict` makes the
        # learner commit an answer before the prose gives one away.
        "try",
        "predict",
        # Emitted by the loader when it inlines a diagram, not hand-authored.
        "caption",
    }
)

SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"

# DFS colours for the prerequisite cycle check.
_UNVISITED, _IN_PROGRESS, _DONE = 0, 1, 2


@dataclass
class Finding:
    rule: str
    severity: str
    where: str
    message: str

    def __str__(self) -> str:
        marker = "ERROR" if self.severity == SEVERITY_ERROR else "warn "
        return f"  {marker}  [{self.rule}] {self.where}: {self.message}"


class Linter:
    def __init__(self, tree: ContentTree) -> None:
        self.tree = tree
        self.findings: list[Finding] = []

    def _error(self, rule: str, where: str, message: str) -> None:
        self.findings.append(Finding(rule, SEVERITY_ERROR, where, message))

    def _warn(self, rule: str, where: str, message: str) -> None:
        self.findings.append(Finding(rule, SEVERITY_WARNING, where, message))

    @property
    def error_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == SEVERITY_ERROR)

    def run(self) -> list[Finding]:
        self.findings = []
        topics = self.tree.all_topics()

        self.check_unique_ids(topics)
        self.check_prerequisites_resolve_and_are_acyclic(topics)
        self.check_paths_reference_real_courses()
        self.check_projects_reference_real_topics()
        self.check_every_topic_is_reachable(topics)

        for topic in topics:
            self.check_objectives_are_assessed(topic)
            self.check_assessables_reference_objectives(topic)
            self.check_required_artifacts_present(topic)
            self.check_lessons(topic)
            self.check_quiz_quality(topic)
            self.check_labs(topic)

        self.check_glossary_coverage(topics)
        return self.findings

    # ------------------------------------------------------------ structural

    def check_unique_ids(self, topics: list[LoadedTopic]) -> None:
        """Two pieces of content sharing an id would silently overwrite each other."""
        seen: dict[str, str] = {}
        for course in self.tree.courses:
            for scope, cid in [("course", course.course.id)]:
                if cid in seen:
                    self._error("unique-id", cid, f"duplicate {scope} id (also {seen[cid]})")
                seen[cid] = scope
            for module in course.modules:
                if module.module.id in seen:
                    self._error("unique-id", module.module.id, "duplicate module id")
                seen[module.module.id] = "module"
        for topic in topics:
            if topic.topic.id in seen:
                self._error("unique-id", topic.topic.id, "duplicate topic id")
            seen[topic.topic.id] = "topic"

    def check_prerequisites_resolve_and_are_acyclic(self, topics: list[LoadedTopic]) -> None:
        """A cycle makes the curriculum order uncomputable and the UI unusable."""
        known = {t.topic.id for t in topics}
        graph: dict[str, list[str]] = {}

        for topic in topics:
            deps = []
            for prerequisite in topic.topic.prerequisites:
                if prerequisite.topic not in known:
                    self._error(
                        "prereq-resolves",
                        topic.topic.id,
                        f"prerequisite '{prerequisite.topic}' does not exist",
                    )
                    continue
                if prerequisite.topic == topic.topic.id:
                    self._error("prereq-acyclic", topic.topic.id, "topic is its own prerequisite")
                    continue
                deps.append(prerequisite.topic)
            graph[topic.topic.id] = deps

        # Standard three-colour DFS: unvisited / on the current path / finished.
        # Meeting a node that is on the current path is exactly a cycle.
        colour = dict.fromkeys(graph, _UNVISITED)

        def visit(node: str, trail: list[str]) -> None:
            colour[node] = _IN_PROGRESS
            for neighbour in graph.get(node, []):
                if colour.get(neighbour) == _IN_PROGRESS:
                    cycle = " -> ".join([*trail, node, neighbour])
                    self._error("prereq-acyclic", node, f"prerequisite cycle: {cycle}")
                elif colour.get(neighbour) == _UNVISITED:
                    visit(neighbour, [*trail, node])
            colour[node] = _DONE

        for node in graph:
            if colour[node] == _UNVISITED:
                visit(node, [])

    def check_projects_reference_real_topics(self) -> None:
        """A project gated on a topic that does not exist can never unlock.

        Nothing else would catch it: the project loads, the API serves it, and
        it simply stays locked for everyone forever — which looks like a
        deliberate gate rather than a typo.
        """
        known = {t.topic.id for t in self.tree.all_topics()}
        for project in self.tree.projects:
            for topic_id in project.requires_topics:
                if topic_id not in known:
                    self._error(
                        "project-requires",
                        project.id,
                        f"requires unknown topic '{topic_id}' — this project can never unlock",
                    )

    def check_paths_reference_real_courses(self) -> None:
        known = {c.course.id for c in self.tree.courses}
        for path in self.tree.paths:
            for entry in path.courses:
                if entry.course not in known:
                    self._error(
                        "path-resolves", path.id, f"references unknown course '{entry.course}'"
                    )

    def check_every_topic_is_reachable(self, topics: list[LoadedTopic]) -> None:
        """Orphan content is content nobody will ever be shown."""
        if not self.tree.paths:
            return
        reachable_courses = {e.course for p in self.tree.paths for e in p.courses}
        for course in self.tree.courses:
            if course.course.id not in reachable_courses:
                self._warn(
                    "reachable",
                    course.course.id,
                    "course is not in any learning path — no learner will reach it",
                )

    # -------------------------------------------------------------- pedagogy

    def check_objectives_are_assessed(self, topic: LoadedTopic) -> None:
        """An objective with no assessment is a promise the platform cannot keep."""
        available = self._assessable_ids(topic)

        for objective in topic.topic.objectives:
            if not objective.assessed_by:
                self._error(
                    "objective-assessed", topic.topic.id, f"{objective.id} assesses nothing"
                )
                continue
            for reference in objective.assessed_by:
                if reference not in available:
                    self._error(
                        "objective-assessed",
                        topic.topic.id,
                        f"{objective.id} references '{reference}', which does not exist "
                        f"(available: {', '.join(sorted(available)) or 'none'})",
                    )

    def check_assessables_reference_objectives(self, topic: LoadedTopic) -> None:
        """Assessment that maps to no objective is busywork."""
        objective_ids = {o.id for o in topic.topic.objectives}

        def verify(owner: str, referenced: list[str]) -> None:
            for objective_id in referenced:
                if objective_id not in objective_ids:
                    self._error(
                        "assessable-mapped",
                        topic.topic.id,
                        f"{owner} references unknown objective '{objective_id}'",
                    )

        if topic.quiz:
            for question in topic.quiz.questions:
                verify(f"quiz.{question.id}", question.objectives)
        for lab in topic.labs:
            verify(f"lab {lab.id}", lab.objectives)
        if topic.exercises:
            for exercise in topic.exercises.exercises:
                verify(f"exercise.{exercise.id}", exercise.objectives)
        for scenario in topic.troubleshooting:
            verify(f"scenario {scenario.id}", scenario.objectives)
        if topic.assessment:
            for part in topic.assessment.parts:
                verify(f"assessment.{part.id}", part.objectives)

    def check_required_artifacts_present(self, topic: LoadedTopic) -> None:
        """The Definition of Done, expressed as code."""
        where = topic.topic.id
        if topic.topic.status == "draft":
            return

        if not topic.lessons:
            self._error("done-lesson", where, "no lesson content")
        if not topic.quiz:
            self._error("done-quiz", where, "no quiz")
        if not topic.assessment:
            self._error("done-assessment", where, "no assessment")
        if not topic.labs:
            self._error("done-lab", where, "no lab")
        if not topic.exercises:
            self._warn("done-exercises", where, "no exercises")
        if not topic.interview:
            self._warn("done-interview", where, "no interview questions")

        # Troubleshooting is required once a topic claims L3 or above: that is
        # the level at which diagnosis becomes the actual skill being taught.
        advanced = {"L3", "L4", "L5"} & {level.value for level in topic.topic.levels}
        if advanced and not topic.troubleshooting:
            self._error(
                "done-troubleshooting",
                where,
                f"declares {sorted(advanced)} but has no troubleshooting scenario",
            )

    # ---------------------------------------------------------------- lessons

    def check_lessons(self, topic: LoadedTopic) -> None:
        known_topic_slugs = {t.topic.slug for t in self.tree.all_topics()}
        for lesson in topic.lessons:
            where = f"{topic.topic.id}/{lesson.frontmatter.section}"

            if lesson.frontmatter.topic != topic.topic.id:
                self._error(
                    "lesson-topic",
                    where,
                    f"frontmatter topic '{lesson.frontmatter.topic}' does not match "
                    f"its directory ({topic.topic.id})",
                )

            for match in DIRECTIVE_RE.finditer(lesson.body):
                name = match.group("name")
                if name not in ALLOWED_DIRECTIVES:
                    self._error(
                        "directive-known",
                        where,
                        f"unknown directive ':::{name}' "
                        f"(allowed: {', '.join(sorted(ALLOWED_DIRECTIVES))})",
                    )

            # An unlabelled code block cannot be syntax-highlighted and cannot be
            # tested. Both matter for a platform whose content is mostly commands.
            #
            # Fences alternate open/close, and only the opening one carries a
            # language — checking every fence would flag every closing ``` as an
            # error, which is how this rule was wrong the first time.
            for index, match in enumerate(FENCE_RE.finditer(lesson.body)):
                is_opening = index % 2 == 0
                if is_opening and not match.group("lang"):
                    line = lesson.body[: match.start()].count("\n") + 1
                    self._error(
                        "code-language", where, f"code block at line {line} has no language"
                    )

            for match in MD_LINK_RE.finditer(lesson.body):
                target = match.group("target")
                if target.startswith(("http://", "https://", "#", "mailto:")):
                    continue

                if target.startswith("/"):
                    # A site route, not a file. Cross-topic links are how the
                    # curriculum stays a web rather than a list, so they are
                    # checked against the topics that actually exist.
                    topic_link = TOPIC_LINK_RE.match(target)
                    if topic_link and topic_link.group("slug") not in known_topic_slugs:
                        self._error(
                            "link-resolves",
                            where,
                            f"link to '{target}' — no topic with that slug exists",
                        )
                    continue

                if lesson.source is None:
                    continue
                resolved = (lesson.source.parent / target.split("#")[0]).resolve()
                if not resolved.exists():
                    self._error("link-resolves", where, f"broken relative link '{target}'")

            objective_ids = {o.id for o in topic.topic.objectives}
            lab_slugs = {lab.id.removeprefix("lab.") for lab in topic.labs}

            for match in DIRECTIVE_RE.finditer(lesson.body):
                name = match.group("name")
                attrs = match.group("attrs") or ""

                if name == "objective":
                    found = re.search(r"id=([A-Za-z0-9.\-]+)", attrs)
                    if found and found.group(1) not in objective_ids:
                        self._error(
                            "directive-objective",
                            where,
                            f":::objective references unknown '{found.group(1)}'",
                        )

                elif name == "try":
                    # The shell borrows a lab's image, seed and isolation tier,
                    # so a `:::try` naming a lab that does not exist renders a
                    # button that fails only when a learner presses it.
                    found = re.search(r"lab=\"?([a-z0-9-]+)\"?", attrs)
                    if not found:
                        self._error(
                            "directive-try",
                            where,
                            ":::try needs lab=<slug> — it has no image to run without one",
                        )
                    elif found.group(1) not in lab_slugs:
                        self._error(
                            "directive-try",
                            where,
                            f":::try references lab '{found.group(1)}', which is not in this topic "
                            f"(has: {', '.join(sorted(lab_slugs)) or 'none'})",
                        )

                elif name == "predict" and "question=" not in attrs:
                    self._warn(
                        "directive-predict",
                        where,
                        ":::predict has no question= — there is nothing to predict",
                    )

    # ------------------------------------------------------------------ quiz

    def check_quiz_quality(self, topic: LoadedTopic) -> None:
        quiz = topic.quiz
        if not quiz:
            return
        where = quiz.id

        if quiz.topic != topic.topic.id:
            self._error("quiz-topic", where, f"quiz.topic '{quiz.topic}' does not match directory")

        # A quiz that only tests recall certifies nothing. Require spread across
        # the levels the topic actually claims to teach.
        claimed = {level.value for level in topic.topic.levels}
        present = {question.level.value for question in quiz.questions}
        missing = claimed - present
        if missing:
            self._warn(
                "quiz-level-spread",
                where,
                f"topic claims {sorted(claimed)} but the quiz has no {sorted(missing)} questions",
            )

        # Every objective should be reachable through the quiz OR another
        # assessable; that is checked elsewhere. Here we catch the narrower
        # failure of a quiz whose questions all target one objective.
        targeted = {o for question in quiz.questions for o in question.objectives}
        if len(topic.topic.objectives) > 2 and len(targeted) < 2:
            self._warn("quiz-coverage", where, "every question targets the same objective")

        for question in quiz.questions:
            # Ordering questions have no distractors — every option is correct,
            # only the sequence is wrong — so the rule does not apply to them.
            if question.type == "ordering":
                continue
            # Distractors that teach nothing waste the most valuable moment in
            # the whole platform: the instant a learner discovers they are wrong.
            annotated = sum(1 for option in question.options if option.note)
            if annotated == 0:
                self._warn(
                    "quiz-distractors",
                    f"{where}.{question.id}",
                    "no option carries a note explaining the misconception it targets",
                )

    # ------------------------------------------------------------------- labs

    def check_labs(self, topic: LoadedTopic) -> None:
        for lab in topic.labs:
            where = lab.id
            if lab.topic != topic.topic.id:
                self._error("lab-topic", where, f"lab.topic '{lab.topic}' does not match directory")

            # A lab with checks but no walkthrough cannot be machine-walked, so
            # nothing proves its instructions actually produce a passing step.
            unwalkable = [step.id for step in lab.steps if step.verify and not step.walkthrough]
            if unwalkable:
                self._warn(
                    "lab-walkthrough",
                    where,
                    f"steps with checks but no walkthrough (untestable): {', '.join(unwalkable)}",
                )

            unverified = [step.id for step in lab.steps if not step.verify]
            if unverified and lab.type == "guided":
                self._warn(
                    "lab-verification",
                    where,
                    f"guided lab has unverified steps: {', '.join(unverified)}",
                )

            # A challenge lab that hands out hints on every step is a guided lab
            # wearing a costume.
            if lab.type == "challenge":
                hinted = sum(1 for step in lab.steps if step.hint)
                if hinted == len(lab.steps) and len(lab.steps) > 1:
                    self._warn(
                        "lab-challenge",
                        where,
                        "every step has a hint — this is a guided lab labelled as a challenge",
                    )

    # -------------------------------------------------------------- glossary

    def check_glossary_coverage(self, topics: list[LoadedTopic]) -> None:
        """Terminology must be defined before it is leaned on.

        Warning rather than error: full first-use detection needs the reading
        order, which arrives with the path ordering work. This catches the
        common case of a topic defining nothing at all while using bold jargon.
        """
        for topic in topics:
            if topic.topic.terminology:
                continue
            if not topic.lessons:
                continue
            body = "\n".join(lesson.body for lesson in topic.lessons)
            if len(body) > 2000:
                self._warn(
                    "glossary",
                    topic.topic.id,
                    "substantial lesson content but no terminology defined",
                )

    # ------------------------------------------------------------------ util

    @staticmethod
    def _assessable_ids(topic: LoadedTopic) -> set[str]:
        available: set[str] = set()
        if topic.quiz:
            available.update(f"quiz.{q.id}" for q in topic.quiz.questions)
        if topic.exercises:
            available.update(f"exercise.{e.id}" for e in topic.exercises.exercises)
        if topic.assessment:
            available.update(f"assessment.{p.id}" for p in topic.assessment.parts)
        available.update(f"lab.{lab.id.rsplit('.', 1)[-1]}" for lab in topic.labs)
        available.update(
            f"troubleshooting.{s.id.rsplit('.', 1)[-1]}" for s in topic.troubleshooting
        )
        return available


def lint(tree: ContentTree) -> list[Finding]:
    return Linter(tree).run()


def format_report(errors: list[str], findings: list[Finding], root: Path) -> str:
    lines = [f"Content check: {root}", ""]

    if errors:
        lines.append(f"Parse/schema errors ({len(errors)}):")
        lines.extend(f"  ERROR  {e}" for e in errors)
        lines.append("")

    if findings:
        error_findings = [f for f in findings if f.severity == SEVERITY_ERROR]
        warnings = [f for f in findings if f.severity == SEVERITY_WARNING]
        if error_findings:
            lines.append(f"Lint errors ({len(error_findings)}):")
            lines.extend(str(f) for f in error_findings)
            lines.append("")
        if warnings:
            lines.append(f"Warnings ({len(warnings)}):")
            lines.extend(str(f) for f in warnings)
            lines.append("")

    total_errors = len(errors) + sum(1 for f in findings if f.severity == SEVERITY_ERROR)
    lines.append("FAILED" if total_errors else "All content checks passed.")
    return "\n".join(lines)
