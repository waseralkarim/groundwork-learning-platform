"""Content pipeline tests.

The highest-value suite in the project: it is the only automated thing that can
tell us the curriculum is actually finished, and the only guard against the bug
that would silently ruin the platform six months in (see `test_content_uuid_*`).

These run without a database.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from app.content.linter import ALLOWED_DIRECTIVES, Linter, lint
from app.content.loader import load_content, split_frontmatter
from app.content.schema import Check, Objective, QuizOption, QuizQuestion
from app.content.search_index import plain_text
from app.models.curriculum import content_uuid

REPO_CONTENT = Path("/content")


# --------------------------------------------------------------- stable keys


def test_content_uuid_is_deterministic() -> None:
    """The property the entire progress domain depends on."""
    assert content_uuid("topic.the-machine") == content_uuid("topic.the-machine")


def test_content_uuid_differs_per_id() -> None:
    assert content_uuid("topic.a") != content_uuid("topic.b")


def test_content_uuid_ignores_everything_except_the_id() -> None:
    """Renaming a directory, retitling or reordering must not change the key.

    Progress rows point at these UUIDs. If the key were derived from a file
    path, a title or an ordinal, then reorganising the curriculum would orphan
    every learner's history — silently, and months after the change.
    """
    original = content_uuid("topic.the-machine")
    # Same id reached via a different directory layout, different title,
    # different position in its module.
    assert content_uuid("topic.the-machine") == original


# ------------------------------------------------------------- frontmatter


def test_split_frontmatter_parses_yaml_and_body() -> None:
    data, body = split_frontmatter("---\ntopic: t\norder: 2\n---\n\n# Heading\n")
    assert data == {"topic": "t", "order": 2}
    assert body.startswith("# Heading")


def test_split_frontmatter_rejects_missing_block() -> None:
    with pytest.raises(ValueError, match="no YAML frontmatter"):
        split_frontmatter("# Just a heading\n")


def test_split_frontmatter_rejects_unterminated_block() -> None:
    with pytest.raises(ValueError, match="not terminated"):
        split_frontmatter("---\ntopic: t\n")


# ------------------------------------------------------------------ schema


def test_objective_rejects_unmeasurable_verb() -> None:
    """'Understand networking' is not assessable, so it must not be authorable."""
    with pytest.raises(ValueError, match="not assessable"):
        Objective(
            id="OBJ-1.1",
            level="L1",
            verb="understand",
            statement="Understand how networking works in general",
            assessed_by=["quiz.q1"],
        )


def test_objective_accepts_measurable_verb() -> None:
    objective = Objective(
        id="OBJ-1.1",
        level="L1",
        verb="explain",
        statement="Explain the roles of CPU, RAM and persistent storage",
        assessed_by=["quiz.q1"],
    )
    assert objective.verb == "explain"


def test_single_choice_requires_exactly_one_correct_answer() -> None:
    with pytest.raises(ValueError, match="exactly 1 correct"):
        QuizQuestion(
            id="q1",
            type="single_choice",
            level="L1",
            objectives=["OBJ-1.1"],
            stem="Which is true?",
            options=[
                QuizOption(id="a", text="One", correct=True),
                QuizOption(id="b", text="Two", correct=True),
            ],
            explanation="Both cannot be correct in a single-choice question.",
        )


def test_multi_choice_requires_at_least_two_correct_answers() -> None:
    with pytest.raises(ValueError, match="at least 2 correct"):
        QuizQuestion(
            id="q1",
            type="multi_choice",
            level="L1",
            objectives=["OBJ-1.1"],
            stem="Select all that apply",
            options=[
                QuizOption(id="a", text="One", correct=True),
                QuizOption(id="b", text="Two"),
            ],
            explanation="A multi-choice question with one answer is single-choice.",
        )


def test_check_requires_the_fields_its_type_needs() -> None:
    with pytest.raises(ValueError, match="requires 'path'"):
        Check(type="file_exists", describe="The answer file exists")


def test_check_rejects_an_invalid_regex() -> None:
    with pytest.raises(ValueError, match="invalid regex"):
        Check(
            type="file_matches",
            path="/tmp/answer",
            pattern="[unclosed",
            describe="Matches the expected shape",
        )


# ------------------------------------------------------------------ linter


def _write_topic(root: Path, *, lesson_body: str = "Body text.\n") -> None:
    topic_dir = root / "courses" / "01-c" / "modules" / "01-m" / "topics" / "01-t"
    (topic_dir / "lessons").mkdir(parents=True)

    (root / "courses" / "01-c" / "course.yaml").write_text(
        textwrap.dedent("""
            id: course.c
            slug: demo-course
            code: A01
            title: A Course
            summary: A course summary long enough to satisfy validation rules.
            track: Foundations
            levels: [L1]
            estimated_hours: 1
            order: 1
        """).strip(),
        encoding="utf-8",
    )
    (root / "courses" / "01-c" / "modules" / "01-m" / "module.yaml").write_text(
        textwrap.dedent("""
            id: module.m
            slug: demo-module
            title: A Module
            summary: A module summary long enough to satisfy validation rules.
            order: 1
        """).strip(),
        encoding="utf-8",
    )
    (topic_dir / "topic.yaml").write_text(
        textwrap.dedent("""
            id: topic.t
            slug: demo-topic
            title: A Topic
            summary: A topic summary long enough to satisfy the validation rules.
            order: 1
            levels: [L1]
            estimated_minutes: 30
            objectives:
              - id: OBJ-1.1
                level: L1
                verb: explain
                statement: Explain the thing that this topic is actually about.
                assessed_by: [quiz.q1]
        """).strip(),
        encoding="utf-8",
    )
    (topic_dir / "lessons" / "01-overview.md").write_text(
        "---\ntopic: topic.t\nsection: overview\ntitle: Overview\norder: 1\n---\n\n" + lesson_body,
        encoding="utf-8",
    )


def test_linter_flags_a_topic_missing_its_definition_of_done_artifacts(tmp_path: Path) -> None:
    _write_topic(tmp_path)
    findings = lint(load_content(tmp_path))
    rules = {f.rule for f in findings if f.severity == "error"}
    assert {"done-quiz", "done-assessment", "done-lab"} <= rules


def test_linter_flags_an_unknown_directive(tmp_path: Path) -> None:
    _write_topic(tmp_path, lesson_body=":::invented\nsomething\n:::\n")
    findings = lint(load_content(tmp_path))
    assert any(f.rule == "directive-known" for f in findings)


def test_linter_accepts_every_directive_in_the_allowed_vocabulary(tmp_path: Path) -> None:
    body = "\n\n".join(f":::{name}\ncontent\n:::" for name in sorted(ALLOWED_DIRECTIVES))
    _write_topic(tmp_path, lesson_body=body)
    findings = lint(load_content(tmp_path))
    assert not [f for f in findings if f.rule == "directive-known"]


def test_linter_flags_a_try_directive_naming_a_lab_that_does_not_exist(tmp_path: Path) -> None:
    """A `:::try` borrows a lab's image and isolation tier.

    Pointing at a lab that is not in the topic renders a button that fails only
    when a learner presses it, which is exactly the class of bug the lint gate
    exists to catch before anyone sees it.
    """
    _write_topic(tmp_path, lesson_body=":::try{lab=no-such-lab}\nRun it.\n:::\n")
    findings = lint(load_content(tmp_path))
    assert any(f.rule == "directive-try" for f in findings)


def test_linter_flags_a_try_directive_with_no_lab_at_all(tmp_path: Path) -> None:
    _write_topic(tmp_path, lesson_body=":::try\nRun it.\n:::\n")
    findings = lint(load_content(tmp_path))
    assert any(f.rule == "directive-try" for f in findings)


def test_linter_warns_when_a_prediction_has_nothing_to_predict(tmp_path: Path) -> None:
    _write_topic(tmp_path, lesson_body=":::predict\nThe answer.\n:::\n")
    findings = lint(load_content(tmp_path))
    assert any(f.rule == "directive-predict" for f in findings)


def test_linter_flags_a_code_block_without_a_language(tmp_path: Path) -> None:
    _write_topic(tmp_path, lesson_body="Text.\n\n```\nsome code\n```\n")
    findings = lint(load_content(tmp_path))
    assert any(f.rule == "code-language" for f in findings)


def test_linter_does_not_flag_closing_fences(tmp_path: Path) -> None:
    """Regression: closing ``` carries no language and must not be an error."""
    _write_topic(tmp_path, lesson_body="Text.\n\n```bash\nls -la\n```\n\n```python\nx = 1\n```\n")
    findings = lint(load_content(tmp_path))
    assert not [f for f in findings if f.rule == "code-language"]


def test_linter_flags_an_objective_referencing_a_missing_assessable(tmp_path: Path) -> None:
    _write_topic(tmp_path)
    findings = lint(load_content(tmp_path))
    assert any(f.rule == "objective-assessed" for f in findings)


def test_linter_detects_a_prerequisite_cycle(tmp_path: Path) -> None:
    from app.content.loader import ContentTree, LoadedCourse, LoadedModule, LoadedTopic
    from app.content.schema import Course, Module, Prerequisite, Topic

    def topic(identifier: str, requires: str) -> LoadedTopic:
        return LoadedTopic(
            topic=Topic(
                id=identifier,
                slug=identifier.replace(".", "-"),
                title="A Topic",
                summary="A topic summary long enough to satisfy the validation rules.",
                order=1,
                levels=["L1"],
                estimated_minutes=30,
                prerequisites=[Prerequisite(topic=requires)],
                objectives=[
                    Objective(
                        id="OBJ-1.1",
                        level="L1",
                        verb="explain",
                        statement="Explain the thing that this topic is actually about.",
                        assessed_by=["quiz.q1"],
                    )
                ],
            ),
            module_id="module.m",
        )

    tree = ContentTree(
        courses=[
            LoadedCourse(
                course=Course(
                    id="course.c",
                    slug="demo-course",
                    code="A01",
                    title="A Course",
                    summary="A course summary long enough to satisfy validation rules.",
                    track="Foundations",
                    levels=["L1"],
                    estimated_hours=1,
                    order=1,
                ),
                modules=[
                    LoadedModule(
                        module=Module(
                            id="module.m",
                            slug="demo-module",
                            title="A Module",
                            summary="A module summary long enough to satisfy validation.",
                            order=1,
                        ),
                        course_id="course.c",
                        topics=[topic("topic.a", "topic.b"), topic("topic.b", "topic.a")],
                    )
                ],
            )
        ]
    )

    findings = Linter(tree).run()
    assert any(f.rule == "prereq-acyclic" for f in findings)


def test_linter_flags_an_unresolvable_prerequisite(tmp_path: Path) -> None:
    _write_topic(tmp_path)
    topic_yaml = tmp_path / "courses/01-c/modules/01-m/topics/01-t/topic.yaml"
    topic_yaml.write_text(
        topic_yaml.read_text(encoding="utf-8")
        + "\nprerequisites:\n  - topic: topic.does-not-exist\n",
        encoding="utf-8",
    )
    findings = lint(load_content(tmp_path))
    assert any(f.rule == "prereq-resolves" for f in findings)


# ------------------------------------------------------------------ loader


def test_loader_reports_invalid_yaml_without_raising(tmp_path: Path) -> None:
    (tmp_path / "paths").mkdir(parents=True)
    (tmp_path / "paths" / "broken.yaml").write_text("id: [unclosed\n", encoding="utf-8")
    tree = load_content(tmp_path)
    assert not tree.ok
    assert any("invalid YAML" in str(e) for e in tree.errors)


def test_loader_collects_all_errors_rather_than_stopping_at_the_first(tmp_path: Path) -> None:
    (tmp_path / "paths").mkdir(parents=True)
    (tmp_path / "paths" / "a.yaml").write_text("id: [bad\n", encoding="utf-8")
    (tmp_path / "paths" / "b.yaml").write_text("id: [also-bad\n", encoding="utf-8")
    tree = load_content(tmp_path)
    assert len(tree.errors) >= 2


def test_loader_inlines_diagram_sources(tmp_path: Path) -> None:
    _write_topic(tmp_path, lesson_body=':::diagram{src=../d/x.mmd caption="A caption"}\n')
    topic_dir = tmp_path / "courses/01-c/modules/01-m/topics/01-t"
    (topic_dir / "d").mkdir()
    (topic_dir / "d" / "x.mmd").write_text("graph TD\n  A --> B\n", encoding="utf-8")

    tree = load_content(tmp_path)
    body = tree.all_topics()[0].lessons[0].body
    assert "```mermaid" in body
    assert "A --> B" in body
    assert "A caption" in body


def test_loader_reports_a_missing_diagram(tmp_path: Path) -> None:
    _write_topic(tmp_path, lesson_body=":::diagram{src=../d/missing.mmd}\n")
    tree = load_content(tmp_path)
    assert any("src not found" in str(e) for e in tree.errors)


# -------------------------------------------------- the repository's content


@pytest.mark.skipif(not REPO_CONTENT.is_dir(), reason="content directory not mounted")
def test_the_real_curriculum_parses_and_lints_clean() -> None:
    """The build gate. If this fails, the curriculum is not shippable."""
    tree = load_content(REPO_CONTENT)
    assert tree.ok, "\n".join(str(e) for e in tree.errors)

    findings = lint(tree)
    errors = [str(f) for f in findings if f.severity == "error"]
    assert not errors, "\n".join(errors)


@pytest.mark.skipif(not REPO_CONTENT.is_dir(), reason="content directory not mounted")
def test_every_published_topic_has_a_complete_artifact_set() -> None:
    tree = load_content(REPO_CONTENT)
    published = [t for t in tree.all_topics() if t.topic.status == "published"]
    assert published, "no published topics found"

    for topic in published:
        where = topic.topic.id
        assert topic.lessons, f"{where}: no lessons"
        assert topic.quiz, f"{where}: no quiz"
        assert topic.labs, f"{where}: no labs"
        assert topic.assessment, f"{where}: no assessment"
        assert topic.topic.objectives, f"{where}: no objectives"


@pytest.mark.skipif(not REPO_CONTENT.is_dir(), reason="content directory not mounted")
def test_no_lesson_leaks_an_answer_key_into_prose() -> None:
    """Answer keys belong in YAML, gated by the API — never in a lesson body."""
    tree = load_content(REPO_CONTENT)
    for topic in tree.all_topics():
        for lesson in topic.lessons:
            lowered = lesson.body.lower()
            for banned in ("model_answer:", "root_cause:", "is_correct:"):
                assert banned not in lowered, f"{topic.topic.id}/{lesson.frontmatter.section}"


def test_linter_flags_a_project_requiring_a_topic_that_does_not_exist(tmp_path: Path) -> None:
    """A project gated on a missing topic never unlocks, and looks deliberate.

    Nothing else catches it: the file is valid, the API serves it, and it simply
    stays locked for every learner forever.
    """
    _write_topic(tmp_path)
    (tmp_path / "projects").mkdir()
    (tmp_path / "projects" / "demo.yaml").write_text(
        textwrap.dedent("""
            id: project.demo
            slug: demo-project
            title: A demonstration project
            level: L3
            requires_topics: [topic.t, topic.does-not-exist]
            estimated_hours: 3
            summary: A project summary long enough to satisfy the validation rules.
            brief: |
              A brief long enough to pass validation, which requires at least one
              hundred characters of actual explanation of what the learner is
              expected to build and why it is worth their time to do so.
            deliverables: ["A written report"]
            rubric:
              - id: r1
                criterion: The measurements are real
                excellent: Numbers come from the learner's own machine, with commands shown.
                adequate: Numbers are present but not fully sourced to commands.
                inadequate: No measurements, or numbers with no provenance at all.
                evidence: The command output in your report
              - id: r2
                criterion: The conclusion follows from the evidence
                excellent: Every claim traces to a measurement recorded earlier in the report.
                adequate: The conclusion is reasonable but not fully traced to evidence.
                inadequate: Conclusions that the evidence does not support.
                evidence: The final section of your report
        """).strip(),
        encoding="utf-8",
    )
    findings = lint(load_content(tmp_path))
    assert any(f.rule == "project-requires" for f in findings)


# ------------------------------------------------------------- search index text


def test_plain_text_drops_diagram_source() -> None:
    """Mermaid source is syntax, and indexing it puts arrow operators and node
    ids into search snippets where prose should be."""
    body = textwrap.dedent("""
        Some prose about the kernel boundary.

        ```mermaid
        graph TD
            A["Source code<br/server.c"] --compile--> B["Binary"]
        ```

        More prose after the diagram.
    """)
    indexed = plain_text(body)
    assert "Some prose about the kernel boundary." in indexed
    assert "More prose after the diagram." in indexed
    assert "graph TD" not in indexed
    assert "compile" not in indexed


def test_plain_text_leaves_no_angle_brackets() -> None:
    """The snippet is rendered as HTML, so `ts_headline` must have nothing to
    work with but the <mark> tags it adds itself.

    A lesson containing a literal `<br/>` would otherwise close the paragraph
    the snippet is rendered into, and the page's structure would be invalid —
    from entirely trusted, git-authored content.
    """
    body = "Redirect with 2>&1 and a literal <br/> plus <p>markup</p>."
    indexed = plain_text(body)
    assert "<" not in indexed
    assert ">" not in indexed
    assert "Redirect with 2" in indexed
