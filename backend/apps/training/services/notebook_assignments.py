from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.db.models import Avg, Count, Max, Q

from apps.online.models import OnlineCourseContentLibraryItem
from apps.training.models import (
    TrainingAuditEvent,
    TrainingContentItem,
    TrainingGradebookEntry,
    TrainingGraderJob,
    TrainingLabSubmission,
    TrainingNotebookLabHint,
    TrainingNotebookLabProfile,
)
from apps.training.services.lab_repeatability import repeatable_lab_reentry_enabled


def effective_assignment_code(lab_profile: TrainingNotebookLabProfile) -> str:
    value = str(lab_profile.assignment_code or "").strip()
    if value:
        return value
    return lab_profile.content_item.slug.replace("-", "_")


def recommended_hint_ids_for_submission(
    *,
    lab_profile: TrainingNotebookLabProfile,
    submission: TrainingLabSubmission | None,
) -> list[int]:
    if submission is None:
        return []
    score_percent = _submission_score_percent(submission)
    hint_ids: list[int] = []
    hints = list(lab_profile.hints.filter(is_active=True).order_by("sort_order", "id"))
    for hint in hints:
        if hint_is_visible_for_submission(hint=hint, submission=submission, score_percent=score_percent):
            hint_ids.append(hint.id)
    return hint_ids


def hint_is_visible_for_submission(
    *,
    hint: TrainingNotebookLabHint,
    submission: TrainingLabSubmission | None,
    score_percent: Decimal | None = None,
) -> bool:
    if not hint.is_active:
        return False
    if hint.availability_mode == TrainingNotebookLabHint.AvailabilityMode.ALWAYS:
        return True
    if submission is None:
        return False
    if hint.availability_mode == TrainingNotebookLabHint.AvailabilityMode.AFTER_ATTEMPT:
        return submission.attempt_number >= max(1, hint.min_attempt_number)
    if hint.availability_mode == TrainingNotebookLabHint.AvailabilityMode.AFTER_FAILURE:
        return submission.attempt_number >= max(1, hint.min_attempt_number) and submission.passed is False
    if hint.availability_mode == TrainingNotebookLabHint.AvailabilityMode.AFTER_SCORE_BELOW:
        resolved_percent = score_percent if score_percent is not None else _submission_score_percent(submission)
        if resolved_percent is None:
            return submission.attempt_number >= max(1, hint.min_attempt_number)
        return (
            submission.attempt_number >= max(1, hint.min_attempt_number)
            and resolved_percent <= Decimal(str(hint.max_score_percent))
        )
    return False


def build_student_lab_summary(*, content_item: TrainingContentItem, user) -> dict[str, Any] | None:
    try:
        lab_profile = content_item.lab_profile
    except TrainingNotebookLabProfile.DoesNotExist:
        return None

    hints = list(lab_profile.hints.filter(is_active=True).order_by("sort_order", "id"))
    gradebook_entry = (
        TrainingGradebookEntry.objects.select_related("latest_submission")
        .filter(user=user, content_item=content_item)
        .first()
    )
    latest_submission = gradebook_entry.latest_submission if gradebook_entry else None
    latest_hint_ids = recommended_hint_ids_for_submission(lab_profile=lab_profile, submission=latest_submission)
    visible_hints = [
        {
            "id": hint.id,
            "title": hint.title,
            "bodyMarkdown": hint.body_markdown,
            "availabilityMode": hint.availability_mode,
            "minAttemptNumber": hint.min_attempt_number,
            "maxScorePercent": hint.max_score_percent,
            "isRecommended": hint.id in latest_hint_ids,
        }
        for hint in hints
        if hint_is_visible_for_submission(hint=hint, submission=latest_submission)
    ]

    score_percent = _submission_score_percent(latest_submission) if latest_submission else None
    attempts_count = gradebook_entry.attempts_count if gradebook_entry else 0
    if repeatable_lab_reentry_enabled(content_item=content_item, gradebook_entry=gradebook_entry):
        attempts_remaining = None
    else:
        attempts_remaining = max(lab_profile.max_attempts - attempts_count, 0) if lab_profile.max_attempts else None

    return {
        "assignmentCode": effective_assignment_code(lab_profile),
        "passThresholdPercent": lab_profile.pass_threshold_percent,
        "maxAttempts": lab_profile.max_attempts,
        "attemptsRemaining": attempts_remaining,
        "unlockedHintsCount": len(visible_hints),
        "lockedHintsCount": max(len(hints) - len(visible_hints), 0),
        "hints": visible_hints,
        "latestScorePercent": str(score_percent) if score_percent is not None else None,
        "gradebook": (
            {
                "attemptsCount": gradebook_entry.attempts_count,
                "latestScore": str(gradebook_entry.latest_score) if gradebook_entry.latest_score is not None else None,
                "bestScore": str(gradebook_entry.best_score) if gradebook_entry.best_score is not None else None,
                "maxScore": str(gradebook_entry.max_score) if gradebook_entry.max_score is not None else None,
                "passed": gradebook_entry.passed,
                "completedAt": gradebook_entry.completed_at.isoformat() if gradebook_entry.completed_at else None,
            }
            if gradebook_entry
            else None
        ),
    }


@dataclass(frozen=True)
class NotebookAssignmentAdminAnalytics:
    learners_attempted: int
    total_submissions: int
    pass_rate_percent: float
    average_score_percent: float | None
    latest_submission_at: object | None
    pending_jobs: int
    failed_jobs: int
    average_attempts_per_learner: float
    best_score_percent: float | None
    hint_views: int
    grade_distribution: dict[str, int]


def build_notebook_assignment_admin_analytics(*, content_item: TrainingContentItem) -> NotebookAssignmentAdminAnalytics:
    submissions = TrainingLabSubmission.objects.filter(content_item=content_item)
    gradebook_entries = TrainingGradebookEntry.objects.filter(content_item=content_item)
    grader_jobs = TrainingGraderJob.objects.filter(submission__content_item=content_item)
    hint_views = TrainingAuditEvent.objects.filter(
        content_item=content_item,
        event_type=TrainingAuditEvent.EventType.LAB_HINT_VIEWED,
    ).count()

    attempted_learners = gradebook_entries.count()
    passed_learners = gradebook_entries.filter(passed=True).count()
    aggregate_scores = submissions.filter(score__isnull=False, max_score__isnull=False).aggregate(
        average_score=Avg("score"),
        best_score=Max("score"),
        latest_submission_at=Max("submitted_at"),
    )
    attempts_avg = gradebook_entries.aggregate(avg_attempts=Avg("attempts_count")).get("avg_attempts")
    grade_distribution = {
        "below50": gradebook_entries.filter(latest_score__lt=50).count(),
        "from50to69": gradebook_entries.filter(latest_score__gte=50, latest_score__lt=70).count(),
        "from70to84": gradebook_entries.filter(latest_score__gte=70, latest_score__lt=85).count(),
        "from85to100": gradebook_entries.filter(latest_score__gte=85).count(),
    }
    pass_rate_percent = 0.0
    if attempted_learners:
        pass_rate_percent = round((passed_learners / attempted_learners) * 100, 2)

    average_score_percent = aggregate_scores.get("average_score")
    best_score_percent = aggregate_scores.get("best_score")
    return NotebookAssignmentAdminAnalytics(
        learners_attempted=attempted_learners,
        total_submissions=submissions.count(),
        pass_rate_percent=pass_rate_percent,
        average_score_percent=float(average_score_percent) if average_score_percent is not None else None,
        latest_submission_at=aggregate_scores.get("latest_submission_at"),
        pending_jobs=grader_jobs.filter(status__in=(TrainingGraderJob.Status.QUEUED, TrainingGraderJob.Status.RUNNING)).count(),
        failed_jobs=grader_jobs.filter(status=TrainingGraderJob.Status.FAILED).count(),
        average_attempts_per_learner=round(float(attempts_avg or 0.0), 2),
        best_score_percent=float(best_score_percent) if best_score_percent is not None else None,
        hint_views=hint_views,
        grade_distribution=grade_distribution,
    )


def sync_course_library_for_notebook_content(*, content_item: TrainingContentItem) -> OnlineCourseContentLibraryItem | None:
    if content_item.content_kind != TrainingContentItem.ContentKind.NOTEBOOK or content_item.course_id is None:
        return None

    library_item, _created = OnlineCourseContentLibraryItem.objects.update_or_create(
        training_content=content_item,
        defaults={
            "section_type": OnlineCourseContentLibraryItem.SECTION_MAIN,
            "title": content_item.name,
            "description": content_item.description,
            "library_group": content_item.course.slug,
            "asset_type": OnlineCourseContentLibraryItem.ASSET_NOTEBOOK,
            "language": content_item.course.LOCALE_EN,
            "body_markdown": "",
            "external_url": content_item.source_url or "",
            "is_active": content_item.status == TrainingContentItem.Status.PUBLISHED,
        },
    )
    return library_item


def _submission_score_percent(submission: TrainingLabSubmission | None) -> Decimal | None:
    if submission is None or submission.score in (None, "") or submission.max_score in (None, "", 0, Decimal("0")):
        return None
    try:
        return (Decimal(str(submission.score)) / Decimal(str(submission.max_score))) * Decimal("100")
    except Exception:
        return None
