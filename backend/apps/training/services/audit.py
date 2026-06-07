from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from django.contrib.auth.models import AnonymousUser

from apps.training.models import TrainingAuditEvent


def log_training_audit_event(
    *,
    event_type: str,
    category: str,
    outcome: str = TrainingAuditEvent.Outcome.SUCCEEDED,
    request=None,
    actor=None,
    target_user=None,
    course=None,
    content_item=None,
    submission=None,
    launch_token=None,
    jupyter_login_token=None,
    metadata: Mapping[str, Any] | None = None,
) -> TrainingAuditEvent:
    resolved_actor = actor
    if resolved_actor is None and request is not None:
        request_user = getattr(request, "user", None)
        if request_user is not None and not isinstance(request_user, AnonymousUser) and getattr(request_user, "is_authenticated", False):
            resolved_actor = request_user

    resolved_course = course
    if resolved_course is None and content_item is not None:
        resolved_course = content_item.course
    if resolved_course is None and submission is not None:
        resolved_course = submission.content_item.course

    return TrainingAuditEvent.objects.create(
        category=category,
        event_type=event_type[:80],
        outcome=outcome,
        actor=resolved_actor,
        actor_email=_user_email(resolved_actor),
        target_user=target_user,
        target_user_email=_user_email(target_user),
        course=resolved_course,
        content_item=content_item,
        submission=submission,
        launch_token=launch_token,
        jupyter_login_token=jupyter_login_token,
        request_id=_request_id(request),
        request_method=_request_method(request),
        request_path=_request_path(request),
        request_ip=_request_ip(request),
        user_agent=_request_user_agent(request),
        metadata=_sanitize_mapping(metadata),
    )


def _request_method(request) -> str:
    if request is None:
        return ""
    return str(getattr(request, "method", "") or "")[:10]


def _request_id(request) -> str:
    if request is None:
        return ""
    request_id = str(request.headers.get("X-Request-ID") or "").strip()
    if request_id:
        return request_id[:80]
    return str(request.headers.get("X-Correlation-ID") or "").strip()[:80]


def _request_path(request) -> str:
    if request is None:
        return ""
    return str(getattr(request, "path", "") or "")[:255]


def _request_ip(request) -> str:
    if request is None:
        return ""
    forwarded_for = str(request.headers.get("X-Forwarded-For") or "").strip()
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()[:64]
    return str(request.META.get("REMOTE_ADDR") or "").strip()[:64]


def _request_user_agent(request) -> str:
    if request is None:
        return ""
    return str(request.headers.get("User-Agent") or "").strip()[:400]


def _user_email(user) -> str:
    if user is None:
        return ""
    return str(getattr(user, "email", "") or "").strip()[:254]


def _sanitize_mapping(metadata: Mapping[str, Any] | None) -> dict[str, Any]:
    if metadata is None:
        return {}
    if not isinstance(metadata, Mapping):
        return {"value": _sanitize_value(metadata)}
    return {str(key)[:80]: _sanitize_value(value) for key, value in metadata.items()}


def _sanitize_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value[:1000]
    if isinstance(value, Mapping):
        return {str(key)[:80]: _sanitize_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_sanitize_value(item) for item in value][:50]
    return str(value)[:1000]
