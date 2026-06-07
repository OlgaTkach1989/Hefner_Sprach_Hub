from __future__ import annotations

from collections.abc import Iterable

from django.contrib.auth.models import AnonymousUser
from django.contrib.contenttypes.models import ContentType

from apps.online.models import (
    OnlineAccessPolicy,
    OnlineCourse,
    OnlineCourseContentLibraryItem,
    OnlineCourseLessonSectionItem,
    OnlineCourseMaterial,
    OnlineWorkspace,
    OnlineWorkspaceContentItem,
)
from apps.training.models import TrainingAudience
from apps.training.services.access import active_audience_slugs_for_user, demo_role_catalog, primary_demo_role_for_user


ONLINE_ROLE_RESTRICTED_MODELS = (
    OnlineCourse,
    OnlineCourseMaterial,
    OnlineCourseContentLibraryItem,
    OnlineCourseLessonSectionItem,
    OnlineWorkspace,
    OnlineWorkspaceContentItem,
)

PUBLIC_GUEST_AUDIENCE_SLUG = "external-users"


def _policy_cache_key(instance) -> tuple[str, int]:
    return (instance._meta.label_lower, int(instance.pk))


def _dedupe_audiences(audiences: Iterable[TrainingAudience]) -> list[TrainingAudience]:
    seen: dict[int, TrainingAudience] = {}
    for audience in audiences:
        seen[audience.id] = audience
    return sorted(
        seen.values(),
        key=lambda audience: (audience.privilege_rank, audience.name, audience.id),
    )


def _privileged_bypass(user) -> bool:
    if not user or isinstance(user, AnonymousUser) or not user.is_authenticated:
        return False
    return bool(
        getattr(user, "is_superuser", False)
        or getattr(user, "is_admin", False)
        or hasattr(user, "lehrer_user")
    )


def online_access_policy_audiences_for_instance(instance) -> list[TrainingAudience]:
    if instance is None or getattr(instance, "pk", None) is None:
        return []

    content_type = ContentType.objects.get_for_model(instance.__class__)
    queryset = (
        OnlineAccessPolicy.objects.select_related("audience")
        .filter(
            content_type=content_type,
            object_id=instance.pk,
            audience__is_active=True,
        )
        .order_by("audience__privilege_rank", "audience__name", "audience_id")
    )
    return [policy.audience for policy in queryset]


def online_access_policy_audience_ids_for_instance(instance) -> list[int]:
    return [audience.id for audience in online_access_policy_audiences_for_instance(instance)]


def serialize_online_audience(audience: TrainingAudience) -> dict[str, object]:
    return {
        "id": audience.id,
        "slug": audience.slug,
        "name": audience.name,
        "shortLabel": audience.short_label or audience.name,
    }


def serialize_online_audiences(audiences: Iterable[TrainingAudience]) -> list[dict[str, object]]:
    return [serialize_online_audience(audience) for audience in audiences]


def online_access_policy_audiences_payload_for_instance(instance) -> list[dict[str, object]]:
    return serialize_online_audiences(online_access_policy_audiences_for_instance(instance))


def sync_online_access_policies_for_instance(*, instance, audience_ids: Iterable[int]) -> list[TrainingAudience]:
    if instance is None or getattr(instance, "pk", None) is None:
        return []

    normalized_ids = {
        int(audience_id)
        for audience_id in audience_ids
        if isinstance(audience_id, int) or (isinstance(audience_id, str) and str(audience_id).isdigit())
    }
    content_type = ContentType.objects.get_for_model(instance.__class__)
    existing_policies = {
        policy.audience_id: policy
        for policy in OnlineAccessPolicy.objects.filter(content_type=content_type, object_id=instance.pk)
    }

    stale_ids = [audience_id for audience_id in existing_policies if audience_id not in normalized_ids]
    if stale_ids:
        OnlineAccessPolicy.objects.filter(
            content_type=content_type,
            object_id=instance.pk,
            audience_id__in=stale_ids,
        ).delete()

    valid_audiences = {
        audience.id: audience
        for audience in TrainingAudience.objects.filter(id__in=normalized_ids, is_active=True)
    }
    for audience_id in normalized_ids:
        if audience_id in existing_policies or audience_id not in valid_audiences:
            continue
        OnlineAccessPolicy.objects.create(
            content_type=content_type,
            object_id=instance.pk,
            audience_id=audience_id,
        )

    return _dedupe_audiences(valid_audiences.values())


def inherited_online_access_policy_audiences(instance, *, _cache: dict[tuple[str, int], list[TrainingAudience]] | None = None) -> list[TrainingAudience]:
    if instance is None or getattr(instance, "pk", None) is None:
        return []

    cache = _cache if _cache is not None else {}
    cache_key = _policy_cache_key(instance)
    if cache_key in cache:
        return cache[cache_key]

    direct = online_access_policy_audiences_for_instance(instance)
    if direct:
        cache[cache_key] = _dedupe_audiences(direct)
        return cache[cache_key]

    inherited: list[TrainingAudience] = []
    if isinstance(instance, OnlineWorkspaceContentItem):
        if instance.linked_course_id:
            inherited = inherited_online_access_policy_audiences(instance.linked_course, _cache=cache)
        if not inherited:
            inherited = inherited_online_access_policy_audiences(instance.workspace, _cache=cache)
    elif isinstance(instance, OnlineCourseMaterial):
        inherited = inherited_online_access_policy_audiences(instance.course, _cache=cache)
    elif isinstance(instance, OnlineCourseLessonSectionItem):
        if instance.source_library_item_id:
            inherited = inherited_online_access_policy_audiences(instance.source_library_item, _cache=cache)
        if not inherited:
            inherited = inherited_online_access_policy_audiences(instance.section.lesson.course, _cache=cache)
    elif isinstance(instance, OnlineCourseContentLibraryItem):
        inherited = []
    elif isinstance(instance, OnlineWorkspace):
        inherited = []
    elif isinstance(instance, OnlineCourse):
        inherited = []

    cache[cache_key] = _dedupe_audiences(inherited)
    return cache[cache_key]


def online_access_payload_for_instance(instance, user) -> dict[str, object]:
    policy_audiences = inherited_online_access_policy_audiences(instance)
    required_labels = [audience.short_label or audience.name for audience in policy_audiences]
    required_slugs = [audience.slug for audience in policy_audiences]
    if not policy_audiences:
        return {
            "isAccessible": True,
            "requiredAudienceLabels": [],
            "requiredAudienceSlugs": [],
            "accessMessage": "",
        }

    if PUBLIC_GUEST_AUDIENCE_SLUG in required_slugs:
        return {
            "isAccessible": True,
            "requiredAudienceLabels": required_labels,
            "requiredAudienceSlugs": required_slugs,
            "accessMessage": "",
        }

    if _privileged_bypass(user):
        return {
            "isAccessible": True,
            "requiredAudienceLabels": required_labels,
            "requiredAudienceSlugs": required_slugs,
            "accessMessage": "",
        }

    if not user or isinstance(user, AnonymousUser) or not user.is_authenticated:
        return {
            "isAccessible": False,
            "requiredAudienceLabels": required_labels,
            "requiredAudienceSlugs": required_slugs,
            "accessMessage": "Sign in with an approved academy role to open this content.",
        }

    audience_slugs = active_audience_slugs_for_user(user)
    has_access = any(audience.slug in audience_slugs for audience in policy_audiences)
    return {
        "isAccessible": has_access,
        "requiredAudienceLabels": required_labels,
        "requiredAudienceSlugs": required_slugs,
        "accessMessage": "" if has_access else "Your current role does not allow access to this content. Contact an administrator.",
    }


def online_object_is_accessible_to_user(instance, user) -> bool:
    return bool(online_access_payload_for_instance(instance, user)["isAccessible"])


def online_role_catalog_payload() -> list[dict[str, object]]:
    return [
        {
            "slug": audience.slug,
            "name": audience.name,
            "shortLabel": audience.short_label or audience.name,
            "description": audience.description,
            "privilegeRank": audience.privilege_rank,
            "isInternal": audience.is_internal,
        }
        for audience in demo_role_catalog()
    ]


def active_online_demo_role_payload_for_user(user) -> dict[str, object] | None:
    active_role = primary_demo_role_for_user(user)
    if active_role is None:
        return None
    return {
        "slug": active_role.slug,
        "name": active_role.name,
        "shortLabel": active_role.short_label or active_role.name,
        "description": active_role.description,
        "privilegeRank": active_role.privilege_rank,
        "isInternal": active_role.is_internal,
    }
