from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.utils import timezone

from apps.online.models import (
    OnlineCompletionEvidence,
    OnlineCourse,
    OnlineEnrollment,
    OnlineEnrollmentAttestation,
    OnlineLessonProgress,
)


def completion_rule_payload(course: OnlineCourse) -> dict[str, Any]:
    return {
        "requiredCompletionPercent": course.required_completion_percent,
        "requiredAttendancePercent": course.required_attendance_percent,
        "requiresAttestation": course.requires_attestation,
    }


def default_attestation_text(course: OnlineCourse) -> str:
    course_title = course.title_en or course.title_de or course.slug
    return (
        f"I confirm that I completed the required learning steps for {course_title} "
        "and understand the expectations described in this course."
    )


def lesson_progress_payload(progress: OnlineLessonProgress | None, *, total_steps: int = 0) -> dict[str, Any]:
    if progress is None:
        return {
            "activeStepId": "",
            "completedStepIds": [],
            "progressPercent": 0,
            "startedAt": None,
            "completedAt": None,
            "totalSteps": total_steps,
        }
    return {
        "activeStepId": progress.active_step_id,
        "completedStepIds": progress.completed_step_ids,
        "progressPercent": progress.progress_percent,
        "startedAt": progress.started_at,
        "completedAt": progress.completed_at,
        "totalSteps": total_steps,
    }


def lesson_progress_map_for_enrollment(
    enrollment: OnlineEnrollment,
    *,
    lesson_ids: list[int],
) -> dict[int, OnlineLessonProgress]:
    if not lesson_ids:
        return {}
    return {
        progress.lesson_id: progress
        for progress in OnlineLessonProgress.objects.filter(
            enrollment=enrollment,
            lesson_id__in=lesson_ids,
        )
    }


def annotate_lessons_payload_with_progress(
    lessons_payload: list[dict[str, Any]],
    *,
    progress_map: dict[int, OnlineLessonProgress],
) -> None:
    for lesson in lessons_payload:
        lesson_id = lesson.get("id")
        interactive_lesson = lesson.get("interactiveLesson") or {}
        total_steps = len(interactive_lesson.get("steps") or [])
        progress = progress_map.get(lesson_id)
        lesson["progress"] = lesson_progress_payload(progress, total_steps=total_steps)


def annotate_modules_payload_with_progress(
    modules_payload: list[dict[str, Any]],
    *,
    progress_map: dict[int, OnlineLessonProgress],
) -> None:
    for module in modules_payload:
        lessons_payload = module.get("lessons")
        if isinstance(lessons_payload, list):
            annotate_lessons_payload_with_progress(lessons_payload, progress_map=progress_map)


def compute_enrollment_attendance_percent(enrollment: OnlineEnrollment) -> float:
    sessions_count = enrollment.cohort.sessions.count()
    if sessions_count <= 0:
        return 0.0
    present_count = enrollment.attendance_records.filter(status="present").count()
    return round((present_count / sessions_count) * 100, 2)


def _evidence_payload(evidence: OnlineCompletionEvidence | None) -> dict[str, Any] | None:
    if evidence is None:
        return None
    return {
        "id": evidence.id,
        "status": evidence.status,
        "evidenceCode": str(evidence.evidence_code),
        "completionPercent": evidence.completion_percent,
        "attendancePercent": float(evidence.attendance_percent),
        "issuedAt": evidence.issued_at,
    }


def _attestation_payload(attestation: OnlineEnrollmentAttestation | None) -> dict[str, Any] | None:
    if attestation is None:
        return None
    return {
        "id": attestation.id,
        "fullName": attestation.full_name,
        "attestationText": attestation.attestation_text,
        "confirmedAt": attestation.confirmed_at,
    }


def _get_enrollment_evidence(enrollment: OnlineEnrollment) -> OnlineCompletionEvidence | None:
    try:
        return enrollment.completion_evidence
    except OnlineCompletionEvidence.DoesNotExist:
        return None


def build_enrollment_completion_summary(
    enrollment: OnlineEnrollment,
    *,
    lessons_payload: list[dict[str, Any]] | None = None,
    progress_map: dict[int, OnlineLessonProgress] | None = None,
) -> dict[str, Any]:
    if lessons_payload is None:
        lesson_ids = list(enrollment.course.structured_lessons.values_list("id", flat=True))
    else:
        lesson_ids = [int(lesson.get("id")) for lesson in lessons_payload if lesson.get("id")]
    if progress_map is None:
        progress_map = lesson_progress_map_for_enrollment(enrollment, lesson_ids=lesson_ids)

    total_lessons = len(lesson_ids) or max(int(enrollment.course.lessons_count or 0), 1)
    completed_lessons = sum(
        1
        for lesson_id in lesson_ids
        if (
            (progress_map.get(lesson_id) and progress_map[lesson_id].completed_at is not None)
            or (progress_map.get(lesson_id) and progress_map[lesson_id].progress_percent >= 100)
        )
    )
    started_lessons = sum(1 for lesson_id in lesson_ids if progress_map.get(lesson_id) and progress_map[lesson_id].progress_percent > 0)
    progress_percent = round((completed_lessons / total_lessons) * 100) if total_lessons > 0 else 0
    attendance_percent = compute_enrollment_attendance_percent(enrollment)
    latest_attestation = enrollment.attestations.order_by("-confirmed_at", "-id").first()
    evidence = _get_enrollment_evidence(enrollment)
    rule = completion_rule_payload(enrollment.course)
    meets_completion_rule = progress_percent >= enrollment.course.required_completion_percent
    meets_attendance_rule = attendance_percent >= enrollment.course.required_attendance_percent
    is_rule_ready = meets_completion_rule and meets_attendance_rule
    requires_attestation = enrollment.course.requires_attestation

    if evidence is not None and evidence.status == OnlineCompletionEvidence.STATUS_ISSUED:
        status = "completed"
        status_label = "Completed"
    elif is_rule_ready and requires_attestation and latest_attestation is None:
        status = "ready_for_attestation"
        status_label = "Ready for attestation"
    elif is_rule_ready:
        status = "eligible"
        status_label = "Eligible for evidence"
    else:
        status = "in_progress"
        status_label = "In progress"

    return {
        "status": status,
        "statusLabel": status_label,
        "progressPercent": progress_percent,
        "completedLessons": completed_lessons,
        "startedLessons": started_lessons,
        "totalLessons": total_lessons,
        "attendancePercent": attendance_percent,
        "ruleReady": is_rule_ready,
        "rule": rule,
        "attestation": _attestation_payload(latest_attestation),
        "evidence": _evidence_payload(evidence),
        "requirements": {
            "completionMet": meets_completion_rule,
            "attendanceMet": meets_attendance_rule,
            "attestationMet": (latest_attestation is not None) if requires_attestation else True,
        },
    }


def issue_completion_evidence_if_eligible(enrollment: OnlineEnrollment) -> OnlineCompletionEvidence | None:
    summary = build_enrollment_completion_summary(enrollment)
    if not summary["ruleReady"]:
        return _get_enrollment_evidence(enrollment)
    if enrollment.course.requires_attestation and summary["attestation"] is None:
        return _get_enrollment_evidence(enrollment)

    latest_attestation = enrollment.attestations.order_by("-confirmed_at", "-id").first()
    defaults = {
        "course": enrollment.course,
        "attestation": latest_attestation,
        "status": OnlineCompletionEvidence.STATUS_ISSUED,
        "completion_percent": summary["progressPercent"],
        "attendance_percent": Decimal(str(summary["attendancePercent"])),
        "rule_snapshot": {
            **summary["rule"],
            "issuedStatus": "completed",
        },
    }
    evidence, created = OnlineCompletionEvidence.objects.get_or_create(
        enrollment=enrollment,
        defaults=defaults,
    )
    if not created:
        changed = False
        for field, value in defaults.items():
            if getattr(evidence, field) != value:
                setattr(evidence, field, value)
                changed = True
        if changed:
            evidence.save(update_fields=["course", "attestation", "status", "completion_percent", "attendance_percent", "rule_snapshot", "updated_at"])

    if enrollment.status != OnlineEnrollment.STATUS_COMPLETED or enrollment.completed_at is None:
        enrollment.status = OnlineEnrollment.STATUS_COMPLETED
        enrollment.completed_at = timezone.now()
        enrollment.save(update_fields=["status", "completed_at"])
    return evidence
