from __future__ import annotations

from django.db.models import Q, QuerySet

from apps.training.models import (
    TrainingAiConversation,
    TrainingAuditEvent,
    TrainingContentSyncEvent,
    TrainingGraderJob,
)


def _course_scoped_audit_q(course_id: int) -> Q:
    return (
        Q(course_id=course_id)
        | Q(content_item__course_id=course_id)
        | Q(submission__content_item__course_id=course_id)
    )


def training_admin_audit_events_queryset(
    *,
    course_id: int | None = None,
    outcome: str = "",
    category: str = "",
    query: str = "",
) -> QuerySet[TrainingAuditEvent]:
    queryset = (
        TrainingAuditEvent.objects.select_related("actor", "target_user", "course", "content_item__course", "submission__content_item__course")
        .order_by("-created_at", "-id")
    )
    if course_id is not None:
        queryset = queryset.filter(_course_scoped_audit_q(course_id))
    if outcome:
        queryset = queryset.filter(outcome=outcome)
    if category:
        queryset = queryset.filter(category=category)
    if query:
        queryset = queryset.filter(
            Q(actor_email__icontains=query)
            | Q(target_user_email__icontains=query)
            | Q(request_path__icontains=query)
            | Q(event_type__icontains=query)
            | Q(content_item__slug__icontains=query)
            | Q(submission__content_item__slug__icontains=query)
        )
    return queryset


def training_admin_content_sync_events_queryset(
    *,
    course_id: int | None = None,
    status_value: str = "",
    query: str = "",
) -> QuerySet[TrainingContentSyncEvent]:
    queryset = TrainingContentSyncEvent.objects.select_related("content_item__course").order_by("-created_at", "-id")
    if course_id is not None:
        queryset = queryset.filter(content_item__course_id=course_id)
    if status_value:
        queryset = queryset.filter(status=status_value)
    if query:
        queryset = queryset.filter(
            Q(content_slug__icontains=query)
            | Q(detail__icontains=query)
            | Q(external_source_id__icontains=query)
        )
    return queryset


def training_admin_grader_jobs_queryset(
    *,
    course_id: int | None = None,
    status_value: str = "",
    query: str = "",
) -> QuerySet[TrainingGraderJob]:
    queryset = (
        TrainingGraderJob.objects.select_related("submission__user", "submission__content_item__course")
        .order_by("-created_at", "-id")
    )
    if course_id is not None:
        queryset = queryset.filter(submission__content_item__course_id=course_id)
    if status_value:
        queryset = queryset.filter(status=status_value)
    if query:
        queryset = queryset.filter(
            Q(submission__user__email__icontains=query)
            | Q(submission__content_item__slug__icontains=query)
            | Q(error_message__icontains=query)
            | Q(worker_name__icontains=query)
        )
    return queryset


def build_training_admin_reports_overview(*, course_id: int | None = None) -> dict[str, object]:
    failed_audit_queryset = training_admin_audit_events_queryset(
        course_id=course_id,
        outcome=TrainingAuditEvent.Outcome.FAILED,
    )
    denied_audit_queryset = training_admin_audit_events_queryset(
        course_id=course_id,
        outcome=TrainingAuditEvent.Outcome.DENIED,
    )
    failed_sync_queryset = training_admin_content_sync_events_queryset(
        course_id=course_id,
        status_value=TrainingContentSyncEvent.Status.FAILED,
    )
    failed_grader_queryset = training_admin_grader_jobs_queryset(
        course_id=course_id,
        status_value=TrainingGraderJob.Status.FAILED,
    )
    ai_queryset = TrainingAiConversation.objects.filter(
        governance_status__in=(
            TrainingAiConversation.GovernanceStatus.OPEN,
            TrainingAiConversation.GovernanceStatus.IN_REVIEW,
        )
    )
    if course_id is not None:
        ai_queryset = ai_queryset.filter(content_item__course_id=course_id)

    latest_audit = failed_audit_queryset.first()
    latest_sync = failed_sync_queryset.first()
    latest_grader = failed_grader_queryset.first()

    return {
        "courseId": course_id,
        "failedAuditEvents": failed_audit_queryset.count(),
        "deniedAuditEvents": denied_audit_queryset.count(),
        "failedSyncEvents": failed_sync_queryset.count(),
        "failedGraderJobs": failed_grader_queryset.count(),
        "unresolvedAiConversations": ai_queryset.count(),
        "latestAuditFailureAt": latest_audit.created_at if latest_audit else None,
        "latestSyncFailureAt": latest_sync.created_at if latest_sync else None,
        "latestGraderFailureAt": latest_grader.created_at if latest_grader else None,
    }
