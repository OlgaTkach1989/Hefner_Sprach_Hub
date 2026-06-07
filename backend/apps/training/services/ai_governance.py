from __future__ import annotations

from dataclasses import dataclass

from django.contrib.auth import get_user_model
from django.db.models import Count, OuterRef, Q, QuerySet, Subquery
from django.utils import timezone

from apps.online.models import OnlineCourse
from apps.training.models import (
    TrainingAiConversation,
    TrainingAiMessage,
    TrainingAiQuizAttempt,
    TrainingContentItem,
    TrainingCourseRoleAssignment,
)
from apps.training.services.knowledge_base import ensure_training_content_indexed

User = get_user_model()


class TrainingAiGovernanceError(RuntimeError):
    pass


@dataclass(frozen=True)
class TrainingKnowledgeRebuildResult:
    rebuilt_content_items: int
    rebuilt_chunks: int
    filters: dict[str, object]


def build_training_ai_governance_overview(*, course_id: int | None = None) -> dict[str, object]:
    content_queryset = TrainingContentItem.objects.all()
    conversation_queryset = TrainingAiConversation.objects.select_related("content_item__course")
    quiz_queryset = TrainingAiQuizAttempt.objects.select_related("content_item__course")
    message_queryset = TrainingAiMessage.objects.select_related("content_item__course")

    if course_id is not None:
        content_queryset = content_queryset.filter(course_id=course_id)
        conversation_queryset = conversation_queryset.filter(content_item__course_id=course_id)
        quiz_queryset = quiz_queryset.filter(content_item__course_id=course_id)
        message_queryset = message_queryset.filter(content_item__course_id=course_id)

    faq_items = content_queryset.filter(content_kind=TrainingContentItem.ContentKind.FAQ)
    non_faq_content = content_queryset.exclude(content_kind=TrainingContentItem.ContentKind.FAQ)
    content_with_faq_links = non_faq_content.filter(
        Q(outgoing_references__to_item__content_kind=TrainingContentItem.ContentKind.FAQ)
        | Q(incoming_references__from_item__content_kind=TrainingContentItem.ContentKind.FAQ)
    ).distinct()
    indexed_content_items = content_queryset.filter(knowledge_chunks__is_active=True).distinct()
    unresolved_queue_queryset = unresolved_training_ai_conversations_queryset(
        course_id=course_id,
        include_resolved=False,
    )

    content_total = non_faq_content.count()
    covered_total = content_with_faq_links.count()
    faq_coverage_percent = round((covered_total / content_total) * 100, 1) if content_total > 0 else 0.0

    return {
        "courseId": course_id,
        "aiConversations": conversation_queryset.count(),
        "distinctLearners": conversation_queryset.values("user_id").distinct().count(),
        "aiQuestions": message_queryset.filter(role=TrainingAiMessage.Role.USER).count(),
        "resolvedResponses": message_queryset.filter(
            role=TrainingAiMessage.Role.ASSISTANT,
            resolution_status=TrainingAiMessage.ResolutionStatus.RESOLVED,
        ).count(),
        "partialResponses": message_queryset.filter(
            role=TrainingAiMessage.Role.ASSISTANT,
            resolution_status=TrainingAiMessage.ResolutionStatus.PARTIAL,
        ).count(),
        "escalatedResponses": message_queryset.filter(
            role=TrainingAiMessage.Role.ASSISTANT,
            resolution_status=TrainingAiMessage.ResolutionStatus.ESCALATE,
        ).count(),
        "unresolvedQueueCount": unresolved_queue_queryset.count(),
        "assignedQueueCount": unresolved_queue_queryset.exclude(assigned_to__isnull=True).count(),
        "resolvedConversations": conversation_queryset.filter(
            governance_status=TrainingAiConversation.GovernanceStatus.RESOLVED
        ).count(),
        "archivedConversations": conversation_queryset.filter(
            governance_status=TrainingAiConversation.GovernanceStatus.ARCHIVED
        ).count(),
        "faqItems": faq_items.count(),
        "contentItemsCoveredByFaq": covered_total,
        "faqCoveragePercent": faq_coverage_percent,
        "indexedContentItems": indexed_content_items.count(),
        "indexedChunks": content_queryset.aggregate(
            total=Count("knowledge_chunks", filter=Q(knowledge_chunks__is_active=True))
        )["total"] or 0,
        "generatedQuizzes": quiz_queryset.count(),
        "completedQuizzes": quiz_queryset.filter(status=TrainingAiQuizAttempt.Status.COMPLETED).count(),
    }


def unresolved_training_ai_conversations_queryset(
    *,
    course_id: int | None = None,
    include_resolved: bool,
) -> QuerySet[TrainingAiConversation]:
    latest_assistant_messages = TrainingAiMessage.objects.filter(
        conversation=OuterRef("pk"),
        role=TrainingAiMessage.Role.ASSISTANT,
    ).order_by("-created_at", "-id")
    latest_owner_assignment = TrainingCourseRoleAssignment.objects.filter(
        course_id=OuterRef("content_item__course_id"),
        role=TrainingCourseRoleAssignment.Role.OWNER,
    ).order_by("-is_primary", "response_sla_hours", "id")

    queryset = (
        TrainingAiConversation.objects.select_related(
            "content_item__course",
            "assigned_to",
            "resolved_by",
            "user",
        )
        .annotate(
            latest_resolution_status=Subquery(latest_assistant_messages.values("resolution_status")[:1]),
            latest_assistant_body=Subquery(latest_assistant_messages.values("body")[:1]),
            latest_assistant_created_at=Subquery(latest_assistant_messages.values("created_at")[:1]),
            latest_assistant_id=Subquery(latest_assistant_messages.values("id")[:1]),
            recommended_owner_id=Subquery(latest_owner_assignment.values("user_id")[:1]),
            recommended_owner_sla_hours=Subquery(latest_owner_assignment.values("response_sla_hours")[:1]),
            user_message_count=Count("messages", filter=Q(messages__role=TrainingAiMessage.Role.USER), distinct=True),
            assistant_message_count=Count("messages", filter=Q(messages__role=TrainingAiMessage.Role.ASSISTANT), distinct=True),
        )
        .exclude(latest_assistant_id__isnull=True)
        .order_by("-last_activity_at", "-id")
    )

    if course_id is not None:
        queryset = queryset.filter(content_item__course_id=course_id)
    if not include_resolved:
        queryset = queryset.filter(
            governance_status__in=(
                TrainingAiConversation.GovernanceStatus.OPEN,
                TrainingAiConversation.GovernanceStatus.IN_REVIEW,
            ),
            latest_resolution_status__in=(
                TrainingAiMessage.ResolutionStatus.PARTIAL,
                TrainingAiMessage.ResolutionStatus.ESCALATE,
            ),
        )
    return queryset


def validate_ai_conversation_assignee(*, conversation: TrainingAiConversation, assigned_to_id: int | None):
    if assigned_to_id is None:
        return None
    user = User.objects.filter(id=assigned_to_id, is_active=True).first()
    if user is None:
        raise TrainingAiGovernanceError("Assigned user was not found.")
    if getattr(user, "is_admin", False) or getattr(user, "is_superuser", False):
        return user
    if conversation.content_item_id and TrainingCourseRoleAssignment.objects.filter(
        course_id=conversation.content_item.course_id,
        user_id=assigned_to_id,
    ).exists():
        return user
    raise TrainingAiGovernanceError("Assigned user must be an admin or hold a course role.")


def update_training_ai_conversation_governance(
    *,
    conversation: TrainingAiConversation,
    actor,
    governance_status: str | None = None,
    assigned_to_id: int | None = None,
    assigned_to_provided: bool = False,
    resolution_note: str | None = None,
) -> TrainingAiConversation:
    assigned_user = conversation.assigned_to
    if assigned_to_provided:
        assigned_user = validate_ai_conversation_assignee(conversation=conversation, assigned_to_id=assigned_to_id)
        conversation.assigned_to = assigned_user

    if resolution_note is not None:
        conversation.resolution_note = str(resolution_note or "").strip()[:255]

    if governance_status:
        if not _governance_transition_allowed(
            current_status=conversation.governance_status,
            target_status=governance_status,
        ):
            raise TrainingAiGovernanceError("Invalid AI governance state transition.")
        conversation.governance_status = governance_status
        if governance_status == TrainingAiConversation.GovernanceStatus.IN_REVIEW and assigned_user is None:
            raise TrainingAiGovernanceError("Assign a user before moving the conversation into review.")
        if governance_status == TrainingAiConversation.GovernanceStatus.RESOLVED:
            conversation.resolved_by = actor
            conversation.resolved_at = timezone.now()
            conversation.status = TrainingAiConversation.Status.ACTIVE
        elif governance_status == TrainingAiConversation.GovernanceStatus.ARCHIVED:
            conversation.status = TrainingAiConversation.Status.ARCHIVED
        else:
            conversation.status = TrainingAiConversation.Status.ACTIVE
            if governance_status != TrainingAiConversation.GovernanceStatus.RESOLVED:
                conversation.resolved_by = None
                conversation.resolved_at = None

    conversation.save(
        update_fields=(
            "assigned_to",
            "resolution_note",
            "governance_status",
            "resolved_by",
            "resolved_at",
            "status",
            "updated_at",
        )
    )
    return conversation


def _governance_transition_allowed(*, current_status: str, target_status: str) -> bool:
    if current_status == target_status:
        return True
    allowed_targets = {
        TrainingAiConversation.GovernanceStatus.OPEN: {
            TrainingAiConversation.GovernanceStatus.IN_REVIEW,
            TrainingAiConversation.GovernanceStatus.RESOLVED,
            TrainingAiConversation.GovernanceStatus.ARCHIVED,
        },
        TrainingAiConversation.GovernanceStatus.IN_REVIEW: {
            TrainingAiConversation.GovernanceStatus.OPEN,
            TrainingAiConversation.GovernanceStatus.RESOLVED,
            TrainingAiConversation.GovernanceStatus.ARCHIVED,
        },
        TrainingAiConversation.GovernanceStatus.RESOLVED: {
            TrainingAiConversation.GovernanceStatus.ARCHIVED,
        },
        TrainingAiConversation.GovernanceStatus.ARCHIVED: set(),
    }
    return target_status in allowed_targets.get(current_status, set())


def rebuild_training_knowledge_index_for_admin(
    *,
    course_id: int | None = None,
    content_slug: str = "",
) -> TrainingKnowledgeRebuildResult:
    queryset = TrainingContentItem.objects.filter(status=TrainingContentItem.Status.PUBLISHED).order_by("course_id", "name", "id")
    filters: dict[str, object] = {}
    if course_id is not None:
        queryset = queryset.filter(course_id=course_id)
        filters["courseId"] = course_id
    normalized_slug = str(content_slug or "").strip()
    if normalized_slug:
        queryset = queryset.filter(slug=normalized_slug)
        filters["contentSlug"] = normalized_slug

    rebuilt_content_items = 0
    rebuilt_chunks = 0
    for content_item in queryset.iterator():
        chunks = ensure_training_content_indexed(content_item)
        rebuilt_content_items += 1
        rebuilt_chunks += len(chunks)

    return TrainingKnowledgeRebuildResult(
        rebuilt_content_items=rebuilt_content_items,
        rebuilt_chunks=rebuilt_chunks,
        filters=filters,
    )
