from __future__ import annotations

from typing import Any

from django.db import transaction

from apps.online.models import OnlineEnrollment, OnlineLessonProgress
from apps.online.services.completion import build_enrollment_completion_summary, issue_completion_evidence_if_eligible, lesson_progress_payload
from apps.online.services.lesson_progress import lesson_payload_for_course_lesson, mark_lesson_step_completed


def sync_training_content_practice_completion(*, user, content_item) -> list[dict[str, Any]]:
    if not getattr(content_item, "online_course_section_items", None):
        return []

    updates: list[dict[str, Any]] = []
    related_section_items = list(
        content_item.online_course_section_items.select_related(
            "section__lesson__course",
            "section__lesson__module",
        ).all()
    )
    if not related_section_items:
        return []

    for section_item in related_section_items:
        lesson = getattr(getattr(section_item, "section", None), "lesson", None)
        if lesson is None or not lesson.is_active or lesson.course_id is None:
            continue
        enrollments = list(
            OnlineEnrollment.objects.select_related("course", "cohort", "profile__user")
            .filter(
                profile__user=user,
                course_id=lesson.course_id,
                status__in=(OnlineEnrollment.STATUS_ACTIVE, OnlineEnrollment.STATUS_COMPLETED),
            )
        )
        if not enrollments:
            continue
        for enrollment in enrollments:
            update = _sync_lesson_practice_completion_for_enrollment(
                enrollment=enrollment,
                lesson=lesson,
            )
            if update is not None:
                updates.append(update)
    return updates


@transaction.atomic
def _sync_lesson_practice_completion_for_enrollment(*, enrollment: OnlineEnrollment, lesson) -> dict[str, Any] | None:
    lesson_payload = lesson_payload_for_course_lesson(enrollment=enrollment, lesson=lesson)
    if not lesson_payload:
        return None
    practice_step_id = f"lesson-{lesson.id}-practice"
    update = mark_lesson_step_completed(
        enrollment=enrollment,
        lesson=lesson,
        lesson_payload=lesson_payload,
        step_id=practice_step_id,
    )
    if update is None:
        return None
    progress, _snapshot, allowed_step_ids = update
    issue_completion_evidence_if_eligible(enrollment)
    completion_summary = build_enrollment_completion_summary(enrollment)
    return {
        "courseId": enrollment.course_id,
        "lessonId": lesson.id,
        "stepId": practice_step_id,
        "progress": lesson_progress_payload(progress, total_steps=len(allowed_step_ids)),
        "completion": completion_summary,
    }
