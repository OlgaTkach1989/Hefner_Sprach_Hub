from __future__ import annotations

from collections import Counter
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from apps.online.models import (
    OnlineAuditEvent,
    OnlineCompletionEvidence,
    OnlineCohort,
    OnlineCourse,
    OnlineEnrollment,
    OnlineIdentityLink,
    OnlineIdentityProvider,
    OnlineScopeAssignment,
    OnlineSession,
)
from apps.online.services.completion import build_enrollment_completion_summary
from apps.online.services.governance import build_course_release_readiness_payload


REPORT_ENROLLMENT_STATUSES = (
    OnlineEnrollment.STATUS_TRIAL,
    OnlineEnrollment.STATUS_ACTIVE,
    OnlineEnrollment.STATUS_COMPLETED,
)


def _course_title(course: OnlineCourse | None) -> str:
    if course is None:
        return "Unknown course"
    return (course.title_en or course.title_de or course.slug or "Unknown course").strip()


def scope_key_for(*, scope_type: str, course: OnlineCourse | None = None, cohort: OnlineCohort | None = None) -> str:
    if scope_type == OnlineScopeAssignment.SCOPE_ACADEMY:
        return "academy"
    if scope_type == OnlineScopeAssignment.SCOPE_COURSE and course is not None:
        return f"course:{course.id}"
    if scope_type == OnlineScopeAssignment.SCOPE_COHORT and cohort is not None:
        return f"cohort:{cohort.id}"
    return scope_type


def scope_assignment_scope_label(assignment: OnlineScopeAssignment) -> str:
    if assignment.scope_type == OnlineScopeAssignment.SCOPE_ACADEMY:
        return "Academy-wide"
    if assignment.scope_type == OnlineScopeAssignment.SCOPE_COURSE and assignment.course_id:
        return _course_title(assignment.course)
    if assignment.scope_type == OnlineScopeAssignment.SCOPE_COHORT and assignment.cohort_id:
        cohort = assignment.cohort
        return f"{_course_title(cohort.course)} / {cohort.group_code}"
    return assignment.scope_type.replace("_", " ").title()


def identity_provider_is_ready(provider: OnlineIdentityProvider) -> bool:
    if provider.provider_type == OnlineIdentityProvider.PROVIDER_LOCAL_PASSWORD:
        return True
    if provider.verification_status == OnlineIdentityProvider.STATUS_READY:
        return True
    return bool(provider.client_id and (provider.discovery_url or provider.authorization_url or provider.issuer))


def identity_provider_payload(provider: OnlineIdentityProvider) -> dict[str, Any]:
    is_ready = identity_provider_is_ready(provider)
    effective_status = provider.verification_status
    if is_ready and effective_status == OnlineIdentityProvider.STATUS_DRAFT:
        effective_status = OnlineIdentityProvider.STATUS_READY
    return {
        "id": provider.id,
        "slug": provider.slug,
        "displayName": provider.display_name,
        "providerType": provider.provider_type,
        "providerLabel": dict(OnlineIdentityProvider.PROVIDER_CHOICES).get(provider.provider_type, provider.provider_type),
        "issuer": provider.issuer,
        "discoveryUrl": provider.discovery_url,
        "authorizationUrl": provider.authorization_url,
        "tokenUrl": provider.token_url,
        "jwksUrl": provider.jwks_url,
        "redirectUri": provider.redirect_uri,
        "tenantId": provider.tenant_id,
        "clientId": provider.client_id,
        "scopes": list(provider.scopes or []),
        "claimMap": provider.claim_map or {},
        "isEnabled": provider.is_enabled,
        "isSso": provider.is_sso,
        "isDefault": provider.is_default,
        "isReady": is_ready,
        "verificationStatus": effective_status,
        "verificationLabel": dict(OnlineIdentityProvider.STATUS_CHOICES).get(effective_status, effective_status.title()),
        "verificationMessage": provider.verification_message,
        "lastVerifiedAt": provider.last_verified_at,
    }


def scope_assignment_payload(assignment: OnlineScopeAssignment) -> dict[str, Any]:
    user = assignment.user
    full_name = f"{user.first_name} {user.last_name}".strip() or user.email
    course = assignment.course or (assignment.cohort.course if assignment.cohort_id else None)
    return {
        "id": assignment.id,
        "role": assignment.role,
        "roleLabel": dict(OnlineScopeAssignment.ROLE_CHOICES).get(assignment.role, assignment.role.replace("_", " ").title()),
        "scopeType": assignment.scope_type,
        "scopeTypeLabel": dict(OnlineScopeAssignment.SCOPE_CHOICES).get(assignment.scope_type, assignment.scope_type.title()),
        "scopeLabel": scope_assignment_scope_label(assignment),
        "scopeKey": assignment.scope_key,
        "note": assignment.note,
        "isPrimary": assignment.is_primary,
        "isActive": assignment.is_active,
        "createdAt": assignment.created_at,
        "createdByEmail": getattr(assignment.created_by, "email", "") or "",
        "user": {
            "id": user.id,
            "email": user.email,
            "fullName": full_name,
            "isActive": bool(user.is_active),
        },
        "course": (
            {
                "id": course.id,
                "slug": course.slug,
                "titleDe": course.title_de,
                "titleEn": course.title_en,
            }
            if course is not None
            else None
        ),
        "cohort": (
            {
                "id": assignment.cohort.id,
                "groupCode": assignment.cohort.group_code,
                "groupName": assignment.cohort.name,
                "courseId": assignment.cohort.course_id,
                "courseTitleDe": assignment.cohort.course.title_de,
                "courseTitleEn": assignment.cohort.course.title_en,
            }
            if assignment.cohort_id
            else None
        ),
    }


def scope_assignments_queryset(
    *,
    course_id: int | None = None,
    user_id: int | None = None,
    role: str = "",
    scope_type: str = "",
    active_only: bool = False,
):
    queryset = OnlineScopeAssignment.objects.select_related(
        "user",
        "course",
        "cohort",
        "cohort__course",
        "created_by",
    ).order_by("-is_primary", "-created_at", "id")
    if user_id:
        queryset = queryset.filter(user_id=user_id)
    if role:
        queryset = queryset.filter(role=role)
    if scope_type:
        queryset = queryset.filter(scope_type=scope_type)
    if active_only:
        queryset = queryset.filter(is_active=True)
    if course_id:
        queryset = queryset.filter(
            Q(scope_type=OnlineScopeAssignment.SCOPE_ACADEMY)
            | Q(course_id=course_id)
            | Q(cohort__course_id=course_id)
        ).distinct()
    return queryset


def build_identity_summary() -> dict[str, Any]:
    providers = [identity_provider_payload(provider) for provider in OnlineIdentityProvider.objects.order_by("sort_order", "id")]
    enabled = [provider for provider in providers if provider["isEnabled"]]
    ready = [provider for provider in providers if provider["isReady"]]
    default_provider = next((provider for provider in providers if provider["isDefault"]), None)
    return {
        "totalProviders": len(providers),
        "enabledProviders": len(enabled),
        "readyProviders": len(ready),
        "defaultProvider": default_provider,
        "linkedAccountsTotal": OnlineIdentityLink.objects.count(),
        "googleClientConfigured": bool(str(getattr(settings, "ONLINE_GOOGLE_CLIENT_ID", "") or "").strip()),
        "graphClientConfigured": bool(
            str(getattr(settings, "ONLINE_GRAPH_CLIENT_ID", "") or "").strip()
            and str(getattr(settings, "ONLINE_GRAPH_TENANT_ID", "") or "").strip()
        ),
        "providers": providers,
    }


def build_enterprise_reporting_summary(*, course_id: int | None = None, risk_limit: int = 8) -> dict[str, Any]:
    course_queryset = OnlineCourse.objects.all().order_by("id")
    if course_id:
        course_queryset = course_queryset.filter(id=course_id)
    courses = list(course_queryset)
    course_ids = [course.id for course in courses]

    enrollments = list(
        OnlineEnrollment.objects.select_related("profile__user", "course", "cohort")
        .filter(course_id__in=course_ids, status__in=REPORT_ENROLLMENT_STATUSES)
        .order_by("profile__last_name", "profile__first_name", "id")
    ) if course_ids else []
    now = timezone.now()
    today = timezone.localdate()
    risk_rows: list[dict[str, Any]] = []
    progress_samples: list[int] = []
    active_enrollments = 0
    completed_enrollments = 0
    ready_for_attestation = 0
    evidence_issued = 0
    attendance_alerts = 0
    overdue_enrollments = 0

    for enrollment in enrollments:
        summary = build_enrollment_completion_summary(enrollment)
        progress_percent = int(summary["progressPercent"] or 0)
        attendance_percent = float(summary["attendancePercent"] or 0)
        progress_samples.append(progress_percent)
        if enrollment.status in {OnlineEnrollment.STATUS_ACTIVE, OnlineEnrollment.STATUS_TRIAL}:
            active_enrollments += 1
        if summary["status"] == "completed":
            completed_enrollments += 1
        if summary["status"] == "ready_for_attestation":
            ready_for_attestation += 1
        if summary["evidence"] is not None:
            evidence_issued += 1

        risk_reasons: list[str] = []
        if summary["status"] == "ready_for_attestation":
            risk_reasons.append("Attestation pending")
        if not summary["requirements"]["attendanceMet"] and enrollment.course.required_attendance_percent > 0:
            attendance_alerts += 1
            risk_reasons.append("Attendance below threshold")
        if enrollment.status in {OnlineEnrollment.STATUS_ACTIVE, OnlineEnrollment.STATUS_TRIAL}:
            if enrollment.cohort.end_date and enrollment.cohort.end_date < today and summary["status"] != "completed":
                overdue_enrollments += 1
                risk_reasons.append("Cohort ended before completion")
            if progress_percent == 0 and enrollment.started_at < now - timedelta(days=7):
                risk_reasons.append("No learner progress in the last week")

        if risk_reasons:
            risk_rows.append(
                {
                    "enrollmentId": enrollment.id,
                    "fullName": f"{enrollment.profile.first_name} {enrollment.profile.last_name}".strip() or enrollment.profile.user.email,
                    "email": enrollment.profile.user.email,
                    "courseId": enrollment.course_id,
                    "courseTitle": _course_title(enrollment.course),
                    "cohortId": enrollment.cohort_id,
                    "cohortLabel": f"{enrollment.cohort.group_code} · {enrollment.cohort.name}",
                    "progressPercent": progress_percent,
                    "attendancePercent": attendance_percent,
                    "completionStatus": summary["status"],
                    "completionStatusLabel": summary["statusLabel"],
                    "evidenceIssued": summary["evidence"] is not None,
                    "attestationRequired": bool(summary["rule"]["requiresAttestation"]),
                    "riskReasons": risk_reasons,
                }
            )

    assignments = list(scope_assignments_queryset(course_id=course_id, active_only=True))
    role_counts = Counter(assignment.role for assignment in assignments)
    recent_assignments = [scope_assignment_payload(assignment) for assignment in assignments[:6]]
    sessions_queryset = OnlineSession.objects.filter(cohort__course_id__in=course_ids) if course_ids else OnlineSession.objects.none()
    cohorts_queryset = OnlineCohort.objects.filter(course_id__in=course_ids) if course_ids else OnlineCohort.objects.none()
    live_sessions = sessions_queryset.filter(status=OnlineSession.STATUS_LIVE).count()
    upcoming_sessions = sessions_queryset.filter(starts_at__gte=now, starts_at__lte=now + timedelta(days=7)).count()
    unsynced_sessions = sessions_queryset.filter(
        Q(status=OnlineSession.STATUS_ENDED) | Q(is_completed=True),
        attendance_synced_at__isnull=True,
    ).count()
    sessions_without_recording = sessions_queryset.filter(
        Q(status=OnlineSession.STATUS_ENDED) | Q(is_completed=True),
        recording_url__isnull=True,
    ).count() + sessions_queryset.filter(
        Q(status=OnlineSession.STATUS_ENDED) | Q(is_completed=True),
        recording_url="",
    ).count()
    low_attendance_cohorts = 0
    for cohort in cohorts_queryset:
        active_rows = cohort.enrollments.filter(status__in=REPORT_ENROLLMENT_STATUSES).count()
        sessions_total = cohort.sessions.count()
        if active_rows == 0 or sessions_total == 0:
            continue
        present_rows = cohort.sessions.filter(attendance_records__status="present").count()
        attendance_percent = round((present_rows / max(1, sessions_total * active_rows)) * 100, 2)
        if attendance_percent < 75:
            low_attendance_cohorts += 1

    pending_review_courses = sum(1 for course in courses if course.lifecycle_status == OnlineCourse.LIFECYCLE_IN_REVIEW)
    approved_not_published = sum(1 for course in courses if course.lifecycle_status == OnlineCourse.LIFECYCLE_APPROVED)
    publish_blocked = sum(
        1
        for course in courses
        if not build_course_release_readiness_payload(course)["isReadyForPublish"]
    )
    audit_events_last_30d = (
        OnlineAuditEvent.objects.filter(course_id__in=course_ids, created_at__gte=now - timedelta(days=30)).count()
        if course_ids
        else 0
    )
    evidence_coverage_percent = round((evidence_issued / len(enrollments)) * 100, 2) if enrollments else 0.0
    average_progress_percent = round(sum(progress_samples) / len(progress_samples), 2) if progress_samples else 0.0

    return {
        "courseId": course_id,
        "identity": build_identity_summary(),
        "scopedAccess": {
            "activeAssignments": len(assignments),
            "primaryAssignments": sum(1 for assignment in assignments if assignment.is_primary),
            "managerAssignments": role_counts.get(OnlineScopeAssignment.ROLE_MANAGER, 0),
            "deliveryManagerAssignments": role_counts.get(OnlineScopeAssignment.ROLE_DELIVERY_MANAGER, 0),
            "complianceManagerAssignments": role_counts.get(OnlineScopeAssignment.ROLE_COMPLIANCE_MANAGER, 0),
            "reviewManagerAssignments": role_counts.get(OnlineScopeAssignment.ROLE_REVIEW_MANAGER, 0),
            "recentAssignments": recent_assignments,
        },
        "learning": {
            "activeEnrollments": active_enrollments,
            "completedEnrollments": completed_enrollments,
            "readyForAttestation": ready_for_attestation,
            "evidenceIssued": evidence_issued,
            "attendanceAlerts": attendance_alerts,
            "overdueEnrollments": overdue_enrollments,
            "averageProgressPercent": average_progress_percent,
        },
        "delivery": {
            "liveSessions": live_sessions,
            "upcomingSessions7d": upcoming_sessions,
            "unsyncedAttendanceSessions": unsynced_sessions,
            "sessionsWithoutRecording": sessions_without_recording,
            "lowAttendanceCohorts": low_attendance_cohorts,
        },
        "compliance": {
            "pendingReviewCourses": pending_review_courses,
            "approvedNotPublishedCourses": approved_not_published,
            "publishBlockedCourses": publish_blocked,
            "auditEvents30d": audit_events_last_30d,
            "evidenceCoveragePercent": evidence_coverage_percent,
        },
        "atRiskLearners": sorted(
            risk_rows,
            key=lambda item: (
                item["completionStatus"] != "ready_for_attestation",
                item["progressPercent"],
                item["attendancePercent"],
            ),
        )[:risk_limit],
    }
