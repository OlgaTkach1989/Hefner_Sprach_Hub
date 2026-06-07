from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from apps.training.models import TrainingNotebookLabProfile


class TrainingRuntimePolicyError(Exception):
    """Runtime policy is invalid or unsupported by the current deployment."""


@dataclass(frozen=True)
class ResolvedTrainingRuntimePolicy:
    allow_gpu: bool
    allow_network: bool
    max_session_minutes: int
    session_expires_at: object


def training_runtime_gpu_enabled() -> bool:
    return bool(getattr(settings, "TRAINING_JUPYTERHUB_GPU_RUNTIME_ENABLED", False))


def training_runtime_network_egress_enabled() -> bool:
    return bool(getattr(settings, "TRAINING_JUPYTERHUB_EGRESS_ENABLED", False))


def training_runtime_max_session_minutes_cap() -> int:
    raw_value = int(getattr(settings, "TRAINING_MAX_LAB_SESSION_MINUTES_CAP", 240) or 240)
    return max(15, min(raw_value, 24 * 60))


def resolve_training_runtime_policy(*, lab_profile: TrainingNotebookLabProfile) -> ResolvedTrainingRuntimePolicy:
    requested_gpu = bool(lab_profile.allow_gpu)
    requested_network = bool(lab_profile.allow_network)

    if requested_gpu and not training_runtime_gpu_enabled():
        raise TrainingRuntimePolicyError("GPU-enabled notebook runtime is not available in this deployment.")
    if requested_network and not training_runtime_network_egress_enabled():
        raise TrainingRuntimePolicyError("Network-enabled notebook runtime is not available in this deployment.")

    session_minutes_cap = training_runtime_max_session_minutes_cap()
    requested_session_minutes = int(lab_profile.max_session_minutes or session_minutes_cap)
    effective_session_minutes = max(15, min(requested_session_minutes, session_minutes_cap))
    session_expires_at = timezone.now() + timedelta(minutes=effective_session_minutes)
    return ResolvedTrainingRuntimePolicy(
        allow_gpu=requested_gpu,
        allow_network=requested_network,
        max_session_minutes=effective_session_minutes,
        session_expires_at=session_expires_at,
    )
