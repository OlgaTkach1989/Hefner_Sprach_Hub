from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from django.utils import timezone

from apps.online.models import OnlineCohort, OnlineSession
from apps.online.services.attendance_service import AttendanceSyncResult, sync_session_attendance_and_stamp


ALLOWED_SESSION_STATUS_TRANSITIONS: dict[str, set[str]] = {
    OnlineSession.STATUS_SCHEDULED: {OnlineSession.STATUS_LIVE, OnlineSession.STATUS_CANCELED},
    OnlineSession.STATUS_LIVE: {OnlineSession.STATUS_ENDED, OnlineSession.STATUS_CANCELED},
    OnlineSession.STATUS_ENDED: set(),
    OnlineSession.STATUS_CANCELED: set(),
}


class SessionLifecycleError(Exception):
    pass


@dataclass
class SessionTransitionResult:
    session: OnlineSession
    cohort_status: str
    sync_result: AttendanceSyncResult | None = None
    sync_error: str = ""


def update_cohort_status_from_sessions(cohort: OnlineCohort) -> None:
    statuses = set(cohort.sessions.values_list("status", flat=True))
    if not statuses:
        return

    if statuses.issubset({OnlineSession.STATUS_ENDED, OnlineSession.STATUS_CANCELED}):
        if cohort.status != OnlineCohort.STATUS_FINISHED:
            cohort.status = OnlineCohort.STATUS_FINISHED
            cohort.save(update_fields=["status", "updated_at"])
        return

    if OnlineSession.STATUS_LIVE in statuses:
        if cohort.status != OnlineCohort.STATUS_RUNNING:
            cohort.status = OnlineCohort.STATUS_RUNNING
            cohort.save(update_fields=["status", "updated_at"])
        return

    if cohort.status == OnlineCohort.STATUS_RUNNING:
        cohort.status = OnlineCohort.STATUS_OPEN
        cohort.save(update_fields=["status", "updated_at"])


def is_valid_session_status_transition(current_status: str, next_status: str) -> bool:
    if current_status == next_status:
        return True
    return next_status in ALLOWED_SESSION_STATUS_TRANSITIONS.get(current_status, set())


def get_other_live_session(*, session: OnlineSession) -> OnlineSession | None:
    return (
        OnlineSession.objects.select_related("cohort")
        .filter(cohort=session.cohort, status=OnlineSession.STATUS_LIVE)
        .exclude(id=session.id)
        .order_by("starts_at", "id")
        .first()
    )


def ensure_single_live_session(*, session: OnlineSession) -> None:
    other_live = get_other_live_session(session=session)
    if other_live is None:
        return
    raise SessionLifecycleError(
        f'Another live session "{other_live.title}" is already open in this cohort. '
        "End it before opening a new session."
    )


def apply_session_status_transition(
    *,
    session: OnlineSession,
    next_status: str,
    sync_attendance_on_end: bool = True,
) -> SessionTransitionResult:
    current_status = session.status
    if not is_valid_session_status_transition(current_status, next_status):
        allowed = sorted(ALLOWED_SESSION_STATUS_TRANSITIONS.get(current_status, set()))
        raise SessionLifecycleError(
            f"Invalid transition from '{current_status}' to '{next_status}'. "
            f"Allowed next statuses: {allowed or 'none'}."
        )

    if next_status == OnlineSession.STATUS_LIVE and current_status != OnlineSession.STATUS_LIVE:
        ensure_single_live_session(session=session)

    if current_status != next_status:
        session.status = next_status
        session.is_completed = next_status == OnlineSession.STATUS_ENDED
        session.save(update_fields=["status", "is_completed", "updated_at"])

    if next_status == OnlineSession.STATUS_LIVE:
        if session.cohort.status != OnlineCohort.STATUS_RUNNING:
            session.cohort.status = OnlineCohort.STATUS_RUNNING
            session.cohort.save(update_fields=["status", "updated_at"])
        return SessionTransitionResult(session=session, cohort_status=session.cohort.status)

    update_cohort_status_from_sessions(session.cohort)

    sync_result: AttendanceSyncResult | None = None
    sync_error = ""
    if next_status == OnlineSession.STATUS_ENDED and sync_attendance_on_end:
        try:
            sync_result = sync_session_attendance_and_stamp(session=session)
        except Exception as exc:  # noqa: BLE001 - keep lifecycle state consistent even if sync fails
            sync_error = str(exc)

    return SessionTransitionResult(
        session=session,
        cohort_status=session.cohort.status,
        sync_result=sync_result,
        sync_error=sync_error,
    )


def auto_end_overdue_live_sessions(
    *,
    grace_period: timedelta = timedelta(),
    session_ids: list[int] | None = None,
    limit: int = 100,
) -> list[SessionTransitionResult]:
    threshold = timezone.now() - grace_period
    queryset = (
        OnlineSession.objects.select_related("cohort")
        .filter(status=OnlineSession.STATUS_LIVE, ends_at__lte=threshold)
        .order_by("ends_at", "id")
    )
    if session_ids:
        queryset = queryset.filter(id__in=session_ids)

    results: list[SessionTransitionResult] = []
    for session in queryset[: max(1, limit)]:
        results.append(
            apply_session_status_transition(
                session=session,
                next_status=OnlineSession.STATUS_ENDED,
                sync_attendance_on_end=True,
            )
        )
    return results
