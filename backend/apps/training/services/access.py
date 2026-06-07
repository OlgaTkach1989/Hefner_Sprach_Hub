from __future__ import annotations

from django.contrib.auth.models import AnonymousUser
from django.db.models import Prefetch, Q, QuerySet
from django.utils import timezone

from apps.online.models import OnlineEnrollment
from apps.training.models import (
    TrainingAudience,
    TrainingContentAudiencePolicy,
    TrainingContentCrossReference,
    TrainingContentItem,
    TrainingCourseRoleAssignment,
    TrainingUserAudienceGrant,
)


ACTIVE_ENROLLMENT_STATUSES = (
    OnlineEnrollment.STATUS_TRIAL,
    OnlineEnrollment.STATUS_ACTIVE,
    OnlineEnrollment.STATUS_COMPLETED,
)


def active_audience_grants_for_user(user) -> list[TrainingUserAudienceGrant]:
    if not user or isinstance(user, AnonymousUser) or not user.is_authenticated:
        return []

    now = timezone.now()
    return list(
        TrainingUserAudienceGrant.objects.select_related("audience")
        .filter(user=user, audience__is_active=True)
        .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
        .order_by("audience__audience_type", "audience__privilege_rank", "audience__name", "audience__id")
    )


def granted_audiences_for_user(user) -> list[TrainingAudience]:
    return [grant.audience for grant in active_audience_grants_for_user(user)]


def demo_role_catalog() -> list[TrainingAudience]:
    return list(
        TrainingAudience.objects.filter(
            is_active=True,
            audience_type=TrainingAudience.AudienceType.DEMO_ROLE,
        ).order_by("privilege_rank", "name", "id")
    )


def primary_demo_role_for_user(user) -> TrainingAudience | None:
    granted_demo_roles = [
        audience
        for audience in granted_audiences_for_user(user)
        if audience.audience_type == TrainingAudience.AudienceType.DEMO_ROLE
    ]
    if not granted_demo_roles:
        return None
    return max(granted_demo_roles, key=lambda audience: (audience.privilege_rank, audience.id))


def effective_audiences_for_user(user) -> list[TrainingAudience]:
    granted_audiences = granted_audiences_for_user(user)
    if not granted_audiences:
        return []

    granted_by_id = {audience.id: audience for audience in granted_audiences}
    primary_demo_role = max(
        (
            audience
            for audience in granted_audiences
            if audience.audience_type == TrainingAudience.AudienceType.DEMO_ROLE
        ),
        default=None,
        key=lambda audience: (audience.privilege_rank, audience.id),
    )
    if primary_demo_role is not None:
        inherited_demo_roles = demo_role_catalog()
        for audience in inherited_demo_roles:
            if audience.privilege_rank <= primary_demo_role.privilege_rank:
                granted_by_id[audience.id] = audience

    return sorted(
        granted_by_id.values(),
        key=lambda audience: (audience.audience_type, audience.privilege_rank, audience.name, audience.id),
    )


def active_audience_slugs_for_user(user) -> set[str]:
    return {audience.slug for audience in effective_audiences_for_user(user)}


def accessible_course_ids_for_user(user) -> set[int]:
    if not user or isinstance(user, AnonymousUser) or not user.is_authenticated:
        return set()

    enrollment_course_ids = set(
        OnlineEnrollment.objects.filter(
            profile__user=user,
            status__in=ACTIVE_ENROLLMENT_STATUSES,
        ).values_list("course_id", flat=True)
    )
    role_course_ids = set(
        TrainingCourseRoleAssignment.objects.filter(user=user).values_list("course_id", flat=True)
    )
    return enrollment_course_ids | role_course_ids


def content_item_is_visible_to_user(
    item: TrainingContentItem,
    user,
    *,
    audience_slugs: set[str] | None = None,
    accessible_course_ids: set[int] | None = None,
) -> bool:
    if item.status != TrainingContentItem.Status.PUBLISHED:
        return False

    if item.access_scope == TrainingContentItem.AccessScope.PUBLIC:
        return True

    if not user or isinstance(user, AnonymousUser) or not user.is_authenticated:
        return False

    if getattr(user, "is_superuser", False) or getattr(user, "is_admin", False):
        return True

    if item.access_scope == TrainingContentItem.AccessScope.AUTHENTICATED:
        return True

    if audience_slugs is None:
        audience_slugs = active_audience_slugs_for_user(user)
    if accessible_course_ids is None:
        accessible_course_ids = accessible_course_ids_for_user(user)

    if item.course_id and item.course_id not in accessible_course_ids:
        return False

    policy_audience_slugs = [
        policy.audience.slug
        for policy in item.audience_policies.all()
        if policy.audience.is_active
    ]
    if not policy_audience_slugs:
        return bool(item.course_id)

    if item.audience_match_mode == TrainingContentItem.AudienceMatchMode.ALL:
        return all(slug in audience_slugs for slug in policy_audience_slugs)
    return any(slug in audience_slugs for slug in policy_audience_slugs)


def base_content_queryset(*, include_references: bool = True) -> QuerySet[TrainingContentItem]:
    queryset = (
        TrainingContentItem.objects.select_related("course", "lab_profile")
        .prefetch_related(
            "asset_classes",
            "topics",
            Prefetch(
                "audience_policies",
                queryset=TrainingContentAudiencePolicy.objects.select_related("audience"),
            ),
        )
    )
    if include_references:
        queryset = queryset.prefetch_related(
            Prefetch(
                "outgoing_references",
                queryset=TrainingContentCrossReference.objects.select_related("to_item"),
            )
        )
    return queryset


def visible_content_items_for_user(
    user,
    *,
    base_queryset: QuerySet[TrainingContentItem] | None = None,
) -> list[TrainingContentItem]:
    queryset = base_queryset if base_queryset is not None else base_content_queryset()
    audience_slugs = active_audience_slugs_for_user(user)
    course_ids = accessible_course_ids_for_user(user)
    return [
        item
        for item in queryset
        if content_item_is_visible_to_user(
            item,
            user,
            audience_slugs=audience_slugs,
            accessible_course_ids=course_ids,
        )
    ]
