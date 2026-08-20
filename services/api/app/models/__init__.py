"""SQLAlchemy models.

Every model must be imported here so Alembic autogenerate can see it.
"""

from app.db.base import Base
from app.models.attainment import Certificate, UserAchievement
from app.models.content import ContentVersion
from app.models.curriculum import (
    Course,
    GlossaryTerm,
    Lab,
    LearningPath,
    Lesson,
    Module,
    Objective,
    PathCourse,
    Prerequisite,
    Quiz,
    QuizOption,
    QuizQuestion,
    Topic,
    TopicItem,
    content_uuid,
)
from app.models.identity import (
    AuditLog,
    Hypothesis,
    LoginAttempt,
    QuizAnswer,
    QuizAttempt,
    Session,
    User,
    UserProgress,
)
from app.models.projects import Project, ProjectSubmission
from app.models.search import ContentSearch

__all__ = [
    "AuditLog",
    "Base",
    "Certificate",
    "ContentSearch",
    "ContentVersion",
    "Course",
    "GlossaryTerm",
    "Hypothesis",
    "Lab",
    "LearningPath",
    "Lesson",
    "LoginAttempt",
    "Module",
    "Objective",
    "PathCourse",
    "Prerequisite",
    "Project",
    "ProjectSubmission",
    "Quiz",
    "QuizAnswer",
    "QuizAttempt",
    "QuizOption",
    "QuizQuestion",
    "Session",
    "Topic",
    "TopicItem",
    "User",
    "UserAchievement",
    "UserProgress",
    "content_uuid",
]
