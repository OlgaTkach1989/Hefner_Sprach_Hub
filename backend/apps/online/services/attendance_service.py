from __future__ import annotations

from dataclasses import dataclass
import logging

from django.conf import settings
from django.utils import timezone

from apps.online.models import OnlineAttendance, OnlineEnrollment, OnlineSession, OnlineStudentProfile
from apps.online.services.graph_attendance_service import (
    GraphSyncNotConfigured,
    GraphSyncRequestError,
    sync_session_attendance_from_graph,
)
from apps.online.services.stats import ONLINE_DASHBOARD_ENROLLMENT_STATUSES

logger = logging.getLogger(__name__)


SYNC_MODE_MANUAL = "manual"
SYNC_MODE_DEMO = "demo"
SYNC_MODE_GRAPH = "graph"
SYNC_MODE_CHOICES = {SYNC_MODE_MANUAL, SYNC_MODE_DEMO, SYNC_MODE_GRAPH}


def get_attendance_sync_mode() -> str:
    raw_mode = str(getattr(settings, "ONLINE_ATTENDANCE_SYNC_MODE", SYNC_MODE_DEMO)).strip().lower()
    if raw_mode in SYNC_MODE_CHOICES:
        return raw_mode
    return SYNC_MODE_DEMO


def get_session_enrollments(session: OnlineSession):
    return OnlineEnrollment.objects.filter(
        cohort=session.cohort,
        status__in=ONLINE_DASHBOARD_ENROLLMENT_STATUSES,
    ).select_related("profile", "profile__user")


def attendance_summary_for_session(*, session: OnlineSession, expected_total: int | None = None) -> dict[str, int]:
    rows = session.attendance_records.all()
    summary = {"present": 0, "absent": 0, "excused": 0, "unknown": 0}
    for row in rows:
        if row.status in summary:
            summary[row.status] += 1
        else:
            summary["unknown"] += 1

    if expected_total is not None:
        counted = summary["present"] + summary["absent"] + summary["excused"] + summary["unknown"]
        if counted < expected_total:
            summary["unknown"] += expected_total - counted
    return summary


def mark_student_join_for_session(*, profile: OnlineStudentProfile, session: OnlineSession) -> OnlineAttendance:
    enrollment = (
        get_session_enrollments(session)
        .filter(profile=profile)
        .first()
    )
    if enrollment is None:
        raise ValueError("Student is not enrolled in this session cohort.")

    now = timezone.now()
    attendance, created = OnlineAttendance.objects.get_or_create(
        enrollment=enrollment,
        session=session,
        defaults={
            "status": OnlineAttendance.STATUS_PRESENT,
            "joined_at": now,
        },
    )
    if created:
        return attendance

    update_fields: list[str] = []
    if attendance.status != OnlineAttendance.STATUS_PRESENT:
        attendance.status = OnlineAttendance.STATUS_PRESENT
        update_fields.append("status")
    if attendance.joined_at is None:
        attendance.joined_at = now
        update_fields.append("joined_at")
    if attendance.left_at is not None and session.status != OnlineSession.STATUS_ENDED:
        attendance.left_at = None
        update_fields.append("left_at")

    if update_fields:
        attendance.save(update_fields=update_fields + ["updated_at"])
    return attendance


@dataclass
class AttendanceSyncResult:
    summary: dict[str, int]
    sync: str
    students_total: int
    rows_total: int


def _finalize_row_for_ended_session(row: OnlineAttendance, *, session: OnlineSession) -> None:
    if session.status != OnlineSession.STATUS_ENDED:
        return
    if row.joined_at is None:
        if row.status == OnlineAttendance.STATUS_UNKNOWN:
            row.status = OnlineAttendance.STATUS_ABSENT
        return
    if row.left_at is None:
        row.left_at = min(timezone.now(), session.ends_at)
    delta = int(max(0, (row.left_at - row.joined_at).total_seconds()))
    if delta > row.attended_seconds:
        row.attended_seconds = delta
    if row.status != OnlineAttendance.STATUS_PRESENT:
        row.status = OnlineAttendance.STATUS_PRESENT


def _sync_attendance_demo(*, session: OnlineSession) -> AttendanceSyncResult:
    enrollments = list(get_session_enrollments(session))
    enrollment_ids = [item.id for item in enrollments]
    rows = {
        item.enrollment_id: item
        for item in OnlineAttendance.objects.filter(session=session, enrollment_id__in=enrollment_ids)
    }

    for enrollment in enrollments:
        row = rows.get(enrollment.id)
        if row is None:
            default_status = (
                OnlineAttendance.STATUS_ABSENT
                if session.status == OnlineSession.STATUS_ENDED
                else OnlineAttendance.STATUS_UNKNOWN
            )
            row = OnlineAttendance.objects.create(
                enrollment=enrollment,
                session=session,
                status=default_status,
            )
            rows[enrollment.id] = row
            continue

        before = (row.status, row.joined_at, row.left_at, row.attended_seconds)
        _finalize_row_for_ended_session(row, session=session)
        after = (row.status, row.joined_at, row.left_at, row.attended_seconds)
        if before != after:
            row.save(update_fields=["status", "left_at", "attended_seconds", "updated_at"])

    summary = attendance_summary_for_session(session=session, expected_total=len(enrollments))
    return AttendanceSyncResult(
        summary=summary,
        sync="manual_demo",
        students_total=len(enrollments),
        rows_total=len(rows),
    )


def _sync_attendance_manual(*, session: OnlineSession) -> AttendanceSyncResult:
    students_total = get_session_enrollments(session).count()
    summary = attendance_summary_for_session(session=session, expected_total=students_total)
    rows_total = (
        summary["present"]
        + summary["absent"]
        + summary["excused"]
        + summary["unknown"]
    )
    return AttendanceSyncResult(
        summary=summary,
        sync="manual_noop",
        students_total=students_total,
        rows_total=rows_total,
    )


def sync_session_attendance(*, session: OnlineSession) -> AttendanceSyncResult:
    mode = get_attendance_sync_mode()
    if mode == SYNC_MODE_MANUAL:
        return _sync_attendance_manual(session=session)
    if mode == SYNC_MODE_GRAPH:
        try:
            graph_payload = sync_session_attendance_from_graph(session=session)
            return AttendanceSyncResult(
                summary=graph_payload.summary,
                sync="graph",
                students_total=graph_payload.students_total,
                rows_total=graph_payload.rows_total,
            )
        except GraphSyncNotConfigured as exc:
            logger.warning(
                "Graph attendance sync is not configured for session=%s. Falling back to demo mode. reason=%s",
                session.id,
                exc,
            )
            fallback = _sync_attendance_demo(session=session)
            return AttendanceSyncResult(
                summary=fallback.summary,
                sync="graph_not_configured_demo",
                students_total=fallback.students_total,
                rows_total=fallback.rows_total,
            )
        except GraphSyncRequestError as exc:
            logger.warning(
                "Graph attendance sync request failed for session=%s. Falling back to demo mode. reason=%s",
                session.id,
                exc,
            )
            fallback = _sync_attendance_demo(session=session)
            return AttendanceSyncResult(
                summary=fallback.summary,
                sync="graph_error_demo",
                students_total=fallback.students_total,
                rows_total=fallback.rows_total,
            )
    return _sync_attendance_demo(session=session)


def sync_session_attendance_and_stamp(*, session: OnlineSession) -> AttendanceSyncResult:
    result = sync_session_attendance(session=session)
    session.attendance_synced_at = timezone.now()
    session.save(update_fields=["attendance_synced_at", "updated_at"])
    return result
