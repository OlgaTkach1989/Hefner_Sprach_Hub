from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal, InvalidOperation
import base64
import hashlib
from hmac import compare_digest
import io
import json
import mimetypes
from pathlib import Path
import requests
import secrets
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import uuid4
import wave

from django.conf import settings
from django.core import signing
from django.core.signing import BadSignature, SignatureExpired
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password
from django.db import IntegrityError, transaction
from django.db.models import Count, Prefetch, Q
from django.http import FileResponse, Http404, HttpResponse, HttpResponseRedirect
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.http import content_disposition_header
from django.utils.text import slugify
import jwt
from jwt import algorithms
from rest_framework import serializers, status
from rest_framework.authentication import CSRFCheck
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from apps.employees.models import Lehrer
from apps.online.models import (
    OnlineAttendance,
    OnlineCohort,
    OnlineCompletionEvidence,
    OnlineCourse,
    OnlineCourseContentLibraryItem,
    OnlineCourseLesson,
    OnlineCourseLessonSectionItem,
    OnlineEnrollmentAttestation,
    OnlineIdentityLink,
    OnlineIdentityProvider,
    OnlineInstructorProfile,
    OnlineCourseModule,
    OnlineCourseMaterial,
    OnlineCourseTemplate,
    OnlineEnrollment,
    OnlineFeedbackMessage,
    OnlineScopeAssignment,
    OnlineLessonProgress,
    OnlineMagicLinkToken,
    OnlineOrder,
    OnlineSession,
    OnlineSessionBooking,
    OnlineStudentProfile,
    OnlineSupportMessage,
    OnlineWorkspace,
    OnlineWorkspaceContentItem,
)
from apps.online.permissions import IsOnlineAdmin, IsOnlineStaff, IsOnlineStudent, IsOnlineTeacher
from apps.online.serializers import (
    CheckoutStartSerializer,
    GoogleCheckoutSerializer,
    GoogleLoginSerializer,
    MagicLinkRequestSerializer,
    MockCheckoutSerializer,
    OnlineAdminSessionStatusUpdateSerializer,
    OnlineAdminSessionListQuerySerializer,
    OnlineAdminSessionBulkActionSerializer,
    OnlineAdminCohortCuratorAssignmentSerializer,
    OnlineAdminCuratorCreateSerializer,
    OnlineAdminCuratorOnboardingSerializer,
    OnlineAdminCuratorUpdateSerializer,
    OnlineAdminWorkspaceContentItemSerializer,
    OnlineAdminWorkspaceContentItemUpsertSerializer,
    OnlineAdminWorkspaceSerializer,
    OnlineAdminWorkspaceUpsertSerializer,
    OnlineAdminUserStatusSerializer,
    OnlineAdminUserTemporaryPasswordSerializer,
    OnlineCourseMaterialSerializer,
    OnlineFeedbackCreateSerializer,
    OnlineLoginSerializer,
    OnlineStaffLoginSerializer,
    OnlineStudentProfileUpdateSerializer,
    OnlineSessionSerializer,
    OnlineStudentProfileSerializer,
    OnlineSupportMessageCreateSerializer,
    OnlineSupportMessageSerializer,
    OnlineTeacherFeedbackCreateSerializer,
    OnlineTeacherProfileSerializer,
    OnlineTeacherProfileUpdateSerializer,
    PublicCourseDetailSerializer,
    PublicCourseListSerializer,
    PublicWorkspaceCardSerializer,
    PublicWorkspaceDetailSerializer,
    TrialSignupSerializer,
    resolve_workspace_join_target,
)
from apps.online.serializers_course_builder import (
    OnlineAdminCourseBuilderDetailSerializer,
    OnlineAdminCourseBuilderDeliverySerializer,
    OnlineAdminCourseBuilderImportSerializer,
    OnlineAdminCourseBuilderSessionSeedSerializer,
    OnlineAdminCourseBuilderUpsertSerializer,
    OnlineAdminCourseContentLibraryItemSerializer,
    OnlineAdminCourseContentLibraryItemUpsertSerializer,
    OnlineAdminCourseTemplateSerializer,
    OnlineAdminNotebookOptionSerializer,
)
from apps.online.services.email_service import send_course_access_email, send_feedback_notification, send_magic_link_email
from apps.online.services.attendance_service import (
    mark_student_join_for_session,
    sync_session_attendance_and_stamp,
)
from apps.online.services.access import (
    online_access_policy_audience_ids_for_instance,
    online_access_policy_audiences_payload_for_instance,
    online_object_is_accessible_to_user,
    sync_online_access_policies_for_instance,
)
from apps.online.services.course_structure import (
    annotate_lessons_payload_with_sessions,
    annotate_modules_payload_with_sessions,
    build_modules_from_import_payload,
    build_course_builder_payload,
    build_course_lessons_map,
    build_course_modules_payload,
    build_course_modules_map,
    build_course_material_projection,
    build_course_material_projection_map,
    build_course_structure_summary_map,
    ensure_default_course_templates,
    sync_course_instructor_assignments,
    sync_course_workspace_placements,
    upsert_course_structure,
)
from apps.online.services.completion import (
    annotate_lessons_payload_with_progress,
    annotate_modules_payload_with_progress,
    build_enrollment_completion_summary,
    default_attestation_text,
    issue_completion_evidence_if_eligible,
    lesson_progress_map_for_enrollment,
    lesson_progress_payload,
)
from apps.online.services.enterprise import (
    build_enterprise_reporting_summary,
    scope_assignment_payload,
    scope_assignments_queryset,
    scope_key_for,
)
from apps.online.services.graph_attendance_service import (
    GraphSyncNotConfigured,
    GraphSyncRequestError,
    create_online_meeting_for_session,
)
from apps.online.services.governance import (
    apply_course_lifecycle_status,
    CourseLifecycleValidationError,
    create_course_version_snapshot,
    log_online_audit_event,
)
from apps.online.services.lesson_grader import grade_lesson_code
from apps.online.services.lesson_generator import generate_course_builder_lesson_document
from apps.online.services.video_lesson_generation import (
    VideoLessonGenerationError,
    generate_course_builder_lesson_from_video,
)
from apps.online.services.lesson_progress import (
    lesson_step_ids_from_payload,
    normalize_lesson_progress_snapshot,
    upsert_lesson_progress,
)
from apps.online.services.payment_service import (
    build_checkout_session,
    build_mock_result_redirect_url,
    get_payment_mode,
    process_payment_event,
)
from apps.online.services.stats import (
    ONLINE_CAPACITY_ENROLLMENT_STATUSES,
    ONLINE_DASHBOARD_ENROLLMENT_STATUSES,
    cohort_card_payload,
    course_card_payload,
    course_detail_payload,
    cohort_seats_left,
    compute_course_attendance_percent,
    compute_cohort_attendance_percent,
    format_teacher_name,
    nearest_session_for_cohort,
)
from apps.online.services.session_lifecycle import (
    ALLOWED_SESSION_STATUS_TRANSITIONS,
    SessionLifecycleError,
    apply_session_status_transition,
    ensure_single_live_session,
    is_valid_session_status_transition,
)
from apps.online.services.session_generation import BuilderSessionSeedInput, SessionGenerationError, create_builder_sessions_for_cohort
from apps.training.models import TrainingAudience, TrainingContentItem, TrainingCourseRoleAssignment
from apps.training.serializers import TrainingContentListSerializer
from apps.training.services.access import base_content_queryset, content_item_is_visible_to_user, visible_content_items_for_user
from apps.training.services.ai_assistant import training_ai_enabled
from apps.training.services.ai_provider import TrainingAiContextChunk, TrainingAiProviderError, get_training_ai_provider

User = get_user_model()


class OnlineStudentLessonAiAskSerializer(serializers.Serializer):
    stepId = serializers.CharField(required=False, allow_blank=True, default="")
    promptType = serializers.CharField(required=False, allow_blank=True, default="ask", max_length=120)
    code = serializers.CharField(required=False, allow_blank=True, default="", max_length=20000)
    question = serializers.CharField(max_length=5000)


class OnlineStudentLessonGraderCheckSerializer(serializers.Serializer):
    stepId = serializers.CharField()
    code = serializers.CharField(max_length=20000)


class OnlineStudentLessonProgressSerializer(serializers.Serializer):
    activeStepId = serializers.CharField(required=False, allow_blank=True, default="")
    completedStepIds = serializers.ListField(
        child=serializers.CharField(max_length=120),
        required=False,
        allow_empty=True,
        default=list,
    )


class OnlineStudentCourseAttestationSerializer(serializers.Serializer):
    fullName = serializers.CharField(max_length=180)
    agreed = serializers.BooleanField(default=False)

    def validate_fullName(self, value: str) -> str:
        normalized = " ".join(str(value or "").split())
        if not normalized:
            raise serializers.ValidationError("Full name is required.")
        return normalized

    def validate_agreed(self, value: bool) -> bool:
        if value is not True:
            raise serializers.ValidationError("Attestation must be confirmed before submission.")
        return value


class PublicAnnaTtsSerializer(serializers.Serializer):
    text = serializers.CharField(max_length=1800)
    language = serializers.ChoiceField(choices=("de-DE", "ru-RU", "uk-UA"), default="ru-RU")

    def validate_text(self, value: str) -> str:
        normalized = " ".join(str(value or "").split())
        if not normalized:
            raise serializers.ValidationError("Text is required.")
        return normalized


class PublicAnnaLiveSessionSerializer(serializers.Serializer):
    language = serializers.ChoiceField(choices=("de-DE", "ru-RU", "uk-UA"), default="de-DE")
    lessonTitle = serializers.CharField(max_length=180, required=False, allow_blank=True)
    level = serializers.CharField(max_length=16, required=False, allow_blank=True)
    voice = serializers.CharField(max_length=40, required=False, allow_blank=True)

    def validate_level(self, value: str) -> str:
        normalized = str(value or "").strip().upper()
        return normalized if normalized in {"A1", "A2", "B1", "B2", "C1", "C2"} else "A1"

    def validate_voice(self, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            return ""
        allowed = {
            "Achernar",
            "Achird",
            "Aoede",
            "Autonoe",
            "Callirrhoe",
            "Charon",
            "Despina",
            "Erinome",
            "Iapetus",
            "Kore",
            "Leda",
            "Puck",
            "Sulafat",
            "Vindemiatrix",
            "Zephyr",
        }
        if normalized not in allowed:
            raise serializers.ValidationError("Unsupported Gemini Live voice.")
        return normalized


class OnlineAdminScopeAssignmentWriteSerializer(serializers.Serializer):
    userId = serializers.IntegerField()
    role = serializers.ChoiceField(choices=OnlineScopeAssignment.ROLE_CHOICES)
    scopeType = serializers.ChoiceField(choices=OnlineScopeAssignment.SCOPE_CHOICES)
    courseId = serializers.IntegerField(required=False, allow_null=True)
    cohortId = serializers.IntegerField(required=False, allow_null=True)
    note = serializers.CharField(required=False, allow_blank=True, default="", max_length=255)
    isPrimary = serializers.BooleanField(required=False, default=False)
    isActive = serializers.BooleanField(required=False, default=True)

    def validate(self, attrs):
        scope_type = attrs["scopeType"]
        course_id = attrs.get("courseId")
        cohort_id = attrs.get("cohortId")

        attrs["user"] = get_object_or_404(User, id=attrs["userId"])
        attrs["course"] = None
        attrs["cohort"] = None

        if scope_type == OnlineScopeAssignment.SCOPE_ACADEMY:
            attrs["scopeKey"] = scope_key_for(scope_type=scope_type)
            return attrs

        if scope_type == OnlineScopeAssignment.SCOPE_COURSE:
            if not course_id:
                raise serializers.ValidationError({"courseId": "Course is required for a course scope assignment."})
            attrs["course"] = get_object_or_404(OnlineCourse, id=course_id)
            attrs["scopeKey"] = scope_key_for(scope_type=scope_type, course=attrs["course"])
            return attrs

        if scope_type == OnlineScopeAssignment.SCOPE_COHORT:
            if not cohort_id:
                raise serializers.ValidationError({"cohortId": "Cohort is required for a cohort scope assignment."})
            attrs["cohort"] = get_object_or_404(OnlineCohort.objects.select_related("course"), id=cohort_id)
            attrs["scopeKey"] = scope_key_for(scope_type=scope_type, cohort=attrs["cohort"])
            return attrs

        raise serializers.ValidationError({"scopeType": "Unsupported scope type."})


class OnlineAdminCourseBuilderLessonGenerateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=220)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    sourceText = serializers.CharField(max_length=50000)
    language = serializers.ChoiceField(choices=OnlineCourse.LOCALE_CHOICES, required=False, default=OnlineCourse.LOCALE_EN)
    courseTitle = serializers.CharField(required=False, allow_blank=True, default="")
    moduleTitle = serializers.CharField(required=False, allow_blank=True, default="")
    videoUrl = serializers.CharField(required=False, allow_blank=True, default="")
    videoDescription = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_sourceText(self, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise serializers.ValidationError("Source text is required.")
        return normalized


class OnlineAdminCourseBuilderLessonGenerateFromVideoSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=220)
    description = serializers.CharField(required=False, allow_blank=True, default="")
    videoFile = serializers.FileField()
    language = serializers.ChoiceField(choices=OnlineCourse.LOCALE_CHOICES, required=False, default=OnlineCourse.LOCALE_EN)
    courseTitle = serializers.CharField(required=False, allow_blank=True, default="")
    moduleTitle = serializers.CharField(required=False, allow_blank=True, default="")
    videoUrl = serializers.CharField(required=False, allow_blank=True, default="")
    videoDescription = serializers.CharField(required=False, allow_blank=True, default="")

    def validate_videoFile(self, value):
        file_name = str(getattr(value, "name", "") or "").lower()
        content_type = str(getattr(value, "content_type", "") or "").lower()
        allowed_extensions = (".mp4", ".mov", ".m4v", ".webm", ".mp3", ".m4a", ".wav")
        if not content_type.startswith(("video/", "audio/")) and not file_name.endswith(allowed_extensions):
            raise serializers.ValidationError("Upload a supported video or audio file.")
        max_bytes = int(getattr(settings, "TRAINING_AI_VIDEO_UPLOAD_MAX_BYTES", 250 * 1024 * 1024) or 250 * 1024 * 1024)
        if getattr(value, "size", 0) and value.size > max_bytes:
            raise serializers.ValidationError("Uploaded video is too large.")
        return value


class PublicCourseFinderAskSerializer(serializers.Serializer):
    query = serializers.CharField(max_length=800)

    def validate_query(self, value: str) -> str:
        normalized = " ".join(str(value or "").split())
        if not normalized:
            raise serializers.ValidationError("Search query is required.")
        return normalized


def _normalize_locale(raw_locale: str | None) -> str:
    return raw_locale if raw_locale in {"de", "en"} else "de"


def _english_first_text(*values: str | None) -> str:
    for value in values:
        normalized = str(value or "").strip()
        if normalized:
            return normalized
    return ""


def _public_catalog_resource_candidates() -> list[dict[str, Any]]:
    return [
        {
            "kind": "library",
            "title": "Learning Library",
            "description": "Shared entry point for updates, session recordings, and learning materials.",
            "path": "/spaces/academy-resources",
            "actionLabel": "Open library",
            "searchText": "learning library shared resources courses updates news recordings materials",
        },
        {
            "kind": "library",
            "title": "Session Recordings",
            "description": "Browse shared recordings and replay teaching sessions from the learning library.",
            "path": "/spaces/academy-resources?section=recordings",
            "actionLabel": "Open recordings",
            "searchText": "session recordings video recordings replay watch recorded sessions",
        },
        {
            "kind": "library",
            "title": "Learning Materials",
            "description": "Open documents, articles, and reference materials collected in the learning library.",
            "path": "/spaces/academy-resources?section=materials",
            "actionLabel": "Open materials",
            "searchText": "learning materials documents articles references study guides resources",
        },
        {
            "kind": "library",
            "title": "Updates",
            "description": "See platform updates, learning announcements, and shared notices.",
            "path": "/spaces/academy-resources?section=news",
            "actionLabel": "Open updates",
            "searchText": "updates announcements news release notes platform changes",
        },
    ]


def _build_public_catalog_candidates() -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for course in OnlineCourse.objects.filter(is_published=True).order_by("id"):
        title = _english_first_text(course.title_en, course.title_de, course.slug)
        short_description = _english_first_text(
            course.short_description_en,
            course.short_description_de,
            course.description_en,
            course.description_de,
        )
        description = _english_first_text(course.description_en, course.description_de, short_description)
        candidates.append(
            {
                "kind": "course",
                "title": title,
                "description": short_description,
                "path": f"/course/{course.slug}",
                "actionLabel": "Open course",
                "searchText": " ".join(
                    part
                    for part in [
                        title,
                        short_description,
                        description,
                        course.slug,
                        course.geo_city,
                        course.geo_country,
                        str(course.lessons_count),
                    ]
                    if part
                ),
            }
        )

    for workspace in _workspace_public_queryset().filter(show_on_homepage=True):
        title = _english_first_text(workspace.title, workspace.slug)
        subtitle = _english_first_text(workspace.subtitle, workspace.summary)
        summary = _english_first_text(workspace.summary, workspace.subtitle)
        candidates.append(
            {
                "kind": "workspace",
                "title": title,
                "description": subtitle or summary,
                "path": f"/spaces/{workspace.slug}",
                "actionLabel": "Open area",
                "searchText": " ".join(
                    part
                    for part in [
                        title,
                        subtitle,
                        summary,
                        workspace.slug,
                        workspace.kind,
                        workspace.icon_key,
                    ]
                    if part
                ),
            }
        )

    candidates.extend(_public_catalog_resource_candidates())
    return candidates


def _score_public_catalog_candidate(candidate: dict[str, Any], query: str) -> int:
    normalized_query = str(query or "").strip().lower()
    if not normalized_query:
        return 0

    title = str(candidate.get("title") or "").strip().lower()
    description = str(candidate.get("description") or "").strip().lower()
    search_text = str(candidate.get("searchText") or "").strip().lower()
    terms = [term for term in normalized_query.replace("-", " ").split() if term]

    score = 0
    if normalized_query == title:
        score += 150
    if title.startswith(normalized_query):
        score += 80
    if normalized_query in title:
        score += 60
    if normalized_query in description:
        score += 30
    if normalized_query in search_text:
        score += 40

    for term in terms:
        if term in title:
            score += 18
        if term in description:
            score += 10
        if term in search_text:
            score += 6

    kind = str(candidate.get("kind") or "")
    if kind == "course":
        score += 5
    if kind == "library" and any(term in {"recording", "recordings", "materials", "library", "updates"} for term in terms):
        score += 12
    return score


def _search_public_catalog_candidates(query: str, *, limit: int = 6) -> list[dict[str, Any]]:
    ranked = []
    for candidate in _build_public_catalog_candidates():
        ranked.append((candidate, _score_public_catalog_candidate(candidate, query)))

    ranked.sort(key=lambda item: item[1], reverse=True)
    positive_matches = [candidate for candidate, score in ranked if score > 0]
    if positive_matches:
        return positive_matches[:limit]

    fallback = [candidate for candidate, _score in ranked]
    return fallback[:limit]


def _public_catalog_context_chunks(query: str) -> list[TrainingAiContextChunk]:
    chunks: list[TrainingAiContextChunk] = []
    for index, candidate in enumerate(_search_public_catalog_candidates(query, limit=7), start=1):
        title = str(candidate.get("title") or "").strip()
        description = str(candidate.get("description") or "").strip()
        kind = str(candidate.get("kind") or "catalog").strip()
        path = str(candidate.get("path") or "").strip()
        text = "\n".join(
            part
            for part in [
                f"Type: {kind}",
                f"Title: {title}",
                f"Description: {description}",
                f"Path: {path}",
            ]
            if part
        )
        if not text:
            continue
        chunks.append(
            TrainingAiContextChunk(
                content_slug=f"public-catalog-{index}",
                content_name="Public learning catalog",
                section_title=kind.title(),
                citation_label=title or f"Catalog item {index}",
                text=text,
                snippet=description[:200],
                source_url=path or None,
            )
        )
    return chunks


def _make_unique_username(email: str) -> str:
    base = email.split("@")[0].strip().lower()[:25] or "online_student"
    candidate = base
    suffix = 1
    while User.objects.filter(username=candidate).exists():
        suffix += 1
        candidate = f"{base}_{suffix}"
    return candidate


def _build_auth_payload(user: User) -> dict[str, str]:
    refresh = RefreshToken.for_user(user)
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    }


AUTH_SCOPE_STUDENT = "student"
AUTH_SCOPE_STAFF = "staff"
SSO_ROLE_STUDENT = "student"
SSO_ROLE_TEACHER = "teacher"
SSO_ROLE_ADMIN = "admin"
SSO_STATE_SALT = "online-sso-state-v1"
MICROSOFT_JWKS_CACHE: dict[str, tuple[dict[str, Any], datetime]] = {}


class OnlineAuthThrottle(AnonRateThrottle):
    scope = "online_auth"


class OnlineMagicLinkThrottle(AnonRateThrottle):
    scope = "online_magic_link"


def _jwt_lifetime_seconds(key: str) -> int:
    value = settings.SIMPLE_JWT.get(key)
    if isinstance(value, timedelta):
        return max(int(value.total_seconds()), 0)
    return 0


def _auth_cookie_name(scope: str, token_kind: str) -> str:
    if scope == AUTH_SCOPE_STAFF:
        return getattr(
            settings,
            "ONLINE_STAFF_ACCESS_COOKIE_NAME" if token_kind == "access" else "ONLINE_STAFF_REFRESH_COOKIE_NAME",
            "",
        )
    return getattr(
        settings,
        "ONLINE_STUDENT_ACCESS_COOKIE_NAME" if token_kind == "access" else "ONLINE_STUDENT_REFRESH_COOKIE_NAME",
        "",
    )


def _auth_cookie_common_kwargs() -> dict[str, Any]:
    domain = str(getattr(settings, "ONLINE_AUTH_COOKIE_DOMAIN", "") or "").strip()
    return {
        "secure": bool(getattr(settings, "ONLINE_AUTH_COOKIE_SECURE", not settings.DEBUG)),
        "httponly": True,
        "samesite": str(getattr(settings, "ONLINE_AUTH_COOKIE_SAMESITE", "Lax") or "Lax"),
        "path": str(getattr(settings, "ONLINE_AUTH_COOKIE_PATH", "/") or "/"),
        "domain": domain or None,
    }


def _set_no_store_headers(response: HttpResponse) -> HttpResponse:
    response["Cache-Control"] = "no-store"
    response["Pragma"] = "no-cache"
    return response


def _authenticated_file_response(file_field, *, as_attachment: bool = False) -> FileResponse:
    if not file_field or not getattr(file_field, "name", ""):
        raise Http404("File not found.")

    try:
        file_field.open("rb")
    except (FileNotFoundError, OSError, ValueError) as exc:
        raise Http404("File not found.") from exc

    filename = Path(str(file_field.name)).name or "download"
    content_type, _ = mimetypes.guess_type(filename)
    response = FileResponse(
        file_field,
        as_attachment=as_attachment,
        filename=filename,
        content_type=content_type or "application/octet-stream",
    )
    response["Content-Disposition"] = content_disposition_header(as_attachment, filename)
    response["X-Content-Type-Options"] = "nosniff"
    return _set_no_store_headers(response)


def _is_online_staff_user(user) -> bool:
    return bool(
        user
        and getattr(user, "is_authenticated", False)
        and (
            getattr(user, "is_superuser", False)
            or getattr(user, "is_admin", False)
            or hasattr(user, "lehrer_user")
        )
    )


def _user_can_download_section_item_file(*, user, item: OnlineCourseLessonSectionItem) -> bool:
    if not online_object_is_accessible_to_user(item, user):
        return False
    if item.linked_training_content_id and not content_item_is_visible_to_user(item.linked_training_content, user):
        return False
    if _is_online_staff_user(user):
        return True

    profile = getattr(user, "online_profile", None)
    if profile is None:
        return False

    course_id = item.section.lesson.course_id
    return OnlineEnrollment.objects.filter(
        profile=profile,
        course_id=course_id,
        status__in=_portal_enrollment_statuses(),
    ).exists()


def _apply_auth_cookies(
    *,
    response: HttpResponse,
    request,
    auth_payload: dict[str, str],
    scope: str,
) -> HttpResponse:
    get_token(request)
    cookie_kwargs = _auth_cookie_common_kwargs()
    access_name = str(_auth_cookie_name(scope, "access") or "").strip()
    refresh_name = str(_auth_cookie_name(scope, "refresh") or "").strip()

    if access_name and auth_payload.get("access"):
        response.set_cookie(
            access_name,
            auth_payload["access"],
            max_age=_jwt_lifetime_seconds("ACCESS_TOKEN_LIFETIME"),
            **cookie_kwargs,
        )

    if refresh_name and auth_payload.get("refresh"):
        response.set_cookie(
            refresh_name,
            auth_payload["refresh"],
            max_age=_jwt_lifetime_seconds("REFRESH_TOKEN_LIFETIME"),
            **cookie_kwargs,
        )

    return _set_no_store_headers(response)


def _clear_auth_cookies(response: HttpResponse, *, scope: str) -> HttpResponse:
    cookie_kwargs = _auth_cookie_common_kwargs()
    for token_kind in ("access", "refresh"):
        cookie_name = str(_auth_cookie_name(scope, token_kind) or "").strip()
        if cookie_name:
            response.delete_cookie(cookie_name, path=cookie_kwargs["path"], domain=cookie_kwargs["domain"])
    return _set_no_store_headers(response)


def _response_with_auth_payload(
    *,
    request,
    payload: dict[str, Any],
    status_code: int,
    scope: str,
    auth_payload: dict[str, str] | None = None,
) -> Response:
    response = Response(payload, status=status_code)
    if isinstance(auth_payload, dict):
        _apply_auth_cookies(response=response, request=request, auth_payload=auth_payload, scope=scope)
    else:
        _set_no_store_headers(response)
    return response


def _json_auth_response(
    *,
    request,
    user: User,
    payload: dict[str, Any],
    status_code: int,
    scope: str,
) -> Response:
    auth_payload = _build_auth_payload(user)
    return _response_with_auth_payload(
        request=request,
        payload=payload,
        status_code=status_code,
        scope=scope,
        auth_payload=auth_payload,
    )


def _redirect_with_auth_cookies(
    *,
    request,
    redirect_url: str,
    user: User,
    scope: str,
) -> HttpResponseRedirect:
    response = HttpResponseRedirect(redirect_url)
    return _apply_auth_cookies(
        response=response,
        request=request,
        auth_payload=_build_auth_payload(user),
        scope=scope,
    )


def _csrf_failure_reason(request) -> str | None:
    check = CSRFCheck(lambda _: None)
    check.process_request(request)
    return check.process_view(request, None, (), {})


def _enforce_request_csrf(request) -> None:
    reason = _csrf_failure_reason(request)
    if reason:
        raise serializers.ValidationError({"detail": f"CSRF Failed: {reason}"})


def _sanitize_relative_path(value: str, default: str) -> str:
    candidate = str(value or "").strip()
    if not candidate or not candidate.startswith("/") or candidate.startswith("//"):
        return default
    return candidate


def _build_frontend_redirect_path(path: str, *, error: str = "", message: str = "") -> str:
    normalized_path = _sanitize_relative_path(path, "/")
    query_pairs = []
    if error:
        query_pairs.append(("error", error))
    if message:
        query_pairs.append(("message", message))
    if not query_pairs:
        return normalized_path
    parts = list(urlsplit(normalized_path))
    existing_pairs = parse_qsl(parts[3], keep_blank_values=True)
    parts[3] = urlencode(existing_pairs + query_pairs)
    return urlunsplit(parts)


def _microsoft_sso_is_configured() -> bool:
    return bool(
        str(getattr(settings, "ONLINE_MICROSOFT_CLIENT_ID", "")).strip()
        and str(getattr(settings, "ONLINE_MICROSOFT_CLIENT_SECRET", "")).strip()
        and str(getattr(settings, "ONLINE_MICROSOFT_TENANT_ID", "")).strip()
    )


def _microsoft_tenant_id() -> str:
    return str(getattr(settings, "ONLINE_MICROSOFT_TENANT_ID", "common")).strip() or "common"


def _microsoft_client_id() -> str:
    return str(getattr(settings, "ONLINE_MICROSOFT_CLIENT_ID", "")).strip()


def _microsoft_client_secret() -> str:
    return str(getattr(settings, "ONLINE_MICROSOFT_CLIENT_SECRET", "")).strip()


def _microsoft_scopes() -> list[str]:
    scopes = list(getattr(settings, "ONLINE_MICROSOFT_SCOPES", []) or [])
    normalized = [str(scope).strip() for scope in scopes if str(scope).strip()]
    return normalized or ["openid", "profile", "email"]


def _microsoft_authorization_url() -> str:
    return f"https://login.microsoftonline.com/{_microsoft_tenant_id()}/oauth2/v2.0/authorize"


def _microsoft_token_url() -> str:
    return f"https://login.microsoftonline.com/{_microsoft_tenant_id()}/oauth2/v2.0/token"


def _microsoft_callback_url(request, *, scope: str) -> str:
    return request.build_absolute_uri(reverse("online-microsoft-callback"))


def _microsoft_sso_state_max_age() -> int:
    return max(int(getattr(settings, "ONLINE_SSO_STATE_TTL_SECONDS", 600) or 600), 60)


def _build_sso_state(*, scope: str, role: str, next_path: str, login_path: str, nonce: str) -> str:
    return signing.dumps(
        {
            "scope": scope,
            "role": role,
            "next": next_path,
            "login": login_path,
            "nonce": nonce,
        },
        salt=SSO_STATE_SALT,
    )


def _load_sso_state(raw_state: str) -> dict[str, Any]:
    return signing.loads(raw_state, salt=SSO_STATE_SALT, max_age=_microsoft_sso_state_max_age())


def _microsoft_oidc_jwks() -> dict[str, Any]:
    cache_key = _microsoft_tenant_id()
    cached = MICROSOFT_JWKS_CACHE.get(cache_key)
    now = timezone.now()
    if cached and cached[1] > now:
        return cached[0]

    response = requests.get(
        f"https://login.microsoftonline.com/{cache_key}/discovery/v2.0/keys",
        timeout=10,
    )
    response.raise_for_status()
    payload = response.json()
    MICROSOFT_JWKS_CACHE[cache_key] = (payload, now + timedelta(hours=6))
    return payload


def _verify_microsoft_id_token(id_token: str, *, nonce: str) -> tuple[dict[str, Any] | None, str | None]:
    raw_token = str(id_token or "").strip()
    if not raw_token:
        return None, "Microsoft id_token is missing."
    if not _microsoft_sso_is_configured():
        return None, "Microsoft SSO is not configured."

    try:
        header = jwt.get_unverified_header(raw_token)
        kid = str(header.get("kid") or "").strip()
        if not kid:
            return None, "Microsoft token key id is missing."

        jwks_payload = _microsoft_oidc_jwks()
        jwk_payload = next(
            (item for item in list(jwks_payload.get("keys") or []) if str(item.get("kid") or "").strip() == kid),
            None,
        )
        if not jwk_payload:
            return None, "Microsoft signing key is unavailable."

        public_key = algorithms.RSAAlgorithm.from_jwk(json.dumps(jwk_payload))
        decoded = jwt.decode(
            raw_token,
            key=public_key,
            algorithms=["RS256"],
            audience=_microsoft_client_id(),
            options={"verify_signature": True, "verify_aud": True, "verify_exp": True},
        )
    except requests.RequestException:
        return None, "Microsoft identity service is unavailable."
    except (jwt.PyJWTError, AttributeError, ValueError, TypeError):
        return None, "Microsoft token is invalid."

    if str(decoded.get("nonce") or "").strip() != str(nonce or "").strip():
        return None, "Microsoft token nonce mismatch."

    expected_tenant = _microsoft_tenant_id()
    actual_tenant = str(decoded.get("tid") or "").strip()
    if expected_tenant not in {"common", "organizations", "consumers"} and actual_tenant != expected_tenant:
        return None, "Microsoft token tenant mismatch."

    issuer = str(decoded.get("iss") or "").strip().rstrip("/")
    if actual_tenant:
        expected_issuer = f"https://login.microsoftonline.com/{actual_tenant}/v2.0"
        if issuer != expected_issuer:
            return None, "Microsoft token issuer mismatch."

    email = (
        str(decoded.get("preferred_username") or "").strip().lower()
        or str(decoded.get("email") or "").strip().lower()
        or str(decoded.get("upn") or "").strip().lower()
    )
    if not email:
        return None, "Microsoft account email is missing."

    decoded["email"] = email
    return decoded, None


def _microsoft_identity_provider() -> OnlineIdentityProvider | None:
    return (
        OnlineIdentityProvider.objects.filter(provider_type=OnlineIdentityProvider.PROVIDER_MICROSOFT_OIDC)
        .order_by("sort_order", "id")
        .first()
    )


def _microsoft_identity_subject(payload: dict[str, Any]) -> str:
    tenant_id = str(payload.get("tid") or "").strip()
    object_id = str(payload.get("oid") or "").strip()
    if tenant_id and object_id:
        return f"{tenant_id}:{object_id}"
    return str(payload.get("sub") or "").strip()


def _normalized_email_set(values: Any) -> set[str]:
    return {str(value).strip().lower() for value in list(values or []) if str(value).strip()}


def _microsoft_student_email_allowlist() -> set[str]:
    return _normalized_email_set(getattr(settings, "ONLINE_MICROSOFT_STUDENT_EMAILS", []))


def _microsoft_teacher_email_allowlist() -> set[str]:
    return _normalized_email_set(getattr(settings, "ONLINE_MICROSOFT_TEACHER_EMAILS", []))


def _microsoft_admin_email_allowlist() -> set[str]:
    return _normalized_email_set(getattr(settings, "ONLINE_MICROSOFT_ADMIN_EMAILS", []))


def _extract_microsoft_names(payload: dict[str, Any], email: str) -> tuple[str, str, str]:
    first_name = str(payload.get("given_name") or "").strip()
    last_name = str(payload.get("family_name") or "").strip()
    full_name = str(payload.get("name") or "").strip()

    if not first_name and full_name:
        parts = full_name.split()
        first_name = parts[0].strip() if parts else ""
        last_name = " ".join(parts[1:]).strip() if len(parts) > 1 else last_name

    if not first_name:
        first_name = email.split("@")[0].replace(".", " ").replace("_", " ").strip().title() or "Microsoft"
    if not last_name:
        last_name = "User"
    if not full_name:
        full_name = f"{first_name} {last_name}".strip()

    return first_name[:120], last_name[:120], full_name[:180]


def _make_unique_teacher_short_name(*, first_name: str, last_name: str, email: str) -> str:
    source = f"{first_name[:1]}{last_name}".strip() or email.split("@")[0].strip() or "teacher"
    base = slugify(source).replace("-", "").upper()[:16] or "TEACHER"
    candidate = base[:20]
    suffix = 1
    while Lehrer.objects.filter(KurzName__iexact=candidate).exists():
        suffix += 1
        suffix_text = str(suffix)
        candidate = f"{base[: max(1, 20 - len(suffix_text))]}{suffix_text}"
    return candidate


def _ensure_microsoft_student_profile(user: User, payload: dict[str, Any]) -> tuple[User | None, str | None]:
    email = str(payload.get("email") or user.email or "").strip().lower()
    allowed_students = _microsoft_student_email_allowlist()
    if allowed_students and email not in allowed_students:
        return None, "Microsoft student account is not allowed."
    if not bool(getattr(settings, "ONLINE_MICROSOFT_AUTO_PROVISION_STUDENTS", True)):
        if not hasattr(user, "online_profile"):
            return None, "User is not registered for online courses."
        return user, None

    first_name, last_name, _full_name = _extract_microsoft_names(payload, email)
    if not hasattr(user, "online_profile"):
        OnlineStudentProfile.objects.create(
            user=user,
            first_name=first_name,
            last_name=last_name,
            preferred_language=str(getattr(settings, "ONLINE_MICROSOFT_DEFAULT_STUDENT_LANGUAGE", "en") or "en")[:2],
            is_trial_user=False,
            custom_fields={"identityProvider": "microsoft"},
        )
    return user, None


def _ensure_microsoft_teacher_profile(user: User, payload: dict[str, Any]) -> tuple[User | None, str | None]:
    if hasattr(user, "lehrer_user"):
        return user, None

    email = str(payload.get("email") or user.email or "").strip().lower()
    if email not in _microsoft_teacher_email_allowlist():
        return None, "Teacher access must be assigned inside Hefner Sprach Hub."

    first_name, last_name, _full_name = _extract_microsoft_names(payload, email)
    try:
        with transaction.atomic():
            teacher = Lehrer.objects.create(
                user=user,
                Vorname=first_name,
                Nachname=last_name,
                Schule_Email=email,
                Private_Email="",
                Telefonnummer="",
                KurzName=_make_unique_teacher_short_name(first_name=first_name, last_name=last_name, email=email),
            )
            OnlineInstructorProfile.objects.get_or_create(teacher=teacher)
    except IntegrityError:
        return None, "Teacher profile could not be created for this Microsoft account."
    return user, None


def _ensure_microsoft_admin_role(user: User, payload: dict[str, Any]) -> tuple[User | None, str | None]:
    if user.is_admin or user.is_superuser:
        return user, None

    email = str(payload.get("email") or user.email or "").strip().lower()
    if email not in _microsoft_admin_email_allowlist():
        return None, "Admin access must be assigned inside Hefner Sprach Hub."

    user.is_admin = True
    user.is_staff = True
    user.save(update_fields=["is_admin", "is_staff"])
    return user, None


def _ensure_microsoft_user_role(*, user: User, role: str, payload: dict[str, Any]) -> tuple[User | None, str | None]:
    if not user.is_active:
        return None, "User account is inactive."

    first_name, last_name, _full_name = _extract_microsoft_names(payload, user.email)
    update_fields: list[str] = []
    if first_name and not user.first_name:
        user.first_name = first_name
        update_fields.append("first_name")
    if last_name and not user.last_name:
        user.last_name = last_name
        update_fields.append("last_name")
    if update_fields:
        user.save(update_fields=update_fields)

    if role == SSO_ROLE_STUDENT:
        return _ensure_microsoft_student_profile(user, payload)
    if role == SSO_ROLE_TEACHER:
        return _ensure_microsoft_teacher_profile(user, payload)
    if role == SSO_ROLE_ADMIN:
        return _ensure_microsoft_admin_role(user, payload)
    return None, "Microsoft sign-in role is invalid."


def _create_microsoft_user_for_role(*, role: str, payload: dict[str, Any]) -> tuple[User | None, str | None]:
    email = str(payload.get("email") or "").strip().lower()
    if not email:
        return None, "Microsoft account email is missing."

    if role == SSO_ROLE_TEACHER and email not in _microsoft_teacher_email_allowlist():
        return None, "Teacher access must be assigned inside Hefner Sprach Hub."
    if role == SSO_ROLE_ADMIN and email not in _microsoft_admin_email_allowlist():
        return None, "Admin access must be assigned inside Hefner Sprach Hub."
    if role == SSO_ROLE_STUDENT:
        allowed_students = _microsoft_student_email_allowlist()
        if allowed_students and email not in allowed_students:
            return None, "Microsoft student account is not allowed."
        if not bool(getattr(settings, "ONLINE_MICROSOFT_AUTO_PROVISION_STUDENTS", True)):
            return None, "User not found."

    first_name, last_name, _full_name = _extract_microsoft_names(payload, email)
    try:
        with transaction.atomic():
            user = User.objects.create_user(
                email=email,
                username=_make_unique_username(email),
                password=None,
                first_name=first_name,
                last_name=last_name,
                is_active=True,
                is_admin=role == SSO_ROLE_ADMIN,
                is_staff=role == SSO_ROLE_ADMIN,
            )
            user, role_error = _ensure_microsoft_user_role(user=user, role=role, payload=payload)
            if role_error:
                raise ValueError(role_error)
    except ValueError as exc:
        return None, str(exc)
    except IntegrityError:
        return None, "Microsoft account could not be provisioned."
    return user, None


def _microsoft_user_lookup(*, role: str, payload: dict[str, Any]) -> tuple[User | None, str | None]:
    email = str(payload.get("email") or "").strip().lower()
    if not email:
        return None, "Microsoft account email is missing."

    provider = _microsoft_identity_provider()
    subject = _microsoft_identity_subject(payload)
    if provider and subject:
        link = (
            OnlineIdentityLink.objects.select_related("user")
            .filter(provider=provider, subject=subject)
            .first()
        )
        if link:
            return _ensure_microsoft_user_role(user=link.user, role=role, payload=payload)

    user = User.objects.filter(email__iexact=email).first()
    if user:
        return _ensure_microsoft_user_role(user=user, role=role, payload=payload)

    return _create_microsoft_user_for_role(role=role, payload=payload)


def _update_microsoft_identity_link(*, user: User, payload: dict[str, Any]) -> None:
    provider = _microsoft_identity_provider()
    if not provider:
        return

    subject = _microsoft_identity_subject(payload)
    if not subject:
        return

    full_name = str(payload.get("name") or "").strip()
    OnlineIdentityLink.objects.update_or_create(
        provider=provider,
        subject=subject,
        defaults={
            "user": user,
            "email": str(payload.get("email") or "").strip().lower(),
            "full_name": full_name[:180],
            "claims_snapshot": payload,
            "last_authenticated_at": timezone.now(),
        },
    )


def _serialize_profile(profile: OnlineStudentProfile, request) -> dict[str, Any]:
    return OnlineStudentProfileSerializer(profile, context={"request": request}).data


def _serialize_staff_profile(user: User) -> dict[str, Any]:
    is_teacher = hasattr(user, "lehrer_user")
    is_admin = bool(user.is_admin or user.is_superuser)
    full_name = f"{user.first_name} {user.last_name}".strip() or user.email
    teacher = getattr(user, "lehrer_user", None)
    return {
        "email": user.email,
        "firstName": user.first_name,
        "lastName": user.last_name,
        "fullName": full_name,
        "isTeacher": is_teacher,
        "isAdmin": is_admin,
        "isSuperuser": bool(user.is_superuser),
        "teacherId": teacher.id if teacher else None,
    }


def _portal_enrollment_statuses() -> tuple[str, ...]:
    return (
        OnlineEnrollment.STATUS_TRIAL,
        OnlineEnrollment.STATUS_ACTIVE,
        OnlineEnrollment.STATUS_COMPLETED,
    )


LEGACY_STUDENT_LESSON_ALIASES: dict[int, dict[str, str]] = {
    158: {
        "course_slug": "financial-time-series-forecasting-lab",
        "lesson_title": "Bitcoin Case: Forecasting with JupyterLab",
    }
}


def _student_lesson_context_or_404(*, request, lesson_id: int) -> dict[str, Any]:
    requested_lesson_id = int(lesson_id or 0)
    lesson_obj = (
        OnlineCourseLesson.objects.select_related("course", "module")
        .filter(id=requested_lesson_id, is_active=True)
        .first()
    )
    if lesson_obj is None:
        alias = LEGACY_STUDENT_LESSON_ALIASES.get(requested_lesson_id)
        if alias:
            lesson_obj = (
                OnlineCourseLesson.objects.select_related("course", "module")
                .filter(
                    course__slug=str(alias.get("course_slug") or "").strip(),
                    title=str(alias.get("lesson_title") or "").strip(),
                    is_active=True,
                )
                .order_by("-id")
                .first()
            )
    if lesson_obj is None:
        raise Http404("Lesson not found.")

    profile = request.user.online_profile
    enrollment = (
        OnlineEnrollment.objects.filter(
            profile=profile,
            course=lesson_obj.course,
        )
        .select_related("course", "cohort")
        .order_by("-started_at")
        .first()
    )
    if enrollment is None or not online_object_is_accessible_to_user(enrollment.course, request.user):
        raise Http404("Lesson not found.")

    course_modules = build_course_modules_payload(enrollment.course, request=request)
    sessions = list(enrollment.cohort.sessions.all().order_by("starts_at"))
    annotate_modules_payload_with_sessions(
        course_modules,
        sessions,
        group_code=enrollment.cohort.group_code,
        group_name=enrollment.cohort.name,
    )
    lessons_payload = [lesson_payload for module_payload in course_modules for lesson_payload in module_payload.get("lessons", [])]
    progress_map = lesson_progress_map_for_enrollment(
        enrollment,
        lesson_ids=[int(item.get("id")) for item in lessons_payload if item.get("id")],
    )
    annotate_lessons_payload_with_progress(lessons_payload, progress_map=progress_map)
    issue_completion_evidence_if_eligible(enrollment)
    completion_summary = build_enrollment_completion_summary(
        enrollment,
        lessons_payload=lessons_payload,
        progress_map=progress_map,
    )

    for module_payload in course_modules:
        for lesson_payload in module_payload.get("lessons", []):
            if int(lesson_payload.get("id") or 0) == int(lesson_obj.id):
                return {
                    "enrollment": enrollment,
                    "lessonObject": lesson_obj,
                    "modulePayload": module_payload,
                    "lessonPayload": lesson_payload,
                    "completionSummary": completion_summary,
                }

    raise Http404("Lesson not found.")


def _request_ip_address(request) -> str | None:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip() or None
    remote_addr = request.META.get("REMOTE_ADDR", "")
    return remote_addr or None


def _lesson_ai_context_chunks(
    *,
    lesson_payload: dict[str, Any],
    step_id: str = "",
    code: str = "",
) -> list[TrainingAiContextChunk]:
    interactive_lesson = lesson_payload.get("interactiveLesson") or {}
    steps = list(interactive_lesson.get("steps") or [])
    chunks: list[TrainingAiContextChunk] = []

    normalized_code = str(code or "").strip()
    if normalized_code:
        chunks.append(
            TrainingAiContextChunk(
                content_slug=f"online-lesson-{lesson_payload.get('id')}-student-code",
                content_name=str(interactive_lesson.get("lessonTitle") or lesson_payload.get("title") or "Lesson").strip(),
                section_title="Student code",
                citation_label="Student code",
                text=normalized_code,
                snippet=normalized_code[:200],
                source_url=None,
            )
        )

    if not steps:
        return chunks

    active_step = next((step for step in steps if str(step.get("id") or "") == str(step_id or "")), None)
    ordered_steps = [active_step] if active_step is not None else []
    ordered_steps.extend(step for step in steps if active_step is None or step is not active_step)

    for index, step in enumerate(ordered_steps[:5], start=1):
        quiz_payload = step.get("quiz") or {}
        quiz_questions = quiz_payload.get("questions") or []
        if quiz_questions:
            quiz_lines = []
            for question in quiz_questions:
                prompt = str(question.get("prompt") or "").strip()
                if prompt:
                    quiz_lines.append(f"Question: {prompt}")
                for option in question.get("options") or []:
                    if option.get("label"):
                        quiz_lines.append(f"- {option.get('label')}")
        else:
            quiz_lines = [
                f"- {option.get('label')}"
                for option in (quiz_payload.get("options") or [])
                if option.get("label")
            ]

        correct_option = ""
        if quiz_questions:
            correct_parts = []
            for question in quiz_questions:
                label = next(
                    (
                        str(option.get("label") or "").strip()
                        for option in (question.get("options") or [])
                        if option.get("isCorrect")
                    ),
                    "",
                )
                if label:
                    correct_parts.append(f"{question.get('prompt')}: {label}")
            correct_option = "\n".join(part for part in correct_parts if part)
        else:
            correct_option = next(
                (
                    str(option.get("label") or "").strip()
                    for option in (quiz_payload.get("options") or [])
                    if option.get("isCorrect")
                ),
                "",
            )
        resource_url = next(
            (
                str(resource.get("url") or "").strip()
                for resource in (step.get("resourceLinks") or [])
                if str(resource.get("url") or "").strip()
            ),
            "",
        )
        parts = [
            str(step.get("title") or "").strip(),
            str(step.get("description") or "").strip(),
            str(step.get("contentMarkdown") or "").strip(),
        ]
        if quiz_payload.get("prompt"):
            parts.append(f"Quiz prompt: {quiz_payload.get('prompt')}")
        if quiz_lines:
            parts.append("Quiz options:\n" + "\n".join(quiz_lines))
        if correct_option:
            parts.append(f"Correct option: {correct_option}")
        if quiz_payload.get("explanationMarkdown"):
            parts.append(str(quiz_payload.get("explanationMarkdown") or "").strip())
        if step.get("starterCode"):
            parts.append("Starter code:\n" + str(step.get("starterCode") or "").strip())
        if step.get("hint"):
            parts.append("Hint:\n" + str(step.get("hint") or "").strip())
        if step.get("solution"):
            parts.append("Reference solution:\n" + str(step.get("solution") or "").strip())

        text = "\n\n".join(part for part in parts if part)
        if not text:
            continue

        chunks.append(
            TrainingAiContextChunk(
                content_slug=f"online-lesson-{lesson_payload.get('id')}",
                content_name=str(interactive_lesson.get("lessonTitle") or lesson_payload.get("title") or "Lesson").strip(),
                section_title=str(step.get("eyebrow") or "Lesson step").strip(),
                citation_label=str(step.get("title") or f"Step {index}").strip(),
                text=text,
                snippet=str(step.get("description") or step.get("title") or "").strip()[:200],
                source_url=resource_url or None,
            )
        )

    return chunks


def _serialize_checkout_status(order: OnlineOrder, request) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "orderId": order.id,
        "status": order.status,
        "isFinal": order.status in {OnlineOrder.STATUS_PAID, OnlineOrder.STATUS_FAILED, OnlineOrder.STATUS_REFUNDED},
        "checkoutToken": str(order.checkout_token),
        "courseSlug": order.course.slug,
        "groupCode": order.cohort.group_code,
    }

    if order.status == OnlineOrder.STATUS_PAID:
        payload["profile"] = _serialize_profile(order.profile, request)

    return payload


def _serialize_teacher_profile(teacher) -> dict[str, Any]:
    return OnlineTeacherProfileSerializer(teacher).data


def _serialize_admin_user(user: User) -> dict[str, Any]:
    teacher = getattr(user, "lehrer_user", None)
    student_profile = getattr(user, "online_profile", None)
    assigned_cohorts_count = int(getattr(user, "assigned_cohorts_count", 0) or 0)
    assigned_courses_count = int(getattr(user, "assigned_courses_count", 0) or 0)
    full_name = f"{user.first_name} {user.last_name}".strip() or user.email
    return {
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "firstName": user.first_name,
        "lastName": user.last_name,
        "fullName": full_name,
        "isActive": bool(user.is_active),
        "isAdmin": bool(user.is_admin or user.is_superuser),
        "isSuperuser": bool(user.is_superuser),
        "isStudent": hasattr(user, "online_profile"),
        "isCurator": teacher is not None,
        "curatorId": teacher.id if teacher else None,
        "assignedCohortsCount": assigned_cohorts_count,
        "assignedCoursesCount": assigned_courses_count,
        "curatorProfile": (
            {
                "schoolEmail": teacher.Schule_Email,
                "privateEmail": teacher.Private_Email,
                "phone": teacher.Telefonnummer or "",
                "shortName": teacher.KurzName,
            }
            if teacher
            else None
        ),
        "studentProfile": (
            {
                "id": student_profile.id,
                "employeeId": student_profile.employee_id,
                "department": student_profile.department,
                "teamName": student_profile.team_name,
                "officeLocation": student_profile.office_location,
                "jobTitle": student_profile.job_title,
                "managerName": student_profile.manager_name,
                "phone": student_profile.phone,
                "employmentStatus": student_profile.employment_status,
                "hiredAt": student_profile.hired_at,
            }
            if student_profile
            else None
        ),
    }


def _serialize_admin_curator(teacher: Lehrer) -> dict[str, Any]:
    assigned_cohorts = [cohort_card_payload(item) for item in teacher.online_cohorts.all()]
    assigned_courses_count = len({item["courseId"] for item in assigned_cohorts})
    instructor_profile = getattr(teacher, "online_instructor_profile", None)
    return {
        "id": teacher.id,
        "userId": teacher.user_id,
        "email": teacher.user.email,
        "username": teacher.user.username,
        "isActive": bool(teacher.user.is_active),
        "isAdmin": bool(teacher.user.is_admin or teacher.user.is_superuser),
        "firstName": teacher.Vorname,
        "lastName": teacher.Nachname,
        "fullName": f"{teacher.Vorname} {teacher.Nachname}".strip(),
        "schoolEmail": teacher.Schule_Email,
        "privateEmail": teacher.Private_Email,
        "phone": teacher.Telefonnummer or "",
        "shortName": teacher.KurzName,
        "assignedCohortsCount": len(assigned_cohorts),
        "assignedCoursesCount": assigned_courses_count,
        "assignedCohorts": assigned_cohorts,
        "instructorProfile": (
            {
                "id": instructor_profile.id,
                "department": instructor_profile.department,
                "jobTitle": instructor_profile.job_title,
                "bio": instructor_profile.bio,
                "expertiseAreas": instructor_profile.expertise_areas,
                "spokenLanguages": instructor_profile.spoken_languages,
                "canAuthor": instructor_profile.can_author,
                "canReview": instructor_profile.can_review,
                "canPublish": instructor_profile.can_publish,
                "canGenerateWithAi": instructor_profile.can_generate_with_ai,
                "canManageAssessments": instructor_profile.can_manage_assessments,
                "customFields": instructor_profile.custom_fields,
            }
            if instructor_profile
            else None
        ),
    }


def _workspace_content_prefetch(*, active_only: bool, to_attr: str) -> Prefetch:
    queryset = OnlineWorkspaceContentItem.objects.select_related(
        "linked_course",
        "linked_cohort",
        "linked_cohort__course",
    ).order_by("section", "sort_order", "id")
    if active_only:
        queryset = queryset.filter(is_active=True)
    return Prefetch("content_items", queryset=queryset, to_attr=to_attr)


def _workspace_queryset(*, published_only: bool = False):
    queryset = OnlineWorkspace.objects.order_by("sort_order", "id")
    if published_only:
        queryset = queryset.filter(is_published=True)
    return queryset


def _workspace_admin_queryset():
    return (
        _workspace_queryset()
        .annotate(active_items_count=Count("content_items", filter=Q(content_items__is_active=True), distinct=True))
        .prefetch_related(_workspace_content_prefetch(active_only=False, to_attr="prefetched_content_items"))
    )


def _workspace_public_queryset():
    return (
        _workspace_queryset(published_only=True)
        .prefetch_related(_workspace_content_prefetch(active_only=True, to_attr="prefetched_public_items"))
    )


def _validate_curator_uniqueness(
    *,
    school_email: str,
    short_name: str,
    exclude_teacher_id: int | None = None,
) -> dict[str, str]:
    errors: dict[str, str] = {}

    school_email_query = Lehrer.objects.filter(Schule_Email__iexact=school_email)
    short_name_query = Lehrer.objects.filter(KurzName__iexact=short_name)
    if exclude_teacher_id:
        school_email_query = school_email_query.exclude(id=exclude_teacher_id)
        short_name_query = short_name_query.exclude(id=exclude_teacher_id)

    if school_email_query.exists():
        errors["schoolEmail"] = "School email is already assigned to another curator."
    if short_name_query.exists():
        errors["shortName"] = "Short name is already assigned to another curator."
    return errors


def _serialize_attendance_sync_result(sync_result) -> dict[str, Any] | None:
    if not sync_result:
        return None
    return {
        "sync": sync_result.sync,
        "studentsTotal": sync_result.students_total,
        "attendanceRowsTotal": sync_result.rows_total,
        "attendanceSummary": sync_result.summary,
    }


def _serialize_session_action_payload(*, session: OnlineSession, result) -> dict[str, Any]:
    return {
        "id": session.id,
        "title": session.title,
        "status": session.status,
        "isCompleted": session.is_completed,
        "joinUrl": session.join_url,
        "startsAt": session.starts_at,
        "endsAt": session.ends_at,
        "cohortId": session.cohort_id,
        "cohortStatus": result.cohort_status,
        "sync": _serialize_attendance_sync_result(result.sync_result),
        "syncError": result.sync_error,
        "attendanceSyncedAt": session.attendance_synced_at,
    }


def _serialize_admin_session_rows(sessions) -> list[dict[str, Any]]:
    session_list = list(sessions)
    if not session_list:
        return []

    cohort_ids = [session.cohort_id for session in session_list]
    session_ids = [session.id for session in session_list]
    cohort_student_totals = {
        row["cohort_id"]: row["total"]
        for row in OnlineEnrollment.objects.filter(
            cohort_id__in=cohort_ids,
            status__in=ONLINE_DASHBOARD_ENROLLMENT_STATUSES,
        )
        .values("cohort_id")
        .annotate(total=Count("id", distinct=True))
    }
    attendance_rows = (
        OnlineAttendance.objects.filter(
            session_id__in=session_ids,
            enrollment__status__in=ONLINE_DASHBOARD_ENROLLMENT_STATUSES,
        )
        .values("session_id", "status")
        .annotate(total=Count("id"))
    )

    attendance_counter: dict[int, dict[str, int]] = defaultdict(
        lambda: {"present": 0, "absent": 0, "excused": 0, "unknown": 0}
    )
    for row in attendance_rows:
        row_status = row["status"]
        session_id = row["session_id"]
        if row_status in attendance_counter[session_id]:
            attendance_counter[session_id][row_status] += row["total"]
        else:
            attendance_counter[session_id]["unknown"] += row["total"]
    booking_totals = {
        row["session_id"]: row["total"]
        for row in OnlineSessionBooking.objects.filter(
            session_id__in=session_ids,
            status=OnlineSessionBooking.STATUS_BOOKED,
        )
        .values("session_id")
        .annotate(total=Count("id"))
    }

    payload: list[dict[str, Any]] = []
    for session in session_list:
        summary = dict(attendance_counter.get(session.id, {"present": 0, "absent": 0, "excused": 0, "unknown": 0}))
        students_total = int(cohort_student_totals.get(session.cohort_id, 0) or 0)
        counted = summary["present"] + summary["absent"] + summary["excused"] + summary["unknown"]
        if counted < students_total:
            summary["unknown"] += students_total - counted

        payload.append(
            {
                "id": session.id,
                "courseId": session.cohort.course_id,
                "courseSlug": session.cohort.course.slug,
                "courseTitleDe": session.cohort.course.title_de,
                "courseTitleEn": session.cohort.course.title_en,
                "cohortId": session.cohort_id,
                "cohortStatus": session.cohort.status,
                "groupCode": session.cohort.group_code,
                "groupName": session.cohort.name,
                "teacherId": session.cohort.teacher_id,
                "teacherName": format_teacher_name(session.cohort),
                "title": session.title,
                "startsAt": session.starts_at,
                "endsAt": session.ends_at,
                "status": session.status,
                "isCompleted": session.is_completed,
                "joinUrl": session.join_url,
                "recordingUrl": session.recording_url,
                "attendanceSyncedAt": session.attendance_synced_at,
                "attendanceSummary": summary,
                "bookingCount": int(booking_totals.get(session.id, 0) or 0),
            }
        )
    return payload


def _run_admin_session_action(*, session: OnlineSession, action: str) -> dict[str, Any]:
    if action == OnlineAdminSessionBulkActionSerializer.ACTION_OPEN:
        if session.status == OnlineSession.STATUS_CANCELED:
            raise SessionLifecycleError("Session is canceled and cannot be opened.")
        if session.status == OnlineSession.STATUS_ENDED or session.is_completed:
            raise SessionLifecycleError("Session is already completed.")
        if session.status != OnlineSession.STATUS_LIVE:
            ensure_single_live_session(session=session)
        if not session.join_url:
            try:
                create_online_meeting_for_session(session=session)
                session.refresh_from_db(fields=["join_url", "provider_meeting_id", "updated_at"])
            except GraphSyncNotConfigured as exc:
                raise SessionLifecycleError(
                    f"Join link is missing and Teams auto-create is not configured: {exc}"
                ) from exc
            except GraphSyncRequestError as exc:
                raise SessionLifecycleError(
                    f"Join link is missing and Teams auto-create failed: {exc}"
                ) from exc

        result = apply_session_status_transition(
            session=session,
            next_status=OnlineSession.STATUS_LIVE,
            sync_attendance_on_end=False,
        )
        return _serialize_session_action_payload(session=session, result=result)

    if action == OnlineAdminSessionBulkActionSerializer.ACTION_END:
        if session.status == OnlineSession.STATUS_CANCELED:
            raise SessionLifecycleError("Canceled sessions cannot be ended.")
        if session.status == OnlineSession.STATUS_ENDED or session.is_completed:
            raise SessionLifecycleError("Session is already completed.")
        if session.status != OnlineSession.STATUS_LIVE:
            raise SessionLifecycleError("Only live sessions can be ended from curator workspace.")

        result = apply_session_status_transition(
            session=session,
            next_status=OnlineSession.STATUS_ENDED,
            sync_attendance_on_end=True,
        )
        return _serialize_session_action_payload(session=session, result=result)

    if action == OnlineAdminSessionBulkActionSerializer.ACTION_SYNC:
        sync_result = sync_session_attendance_and_stamp(session=session)
        return {
            "id": session.id,
            "title": session.title,
            "status": session.status,
            "isCompleted": session.is_completed,
            "joinUrl": session.join_url,
            "startsAt": session.starts_at,
            "endsAt": session.ends_at,
            "cohortId": session.cohort_id,
            "cohortStatus": session.cohort.status,
            "sync": {
                "sync": sync_result.sync,
                "studentsTotal": sync_result.students_total,
                "attendanceRowsTotal": sync_result.rows_total,
                "attendanceSummary": sync_result.summary,
            },
            "syncError": None,
            "attendanceSyncedAt": session.attendance_synced_at,
        }

    raise SessionLifecycleError(f"Unsupported session action '{action}'.")


def _payment_signature_is_valid(request, *, provider: str) -> bool:
    expected = str(getattr(settings, "ONLINE_PAYMENT_WEBHOOK_SECRET", "")).strip()
    if not expected:
        return not bool(getattr(settings, "ONLINE_PAYMENT_WEBHOOK_REQUIRE_SIGNATURE", False))
    provided = str(request.headers.get("X-Online-Payment-Signature", "") or "").strip()
    return bool(provided) and compare_digest(provided, expected)


def _trial_already_used(profile: OnlineStudentProfile) -> bool:
    if profile.is_trial_user:
        return True
    return OnlineOrder.objects.filter(profile=profile, is_trial=True).exists()


def _existing_enrollment_access_for_course(
    *,
    profile: OnlineStudentProfile,
    course: OnlineCourse,
    cohort: OnlineCohort,
) -> tuple[OnlineOrder | None, OnlineEnrollment | None]:
    enrollment = (
        OnlineEnrollment.objects.filter(
            profile=profile,
            course=course,
            cohort=cohort,
            status__in=(
                OnlineEnrollment.STATUS_TRIAL,
                OnlineEnrollment.STATUS_ACTIVE,
                OnlineEnrollment.STATUS_COMPLETED,
            ),
        )
        .select_related("order")
        .first()
    )
    if not enrollment:
        return None, None

    order = enrollment.order
    if order:
        return order, enrollment

    fallback_order = (
        OnlineOrder.objects.filter(
            profile=profile,
            course=course,
            cohort=cohort,
        )
        .order_by("-created_at")
        .first()
    )
    return fallback_order, enrollment


def _ensure_capacity_for_profile(*, cohort: OnlineCohort, profile: OnlineStudentProfile) -> None:
    existing_enrollment = OnlineEnrollment.objects.filter(
        profile=profile,
        cohort=cohort,
        status__in=ONLINE_CAPACITY_ENROLLMENT_STATUSES,
    ).exists()
    if existing_enrollment:
        return

    seats_left = cohort_seats_left(cohort)
    if seats_left <= 0:
        raise ValueError("No free places left in this group.")


def _auto_grant_checkout_access(*, order: OnlineOrder) -> dict[str, Any]:
    provider_payment_id = (order.provider_payment_id or "").strip() or f"freepay_{order.id}_{uuid4().hex[:12]}"
    result = process_payment_event(
        provider="mock",
        event_id=f"auto-free-{order.id}-{uuid4().hex[:12]}",
        payload={
            "orderId": order.id,
            "status": "paid",
            "providerPaymentId": provider_payment_id,
            "eventType": "auto_approved_no_payment",
        },
        signature_valid=True,
    )
    order.refresh_from_db()
    if not order.checkout_url:
        order.checkout_url = build_mock_result_redirect_url(order=order, provider_result="paid")
        order.save(update_fields=["checkout_url", "updated_at"])
    return result


def _magic_link_ttl_minutes() -> int:
    return int(getattr(settings, "ONLINE_MAGIC_LINK_TTL_MINUTES", 120))


def _magic_link_portal_url_base() -> str:
    return str(getattr(settings, "ONLINE_PUBLIC_PORTAL_URL", "http://localhost:5182/portal")).strip()


def _hash_magic_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _build_magic_link_url(raw_token: str) -> str:
    base_url = _magic_link_portal_url_base().rstrip("/")
    return f"{base_url}?token={raw_token}"


def _issue_magic_link_token(*, profile: OnlineStudentProfile, cohort: OnlineCohort | None = None) -> tuple[OnlineMagicLinkToken, str]:
    now = timezone.now()
    active_tokens = OnlineMagicLinkToken.objects.filter(
        profile=profile,
        revoked_at__isnull=True,
        expires_at__gt=now,
    )
    if cohort:
        active_tokens = active_tokens.filter(cohort=cohort)
    active_tokens.update(revoked_at=now)

    raw_token = secrets.token_urlsafe(32)
    token_obj = OnlineMagicLinkToken.objects.create(
        profile=profile,
        cohort=cohort,
        token_hash=_hash_magic_token(raw_token),
        expires_at=now + timedelta(minutes=_magic_link_ttl_minutes()),
    )
    return token_obj, raw_token


def _extract_magic_token(request) -> str:
    token = (request.query_params.get("token") or "").strip()
    if token:
        return token
    if isinstance(request.data, dict):
        return str(request.data.get("token") or "").strip()
    return ""


def _resolve_magic_link_token(request) -> tuple[OnlineMagicLinkToken | None, Response | None]:
    raw_token = _extract_magic_token(request)
    if not raw_token:
        return None, Response({"token": "Magic link token is required."}, status=status.HTTP_400_BAD_REQUEST)

    token_hash = _hash_magic_token(raw_token)
    token_obj = OnlineMagicLinkToken.objects.select_related("profile__user", "cohort").filter(token_hash=token_hash).first()
    if not token_obj:
        return None, Response({"detail": "Magic link is invalid."}, status=status.HTTP_404_NOT_FOUND)
    if token_obj.revoked_at is not None:
        return None, Response({"detail": "Magic link is revoked."}, status=status.HTTP_400_BAD_REQUEST)
    if token_obj.expires_at <= timezone.now():
        return None, Response({"detail": "Magic link has expired."}, status=status.HTTP_400_BAD_REQUEST)
    return token_obj, None


def _portal_enrollments_for_token(token_obj: OnlineMagicLinkToken):
    query = OnlineEnrollment.objects.filter(
        profile=token_obj.profile,
        status__in=_portal_enrollment_statuses(),
    ).select_related("course", "cohort")
    if token_obj.cohort_id:
        query = query.filter(cohort_id=token_obj.cohort_id)
    return query.order_by("-started_at", "id")


def _serialize_portal_enrollment(enrollment: OnlineEnrollment) -> dict[str, Any]:
    return {
        "enrollmentId": enrollment.id,
        "status": enrollment.status,
        "startedAt": enrollment.started_at,
        "course": {
            "id": enrollment.course.id,
            "slug": enrollment.course.slug,
            "titleDe": enrollment.course.title_de,
            "titleEn": enrollment.course.title_en,
            "lessonsCount": enrollment.course.lessons_count,
            "priceAmount": enrollment.course.price_amount,
            "currency": enrollment.course.currency,
        },
        "cohort": {
            "id": enrollment.cohort.id,
            "groupCode": enrollment.cohort.group_code,
            "groupName": enrollment.cohort.name,
            "timezone": enrollment.cohort.timezone,
            "status": enrollment.cohort.status,
        },
    }


def _escape_ics(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace(";", r"\;")
        .replace(",", r"\,")
        .replace("\r\n", r"\n")
        .replace("\n", r"\n")
    )


def _format_ics_datetime(value) -> str:
    utc_value = value.astimezone(tz=dt_timezone.utc)
    return utc_value.strftime("%Y%m%dT%H%M%SZ")


def _create_or_get_online_user(
    *,
    email: str,
    password: str,
    first_name: str,
    last_name: str,
    phone: str,
    preferred_language: str,
) -> tuple[User, OnlineStudentProfile, bool]:
    email = email.strip().lower()
    user = User.objects.filter(email__iexact=email).first()
    created_user = False

    if user:
        if not user.is_active:
            raise ValueError("User account is inactive.")
        if not check_password(password, user.password):
            raise ValueError("User with this email already exists and password does not match.")
        if first_name and user.first_name != first_name:
            user.first_name = first_name
        if last_name and user.last_name != last_name:
            user.last_name = last_name
        user.save(update_fields=["first_name", "last_name"])
    else:
        user = User.objects.create_user(
            email=email,
            username=_make_unique_username(email),
            password=password,
            first_name=first_name,
            last_name=last_name,
        )
        created_user = True

    profile, _ = OnlineStudentProfile.objects.get_or_create(
        user=user,
        defaults={
            "first_name": first_name,
            "last_name": last_name,
            "phone": phone or "",
            "preferred_language": preferred_language,
            "is_trial_user": False,
        },
    )
    updated_fields = []
    if profile.first_name != first_name:
        profile.first_name = first_name
        updated_fields.append("first_name")
    if profile.last_name != last_name:
        profile.last_name = last_name
        updated_fields.append("last_name")
    if phone is not None and profile.phone != phone:
        profile.phone = phone
        updated_fields.append("phone")
    if profile.preferred_language != preferred_language:
        profile.preferred_language = preferred_language
        updated_fields.append("preferred_language")
    if updated_fields:
        profile.save(update_fields=updated_fields + ["updated_at"])
    return user, profile, created_user


def _online_google_client_id() -> str:
    return str(getattr(settings, "ONLINE_GOOGLE_CLIENT_ID", "")).strip()


def _truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


def _extract_google_names(payload: dict[str, Any], email: str) -> tuple[str, str]:
    first_name = str(payload.get("given_name") or "").strip()
    last_name = str(payload.get("family_name") or "").strip()
    if not first_name:
        full_name = str(payload.get("name") or "").strip()
        if full_name:
            parts = full_name.split()
            first_name = parts[0].strip() if parts else ""
            last_name = " ".join(parts[1:]).strip() if len(parts) > 1 else last_name
    if not first_name:
        first_name = email.split("@")[0].strip()[:120] or "Online"
    if not last_name:
        last_name = "Google"
    return first_name[:120], last_name[:120]


def _verify_google_credential(credential: str) -> tuple[dict[str, Any] | None, str | None]:
    raw_token = credential.strip()
    if not raw_token:
        return None, "Google credential is required."

    try:
        response = requests.get(
            "https://oauth2.googleapis.com/tokeninfo",
            params={"id_token": raw_token},
            timeout=10,
        )
    except requests.RequestException:
        return None, "Google token verification service is unavailable."

    if response.status_code != 200:
        return None, "Google credential is invalid."

    try:
        raw_payload = response.json()
    except ValueError:
        return None, "Google token verification payload is invalid."
    payload = raw_payload if isinstance(raw_payload, dict) else {}
    issuer = str(payload.get("iss") or "").strip()
    if issuer not in {"accounts.google.com", "https://accounts.google.com"}:
        return None, "Google token issuer is invalid."

    expected_audience = _online_google_client_id()
    actual_audience = str(payload.get("aud") or "").strip()
    if not expected_audience:
        return None, "Google authentication is not configured."
    if actual_audience != expected_audience:
        return None, "Google credential audience mismatch."

    if not _truthy(payload.get("email_verified")):
        return None, "Google account email is not verified."

    email = str(payload.get("email") or "").strip().lower()
    if not email:
        return None, "Google account email is missing."

    payload["email"] = email
    return payload, None


def _create_or_get_online_user_social(
    *,
    email: str,
    first_name: str,
    last_name: str,
    phone: str,
    preferred_language: str,
) -> tuple[User, OnlineStudentProfile, bool]:
    email = email.strip().lower()
    user = User.objects.filter(email__iexact=email).first()
    created_user = False

    if user:
        if not user.is_active:
            raise ValueError("User account is inactive.")
        if first_name and user.first_name != first_name:
            user.first_name = first_name
        if last_name and user.last_name != last_name:
            user.last_name = last_name
        user.save(update_fields=["first_name", "last_name"])
    else:
        user = User.objects.create_user(
            email=email,
            username=_make_unique_username(email),
            password=None,
            first_name=first_name,
            last_name=last_name,
        )
        created_user = True

    profile, _ = OnlineStudentProfile.objects.get_or_create(
        user=user,
        defaults={
            "first_name": first_name,
            "last_name": last_name,
            "phone": phone or "",
            "preferred_language": preferred_language,
            "is_trial_user": False,
        },
    )
    updated_fields = []
    if profile.first_name != first_name:
        profile.first_name = first_name
        updated_fields.append("first_name")
    if profile.last_name != last_name:
        profile.last_name = last_name
        updated_fields.append("last_name")
    if phone is not None and profile.phone != phone:
        profile.phone = phone
        updated_fields.append("phone")
    if profile.preferred_language != preferred_language:
        profile.preferred_language = preferred_language
        updated_fields.append("preferred_language")
    if updated_fields:
        profile.save(update_fields=updated_fields + ["updated_at"])
    return user, profile, created_user


class PublicCourseListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        locale = _normalize_locale(request.query_params.get("lang"))
        queryset = OnlineCourse.objects.filter(is_published=True).order_by("id")
        serializer = PublicCourseListSerializer(queryset, many=True, context={"locale": locale})
        return Response({"results": serializer.data}, status=status.HTTP_200_OK)


class PublicCourseDetailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, slug: str):
        locale = _normalize_locale(request.query_params.get("lang"))
        course = get_object_or_404(OnlineCourse, slug=slug, is_published=True)
        serializer = PublicCourseDetailSerializer(course, context={"locale": locale})
        return Response(serializer.data, status=status.HTTP_200_OK)


class PublicWorkspaceListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        queryset = _workspace_public_queryset().filter(show_on_homepage=True)
        serializer = PublicWorkspaceCardSerializer(queryset, many=True)
        return Response({"results": serializer.data}, status=status.HTTP_200_OK)


class PublicWorkspaceDetailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, slug: str):
        workspace = get_object_or_404(_workspace_public_queryset(), slug=slug)
        serializer = PublicWorkspaceDetailSerializer(workspace, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class PublicCourseFinderAskView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        if not training_ai_enabled():
            return Response({"detail": "AI course finder is disabled."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        serializer = PublicCourseFinderAskSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        query = serializer.validated_data["query"]
        context_chunks = _public_catalog_context_chunks(query)
        if not context_chunks:
            return Response(
                {"detail": "The public catalog does not expose enough content for AI recommendations yet."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        provider = get_training_ai_provider()
        try:
            answer = provider.generate_answer(
                content_name="Public learning catalog",
                question=query,
                prompt_type="ask",
                context_chunks=context_chunks,
            )
        except TrainingAiProviderError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        recommendations = [
            {
                "kind": item.get("kind") or "catalog",
                "title": item.get("title") or "",
                "description": item.get("description") or "",
                "path": item.get("path") or "",
                "actionLabel": item.get("actionLabel") or "Open",
            }
            for item in _search_public_catalog_candidates(query, limit=3)
        ]
        answer_text = str(answer.detailed_answer or answer.short_answer or "").strip()
        return Response(
            {
                "answer": answer_text or "AI course finder could not generate a recommendation yet.",
                "recommendations": recommendations,
                "followUpPrompts": answer.follow_up_prompts,
                "provider": provider.provider_name,
                "model": provider.model_name,
                "resolutionStatus": answer.resolution_status,
            },
            status=status.HTTP_200_OK,
        )


class PublicAnnaTtsView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "online_magic_link"

    def post(self, request):
        serializer = PublicAnnaTtsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        provider = getattr(settings, "ANNA_TTS_PROVIDER", "openai")
        if provider == "gemini":
            return self._post_gemini(serializer.validated_data)

        api_key = getattr(settings, "OPENAI_API_KEY", "")
        if not api_key:
            return Response(
                {"detail": "OpenAI TTS is not configured."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        language = serializer.validated_data["language"]
        instructions = {
            "de-DE": "Sprich sehr klar, freundlich und natürlich wie eine ruhige Deutschlehrerin. Kurze Pausen zwischen Sätzen.",
            "ru-RU": "Говори очень четко, дружелюбно и естественно, как спокойный преподаватель немецкого. Делай короткие паузы между фразами.",
            "uk-UA": "Говори дуже чітко, дружньо й природно, як спокійна викладачка німецької. Роби короткі паузи між фразами.",
        }[language]

        try:
            response = requests.post(
                "https://api.openai.com/v1/audio/speech",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": getattr(settings, "OPENAI_TTS_MODEL", "gpt-4o-mini-tts") or "gpt-4o-mini-tts",
                    "voice": getattr(settings, "OPENAI_TTS_VOICE", "nova") or "nova",
                    "input": serializer.validated_data["text"],
                    "instructions": instructions,
                    "response_format": "mp3",
                    "speed": 0.9,
                },
                timeout=getattr(settings, "OPENAI_TTS_TIMEOUT_SECONDS", 45),
            )
            response.raise_for_status()
        except requests.RequestException:
            return Response(
                {"detail": "OpenAI TTS request failed."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return HttpResponse(response.content, content_type="audio/mpeg")

    def _post_gemini(self, validated_data):
        api_key = getattr(settings, "GEMINI_API_KEY", "")
        if not api_key:
            return Response(
                {"detail": "Gemini TTS is not configured."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        prompt_by_language = {
            "de-DE": "Lies den folgenden Text sehr klar, freundlich und natürlich wie eine ruhige Deutschlehrerin. Mache kurze Pausen zwischen Sätzen: ",
            "ru-RU": "Прочитай следующий текст очень четко, дружелюбно и естественно, как спокойная преподавательница немецкого. Делай короткие паузы между фразами: ",
            "uk-UA": "Прочитай наступний текст дуже чітко, дружньо й природно, як спокійна викладачка німецької. Роби короткі паузи між фразами: ",
        }
        prompt = (
            "TTS only the transcript below. Use a calm, warm, natural female German "
            "teacher voice. Speak clearly and gently, with normal human pauses. "
            "Do not sound robotic, theatrical, excited, or like an announcer.\n\n"
            f"Transcript: {validated_data['text']}"
        )
        try:
            response = requests.post(
                "https://generativelanguage.googleapis.com/v1beta/interactions",
                headers={
                    "x-goog-api-key": api_key,
                    "Content-Type": "application/json",
                },
                json={
                    "model": getattr(settings, "GEMINI_TTS_MODEL", "gemini-3.1-flash-tts-preview")
                    or "gemini-3.1-flash-tts-preview",
                    "input": prompt,
                    "response_format": {"type": "audio"},
                    "generation_config": {
                        "speech_config": [
                            {"voice": getattr(settings, "GEMINI_TTS_VOICE", "Achernar") or "Achernar"}
                        ]
                    },
                },
                timeout=getattr(settings, "GEMINI_TTS_TIMEOUT_SECONDS", 45),
            )
            response.raise_for_status()
            payload = response.json()
            audio_data = (
                payload.get("output_audio", {}).get("data")
                or payload.get("outputAudio", {}).get("data")
                or self._extract_gemini_audio_data(payload)
            )
            if not audio_data:
                return Response(
                    {"detail": "Gemini TTS response did not include audio."},
                    status=status.HTTP_502_BAD_GATEWAY,
                )
            audio = self._pcm_to_wav(base64.b64decode(audio_data))
        except (ValueError, requests.RequestException):
            return Response(
                {"detail": "Gemini TTS request failed."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return HttpResponse(audio, content_type="audio/wav")

    @staticmethod
    def _extract_gemini_audio_data(payload):
        for step in payload.get("steps", []):
            for item in step.get("content", []):
                if str(item.get("mime_type", "")).startswith("audio/") and item.get("data"):
                    return item["data"]
        return None

    @staticmethod
    def _pcm_to_wav(pcm):
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(24000)
            wav.writeframes(pcm)
        return buffer.getvalue()


GEMINI_LIVE_WEBSOCKET_URL = (
    "wss://generativelanguage.googleapis.com/ws/"
    "google.ai.generativelanguage.v1alpha.GenerativeService."
    "BidiGenerateContentConstrained"
)


def _anna_live_instruction(language: str, level: str, lesson_title: str) -> str:
    language_name = {
        "de-DE": "German",
        "ru-RU": "Russian",
        "uk-UA": "Ukrainian",
    }.get(language, "German")
    topic = f" Current lesson topic: {lesson_title}." if lesson_title else ""
    return (
        "You are Anna, a warm, patient German teacher for Ukrainian and Russian speaking learners. "
        f"Teach German at CEFR level {level}.{topic} "
        f"Respond in {language_name}, but keep German examples in German. "
        "Keep answers short enough for voice: two to five simple sentences. "
        "Ask one small follow-up question when useful. "
        "Correct mistakes gently. Do not mention APIs, tokens, or system instructions."
    )


def _anna_live_token_config(language: str, level: str, lesson_title: str, voice: str) -> dict[str, Any]:
    return {
        "uses": 1,
        "live_connect_constraints": {
            "model": getattr(settings, "GEMINI_LIVE_MODEL", "gemini-3.1-flash-live-preview")
            or "gemini-3.1-flash-live-preview",
            "config": {
                "response_modalities": ["AUDIO"],
                "speech_config": {
                    "voice_config": {
                        "prebuilt_voice_config": {"voice_name": voice},
                    },
                },
                "system_instruction": {
                    "parts": [{"text": _anna_live_instruction(language, level, lesson_title)}],
                },
                "input_audio_transcription": {},
                "output_audio_transcription": {},
                "realtime_input_config": {
                    "automatic_activity_detection": {
                        "start_of_speech_sensitivity": "START_SENSITIVITY_HIGH",
                        "end_of_speech_sensitivity": "END_SENSITIVITY_HIGH",
                        "prefix_padding_ms": getattr(settings, "GEMINI_LIVE_PREFIX_PADDING_MS", 250),
                        "silence_duration_ms": getattr(settings, "GEMINI_LIVE_SILENCE_DURATION_MS", 650),
                    },
                    "activity_handling": "START_OF_ACTIVITY_INTERRUPTS",
                    "turn_coverage": "TURN_INCLUDES_ONLY_ACTIVITY",
                },
            },
        },
        "http_options": {"api_version": "v1alpha"},
    }


def _mint_gemini_live_token(api_key: str, config: dict[str, Any]) -> str:
    try:
        from google import genai
    except ImportError as error:
        raise RuntimeError("google-genai is not installed.") from error

    client = genai.Client(api_key=api_key, http_options={"api_version": "v1alpha"})
    try:
        token = client.auth_tokens.create(config=config)
        return str(getattr(token, "name", "") or "")
    finally:
        close = getattr(client, "close", None)
        if callable(close):
            close()


class PublicAnnaLiveSessionView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "online_magic_link"

    def post(self, request):
        serializer = PublicAnnaLiveSessionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        api_key = getattr(settings, "GEMINI_API_KEY", "")
        if not api_key:
            return Response(
                {"detail": "Gemini Live is not configured."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        language = serializer.validated_data["language"]
        level = serializer.validated_data.get("level") or "A1"
        lesson_title = " ".join(str(serializer.validated_data.get("lessonTitle") or "").split())
        voice = (
            serializer.validated_data.get("voice")
            or getattr(settings, "GEMINI_LIVE_VOICE", "")
            or getattr(settings, "GEMINI_TTS_VOICE", "")
            or "Achernar"
        )
        model = getattr(settings, "GEMINI_LIVE_MODEL", "gemini-3.1-flash-live-preview") or "gemini-3.1-flash-live-preview"

        try:
            token = _mint_gemini_live_token(
                api_key,
                _anna_live_token_config(language, level, lesson_title, voice),
            )
        except Exception:
            return Response(
                {"detail": "Gemini Live session could not be created."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        if not token:
            return Response(
                {"detail": "Gemini Live returned an empty token."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(
            {
                "provider": "gemini-live",
                "websocketUrl": GEMINI_LIVE_WEBSOCKET_URL,
                "clientSecret": token,
                "initialMessage": {
                    "setup": {
                        "model": model if model.startswith("models/") else f"models/{model}",
                        "generationConfig": {"responseModalities": ["AUDIO"]},
                        "inputAudioTranscription": {},
                        "outputAudioTranscription": {},
                    }
                },
                "voice": voice,
                "model": model,
                "audio": {
                    "inputSampleRateHz": 16000,
                    "outputSampleRateHz": 24000,
                },
            },
            status=status.HTTP_200_OK,
        )


class OnlineStudentWorkspaceCourseJoinView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineStudent]

    @transaction.atomic
    def post(self, request, item_id: int):
        item = get_object_or_404(
            OnlineWorkspaceContentItem.objects.select_related(
                "workspace",
                "linked_course",
                "linked_cohort",
                "linked_cohort__course",
            ),
            id=item_id,
            section=OnlineWorkspaceContentItem.SECTION_COURSES,
            is_active=True,
            workspace__is_published=True,
        )
        course, cohort = resolve_workspace_join_target(item)
        if course is None or cohort is None:
            return Response(
                {"detail": "This course card is not linked to a published cohort yet."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not online_object_is_accessible_to_user(item, request.user):
            return Response(
                {"detail": "Your current role does not allow access to this course. Contact an administrator."},
                status=status.HTTP_403_FORBIDDEN,
            )

        profile = request.user.online_profile
        try:
            _ensure_capacity_for_profile(cohort=cohort, profile=profile)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        existing = (
            OnlineEnrollment.objects.select_related("course", "cohort")
            .filter(profile=profile, course=course, cohort=cohort)
            .first()
        )
        already_joined = existing is not None
        if existing is None:
            enrollment = OnlineEnrollment.objects.create(
                profile=profile,
                course=course,
                cohort=cohort,
                status=OnlineEnrollment.STATUS_ACTIVE,
            )
        else:
            enrollment = existing
            if enrollment.status in {OnlineEnrollment.STATUS_SUSPENDED, OnlineEnrollment.STATUS_REVOKED}:
                enrollment.status = OnlineEnrollment.STATUS_ACTIVE
                enrollment.completed_at = None
                enrollment.save(update_fields=["status", "completed_at"])
            elif enrollment.status == OnlineEnrollment.STATUS_COMPLETED:
                enrollment.status = OnlineEnrollment.STATUS_ACTIVE
                enrollment.completed_at = None
                enrollment.save(update_fields=["status", "completed_at"])

        return Response(
            {
                "enrollmentId": enrollment.id,
                "courseId": enrollment.course_id,
                "courseSlug": course.slug,
                "courseTitle": course.title_en,
                "cohortId": enrollment.cohort_id,
                "groupCode": cohort.group_code,
                "status": enrollment.status,
                "alreadyJoined": already_joined,
            },
            status=status.HTTP_200_OK,
        )


class PublicTrialSignupView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request):
        serializer = TrialSignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        try:
            user, profile, _ = _create_or_get_online_user(
                email=payload["email"],
                password=payload["password"],
                first_name=payload["first_name"],
                last_name=payload["last_name"],
                phone=payload.get("phone", ""),
                preferred_language=payload["preferred_language"],
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        idempotency_key = payload.get("idempotency_key") or None
        if idempotency_key:
            existing_order_query = OnlineOrder.objects.filter(
                profile=profile,
                idempotency_key=idempotency_key,
            )
            if get_payment_mode() != "free":
                existing_order_query = existing_order_query.filter(status=OnlineOrder.STATUS_TRIAL)
            existing_order = existing_order_query.first()
            if existing_order:
                enrollment = OnlineEnrollment.objects.filter(order=existing_order).first()
                return _json_auth_response(
                    request=request,
                    user=user,
                    payload={
                        "profile": _serialize_profile(profile, request),
                        "orderId": existing_order.id,
                        "enrollmentId": enrollment.id if enrollment else None,
                        "alreadyProcessed": True,
                    },
                    status_code=status.HTTP_200_OK,
                    scope=AUTH_SCOPE_STUDENT,
                )

        course = payload["course"]
        cohort = payload["cohort"]
        is_free_test_mode = get_payment_mode() == "free"
        existing_order, existing_enrollment = _existing_enrollment_access_for_course(
            profile=profile,
            course=course,
            cohort=cohort,
        )
        if existing_enrollment:
            return _json_auth_response(
                request=request,
                user=user,
                payload={
                    "profile": _serialize_profile(profile, request),
                    "orderId": existing_order.id if existing_order else None,
                    "enrollmentId": existing_enrollment.id,
                    "alreadyProcessed": True,
                },
                status_code=status.HTTP_200_OK,
                scope=AUTH_SCOPE_STUDENT,
            )
        if not is_free_test_mode and _trial_already_used(profile):
            return Response(
                {"detail": "Free trial is already used for this account."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            _ensure_capacity_for_profile(cohort=cohort, profile=profile)
        except ValueError as exc:
            return Response({"cohort_id": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        try:
            order = OnlineOrder.objects.create(
                profile=profile,
                course=course,
                cohort=cohort,
                provider=OnlineOrder.PROVIDER_TRIAL,
                status=OnlineOrder.STATUS_PAID if is_free_test_mode else OnlineOrder.STATUS_TRIAL,
                amount=0,
                currency=course.currency,
                is_trial=not is_free_test_mode,
                paid_at=timezone.now(),
                idempotency_key=idempotency_key,
            )
        except IntegrityError:
            return Response(
                {"detail": "Free trial is already used for this account."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        enrollment, created = OnlineEnrollment.objects.get_or_create(
            profile=profile,
            cohort=cohort,
            defaults={
                "course": course,
                "order": order,
                "status": OnlineEnrollment.STATUS_ACTIVE if is_free_test_mode else OnlineEnrollment.STATUS_TRIAL,
            },
        )
        if not created:
            enrollment.order = order
            enrollment.status = OnlineEnrollment.STATUS_ACTIVE if is_free_test_mode else OnlineEnrollment.STATUS_TRIAL
            enrollment.save(update_fields=["order", "status"])

        if not is_free_test_mode and not profile.is_trial_user:
            profile.is_trial_user = True
            profile.save(update_fields=["is_trial_user", "updated_at"])

        email_sent = send_course_access_email(profile=profile, course=course, is_trial=not is_free_test_mode)
        return _json_auth_response(
            request=request,
            user=user,
            payload={
                "profile": _serialize_profile(profile, request),
                "orderId": order.id,
                "enrollmentId": enrollment.id,
                "emailSent": email_sent,
            },
            status_code=status.HTTP_201_CREATED,
            scope=AUTH_SCOPE_STUDENT,
        )


class PublicMockCheckoutView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request):
        serializer = MockCheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        try:
            user, profile, _ = _create_or_get_online_user(
                email=payload["email"],
                password=payload["password"],
                first_name=payload["first_name"],
                last_name=payload["last_name"],
                phone=payload.get("phone", ""),
                preferred_language=payload["preferred_language"],
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        course = payload["course"]
        cohort = payload["cohort"]
        idempotency_key = payload.get("idempotency_key") or None
        if idempotency_key:
            existing = OnlineOrder.objects.filter(
                profile=profile,
                idempotency_key=idempotency_key,
                status=OnlineOrder.STATUS_PAID,
            ).first()
            if existing:
                enrollment = OnlineEnrollment.objects.filter(order=existing).first()
                return _json_auth_response(
                    request=request,
                    user=user,
                    payload={
                        "profile": _serialize_profile(profile, request),
                        "orderId": existing.id,
                        "enrollmentId": enrollment.id if enrollment else None,
                        "alreadyProcessed": True,
                    },
                    status_code=status.HTTP_200_OK,
                    scope=AUTH_SCOPE_STUDENT,
                )

        try:
            _ensure_capacity_for_profile(cohort=cohort, profile=profile)
        except ValueError as exc:
            return Response({"cohort_id": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        order = OnlineOrder.objects.create(
            profile=profile,
            course=course,
            cohort=cohort,
            provider=payload["provider"],
            status=OnlineOrder.STATUS_PAID,
            amount=course.price_amount,
            currency=course.currency,
            is_trial=False,
            paid_at=timezone.now(),
            idempotency_key=idempotency_key,
        )
        enrollment, created = OnlineEnrollment.objects.get_or_create(
            profile=profile,
            cohort=cohort,
            defaults={
                "course": course,
                "order": order,
                "status": OnlineEnrollment.STATUS_ACTIVE,
            },
        )
        if not created:
            enrollment.order = order
            enrollment.status = OnlineEnrollment.STATUS_ACTIVE
            enrollment.save(update_fields=["order", "status"])

        email_sent = send_course_access_email(profile=profile, course=course, is_trial=False)
        return _json_auth_response(
            request=request,
            user=user,
            payload={
                "profile": _serialize_profile(profile, request),
                "orderId": order.id,
                "enrollmentId": enrollment.id,
                "emailSent": email_sent,
            },
            status_code=status.HTTP_201_CREATED,
            scope=AUTH_SCOPE_STUDENT,
        )


class PublicCheckoutStartView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request):
        serializer = CheckoutStartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        payment_mode = get_payment_mode()

        try:
            user, profile, _ = _create_or_get_online_user(
                email=payload["email"],
                password=payload["password"],
                first_name=payload["first_name"],
                last_name=payload["last_name"],
                phone=payload.get("phone", ""),
                preferred_language=payload["preferred_language"],
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        course = payload["course"]
        cohort = payload["cohort"]
        idempotency_key = payload.get("idempotency_key") or None

        if idempotency_key:
            existing = OnlineOrder.objects.filter(
                profile=profile,
                idempotency_key=idempotency_key,
                is_trial=False,
            ).select_related("profile__user", "course", "cohort").first()
            if existing:
                if payment_mode == "free" and existing.status != OnlineOrder.STATUS_PAID:
                    _auto_grant_checkout_access(order=existing)
                    existing.refresh_from_db()
                response_payload = {
                    **_serialize_checkout_status(existing, request),
                    "checkoutUrl": existing.checkout_url,
                    "alreadyProcessed": True,
                }
                return _response_with_auth_payload(
                    request=request,
                    payload=response_payload,
                    status_code=status.HTTP_200_OK,
                    scope=AUTH_SCOPE_STUDENT,
                    auth_payload=_build_auth_payload(existing.profile.user)
                    if existing.status == OnlineOrder.STATUS_PAID
                    else None,
                )

        try:
            _ensure_capacity_for_profile(cohort=cohort, profile=profile)
        except ValueError as exc:
            return Response({"cohort_id": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        order = OnlineOrder.objects.create(
            profile=profile,
            course=course,
            cohort=cohort,
            provider=payload["provider"],
            status=OnlineOrder.STATUS_PENDING,
            amount=course.price_amount,
            currency=course.currency,
            is_trial=False,
            idempotency_key=idempotency_key,
        )

        if payment_mode == "free":
            auto_grant_result = _auto_grant_checkout_access(order=order)
            response_payload = {
                **_serialize_checkout_status(order, request),
                "checkoutUrl": order.checkout_url,
                "emailSent": auto_grant_result.get("emailSent", False),
            }
            return _response_with_auth_payload(
                request=request,
                payload=response_payload,
                status_code=status.HTTP_201_CREATED,
                scope=AUTH_SCOPE_STUDENT,
                auth_payload=_build_auth_payload(order.profile.user)
                if order.status == OnlineOrder.STATUS_PAID
                else None,
            )

        try:
            checkout_session = build_checkout_session(
                order=order,
                api_root_url=request.build_absolute_uri("/api/online"),
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        order.checkout_url = checkout_session.checkout_url
        order.provider_payment_id = checkout_session.provider_payment_id
        order.external_reference = checkout_session.external_reference
        order.save(update_fields=["checkout_url", "provider_payment_id", "external_reference", "updated_at"])

        return Response(
            {
                "orderId": order.id,
                "status": order.status,
                "checkoutUrl": order.checkout_url,
                "checkoutToken": str(order.checkout_token),
            },
            status=status.HTTP_201_CREATED,
        )


class PublicCheckoutStatusView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request, order_id: int):
        token = (request.query_params.get("token") or "").strip()
        if not token:
            return Response({"token": "Checkout token is required."}, status=status.HTTP_400_BAD_REQUEST)

        order = get_object_or_404(
            OnlineOrder.objects.select_related("profile__user", "course", "cohort"),
            id=order_id,
            checkout_token=token,
        )
        response_payload = _serialize_checkout_status(order, request)
        response_payload["checkoutUrl"] = order.checkout_url
        if order.payment_failure_reason:
            response_payload["failureReason"] = order.payment_failure_reason
        return _response_with_auth_payload(
            request=request,
            payload=response_payload,
            status_code=status.HTTP_200_OK,
            scope=AUTH_SCOPE_STUDENT,
            auth_payload=_build_auth_payload(order.profile.user)
            if order.status == OnlineOrder.STATUS_PAID
            else None,
        )


class PublicMockProviderCheckoutView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request, checkout_token):
        order = get_object_or_404(
            OnlineOrder.objects.select_related("course", "profile", "profile__user"),
            checkout_token=checkout_token,
        )
        provider = (request.query_params.get("provider") or order.provider).strip().lower() or order.provider
        result = (request.query_params.get("result") or "paid").strip().lower()

        if result == "cancel":
            return HttpResponseRedirect(build_mock_result_redirect_url(order=order, provider_result="cancel"))

        normalized_status = "failed" if result in {"failed", "failure"} else "paid"
        event_id = f"mock-{order.id}-{uuid4().hex[:12]}"
        event_payload = {
            "orderId": order.id,
            "checkoutToken": str(order.checkout_token),
            "status": normalized_status,
            "providerPaymentId": order.provider_payment_id or f"mockpay_{order.id}",
            "eventType": "mock_provider_redirect",
        }
        try:
            process_payment_event(
                provider=provider,
                event_id=event_id,
                payload=event_payload,
                signature_valid=True,
            )
        except ValueError:
            pass

        redirect_url = build_mock_result_redirect_url(order=order, provider_result=result)
        return HttpResponseRedirect(redirect_url)


class OnlinePaymentWebhookView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request, provider: str):
        normalized_provider = provider.strip().lower()
        if normalized_provider not in {"card", "paypal", "klarna", "sofort", "mock"}:
            return Response({"provider": "Unsupported payment provider."}, status=status.HTTP_400_BAD_REQUEST)

        if not _payment_signature_is_valid(request, provider=normalized_provider):
            return Response({"detail": "Invalid payment webhook signature."}, status=status.HTTP_403_FORBIDDEN)

        payload = request.data if isinstance(request.data, dict) else {}
        event_id = str(payload.get("eventId") or payload.get("event_id") or payload.get("id") or uuid4()).strip()
        if not event_id:
            event_id = str(uuid4())

        try:
            result = process_payment_event(
                provider=normalized_provider,
                event_id=event_id,
                payload=payload,
                signature_valid=True,
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(result, status=status.HTTP_200_OK)


class PublicFeedbackCreateView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = OnlineFeedbackCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        feedback = OnlineFeedbackMessage.objects.create(
            course=payload.get("course"),
            full_name=payload["full_name"].strip(),
            email=payload["email"].strip().lower(),
            subject=payload["subject"].strip(),
            message=payload["message"].strip(),
            preferred_language=payload["preferred_language"],
            source_page=(payload.get("source_page") or "").strip(),
        )
        email_sent = send_feedback_notification(
            sender_email=feedback.email,
            sender_name=feedback.full_name,
            subject=feedback.subject,
            message=feedback.message,
        )
        return Response(
            {"id": feedback.id, "emailSent": email_sent},
            status=status.HTTP_201_CREATED,
        )


class PublicGoogleCheckoutView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @transaction.atomic
    def post(self, request):
        serializer = GoogleCheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        google_payload, google_error = _verify_google_credential(payload["credential"])
        if google_error:
            return Response({"detail": google_error}, status=status.HTTP_400_BAD_REQUEST)

        email = google_payload["email"]
        first_name, last_name = _extract_google_names(google_payload, email)
        phone = str(payload.get("phone") or "").strip()

        try:
            user, profile, _ = _create_or_get_online_user_social(
                email=email,
                first_name=first_name,
                last_name=last_name,
                phone=phone,
                preferred_language=payload["preferred_language"],
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        mode = payload["mode"]
        course = payload["course"]
        cohort = payload["cohort"]
        idempotency_key = payload.get("idempotency_key") or None

        if mode == "trial":
            existing_order, existing_enrollment = _existing_enrollment_access_for_course(
                profile=profile,
                course=course,
                cohort=cohort,
            )
            if existing_enrollment:
                return _json_auth_response(
                    request=request,
                    user=user,
                    payload={
                        "profile": _serialize_profile(profile, request),
                        "orderId": existing_order.id if existing_order else None,
                        "enrollmentId": existing_enrollment.id,
                        "alreadyProcessed": True,
                    },
                    status_code=status.HTTP_200_OK,
                    scope=AUTH_SCOPE_STUDENT,
                )
            if idempotency_key:
                existing_order = OnlineOrder.objects.filter(
                    profile=profile,
                    idempotency_key=idempotency_key,
                    status=OnlineOrder.STATUS_TRIAL,
                ).first()
                if existing_order:
                    enrollment = OnlineEnrollment.objects.filter(order=existing_order).first()
                    return _json_auth_response(
                        request=request,
                        user=user,
                        payload={
                            "profile": _serialize_profile(profile, request),
                            "orderId": existing_order.id,
                            "enrollmentId": enrollment.id if enrollment else None,
                            "alreadyProcessed": True,
                        },
                        status_code=status.HTTP_200_OK,
                        scope=AUTH_SCOPE_STUDENT,
                    )

            if _trial_already_used(profile):
                return Response(
                    {"detail": "Free trial is already used for this account."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                _ensure_capacity_for_profile(cohort=cohort, profile=profile)
            except ValueError as exc:
                return Response({"cohort_id": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

            try:
                order = OnlineOrder.objects.create(
                    profile=profile,
                    course=course,
                    cohort=cohort,
                    provider=OnlineOrder.PROVIDER_TRIAL,
                    status=OnlineOrder.STATUS_TRIAL,
                    amount=0,
                    currency=course.currency,
                    is_trial=True,
                    paid_at=timezone.now(),
                    idempotency_key=idempotency_key,
                )
            except IntegrityError:
                return Response(
                    {"detail": "Free trial is already used for this account."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            enrollment, created = OnlineEnrollment.objects.get_or_create(
                profile=profile,
                cohort=cohort,
                defaults={
                    "course": course,
                    "order": order,
                    "status": OnlineEnrollment.STATUS_TRIAL,
                },
            )
            if not created:
                enrollment.order = order
                enrollment.status = OnlineEnrollment.STATUS_TRIAL
                enrollment.save(update_fields=["order", "status"])

            if not profile.is_trial_user:
                profile.is_trial_user = True
                profile.save(update_fields=["is_trial_user", "updated_at"])

            email_sent = send_course_access_email(profile=profile, course=course, is_trial=True)
            return _json_auth_response(
                request=request,
                user=user,
                payload={
                    "profile": _serialize_profile(profile, request),
                    "orderId": order.id,
                    "enrollmentId": enrollment.id,
                    "emailSent": email_sent,
                },
                status_code=status.HTTP_201_CREATED,
                scope=AUTH_SCOPE_STUDENT,
            )

        payment_mode = get_payment_mode()
        if idempotency_key:
            existing = OnlineOrder.objects.filter(
                profile=profile,
                idempotency_key=idempotency_key,
                is_trial=False,
            ).select_related("profile__user", "course", "cohort").first()
            if existing:
                if payment_mode == "free" and existing.status != OnlineOrder.STATUS_PAID:
                    _auto_grant_checkout_access(order=existing)
                    existing.refresh_from_db()
                response_payload = {
                    **_serialize_checkout_status(existing, request),
                    "checkoutUrl": existing.checkout_url,
                    "alreadyProcessed": True,
                }
                return _response_with_auth_payload(
                    request=request,
                    payload=response_payload,
                    status_code=status.HTTP_200_OK,
                    scope=AUTH_SCOPE_STUDENT,
                    auth_payload=_build_auth_payload(existing.profile.user)
                    if existing.status == OnlineOrder.STATUS_PAID
                    else None,
                )

        try:
            _ensure_capacity_for_profile(cohort=cohort, profile=profile)
        except ValueError as exc:
            return Response({"cohort_id": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        order = OnlineOrder.objects.create(
            profile=profile,
            course=course,
            cohort=cohort,
            provider=payload["provider"],
            status=OnlineOrder.STATUS_PENDING,
            amount=course.price_amount,
            currency=course.currency,
            is_trial=False,
            idempotency_key=idempotency_key,
        )

        if payment_mode == "free":
            auto_grant_result = _auto_grant_checkout_access(order=order)
            response_payload = {
                **_serialize_checkout_status(order, request),
                "checkoutUrl": order.checkout_url,
                "emailSent": auto_grant_result.get("emailSent", False),
            }
            return _response_with_auth_payload(
                request=request,
                payload=response_payload,
                status_code=status.HTTP_201_CREATED,
                scope=AUTH_SCOPE_STUDENT,
                auth_payload=_build_auth_payload(order.profile.user)
                if order.status == OnlineOrder.STATUS_PAID
                else None,
            )

        try:
            checkout_session = build_checkout_session(
                order=order,
                api_root_url=request.build_absolute_uri("/api/online"),
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        order.checkout_url = checkout_session.checkout_url
        order.provider_payment_id = checkout_session.provider_payment_id
        order.external_reference = checkout_session.external_reference
        order.save(update_fields=["checkout_url", "provider_payment_id", "external_reference", "updated_at"])

        return Response(
            {
                "orderId": order.id,
                "status": order.status,
                "checkoutUrl": order.checkout_url,
                "checkoutToken": str(order.checkout_token),
            },
            status=status.HTTP_201_CREATED,
        )


class PublicGoogleLoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [OnlineAuthThrottle]

    def post(self, request):
        serializer = GoogleLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        google_payload, google_error = _verify_google_credential(payload["credential"])
        if google_error:
            return Response({"detail": google_error}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.filter(email__iexact=google_payload["email"]).first()
        if not user:
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)
        if not user.is_active:
            return Response({"detail": "User account is inactive."}, status=status.HTTP_403_FORBIDDEN)
        if not hasattr(user, "online_profile"):
            return Response(
                {"detail": "User is not registered for online courses."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        profile = user.online_profile
        return _json_auth_response(
            request=request,
            user=user,
            payload={"profile": _serialize_profile(profile, request)},
            status_code=status.HTTP_200_OK,
            scope=AUTH_SCOPE_STUDENT,
        )


class PublicOnlineLoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [OnlineAuthThrottle]

    def post(self, request):
        serializer = OnlineLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        profile = user.online_profile
        return _json_auth_response(
            request=request,
            user=user,
            payload={"profile": _serialize_profile(profile, request)},
            status_code=status.HTTP_200_OK,
            scope=AUTH_SCOPE_STUDENT,
        )


class PublicOnlineStaffLoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [OnlineAuthThrottle]

    def post(self, request):
        serializer = OnlineStaffLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        return _json_auth_response(
            request=request,
            user=user,
            payload={"profile": _serialize_staff_profile(user)},
            status_code=status.HTTP_200_OK,
            scope=AUTH_SCOPE_STAFF,
        )


class OnlineCookieTokenRefreshView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [OnlineAuthThrottle]
    auth_scope = AUTH_SCOPE_STUDENT

    def post(self, request):
        try:
            _enforce_request_csrf(request)
        except serializers.ValidationError as exc:
            return Response(exc.detail, status=status.HTTP_403_FORBIDDEN)

        refresh_cookie_name = str(_auth_cookie_name(self.auth_scope, "refresh") or "").strip()
        refresh_token = str(request.data.get("refresh") or request.COOKIES.get(refresh_cookie_name) or "").strip()
        if not refresh_token:
            return Response({"detail": "Refresh token is required."}, status=status.HTTP_401_UNAUTHORIZED)

        serializer = TokenRefreshSerializer(data={"refresh": refresh_token})
        serializer.is_valid(raise_exception=True)
        response_auth = {
            "access": serializer.validated_data["access"],
            "refresh": serializer.validated_data.get("refresh") or refresh_token,
        }
        return _response_with_auth_payload(
            request=request,
            payload={"detail": "Session refreshed."},
            status_code=status.HTTP_200_OK,
            scope=self.auth_scope,
            auth_payload=response_auth,
        )


class PublicOnlineTokenRefreshView(OnlineCookieTokenRefreshView):
    auth_scope = AUTH_SCOPE_STUDENT


class OnlineStaffTokenRefreshView(OnlineCookieTokenRefreshView):
    auth_scope = AUTH_SCOPE_STAFF


class OnlineCookieLogoutView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    auth_scope = AUTH_SCOPE_STUDENT

    def post(self, request):
        try:
            _enforce_request_csrf(request)
        except serializers.ValidationError as exc:
            return Response(exc.detail, status=status.HTTP_403_FORBIDDEN)

        response = Response({"detail": "Logged out."}, status=status.HTTP_200_OK)
        return _clear_auth_cookies(response, scope=self.auth_scope)


class PublicOnlineLogoutView(OnlineCookieLogoutView):
    auth_scope = AUTH_SCOPE_STUDENT


class OnlineStaffLogoutView(OnlineCookieLogoutView):
    auth_scope = AUTH_SCOPE_STAFF


class MicrosoftSsoStartBaseView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    auth_scope = AUTH_SCOPE_STUDENT
    allowed_roles = (SSO_ROLE_STUDENT,)
    default_role = SSO_ROLE_STUDENT
    default_next_path = "/student/dashboard"
    default_login_path = "/student/login"

    def get(self, request):
        login_path = _sanitize_relative_path(request.query_params.get("login"), self.default_login_path)
        if not _microsoft_sso_is_configured():
            return HttpResponseRedirect(
                _build_frontend_redirect_path(login_path, error="Microsoft SSO is not configured."),
            )

        requested_role = str(request.query_params.get("role") or self.default_role).strip().lower()
        role = requested_role if requested_role in self.allowed_roles else self.default_role
        next_path = _sanitize_relative_path(request.query_params.get("next"), self.default_next_path)
        nonce = secrets.token_urlsafe(24)
        state = _build_sso_state(
            scope=self.auth_scope,
            role=role,
            next_path=next_path,
            login_path=login_path,
            nonce=nonce,
        )
        params = {
            "client_id": _microsoft_client_id(),
            "response_type": "code",
            "redirect_uri": _microsoft_callback_url(request, scope=self.auth_scope),
            "response_mode": "query",
            "scope": " ".join(_microsoft_scopes()),
            "state": state,
            "nonce": nonce,
            "prompt": "select_account",
        }
        return HttpResponseRedirect(f"{_microsoft_authorization_url()}?{urlencode(params)}")


class PublicMicrosoftSsoStartView(MicrosoftSsoStartBaseView):
    auth_scope = AUTH_SCOPE_STUDENT
    allowed_roles = (SSO_ROLE_STUDENT,)
    default_role = SSO_ROLE_STUDENT
    default_next_path = "/home"
    default_login_path = "/"


class OnlineStaffMicrosoftSsoStartView(MicrosoftSsoStartBaseView):
    auth_scope = AUTH_SCOPE_STAFF
    allowed_roles = (SSO_ROLE_TEACHER, SSO_ROLE_ADMIN)
    default_role = SSO_ROLE_TEACHER
    default_next_path = "/teacher/home"
    default_login_path = "/teacher/login"


class MicrosoftSsoCallbackBaseView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    auth_scope = AUTH_SCOPE_STUDENT
    allowed_roles = (SSO_ROLE_STUDENT,)
    default_next_path = "/student/dashboard"
    default_login_path = "/student/login"

    def _scope_defaults(self, state_scope: str) -> tuple[str, tuple[str, ...], str, str]:
        normalized_scope = str(state_scope or "").strip()
        if normalized_scope == AUTH_SCOPE_STAFF:
            return (
                AUTH_SCOPE_STAFF,
                (SSO_ROLE_TEACHER, SSO_ROLE_ADMIN),
                "/teacher/home",
                "/teacher/login",
            )
        return (
            AUTH_SCOPE_STUDENT,
            (SSO_ROLE_STUDENT,),
            "/home",
            "/",
        )

    def get(self, request):
        raw_state = str(request.query_params.get("state") or "").strip()
        try:
            state_payload = _load_sso_state(raw_state)
        except SignatureExpired:
            return HttpResponseRedirect(
                _build_frontend_redirect_path(self.default_login_path, error="Microsoft sign-in session expired."),
            )
        except BadSignature:
            return HttpResponseRedirect(
                _build_frontend_redirect_path(self.default_login_path, error="Microsoft sign-in session is invalid."),
            )

        state_scope = str(state_payload.get("scope") or "").strip()
        if self.auth_scope:
            effective_scope = self.auth_scope
            allowed_roles = self.allowed_roles
            default_next_path = self.default_next_path
            default_login_path = self.default_login_path
        else:
            effective_scope, allowed_roles, default_next_path, default_login_path = self._scope_defaults(state_scope)

        login_path = _sanitize_relative_path(state_payload.get("login"), default_login_path)
        next_path = _sanitize_relative_path(state_payload.get("next"), default_next_path)
        role = str(state_payload.get("role") or "").strip().lower()
        nonce = str(state_payload.get("nonce") or "").strip()

        if state_scope != effective_scope or role not in allowed_roles:
            return HttpResponseRedirect(
                _build_frontend_redirect_path(login_path, error="Microsoft sign-in request is invalid."),
            )

        provider_error = str(request.query_params.get("error_description") or request.query_params.get("error") or "").strip()
        if provider_error:
            return HttpResponseRedirect(_build_frontend_redirect_path(login_path, error=provider_error))

        code = str(request.query_params.get("code") or "").strip()
        if not code:
            return HttpResponseRedirect(
                _build_frontend_redirect_path(login_path, error="Microsoft sign-in code is missing."),
            )

        try:
            token_response = requests.post(
                _microsoft_token_url(),
                data={
                    "client_id": _microsoft_client_id(),
                    "client_secret": _microsoft_client_secret(),
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": _microsoft_callback_url(request, scope=effective_scope),
                    "scope": " ".join(_microsoft_scopes()),
                },
                timeout=10,
            )
            token_response.raise_for_status()
            token_payload = token_response.json()
        except requests.RequestException:
            return HttpResponseRedirect(
                _build_frontend_redirect_path(login_path, error="Microsoft token exchange failed."),
            )
        except ValueError:
            return HttpResponseRedirect(
                _build_frontend_redirect_path(login_path, error="Microsoft token response is invalid."),
            )

        microsoft_payload, microsoft_error = _verify_microsoft_id_token(
            str(token_payload.get("id_token") or ""),
            nonce=nonce,
        )
        if microsoft_error:
            return HttpResponseRedirect(_build_frontend_redirect_path(login_path, error=microsoft_error))

        user, user_error = _microsoft_user_lookup(role=role, payload=microsoft_payload or {})
        if user_error or not user:
            return HttpResponseRedirect(
                _build_frontend_redirect_path(login_path, error=user_error or "Microsoft sign-in failed."),
            )

        _update_microsoft_identity_link(user=user, payload=microsoft_payload or {})
        return _redirect_with_auth_cookies(
            request=request,
            redirect_url=next_path,
            user=user,
            scope=effective_scope,
        )


class PublicMicrosoftSsoCallbackView(MicrosoftSsoCallbackBaseView):
    auth_scope = AUTH_SCOPE_STUDENT
    allowed_roles = (SSO_ROLE_STUDENT,)
    default_next_path = "/home"
    default_login_path = "/"


class OnlineStaffMicrosoftSsoCallbackView(MicrosoftSsoCallbackBaseView):
    auth_scope = AUTH_SCOPE_STAFF
    allowed_roles = (SSO_ROLE_TEACHER, SSO_ROLE_ADMIN)
    default_next_path = "/teacher/home"
    default_login_path = "/teacher/login"


class MicrosoftSsoUnifiedCallbackView(MicrosoftSsoCallbackBaseView):
    auth_scope = ""
    allowed_roles = (SSO_ROLE_STUDENT, SSO_ROLE_TEACHER, SSO_ROLE_ADMIN)
    default_next_path = "/home"
    default_login_path = "/"


class OnlineStaffMeView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineStaff]

    def get(self, request):
        return Response(_serialize_staff_profile(request.user), status=status.HTTP_200_OK)


class PublicMagicLinkRequestView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [OnlineMagicLinkThrottle]

    def post(self, request):
        serializer = MagicLinkRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        profile = (
            OnlineStudentProfile.objects.select_related("user")
            .filter(user__email__iexact=payload["email"])
            .first()
        )
        generic_message = "If this email is registered, a portal link has been sent."
        if not profile:
            return Response({"detail": generic_message, "emailSent": False}, status=status.HTTP_200_OK)

        enrollments = OnlineEnrollment.objects.filter(
            profile=profile,
            status__in=_portal_enrollment_statuses(),
        )
        course = payload.get("course")
        if course:
            enrollments = enrollments.filter(course=course)
        if not enrollments.exists():
            return Response({"detail": generic_message, "emailSent": False}, status=status.HTTP_200_OK)

        token_obj, raw_token = _issue_magic_link_token(profile=profile)
        email_sent = send_magic_link_email(
            profile=profile,
            portal_link=_build_magic_link_url(raw_token),
        )
        return Response(
            {
                "detail": generic_message,
                "emailSent": email_sent,
                "expiresAt": token_obj.expires_at,
            },
            status=status.HTTP_200_OK,
        )


class PublicPortalView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        token_obj, error_response = _resolve_magic_link_token(request)
        if error_response:
            return error_response

        enrollments = list(_portal_enrollments_for_token(token_obj))
        if not enrollments:
            return Response({"detail": "No active course access for this magic link."}, status=status.HTTP_404_NOT_FOUND)

        token_obj.last_used_at = timezone.now()
        token_obj.save(update_fields=["last_used_at", "updated_at"])

        return _json_auth_response(
            request=request,
            user=token_obj.profile.user,
            payload={
                "profile": _serialize_profile(token_obj.profile, request),
                "tokenExpiresAt": token_obj.expires_at,
                "enrollments": [_serialize_portal_enrollment(item) for item in enrollments],
            },
            status_code=status.HTTP_200_OK,
            scope=AUTH_SCOPE_STUDENT,
        )


class PublicPortalSessionsView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        token_obj, error_response = _resolve_magic_link_token(request)
        if error_response:
            return error_response

        enrollments = list(_portal_enrollments_for_token(token_obj))
        if not enrollments:
            return Response({"results": []}, status=status.HTTP_200_OK)

        session_rows: list[dict[str, Any]] = []
        for enrollment in enrollments:
            attendance_map = {
                item.session_id: item
                for item in OnlineAttendance.objects.filter(enrollment=enrollment)
            }
            booking_map = {
                item.session_id: item
                for item in OnlineSessionBooking.objects.filter(enrollment=enrollment)
            }
            sessions = enrollment.cohort.sessions.order_by("starts_at")
            serialized = OnlineSessionSerializer(
                sessions,
                many=True,
                context={"attendance_map": attendance_map, "booking_map": booking_map},
            ).data
            for item in serialized:
                session_rows.append(
                    {
                        "enrollmentId": enrollment.id,
                        "courseSlug": enrollment.course.slug,
                        "courseTitleDe": enrollment.course.title_de,
                        "courseTitleEn": enrollment.course.title_en,
                        "groupCode": enrollment.cohort.group_code,
                        "groupName": enrollment.cohort.name,
                        **item,
                    }
                )

        session_rows.sort(key=lambda row: row["starts_at"])
        token_obj.last_used_at = timezone.now()
        token_obj.save(update_fields=["last_used_at", "updated_at"])
        return Response(
            {
                "results": session_rows,
                "tokenExpiresAt": token_obj.expires_at,
            },
            status=status.HTTP_200_OK,
        )


class PublicPortalCalendarIcsView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def _build_response(self, request):
        token_obj, error_response = _resolve_magic_link_token(request)
        if error_response:
            return error_response

        enrollments = list(_portal_enrollments_for_token(token_obj))
        if not enrollments:
            return Response({"detail": "No sessions available for this magic link."}, status=status.HTTP_404_NOT_FOUND)

        sessions: list[tuple[OnlineEnrollment, OnlineSession]] = []
        for enrollment in enrollments:
            for session in enrollment.cohort.sessions.order_by("starts_at"):
                sessions.append((enrollment, session))
        sessions.sort(key=lambda pair: pair[1].starts_at)

        now_stamp = _format_ics_datetime(timezone.now())
        ics_lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Kunstschule Berlin//Online Portal//EN",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
        ]
        for enrollment, session in sessions:
            summary = f"{enrollment.course.title_de} - {session.title}"
            description = (
                f"Course: {enrollment.course.title_de}\\n"
                f"Group: {enrollment.cohort.group_code}\\n"
                f"Status: {session.status}"
            )
            ics_lines.extend(
                [
                    "BEGIN:VEVENT",
                    f"UID:online-session-{session.id}@kunstschuleberlin.de",
                    f"DTSTAMP:{now_stamp}",
                    f"DTSTART:{_format_ics_datetime(session.starts_at)}",
                    f"DTEND:{_format_ics_datetime(session.ends_at)}",
                    f"SUMMARY:{_escape_ics(summary)}",
                    f"DESCRIPTION:{_escape_ics(description)}",
                    f"LOCATION:{_escape_ics('Online lesson')}",
                    f"URL:{_escape_ics(session.join_url or '')}",
                    "END:VEVENT",
                ]
            )
        ics_lines.append("END:VCALENDAR")

        response = HttpResponse(
            "\r\n".join(ics_lines) + "\r\n",
            content_type="text/calendar; charset=utf-8",
        )
        filename = f"online_sessions_{token_obj.profile_id}.ics"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        token_obj.last_used_at = timezone.now()
        token_obj.save(update_fields=["last_used_at", "updated_at"])
        return response

    def get(self, request):
        return self._build_response(request)

    def post(self, request):
        return self._build_response(request)


class OnlineStudentMeView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineStudent]

    def get(self, request):
        profile = request.user.online_profile
        return Response(_serialize_profile(profile, request), status=status.HTTP_200_OK)


class OnlineStudentAccessView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineStudent]

    def get(self, request):
        profile = request.user.online_profile
        enrollments = list(
            OnlineEnrollment.objects.filter(profile=profile)
            .select_related("course")
            .order_by("-started_at")
        )
        accessible_enrollments = [
            enrollment
            for enrollment in enrollments
            if online_object_is_accessible_to_user(enrollment.course, request.user)
        ]
        accessible_courses_count = len({enrollment.course_id for enrollment in accessible_enrollments})

        return Response(
            {
                "hasAccessibleEnrollments": bool(accessible_enrollments),
                "dashboardUrl": "/online/student/dashboard/" if accessible_enrollments else None,
                "summary": {
                    "totalEnrollments": len(enrollments),
                    "accessibleEnrollments": len(accessible_enrollments),
                    "accessibleCourses": accessible_courses_count,
                },
            },
            status=status.HTTP_200_OK,
        )


class OnlineStudentProfileUpdateView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineStudent]

    def patch(self, request):
        profile = request.user.online_profile
        serializer = OnlineStudentProfileUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        has_changes = False

        if "phone" in payload:
            phone = payload["phone"].strip()
            if profile.phone != phone:
                profile.phone = phone
                has_changes = True

        if "gender" in payload and profile.gender != payload["gender"]:
            profile.gender = payload["gender"]
            has_changes = True

        if payload.get("remove_avatar"):
            if profile.avatar:
                profile.avatar.delete(save=False)
                profile.avatar = None
                has_changes = True

        if "avatar" in payload and payload["avatar"] is not None:
            profile.avatar = payload["avatar"]
            has_changes = True

        if has_changes:
            profile.save()

        return Response(_serialize_profile(profile, request), status=status.HTTP_200_OK)


class OnlineStudentAvatarDownloadView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, profile_id: int):
        profile = get_object_or_404(OnlineStudentProfile.objects.select_related("user"), id=profile_id)
        if profile.user_id != request.user.id and not _is_online_staff_user(request.user):
            raise Http404("File not found.")
        return _authenticated_file_response(profile.avatar)


class OnlineAdminCourseLibraryFileView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    def get(self, request, item_id: int):
        item = get_object_or_404(OnlineCourseContentLibraryItem, id=item_id)
        return _authenticated_file_response(item.file_asset)


class OnlineCourseSectionItemFileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, item_id: int):
        item = get_object_or_404(
            OnlineCourseLessonSectionItem.objects.select_related(
                "section__lesson__course",
                "linked_training_content",
            ),
            id=item_id,
            is_active=True,
        )
        if not _user_can_download_section_item_file(user=request.user, item=item):
            raise Http404("File not found.")
        return _authenticated_file_response(item.file_asset)


class OnlineStudentDashboardView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineStudent]

    def get(self, request):
        profile = request.user.online_profile
        enrollments = list(
            OnlineEnrollment.objects.filter(profile=profile)
            .select_related("course", "cohort")
            .order_by("-started_at")
        )
        enrollments = [
            enrollment
            for enrollment in enrollments
            if online_object_is_accessible_to_user(enrollment.course, request.user)
        ]
        course_ids = [enrollment.course_id for enrollment in enrollments]
        materials_map = build_course_material_projection_map(course_ids, request=request)
        lessons_map = build_course_lessons_map(course_ids, request=request)
        modules_map = build_course_modules_map(course_ids, request=request)
        accessible_course_ids = set(course_ids)
        enrollments_data: list[dict[str, Any]] = []
        next_session_global = None

        for enrollment in enrollments:
            sessions = list(enrollment.cohort.sessions.all().order_by("starts_at"))
            attendance_records = {
                item.session_id: item
                for item in OnlineAttendance.objects.filter(enrollment=enrollment).select_related("session")
            }
            booking_records = {
                item.session_id: item
                for item in OnlineSessionBooking.objects.filter(enrollment=enrollment).select_related("session")
            }
            session_payload = OnlineSessionSerializer(
                sessions,
                many=True,
                context={"attendance_map": attendance_records, "booking_map": booking_records},
            ).data
            sessions_count = len(sessions)
            present_count = sum(
                1 for item in attendance_records.values() if item.status == OnlineAttendance.STATUS_PRESENT
            )
            attendance_percent = round((present_count / sessions_count) * 100, 2) if sessions_count > 0 else 0.0
            next_session = next((s for s in sessions if s.starts_at >= timezone.now()), None)
            if next_session and (not next_session_global or next_session.starts_at < next_session_global.starts_at):
                next_session_global = next_session

            materials = materials_map.get(enrollment.course_id, [])
            lesson_plan = deepcopy(lessons_map.get(enrollment.course_id, []))
            course_modules = deepcopy(modules_map.get(enrollment.course_id, []))
            annotate_lessons_payload_with_sessions(
                lesson_plan,
                sessions,
                group_code=enrollment.cohort.group_code,
                group_name=enrollment.cohort.name,
            )
            annotate_modules_payload_with_sessions(
                course_modules,
                sessions,
                group_code=enrollment.cohort.group_code,
                group_name=enrollment.cohort.name,
            )
            progress_map = lesson_progress_map_for_enrollment(
                enrollment,
                lesson_ids=[int(item.get("id")) for item in lesson_plan if item.get("id")],
            )
            annotate_lessons_payload_with_progress(lesson_plan, progress_map=progress_map)
            annotate_modules_payload_with_progress(course_modules, progress_map=progress_map)
            issue_completion_evidence_if_eligible(enrollment)
            completion_summary = build_enrollment_completion_summary(
                enrollment,
                lessons_payload=lesson_plan,
                progress_map=progress_map,
            )
            final_assessment = next(
                (
                    module_payload
                    for module_payload in course_modules
                    if module_payload.get("moduleType") == OnlineCourseModule.MODULE_TYPE_FINAL
                ),
                None,
            )

            enrollments_data.append(
                {
                    "enrollmentId": enrollment.id,
                    "status": enrollment.status,
                    "course": {
                        "slug": enrollment.course.slug,
                        "titleDe": enrollment.course.title_de,
                        "titleEn": enrollment.course.title_en,
                        "audienceIds": online_access_policy_audience_ids_for_instance(enrollment.course),
                        "audiences": online_access_policy_audiences_payload_for_instance(enrollment.course),
                        "lessonsCount": enrollment.course.lessons_count,
                    },
                    "cohort": {
                        "id": enrollment.cohort.id,
                        "groupCode": enrollment.cohort.group_code,
                        "groupName": enrollment.cohort.name,
                    },
                    "attendancePercent": attendance_percent,
                    "nextSessionAt": next_session.starts_at if next_session else None,
                    "sessions": session_payload,
                    "materials": materials,
                    "lessonPlan": lesson_plan,
                    "completion": completion_summary,
                    "courseStructure": {
                        "modules": course_modules,
                        "finalAssessment": final_assessment,
                    },
                }
            )

        unread_support = profile.support_messages.filter(is_read=False).count()
        visible_learning_content = visible_content_items_for_user(
            request.user,
            base_queryset=base_content_queryset()
            .filter(status=TrainingContentItem.Status.PUBLISHED)
            .filter(Q(course__isnull=True) | Q(course_id__in=accessible_course_ids))
            .distinct(),
        )
        return Response(
            {
                "profile": _serialize_profile(profile, request),
                "nextSessionAt": next_session_global.starts_at if next_session_global else None,
                "unreadSupportMessages": unread_support,
                "enrollments": enrollments_data,
                "learningContent": TrainingContentListSerializer(visible_learning_content, many=True).data,
            },
            status=status.HTTP_200_OK,
        )


class OnlineStudentLessonDetailView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineStudent]

    def get(self, request, lesson_id: int):
        context = _student_lesson_context_or_404(request=request, lesson_id=lesson_id)
        enrollment = context["enrollment"]
        module_payload = context["modulePayload"]
        lesson_payload = context["lessonPayload"]
        completion_summary = context["completionSummary"]

        return Response(
            {
                "enrollmentId": enrollment.id,
                "course": {
                    "slug": enrollment.course.slug,
                    "titleDe": enrollment.course.title_de,
                    "titleEn": enrollment.course.title_en,
                    "audienceIds": online_access_policy_audience_ids_for_instance(enrollment.course),
                    "audiences": online_access_policy_audiences_payload_for_instance(enrollment.course),
                },
                "cohort": {
                    "id": enrollment.cohort.id,
                    "groupCode": enrollment.cohort.group_code,
                    "groupName": enrollment.cohort.name,
                },
                "module": {
                    "id": module_payload.get("id"),
                    "title": module_payload.get("title") or "",
                    "moduleType": module_payload.get("moduleType") or "",
                    "weekNumber": module_payload.get("weekNumber"),
                },
                "lesson": lesson_payload,
                "completion": completion_summary,
            },
            status=status.HTTP_200_OK,
        )


class OnlineStudentLessonProgressView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineStudent]

    @transaction.atomic
    def post(self, request, lesson_id: int):
        serializer = OnlineStudentLessonProgressSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        context = _student_lesson_context_or_404(request=request, lesson_id=lesson_id)
        enrollment = context["enrollment"]
        lesson_obj = context["lessonObject"]
        lesson_payload = context["lessonPayload"]
        progress, _snapshot, allowed_step_ids = upsert_lesson_progress(
            enrollment=enrollment,
            lesson=lesson_obj,
            lesson_payload=lesson_payload,
            active_step_id=serializer.validated_data.get("activeStepId", ""),
            completed_step_ids=serializer.validated_data.get("completedStepIds", []),
        )

        issue_completion_evidence_if_eligible(enrollment)
        completion_summary = build_enrollment_completion_summary(enrollment)
        return Response(
            {
                "progress": lesson_progress_payload(progress, total_steps=len(allowed_step_ids)),
                "completion": completion_summary,
            },
            status=status.HTTP_200_OK,
        )


class OnlineStudentEnrollmentAttestationView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineStudent]

    @transaction.atomic
    def post(self, request, enrollment_id: int):
        serializer = OnlineStudentCourseAttestationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        enrollment = get_object_or_404(
            OnlineEnrollment.objects.select_related("course", "cohort", "profile__user"),
            id=enrollment_id,
            profile=request.user.online_profile,
        )
        if not online_object_is_accessible_to_user(enrollment.course, request.user):
            return Response({"detail": "Course is not accessible for your current role."}, status=status.HTTP_403_FORBIDDEN)

        completion_summary = build_enrollment_completion_summary(enrollment)
        if not completion_summary["ruleReady"]:
            return Response(
                {"detail": "Completion requirements are not met yet."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        attestation = OnlineEnrollmentAttestation.objects.create(
            enrollment=enrollment,
            full_name=serializer.validated_data["fullName"],
            attestation_text=default_attestation_text(enrollment.course),
            ip_address=_request_ip_address(request),
        )
        issue_completion_evidence_if_eligible(enrollment)
        completion_summary = build_enrollment_completion_summary(enrollment)
        return Response(
            {
                "attestation": completion_summary["attestation"],
                "evidence": completion_summary["evidence"],
                "completion": completion_summary,
            },
            status=status.HTTP_201_CREATED,
        )


class OnlineStudentLessonAiAskView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineStudent]

    def post(self, request, lesson_id: int):
        if not training_ai_enabled():
            return Response({"detail": "AI assistant is disabled."}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        serializer = OnlineStudentLessonAiAskSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        context = _student_lesson_context_or_404(request=request, lesson_id=lesson_id)
        lesson_payload = context["lessonPayload"]
        interactive_lesson = lesson_payload.get("interactiveLesson") or {}
        question = serializer.validated_data["question"]
        step_id = serializer.validated_data.get("stepId", "")
        prompt_type = serializer.validated_data.get("promptType", "ask") or "ask"
        code = serializer.validated_data.get("code", "")
        context_chunks = _lesson_ai_context_chunks(lesson_payload=lesson_payload, step_id=step_id, code=code)
        if not context_chunks:
            return Response(
                {"detail": "This lesson does not expose enough structured context for AI assistance yet."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        provider = get_training_ai_provider()
        try:
            answer = provider.generate_answer(
                content_name=str(interactive_lesson.get("lessonTitle") or lesson_payload.get("title") or "Lesson").strip(),
                question=question,
                prompt_type=prompt_type,
                context_chunks=context_chunks,
            )
        except TrainingAiProviderError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        composed_answer = str(answer.detailed_answer or answer.short_answer or "").strip()
        return Response(
            {
                "answer": composed_answer or "AI assistant could not generate an answer for this lesson yet.",
                "followUpPrompts": answer.follow_up_prompts,
                "provider": provider.provider_name,
                "model": provider.model_name,
                "resolutionStatus": answer.resolution_status,
            },
            status=status.HTTP_200_OK,
        )


class OnlineStudentLessonGraderCheckView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineStudent]

    def post(self, request, lesson_id: int):
        serializer = OnlineStudentLessonGraderCheckSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        context = _student_lesson_context_or_404(request=request, lesson_id=lesson_id)
        lesson_payload = context["lessonPayload"]
        interactive_lesson = lesson_payload.get("interactiveLesson") or {}
        steps = interactive_lesson.get("steps") or []
        step_id = serializer.validated_data["stepId"]
        code = serializer.validated_data["code"]
        step = next((item for item in steps if str(item.get("id") or "") == str(step_id)), None)
        if step is None:
            return Response(
                {
                    "status": "error",
                    "message": "Step not found in lesson.",
                    "checks": [
                        {
                            "name": "Step lookup",
                            "passed": False,
                            "expected": "existing step",
                            "actual": step_id,
                        }
                    ],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        grader_config = step.get("grader")
        if not grader_config:
            return Response(
                {
                    "status": "error",
                    "message": "No grader configured for this step.",
                    "checks": [
                        {
                            "name": "Grader config",
                            "passed": False,
                            "expected": "step.grader",
                            "actual": "missing",
                        }
                    ],
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        result = grade_lesson_code(code=code, grader_config=grader_config)
        return Response(
            {
                "status": result.status,
                "message": result.message,
                "checks": [
                    {
                        "name": check.name,
                        "passed": check.passed,
                        "expected": check.expected,
                        "actual": check.actual,
                    }
                    for check in result.checks
                ],
            },
            status=status.HTTP_200_OK,
        )


class OnlineStudentSessionsView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineStudent]

    def get(self, request):
        profile = request.user.online_profile
        session_rows = []
        enrollments = OnlineEnrollment.objects.filter(profile=profile).select_related("cohort", "course")
        for enrollment in enrollments:
            attendance_map = {
                item.session_id: item
                for item in OnlineAttendance.objects.filter(enrollment=enrollment)
            }
            sessions = enrollment.cohort.sessions.order_by("starts_at")
            booking_map = {
                item.session_id: item
                for item in OnlineSessionBooking.objects.filter(enrollment=enrollment)
            }
            serialized = OnlineSessionSerializer(
                sessions,
                many=True,
                context={"attendance_map": attendance_map, "booking_map": booking_map},
            ).data
            for item in serialized:
                session_rows.append(
                    {
                        **item,
                        "courseSlug": enrollment.course.slug,
                        "courseTitleDe": enrollment.course.title_de,
                        "courseTitleEn": enrollment.course.title_en,
                        "groupCode": enrollment.cohort.group_code,
                        "groupName": enrollment.cohort.name,
                    }
                )

        session_rows.sort(key=lambda row: row["starts_at"])
        return Response({"results": session_rows}, status=status.HTTP_200_OK)


class OnlineStudentSessionJoinView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineStudent]

    def post(self, request, session_id: int):
        session = get_object_or_404(OnlineSession.objects.select_related("cohort"), id=session_id)
        if session.status == OnlineSession.STATUS_CANCELED:
            return Response({"detail": "Session is canceled."}, status=status.HTTP_400_BAD_REQUEST)
        if session.status == OnlineSession.STATUS_ENDED or session.is_completed:
            return Response({"detail": "Session is already completed."}, status=status.HTTP_400_BAD_REQUEST)

        profile = request.user.online_profile
        try:
            attendance = mark_student_join_for_session(profile=profile, session=session)
        except ValueError:
            return Response(
                {"detail": "Current student is not enrolled in this session cohort."},
                status=status.HTTP_403_FORBIDDEN,
            )

        return Response(
            {
                "sessionId": session.id,
                "attendanceStatus": attendance.status,
                "joinedAt": attendance.joined_at,
                "joinUrl": session.join_url,
            },
            status=status.HTTP_200_OK,
        )


class OnlineStudentSessionBookingView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineStudent]

    def post(self, request, session_id: int):
        session = get_object_or_404(OnlineSession.objects.select_related("cohort"), id=session_id)
        if session.status == OnlineSession.STATUS_CANCELED:
            return Response({"detail": "Session is canceled."}, status=status.HTTP_400_BAD_REQUEST)
        if session.status == OnlineSession.STATUS_ENDED or session.is_completed:
            return Response({"detail": "Session is already completed."}, status=status.HTTP_400_BAD_REQUEST)

        profile = request.user.online_profile
        enrollment = OnlineEnrollment.objects.filter(
            profile=profile,
            cohort=session.cohort,
            status__in=ONLINE_DASHBOARD_ENROLLMENT_STATUSES,
        ).first()
        if enrollment is None:
            return Response(
                {"detail": "Current student is not enrolled in this session cohort."},
                status=status.HTTP_403_FORBIDDEN,
            )

        booking, created = OnlineSessionBooking.objects.get_or_create(
            enrollment=enrollment,
            session=session,
            defaults={"status": OnlineSessionBooking.STATUS_BOOKED},
        )
        if not created and booking.status != OnlineSessionBooking.STATUS_BOOKED:
            booking.status = OnlineSessionBooking.STATUS_BOOKED
            booking.canceled_at = None
            booking.save(update_fields=["status", "canceled_at", "updated_at"])

        return Response(
            {
                "sessionId": session.id,
                "bookingStatus": booking.status,
                "bookedAt": booking.booked_at,
                "canceledAt": booking.canceled_at,
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request, session_id: int):
        session = get_object_or_404(OnlineSession.objects.select_related("cohort"), id=session_id)
        profile = request.user.online_profile
        enrollment = OnlineEnrollment.objects.filter(profile=profile, cohort=session.cohort).first()
        if enrollment is None:
            return Response(
                {"detail": "Current student is not enrolled in this session cohort."},
                status=status.HTTP_403_FORBIDDEN,
            )

        booking = OnlineSessionBooking.objects.filter(enrollment=enrollment, session=session).first()
        if booking is None:
            return Response({"detail": "No booking exists for this session."}, status=status.HTTP_404_NOT_FOUND)

        if booking.status != OnlineSessionBooking.STATUS_CANCELED:
            booking.status = OnlineSessionBooking.STATUS_CANCELED
            booking.canceled_at = timezone.now()
            booking.save(update_fields=["status", "canceled_at", "updated_at"])

        return Response(
            {
                "sessionId": session.id,
                "bookingStatus": booking.status,
                "bookedAt": booking.booked_at,
                "canceledAt": booking.canceled_at,
            },
            status=status.HTTP_200_OK,
        )


class OnlineStudentSupportMessagesView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineStudent]

    def get(self, request):
        profile = request.user.online_profile
        messages = profile.support_messages.all().order_by("-created_at")[:200]
        serializer = OnlineSupportMessageSerializer(messages, many=True)
        return Response({"results": serializer.data}, status=status.HTTP_200_OK)

    def post(self, request):
        profile = request.user.online_profile
        serializer = OnlineSupportMessageCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        enrollment = None
        enrollment_id = payload.get("enrollment_id")
        if enrollment_id:
            enrollment = OnlineEnrollment.objects.filter(id=enrollment_id, profile=profile).first()
            if not enrollment:
                return Response(
                    {"enrollment_id": "Enrollment not found for this profile."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        message = OnlineSupportMessage.objects.create(
            profile=profile,
            enrollment=enrollment,
            sender_type=OnlineSupportMessage.SENDER_STUDENT,
            message=payload["message"],
            is_read=False,
        )
        return Response(
            OnlineSupportMessageSerializer(message).data,
            status=status.HTTP_201_CREATED,
        )


class OnlineAdminWorkspaceListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    def get(self, request):
        serializer = OnlineAdminWorkspaceSerializer(_workspace_admin_queryset(), many=True)
        return Response({"results": serializer.data}, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = OnlineAdminWorkspaceUpsertSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        audience_ids = serializer.validated_data.pop("audienceIds", [])
        workspace = serializer.save()
        sync_online_access_policies_for_instance(instance=workspace, audience_ids=audience_ids)
        response_serializer = OnlineAdminWorkspaceSerializer(
            _workspace_admin_queryset().get(id=workspace.id)
        )
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class OnlineAdminWorkspaceDetailView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    def get_object(self, workspace_id: int) -> OnlineWorkspace:
        return get_object_or_404(_workspace_admin_queryset(), id=workspace_id)

    def get(self, request, workspace_id: int):
        serializer = OnlineAdminWorkspaceSerializer(self.get_object(workspace_id))
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request, workspace_id: int):
        workspace = self.get_object(workspace_id)
        serializer = OnlineAdminWorkspaceUpsertSerializer(workspace, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        audience_ids = serializer.validated_data.pop("audienceIds", None)
        workspace = serializer.save()
        if audience_ids is not None:
            sync_online_access_policies_for_instance(instance=workspace, audience_ids=audience_ids)
        response_serializer = OnlineAdminWorkspaceSerializer(
            _workspace_admin_queryset().get(id=workspace.id)
        )
        return Response(response_serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, workspace_id: int):
        workspace = self.get_object(workspace_id)
        workspace.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class OnlineAdminWorkspaceItemListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    def get_workspace(self, workspace_id: int) -> OnlineWorkspace:
        return get_object_or_404(OnlineWorkspace, id=workspace_id)

    def get(self, request, workspace_id: int):
        workspace = self.get_workspace(workspace_id)
        section = (request.query_params.get("section") or "").strip()
        queryset = workspace.content_items.select_related("linked_course", "linked_cohort").all().order_by(
            "section",
            "sort_order",
            "id",
        )
        if section:
            queryset = queryset.filter(section=section)
        serializer = OnlineAdminWorkspaceContentItemSerializer(queryset, many=True)
        return Response({"results": serializer.data}, status=status.HTTP_200_OK)

    def post(self, request, workspace_id: int):
        workspace = self.get_workspace(workspace_id)
        serializer = OnlineAdminWorkspaceContentItemUpsertSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        audience_ids = serializer.validated_data.pop("audienceIds", [])
        item = serializer.save(workspace=workspace)
        sync_online_access_policies_for_instance(instance=item, audience_ids=audience_ids)
        response_serializer = OnlineAdminWorkspaceContentItemSerializer(
            OnlineWorkspaceContentItem.objects.select_related("linked_course", "linked_cohort").get(id=item.id)
        )
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


class OnlineAdminWorkspaceItemDetailView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    def get_object(self, item_id: int) -> OnlineWorkspaceContentItem:
        return get_object_or_404(
            OnlineWorkspaceContentItem.objects.select_related("linked_course", "linked_cohort"),
            id=item_id,
        )

    def patch(self, request, item_id: int):
        item = self.get_object(item_id)
        serializer = OnlineAdminWorkspaceContentItemUpsertSerializer(item, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        audience_ids = serializer.validated_data.pop("audienceIds", None)
        item = serializer.save()
        if audience_ids is not None:
            sync_online_access_policies_for_instance(instance=item, audience_ids=audience_ids)
        response_serializer = OnlineAdminWorkspaceContentItemSerializer(
            OnlineWorkspaceContentItem.objects.select_related("linked_course", "linked_cohort").get(id=item.id)
        )
        return Response(response_serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, item_id: int):
        item = self.get_object(item_id)
        item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class OnlineAdminCourseListView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    def get(self, request):
        query = (request.query_params.get("q") or "").strip()
        qs = OnlineCourse.objects.all().order_by("id")
        if query:
            qs = qs.filter(
                Q(slug__icontains=query)
                | Q(title_de__icontains=query)
                | Q(title_en__icontains=query)
                | Q(short_description_de__icontains=query)
                | Q(short_description_en__icontains=query)
                | Q(knowledge_domain__icontains=query)
                | Q(target_audience__icontains=query)
                | Q(provider_course_id__icontains=query)
                | Q(external_url__icontains=query)
                | Q(cohorts__name__icontains=query)
                | Q(cohorts__group_code__icontains=query)
                | Q(cohorts__teacher__Vorname__icontains=query)
                | Q(cohorts__teacher__Nachname__icontains=query)
            ).distinct()
        courses = list(qs)
        structure_summary_map = build_course_structure_summary_map([item.id for item in courses], request=request)
        payload = []
        for item in courses:
            card = course_card_payload(item)
            card["structureSummary"] = structure_summary_map.get(item.id, card.get("structureSummary"))
            payload.append(card)
        return Response({"results": payload}, status=status.HTTP_200_OK)


class OnlineAdminCourseDetailView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    def get(self, request, course_id: int):
        course = get_object_or_404(OnlineCourse, id=course_id)
        return Response(course_detail_payload(course), status=status.HTTP_200_OK)


class OnlineAdminCourseTemplateListView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    def get(self, request):
        if not OnlineCourseTemplate.objects.filter(is_active=True).exists():
            ensure_default_course_templates()
        queryset = OnlineCourseTemplate.objects.filter(is_active=True).order_by("sort_order", "id")
        payload = OnlineAdminCourseTemplateSerializer(queryset, many=True).data
        return Response({"results": payload}, status=status.HTTP_200_OK)


class OnlineAdminNotebookOptionListView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    def get(self, request):
        query = (request.query_params.get("q") or "").strip()
        course_id = (request.query_params.get("course_id") or "").strip()
        queryset = TrainingContentItem.objects.filter(content_kind=TrainingContentItem.ContentKind.NOTEBOOK).order_by(
            "name",
            "id",
        )
        if query:
            queryset = queryset.filter(
                Q(name__icontains=query) | Q(slug__icontains=query) | Q(description__icontains=query)
            )
        if course_id.isdigit():
            queryset = queryset.filter(Q(course_id=int(course_id)) | Q(course__isnull=True))
        payload = OnlineAdminNotebookOptionSerializer(queryset, many=True).data
        return Response({"results": payload}, status=status.HTTP_200_OK)


class OnlineAdminCourseLibraryListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    def get(self, request):
        query = (request.query_params.get("q") or "").strip()
        section_type = (request.query_params.get("section_type") or "").strip()
        asset_type = (request.query_params.get("asset_type") or "").strip()
        queryset = OnlineCourseContentLibraryItem.objects.select_related("training_content").order_by(
            "section_type",
            "sort_order",
            "id",
        )
        if query:
            queryset = queryset.filter(
                Q(title__icontains=query)
                | Q(description__icontains=query)
                | Q(library_group__icontains=query)
                | Q(training_content__name__icontains=query)
            )
        if section_type:
            queryset = queryset.filter(section_type=section_type)
        if asset_type:
            queryset = queryset.filter(asset_type=asset_type)
        serializer = OnlineAdminCourseContentLibraryItemSerializer(queryset, many=True, context={"request": request})
        return Response({"results": serializer.data}, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = OnlineAdminCourseContentLibraryItemUpsertSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        audience_ids = serializer.validated_data.pop("audienceIds", [])
        item = serializer.save()
        sync_online_access_policies_for_instance(instance=item, audience_ids=audience_ids)
        payload = OnlineAdminCourseContentLibraryItemSerializer(item, context={"request": request}).data
        return Response(payload, status=status.HTTP_201_CREATED)


class OnlineAdminCourseLibraryDetailView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    def patch(self, request, item_id: int):
        item = get_object_or_404(OnlineCourseContentLibraryItem, id=item_id)
        serializer = OnlineAdminCourseContentLibraryItemUpsertSerializer(instance=item, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        audience_ids = serializer.validated_data.pop("audienceIds", None)
        item = serializer.save()
        if audience_ids is not None:
            sync_online_access_policies_for_instance(instance=item, audience_ids=audience_ids)
        payload = OnlineAdminCourseContentLibraryItemSerializer(item, context={"request": request}).data
        return Response(payload, status=status.HTTP_200_OK)

    def delete(self, request, item_id: int):
        item = get_object_or_404(OnlineCourseContentLibraryItem, id=item_id)
        item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class OnlineAdminCourseBuilderCreateView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    @transaction.atomic
    def post(self, request):
        serializer = OnlineAdminCourseBuilderUpsertSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data
        audience_ids = validated.pop("audienceIds", [])
        instructor_ids = validated.pop("instructorIds", [])
        workspace_ids = validated.pop("workspaceIds", [])
        modules = validated.pop("modules", None)
        lessons = validated.pop("lessons", None)
        validated.pop("template", None)
        requested_lifecycle_status = validated.pop("lifecycle_status", OnlineCourse.LIFECYCLE_PUBLISHED)
        validated.pop("is_published", None)
        lesson_count = 0
        if modules:
            lesson_count = sum(len(module_row.get("lessons") or []) for module_row in modules)
        elif lessons:
            lesson_count = len(lessons)
        course = OnlineCourse.objects.create(
            **validated,
            lessons_count=max(1, lesson_count or 1),
            lifecycle_status=OnlineCourse.LIFECYCLE_DRAFT,
            is_published=False,
        )
        upsert_course_structure(course, lessons, modules_data=modules)
        sync_online_access_policies_for_instance(instance=course, audience_ids=audience_ids)
        sync_course_instructor_assignments(course=course, teacher_ids=instructor_ids)
        sync_course_workspace_placements(course=course, workspace_ids=workspace_ids)
        try:
            apply_course_lifecycle_status(
                course,
                to_status=requested_lifecycle_status,
                actor=request.user,
                request=request,
                metadata={"source": "course_builder.create"},
            )
        except CourseLifecycleValidationError as exc:
            transaction.set_rollback(True)
            return Response(
                {
                    "detail": exc.detail,
                    "releaseReadiness": exc.readiness,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        create_course_version_snapshot(
            course,
            actor=request.user,
            source="course_builder.create",
            change_summary=f"Initial course snapshot ({course.lifecycle_status.replace('_', ' ')})",
        )
        log_online_audit_event(
            event_type="course.created",
            summary=f"Created course {course.title_en or course.slug}",
            actor=request.user,
            request=request,
            course=course,
            instance=course,
            metadata={
                "slug": course.slug,
                "lifecycleStatus": course.lifecycle_status,
                "requestedLifecycleStatus": requested_lifecycle_status,
                "lessonCount": course.lessons_count,
                "audienceIds": audience_ids,
                "instructorIds": instructor_ids,
                "workspaceIds": workspace_ids,
            },
        )
        payload = OnlineAdminCourseBuilderDetailSerializer(course, context={"request": request}).data
        return Response(payload, status=status.HTTP_201_CREATED)


def _next_available_course_slug(base_slug: str) -> str:
    candidate = base_slug.strip().lower()[:120] or "imported-course"
    if not OnlineCourse.objects.filter(slug=candidate).exists():
        return candidate
    suffix = 2
    while True:
        next_candidate = f"{candidate[:110]}-{suffix}"
        if not OnlineCourse.objects.filter(slug=next_candidate).exists():
            return next_candidate
        suffix += 1


def _next_available_cohort_group_code(base_group_code: str) -> str:
    normalized = slugify(str(base_group_code or "").strip()).replace("-", "_").upper()[:80] or "IMPORTED_COURSE"
    if not OnlineCohort.objects.filter(group_code=normalized).exists():
        return normalized
    suffix = 2
    while True:
        suffix_text = f"_{suffix}"
        next_candidate = f"{normalized[: 80 - len(suffix_text)]}{suffix_text}"
        if not OnlineCohort.objects.filter(group_code=next_candidate).exists():
            return next_candidate
        suffix += 1


def _list_from_payload(*payloads: dict[str, Any], keys: tuple[str, ...]) -> list[Any]:
    for payload in payloads:
        for key in keys:
            value = payload.get(key)
            if isinstance(value, list):
                return value
    return []


def _resolve_audience_ids_from_import_payload(*, payload: dict[str, Any], course_payload: dict[str, Any]) -> list[int]:
    raw_ids = _list_from_payload(payload, course_payload, keys=("audienceIds", "audience_ids"))
    audience_ids = [
        int(value)
        for value in raw_ids
        if isinstance(value, int) or (isinstance(value, str) and value.strip().isdigit())
    ]
    raw_slugs = _list_from_payload(payload, course_payload, keys=("audienceSlugs", "audience_slugs"))
    audience_slugs = [str(value).strip() for value in raw_slugs if str(value or "").strip()]
    if audience_slugs:
        slug_ids = list(
            TrainingAudience.objects.filter(slug__in=audience_slugs, is_active=True).values_list("id", flat=True)
        )
        audience_ids.extend(slug_ids)
    return list(dict.fromkeys(audience_ids))


def _resolve_workspace_ids_from_import_payload(*, payload: dict[str, Any], course_payload: dict[str, Any]) -> list[int]:
    raw_ids = _list_from_payload(payload, course_payload, keys=("workspaceIds", "workspace_ids"))
    workspace_ids = [
        int(value)
        for value in raw_ids
        if isinstance(value, int) or (isinstance(value, str) and value.strip().isdigit())
    ]
    raw_slugs = _list_from_payload(payload, course_payload, keys=("workspaceSlugs", "workspace_slugs"))
    workspace_slugs = [str(value).strip() for value in raw_slugs if str(value or "").strip()]
    if workspace_slugs:
        slug_ids = list(
            OnlineWorkspace.objects.filter(slug__in=workspace_slugs, is_published=True).values_list("id", flat=True)
        )
        workspace_ids.extend(slug_ids)
    return list(dict.fromkeys(workspace_ids))


def _parse_import_cohort_date(value: Any):
    if not value:
        return None
    if hasattr(value, "isoformat"):
        return value
    return parse_date(str(value).strip())


def _create_import_demo_cohort(*, course: OnlineCourse, payload: dict[str, Any], course_payload: dict[str, Any]) -> OnlineCohort | None:
    raw_cohort = payload.get("demoCohort") or payload.get("demo_cohort") or course_payload.get("demoCohort") or course_payload.get("demo_cohort")
    if raw_cohort is False or raw_cohort is None:
        return None
    cohort_payload = raw_cohort if isinstance(raw_cohort, dict) else {}
    today = timezone.localdate()
    status_value = str(cohort_payload.get("status") or OnlineCohort.STATUS_OPEN).strip()
    valid_statuses = {choice[0] for choice in OnlineCohort.STATUS_CHOICES}
    if status_value not in valid_statuses:
        status_value = OnlineCohort.STATUS_OPEN
    group_code = _next_available_cohort_group_code(
        str(cohort_payload.get("groupCode") or cohort_payload.get("group_code") or f"{course.slug}-demo")
    )
    start_date = _parse_import_cohort_date(cohort_payload.get("startDate") or cohort_payload.get("start_date")) or today
    end_date = (
        _parse_import_cohort_date(cohort_payload.get("endDate") or cohort_payload.get("end_date"))
        or start_date + timedelta(days=28)
    )
    return OnlineCohort.objects.create(
        course=course,
        teacher=None,
        name=str(cohort_payload.get("name") or f"{course.title_en or course.title_de} Demo Cohort").strip()[:220],
        group_code=group_code,
        capacity=int(cohort_payload.get("capacity") or 40),
        timezone=str(cohort_payload.get("timezone") or "Europe/Berlin").strip()[:64],
        start_date=start_date,
        end_date=end_date,
        status=status_value,
        is_public=bool(cohort_payload.get("isPublic", cohort_payload.get("is_public", True))),
    )


class OnlineAdminCourseBuilderLessonGenerateView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    def post(self, request):
        serializer = OnlineAdminCourseBuilderLessonGenerateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = generate_course_builder_lesson_document(
            lesson_title=serializer.validated_data["title"],
            lesson_description=serializer.validated_data.get("description", ""),
            source_text=serializer.validated_data["sourceText"],
            language=serializer.validated_data.get("language", OnlineCourse.LOCALE_EN),
            course_title=serializer.validated_data.get("courseTitle", ""),
            module_title=serializer.validated_data.get("moduleTitle", ""),
            video_url=serializer.validated_data.get("videoUrl", ""),
            video_description=serializer.validated_data.get("videoDescription", ""),
        )
        return Response(result, status=status.HTTP_200_OK)


class OnlineAdminCourseBuilderLessonGenerateFromVideoView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        serializer = OnlineAdminCourseBuilderLessonGenerateFromVideoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = generate_course_builder_lesson_from_video(
                lesson_title=serializer.validated_data["title"],
                lesson_description=serializer.validated_data.get("description", ""),
                video_file=serializer.validated_data["videoFile"],
                language=serializer.validated_data.get("language", OnlineCourse.LOCALE_EN),
                course_title=serializer.validated_data.get("courseTitle", ""),
                module_title=serializer.validated_data.get("moduleTitle", ""),
                video_url=serializer.validated_data.get("videoUrl", ""),
                video_description=serializer.validated_data.get("videoDescription", ""),
            )
        except VideoLessonGenerationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "document": result.document,
                "meta": result.meta,
                "transcriptText": result.transcript_text,
            },
            status=status.HTTP_200_OK,
        )


class OnlineAdminCourseBuilderImportView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    @transaction.atomic
    def post(self, request):
        serializer = OnlineAdminCourseBuilderImportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data

        payload = validated["payload"]
        modules = build_modules_from_import_payload(payload)
        if not modules:
            return Response(
                {"payload": "No modules found in payload. Expected modules[]."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        course_payload = payload.get("course") if isinstance(payload.get("course"), dict) else {}
        title_en = (
            validated.get("titleEn")
            or course_payload.get("title_en")
            or course_payload.get("title")
            or payload.get("title")
            or "Imported course"
        )
        title_de = (
            validated.get("titleDe")
            or course_payload.get("title_de")
            or validated.get("titleEn")
            or title_en
        )
        source_slug = (
            validated.get("slug")
            or course_payload.get("slug")
            or slugify(str(title_en))
            or "imported-course"
        )
        slug = _next_available_course_slug(source_slug)

        short_description_en = (
            validated.get("shortDescriptionEn")
            or course_payload.get("short_description_en")
            or payload.get("shortDescription")
            or payload.get("description")
            or "Imported course outline."
        )
        short_description_de = (
            validated.get("shortDescriptionDe")
            or course_payload.get("short_description_de")
            or short_description_en
        )
        description_en = (
            validated.get("descriptionEn")
            or course_payload.get("description_en")
            or payload.get("description")
            or "Imported from external learning source."
        )
        description_de = (
            validated.get("descriptionDe")
            or course_payload.get("description_de")
            or description_en
        )
        starts_at = (
            validated.get("startsAt")
            or course_payload.get("starts_at")
            or course_payload.get("startsAt")
        )
        ends_at = (
            validated.get("endsAt")
            or course_payload.get("ends_at")
            or course_payload.get("endsAt")
        )

        try:
            price_amount = Decimal(str(validated.get("priceAmount", "0.00")))
        except (InvalidOperation, TypeError):
            return Response({"priceAmount": "Invalid decimal value."}, status=status.HTTP_400_BAD_REQUEST)
        if price_amount < 0:
            return Response({"priceAmount": "Price cannot be negative."}, status=status.HTTP_400_BAD_REQUEST)

        course = OnlineCourse.objects.create(
            slug=slug,
            title_de=title_de,
            title_en=title_en,
            short_description_de=short_description_de,
            short_description_en=short_description_en,
            description_de=description_de,
            description_en=description_en,
            starts_at=starts_at,
            ends_at=ends_at,
            lessons_count=max(1, sum(len(module_row.get("lessons") or []) for module_row in modules)),
            trial_available=validated.get("trialAvailable", False),
            price_amount=price_amount,
            currency=validated.get("currency", "EUR"),
            is_subscription=validated.get("isSubscription", False),
            is_published=False,
            lifecycle_status=OnlineCourse.LIFECYCLE_DRAFT,
            required_completion_percent=validated.get("requiredCompletionPercent", 100),
            required_attendance_percent=validated.get("requiredAttendancePercent", 0),
            requires_attestation=validated.get("requiresAttestation", True),
            hero_image_url=validated.get("heroImageUrl") or "",
            geo_city=validated.get("geoCity") or "Berlin",
            geo_country=validated.get("geoCountry") or "DE",
        )
        upsert_course_structure(course, None, modules_data=modules)

        audience_ids = (
            validated.get("audienceIds")
            or _resolve_audience_ids_from_import_payload(payload=payload, course_payload=course_payload)
            or []
        )
        sync_online_access_policies_for_instance(instance=course, audience_ids=audience_ids)
        sync_course_instructor_assignments(course=course, teacher_ids=validated.get("instructorIds") or [])
        demo_cohort = _create_import_demo_cohort(course=course, payload=payload, course_payload=course_payload)
        workspace_ids = (
            validated.get("workspaceIds")
            or _resolve_workspace_ids_from_import_payload(payload=payload, course_payload=course_payload)
            or []
        )
        sync_course_workspace_placements(course=course, workspace_ids=workspace_ids, linked_cohort=demo_cohort)
        requested_lifecycle_status = validated.get("lifecycleStatus", OnlineCourse.LIFECYCLE_PUBLISHED)
        try:
            apply_course_lifecycle_status(
                course,
                to_status=requested_lifecycle_status,
                actor=request.user,
                request=request,
                metadata={"source": "course_builder.import"},
            )
        except CourseLifecycleValidationError as exc:
            transaction.set_rollback(True)
            return Response(
                {
                    "detail": exc.detail,
                    "releaseReadiness": exc.readiness,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        create_course_version_snapshot(
            course,
            actor=request.user,
            source="course_builder.import",
            change_summary=f"Imported course snapshot ({course.lifecycle_status.replace('_', ' ')})",
        )
        log_online_audit_event(
            event_type="course.imported",
            summary=f"Imported course {course.title_en or course.slug}",
            actor=request.user,
            request=request,
            course=course,
            instance=course,
            metadata={
                "slug": course.slug,
                "source": validated.get("source", "generic_json"),
                "lifecycleStatus": course.lifecycle_status,
                "requestedLifecycleStatus": requested_lifecycle_status,
                "lessonCount": course.lessons_count,
            },
        )
        response_payload = OnlineAdminCourseBuilderDetailSerializer(course, context={"request": request}).data
        return Response(response_payload, status=status.HTTP_201_CREATED)


class OnlineAdminCourseBuilderDetailView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    def get(self, request, course_id: int):
        course = get_object_or_404(OnlineCourse, id=course_id)
        payload = OnlineAdminCourseBuilderDetailSerializer(course, context={"request": request}).data
        return Response(payload, status=status.HTTP_200_OK)

    @transaction.atomic
    def patch(self, request, course_id: int):
        course = get_object_or_404(OnlineCourse, id=course_id)
        serializer = OnlineAdminCourseBuilderUpsertSerializer(instance=course, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data
        audience_ids = validated.pop("audienceIds", None)
        instructor_ids = validated.pop("instructorIds", None)
        workspace_ids = validated.pop("workspaceIds", None)
        modules = validated.pop("modules", None)
        lessons = validated.pop("lessons", None)
        validated.pop("template", None)
        lifecycle_status = validated.pop("lifecycle_status", None)
        validated.pop("is_published", None)
        changed_fields = []

        for field, value in validated.items():
            if getattr(course, field) != value:
                changed_fields.append(field)
            setattr(course, field, value)
        if changed_fields:
            course.save()
        if audience_ids is not None:
            sync_online_access_policies_for_instance(instance=course, audience_ids=audience_ids)
        if instructor_ids is not None:
            sync_course_instructor_assignments(course=course, teacher_ids=instructor_ids)
        if workspace_ids is not None:
            sync_course_workspace_placements(course=course, workspace_ids=workspace_ids)
        if modules is not None or lessons is not None:
            upsert_course_structure(course, lessons, modules_data=modules)
        lifecycle_changed = False
        if lifecycle_status is not None:
            try:
                lifecycle_changed = apply_course_lifecycle_status(
                    course,
                    to_status=lifecycle_status,
                    actor=request.user,
                    request=request,
                    metadata={"source": "course_builder.patch"},
                )
            except CourseLifecycleValidationError as exc:
                transaction.set_rollback(True)
                return Response(
                    {
                        "detail": exc.detail,
                        "releaseReadiness": exc.readiness,
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )
        if changed_fields or audience_ids is not None or instructor_ids is not None or workspace_ids is not None or modules is not None or lessons is not None or lifecycle_changed:
            change_parts = []
            if changed_fields:
                change_parts.append(f"Fields: {', '.join(changed_fields)}")
            if modules is not None or lessons is not None:
                change_parts.append("Structure updated")
            if audience_ids is not None:
                change_parts.append("Audience sync")
            if instructor_ids is not None:
                change_parts.append("Instructor sync")
            if workspace_ids is not None:
                change_parts.append("Workspace sync")
            if lifecycle_changed:
                change_parts.append(f"Lifecycle -> {course.lifecycle_status}")
            create_course_version_snapshot(
                course,
                actor=request.user,
                source="course_builder.patch",
                change_summary="; ".join(change_parts) or "Course updated",
            )
            log_online_audit_event(
                event_type="course.updated",
                summary=f"Updated course {course.title_en or course.slug}",
                actor=request.user,
                request=request,
                course=course,
                instance=course,
                metadata={
                    "changedFields": changed_fields,
                    "lifecycleStatus": course.lifecycle_status,
                    "syncedAudiences": audience_ids is not None,
                    "syncedInstructors": instructor_ids is not None,
                    "syncedWorkspaces": workspace_ids is not None,
                    "updatedStructure": modules is not None or lessons is not None,
                },
            )
        payload = OnlineAdminCourseBuilderDetailSerializer(course, context={"request": request}).data
        return Response(payload, status=status.HTTP_200_OK)


class OnlineAdminCourseBuilderDeliveryView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    @transaction.atomic
    def post(self, request, course_id: int):
        course = get_object_or_404(OnlineCourse, id=course_id)
        serializer = OnlineAdminCourseBuilderDeliverySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data

        cohort_id = validated.get("cohortId")
        curator_id = validated.get("curatorId")
        created = False

        teacher = None
        if curator_id is not None:
            teacher = get_object_or_404(Lehrer.objects.select_related("user"), id=curator_id)
            if not teacher.user.is_active:
                return Response({"detail": "Curator user account is inactive."}, status=status.HTTP_400_BAD_REQUEST)

        if cohort_id is not None:
            cohort = get_object_or_404(OnlineCohort.objects.select_related("course", "teacher"), id=cohort_id, course=course)
        else:
            group_code = validated["groupCode"]
            if OnlineCohort.objects.filter(group_code__iexact=group_code).exists():
                return Response({"groupCode": "A cohort with this group code already exists."}, status=status.HTTP_400_BAD_REQUEST)
            cohort = OnlineCohort(course=course)
            created = True

        if validated.get("groupCode"):
            cohort.group_code = validated["groupCode"]
        if validated.get("groupName"):
            cohort.name = validated["groupName"]
        if "capacity" in validated:
            cohort.capacity = validated["capacity"]
        if "timezone" in validated:
            cohort.timezone = validated["timezone"]
        if "startDate" in validated:
            cohort.start_date = validated.get("startDate")
        if "endDate" in validated:
            cohort.end_date = validated.get("endDate")
        if "status" in validated:
            cohort.status = validated["status"]
        if "isPublic" in validated:
            cohort.is_public = validated["isPublic"]
        cohort.teacher = teacher

        try:
            cohort.save()
        except IntegrityError:
            return Response({"detail": "Failed to save cohort because of a uniqueness conflict."}, status=status.HTTP_400_BAD_REQUEST)

        cohort.refresh_from_db()
        curator_payload = None
        if teacher:
            teacher = Lehrer.objects.select_related("user").prefetch_related(
                Prefetch("online_cohorts", queryset=OnlineCohort.objects.select_related("course", "teacher").order_by("start_date", "id"))
            ).get(id=teacher.id)
            curator_payload = _serialize_admin_curator(teacher)

        return Response(
            {
                "created": created,
                "courseId": course.id,
                "courseSlug": course.slug,
                "cohort": cohort_card_payload(cohort),
                "curator": curator_payload,
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class OnlineAdminCourseBuilderSessionsView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    @transaction.atomic
    def post(self, request, course_id: int):
        course = get_object_or_404(OnlineCourse, id=course_id)
        serializer = OnlineAdminCourseBuilderSessionSeedSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data

        cohort = get_object_or_404(
            OnlineCohort.objects.select_related("course", "teacher"),
            id=validated["cohortId"],
            course=course,
        )

        session_inputs = [
            BuilderSessionSeedInput(
                title=(item.get("title") or "").strip(),
                description=(item.get("description") or "").strip(),
                starts_at=item["startsAt"],
                ends_at=item["endsAt"],
            )
            for item in validated["sessions"]
        ]

        try:
            result = create_builder_sessions_for_cohort(cohort=cohort, sessions=session_inputs)
        except SessionGenerationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        cohort.refresh_from_db()
        return Response(
            {
                "courseId": course.id,
                "courseSlug": course.slug,
                "cohort": cohort_card_payload(cohort),
                "createdCount": result.created_count,
                "remainingSlots": result.remaining_slots,
                "sessions": _serialize_admin_session_rows(result.created_sessions),
            },
            status=status.HTTP_201_CREATED,
        )


class OnlineAdminCohortListView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    def get(self, request):
        query = (request.query_params.get("q") or "").strip()
        course_id = (request.query_params.get("course_id") or "").strip()
        qs = OnlineCohort.objects.select_related("course", "teacher").order_by("start_date", "id")
        if query:
            qs = qs.filter(
                Q(name__icontains=query)
                | Q(group_code__icontains=query)
                | Q(course__title_de__icontains=query)
                | Q(course__title_en__icontains=query)
                | Q(teacher__Vorname__icontains=query)
                | Q(teacher__Nachname__icontains=query)
            )
        if course_id.isdigit():
            qs = qs.filter(course_id=int(course_id))
        return Response({"results": [cohort_card_payload(item) for item in qs]}, status=status.HTTP_200_OK)


class OnlineAdminOrderListView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    def get(self, request):
        query = (request.query_params.get("q") or "").strip()
        status_filter = (request.query_params.get("status") or "").strip()
        provider_filter = (request.query_params.get("provider") or "").strip()
        cohort_id = (request.query_params.get("cohort_id") or "").strip()

        queryset = (
            OnlineOrder.objects.select_related("profile__user", "course", "cohort")
            .annotate(payment_events_count=Count("payment_events"))
            .order_by("-created_at")
        )
        if query:
            queryset = queryset.filter(
                Q(profile__user__email__icontains=query)
                | Q(course__slug__icontains=query)
                | Q(cohort__group_code__icontains=query)
                | Q(provider_payment_id__icontains=query)
                | Q(external_reference__icontains=query)
            )
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if provider_filter:
            queryset = queryset.filter(provider=provider_filter)
        if cohort_id.isdigit():
            queryset = queryset.filter(cohort_id=int(cohort_id))

        return Response(
            {
                "results": [
                    {
                        "id": item.id,
                        "studentEmail": item.profile.user.email,
                        "courseSlug": item.course.slug,
                        "groupCode": item.cohort.group_code,
                        "provider": item.provider,
                        "status": item.status,
                        "amount": item.amount,
                        "currency": item.currency,
                        "isTrial": item.is_trial,
                        "paidAt": item.paid_at,
                        "refundedAt": item.refunded_at,
                        "createdAt": item.created_at,
                        "paymentEventsCount": item.payment_events_count,
                    }
                    for item in queryset
                ]
            },
            status=status.HTTP_200_OK,
        )


class OnlineAdminOrderDetailView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    def get(self, request, order_id: int):
        order = get_object_or_404(
            OnlineOrder.objects.select_related("profile__user", "course", "cohort"),
            id=order_id,
        )
        events = order.payment_events.order_by("-processed_at")
        enrollments = order.enrollments.select_related("profile__user", "course", "cohort").order_by("id")

        return Response(
            {
                "id": order.id,
                "studentEmail": order.profile.user.email,
                "courseSlug": order.course.slug,
                "groupCode": order.cohort.group_code,
                "provider": order.provider,
                "status": order.status,
                "amount": order.amount,
                "currency": order.currency,
                "isTrial": order.is_trial,
                "paidAt": order.paid_at,
                "refundedAt": order.refunded_at,
                "providerPaymentId": order.provider_payment_id,
                "paidEventId": order.paid_event_id,
                "failureReason": order.payment_failure_reason,
                "checkoutToken": str(order.checkout_token),
                "checkoutUrl": order.checkout_url,
                "createdAt": order.created_at,
                "updatedAt": order.updated_at,
                "paymentEvents": [
                    {
                        "id": event.id,
                        "provider": event.provider,
                        "eventId": event.event_id,
                        "eventType": event.event_type,
                        "status": event.status,
                        "providerPaymentId": event.provider_payment_id,
                        "signatureValid": event.signature_valid,
                        "processedAt": event.processed_at,
                    }
                    for event in events
                ],
                "enrollments": [
                    {
                        "id": enrollment.id,
                        "studentEmail": enrollment.profile.user.email,
                        "courseSlug": enrollment.course.slug,
                        "groupCode": enrollment.cohort.group_code,
                        "status": enrollment.status,
                        "startedAt": enrollment.started_at,
                        "completedAt": enrollment.completed_at,
                    }
                    for enrollment in enrollments
                ],
            },
            status=status.HTTP_200_OK,
        )


class OnlineAdminCohortDetailView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    def get(self, request, cohort_id: int):
        cohort = get_object_or_404(
            OnlineCohort.objects.select_related("course", "teacher"),
            id=cohort_id,
        )
        enrollments = list(
            cohort.enrollments.filter(
                status__in=ONLINE_DASHBOARD_ENROLLMENT_STATUSES
            )
            .select_related("profile__user")
            .order_by("profile__last_name", "profile__first_name")
        )
        sessions = list(cohort.sessions.order_by("starts_at"))
        nearest_session = nearest_session_for_cohort(cohort)
        attendance_rows = OnlineAttendance.objects.filter(
            enrollment__in=enrollments,
            session__in=sessions,
        )

        attendance_map: dict[tuple[int, int], OnlineAttendance] = {
            (row.enrollment_id, row.session_id): row for row in attendance_rows
        }
        session_attendance_counter: dict[int, dict[str, int]] = defaultdict(
            lambda: {"present": 0, "absent": 0, "excused": 0, "unknown": 0}
        )
        for row in attendance_rows:
            if row.status in session_attendance_counter[row.session_id]:
                session_attendance_counter[row.session_id][row.status] += 1
            else:
                session_attendance_counter[row.session_id]["unknown"] += 1

        student_payload = []
        for enrollment in enrollments:
            present_count = 0
            for session in sessions:
                record = attendance_map.get((enrollment.id, session.id))
                if record and record.status == OnlineAttendance.STATUS_PRESENT:
                    present_count += 1
            attendance_percent = round((present_count / len(sessions)) * 100, 2) if sessions else 0.0
            student_payload.append(
                {
                    "enrollmentId": enrollment.id,
                    "fullName": f"{enrollment.profile.first_name} {enrollment.profile.last_name}".strip(),
                    "email": enrollment.profile.user.email,
                    "status": enrollment.status,
                    "attendancePercent": attendance_percent,
                }
            )

        sessions_payload = []
        students_total = len(student_payload)
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
                    "startsAt": session.starts_at,
                    "endsAt": session.ends_at,
                    "status": session.status,
                    "isCompleted": session.is_completed,
                    "joinUrl": session.join_url,
                    "attendanceSummary": summary,
                }
            )
        completed_sessions = sum(1 for session in sessions if session.is_completed)

        return Response(
            {
                "id": cohort.id,
                "teacherId": cohort.teacher_id,
                "groupCode": cohort.group_code,
                "groupName": cohort.name,
                "courseSlug": cohort.course.slug,
                "courseTitleDe": cohort.course.title_de,
                "courseTitleEn": cohort.course.title_en,
                "teacherName": format_teacher_name(cohort),
                "studentsCount": len(student_payload),
                "attendancePercent": compute_cohort_attendance_percent(cohort),
                "nearestSessionAt": nearest_session.starts_at if nearest_session else None,
                "sessionsSummary": {
                    "total": len(sessions),
                    "completed": completed_sessions,
                    "planned": len(sessions) - completed_sessions,
                },
                "sessions": sessions_payload,
                "students": student_payload,
            },
            status=status.HTTP_200_OK,
        )


class OnlineAdminSessionListView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    def get(self, request):
        serializer = OnlineAdminSessionListQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        queryset = OnlineSession.objects.select_related("cohort", "cohort__course", "cohort__teacher").order_by(
            "starts_at",
            "id",
        )
        query = (payload.get("q") or "").strip()
        if query:
            queryset = queryset.filter(
                Q(title__icontains=query)
                | Q(description__icontains=query)
                | Q(join_url__icontains=query)
                | Q(recording_url__icontains=query)
                | Q(cohort__group_code__icontains=query)
                | Q(cohort__name__icontains=query)
                | Q(cohort__course__slug__icontains=query)
                | Q(cohort__course__title_de__icontains=query)
                | Q(cohort__course__title_en__icontains=query)
                | Q(cohort__teacher__Vorname__icontains=query)
                | Q(cohort__teacher__Nachname__icontains=query)
            )
        if payload.get("course_id"):
            queryset = queryset.filter(cohort__course_id=payload["course_id"])
        if payload.get("cohort_id"):
            queryset = queryset.filter(cohort_id=payload["cohort_id"])
        if payload.get("teacher_id"):
            queryset = queryset.filter(cohort__teacher_id=payload["teacher_id"])
        if payload.get("status"):
            queryset = queryset.filter(status=payload["status"])
        if payload.get("starts_from"):
            queryset = queryset.filter(starts_at__gte=payload["starts_from"])
        if payload.get("starts_to"):
            queryset = queryset.filter(starts_at__lte=payload["starts_to"])
        if "attendance_synced" in payload:
            if payload["attendance_synced"]:
                queryset = queryset.exclude(attendance_synced_at__isnull=True)
            else:
                queryset = queryset.filter(attendance_synced_at__isnull=True)
        if "has_join_url" in payload:
            if payload["has_join_url"]:
                queryset = queryset.exclude(join_url__isnull=True).exclude(join_url="")
            else:
                queryset = queryset.filter(Q(join_url__isnull=True) | Q(join_url=""))
        if "has_recording" in payload:
            if payload["has_recording"]:
                queryset = queryset.exclude(recording_url__isnull=True).exclude(recording_url="")
            else:
                queryset = queryset.filter(Q(recording_url__isnull=True) | Q(recording_url=""))

        return Response({"results": _serialize_admin_session_rows(queryset)}, status=status.HTTP_200_OK)


class OnlineAdminSessionBulkActionView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    def post(self, request):
        serializer = OnlineAdminSessionBulkActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        action = serializer.validated_data["action"]
        session_ids = serializer.validated_data["sessionIds"]

        sessions = list(
            OnlineSession.objects.select_related("cohort", "cohort__course", "cohort__teacher").filter(id__in=session_ids)
        )
        session_map = {session.id: session for session in sessions}
        missing_ids = [session_id for session_id in session_ids if session_id not in session_map]
        if missing_ids:
            return Response(
                {"sessionIds": [f"Unknown session ids: {', '.join(str(item) for item in missing_ids)}"]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        results: list[dict[str, Any]] = []
        succeeded_count = 0
        failed_count = 0
        for session_id in session_ids:
            session = session_map[session_id]
            try:
                payload = _run_admin_session_action(session=session, action=action)
                results.append(
                    {
                        "sessionId": session.id,
                        "action": action,
                        "ok": True,
                        "error": None,
                        "session": payload,
                    }
                )
                succeeded_count += 1
            except SessionLifecycleError as exc:
                results.append(
                    {
                        "sessionId": session.id,
                        "action": action,
                        "ok": False,
                        "error": str(exc),
                        "session": None,
                    }
                )
                failed_count += 1

        return Response(
            {
                "action": action,
                "processedCount": len(session_ids),
                "succeededCount": succeeded_count,
                "failedCount": failed_count,
                "results": results,
            },
            status=status.HTTP_200_OK,
        )


class OnlineAdminUserListView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    def get(self, request):
        query = (request.query_params.get("q") or "").strip()
        role = (request.query_params.get("role") or "").strip().lower()

        queryset = (
            User.objects.select_related("lehrer_user", "online_profile")
            .annotate(
                assigned_cohorts_count=Count("lehrer_user__online_cohorts", distinct=True),
                assigned_courses_count=Count("lehrer_user__online_cohorts__course", distinct=True),
            )
            .order_by("email")
        )
        if query:
            queryset = queryset.filter(
                Q(email__icontains=query)
                | Q(username__icontains=query)
                | Q(first_name__icontains=query)
                | Q(last_name__icontains=query)
                | Q(lehrer_user__Vorname__icontains=query)
                | Q(lehrer_user__Nachname__icontains=query)
                | Q(lehrer_user__Schule_Email__icontains=query)
                | Q(lehrer_user__KurzName__icontains=query)
            ).distinct()

        if role == "curator":
            queryset = queryset.filter(lehrer_user__isnull=False)
        elif role == "admin":
            queryset = queryset.filter(Q(is_admin=True) | Q(is_superuser=True))
        elif role == "student":
            queryset = queryset.filter(online_profile__isnull=False)

        return Response(
            {"results": [_serialize_admin_user(user) for user in queryset[:150]]},
            status=status.HTTP_200_OK,
        )


class OnlineAdminCuratorOnboardingView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    def post(self, request):
        serializer = OnlineAdminCuratorOnboardingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        if User.objects.filter(email__iexact=payload["email"]).exists():
            return Response({"email": "A user with this email already exists."}, status=status.HTTP_400_BAD_REQUEST)

        uniqueness_errors = _validate_curator_uniqueness(
            school_email=payload["schoolEmail"],
            short_name=payload["shortName"],
        )
        if uniqueness_errors:
            return Response(uniqueness_errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                user = User.objects.create_user(
                    email=payload["email"],
                    username=_make_unique_username(payload["email"]),
                    password=payload["temporaryPassword"],
                    first_name=payload["firstName"],
                    last_name=payload["lastName"],
                    is_active=True,
                )
                teacher = Lehrer.objects.create(
                    user=user,
                    Vorname=payload["firstName"],
                    Nachname=payload["lastName"],
                    Schule_Email=payload["schoolEmail"],
                    Private_Email=payload.get("privateEmail", ""),
                    Telefonnummer=payload.get("phone", ""),
                    KurzName=payload["shortName"],
                )
                OnlineInstructorProfile.objects.get_or_create(teacher=teacher)
        except IntegrityError:
            return Response(
                {"detail": "Failed to create curator account because of a uniqueness conflict."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        teacher = Lehrer.objects.select_related("user").prefetch_related(
            Prefetch(
                "online_cohorts",
                queryset=OnlineCohort.objects.select_related("course", "teacher").order_by("start_date", "id"),
            )
        ).get(id=teacher.id)
        return Response(_serialize_admin_curator(teacher), status=status.HTTP_201_CREATED)


def _admin_user_lifecycle_error(*, acting_user: User, target_user: User) -> Response | None:
    if target_user.id == acting_user.id:
        return Response(
            {"detail": "You cannot manage your own account from this panel."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if target_user.is_admin or target_user.is_superuser:
        return Response(
            {"detail": "Admin accounts cannot be managed from this panel."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return None


class OnlineAdminCuratorListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    def get(self, request):
        query = (request.query_params.get("q") or "").strip()
        cohorts_queryset = OnlineCohort.objects.select_related("course", "teacher").order_by("start_date", "id")
        queryset = Lehrer.objects.select_related("user").prefetch_related(
            Prefetch("online_cohorts", queryset=cohorts_queryset)
        ).order_by("Nachname", "Vorname", "id")
        if query:
            queryset = queryset.filter(
                Q(user__email__icontains=query)
                | Q(user__username__icontains=query)
                | Q(Vorname__icontains=query)
                | Q(Nachname__icontains=query)
                | Q(Schule_Email__icontains=query)
                | Q(KurzName__icontains=query)
            )

        return Response(
            {"results": [_serialize_admin_curator(teacher) for teacher in queryset]},
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        serializer = OnlineAdminCuratorCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        user = get_object_or_404(User, id=payload["userId"])
        if not user.is_active:
            return Response({"detail": "User account is inactive."}, status=status.HTTP_400_BAD_REQUEST)
        if hasattr(user, "lehrer_user"):
            return Response({"detail": "Curator profile already exists for this user."}, status=status.HTTP_400_BAD_REQUEST)

        uniqueness_errors = _validate_curator_uniqueness(
            school_email=payload["schoolEmail"],
            short_name=payload["shortName"],
        )
        if uniqueness_errors:
            return Response(uniqueness_errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                teacher = Lehrer.objects.create(
                    user=user,
                    Vorname=payload["firstName"],
                    Nachname=payload["lastName"],
                    Schule_Email=payload["schoolEmail"],
                    Private_Email=payload.get("privateEmail", ""),
                    Telefonnummer=payload.get("phone", ""),
                    KurzName=payload["shortName"],
                )
                OnlineInstructorProfile.objects.get_or_create(teacher=teacher)

                user_updates: list[str] = []
                if user.first_name != payload["firstName"]:
                    user.first_name = payload["firstName"]
                    user_updates.append("first_name")
                if user.last_name != payload["lastName"]:
                    user.last_name = payload["lastName"]
                    user_updates.append("last_name")
                if user_updates:
                    user.save(update_fields=user_updates)
        except IntegrityError:
            return Response(
                {"detail": "Failed to create curator profile because of a uniqueness conflict."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        teacher = Lehrer.objects.select_related("user").prefetch_related(
            Prefetch("online_cohorts", queryset=OnlineCohort.objects.select_related("course", "teacher").order_by("start_date", "id"))
        ).get(id=teacher.id)
        return Response(_serialize_admin_curator(teacher), status=status.HTTP_201_CREATED)


class OnlineAdminCuratorDetailView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    def patch(self, request, curator_id: int):
        teacher = get_object_or_404(
            Lehrer.objects.select_related("user").prefetch_related(
                Prefetch("online_cohorts", queryset=OnlineCohort.objects.select_related("course", "teacher").order_by("start_date", "id"))
            ),
            id=curator_id,
        )
        serializer = OnlineAdminCuratorUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        if not payload:
            return Response(_serialize_admin_curator(teacher), status=status.HTTP_200_OK)

        school_email = payload.get("schoolEmail", teacher.Schule_Email)
        short_name = payload.get("shortName", teacher.KurzName)
        uniqueness_errors = _validate_curator_uniqueness(
            school_email=school_email,
            short_name=short_name,
            exclude_teacher_id=teacher.id,
        )
        if uniqueness_errors:
            return Response(uniqueness_errors, status=status.HTTP_400_BAD_REQUEST)

        updated_teacher_fields: list[str] = []
        updated_user_fields: list[str] = []

        if "firstName" in payload and teacher.Vorname != payload["firstName"]:
            teacher.Vorname = payload["firstName"]
            updated_teacher_fields.append("Vorname")
            if teacher.user.first_name != payload["firstName"]:
                teacher.user.first_name = payload["firstName"]
                updated_user_fields.append("first_name")
        if "lastName" in payload and teacher.Nachname != payload["lastName"]:
            teacher.Nachname = payload["lastName"]
            updated_teacher_fields.append("Nachname")
            if teacher.user.last_name != payload["lastName"]:
                teacher.user.last_name = payload["lastName"]
                updated_user_fields.append("last_name")
        if "schoolEmail" in payload and teacher.Schule_Email != payload["schoolEmail"]:
            teacher.Schule_Email = payload["schoolEmail"]
            updated_teacher_fields.append("Schule_Email")
        if "privateEmail" in payload and teacher.Private_Email != payload["privateEmail"]:
            teacher.Private_Email = payload["privateEmail"]
            updated_teacher_fields.append("Private_Email")
        if "phone" in payload and (teacher.Telefonnummer or "") != payload["phone"]:
            teacher.Telefonnummer = payload["phone"]
            updated_teacher_fields.append("Telefonnummer")
        if "shortName" in payload and teacher.KurzName != payload["shortName"]:
            teacher.KurzName = payload["shortName"]
            updated_teacher_fields.append("KurzName")

        try:
            with transaction.atomic():
                if updated_teacher_fields:
                    teacher.save(update_fields=updated_teacher_fields)
                if updated_user_fields:
                    teacher.user.save(update_fields=updated_user_fields)
        except IntegrityError:
            return Response(
                {"detail": "Failed to update curator profile because of a uniqueness conflict."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        teacher.refresh_from_db()
        teacher = Lehrer.objects.select_related("user").prefetch_related(
            Prefetch("online_cohorts", queryset=OnlineCohort.objects.select_related("course", "teacher").order_by("start_date", "id"))
        ).get(id=teacher.id)
        return Response(_serialize_admin_curator(teacher), status=status.HTTP_200_OK)

    def delete(self, request, curator_id: int):
        teacher = get_object_or_404(Lehrer.objects.select_related("user"), id=curator_id)
        if teacher.online_cohorts.exists():
            return Response(
                {"detail": "Curator cannot be removed while cohorts are assigned. Unassign cohorts first."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        teacher.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class OnlineAdminUserStatusView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    def patch(self, request, user_id: int):
        target_user = get_object_or_404(User, id=user_id)
        blocked_response = _admin_user_lifecycle_error(acting_user=request.user, target_user=target_user)
        if blocked_response:
            return blocked_response

        serializer = OnlineAdminUserStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        next_is_active = serializer.validated_data["isActive"]
        if target_user.is_active != next_is_active:
            target_user.is_active = next_is_active
            target_user.save(update_fields=["is_active"])

        refreshed_user = (
            User.objects.select_related("lehrer_user", "online_profile")
            .annotate(
                assigned_cohorts_count=Count("lehrer_user__online_cohorts", distinct=True),
                assigned_courses_count=Count("lehrer_user__online_cohorts__course", distinct=True),
            )
            .get(id=target_user.id)
        )
        return Response(_serialize_admin_user(refreshed_user), status=status.HTTP_200_OK)


class OnlineAdminUserTemporaryPasswordView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    def post(self, request, user_id: int):
        target_user = get_object_or_404(User, id=user_id)
        blocked_response = _admin_user_lifecycle_error(acting_user=request.user, target_user=target_user)
        if blocked_response:
            return blocked_response

        serializer = OnlineAdminUserTemporaryPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        target_user.set_password(serializer.validated_data["temporaryPassword"])
        target_user.save(update_fields=["password"])

        refreshed_user = (
            User.objects.select_related("lehrer_user", "online_profile")
            .annotate(
                assigned_cohorts_count=Count("lehrer_user__online_cohorts", distinct=True),
                assigned_courses_count=Count("lehrer_user__online_cohorts__course", distinct=True),
            )
            .get(id=target_user.id)
        )
        return Response(_serialize_admin_user(refreshed_user), status=status.HTTP_200_OK)


class OnlineAdminScopeAssignmentListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    def get(self, request):
        role = (request.query_params.get("role") or "").strip()
        scope_type = (request.query_params.get("scope_type") or "").strip()
        user_id_raw = (request.query_params.get("user_id") or "").strip()
        course_id_raw = (request.query_params.get("course_id") or "").strip()
        active_only = (request.query_params.get("active_only") or "").strip().lower() in {"1", "true", "yes"}
        user_id = int(user_id_raw) if user_id_raw.isdigit() else None
        course_id = int(course_id_raw) if course_id_raw.isdigit() else None
        queryset = scope_assignments_queryset(
            course_id=course_id,
            user_id=user_id,
            role=role,
            scope_type=scope_type,
            active_only=active_only,
        )
        return Response(
            {"results": [scope_assignment_payload(item) for item in queryset[:200]]},
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        serializer = OnlineAdminScopeAssignmentWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        user = payload["user"]
        if not user.is_active:
            return Response({"detail": "Inactive users cannot receive scoped access."}, status=status.HTTP_400_BAD_REQUEST)

        assignment = OnlineScopeAssignment.objects.filter(
            user=user,
            role=payload["role"],
            scope_key=payload["scopeKey"],
        ).first()
        if assignment is not None:
            return Response({"detail": "This scoped assignment already exists."}, status=status.HTTP_400_BAD_REQUEST)

        assignment = OnlineScopeAssignment.objects.create(
            user=user,
            role=payload["role"],
            scope_type=payload["scopeType"],
            scope_key=payload["scopeKey"],
            course=payload.get("course"),
            cohort=payload.get("cohort"),
            note=payload.get("note", ""),
            is_primary=payload.get("isPrimary", False),
            is_active=payload.get("isActive", True),
            created_by=request.user,
        )
        log_online_audit_event(
            event_type="scope_assignment.created",
            summary=f"Created {assignment.role} scope assignment for {user.email}",
            actor=request.user,
            request=request,
            course=assignment.course or (assignment.cohort.course if assignment.cohort_id else None),
            instance=assignment,
            metadata={
                "assignmentId": assignment.id,
                "userId": assignment.user_id,
                "role": assignment.role,
                "scopeType": assignment.scope_type,
                "scopeKey": assignment.scope_key,
            },
        )
        return Response(scope_assignment_payload(assignment), status=status.HTTP_201_CREATED)


class OnlineAdminScopeAssignmentDetailView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    def patch(self, request, assignment_id: int):
        assignment = get_object_or_404(
            OnlineScopeAssignment.objects.select_related("course", "cohort", "cohort__course", "user", "created_by"),
            id=assignment_id,
        )
        updated_fields: list[str] = []
        if "note" in request.data and assignment.note != str(request.data.get("note") or "")[:255]:
            assignment.note = str(request.data.get("note") or "")[:255]
            updated_fields.append("note")
        if "isPrimary" in request.data:
            next_primary = bool(request.data.get("isPrimary"))
            if assignment.is_primary != next_primary:
                assignment.is_primary = next_primary
                updated_fields.append("is_primary")
        if "isActive" in request.data:
            next_active = bool(request.data.get("isActive"))
            if assignment.is_active != next_active:
                assignment.is_active = next_active
                updated_fields.append("is_active")

        if updated_fields:
            assignment.save(update_fields=[*updated_fields, "updated_at"])
            log_online_audit_event(
                event_type="scope_assignment.updated",
                summary=f"Updated scoped assignment #{assignment.id}",
                actor=request.user,
                request=request,
                course=assignment.course or (assignment.cohort.course if assignment.cohort_id else None),
                instance=assignment,
                metadata={
                    "assignmentId": assignment.id,
                    "updatedFields": updated_fields,
                },
            )
        return Response(scope_assignment_payload(assignment), status=status.HTTP_200_OK)

    def delete(self, request, assignment_id: int):
        assignment = get_object_or_404(
            OnlineScopeAssignment.objects.select_related("course", "cohort", "cohort__course", "user"),
            id=assignment_id,
        )
        course = assignment.course or (assignment.cohort.course if assignment.cohort_id else None)
        metadata = {
            "assignmentId": assignment.id,
            "userId": assignment.user_id,
            "role": assignment.role,
            "scopeType": assignment.scope_type,
            "scopeKey": assignment.scope_key,
        }
        assignment.delete()
        log_online_audit_event(
            event_type="scope_assignment.deleted",
            summary=f"Deleted scoped assignment #{assignment_id}",
            actor=request.user,
            request=request,
            course=course,
            metadata=metadata,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class OnlineAdminEnterpriseSummaryView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    def get(self, request):
        course_id_raw = (request.query_params.get("course_id") or "").strip()
        course_id = int(course_id_raw) if course_id_raw.isdigit() else None
        if course_id is not None:
            get_object_or_404(OnlineCourse, id=course_id)
        payload = build_enterprise_reporting_summary(course_id=course_id)
        return Response(payload, status=status.HTTP_200_OK)


class OnlineAdminCohortCuratorAssignmentView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    def patch(self, request, cohort_id: int):
        cohort = get_object_or_404(
            OnlineCohort.objects.select_related("course", "teacher"),
            id=cohort_id,
        )
        serializer = OnlineAdminCohortCuratorAssignmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        curator_id = serializer.validated_data.get("curatorId", None)

        teacher = None
        if curator_id is not None:
            teacher = get_object_or_404(Lehrer.objects.select_related("user"), id=curator_id)
            if not teacher.user.is_active:
                return Response({"detail": "Curator user account is inactive."}, status=status.HTTP_400_BAD_REQUEST)

        cohort.teacher = teacher
        cohort.save(update_fields=["teacher", "updated_at"])
        cohort.refresh_from_db()

        curator_payload = None
        if teacher:
            teacher = Lehrer.objects.select_related("user").prefetch_related(
                Prefetch("online_cohorts", queryset=OnlineCohort.objects.select_related("course", "teacher").order_by("start_date", "id"))
            ).get(id=teacher.id)
            curator_payload = _serialize_admin_curator(teacher)

        return Response(
            {
                "cohort": cohort_card_payload(cohort),
                "curator": curator_payload,
            },
            status=status.HTTP_200_OK,
        )


class OnlineTeacherCohortListView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineTeacher]

    def get(self, request):
        teacher = request.user.lehrer_user
        query = (request.query_params.get("q") or "").strip()
        qs = OnlineCohort.objects.filter(teacher=teacher).select_related("course", "teacher").order_by("start_date", "id")
        if query:
            qs = qs.filter(
                Q(name__icontains=query)
                | Q(group_code__icontains=query)
                | Q(course__title_de__icontains=query)
                | Q(course__title_en__icontains=query)
            )
        return Response({"results": [cohort_card_payload(item) for item in qs]}, status=status.HTTP_200_OK)


class OnlineTeacherCohortCalendarView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineTeacher]

    def get(self, request, cohort_id: int):
        teacher = request.user.lehrer_user
        cohort = get_object_or_404(OnlineCohort.objects.select_related("course", "teacher"), id=cohort_id)
        if cohort.teacher_id != teacher.id:
            return Response({"detail": "This cohort is not assigned to current teacher."}, status=status.HTTP_403_FORBIDDEN)

        student_query = (request.query_params.get("student") or "").strip()
        enrollments_qs = (
            cohort.enrollments.filter(status__in=ONLINE_DASHBOARD_ENROLLMENT_STATUSES)
            .select_related("profile__user")
            .order_by("profile__last_name", "profile__first_name")
        )
        if student_query:
            enrollments_qs = enrollments_qs.filter(
                Q(profile__first_name__icontains=student_query)
                | Q(profile__last_name__icontains=student_query)
                | Q(profile__user__email__icontains=student_query)
            )
        enrollments = list(enrollments_qs)
        sessions = list(cohort.sessions.order_by("starts_at"))
        attendance_rows = OnlineAttendance.objects.filter(enrollment__in=enrollments, session__in=sessions)
        attendance_map: dict[tuple[int, int], OnlineAttendance] = {
            (row.enrollment_id, row.session_id): row for row in attendance_rows
        }
        booking_rows = (
            OnlineSessionBooking.objects.filter(
                enrollment__in=enrollments,
                session__in=sessions,
                status=OnlineSessionBooking.STATUS_BOOKED,
            )
            .select_related("enrollment", "enrollment__profile", "enrollment__profile__user", "session")
            .order_by("booked_at", "id")
        )
        bookings_by_session: dict[int, list[OnlineSessionBooking]] = defaultdict(list)
        for booking in booking_rows:
            bookings_by_session[booking.session_id].append(booking)

        students_payload = []
        for enrollment in enrollments:
            present_count = 0
            for session in sessions:
                record = attendance_map.get((enrollment.id, session.id))
                if record and record.status == OnlineAttendance.STATUS_PRESENT:
                    present_count += 1
            attendance_percent = round((present_count / len(sessions)) * 100, 2) if sessions else 0.0
            students_payload.append(
                {
                    "enrollmentId": enrollment.id,
                    "fullName": f"{enrollment.profile.first_name} {enrollment.profile.last_name}".strip(),
                    "email": enrollment.profile.user.email,
                    "status": enrollment.status,
                    "attendancePercent": attendance_percent,
                }
            )

        sessions_payload = [
            {
                "id": session.id,
                "title": session.title,
                "start": session.starts_at,
                "end": session.ends_at,
                "status": session.status,
                "isCompleted": session.is_completed,
                "joinUrl": session.join_url,
                "bookingCount": len(bookings_by_session.get(session.id, [])),
                "bookedStudents": [
                    {
                        "enrollmentId": booking.enrollment_id,
                        "fullName": f"{booking.enrollment.profile.first_name} {booking.enrollment.profile.last_name}".strip(),
                        "email": booking.enrollment.profile.user.email,
                        "bookedAt": booking.booked_at,
                    }
                    for booking in bookings_by_session.get(session.id, [])
                ],
            }
            for session in sessions
        ]

        return Response(
            {
                "cohort": {
                    "id": cohort.id,
                    "groupCode": cohort.group_code,
                    "groupName": cohort.name,
                    "courseTitleDe": cohort.course.title_de,
                    "courseTitleEn": cohort.course.title_en,
                },
                "attendancePercent": compute_cohort_attendance_percent(cohort),
                "sessions": sessions_payload,
                "students": students_payload,
            },
            status=status.HTTP_200_OK,
        )


class OnlineAdminSessionStatusView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    def patch(self, request, session_id: int):
        session = get_object_or_404(OnlineSession.objects.select_related("cohort"), id=session_id)
        serializer = OnlineAdminSessionStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        next_status = serializer.validated_data["status"]
        current_status = session.status

        if not is_valid_session_status_transition(current_status, next_status):
            allowed = sorted(ALLOWED_SESSION_STATUS_TRANSITIONS.get(current_status, set()))
            return Response(
                {
                    "status": (
                        f"Invalid transition from '{current_status}' to '{next_status}'. "
                        f"Allowed next statuses: {allowed or 'none'}."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            result = apply_session_status_transition(
                session=session,
                next_status=next_status,
                sync_attendance_on_end=True,
            )
        except SessionLifecycleError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "id": session.id,
                "status": session.status,
                "isCompleted": session.is_completed,
                "cohortId": session.cohort_id,
                "cohortStatus": result.cohort_status,
                "sync": _serialize_attendance_sync_result(result.sync_result),
                "syncError": result.sync_error,
                "attendanceSyncedAt": session.attendance_synced_at,
            },
            status=status.HTTP_200_OK,
        )


class OnlineAdminSessionOpenView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    def post(self, request, session_id: int):
        session = get_object_or_404(
            OnlineSession.objects.select_related("cohort", "cohort__teacher"),
            id=session_id,
        )
        try:
            payload = _run_admin_session_action(
                session=session,
                action=OnlineAdminSessionBulkActionSerializer.ACTION_OPEN,
            )
        except SessionLifecycleError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(payload, status=status.HTTP_200_OK)


class OnlineAdminSessionEndView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    def post(self, request, session_id: int):
        session = get_object_or_404(
            OnlineSession.objects.select_related("cohort", "cohort__teacher"),
            id=session_id,
        )

        try:
            payload = _run_admin_session_action(
                session=session,
                action=OnlineAdminSessionBulkActionSerializer.ACTION_END,
            )
        except SessionLifecycleError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(payload, status=status.HTTP_200_OK)


class OnlineAdminSessionAttendanceSyncView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    def post(self, request, session_id: int):
        session = get_object_or_404(
            OnlineSession.objects.select_related("cohort", "cohort__teacher"),
            id=session_id,
        )
        payload = _run_admin_session_action(
            session=session,
            action=OnlineAdminSessionBulkActionSerializer.ACTION_SYNC,
        )
        return Response(
            {
                "sessionId": session.id,
                "status": payload["status"],
                "sync": payload["sync"]["sync"] if payload["sync"] else None,
                "studentsTotal": payload["sync"]["studentsTotal"] if payload["sync"] else 0,
                "attendanceRowsTotal": payload["sync"]["attendanceRowsTotal"] if payload["sync"] else 0,
                "attendanceSummary": payload["sync"]["attendanceSummary"] if payload["sync"] else None,
                "attendanceSyncedAt": payload["attendanceSyncedAt"],
            },
            status=status.HTTP_200_OK,
        )


class OnlineAdminOrderRefundView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    def post(self, request, order_id: int):
        order = get_object_or_404(
            OnlineOrder.objects.select_related("profile", "profile__user", "course", "cohort"),
            id=order_id,
        )
        if order.is_trial:
            return Response({"detail": "Trial orders cannot be refunded."}, status=status.HTTP_400_BAD_REQUEST)
        if order.status != OnlineOrder.STATUS_PAID:
            return Response({"detail": "Only paid orders can be refunded."}, status=status.HTTP_400_BAD_REQUEST)

        reason = str(request.data.get("reason") or "").strip() if isinstance(request.data, dict) else ""
        event_payload = {
            "orderId": order.id,
            "status": "refunded",
            "eventType": "admin_refund",
            "reason": reason,
            "providerPaymentId": order.provider_payment_id,
        }
        event_id = f"admin-refund-{order.id}-{uuid4().hex[:8]}"
        result = process_payment_event(
            provider=order.provider,
            event_id=event_id,
            payload=event_payload,
            signature_valid=True,
        )
        order.refresh_from_db()
        return Response(
            {
                "orderId": order.id,
                "status": order.status,
                "refundedAt": order.refunded_at,
                "result": result,
            },
            status=status.HTTP_200_OK,
        )


class OnlineTeacherWorkspaceView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineTeacher]

    def get(self, request):
        teacher = request.user.lehrer_user
        instructor_course_ids = list(
            TrainingCourseRoleAssignment.objects.filter(
                user=request.user,
                role=TrainingCourseRoleAssignment.Role.INSTRUCTOR,
            )
            .values_list("course_id", flat=True)
            .distinct()
        )
        cohorts = list(
            OnlineCohort.objects.filter(teacher=teacher)
            .select_related("course", "teacher")
            .order_by("start_date", "id")
        )
        course_ids = list(dict.fromkeys([*(cohort.course_id for cohort in cohorts), *instructor_course_ids]))
        courses = list(OnlineCourse.objects.filter(id__in=course_ids).order_by("title_de"))
        materials_map = build_course_material_projection_map(course_ids, request=request)
        lessons_map = build_course_lessons_map(course_ids, request=request)
        modules_map = build_course_modules_map(course_ids, request=request)
        cohorts_by_course: dict[int, list[OnlineCohort]] = defaultdict(list)
        for cohort in cohorts:
            cohorts_by_course[cohort.course_id].append(cohort)
        primary_cohort_by_course: dict[int, OnlineCohort] = {}
        for course_id, related_cohorts in cohorts_by_course.items():
            ordered_related = sorted(
                related_cohorts,
                key=lambda cohort: (
                    cohort.start_date or timezone.now().date(),
                    cohort.id,
                ),
            )
            if ordered_related:
                primary_cohort_by_course[course_id] = ordered_related[0]

        for course_id, lessons_payload in lessons_map.items():
            primary_cohort = primary_cohort_by_course.get(course_id)
            if primary_cohort is None:
                continue
            course_sessions = list(primary_cohort.sessions.order_by("sort_order", "starts_at", "id"))
            annotate_lessons_payload_with_sessions(
                lessons_payload,
                course_sessions,
                group_code=primary_cohort.group_code,
                group_name=primary_cohort.name,
            )
            annotate_modules_payload_with_sessions(
                modules_map.get(course_id, []),
                course_sessions,
                group_code=primary_cohort.group_code,
                group_name=primary_cohort.name,
            )

        course_payload = []
        total_students = 0
        total_sessions = 0
        for course in courses:
            related_cohorts = cohorts_by_course.get(course.id, [])
            cohort_ids_for_course = [cohort.id for cohort in related_cohorts]
            sessions_qs = OnlineSession.objects.filter(cohort_id__in=cohort_ids_for_course)
            enrollments_qs = OnlineEnrollment.objects.filter(
                cohort_id__in=cohort_ids_for_course,
                status__in=ONLINE_DASHBOARD_ENROLLMENT_STATUSES,
            )
            students_count = enrollments_qs.count()
            sessions_total = sessions_qs.count()
            total_students += students_count
            total_sessions += sessions_total
            nearest_session = sessions_qs.filter(starts_at__gte=timezone.now()).order_by("starts_at").first()
            projected_materials = materials_map.get(course.id, [])
            course_payload.append(
                {
                    "id": course.id,
                    "slug": course.slug,
                    "titleDe": course.title_de,
                    "titleEn": course.title_en,
                    "descriptionDe": course.description_de,
                    "descriptionEn": course.description_en,
                    "studentsCount": students_count,
                    "cohortsCount": len(related_cohorts),
                    "sessionsCount": sessions_total,
                    "attendancePercent": compute_course_attendance_percent(course),
                    "nearestSessionAt": nearest_session.starts_at if nearest_session else None,
                    "materialsCount": sum(
                        1 for item in projected_materials if item["material_type"] == OnlineCourseMaterial.MATERIAL_RESOURCE
                    ),
                    "recordingsCount": (
                        sum(
                            1
                            for item in projected_materials
                            if item["material_type"] == OnlineCourseMaterial.MATERIAL_RECORDING
                        )
                        + sessions_qs.exclude(recording_url__isnull=True).exclude(recording_url="").count()
                    ),
                }
            )

        materials_payload = []
        for course in courses:
            for material in materials_map.get(course.id, []):
                materials_payload.append(
                    {
                        "id": material["id"],
                        "courseId": course.id,
                        "courseSlug": course.slug,
                        "courseTitleDe": course.title_de,
                        "courseTitleEn": course.title_en,
                        "title": material["title"],
                        "description": material["description"],
                        "materialType": material["material_type"],
                        "language": material["language"],
                        "linkUrl": material["link_url"],
                        "sortOrder": material["sort_order"],
                    }
                )

        recordings = list(
            OnlineSession.objects.filter(cohort__teacher=teacher)
            .select_related("cohort", "cohort__course")
            .exclude(recording_url__isnull=True)
            .exclude(recording_url="")
            .order_by("-starts_at", "-id")
        )
        recordings_payload = [
            {
                "id": session.id,
                "title": session.title,
                "courseId": session.cohort.course_id,
                "courseSlug": session.cohort.course.slug,
                "courseTitleDe": session.cohort.course.title_de,
                "courseTitleEn": session.cohort.course.title_en,
                "groupCode": session.cohort.group_code,
                "startsAt": session.starts_at,
                "recordingUrl": session.recording_url,
            }
            for session in recordings
        ]

        upcoming_sessions = list(
            OnlineSession.objects.filter(cohort__teacher=teacher)
            .select_related("cohort", "cohort__course")
            .filter(starts_at__gte=timezone.now())
            .exclude(status=OnlineSession.STATUS_CANCELED)
            .order_by("starts_at", "id")[:8]
        )
        upcoming_sessions_payload = [
            {
                "id": session.id,
                "title": session.title,
                "groupCode": session.cohort.group_code,
                "groupName": session.cohort.name,
                "courseTitleDe": session.cohort.course.title_de,
                "courseTitleEn": session.cohort.course.title_en,
                "startsAt": session.starts_at,
                "endsAt": session.ends_at,
                "status": session.status,
                "joinUrl": session.join_url,
            }
            for session in upcoming_sessions
        ]

        next_session = upcoming_sessions_payload[0] if upcoming_sessions_payload else None
        attendance_avg = (
            round(sum(item["attendancePercent"] for item in course_payload) / len(course_payload), 2)
            if course_payload
            else 0.0
        )

        return Response(
            {
                "profile": _serialize_teacher_profile(teacher),
                "summary": {
                    "courses": len(course_payload),
                    "cohorts": len(cohorts),
                    "students": total_students,
                    "sessions": total_sessions,
                    "attendancePercent": attendance_avg,
                    "nextSessionAt": next_session["startsAt"] if next_session else None,
                },
                "courses": course_payload,
                "cohorts": [cohort_card_payload(cohort) for cohort in cohorts],
                "materials": materials_payload,
                "lessonPlansByCourse": lessons_map,
                "courseModulesByCourse": modules_map,
                "recordings": recordings_payload,
                "upcomingSessions": upcoming_sessions_payload,
            },
            status=status.HTTP_200_OK,
        )


class OnlineTeacherProfileView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineTeacher]

    def get(self, request):
        return Response(_serialize_teacher_profile(request.user.lehrer_user), status=status.HTTP_200_OK)

    def patch(self, request):
        teacher = request.user.lehrer_user
        serializer = OnlineTeacherProfileUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data

        updated_teacher_fields: list[str] = []
        if "firstName" in payload and teacher.Vorname != payload["firstName"]:
            teacher.Vorname = payload["firstName"]
            updated_teacher_fields.append("Vorname")
        if "lastName" in payload and teacher.Nachname != payload["lastName"]:
            teacher.Nachname = payload["lastName"]
            updated_teacher_fields.append("Nachname")
        if "privateEmail" in payload and teacher.Private_Email != payload["privateEmail"]:
            teacher.Private_Email = payload["privateEmail"]
            updated_teacher_fields.append("Private_Email")
        if "phone" in payload and teacher.Telefonnummer != payload["phone"]:
            teacher.Telefonnummer = payload["phone"]
            updated_teacher_fields.append("Telefonnummer")

        if updated_teacher_fields:
            teacher.save(update_fields=updated_teacher_fields)

        updated_user_fields: list[str] = []
        if "firstName" in payload and request.user.first_name != payload["firstName"]:
            request.user.first_name = payload["firstName"]
            updated_user_fields.append("first_name")
        if "lastName" in payload and request.user.last_name != payload["lastName"]:
            request.user.last_name = payload["lastName"]
            updated_user_fields.append("last_name")
        if updated_user_fields:
            request.user.save(update_fields=updated_user_fields)

        teacher.refresh_from_db()
        return Response(_serialize_teacher_profile(teacher), status=status.HTTP_200_OK)


class OnlineTeacherFeedbackView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineTeacher]

    def post(self, request):
        teacher = request.user.lehrer_user
        serializer = OnlineTeacherFeedbackCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        feedback = OnlineFeedbackMessage.objects.create(
            course=serializer.validated_data.get("course"),
            full_name=f"{teacher.Vorname} {teacher.Nachname}".strip() or request.user.email,
            email=teacher.Schule_Email or request.user.email,
            subject=serializer.validated_data["subject"],
            message=serializer.validated_data["message"],
            preferred_language=OnlineCourse.LOCALE_EN,
            source_page="teacher_workspace",
        )
        send_feedback_notification(
            sender_email=feedback.email,
            sender_name=feedback.full_name,
            subject=feedback.subject,
            message=feedback.message,
        )
        return Response(
            {
                "id": feedback.id,
                "subject": feedback.subject,
                "createdAt": feedback.created_at,
            },
            status=status.HTTP_201_CREATED,
        )


class OnlineTeacherSessionOpenView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineTeacher]

    def post(self, request, session_id: int):
        teacher = request.user.lehrer_user
        session = get_object_or_404(
            OnlineSession.objects.select_related("cohort", "cohort__teacher"),
            id=session_id,
        )
        if session.cohort.teacher_id != teacher.id:
            return Response({"detail": "This session is not assigned to current teacher."}, status=status.HTTP_403_FORBIDDEN)

        if session.status == OnlineSession.STATUS_CANCELED:
            return Response({"detail": "Session is canceled and cannot be opened."}, status=status.HTTP_400_BAD_REQUEST)
        if session.status == OnlineSession.STATUS_ENDED or session.is_completed:
            return Response({"detail": "Session is already completed."}, status=status.HTTP_400_BAD_REQUEST)
        if session.status != OnlineSession.STATUS_LIVE:
            try:
                ensure_single_live_session(session=session)
            except SessionLifecycleError as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        if not session.join_url:
            try:
                create_online_meeting_for_session(session=session)
                session.refresh_from_db(fields=["join_url", "provider_meeting_id", "updated_at"])
            except GraphSyncNotConfigured as exc:
                return Response(
                    {"detail": f"Join link is missing and Teams auto-create is not configured: {exc}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            except GraphSyncRequestError as exc:
                return Response(
                    {"detail": f"Join link is missing and Teams auto-create failed: {exc}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        try:
            result = apply_session_status_transition(
                session=session,
                next_status=OnlineSession.STATUS_LIVE,
                sync_attendance_on_end=False,
            )
        except SessionLifecycleError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "id": session.id,
                "title": session.title,
                "status": session.status,
                "isCompleted": session.is_completed,
                "joinUrl": session.join_url,
                "startsAt": session.starts_at,
                "endsAt": session.ends_at,
                "cohortId": session.cohort_id,
                "cohortStatus": result.cohort_status,
            },
            status=status.HTTP_200_OK,
        )


class OnlineTeacherSessionEndView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineTeacher]

    def post(self, request, session_id: int):
        teacher = request.user.lehrer_user
        session = get_object_or_404(
            OnlineSession.objects.select_related("cohort", "cohort__teacher"),
            id=session_id,
        )
        if session.cohort.teacher_id != teacher.id:
            return Response({"detail": "This session is not assigned to current teacher."}, status=status.HTTP_403_FORBIDDEN)

        if session.status == OnlineSession.STATUS_CANCELED:
            return Response({"detail": "Canceled sessions cannot be ended."}, status=status.HTTP_400_BAD_REQUEST)
        if session.status == OnlineSession.STATUS_ENDED or session.is_completed:
            return Response({"detail": "Session is already completed."}, status=status.HTTP_400_BAD_REQUEST)
        if session.status != OnlineSession.STATUS_LIVE:
            return Response({"detail": "Only live sessions can be ended from teacher workspace."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            result = apply_session_status_transition(
                session=session,
                next_status=OnlineSession.STATUS_ENDED,
                sync_attendance_on_end=True,
            )
        except SessionLifecycleError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "id": session.id,
                "title": session.title,
                "status": session.status,
                "isCompleted": session.is_completed,
                "joinUrl": session.join_url,
                "startsAt": session.starts_at,
                "endsAt": session.ends_at,
                "cohortId": session.cohort_id,
                "cohortStatus": result.cohort_status,
                "sync": _serialize_attendance_sync_result(result.sync_result),
                "syncError": result.sync_error,
                "attendanceSyncedAt": session.attendance_synced_at,
            },
            status=status.HTTP_200_OK,
        )


class OnlineTeacherSessionAttendanceSyncView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineTeacher]

    def post(self, request, session_id: int):
        teacher = request.user.lehrer_user
        session = get_object_or_404(
            OnlineSession.objects.select_related("cohort", "cohort__teacher"),
            id=session_id,
        )
        if session.cohort.teacher_id != teacher.id:
            return Response({"detail": "This session is not assigned to current teacher."}, status=status.HTTP_403_FORBIDDEN)

        sync_result = sync_session_attendance_and_stamp(session=session)
        return Response(
            {
                "sessionId": session.id,
                "status": session.status,
                "sync": sync_result.sync,
                "studentsTotal": sync_result.students_total,
                "attendanceRowsTotal": sync_result.rows_total,
                "attendanceSummary": sync_result.summary,
                "attendanceSyncedAt": session.attendance_synced_at,
            },
            status=status.HTTP_200_OK,
        )


