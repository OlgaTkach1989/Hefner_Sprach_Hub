from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import time

from django.conf import settings


class TrainingNotebookActionError(RuntimeError):
    pass


@dataclass(frozen=True)
class ResolvedNotebookActionToken:
    user_id: int
    expires_at_epoch: int


def build_internal_notebook_action_token(*, content_slug: str, user_id: int, expires_at_epoch: int) -> str:
    secret = _signing_secret()
    normalized_slug = str(content_slug or "").strip()
    normalized_user_id = int(user_id or 0)
    expiry_value = int(expires_at_epoch or 0)
    if not secret:
        raise TrainingNotebookActionError("Notebook action signing secret is not configured.")
    if not normalized_slug or normalized_user_id <= 0 or expiry_value <= 0:
        raise TrainingNotebookActionError("Notebook action token payload is incomplete.")
    message = f"{normalized_slug}:{normalized_user_id}:{expiry_value}"
    signature = hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{normalized_user_id}.{expiry_value}.{signature}"


def validate_internal_notebook_action_token(*, content_slug: str, token: str) -> ResolvedNotebookActionToken:
    normalized_slug = str(content_slug or "").strip()
    raw_token = str(token or "").strip()
    if not normalized_slug or not raw_token:
        raise TrainingNotebookActionError("Notebook action token is missing.")
    try:
        user_part, expiry_part, signature_part = raw_token.split(".", 2)
        user_id = int(user_part)
        expires_at_epoch = int(expiry_part)
    except (TypeError, ValueError) as exc:
        raise TrainingNotebookActionError("Notebook action token format is invalid.") from exc
    grace_seconds = training_notebook_action_token_grace_seconds()
    if user_id <= 0 or expires_at_epoch <= int(time.time()) - grace_seconds:
        raise TrainingNotebookActionError("Notebook action token is expired.")
    expected_token = build_internal_notebook_action_token(
        content_slug=normalized_slug,
        user_id=user_id,
        expires_at_epoch=expires_at_epoch,
    )
    _expected_user_id, _expected_expiry, expected_signature = expected_token.split(".", 2)
    if not hmac.compare_digest(signature_part, expected_signature):
        raise TrainingNotebookActionError("Notebook action token signature is invalid.")
    return ResolvedNotebookActionToken(user_id=user_id, expires_at_epoch=expires_at_epoch)


def _signing_secret() -> str:
    configured_secret = str(getattr(settings, "TRAINING_JUPYTERHUB_SHARED_SECRET", "") or "").strip()
    if configured_secret:
        return configured_secret
    return str(settings.SECRET_KEY)


def training_notebook_action_token_grace_seconds() -> int:
    raw_value = int(getattr(settings, "TRAINING_JUPYTER_SESSION_API_TOKEN_GRACE_SECONDS", 30 * 24 * 60 * 60) or 0)
    return max(0, min(raw_value, 90 * 24 * 60 * 60))
