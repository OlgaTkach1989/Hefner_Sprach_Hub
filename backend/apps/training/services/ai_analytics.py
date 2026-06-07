from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone as dt_timezone
import hashlib

from django.conf import settings
from django.utils import timezone

from apps.training.models import (
    TrainingAiConversation,
    TrainingAuditEvent,
    TrainingContentItem,
    TrainingContentSyncEvent,
)
from apps.training.services.knowledge_base import build_training_content_source_text


def build_training_ai_admin_analytics(*, course_id: int | None = None, window_days: int = 7) -> dict[str, object]:
    safe_window_days = max(1, min(int(window_days or 7), 90))
    window_start = timezone.now() - timedelta(days=safe_window_days)

    audit_queryset = TrainingAuditEvent.objects.select_related("content_item")
    conversation_queryset = TrainingAiConversation.objects.select_related("content_item")
    content_queryset = (
        TrainingContentItem.objects.select_related("course", "owner")
        .prefetch_related("knowledge_chunks", "audience_policies")
        .all()
    )
    sync_event_queryset = (
        TrainingContentSyncEvent.objects.select_related("content_item")
        .filter(source=TrainingContentSyncEvent.Source.DIRECTUS)
    )

    if course_id is not None:
        audit_queryset = audit_queryset.filter(course_id=course_id)
        conversation_queryset = conversation_queryset.filter(content_item__course_id=course_id)
        content_queryset = content_queryset.filter(course_id=course_id)
        sync_event_queryset = sync_event_queryset.filter(content_item__course_id=course_id)

    window_audits = audit_queryset.filter(created_at__gte=window_start)
    window_sync_events = sync_event_queryset.filter(created_at__gte=window_start)

    resolved_conversations = list(
        conversation_queryset.filter(
            governance_status=TrainingAiConversation.GovernanceStatus.RESOLVED,
            resolved_at__isnull=False,
        )
    )
    avg_resolution_hours = _average_resolution_hours(resolved_conversations)

    published_content_items = 0
    directus_managed_content_items = 0
    directus_items_without_owner = 0
    unindexed_published_items = 0
    stale_indexed_published_items = 0

    for content_item in content_queryset:
        if content_item.authoring_source == TrainingContentItem.AuthoringSource.DIRECTUS:
            directus_managed_content_items += 1
            if content_item.owner_id is None:
                directus_items_without_owner += 1

        if content_item.status != TrainingContentItem.Status.PUBLISHED:
            continue

        published_content_items += 1
        active_chunks = [chunk for chunk in content_item.knowledge_chunks.all() if chunk.is_active]
        if not active_chunks or content_item.knowledge_indexed_at is None:
            unindexed_published_items += 1
            continue
        current_source_checksum = hashlib.sha256(
            build_training_content_source_text(content_item).encode("utf-8")
        ).hexdigest()
        active_source_checksums = {chunk.source_checksum for chunk in active_chunks}
        if (
            content_item.knowledge_indexed_at < content_item.updated_at
            or current_source_checksum not in active_source_checksums
        ):
            stale_indexed_published_items += 1

    latest_index_rebuild_audit = (
        audit_queryset.filter(event_type=TrainingAuditEvent.EventType.ADMIN_AI_INDEX_REBUILT)
        .order_by("-created_at", "-id")
        .first()
    )
    latest_directus_sync_event = sync_event_queryset.order_by("-created_at", "-id").first()
    latest_successful_sync_event = (
        sync_event_queryset.filter(status=TrainingContentSyncEvent.Status.SUCCEEDED)
        .order_by("-created_at", "-id")
        .first()
    )
    last_knowledge_refresh_at = max(
        [
            value
            for value in (
                latest_index_rebuild_audit.created_at if latest_index_rebuild_audit is not None else None,
                latest_successful_sync_event.created_at if latest_successful_sync_event is not None else None,
            )
            if value is not None
        ],
        default=None,
    )

    top_content_items = _build_top_content_items(
        audit_queryset=window_audits,
        conversation_queryset=conversation_queryset,
    )

    provider_mode = str(getattr(settings, "TRAINING_AI_PROVIDER", "demo") or "demo").strip() or "demo"
    external_provider_configured = bool(
        str(getattr(settings, "TRAINING_AI_API_KEY", "") or "").strip()
        and (provider_mode == "demo" or str(getattr(settings, "TRAINING_AI_BASE_URL", "") or "").strip() or provider_mode)
    )

    ai_questions_window = window_audits.filter(
        event_type=TrainingAuditEvent.EventType.AI_QUESTION_ASKED
    ).count()
    ai_failures_window = window_audits.filter(
        event_type=TrainingAuditEvent.EventType.AI_RESPONSE_FAILED
    ).count()
    escalations_window = window_audits.filter(
        event_type=TrainingAuditEvent.EventType.AI_ESCALATION_SUGGESTED
    ).count()
    quiz_failures_window = window_audits.filter(
        event_type=TrainingAuditEvent.EventType.AI_QUIZ_SUBMIT_FAILED
    ).count()

    return {
        "courseId": course_id,
        "aiQuestionsLast7Days": ai_questions_window,
        "aiFailuresLast7Days": ai_failures_window,
        "quizFailuresLast7Days": quiz_failures_window,
        "escalationsLast7Days": escalations_window,
        "avgResolutionHours": avg_resolution_hours,
        "publishedContentItems": published_content_items,
        "directusManagedContentItems": directus_managed_content_items,
        "directusItemsWithoutOwner": directus_items_without_owner,
        "unindexedPublishedItems": unindexed_published_items,
        "staleIndexedPublishedItems": stale_indexed_published_items,
        "directusSyncFailuresLast7Days": window_sync_events.filter(
            status=TrainingContentSyncEvent.Status.FAILED,
        ).count(),
        "lastDirectusSyncAt": latest_directus_sync_event.created_at if latest_directus_sync_event is not None else None,
        "lastKnowledgeRefreshAt": last_knowledge_refresh_at,
        "windowDays": safe_window_days,
        "providerMode": provider_mode,
        "externalProviderConfigured": external_provider_configured,
        "pgvectorEnabled": bool(getattr(settings, "TRAINING_AI_PGVECTOR_ENABLED", False)),
        "aiQuestionsWindow": ai_questions_window,
        "aiResponseFailuresWindow": ai_failures_window,
        "aiEscalationsWindow": escalations_window,
        "quizSubmitFailuresWindow": quiz_failures_window,
        "contentAccessDeniedWindow": window_audits.filter(
            event_type=TrainingAuditEvent.EventType.CONTENT_ACCESS_DENIED
        ).count(),
        "directusSyncAppliedWindow": window_sync_events.filter(
            status=TrainingContentSyncEvent.Status.SUCCEEDED,
        ).count(),
        "directusSyncFailedWindow": window_sync_events.filter(
            status=TrainingContentSyncEvent.Status.FAILED,
        ).count(),
        "unresolvedQueueCount": conversation_queryset.filter(
            governance_status__in=(
                TrainingAiConversation.GovernanceStatus.OPEN,
                TrainingAiConversation.GovernanceStatus.IN_REVIEW,
            )
        ).count(),
        "staleIndexedContentCount": stale_indexed_published_items,
        "latestIndexRebuildAt": latest_index_rebuild_audit.created_at if latest_index_rebuild_audit is not None else None,
        "latestIndexRebuildOutcome": latest_index_rebuild_audit.outcome if latest_index_rebuild_audit is not None else "",
        "latestDirectusSyncAt": latest_directus_sync_event.created_at if latest_directus_sync_event is not None else None,
        "latestDirectusSyncOutcome": (
            latest_directus_sync_event.status if latest_directus_sync_event is not None else ""
        ),
        "topContentItems": top_content_items,
    }


def _average_resolution_hours(resolved_conversations: list[TrainingAiConversation]) -> float | None:
    resolution_hours = [
        round((conversation.resolved_at - conversation.created_at).total_seconds() / 3600, 2)
        for conversation in resolved_conversations
        if conversation.resolved_at and conversation.created_at
    ]
    if not resolution_hours:
        return None
    return round(sum(resolution_hours) / len(resolution_hours), 2)


def _build_top_content_items(*, audit_queryset, conversation_queryset) -> list[dict[str, object]]:
    ai_question_stats: dict[int, dict[str, object]] = defaultdict(
        lambda: {"aiQuestions": 0, "accessDeniedCount": 0, "latestQuestionAt": None}
    )

    for audit_event in audit_queryset:
        content_item_id = audit_event.content_item_id
        if not content_item_id:
            continue
        entry = ai_question_stats[content_item_id]
        if audit_event.event_type == TrainingAuditEvent.EventType.AI_QUESTION_ASKED:
            entry["aiQuestions"] += 1
            if entry["latestQuestionAt"] is None or audit_event.created_at > entry["latestQuestionAt"]:
                entry["latestQuestionAt"] = audit_event.created_at
        elif audit_event.event_type == TrainingAuditEvent.EventType.CONTENT_ACCESS_DENIED:
            entry["accessDeniedCount"] += 1

    unresolved_counts: dict[int, int] = defaultdict(int)
    content_items_by_id: dict[int, TrainingContentItem] = {}
    for conversation in conversation_queryset.select_related("content_item"):
        if conversation.content_item_id:
            content_items_by_id[conversation.content_item_id] = conversation.content_item
        if conversation.content_item_id and conversation.governance_status in {
            TrainingAiConversation.GovernanceStatus.OPEN,
            TrainingAiConversation.GovernanceStatus.IN_REVIEW,
        }:
            unresolved_counts[conversation.content_item_id] += 1

    ranked_rows: list[dict[str, object]] = []
    content_ids = set(ai_question_stats.keys()) | set(unresolved_counts.keys())
    if not content_ids:
        return ranked_rows

    if len(content_items_by_id) != len(content_ids):
        for content_item in TrainingContentItem.objects.filter(id__in=content_ids):
            content_items_by_id[content_item.id] = content_item

    for content_id in content_ids:
        content_item = content_items_by_id.get(content_id)
        if content_item is None:
            continue
        stats = ai_question_stats[content_id]
        ranked_rows.append(
            {
                "contentId": content_item.id,
                "slug": content_item.slug,
                "name": content_item.name,
                "aiQuestions": int(stats["aiQuestions"]),
                "unresolvedConversations": unresolved_counts[content_id],
                "accessDeniedCount": int(stats["accessDeniedCount"]),
                "latestQuestionAt": stats["latestQuestionAt"],
            }
        )

    ranked_rows.sort(
        key=lambda item: (
            -int(item["aiQuestions"]),
            -int(item["unresolvedConversations"]),
            -int(item["accessDeniedCount"]),
            item["latestQuestionAt"] or datetime.min.replace(tzinfo=dt_timezone.utc),
        )
    )
    return ranked_rows[:5]
