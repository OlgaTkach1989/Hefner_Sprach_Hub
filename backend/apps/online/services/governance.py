from __future__ import annotations

import json
from typing import Any

from django.contrib.contenttypes.models import ContentType
from django.http import HttpRequest
from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone

from apps.online.models import (
    OnlineAuditEvent,
    OnlineCourse,
    OnlineCourseApproval,
    OnlineCourseVersion,
)


COURSE_LIFECYCLE_LABELS = dict(OnlineCourse.LIFECYCLE_CHOICES)
COURSE_LIFECYCLE_ORDER = (
    OnlineCourse.LIFECYCLE_DRAFT,
    OnlineCourse.LIFECYCLE_IN_REVIEW,
    OnlineCourse.LIFECYCLE_APPROVED,
    OnlineCourse.LIFECYCLE_PUBLISHED,
)


class CourseLifecycleValidationError(ValueError):
    def __init__(self, detail: str, *, readiness: dict[str, Any] | None = None):
        super().__init__(detail)
        self.detail = detail
        self.readiness = readiness


def lifecycle_status_label(status: str) -> str:
    return COURSE_LIFECYCLE_LABELS.get(status, status.replace("_", " ").title())


def normalize_course_lifecycle_status(
    *,
    lifecycle_status: str | None = None,
    is_published: bool | None = None,
    current_status: str | None = None,
) -> str:
    if lifecycle_status:
        return lifecycle_status
    if is_published is True:
        return OnlineCourse.LIFECYCLE_PUBLISHED
    if is_published is False:
        return OnlineCourse.LIFECYCLE_DRAFT
    return current_status or OnlineCourse.LIFECYCLE_PUBLISHED


def _request_metadata(request: HttpRequest | None) -> dict[str, Any]:
    if request is None:
        return {"method": "", "path": "", "ip_address": None}
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    ip_address = forwarded.split(",")[0].strip() if forwarded else request.META.get("REMOTE_ADDR")
    return {
        "method": request.method,
        "path": request.path[:255],
        "ip_address": ip_address or None,
    }


def log_online_audit_event(
    *,
    event_type: str,
    summary: str,
    actor=None,
    request: HttpRequest | None = None,
    course: OnlineCourse | None = None,
    instance=None,
    metadata: dict[str, Any] | None = None,
) -> OnlineAuditEvent:
    request_meta = _request_metadata(request)
    content_type = None
    object_id = None
    if instance is not None:
        content_type = ContentType.objects.get_for_model(instance.__class__)
        object_id = instance.pk
    actor_email = ""
    if actor is not None:
        actor_email = getattr(actor, "email", "") or getattr(actor, "username", "") or ""
    return OnlineAuditEvent.objects.create(
        actor=actor,
        actor_email=actor_email,
        course=course,
        content_type=content_type,
        object_id=object_id,
        event_type=event_type,
        summary=summary[:220],
        request_method=request_meta["method"],
        request_path=request_meta["path"],
        ip_address=request_meta["ip_address"],
        metadata=metadata or {},
    )


def _approval_action_for_transition(from_status: str, to_status: str) -> str:
    if to_status == OnlineCourse.LIFECYCLE_IN_REVIEW:
        return OnlineCourseApproval.ACTION_SUBMITTED
    if to_status == OnlineCourse.LIFECYCLE_APPROVED:
        return OnlineCourseApproval.ACTION_APPROVED
    if to_status == OnlineCourse.LIFECYCLE_PUBLISHED:
        return OnlineCourseApproval.ACTION_PUBLISHED
    if to_status == OnlineCourse.LIFECYCLE_ARCHIVED:
        return OnlineCourseApproval.ACTION_ARCHIVED
    return OnlineCourseApproval.ACTION_RETURNED_TO_DRAFT


def _latest_version_payload(version: OnlineCourseVersion | None) -> dict[str, Any] | None:
    if version is None:
        return None
    return {
        "id": version.id,
        "versionNumber": version.version_number,
        "lifecycleStatus": version.lifecycle_status,
        "lifecycleLabel": lifecycle_status_label(version.lifecycle_status),
        "source": version.source,
        "changeSummary": version.change_summary,
        "createdAt": version.created_at,
        "createdByEmail": getattr(version.created_by, "email", "") or "",
    }


def _version_history_payload(course: OnlineCourse, *, limit: int = 8) -> list[dict[str, Any]]:
    versions = list(course.versions.select_related("created_by").order_by("-version_number", "-id")[:limit])
    return [_latest_version_payload(version) for version in versions if version is not None]


def build_course_release_readiness_payload(course: OnlineCourse) -> dict[str, Any]:
    from apps.online.services.access import online_access_policy_audience_ids_for_instance
    from apps.online.services.course_structure import build_course_workspace_ids, summarize_course_structure

    structure_summary = summarize_course_structure(course)
    audience_ids = online_access_policy_audience_ids_for_instance(course)
    workspace_ids = build_course_workspace_ids(course)
    completion_rule_valid = 0 <= int(course.required_completion_percent or 0) <= 100 and 0 <= int(course.required_attendance_percent or 0) <= 100
    checks = [
        {
            "id": "title",
            "label": "Course title",
            "description": "Public course title is set.",
            "passed": bool((course.title_en or course.title_de or "").strip()),
            "required": True,
        },
        {
            "id": "short_description",
            "label": "Short description",
            "description": "Short public summary is ready for catalog use.",
            "passed": bool((course.short_description_en or course.short_description_de or "").strip()),
            "required": True,
        },
        {
            "id": "description",
            "label": "Full description",
            "description": "Long-form course description is filled in.",
            "passed": bool((course.description_en or course.description_de or "").strip()),
            "required": True,
        },
        {
            "id": "lesson_structure",
            "label": "Lesson structure",
            "description": "At least one module and lesson are present.",
            "passed": bool(structure_summary.get("modulesCount", 0) and structure_summary.get("lessonsCount", 0)),
            "required": True,
        },
        {
            "id": "lesson_content",
            "label": "Lesson content items",
            "description": "The learning flow contains actual content items.",
            "passed": bool(structure_summary.get("itemsCount", 0)),
            "required": True,
        },
        {
            "id": "completion_rule",
            "label": "Completion rule",
            "description": "Completion and attendance thresholds are valid.",
            "passed": completion_rule_valid,
            "required": True,
        },
        {
            "id": "audience_policy",
            "label": "Audience policy",
            "description": "At least one audience or access role is linked.",
            "passed": bool(audience_ids),
            "required": False,
        },
        {
            "id": "workspace_placement",
            "label": "Workspace placement",
            "description": "The course is linked to at least one public learning area.",
            "passed": bool(workspace_ids),
            "required": False,
        },
    ]
    required_failed = [check for check in checks if check["required"] and not check["passed"]]
    optional_failed = [check for check in checks if not check["required"] and not check["passed"]]
    return {
        "checks": checks,
        "requiredChecksPassed": len(required_failed) == 0,
        "requiredFailedCount": len(required_failed),
        "optionalFailedCount": len(optional_failed),
        "failedCheckIds": [check["id"] for check in required_failed + optional_failed],
        "isReadyForReview": len(required_failed) == 0,
        "isReadyForApproval": len(required_failed) == 0,
        "isReadyForPublish": len(required_failed) == 0,
        "statusLabel": "Ready" if len(required_failed) == 0 else "Action required",
    }


def _single_transition_allowed(from_status: str, to_status: str) -> bool:
    allowed = {
        OnlineCourse.LIFECYCLE_DRAFT: {OnlineCourse.LIFECYCLE_IN_REVIEW, OnlineCourse.LIFECYCLE_ARCHIVED},
        OnlineCourse.LIFECYCLE_IN_REVIEW: {
            OnlineCourse.LIFECYCLE_DRAFT,
            OnlineCourse.LIFECYCLE_APPROVED,
            OnlineCourse.LIFECYCLE_ARCHIVED,
        },
        OnlineCourse.LIFECYCLE_APPROVED: {
            OnlineCourse.LIFECYCLE_DRAFT,
            OnlineCourse.LIFECYCLE_IN_REVIEW,
            OnlineCourse.LIFECYCLE_PUBLISHED,
            OnlineCourse.LIFECYCLE_ARCHIVED,
        },
        OnlineCourse.LIFECYCLE_PUBLISHED: {
            OnlineCourse.LIFECYCLE_DRAFT,
            OnlineCourse.LIFECYCLE_IN_REVIEW,
            OnlineCourse.LIFECYCLE_APPROVED,
            OnlineCourse.LIFECYCLE_ARCHIVED,
        },
        OnlineCourse.LIFECYCLE_ARCHIVED: {OnlineCourse.LIFECYCLE_DRAFT},
    }
    return to_status in allowed.get(from_status, set())


def _transition_path(from_status: str, to_status: str) -> list[str]:
    if from_status == to_status:
        return []
    if to_status == OnlineCourse.LIFECYCLE_ARCHIVED:
        return [OnlineCourse.LIFECYCLE_ARCHIVED]
    if from_status == OnlineCourse.LIFECYCLE_ARCHIVED:
        if to_status == OnlineCourse.LIFECYCLE_DRAFT:
            return [OnlineCourse.LIFECYCLE_DRAFT]
        return [OnlineCourse.LIFECYCLE_DRAFT, *_transition_path(OnlineCourse.LIFECYCLE_DRAFT, to_status)]
    if from_status in COURSE_LIFECYCLE_ORDER and to_status in COURSE_LIFECYCLE_ORDER:
        from_index = COURSE_LIFECYCLE_ORDER.index(from_status)
        to_index = COURSE_LIFECYCLE_ORDER.index(to_status)
        if from_index < to_index:
            return list(COURSE_LIFECYCLE_ORDER[from_index + 1 : to_index + 1])
        return [to_status]
    return [to_status]


def _validate_publish_gate(course: OnlineCourse) -> dict[str, Any]:
    readiness = build_course_release_readiness_payload(course)
    if not readiness["isReadyForPublish"]:
        failed_required = [check["label"] for check in readiness["checks"] if check["required"] and not check["passed"]]
        detail = "Publish is blocked until required release checks are complete."
        if failed_required:
            detail = f"{detail} Missing: {', '.join(failed_required)}."
        raise CourseLifecycleValidationError(detail, readiness=readiness)
    return readiness


def _apply_single_course_lifecycle_status(
    course: OnlineCourse,
    *,
    to_status: str,
    actor=None,
    request: HttpRequest | None = None,
    note: str = "",
    metadata: dict[str, Any] | None = None,
    save: bool = True,
) -> bool:
    from_status = course.lifecycle_status or OnlineCourse.LIFECYCLE_DRAFT
    if from_status == to_status:
        return False
    if not _single_transition_allowed(from_status, to_status):
        raise CourseLifecycleValidationError(
            f"Cannot move a course from {lifecycle_status_label(from_status)} to {lifecycle_status_label(to_status)}."
        )
    if to_status == OnlineCourse.LIFECYCLE_PUBLISHED:
        _validate_publish_gate(course)

    changed = course.is_published != (to_status == OnlineCourse.LIFECYCLE_PUBLISHED) or from_status != to_status
    now = timezone.now()
    course.lifecycle_status = to_status
    course.is_published = to_status == OnlineCourse.LIFECYCLE_PUBLISHED
    if changed or course.lifecycle_status_changed_at is None:
        course.lifecycle_status_changed_at = now
    if to_status == OnlineCourse.LIFECYCLE_IN_REVIEW and course.submitted_for_review_at is None:
        course.submitted_for_review_at = now
    if to_status == OnlineCourse.LIFECYCLE_APPROVED and course.approved_at is None:
        course.approved_at = now
    if to_status == OnlineCourse.LIFECYCLE_PUBLISHED and course.published_at is None:
        course.published_at = now
    if to_status == OnlineCourse.LIFECYCLE_ARCHIVED and course.archived_at is None:
        course.archived_at = now
    if save:
        update_fields = ["lifecycle_status", "is_published", "updated_at", "lifecycle_status_changed_at"]
        if to_status == OnlineCourse.LIFECYCLE_IN_REVIEW:
            update_fields.append("submitted_for_review_at")
        if to_status == OnlineCourse.LIFECYCLE_APPROVED:
            update_fields.append("approved_at")
        if to_status == OnlineCourse.LIFECYCLE_PUBLISHED:
            update_fields.append("published_at")
        if to_status == OnlineCourse.LIFECYCLE_ARCHIVED:
            update_fields.append("archived_at")
        course.save(update_fields=update_fields)
    if changed:
        OnlineCourseApproval.objects.create(
            course=course,
            action=_approval_action_for_transition(from_status, to_status),
            from_status=from_status,
            to_status=to_status,
            actor=actor,
            note=note or "",
        )
        log_online_audit_event(
            event_type="course.lifecycle.changed",
            summary=f"Course lifecycle changed to {lifecycle_status_label(to_status)}",
            actor=actor,
            request=request,
            course=course,
            instance=course,
            metadata={
                "fromStatus": from_status,
                "toStatus": to_status,
                "note": note or "",
                **(metadata or {}),
            },
        )
    return changed


def apply_course_lifecycle_status(
    course: OnlineCourse,
    *,
    to_status: str,
    actor=None,
    request: HttpRequest | None = None,
    note: str = "",
    metadata: dict[str, Any] | None = None,
    save: bool = True,
) -> bool:
    current_status = course.lifecycle_status or OnlineCourse.LIFECYCLE_DRAFT
    path = _transition_path(current_status, to_status)
    changed = False
    for step in path:
        step_note = note
        if len(path) > 1 and not note:
            step_note = f"Auto-transitioned to {lifecycle_status_label(step)}."
        changed = _apply_single_course_lifecycle_status(
            course,
            to_status=step,
            actor=actor,
            request=request,
            note=step_note,
            metadata=metadata,
            save=save,
        ) or changed
    return changed


def create_course_version_snapshot(
    course: OnlineCourse,
    *,
    actor=None,
    source: str = "",
    change_summary: str = "",
) -> OnlineCourseVersion:
    from apps.online.services.access import online_access_policy_audience_ids_for_instance
    from apps.online.services.course_structure import (
        build_course_instructor_ids,
        build_course_modules_payload,
        build_course_workspace_ids,
        summarize_course_structure,
    )

    latest_version = course.versions.order_by("-version_number", "-id").first()
    version_number = (latest_version.version_number if latest_version is not None else 0) + 1
    structure_summary = summarize_course_structure(course)
    snapshot = {
        "slug": course.slug,
        "titleEn": course.title_en,
        "titleDe": course.title_de,
        "shortDescriptionEn": course.short_description_en,
        "shortDescriptionDe": course.short_description_de,
        "descriptionEn": course.description_en,
        "descriptionDe": course.description_de,
        "lifecycleStatus": course.lifecycle_status,
        "governance": build_course_governance_payload(course, include_history=False),
        "completionRule": {
            "requiredCompletionPercent": course.required_completion_percent,
            "requiredAttendancePercent": course.required_attendance_percent,
            "requiresAttestation": course.requires_attestation,
        },
        "audienceIds": online_access_policy_audience_ids_for_instance(course),
        "instructorIds": build_course_instructor_ids(course),
        "workspaceIds": build_course_workspace_ids(course),
        "modules": build_course_modules_payload(course),
    }
    normalized_snapshot = json.loads(json.dumps(snapshot, cls=DjangoJSONEncoder))
    normalized_structure_summary = json.loads(json.dumps(structure_summary, cls=DjangoJSONEncoder))
    version = OnlineCourseVersion.objects.create(
        course=course,
        version_number=version_number,
        lifecycle_status=course.lifecycle_status,
        source=(source or "manual").strip()[:80],
        change_summary=(change_summary or f"Snapshot for {lifecycle_status_label(course.lifecycle_status)}").strip()[:255],
        snapshot=normalized_snapshot,
        structure_summary=normalized_structure_summary,
        created_by=actor,
    )
    log_online_audit_event(
        event_type="course.version.created",
        summary=f"Created course version v{version.version_number}",
        actor=actor,
        course=course,
        instance=course,
        metadata={
            "versionNumber": version.version_number,
            "lifecycleStatus": course.lifecycle_status,
            "source": version.source,
            "changeSummary": version.change_summary,
        },
    )
    return version


def build_course_governance_payload(course: OnlineCourse, *, include_history: bool = False) -> dict[str, Any]:
    latest_approval = course.approval_events.order_by("-created_at", "-id").first()
    latest_version = course.versions.select_related("created_by").order_by("-version_number", "-id").first()
    payload = {
        "lifecycleStatus": course.lifecycle_status,
        "lifecycleLabel": lifecycle_status_label(course.lifecycle_status),
        "isPubliclyVisible": course.is_published,
        "statusChangedAt": course.lifecycle_status_changed_at,
        "submittedForReviewAt": course.submitted_for_review_at,
        "approvedAt": course.approved_at,
        "publishedAt": course.published_at,
        "archivedAt": course.archived_at,
        "approvalsCount": course.approval_events.count(),
        "versionsCount": course.versions.count(),
        "latestVersion": _latest_version_payload(latest_version),
        "readiness": build_course_release_readiness_payload(course),
        "latestApproval": (
            {
                "action": latest_approval.action,
                "actionLabel": latest_approval.get_action_display(),
                "fromStatus": latest_approval.from_status,
                "toStatus": latest_approval.to_status,
                "note": latest_approval.note,
                "createdAt": latest_approval.created_at,
                "actorEmail": getattr(latest_approval.actor, "email", "") or "",
            }
            if latest_approval is not None
            else None
        ),
    }
    if include_history:
        payload["versionHistory"] = _version_history_payload(course)
    return payload
