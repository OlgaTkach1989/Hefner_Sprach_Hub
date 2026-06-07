from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone as dt_timezone
import logging
from typing import Any
from urllib.parse import quote
from uuid import UUID

import requests
from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.online.models import OnlineAttendance, OnlineEnrollment, OnlineSession
from apps.online.services.stats import ONLINE_DASHBOARD_ENROLLMENT_STATUSES

logger = logging.getLogger(__name__)


class GraphSyncNotConfigured(Exception):
    pass


class GraphSyncRequestError(Exception):
    pass


@dataclass
class GraphAttendanceSyncPayload:
    summary: dict[str, int]
    students_total: int
    rows_total: int
    meeting_id: str
    report_id: str


@dataclass
class GraphAttendanceProbePayload:
    organizer_user_id: str
    meeting_id: str
    report_id: str
    records_total: int


@dataclass
class GraphMeetingCreatePayload:
    organizer_user_id: str
    meeting_id: str
    join_url: str


_TOKEN_CACHE: dict[str, Any] = {
    "access_token": "",
    "expires_at": None,
}


def _get_setting(name: str, default: str = "") -> str:
    value = getattr(settings, name, default)
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _graph_base_url() -> str:
    return _get_setting("ONLINE_GRAPH_API_BASE_URL", "https://graph.microsoft.com/v1.0").rstrip("/")


def _graph_timeout() -> int:
    raw = _get_setting("ONLINE_GRAPH_TIMEOUT_SECONDS", "15")
    try:
        return max(5, int(raw))
    except ValueError:
        return 15


def _graph_scope() -> str:
    base = _graph_base_url()
    if base.endswith("/v1.0"):
        base = base[:-5]
    elif base.endswith("/beta"):
        base = base[:-5]
    return f"{base.rstrip('/')}/.default"


def _token_endpoint(tenant_id: str) -> str:
    return f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"


def _resolve_graph_credentials() -> tuple[str, str, str]:
    tenant_id = _get_setting("ONLINE_GRAPH_TENANT_ID") or _get_setting("AZUREAD_OAUTH2_TENANT_ID")
    client_id = _get_setting("ONLINE_GRAPH_CLIENT_ID") or _get_setting("AZUREAD_OAUTH2_KEY")
    client_secret = _get_setting("ONLINE_GRAPH_CLIENT_SECRET")
    if not tenant_id or not client_id or not client_secret:
        raise GraphSyncNotConfigured("Microsoft Graph app credentials are not configured.")
    return tenant_id, client_id, client_secret


def _get_graph_access_token() -> str:
    tenant_id, client_id, client_secret = _resolve_graph_credentials()

    cached_token = str(_TOKEN_CACHE.get("access_token") or "").strip()
    cached_expires_at = _TOKEN_CACHE.get("expires_at")
    if cached_token and cached_expires_at and timezone.now() < cached_expires_at - timedelta(seconds=60):
        return cached_token

    try:
        response = requests.post(
            _token_endpoint(tenant_id),
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
                "scope": _graph_scope(),
            },
            timeout=_graph_timeout(),
        )
    except requests.RequestException as exc:
        raise GraphSyncRequestError(f"Graph token request failed: {exc}") from exc
    if response.status_code >= 400:
        raise GraphSyncRequestError(f"Graph token request failed ({response.status_code}): {response.text}")

    payload = response.json()
    access_token = str(payload.get("access_token") or "").strip()
    if not access_token:
        raise GraphSyncRequestError("Graph token response does not include access_token.")

    try:
        expires_in = int(payload.get("expires_in") or 3599)
    except (TypeError, ValueError):
        expires_in = 3599

    _TOKEN_CACHE["access_token"] = access_token
    _TOKEN_CACHE["expires_at"] = timezone.now() + timedelta(seconds=max(60, expires_in))
    return access_token


def _parse_graph_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    parsed = parse_datetime(str(value))
    if not parsed:
        return None
    if timezone.is_naive(parsed):
        return parsed.replace(tzinfo=dt_timezone.utc)
    return parsed


def _min_aware_datetime() -> datetime:
    return datetime.min.replace(tzinfo=dt_timezone.utc)


def _format_graph_datetime(value: datetime) -> str:
    normalized = value.astimezone(dt_timezone.utc).replace(microsecond=0)
    return normalized.isoformat().replace("+00:00", "Z")


def _graph_get_json(path: str, *, params: dict[str, str] | None = None, absolute_url: str | None = None) -> dict[str, Any]:
    token = _get_graph_access_token()
    url = absolute_url or f"{_graph_base_url()}{path}"
    try:
        response = requests.get(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            },
            params=params,
            timeout=_graph_timeout(),
        )
    except requests.RequestException as exc:
        raise GraphSyncRequestError(f"Graph request failed for {url}: {exc}") from exc
    if response.status_code >= 400:
        raise GraphSyncRequestError(f"Graph request failed ({response.status_code}) {url}: {response.text}")
    payload = response.json()
    if not isinstance(payload, dict):
        raise GraphSyncRequestError(f"Graph response payload is not a JSON object for {url}.")
    return payload


def _graph_post_json(path: str, *, payload: dict[str, Any]) -> dict[str, Any]:
    token = _get_graph_access_token()
    url = f"{_graph_base_url()}{path}"
    try:
        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=_graph_timeout(),
        )
    except requests.RequestException as exc:
        raise GraphSyncRequestError(f"Graph request failed for {url}: {exc}") from exc
    if response.status_code >= 400:
        raise GraphSyncRequestError(f"Graph request failed ({response.status_code}) {url}: {response.text}")
    parsed_payload = response.json()
    if not isinstance(parsed_payload, dict):
        raise GraphSyncRequestError(f"Graph response payload is not a JSON object for {url}.")
    return parsed_payload


def _graph_collect_pages(path: str, *, params: dict[str, str] | None = None) -> list[dict[str, Any]]:
    payload = _graph_get_json(path, params=params)
    value = payload.get("value") or []
    items: list[dict[str, Any]] = [item for item in value if isinstance(item, dict)]
    next_link = str(payload.get("@odata.nextLink") or "").strip()

    while next_link:
        payload = _graph_get_json("", absolute_url=next_link)
        value = payload.get("value") or []
        items.extend(item for item in value if isinstance(item, dict))
        next_link = str(payload.get("@odata.nextLink") or "").strip()

    return items


def _resolve_organizer_identifier(session: OnlineSession) -> str:
    configured_user_id = _get_setting("ONLINE_GRAPH_ORGANIZER_USER_ID")
    if configured_user_id:
        return configured_user_id

    configured_email = _get_setting("ONLINE_GRAPH_ORGANIZER_EMAIL")
    if configured_email:
        return configured_email

    teacher = getattr(session.cohort, "teacher", None)
    if teacher and getattr(teacher, "Schule_Email", ""):
        return str(teacher.Schule_Email).strip()

    raise GraphSyncNotConfigured("Graph organizer user identifier is not configured.")


def _resolve_organizer_user_id(raw_identifier: str) -> str:
    normalized = raw_identifier.strip()
    if not normalized:
        raise GraphSyncNotConfigured("Graph organizer user identifier is empty.")

    try:
        UUID(normalized)
        return normalized
    except ValueError:
        pass

    user_payload = _graph_get_json(f"/users/{quote(normalized, safe='')}", params={"$select": "id"})
    user_id = str(user_payload.get("id") or "").strip()
    if not user_id:
        raise GraphSyncRequestError("Unable to resolve organizer user ID from Graph.")
    return user_id


def _escape_odata_string(value: str) -> str:
    return value.replace("'", "''")


def _meeting_id_by_join_url(*, organizer_user_id: str, join_url: str) -> str:
    normalized_join_url = join_url.strip()
    if not normalized_join_url:
        raise GraphSyncNotConfigured("Session join URL is missing.")

    filter_value = f"JoinWebUrl eq '{_escape_odata_string(normalized_join_url)}'"
    meetings = _graph_collect_pages(
        f"/users/{quote(organizer_user_id, safe='')}/onlineMeetings",
        params={
            "$filter": filter_value,
        },
    )

    if not meetings:
        # Tenant-level lookup (fallback path used by some Graph tenants).
        try:
            meetings = _graph_collect_pages(
                "/communications/onlineMeetings",
                params={
                    "$filter": f"joinWebUrl eq '{_escape_odata_string(normalized_join_url)}'",
                },
            )
        except GraphSyncRequestError:
            meetings = []

    if not meetings:
        raise GraphSyncRequestError("Graph did not return online meeting for provided join URL.")

    meetings_sorted = sorted(
        meetings,
        key=lambda item: _parse_graph_datetime(item.get("startDateTime")) or _min_aware_datetime(),
        reverse=True,
    )
    meeting_id = str(meetings_sorted[0].get("id") or "").strip()
    if not meeting_id:
        raise GraphSyncRequestError("Graph online meeting payload has no id.")
    return meeting_id


def _latest_report_id(*, organizer_user_id: str, meeting_id: str) -> str:
    reports = _graph_collect_pages(
        f"/users/{quote(organizer_user_id, safe='')}/onlineMeetings/{quote(meeting_id, safe='')}/attendanceReports",
    )
    if not reports:
        raise GraphSyncRequestError("Graph attendance reports list is empty for this meeting.")

    reports_sorted = sorted(
        reports,
        key=lambda item: _parse_graph_datetime(item.get("meetingEndDateTime") or item.get("meetingStartDateTime"))
        or _min_aware_datetime(),
        reverse=True,
    )
    report_id = str(reports_sorted[0].get("id") or "").strip()
    if not report_id:
        raise GraphSyncRequestError("Graph attendance report payload has no id.")
    return report_id


def _attendance_records(*, organizer_user_id: str, meeting_id: str, report_id: str) -> list[dict[str, Any]]:
    return _graph_collect_pages(
        f"/users/{quote(organizer_user_id, safe='')}/onlineMeetings/{quote(meeting_id, safe='')}/attendanceReports/{quote(report_id, safe='')}/attendanceRecords",
    )


def create_online_meeting_for_session(*, session: OnlineSession) -> GraphMeetingCreatePayload:
    organizer_identifier = _resolve_organizer_identifier(session)
    organizer_user_id = _resolve_organizer_user_id(organizer_identifier)
    meeting_payload = _graph_post_json(
        f"/users/{quote(organizer_user_id, safe='')}/onlineMeetings",
        payload={
            "subject": session.title,
            "startDateTime": _format_graph_datetime(session.starts_at),
            "endDateTime": _format_graph_datetime(session.ends_at),
        },
    )
    meeting_id = str(meeting_payload.get("id") or "").strip()
    join_url = str(meeting_payload.get("joinWebUrl") or "").strip()
    if not meeting_id:
        raise GraphSyncRequestError("Graph create meeting response has no id.")
    if not join_url:
        raise GraphSyncRequestError("Graph create meeting response has no joinWebUrl.")

    update_fields: list[str] = []
    if session.provider_meeting_id != meeting_id:
        session.provider_meeting_id = meeting_id
        update_fields.append("provider_meeting_id")
    if session.join_url != join_url:
        session.join_url = join_url
        update_fields.append("join_url")
    if update_fields:
        session.save(update_fields=update_fields + ["updated_at"])

    return GraphMeetingCreatePayload(
        organizer_user_id=organizer_user_id,
        meeting_id=meeting_id,
        join_url=join_url,
    )


def _load_graph_context_for_session(session: OnlineSession) -> tuple[str, str, str, list[dict[str, Any]]]:
    organizer_identifier = _resolve_organizer_identifier(session)
    organizer_user_id = _resolve_organizer_user_id(organizer_identifier)
    meeting_id = (session.provider_meeting_id or "").strip()
    if not meeting_id:
        meeting_id = _meeting_id_by_join_url(organizer_user_id=organizer_user_id, join_url=session.join_url or "")
        session.provider_meeting_id = meeting_id
        session.save(update_fields=["provider_meeting_id", "updated_at"])
    report_id = _latest_report_id(organizer_user_id=organizer_user_id, meeting_id=meeting_id)
    records = _attendance_records(organizer_user_id=organizer_user_id, meeting_id=meeting_id, report_id=report_id)
    return organizer_user_id, meeting_id, report_id, records


def probe_session_attendance_from_graph(*, session: OnlineSession) -> GraphAttendanceProbePayload:
    organizer_user_id, meeting_id, report_id, records = _load_graph_context_for_session(session)
    return GraphAttendanceProbePayload(
        organizer_user_id=organizer_user_id,
        meeting_id=meeting_id,
        report_id=report_id,
        records_total=len(records),
    )


def _record_email(row: dict[str, Any]) -> str:
    candidates = [
        row.get("emailAddress"),
        (row.get("identity") or {}).get("emailAddress") if isinstance(row.get("identity"), dict) else "",
        (row.get("registrant") or {}).get("email") if isinstance(row.get("registrant"), dict) else "",
    ]
    for raw in candidates:
        email = str(raw or "").strip().lower()
        if email:
            return email
    return ""


def _record_total_seconds(row: dict[str, Any]) -> int:
    try:
        total_seconds = int(row.get("totalAttendanceInSeconds") or 0)
    except (TypeError, ValueError):
        total_seconds = 0

    intervals = row.get("attendanceIntervals") or []
    if isinstance(intervals, list):
        for interval in intervals:
            if not isinstance(interval, dict):
                continue
            joined_at = _parse_graph_datetime(interval.get("joinDateTime"))
            left_at = _parse_graph_datetime(interval.get("leaveDateTime"))
            if joined_at and left_at:
                duration = int(max(0, (left_at - joined_at).total_seconds()))
                if duration > total_seconds:
                    total_seconds = duration
    return total_seconds


def _record_joined_left(row: dict[str, Any]) -> tuple[datetime | None, datetime | None]:
    joined_at: datetime | None = None
    left_at: datetime | None = None
    intervals = row.get("attendanceIntervals") or []
    if not isinstance(intervals, list):
        return joined_at, left_at

    for interval in intervals:
        if not isinstance(interval, dict):
            continue
        interval_joined = _parse_graph_datetime(interval.get("joinDateTime"))
        interval_left = _parse_graph_datetime(interval.get("leaveDateTime"))
        if interval_joined and (joined_at is None or interval_joined < joined_at):
            joined_at = interval_joined
        if interval_left and (left_at is None or interval_left > left_at):
            left_at = interval_left
    return joined_at, left_at


def _records_index(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_email: dict[str, dict[str, Any]] = {}
    for row in records:
        email = _record_email(row)
        if not email:
            continue

        total_seconds = _record_total_seconds(row)
        joined_at, left_at = _record_joined_left(row)
        existing = by_email.get(email)
        if existing and int(existing.get("total_seconds") or 0) > total_seconds:
            continue
        by_email[email] = {
            "total_seconds": total_seconds,
            "joined_at": joined_at,
            "left_at": left_at,
        }
    return by_email


def _attendance_summary_for_session(*, session: OnlineSession, expected_total: int) -> dict[str, int]:
    rows = session.attendance_records.all()
    summary = {"present": 0, "absent": 0, "excused": 0, "unknown": 0}
    for row in rows:
        if row.status in summary:
            summary[row.status] += 1
        else:
            summary["unknown"] += 1

    counted = summary["present"] + summary["absent"] + summary["excused"] + summary["unknown"]
    if counted < expected_total:
        summary["unknown"] += expected_total - counted
    return summary


def sync_session_attendance_from_graph(*, session: OnlineSession) -> GraphAttendanceSyncPayload:
    organizer_user_id, meeting_id, report_id, records = _load_graph_context_for_session(session)
    records_by_email = _records_index(records)

    enrollments = list(
        OnlineEnrollment.objects.filter(
            cohort=session.cohort,
            status__in=ONLINE_DASHBOARD_ENROLLMENT_STATUSES,
        ).select_related("profile__user")
    )
    now = timezone.now()

    for enrollment in enrollments:
        row, _ = OnlineAttendance.objects.get_or_create(
            enrollment=enrollment,
            session=session,
            defaults={"status": OnlineAttendance.STATUS_UNKNOWN},
        )
        email = str(enrollment.profile.user.email or "").strip().lower()
        match = records_by_email.get(email)

        if match:
            update_fields: list[str] = []
            if row.status != OnlineAttendance.STATUS_PRESENT:
                row.status = OnlineAttendance.STATUS_PRESENT
                update_fields.append("status")

            matched_seconds = int(match.get("total_seconds") or 0)
            if matched_seconds > row.attended_seconds:
                row.attended_seconds = matched_seconds
                update_fields.append("attended_seconds")

            joined_at = match.get("joined_at") or row.joined_at
            left_at = match.get("left_at") or row.left_at
            if joined_at and row.joined_at != joined_at:
                row.joined_at = joined_at
                update_fields.append("joined_at")
            if left_at and row.left_at != left_at:
                row.left_at = left_at
                update_fields.append("left_at")

            if row.joined_at and row.left_at:
                attendance_duration = int(max(0, (row.left_at - row.joined_at).total_seconds()))
                if attendance_duration > row.attended_seconds:
                    row.attended_seconds = attendance_duration
                    if "attended_seconds" not in update_fields:
                        update_fields.append("attended_seconds")

            if session.status == OnlineSession.STATUS_ENDED and row.joined_at and row.left_at is None:
                row.left_at = min(now, session.ends_at)
                update_fields.append("left_at")
                final_duration = int(max(0, (row.left_at - row.joined_at).total_seconds()))
                if final_duration > row.attended_seconds:
                    row.attended_seconds = final_duration
                    if "attended_seconds" not in update_fields:
                        update_fields.append("attended_seconds")

            if update_fields:
                row.save(update_fields=update_fields + ["updated_at"])
            continue

        if row.status == OnlineAttendance.STATUS_PRESENT and row.joined_at:
            if session.status == OnlineSession.STATUS_ENDED and row.left_at is None:
                row.left_at = min(now, session.ends_at)
                row.attended_seconds = int(max(0, (row.left_at - row.joined_at).total_seconds()))
                row.save(update_fields=["left_at", "attended_seconds", "updated_at"])
            continue

        next_status = (
            OnlineAttendance.STATUS_ABSENT
            if session.status == OnlineSession.STATUS_ENDED
            else OnlineAttendance.STATUS_UNKNOWN
        )
        if (
            row.status != next_status
            or row.attended_seconds != 0
            or row.joined_at is not None
            or row.left_at is not None
        ):
            row.status = next_status
            row.attended_seconds = 0
            row.joined_at = None
            row.left_at = None
            row.save(update_fields=["status", "attended_seconds", "joined_at", "left_at", "updated_at"])

    rows_total = OnlineAttendance.objects.filter(session=session, enrollment__in=enrollments).count()
    summary = _attendance_summary_for_session(session=session, expected_total=len(enrollments))
    logger.info(
        "Graph attendance sync finished: session=%s meeting=%s report=%s students=%s records=%s rows=%s",
        session.id,
        meeting_id,
        report_id,
        len(enrollments),
        len(records),
        rows_total,
    )
    return GraphAttendanceSyncPayload(
        summary=summary,
        students_total=len(enrollments),
        rows_total=rows_total,
        meeting_id=meeting_id,
        report_id=report_id,
    )
