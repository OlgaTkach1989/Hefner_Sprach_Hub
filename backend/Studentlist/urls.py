# SPDX-FileCopyrightText: 2026 Serhii TK
# SPDX-License-Identifier: LicenseRef-Proprietary

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.core.cache import caches
from django.db import connections
from django.http import JsonResponse
from django.urls import include, path
from django.utils import timezone
from apps.online.views import MicrosoftSsoUnifiedCallbackView
from apps.training.views import TrainingJupyterLaunchGatewayView


def healthcheck_view(_request):
    return JsonResponse(
        {
            "status": "ok",
            "service": "learning-hub-backend",
            "release": settings.APP_RELEASE,
            "timestamp": timezone.now().isoformat(),
        }
    )


def readiness_view(_request):
    database_status = _check_database()
    media_status = _check_directory(settings.MEDIA_ROOT)
    static_status = _check_directory(settings.STATIC_ROOT)
    cache_status = _check_cache()
    pgvector_status = _check_pgvector(database_status["ok"])
    critical_checks = (database_status, media_status, static_status)
    ready = all(check["ok"] for check in critical_checks)
    overall_status = "ok" if ready else "error"
    warnings: list[str] = []

    if not _directus_sync_token_configured():
        warnings.append("TRAINING_DIRECTUS_SYNC_TOKEN is empty.")
    if str(getattr(settings, "ONLINE_EMAIL_MODE", "console") or "").strip() == "directus_flow" and not _directus_email_flow_configured():
        warnings.append("ONLINE_EMAIL_MODE=directus_flow but Directus flow env vars are incomplete.")
    if bool(getattr(settings, "TRAINING_NOTEBOOK_RUNTIME_ENABLED", False)) and not _jupyter_runtime_configured():
        warnings.append("Notebook runtime is enabled but JupyterHub secrets/base URL are incomplete.")
    if bool(getattr(settings, "TRAINING_GRADER_RUNTIME_ENABLED", False)) and not _grader_runtime_configured():
        warnings.append("Grader runtime is enabled but grader secrets/course root are incomplete.")

    checks = {
        "database": database_status,
        "mediaRoot": media_status,
        "staticRoot": static_status,
        "cache": cache_status,
        "pgvector": pgvector_status,
    }
    payload = {
        "status": overall_status,
        "ready": ready,
        "service": "learning-hub-backend",
        "release": settings.APP_RELEASE,
        "timestamp": timezone.now().isoformat(),
    }
    if bool(getattr(settings, "HEALTHCHECK_EXPOSE_DETAILS", settings.DEBUG)):
        payload.update(
            {
                "checks": checks,
                "features": {
                    "trainingAiEnabled": bool(getattr(settings, "TRAINING_AI_ENABLED", False)),
                    "trainingNotebookRuntimeEnabled": bool(
                        getattr(settings, "TRAINING_NOTEBOOK_RUNTIME_ENABLED", False)
                    ),
                    "trainingGraderRuntimeEnabled": bool(getattr(settings, "TRAINING_GRADER_RUNTIME_ENABLED", False)),
                    "directusEmailFlowConfigured": _directus_email_flow_configured(),
                    "directusTrainingSyncConfigured": _directus_sync_token_configured(),
                    "jupyterRuntimeConfigured": _jupyter_runtime_configured(),
                    "graderRuntimeConfigured": _grader_runtime_configured(),
                    "pgvectorEnabled": bool(getattr(settings, "TRAINING_AI_PGVECTOR_ENABLED", False)),
                },
                "warnings": warnings,
            }
        )
    else:
        payload["checks"] = {name: {"ok": bool(check["ok"])} for name, check in checks.items()}

    return JsonResponse(payload, status=200 if ready else 503)


def _check_database() -> dict[str, object]:
    try:
        with connections["default"].cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return {"ok": True, "engine": connections["default"].vendor}
    except Exception as exc:  # pragma: no cover - defensive operational seam
        return {
            "ok": False,
            "engine": connections["default"].vendor,
            "detail": exc.__class__.__name__,
        }


def _check_directory(path_obj) -> dict[str, object]:
    try:
        path_obj.mkdir(parents=True, exist_ok=True)
        return {
            "ok": path_obj.is_dir(),
            "path": str(path_obj),
            "exists": path_obj.exists(),
        }
    except Exception as exc:  # pragma: no cover - defensive operational seam
        return {
            "ok": False,
            "path": str(path_obj),
            "detail": exc.__class__.__name__,
        }


def _check_cache() -> dict[str, object]:
    try:
        cache = caches["default"]
        probe_key = "ops.health"
        cache.set(probe_key, "ok", timeout=5)
        return {"ok": cache.get(probe_key) == "ok", "backend": cache.__class__.__name__}
    except Exception as exc:  # pragma: no cover - default cache may be local memory
        return {"ok": False, "backend": "unknown", "detail": exc.__class__.__name__}


def _check_pgvector(database_ready: bool) -> dict[str, object]:
    enabled = bool(getattr(settings, "TRAINING_AI_PGVECTOR_ENABLED", False))
    if not enabled:
        return {"ok": True, "enabled": False}
    if not database_ready or connections["default"].vendor != "postgresql":
        return {
            "ok": database_ready,
            "enabled": enabled,
            "available": database_ready,
        }
    try:
        with connections["default"].cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_extension WHERE extname = 'vector' LIMIT 1")
            available = cursor.fetchone() is not None
        return {"ok": available, "enabled": enabled, "available": available}
    except Exception as exc:  # pragma: no cover - defensive operational seam
        return {"ok": False, "enabled": enabled, "detail": exc.__class__.__name__}


def _directus_email_flow_configured() -> bool:
    return bool(
        str(getattr(settings, "ONLINE_EMAIL_DIRECTUS_FLOW_URL", "") or "").strip()
        and str(getattr(settings, "ONLINE_COURSE_ACCESS_DIRECTUS_FLOW_URL", "") or "").strip()
    )


def _directus_sync_token_configured() -> bool:
    return bool(str(getattr(settings, "TRAINING_DIRECTUS_SYNC_TOKEN", "") or "").strip())


def _jupyter_runtime_configured() -> bool:
    required_values = (
        getattr(settings, "TRAINING_JUPYTERHUB_BASE_URL", ""),
        getattr(settings, "TRAINING_JUPYTERHUB_SERVICE_TOKEN", ""),
        getattr(settings, "TRAINING_JUPYTERHUB_API_TOKEN", ""),
        getattr(settings, "TRAINING_JUPYTERHUB_SHARED_SECRET", ""),
    )
    return all(str(value or "").strip() for value in required_values)


def _grader_runtime_configured() -> bool:
    required_values = (
        getattr(settings, "TRAINING_GRADER_WEBHOOK_SECRET", ""),
        getattr(settings, "TRAINING_NBGRADER_COURSE_ROOT", ""),
    )
    return all(str(value or "").strip() for value in required_values)


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/health/", healthcheck_view, name="healthcheck"),
    path("api/health/ready/", readiness_view, name="healthcheck-ready"),
    path("api/auth/microsoft/callback/", MicrosoftSsoUnifiedCallbackView.as_view(), name="online-microsoft-callback"),
    path("api/online/", include("apps.online.urls")),
    path("api/training/", include("apps.training.urls")),
    path("lab/launch/", TrainingJupyterLaunchGatewayView.as_view(), name="training-jupyter-launch-gateway"),
    path("online/", include("apps.online.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
