from __future__ import annotations

from typing import Any

from django.utils import timezone

from apps.online.models import OnlineEnrollment, OnlineCourseLesson, OnlineLessonProgress
from apps.online.services.course_structure import build_course_lessons_payload


def lesson_step_ids_from_payload(lesson_payload: dict[str, Any]) -> list[str]:
    interactive_lesson = lesson_payload.get("interactiveLesson") or {}
    return [
        str(step.get("id") or "").strip()
        for step in interactive_lesson.get("steps") or []
        if str(step.get("id") or "").strip()
    ]


def normalize_lesson_progress_snapshot(
    *,
    active_step_id: str,
    completed_step_ids: list[str],
    allowed_step_ids: list[str],
) -> dict[str, Any]:
    allowed_set = set(allowed_step_ids)
    normalized_completed: list[str] = []
    for step_id in completed_step_ids:
        if step_id in allowed_set and step_id not in normalized_completed:
            normalized_completed.append(step_id)
    normalized_active = active_step_id if active_step_id in allowed_set else ""
    if not normalized_active:
        normalized_active = next(
            (step_id for step_id in allowed_step_ids if step_id not in normalized_completed),
            "",
        ) or (allowed_step_ids[0] if allowed_step_ids else "")
    progress_percent = round((len(normalized_completed) / len(allowed_step_ids)) * 100) if allowed_step_ids else 0
    return {
        "activeStepId": normalized_active,
        "completedStepIds": normalized_completed,
        "progressPercent": progress_percent,
        "isCompleted": bool(allowed_step_ids) and len(normalized_completed) >= len(allowed_step_ids),
    }


def upsert_lesson_progress(
    *,
    enrollment: OnlineEnrollment,
    lesson: OnlineCourseLesson,
    lesson_payload: dict[str, Any],
    active_step_id: str,
    completed_step_ids: list[str],
) -> tuple[OnlineLessonProgress, dict[str, Any], list[str]]:
    allowed_step_ids = lesson_step_ids_from_payload(lesson_payload)
    snapshot = normalize_lesson_progress_snapshot(
        active_step_id=active_step_id,
        completed_step_ids=completed_step_ids,
        allowed_step_ids=allowed_step_ids,
    )
    progress, _created = OnlineLessonProgress.objects.get_or_create(
        enrollment=enrollment,
        lesson=lesson,
        defaults={
            "active_step_id": snapshot["activeStepId"],
            "completed_step_ids": snapshot["completedStepIds"],
            "progress_percent": snapshot["progressPercent"],
            "completed_at": timezone.now() if snapshot["isCompleted"] else None,
        },
    )
    progress.active_step_id = snapshot["activeStepId"]
    progress.completed_step_ids = snapshot["completedStepIds"]
    progress.progress_percent = snapshot["progressPercent"]
    progress.completed_at = progress.completed_at or timezone.now() if snapshot["isCompleted"] else None
    progress.save(
        update_fields=[
            "active_step_id",
            "completed_step_ids",
            "progress_percent",
            "completed_at",
            "updated_at",
        ]
    )
    return progress, snapshot, allowed_step_ids


def lesson_payload_for_course_lesson(*, enrollment: OnlineEnrollment, lesson: OnlineCourseLesson) -> dict[str, Any] | None:
    lessons_payload = build_course_lessons_payload(enrollment.course)
    return next(
        (lesson_payload for lesson_payload in lessons_payload if int(lesson_payload.get("id") or 0) == lesson.id),
        None,
    )


def mark_lesson_step_completed(
    *,
    enrollment: OnlineEnrollment,
    lesson: OnlineCourseLesson,
    lesson_payload: dict[str, Any],
    step_id: str,
) -> tuple[OnlineLessonProgress, dict[str, Any], list[str]] | None:
    normalized_step_id = str(step_id or "").strip()
    if not normalized_step_id:
        return None

    existing_progress = (
        OnlineLessonProgress.objects.filter(enrollment=enrollment, lesson=lesson).first()
    )
    completed_step_ids = list(existing_progress.completed_step_ids or []) if existing_progress else []
    if normalized_step_id not in completed_step_ids:
        completed_step_ids.append(normalized_step_id)

    allowed_step_ids = lesson_step_ids_from_payload(lesson_payload)
    completed_set = set(completed_step_ids)
    current_index = allowed_step_ids.index(normalized_step_id) if normalized_step_id in allowed_step_ids else -1
    active_step_id = (
        next(
            (
                step_id
                for step_id in allowed_step_ids[max(current_index + 1, 0) :]
                if step_id not in completed_set
            ),
            "",
        )
        or next((step_id for step_id in allowed_step_ids if step_id not in completed_set), "")
        or normalized_step_id
    )
    return upsert_lesson_progress(
        enrollment=enrollment,
        lesson=lesson,
        lesson_payload=lesson_payload,
        active_step_id=active_step_id,
        completed_step_ids=completed_step_ids,
    )
