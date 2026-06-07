from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.core import signing
from django.utils import timezone

from apps.training.models import TrainingContentItem, TrainingLabLaunchToken, TrainingNotebookLabProfile
from apps.training.services.access import active_audience_slugs_for_user
from apps.training.services.runtime_policy import TrainingRuntimePolicyError, resolve_training_runtime_policy


class TrainingLabLaunchError(Exception):
    """Base error for lab launch flow."""


class TrainingLabRuntimeDisabledError(TrainingLabLaunchError):
    """Notebook runtime is not enabled."""


class TrainingLabLaunchTokenInvalidError(TrainingLabLaunchError):
    """Launch token is invalid, expired, or already consumed."""


@dataclass(frozen=True)
class ResolvedLabLaunch:
    token: TrainingLabLaunchToken
    payload: dict[str, object]


TRAINING_LAB_LAUNCH_SIGNING_SALT = "training.lab.launch"


def training_lab_launch_ttl_seconds() -> int:
    raw_value = int(getattr(settings, "TRAINING_LAB_LAUNCH_TTL_SECONDS", 300) or 300)
    return max(60, min(raw_value, 3600))


def _signing_key() -> str:
    configured_key = str(getattr(settings, "TRAINING_JUPYTERHUB_SHARED_SECRET", "") or "").strip()
    if configured_key:
        return configured_key
    return str(settings.SECRET_KEY)


def training_lab_runtime_enabled() -> bool:
    return bool(getattr(settings, "TRAINING_NOTEBOOK_RUNTIME_ENABLED", False))


def issue_lab_launch_token(*, user, content_item: TrainingContentItem, request) -> tuple[TrainingLabLaunchToken, str]:
    if not training_lab_runtime_enabled():
        raise TrainingLabRuntimeDisabledError("Notebook runtime is disabled.")

    try:
        lab_profile = content_item.lab_profile
    except TrainingNotebookLabProfile.DoesNotExist as exc:
        raise TrainingLabLaunchError("Notebook runtime profile is missing.") from exc
    if not lab_profile.is_active:
        raise TrainingLabLaunchError("Notebook runtime profile is inactive.")
    try:
        resolve_training_runtime_policy(lab_profile=lab_profile)
    except TrainingRuntimePolicyError as exc:
        raise TrainingLabLaunchError(str(exc)) from exc

    audience_snapshot = sorted(active_audience_slugs_for_user(user))
    ttl_seconds = training_lab_launch_ttl_seconds()
    expires_at = timezone.now() + timedelta(seconds=ttl_seconds)
    launch_token = TrainingLabLaunchToken.objects.create(
        user=user,
        content_item=content_item,
        expires_at=expires_at,
        requested_ip=_request_ip(request),
        user_agent=str(request.headers.get("User-Agent") or "")[:400],
        audience_snapshot=audience_snapshot,
    )
    signed_token = signing.dumps(
        {
            "tid": str(launch_token.token_id),
            "uid": user.id,
            "cid": content_item.id,
        },
        key=_signing_key(),
        salt=TRAINING_LAB_LAUNCH_SIGNING_SALT,
        compress=True,
    )
    return launch_token, signed_token


def resolve_lab_launch_token(*, signed_token: str) -> ResolvedLabLaunch:
    try:
        payload = signing.loads(
            signed_token,
            key=_signing_key(),
            salt=TRAINING_LAB_LAUNCH_SIGNING_SALT,
            max_age=training_lab_launch_ttl_seconds(),
        )
    except signing.SignatureExpired as exc:
        raise TrainingLabLaunchTokenInvalidError("Launch token is expired.") from exc
    except signing.BadSignature as exc:
        raise TrainingLabLaunchTokenInvalidError("Launch token signature is invalid.") from exc

    token_id = str(payload.get("tid") or "").strip()
    content_item_id = payload.get("cid")
    user_id = payload.get("uid")
    if not token_id or not content_item_id or not user_id:
        raise TrainingLabLaunchTokenInvalidError("Launch token payload is incomplete.")

    token = (
        TrainingLabLaunchToken.objects.select_related("content_item__course", "content_item__lab_profile", "user")
        .filter(token_id=token_id)
        .first()
    )
    if token is None:
        raise TrainingLabLaunchTokenInvalidError("Launch token record was not found.")

    now = timezone.now()
    if token.status != TrainingLabLaunchToken.Status.ISSUED:
        raise TrainingLabLaunchTokenInvalidError("Launch token is no longer active.")
    if token.expires_at <= now:
        token.status = TrainingLabLaunchToken.Status.EXPIRED
        token.save(update_fields=["status", "updated_at"])
        raise TrainingLabLaunchTokenInvalidError("Launch token is expired.")
    if token.user_id != int(user_id) or token.content_item_id != int(content_item_id):
        raise TrainingLabLaunchTokenInvalidError("Launch token payload mismatch.")
    try:
        lab_profile = token.content_item.lab_profile
    except TrainingNotebookLabProfile.DoesNotExist as exc:
        raise TrainingLabLaunchTokenInvalidError("Notebook runtime profile is missing.") from exc
    if not lab_profile.is_active:
        raise TrainingLabLaunchTokenInvalidError("Notebook runtime profile is inactive.")

    token.status = TrainingLabLaunchToken.Status.CONSUMED
    token.consumed_at = now
    token.save(update_fields=["status", "consumed_at", "updated_at"])
    return ResolvedLabLaunch(token=token, payload=payload)


def build_lab_launch_contract(*, launch_token: TrainingLabLaunchToken, signed_token: str) -> dict[str, object]:
    lab_profile = launch_token.content_item.lab_profile
    runtime_policy = resolve_training_runtime_policy(lab_profile=lab_profile)
    runtime_base_url = str(getattr(settings, "TRAINING_JUPYTERHUB_BASE_URL", "") or "").strip().rstrip("/")
    launch_path = lab_profile.launch_path or "/lab"
    launch_url = None
    if runtime_base_url:
        launch_url = f"{runtime_base_url}/launch/?training_launch_token={signed_token}"

    return {
        "tokenId": str(launch_token.token_id),
        "launchToken": signed_token,
        "expiresAt": launch_token.expires_at,
        "launchUrl": launch_url,
        "runtime": {
            "baseUrl": runtime_base_url,
            "backend": lab_profile.runtime_backend,
            "graderBackend": lab_profile.grader_backend,
            "launchPath": launch_path,
            "allowGpu": runtime_policy.allow_gpu,
            "allowNetwork": runtime_policy.allow_network,
            "maxSessionMinutes": runtime_policy.max_session_minutes,
            "sessionExpiresAt": runtime_policy.session_expires_at,
        },
        "content": {
            "id": launch_token.content_item.id,
            "slug": launch_token.content_item.slug,
            "name": launch_token.content_item.name,
            "courseId": launch_token.content_item.course_id,
        },
    }


def build_resolved_lab_contract(*, resolved_launch: ResolvedLabLaunch) -> dict[str, object]:
    token = resolved_launch.token
    content_item = token.content_item
    lab_profile = content_item.lab_profile
    runtime_policy = resolve_training_runtime_policy(lab_profile=lab_profile)
    return {
        "tokenId": str(token.token_id),
        "issuedAt": token.created_at,
        "expiresAt": token.expires_at,
        "user": {
            "id": token.user_id,
            "email": token.user.email,
        },
        "content": {
            "id": content_item.id,
            "slug": content_item.slug,
            "name": content_item.name,
            "courseId": content_item.course_id,
        },
        "lab": {
            "runtimeBackend": lab_profile.runtime_backend,
            "graderBackend": lab_profile.grader_backend,
            "runtimeImage": lab_profile.runtime_image,
            "notebookPath": lab_profile.notebook_path,
            "launchPath": lab_profile.launch_path or "/lab",
            "allowGpu": runtime_policy.allow_gpu,
            "allowNetwork": runtime_policy.allow_network,
            "maxSessionMinutes": runtime_policy.max_session_minutes,
            "sessionExpiresAt": runtime_policy.session_expires_at,
            "graderConfig": lab_profile.grader_config,
        },
        "audienceSlugs": token.audience_snapshot,
    }


def _request_ip(request) -> str:
    forwarded_for = str(request.headers.get("X-Forwarded-For") or "").strip()
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()[:64]
    remote_addr = str(request.META.get("REMOTE_ADDR") or "").strip()
    return remote_addr[:64]
