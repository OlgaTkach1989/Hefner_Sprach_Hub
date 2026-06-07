from __future__ import annotations

from hmac import compare_digest

from django.conf import settings
from rest_framework.permissions import BasePermission


def has_training_bearer_service_token(request, *, setting_name: str) -> bool:
    expected_token = str(getattr(settings, setting_name, "") or "").strip()
    if not expected_token:
        return False

    raw_authorization = str(request.headers.get("Authorization") or "")
    if not raw_authorization.startswith("Bearer "):
        return False

    provided_token = raw_authorization.removeprefix("Bearer ").strip()
    if not provided_token:
        return False

    return compare_digest(provided_token, expected_token)


class IsTrainingInternalService(BasePermission):
    message = "Internal training service token required."

    def has_permission(self, request, view) -> bool:
        return has_training_bearer_service_token(request, setting_name="TRAINING_JUPYTERHUB_SERVICE_TOKEN")


class IsTrainingGraderService(BasePermission):
    message = "Training grader service token required."

    def has_permission(self, request, view) -> bool:
        return has_training_bearer_service_token(request, setting_name="TRAINING_GRADER_WEBHOOK_SECRET")


class IsTrainingDirectusService(BasePermission):
    message = "Training Directus sync token required."

    def has_permission(self, request, view) -> bool:
        return has_training_bearer_service_token(request, setting_name="TRAINING_DIRECTUS_SYNC_TOKEN")
