from __future__ import annotations

from collections import defaultdict
from typing import Any

from django.db.models import Count, Q
from django.utils import timezone

from apps.online.models import OnlineAttendance, OnlineCohort, OnlineCourse, OnlineEnrollment, OnlineSession
from apps.online.services.access import (
    online_access_policy_audience_ids_for_instance,
    online_access_policy_audiences_payload_for_instance,
)
from apps.online.services.course_structure import (
    build_course_lessons_payload,
    build_course_modules_payload,
    summarize_course_structure,
)
from apps.online.services.governance import build_course_governance_payload

ONLINE_DASHBOARD_ENROLLMENT_STATUSES = (
    OnlineEnrollment.STATUS_TRIAL,
    OnlineEnrollment.STATUS_ACTIVE,
    OnlineEnrollment.STATUS_COMPLETED,
)
ONLINE_CAPACITY_ENROLLMENT_STATUSES = (
    OnlineEnrollment.STATUS_TRIAL,
    OnlineEnrollment.STATUS_ACTIVE,
    OnlineEnrollment.STATUS_SUSPENDED,
)


def cohort_occupied_slots(cohort: OnlineCohort) -> int:
    return cohort.enrollments.filter(status__in=ONLINE_CAPACITY_ENROLLMENT_STATUSES).count()


def cohort_seats_left(cohort: OnlineCohort) -> int:
    return max(0, cohort.capacity - cohort_occupied_slots(cohort))


def compute_cohort_attendance_percent(cohort: OnlineCohort) -> float:
    enrollments_count = cohort.enrollments.filter(status__in=ONLINE_DASHBOARD_ENROLLMENT_STATUSES).count()
    sessions_count = cohort.sessions.count()
    if enrollments_count == 0 or sessions_count == 0:
        return 0.0

    expected_rows = enrollments_count * sessions_count
    present_rows = OnlineAttendance.objects.filter(
        session__cohort=cohort,
        enrollment__status__in=ONLINE_DASHBOARD_ENROLLMENT_STATUSES,
        status=OnlineAttendance.STATUS_PRESENT,
    ).count()
    return round((present_rows / expected_rows) * 100, 2)


def nearest_session_for_cohort(cohort: OnlineCohort):
    return cohort.sessions.filter(starts_at__gte=timezone.now()).order_by("starts_at").first()


def nearest_session_for_course(course: OnlineCourse):
    return OnlineSession.objects.filter(cohort__course=course, starts_at__gte=timezone.now()).order_by("starts_at").first()


def format_teacher_name(cohort: OnlineCohort) -> str:
    if not cohort.teacher_id:
        return "Not assigned"
    return f"{cohort.teacher.Vorname} {cohort.teacher.Nachname}".strip()


def course_teacher_names(course: OnlineCourse) -> list[str]:
    teachers = (
        course.cohorts.exclude(teacher=None)
        .values_list("teacher__Vorname", "teacher__Nachname")
        .distinct()
    )
    return [f"{first_name} {last_name}".strip() for first_name, last_name in teachers]


def compute_course_attendance_percent(course: OnlineCourse) -> float:
    cohort_rows = (
        course.cohorts.annotate(
            enrollments_count=Count(
                "enrollments",
                filter=Q(enrollments__status__in=ONLINE_DASHBOARD_ENROLLMENT_STATUSES),
                distinct=True,
            ),
            sessions_count=Count("sessions", distinct=True),
        ).values_list("enrollments_count", "sessions_count")
    )
    expected_rows = sum(enrollments_count * sessions_count for enrollments_count, sessions_count in cohort_rows)
    if expected_rows == 0:
        return 0.0

    present_rows = OnlineAttendance.objects.filter(
        session__cohort__course=course,
        enrollment__status__in=ONLINE_DASHBOARD_ENROLLMENT_STATUSES,
        status=OnlineAttendance.STATUS_PRESENT,
    ).count()
    return round((present_rows / expected_rows) * 100, 2)


def cohort_card_payload(cohort: OnlineCohort) -> dict[str, Any]:
    nearest = nearest_session_for_cohort(cohort)
    students_count = cohort.enrollments.filter(status__in=ONLINE_DASHBOARD_ENROLLMENT_STATUSES).count()
    return {
        "id": cohort.id,
        "courseId": cohort.course_id,
        "teacherId": cohort.teacher_id,
        "groupCode": cohort.group_code,
        "groupName": cohort.name,
        "capacity": cohort.capacity,
        "timezone": cohort.timezone,
        "startDate": cohort.start_date,
        "endDate": cohort.end_date,
        "courseSlug": cohort.course.slug,
        "courseTitleDe": cohort.course.title_de,
        "courseTitleEn": cohort.course.title_en,
        "teacherName": format_teacher_name(cohort),
        "studentsCount": students_count,
        "attendancePercent": compute_cohort_attendance_percent(cohort),
        "nearestSessionAt": nearest.starts_at if nearest else None,
        "status": cohort.status,
        "isPublic": cohort.is_public,
        "sessionsCount": cohort.sessions.count(),
    }


def course_card_payload(course: OnlineCourse) -> dict[str, Any]:
    cohorts = course.cohorts.all()
    nearest = nearest_session_for_course(course)
    cohorts_total = cohorts.count()
    public_cohorts_total = cohorts.filter(is_public=True).count()
    sessions_total = OnlineSession.objects.filter(cohort__course=course).count()
    completed_sessions = OnlineSession.objects.filter(cohort__course=course, is_completed=True).count()
    live_sessions = OnlineSession.objects.filter(cohort__course=course, status=OnlineSession.STATUS_LIVE).count()
    canceled_sessions = OnlineSession.objects.filter(cohort__course=course, status=OnlineSession.STATUS_CANCELED).count()
    students_count = course.enrollments.filter(status__in=ONLINE_DASHBOARD_ENROLLMENT_STATUSES).count()
    teacher_names = course_teacher_names(course)
    structure_summary = summarize_course_structure(course)
    return {
        "id": course.id,
        "slug": course.slug,
        "titleDe": course.title_de,
        "titleEn": course.title_en,
        "providerType": course.provider_type,
        "courseOrigin": course.course_origin,
        "courseType": course.course_type,
        "deliveryModel": course.delivery_model,
        "difficultyLevel": course.difficulty_level,
        "confidentialityLevel": course.confidentiality_level,
        "knowledgeDomain": course.knowledge_domain,
        "targetAudience": course.target_audience,
        "estimatedDurationMinutes": course.estimated_duration_minutes,
        "averageRating": str(course.average_rating),
        "ratingsCount": course.ratings_count,
        "isMandatory": course.is_mandatory,
        "isRecommended": course.is_recommended,
        "providerCourseId": course.provider_course_id,
        "externalUrl": course.external_url,
        "tags": course.tags or [],
        "skills": course.skills or [],
        "audienceIds": online_access_policy_audience_ids_for_instance(course),
        "audiences": online_access_policy_audiences_payload_for_instance(course),
        "lessonsCount": course.lessons_count,
        "isPublished": course.is_published,
        "lifecycleStatus": course.lifecycle_status,
        "trialAvailable": course.trial_available,
        "priceAmount": course.price_amount,
        "currency": course.currency,
        "cohortsCount": cohorts_total,
        "publicCohortsCount": public_cohorts_total,
        "studentsCount": students_count,
        "attendancePercent": compute_course_attendance_percent(course),
        "nearestSessionAt": nearest.starts_at if nearest else None,
        "teachers": teacher_names,
        "governance": build_course_governance_payload(course),
        "structureSummary": structure_summary,
        "sessionsSummary": {
            "total": sessions_total,
            "completed": completed_sessions,
            "planned": max(0, sessions_total - completed_sessions),
            "live": live_sessions,
            "canceled": canceled_sessions,
        },
    }


def course_detail_payload(course: OnlineCourse) -> dict[str, Any]:
    cohorts = list(
        OnlineCohort.objects.filter(course=course)
        .select_related("teacher")
        .order_by("start_date", "id")
    )
    sessions = list(
        OnlineSession.objects.filter(cohort__course=course)
        .select_related("cohort")
        .order_by("starts_at", "id")
    )
    enrollments = list(
        OnlineEnrollment.objects.filter(
            course=course,
            status__in=ONLINE_DASHBOARD_ENROLLMENT_STATUSES,
        )
        .select_related("profile__user", "cohort")
        .order_by("profile__last_name", "profile__first_name")
    )
    attendance_rows = OnlineAttendance.objects.filter(
        enrollment__in=enrollments,
        session__in=sessions,
    )

    session_attendance_counter: dict[int, dict[str, int]] = defaultdict(
        lambda: {"present": 0, "absent": 0, "excused": 0, "unknown": 0}
    )
    for row in attendance_rows:
        if row.status in session_attendance_counter[row.session_id]:
            session_attendance_counter[row.session_id][row.status] += 1
        else:
            session_attendance_counter[row.session_id]["unknown"] += 1

    sessions_payload = []
    students_total = len(enrollments)
    for session in sessions:
        summary = session_attendance_counter.get(
            session.id, {"present": 0, "absent": 0, "excused": 0, "unknown": 0}
        )
        counted = summary["present"] + summary["absent"] + summary["excused"] + summary["unknown"]
        if counted < students_total:
            summary = {**summary, "unknown": summary["unknown"] + (students_total - counted)}
        sessions_payload.append(
            {
                "id": session.id,
                "title": session.title,
                "groupCode": session.cohort.group_code,
                "groupName": session.cohort.name,
                "startsAt": session.starts_at,
                "endsAt": session.ends_at,
                "status": session.status,
                "isCompleted": session.is_completed,
                "attendanceSummary": summary,
            }
        )

    cohorts_summary = {
        "total": len(cohorts),
        "public": sum(1 for cohort in cohorts if cohort.is_public),
        "running": sum(1 for cohort in cohorts if cohort.status == OnlineCohort.STATUS_RUNNING),
        "open": sum(1 for cohort in cohorts if cohort.status == OnlineCohort.STATUS_OPEN),
        "finished": sum(1 for cohort in cohorts if cohort.status == OnlineCohort.STATUS_FINISHED),
        "draft": sum(1 for cohort in cohorts if cohort.status == OnlineCohort.STATUS_DRAFT),
    }
    nearest_session = nearest_session_for_course(course)
    return {
        **course_card_payload(course),
        "descriptionDe": course.description_de,
        "descriptionEn": course.description_en,
        "metadataJson": course.metadata_json or {},
        "customFields": course.custom_fields or {},
        "cohortsSummary": cohorts_summary,
        "attendancePercent": compute_course_attendance_percent(course),
        "nearestSessionAt": nearest_session.starts_at if nearest_session else None,
        "teachers": course_teacher_names(course),
        "cohorts": [cohort_card_payload(item) for item in cohorts],
        "sessions": sessions_payload,
        "modules": build_course_modules_payload(course),
        "lessons": build_course_lessons_payload(course),
    }
