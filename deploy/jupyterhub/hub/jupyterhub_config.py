from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import hmac
import os
import time
import sys
from pathlib import Path

sys.path.insert(0, "/srv/jupyterhub")

from dockerspawner import DockerSpawner
from external_token_auth import ExternalTokenAuthenticator


def _env(name: str, default: str = "") -> str:
    return str(os.getenv(name) or default).strip()


def _env_int(name: str, default: int) -> int:
    try:
        return int(_env(name, str(default)))
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(_env(name, str(default)))
    except ValueError:
        return default


def _session_api_token_ttl_seconds() -> int:
    raw_value = _env_int("JUPYTERHUB_SESSION_API_TOKEN_TTL_SECONDS", 30 * 24 * 60 * 60)
    return max(15 * 60, min(raw_value, 90 * 24 * 60 * 60))


def _jupyter_ai_proxy_token(content_slug: str, session_expires_at: str, max_session_minutes: object) -> str:
    secret = _env("TRAINING_JUPYTERHUB_SHARED_SECRET")
    normalized_slug = str(content_slug or "").strip()
    if not secret or not normalized_slug:
        return ""
    expires_at_epoch = _jupyter_ai_proxy_expiry_epoch(
        session_expires_at=session_expires_at,
        max_session_minutes=max_session_minutes,
    )
    message = f"{normalized_slug}:{expires_at_epoch}"
    signature = hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{expires_at_epoch}.{signature}"


def _jupyter_ai_proxy_expiry_epoch(*, session_expires_at: str, max_session_minutes: object) -> int:
    current_epoch = int(time.time())
    raw_value = str(session_expires_at or "").strip()
    expiry_candidates = [current_epoch + _session_api_token_ttl_seconds()]
    if raw_value:
        try:
            expiry_candidates.append(int(datetime.fromisoformat(raw_value).timestamp()))
        except ValueError:
            pass
    try:
        fallback_minutes = int(max_session_minutes or MAX_SESSION_MINUTES_CAP)
    except (TypeError, ValueError):
        fallback_minutes = MAX_SESSION_MINUTES_CAP
    expiry_candidates.append(current_epoch + max(15, fallback_minutes) * 60)
    return max(expiry_candidates)


def _jupyter_ai_proxy_base_url(content_slug: str) -> str:
    normalized_slug = str(content_slug or "").strip()
    if not normalized_slug:
        return ""
    return f"http://backend:1212/api/training/internal/openai/{normalized_slug}/"


def _notebook_actions_expiry_epoch(*, session_expires_at: str, max_session_minutes: object) -> int:
    return _jupyter_ai_proxy_expiry_epoch(
        session_expires_at=session_expires_at,
        max_session_minutes=max_session_minutes,
    )


def _notebook_action_token(*, content_slug: str, user_id: object, session_expires_at: str, max_session_minutes: object) -> str:
    secret = _env("TRAINING_JUPYTERHUB_SHARED_SECRET")
    normalized_slug = str(content_slug or "").strip()
    normalized_user_id = str(user_id or "").strip()
    if not secret or not normalized_slug or not normalized_user_id:
        return ""
    expires_at_epoch = _notebook_actions_expiry_epoch(
        session_expires_at=session_expires_at,
        max_session_minutes=max_session_minutes,
    )
    message = f"{normalized_slug}:{normalized_user_id}:{expires_at_epoch}"
    signature = hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{normalized_user_id}.{expires_at_epoch}.{signature}"


def _notebook_actions_base_url(content_slug: str) -> str:
    normalized_slug = str(content_slug or "").strip()
    if not normalized_slug:
        return ""
    return f"http://backend:1212/api/training/internal/notebook-actions/{normalized_slug}/"


BASE_URL = _env("JUPYTERHUB_BASE_URL", "/lab/")
DATA_DIR = Path(_env("JUPYTERHUB_DATA_DIR", "/data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

HUB_IMAGE = _env("JUPYTERHUB_HUB_IMAGE", "learning-hub-jupyterhub:local")
SINGLEUSER_IMAGE = _env("JUPYTERHUB_SINGLEUSER_IMAGE", HUB_IMAGE)
ISOLATED_NETWORK_NAME = _env("JUPYTERHUB_RUNTIME_ISOLATED_NETWORK_NAME", _env("JUPYTERHUB_RUNTIME_NETWORK_NAME", "onlinelessons_lab"))
EGRESS_NETWORK_NAME = _env("JUPYTERHUB_RUNTIME_EGRESS_NETWORK_NAME", "onlinelessons_lab_egress")
NOTEBOOK_DIR = _env("JUPYTERHUB_RUNTIME_NOTEBOOK_DIR", "/home/jovyan/work")
SINGLEUSER_UID = _env("JUPYTERHUB_SINGLEUSER_UID", "1000")
SINGLEUSER_GID = _env("JUPYTERHUB_SINGLEUSER_GID", "100")
GPU_RUNTIME_ENABLED = _env("JUPYTERHUB_GPU_RUNTIME_ENABLED", "false").lower() in {"1", "true", "yes", "on"}
GPU_DEVICE_COUNT = _env_int("JUPYTERHUB_GPU_RUNTIME_DEVICE_COUNT", 1)
MAX_SESSION_MINUTES_CAP = _env_int("JUPYTERHUB_RUNTIME_MAX_SESSION_MINUTES_CAP", 240)
ALLOWED_RUNTIME_IMAGES = {
    value
    for value in (
        item.strip()
        for item in _env("JUPYTERHUB_ALLOWED_RUNTIME_IMAGES", SINGLEUSER_IMAGE).split(",")
    )
    if value
}
if SINGLEUSER_IMAGE not in ALLOWED_RUNTIME_IMAGES:
    ALLOWED_RUNTIME_IMAGES.add(SINGLEUSER_IMAGE)

c.JupyterHub.bind_url = f"http://:8000{BASE_URL}"
c.JupyterHub.base_url = BASE_URL
c.JupyterHub.cookie_secret_file = str(DATA_DIR / "jupyterhub_cookie_secret")
c.JupyterHub.db_url = f"sqlite:///{DATA_DIR / 'jupyterhub.sqlite'}"
c.JupyterHub.hub_ip = "0.0.0.0"
c.JupyterHub.hub_connect_ip = _env("JUPYTERHUB_HUB_CONNECT_IP", "jupyterhub")
c.JupyterHub.spawner_class = DockerSpawner
c.JupyterHub.authenticator_class = ExternalTokenAuthenticator
c.Authenticator.allow_all = True
c.Authenticator.enable_auth_state = True
c.ExternalTokenAuthenticator.token_exchange_url = _env(
    "JUPYTERHUB_LOGIN_EXCHANGE_URL",
    "http://backend:1212/api/training/internal/labs/exchange-jupyter-login/",
)
c.ExternalTokenAuthenticator.token_exchange_service_token = _env("TRAINING_JUPYTERHUB_SERVICE_TOKEN")

crypt_key = _env("JUPYTERHUB_CRYPT_KEY")
if crypt_key:
    c.CryptKeeper.keys = [crypt_key]

service_name = _env("JUPYTERHUB_LAUNCHER_SERVICE_NAME", "learning-hub-launcher")
service_token = _env("TRAINING_JUPYTERHUB_API_TOKEN")
c.JupyterHub.services = [
    {
        "name": service_name,
        "api_token": service_token,
    }
]
c.JupyterHub.load_roles = [
    {
        "name": "learning-hub-launcher-role",
        "services": [service_name],
        "scopes": [
            "read:users",
            "list:users",
            "admin:users",
            "read:servers",
            "admin:servers",
            "access:servers",
        ],
    }
]

c.JupyterHub.cleanup_servers = True
c.JupyterHub.shutdown_on_logout = False
c.DockerSpawner.default_url = "/lab"
c.DockerSpawner.cmd = ["/usr/local/bin/learning-hub-singleuser-start.sh"]
c.DockerSpawner.image = SINGLEUSER_IMAGE
c.DockerSpawner.use_internal_ip = True
c.DockerSpawner.network_name = ISOLATED_NETWORK_NAME
c.DockerSpawner.notebook_dir = NOTEBOOK_DIR
c.DockerSpawner.remove = True
c.DockerSpawner.debug = False
c.DockerSpawner.start_timeout = _env_int("JUPYTERHUB_START_TIMEOUT_SECONDS", 120)
c.DockerSpawner.http_timeout = _env_int("JUPYTERHUB_HTTP_TIMEOUT_SECONDS", 120)
c.DockerSpawner.mem_limit = _env("JUPYTERHUB_RUNTIME_MEM_LIMIT", "2G")
c.DockerSpawner.mem_guarantee = _env("JUPYTERHUB_RUNTIME_MEM_GUARANTEE", "1G")
c.DockerSpawner.cpu_limit = _env_float("JUPYTERHUB_RUNTIME_CPU_LIMIT", 1.0)
c.DockerSpawner.cpu_guarantee = _env_float("JUPYTERHUB_RUNTIME_CPU_GUARANTEE", 0.5)
c.DockerSpawner.extra_create_kwargs = {
    "entrypoint": ["/usr/local/bin/learning-hub-singleuser-start.sh"],
    "working_dir": NOTEBOOK_DIR,
}
c.DockerSpawner.extra_host_config = {
    "security_opt": ["no-new-privileges:true"],
    "cap_drop": ["ALL"],
    "pids_limit": _env_int("JUPYTERHUB_RUNTIME_PIDS_LIMIT", 256),
}
c.DockerSpawner.environment = {
    "JUPYTER_DOCKER_STACKS_QUIET": "1",
    "GRANT_SUDO": "no",
    "CHOWN_HOME": "no",
    "CHOWN_EXTRA": "",
    "JUPYTER_ENV_VARS_TO_UNSET": "",
    "JUPYTERHUB_SINGLEUSER_APP": "jupyter_server.serverapp.ServerApp",
    "JUPYTERHUB_NOTEBOOK_DIR": NOTEBOOK_DIR,
    "TRAINING_CONTENT_ROOT": "/opt/training-content",
    "TRAINING_CONTENT_ROOTS": "/srv/training-media/training/runtime-content,/opt/training-content",
    "TRAINING_AI_PROVIDER": _env("TRAINING_AI_PROVIDER", "demo"),
    "TRAINING_AI_BASE_URL": _env("TRAINING_AI_BASE_URL"),
    "TRAINING_AI_CHAT_MODEL": _env("TRAINING_AI_CHAT_MODEL", "demo-extractive-v1"),
    "OPENAI_API_KEY": "",
    "OPENAI_API_BASE": "",
    "OPENAI_BASE_URL": "",
}
c.DockerSpawner.volumes = {
    "jupyterhub-user-{username}": NOTEBOOK_DIR,
    "onlinelessons_media": {"bind": "/srv/training-media", "mode": "ro"},
}


async def _pre_spawn_hook(spawner):
    auth_state = await spawner.user.get_auth_state() or {}
    training_content = auth_state.get("trainingContent") or {}
    platform_user = auth_state.get("platformUser") or {}
    audience_slugs = auth_state.get("audienceSlugs") or []
    notebook_path = str(training_content.get("notebookPath") or "").strip().lstrip("/")
    launch_path = str(training_content.get("launchPath") or "").strip()
    runtime_image = str(training_content.get("runtimeImage") or "").strip()
    grader_backend = str(training_content.get("graderBackend") or "").strip()
    allow_network = bool(training_content.get("allowNetwork"))
    allow_gpu = bool(training_content.get("allowGpu"))
    max_session_minutes = training_content.get("maxSessionMinutes")
    session_expires_at = str(training_content.get("sessionExpiresAt") or "").strip()

    selected_image = SINGLEUSER_IMAGE
    if runtime_image and runtime_image in ALLOWED_RUNTIME_IMAGES:
        selected_image = runtime_image
    spawner.image = selected_image
    spawner.network_name = EGRESS_NETWORK_NAME if allow_network else ISOLATED_NETWORK_NAME
    host_config = {
        "security_opt": ["no-new-privileges:true"],
        "cap_drop": ["ALL"],
        "pids_limit": _env_int("JUPYTERHUB_RUNTIME_PIDS_LIMIT", 256),
    }
    if allow_gpu and GPU_RUNTIME_ENABLED:
        host_config["device_requests"] = [
            {
                "Driver": "nvidia",
                "Count": max(1, GPU_DEVICE_COUNT),
                "Capabilities": [["gpu"]],
            }
        ]
    spawner.extra_host_config = host_config
    spawner.extra_create_kwargs = {
        "entrypoint": ["/usr/local/bin/learning-hub-singleuser-start.sh"],
        "working_dir": NOTEBOOK_DIR,
        "labels": {
            "learning-hub.training-content-slug": str(training_content.get("slug") or ""),
            "learning-hub.platform-user-id": str(platform_user.get("id") or ""),
            "learning-hub.allow-network": "true" if allow_network else "false",
            "learning-hub.allow-gpu": "true" if allow_gpu else "false",
            "learning-hub.max-session-minutes": str(max_session_minutes or ""),
            "learning-hub.session-expires-at": session_expires_at,
            "learning-hub.audiences": ",".join(str(value) for value in audience_slugs if value),
        },
    }
    spawner.default_url = f"/lab/tree/{notebook_path}" if notebook_path else "/lab"
    content_slug = str(training_content.get("slug") or "").strip()
    jupyter_ai_base_url = _jupyter_ai_proxy_base_url(content_slug)
    jupyter_ai_token = _jupyter_ai_proxy_token(
        content_slug=content_slug,
        session_expires_at=session_expires_at,
        max_session_minutes=max_session_minutes,
    )
    notebook_actions_base_url = _notebook_actions_base_url(content_slug)
    notebook_action_token = _notebook_action_token(
        content_slug=content_slug,
        user_id=platform_user.get("id"),
        session_expires_at=session_expires_at,
        max_session_minutes=max_session_minutes,
    )
    spawner.environment.update(
        {
            "TRAINING_PLATFORM_USER_ID": str(platform_user.get("id") or ""),
            "TRAINING_PLATFORM_USER_EMAIL": str(platform_user.get("email") or ""),
            "TRAINING_CONTENT_ID": str(training_content.get("id") or ""),
            "TRAINING_CONTENT_SLUG": str(training_content.get("slug") or ""),
            "TRAINING_CONTENT_NAME": str(training_content.get("name") or ""),
            "TRAINING_NOTEBOOK_PATH": notebook_path,
            "TRAINING_LAUNCH_PATH": launch_path,
            "TRAINING_RUNTIME_IMAGE": runtime_image,
            "TRAINING_GRADER_BACKEND": grader_backend,
            "TRAINING_ALLOW_NETWORK": "1" if allow_network else "0",
            "TRAINING_ALLOW_GPU": "1" if allow_gpu else "0",
            "TRAINING_SESSION_MAX_MINUTES": str(max_session_minutes or MAX_SESSION_MINUTES_CAP),
            "TRAINING_SESSION_EXPIRES_AT": session_expires_at,
            "TRAINING_NOTEBOOK_FORCE_RESET": "1" if bool(training_content.get("forceNotebookReset")) else "0",
            "TRAINING_NOTEBOOK_ACTIONS_BASE_URL": notebook_actions_base_url,
            "TRAINING_NOTEBOOK_ACTION_TOKEN": notebook_action_token,
            "TRAINING_NOTEBOOK_ACTIONS_EXPIRES_AT": str(
                _notebook_actions_expiry_epoch(
                    session_expires_at=session_expires_at,
                    max_session_minutes=max_session_minutes,
                )
            ),
            "OPENAI_API_KEY": jupyter_ai_token,
            "OPENAI_API_BASE": jupyter_ai_base_url,
            "OPENAI_BASE_URL": jupyter_ai_base_url,
            "JUPYTER_AI_DEFAULT_MODEL": _env("TRAINING_AI_CHAT_MODEL", "demo-extractive-v1") or "demo-extractive-v1",
        }
    )


c.Spawner.pre_spawn_hook = _pre_spawn_hook
