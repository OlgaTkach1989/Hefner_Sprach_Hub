from __future__ import annotations

from dataclasses import dataclass
import hashlib

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.online.models import OnlineCourse
from apps.training.models import (
    TrainingAssetClass,
    TrainingAudience,
    TrainingContentAudiencePolicy,
    TrainingContentCrossReference,
    TrainingContentItem,
    TrainingContentSyncEvent,
    TrainingTopic,
)
from apps.training.services.knowledge_base import deactivate_training_content_index, ensure_training_content_indexed

User = get_user_model()


class TrainingDirectusSyncError(RuntimeError):
    pass


@dataclass(frozen=True)
class TrainingDirectusSyncResult:
    action: str
    content_item_id: int | None
    slug: str
    status: str
    index_action: str
    indexed_chunks: int
    warnings: list[str]


@transaction.atomic
def sync_training_content_from_directus(payload: dict) -> TrainingDirectusSyncResult:
    operation = str(payload.get("operation") or "upsert").strip().lower()
    if operation not in {"upsert", "delete"}:
        raise TrainingDirectusSyncError("Unsupported Directus sync operation.")

    external_id = str(payload.get("externalId") or "").strip()
    slug = str(payload.get("slug") or "").strip()
    if operation == "delete" and not external_id:
        raise TrainingDirectusSyncError("Delete operations require a stable externalId.")
    content_item = _find_existing_content_item(
        external_id=external_id,
        slug=slug,
        require_stable_identity=operation == "delete",
    )
    warnings: list[str] = []

    if operation == "delete":
        if content_item is None:
            raise TrainingDirectusSyncError("Directus content item was not found for delete operation.")
        content_item.status = TrainingContentItem.Status.RETIRED
        content_item.published_at = None
        content_item.last_synced_at = timezone.now()
        content_item.authoring_source = TrainingContentItem.AuthoringSource.DIRECTUS
        if external_id:
            content_item.authoring_source_id = external_id
        content_item.save(update_fields=("status", "published_at", "last_synced_at", "authoring_source", "authoring_source_id", "updated_at"))
        deactivate_training_content_index(content_item)
        TrainingContentSyncEvent.objects.create(
            content_item=content_item,
            source=TrainingContentSyncEvent.Source.DIRECTUS,
            event_type=TrainingContentSyncEvent.EventType.UNPUBLISH,
            status=TrainingContentSyncEvent.Status.SUCCEEDED,
            external_source_id=external_id,
            content_slug=content_item.slug,
            detail="Content retired from Directus delete event.",
            payload_summary=_build_payload_summary(payload),
        )
        return TrainingDirectusSyncResult(
            action="deleted",
            content_item_id=content_item.id,
            slug=content_item.slug,
            status=content_item.status,
            index_action="deactivated",
            indexed_chunks=0,
            warnings=warnings,
        )

    if content_item is None:
        content_item = TrainingContentItem(
            slug=slug,
            content_kind=payload.get("contentKind") or TrainingContentItem.ContentKind.ARTICLE,
        )
        action = "created"
    else:
        action = "updated"

    content_item.slug = slug
    content_item.name = str(payload.get("name") or "").strip()
    content_item.description = str(payload.get("description") or "").strip()
    content_item.body_markdown = str(payload.get("bodyMarkdown") or "").strip()
    content_item.content_kind = str(payload.get("contentKind") or TrainingContentItem.ContentKind.ARTICLE)
    content_item.status = str(payload.get("status") or TrainingContentItem.Status.PUBLISHED)
    content_item.access_scope = str(payload.get("accessScope") or TrainingContentItem.AccessScope.ENTITLED)
    content_item.difficulty = str(payload.get("difficulty") or TrainingContentItem.Difficulty.INTERMEDIATE)
    content_item.audience_match_mode = str(
        payload.get("audienceMatchMode") or TrainingContentItem.AudienceMatchMode.ANY
    )
    content_item.course = _resolve_course(str(payload.get("courseSlug") or "").strip())
    content_item.owner = _resolve_owner(str(payload.get("ownerEmail") or "").strip())
    content_item.authoring_source = TrainingContentItem.AuthoringSource.DIRECTUS
    content_item.authoring_source_id = external_id
    content_item.authoring_checksum = _build_authoring_checksum(payload)
    content_item.last_synced_at = timezone.now()
    content_item.source_url = str(payload.get("sourceUrl") or "").strip() or None
    content_item.search_keywords = str(payload.get("searchKeywords") or "").strip()
    content_item.version_label = str(payload.get("versionLabel") or "").strip()
    content_item.estimated_minutes = int(payload.get("estimatedMinutes") or 0)
    content_item.is_repeatable_on_demand = bool(payload.get("isRepeatableOnDemand", True))
    content_item.supports_inline_lab = bool(payload.get("supportsInlineLab", False))
    content_item.published_at = payload.get("publishedAt") if content_item.status == TrainingContentItem.Status.PUBLISHED else None
    content_item.save()

    _sync_asset_classes(content_item=content_item, raw_items=payload.get("assetClasses") or [])
    _sync_topics(content_item=content_item, raw_items=payload.get("topics") or [])
    _sync_audience_policies(content_item=content_item, audience_slugs=payload.get("audienceSlugs") or [])
    warnings.extend(
        _sync_cross_references(content_item=content_item, raw_references=payload.get("crossReferences") or [])
    )

    if content_item.status == TrainingContentItem.Status.PUBLISHED:
        indexed_chunks = len(ensure_training_content_indexed(content_item))
        index_action = "rebuilt"
        event_type = TrainingContentSyncEvent.EventType.UPSERT
    else:
        indexed_chunks = 0
        deactivate_training_content_index(content_item)
        index_action = "deactivated"
        event_type = TrainingContentSyncEvent.EventType.UNPUBLISH

    TrainingContentSyncEvent.objects.create(
        content_item=content_item,
        source=TrainingContentSyncEvent.Source.DIRECTUS,
        event_type=event_type,
        status=TrainingContentSyncEvent.Status.SUCCEEDED,
        external_source_id=external_id,
        content_slug=content_item.slug,
        detail="Directus content sync applied.",
        payload_summary=_build_payload_summary(payload),
    )

    return TrainingDirectusSyncResult(
        action=action,
        content_item_id=content_item.id,
        slug=content_item.slug,
        status=content_item.status,
        index_action=index_action,
        indexed_chunks=indexed_chunks,
        warnings=warnings,
    )


def record_failed_training_directus_sync(payload: dict, *, reason: str) -> TrainingContentSyncEvent:
    operation = str(payload.get("operation") or "upsert").strip().lower()
    return TrainingContentSyncEvent.objects.create(
        source=TrainingContentSyncEvent.Source.DIRECTUS,
        event_type=(
            TrainingContentSyncEvent.EventType.UNPUBLISH
            if operation == "delete"
            else TrainingContentSyncEvent.EventType.UPSERT
        ),
        status=TrainingContentSyncEvent.Status.FAILED,
        external_source_id=str(payload.get("externalId") or "").strip(),
        content_slug=str(payload.get("slug") or "").strip(),
        detail=reason[:255],
        payload_summary=_build_payload_summary(payload),
    )


def _find_existing_content_item(
    *,
    external_id: str,
    slug: str,
    require_stable_identity: bool,
) -> TrainingContentItem | None:
    if external_id:
        directus_match = TrainingContentItem.objects.filter(
            authoring_source=TrainingContentItem.AuthoringSource.DIRECTUS,
            authoring_source_id=external_id,
        ).first()
        if directus_match is not None:
            return directus_match
    if slug:
        slug_match = TrainingContentItem.objects.filter(slug=slug).first()
        if slug_match is None:
            return None
        if slug_match.authoring_source != TrainingContentItem.AuthoringSource.DIRECTUS:
            raise TrainingDirectusSyncError(
                "Directus sync cannot overwrite manually managed content by slug. Provide a stable externalId."
            )
        if external_id and slug_match.authoring_source_id and slug_match.authoring_source_id != external_id:
            raise TrainingDirectusSyncError(
                "Directus sync externalId does not match the existing managed content identity."
            )
        if require_stable_identity and not slug_match.authoring_source_id:
            raise TrainingDirectusSyncError(
                "Directus-managed content is missing a stable external source id and cannot be synced safely."
            )
        return slug_match
    return None


def _resolve_course(course_slug: str) -> OnlineCourse | None:
    if not course_slug:
        return None
    course = OnlineCourse.objects.filter(slug=course_slug).first()
    if course is None:
        raise TrainingDirectusSyncError("Referenced course slug was not found.")
    return course


def _resolve_owner(owner_email: str):
    if not owner_email:
        return None
    owner = User.objects.filter(email__iexact=owner_email, is_active=True).first()
    if owner is None:
        raise TrainingDirectusSyncError("Referenced owner email was not found.")
    return owner


def _sync_asset_classes(*, content_item: TrainingContentItem, raw_items: list) -> None:
    asset_class_ids: list[int] = []
    for item in raw_items:
        slug, name, description = _taxonomy_payload(item)
        if not slug:
            continue
        asset_class, _ = TrainingAssetClass.objects.get_or_create(
            slug=slug,
            defaults={
                "name": name or _fallback_name(slug),
                "description": description,
            },
        )
        updated_fields: list[str] = []
        if name and asset_class.name != name:
            asset_class.name = name
            updated_fields.append("name")
        if description and asset_class.description != description:
            asset_class.description = description
            updated_fields.append("description")
        if updated_fields:
            updated_fields.append("updated_at")
            asset_class.save(update_fields=updated_fields)
        asset_class_ids.append(asset_class.id)
    content_item.asset_classes.set(asset_class_ids)


def _sync_topics(*, content_item: TrainingContentItem, raw_items: list) -> None:
    topic_ids: list[int] = []
    for item in raw_items:
        slug, name, description = _taxonomy_payload(item)
        if not slug:
            continue
        topic, _ = TrainingTopic.objects.get_or_create(
            slug=slug,
            defaults={
                "name": name or _fallback_name(slug),
                "description": description,
            },
        )
        updated_fields: list[str] = []
        if name and topic.name != name:
            topic.name = name
            updated_fields.append("name")
        if description and topic.description != description:
            topic.description = description
            updated_fields.append("description")
        if updated_fields:
            updated_fields.append("updated_at")
            topic.save(update_fields=updated_fields)
        topic_ids.append(topic.id)
    content_item.topics.set(topic_ids)


def _sync_audience_policies(*, content_item: TrainingContentItem, audience_slugs: list[str]) -> None:
    normalized_slugs = [str(slug or "").strip() for slug in audience_slugs if str(slug or "").strip()]
    audience_map = {
        audience.slug: audience
        for audience in TrainingAudience.objects.filter(slug__in=normalized_slugs)
    }
    missing_slugs = [slug for slug in normalized_slugs if slug not in audience_map]
    if missing_slugs:
        raise TrainingDirectusSyncError(f"Unknown audience slugs: {', '.join(sorted(missing_slugs))}.")

    existing = {
        policy.audience.slug: policy
        for policy in TrainingContentAudiencePolicy.objects.select_related("audience").filter(content_item=content_item)
    }
    for slug in list(existing):
        if slug not in audience_map:
            existing[slug].delete()
    for slug, audience in audience_map.items():
        TrainingContentAudiencePolicy.objects.get_or_create(content_item=content_item, audience=audience)


def _sync_cross_references(*, content_item: TrainingContentItem, raw_references: list[dict]) -> list[str]:
    warnings: list[str] = []
    desired_keys: set[tuple[int, str]] = set()
    for reference in raw_references:
        slug = str(reference.get("slug") or "").strip()
        if not slug:
            continue
        related_item = TrainingContentItem.objects.filter(slug=slug).first()
        if related_item is None:
            warnings.append(f"Cross-reference skipped because content '{slug}' was not found.")
            continue
        relation_type = str(
            reference.get("relationType") or TrainingContentCrossReference.RelationType.RELATED
        ).strip()
        if relation_type not in TrainingContentCrossReference.RelationType.values:
            relation_type = TrainingContentCrossReference.RelationType.RELATED
        note = str(reference.get("note") or "").strip()[:255]
        desired_keys.add((related_item.id, relation_type))
        existing = TrainingContentCrossReference.objects.filter(
            from_item=content_item,
            to_item=related_item,
            relation_type=relation_type,
        ).first()
        if existing is None:
            TrainingContentCrossReference.objects.create(
                from_item=content_item,
                to_item=related_item,
                relation_type=relation_type,
                note=note,
            )
        elif existing.note != note:
            existing.note = note
            existing.save(update_fields=("note",))

    for reference in list(content_item.outgoing_references.all()):
        if (reference.to_item_id, reference.relation_type) not in desired_keys:
            reference.delete()
    return warnings


def _taxonomy_payload(value) -> tuple[str, str, str]:
    if isinstance(value, dict):
        slug = str(value.get("slug") or "").strip()
        name = str(value.get("name") or "").strip()
        description = str(value.get("description") or "").strip()
        if not slug and name:
            slug = slugify(name)
        return slug, name, description
    name = str(value or "").strip()
    return slugify(name), name, ""


def _fallback_name(slug: str) -> str:
    return slug.replace("-", " ").replace("_", " ").strip().title() or slug


def _build_authoring_checksum(payload: dict) -> str:
    source = "|".join(
        [
            str(payload.get("slug") or "").strip(),
            str(payload.get("name") or "").strip(),
            str(payload.get("description") or "").strip(),
            str(payload.get("bodyMarkdown") or "").strip(),
            str(payload.get("status") or "").strip(),
            str(payload.get("versionLabel") or "").strip(),
        ]
    )
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def _build_payload_summary(payload: dict) -> dict:
    return {
        "slug": str(payload.get("slug") or "").strip()[:140],
        "externalId": str(payload.get("externalId") or "").strip()[:120],
        "status": str(payload.get("status") or "").strip()[:20],
        "courseSlug": str(payload.get("courseSlug") or "").strip()[:140],
        "audienceSlugs": [str(item or "").strip()[:80] for item in payload.get("audienceSlugs") or []][:20],
    }
