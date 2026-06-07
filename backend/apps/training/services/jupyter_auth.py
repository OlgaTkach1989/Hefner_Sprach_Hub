from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from urllib.parse import quote

from django.conf import settings
from django.core import signing
from django.utils import timezone
from django.utils.text import slugify

from apps.training.models import TrainingJupyterLoginToken, TrainingLabLaunchToken, TrainingNotebookLabProfile
from apps.training.services.lab_repeatability import repeatable_lab_reentry_enabled
from apps.training.services.runtime_policy import TrainingRuntimePolicyError, resolve_training_runtime_policy


class TrainingJupyterAuthError(Exception):
    """Base error for JupyterHub authentication handoff."""


class TrainingJupyterLoginTokenInvalidError(TrainingJupyterAuthError):
    """Login token is invalid, expired, revoked, or already consumed."""


@dataclass(frozen=True)
class ResolvedJupyterLogin:
    token: TrainingJupyterLoginToken
    payload: dict[str, object]


TRAINING_JUPYTER_LOGIN_SIGNING_SALT = "training.lab.jupyter.login"


def training_jupyter_login_ttl_seconds() -> int:
    raw_value = int(getattr(settings, "TRAINING_JUPYTER_LOGIN_TTL_SECONDS", 180) or 180)
    return max(30, min(raw_value, 900))


def training_jupyterhub_base_url() -> str:
    return str(getattr(settings, "TRAINING_JUPYTERHUB_BASE_URL", "") or "").strip().rstrip("/")


def training_jupyterhub_force_logout_before_login() -> bool:
    return bool(getattr(settings, "TRAINING_JUPYTERHUB_FORCE_LOGOUT_BEFORE_LOGIN", True))


def build_training_jupyter_username(user) -> str:
    base = slugify((getattr(user, "username", None) or str(user.email).split("@")[0]).strip()) or f"user-{user.id}"
    composed = f"student-{user.id}-{base}"
    return composed[:120]


def issue_jupyter_login_token(*, launch_token: TrainingLabLaunchToken) -> tuple[TrainingJupyterLoginToken, str]:
    now = timezone.now()
    if launch_token.status != TrainingLabLaunchToken.Status.CONSUMED:
        raise TrainingJupyterAuthError("Launch token must be consumed before Jupyter login is issued.")
    if launch_token.expires_at <= now:
        raise TrainingJupyterAuthError("Launch token is expired.")

    try:
        lab_profile = launch_token.content_item.lab_profile
    except TrainingNotebookLabProfile.DoesNotExist as exc:
        raise TrainingJupyterAuthError("Notebook runtime profile is missing.") from exc
    if not lab_profile.is_active:
        raise TrainingJupyterAuthError("Notebook runtime profile is inactive.")
    if lab_profile.runtime_backend != TrainingNotebookLabProfile.RuntimeBackend.JUPYTERHUB:
        raise TrainingJupyterAuthError("Notebook runtime is not configured for JupyterHub.")
    try:
        runtime_policy = resolve_training_runtime_policy(lab_profile=lab_profile)
    except TrainingRuntimePolicyError as exc:
        raise TrainingJupyterAuthError(str(exc)) from exc

    gradebook_entry = (
        launch_token.content_item.gradebook_entries.filter(user=launch_token.user)
        .only("attempts_count", "passed")
        .first()
    )
    force_notebook_reset = repeatable_lab_reentry_enabled(
        content_item=launch_token.content_item,
        gradebook_entry=gradebook_entry,
    )

    jupyter_username = build_training_jupyter_username(launch_token.user)
    expires_at = now + timedelta(seconds=training_jupyter_login_ttl_seconds())
    login_token = TrainingJupyterLoginToken.objects.create(
        launch_token=launch_token,
        user=launch_token.user,
        content_item=launch_token.content_item,
        jupyter_username=jupyter_username,
        expires_at=expires_at,
        auth_state={
            "platformUser": {
                "id": launch_token.user_id,
                "email": launch_token.user.email,
                "jupyterUsername": jupyter_username,
            },
            "trainingContent": {
                "id": launch_token.content_item_id,
                "slug": launch_token.content_item.slug,
                "name": launch_token.content_item.name,
                "courseId": launch_token.content_item.course_id,
                "notebookPath": lab_profile.notebook_path,
                "launchPath": lab_profile.launch_path or "/lab",
                "runtimeImage": lab_profile.runtime_image,
                "graderBackend": lab_profile.grader_backend,
                "graderConfig": lab_profile.grader_config,
                "allowGpu": runtime_policy.allow_gpu,
                "allowNetwork": runtime_policy.allow_network,
                "maxSessionMinutes": runtime_policy.max_session_minutes,
                "sessionExpiresAt": runtime_policy.session_expires_at.isoformat(),
                "forceNotebookReset": force_notebook_reset,
            },
            "audienceSlugs": launch_token.audience_snapshot,
            "launchTokenId": str(launch_token.token_id),
        },
    )
    signed_token = signing.dumps(
        {
            "tid": str(login_token.token_id),
            "uid": launch_token.user_id,
            "cid": launch_token.content_item_id,
            "jupyter_username": jupyter_username,
        },
        key=_signing_key(),
        salt=TRAINING_JUPYTER_LOGIN_SIGNING_SALT,
        compress=True,
    )
    return login_token, signed_token


def resolve_jupyter_login_token(*, signed_token: str) -> ResolvedJupyterLogin:
    try:
        payload = signing.loads(
            signed_token,
            key=_signing_key(),
            salt=TRAINING_JUPYTER_LOGIN_SIGNING_SALT,
            max_age=training_jupyter_login_ttl_seconds(),
        )
    except signing.SignatureExpired as exc:
        raise TrainingJupyterLoginTokenInvalidError("Jupyter login token is expired.") from exc
    except signing.BadSignature as exc:
        raise TrainingJupyterLoginTokenInvalidError("Jupyter login token signature is invalid.") from exc

    token_id = str(payload.get("tid") or "").strip()
    user_id = payload.get("uid")
    content_item_id = payload.get("cid")
    jupyter_username = str(payload.get("jupyter_username") or "").strip()
    if not token_id or not user_id or not content_item_id or not jupyter_username:
        raise TrainingJupyterLoginTokenInvalidError("Jupyter login token payload is incomplete.")

    token = (
        TrainingJupyterLoginToken.objects.select_related("content_item", "launch_token", "user")
        .filter(token_id=token_id)
        .first()
    )
    if token is None:
        raise TrainingJupyterLoginTokenInvalidError("Jupyter login token record was not found.")

    now = timezone.now()
    if token.status != TrainingJupyterLoginToken.Status.ISSUED:
        raise TrainingJupyterLoginTokenInvalidError("Jupyter login token is no longer active.")
    if token.expires_at <= now:
        token.status = TrainingJupyterLoginToken.Status.EXPIRED
        token.save(update_fields=["status", "updated_at"])
        raise TrainingJupyterLoginTokenInvalidError("Jupyter login token is expired.")
    if token.user_id != int(user_id) or token.content_item_id != int(content_item_id):
        raise TrainingJupyterLoginTokenInvalidError("Jupyter login token payload mismatch.")
    if token.jupyter_username != jupyter_username:
        raise TrainingJupyterLoginTokenInvalidError("Jupyter login token username mismatch.")

    token.status = TrainingJupyterLoginToken.Status.CONSUMED
    token.consumed_at = now
    token.save(update_fields=["status", "consumed_at", "updated_at"])
    return ResolvedJupyterLogin(token=token, payload=payload)


def build_jupyter_login_contract(*, login_token: TrainingJupyterLoginToken, signed_token: str) -> dict[str, object]:
    return {
        "tokenId": str(login_token.token_id),
        "loginToken": signed_token,
        "expiresAt": login_token.expires_at,
        "jupyterUsername": login_token.jupyter_username,
        "authState": login_token.auth_state,
    }


def build_resolved_jupyter_login_contract(*, resolved_login: ResolvedJupyterLogin) -> dict[str, object]:
    token = resolved_login.token
    return {
        "name": token.jupyter_username,
        "authState": token.auth_state,
        "user": {
            "id": token.user_id,
            "email": token.user.email,
        },
        "content": {
            "id": token.content_item_id,
            "slug": token.content_item.slug,
            "name": token.content_item.name,
            "courseId": token.content_item.course_id,
        },
    }


def build_jupyterhub_login_redirect_url(*, login_token: TrainingJupyterLoginToken, signed_token: str) -> str | None:
    base_url = training_jupyterhub_base_url()
    if not base_url:
        return None

    next_path = _jupyterhub_next_path(login_token=login_token)
    login_path = f"/lab/hub/login?login_token={quote(signed_token)}&next={quote(next_path)}"
    if training_jupyterhub_force_logout_before_login():
        return f"{base_url}/hub/logout?next={quote(login_path)}"
    return f"{base_url}/hub/login?login_token={quote(signed_token)}&next={quote(next_path)}"


def _signing_key() -> str:
    configured_key = str(getattr(settings, "TRAINING_JUPYTERHUB_SHARED_SECRET", "") or "").strip()
    if configured_key:
        return configured_key
    return str(settings.SECRET_KEY)


def _jupyterhub_next_path(*, login_token: TrainingJupyterLoginToken) -> str:
    try:
        lab_profile = login_token.content_item.lab_profile
    except TrainingNotebookLabProfile.DoesNotExist:
        return "/lab/hub/user-redirect/lab"

    launch_path = str(lab_profile.launch_path or "").strip()
    notebook_path = str(lab_profile.notebook_path or "").strip().lstrip("/")

    if launch_path.startswith("/lab/hub/user-redirect/"):
        return launch_path
    if launch_path.startswith("/hub/user-redirect/"):
        return f"/lab{launch_path}"
    if launch_path.startswith("/user-redirect/"):
        return f"/lab/hub{launch_path}"
    if launch_path.startswith("/lab/tree/"):
        return f"/lab/hub/user-redirect/{launch_path.removeprefix('/lab/').lstrip('/')}"
    if launch_path.startswith("/tree/"):
        return f"/lab/hub/user-redirect/lab{launch_path}"
    if notebook_path:
        return f"/lab/hub/user-redirect/lab/tree/{notebook_path}"
    return "/lab/hub/user-redirect/lab"
