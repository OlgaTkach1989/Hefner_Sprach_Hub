from __future__ import annotations

import hashlib
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from apps.online import views as online_views
from apps.employees.models import Lehrer
from apps.online.models import (
    OnlineAccessPolicy,
    OnlineAttendance,
    OnlineAuditEvent,
    OnlineCatalogAttributeDefinition,
    OnlineCatalogAttributeValue,
    OnlineCohort,
    OnlineCompletionEvidence,
    OnlineCourse,
    OnlineCourseApproval,
    OnlineCourseContentLibraryItem,
    OnlineCourseLesson,
    OnlineCourseLessonSection,
    OnlineCourseLessonSectionItem,
    OnlineCourseModule,
    OnlineCourseMaterial,
    OnlineCourseVersion,
    OnlineEnrollmentAttestation,
    OnlineIdentityLink,
    OnlineExternalCatalogProvider,
    OnlineCourseTemplate,
    OnlineEnrollment,
    OnlineFeedbackMessage,
    OnlineIdentityProvider,
    OnlineInstructorProfile,
    OnlineKnowledgeDocument,
    OnlineKnowledgeSource,
    OnlineLessonProgress,
    OnlineLearningProgram,
    OnlineLearningProgramCourse,
    OnlineMagicLinkToken,
    OnlineOrder,
    OnlinePaymentEvent,
    OnlineScopeAssignment,
    OnlineSession,
    OnlineSessionReminder,
    OnlineStudentProfile,
    OnlineStudentProgramAssignment,
    OnlineWorkspace,
    OnlineWorkspaceContentItem,
)
from apps.online.services.email_service import send_course_access_email, send_online_email
from apps.online.services.graph_attendance_service import GraphSyncRequestError
from apps.online.services.course_agents_orchestrator import CourseBuilderAgentsError
from apps.online.services.course_structure import upsert_course_structure
from apps.online.services.session_generation import SessionGenerationError, generate_missing_sessions_for_cohort
from apps.training.models import TrainingAudience, TrainingContentAudiencePolicy, TrainingContentItem, TrainingUserAudienceGrant

User = get_user_model()


class OnlineOperationsHealthTests(APITestCase):
    def test_healthcheck_returns_release_metadata(self):
        response = self.client.get("/api/health/")
        payload = response.json()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["service"], "learning-hub-backend")
        self.assertIn("timestamp", payload)

    @override_settings(
        TRAINING_NOTEBOOK_RUNTIME_ENABLED=True,
        TRAINING_GRADER_RUNTIME_ENABLED=True,
        TRAINING_AI_ENABLED=True,
        TRAINING_AI_PGVECTOR_ENABLED=True,
        ONLINE_EMAIL_MODE="directus_flow",
        ONLINE_EMAIL_DIRECTUS_FLOW_URL="https://directus.example.com/flows/trigger/online-email",
        ONLINE_COURSE_ACCESS_DIRECTUS_FLOW_URL="https://directus.example.com/flows/trigger/course-access",
        TRAINING_DIRECTUS_SYNC_TOKEN="training-sync-token",
        TRAINING_JUPYTERHUB_BASE_URL="https://example.com/lab",
        TRAINING_JUPYTERHUB_SERVICE_TOKEN="service-token",
        TRAINING_JUPYTERHUB_API_TOKEN="api-token",
        TRAINING_JUPYTERHUB_SHARED_SECRET="shared-secret",
        TRAINING_GRADER_WEBHOOK_SECRET="grader-secret",
        TRAINING_NBGRADER_COURSE_ROOT="/tmp/training-course-root",
    )
    def test_readiness_endpoint_reports_checks_and_feature_flags(self):
        response = self.client.get("/api/health/ready/")
        payload = response.json()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(payload["status"], "ok")
        self.assertTrue(payload["ready"])
        self.assertEqual(payload["checks"]["database"]["ok"], True)
        self.assertEqual(payload["checks"]["mediaRoot"]["ok"], True)
        self.assertEqual(payload["checks"]["staticRoot"]["ok"], True)
        self.assertIn("cache", payload["checks"])
        self.assertIn("pgvector", payload["checks"])
        self.assertTrue(payload["features"]["directusEmailFlowConfigured"])
        self.assertTrue(payload["features"]["directusTrainingSyncConfigured"])
        self.assertTrue(payload["features"]["jupyterRuntimeConfigured"])
        self.assertTrue(payload["features"]["graderRuntimeConfigured"])


class OnlineSprintOneTests(APITestCase):
    def setUp(self):
        self.client = APIClient()

    def _create_course(
        self,
        *,
        slug: str,
        trial_available: bool,
        price_amount: Decimal,
        title_de: str | None = None,
        title_en: str | None = None,
        short_description_de: str | None = None,
        short_description_en: str | None = None,
        description_de: str | None = None,
        description_en: str | None = None,
    ) -> OnlineCourse:
        return OnlineCourse.objects.create(
            slug=slug,
            title_de=title_de or f"{slug} de",
            title_en=title_en or f"{slug} en",
            short_description_de=short_description_de or "Kurzbeschreibung",
            short_description_en=short_description_en or "Short description",
            description_de=description_de or "Beschreibung",
            description_en=description_en or "Description",
            lessons_count=12,
            trial_available=trial_available,
            price_amount=price_amount,
            currency="EUR",
            is_subscription=False,
            is_published=True,
        )

    def _create_cohort(self, *, course: OnlineCourse, group_code: str, capacity: int = 20, teacher: Lehrer | None = None):
        return OnlineCohort.objects.create(
            course=course,
            teacher=teacher,
            name=f"Group {group_code}",
            group_code=group_code,
            capacity=capacity,
            timezone="Europe/Berlin",
            status=OnlineCohort.STATUS_OPEN,
            is_public=True,
        )

    def _ensure_demo_audiences(self) -> dict[str, TrainingAudience]:
        payloads = (
            {
                "slug": "external-users",
                "name": "Guest access",
                "short_label": "Guest",
                "audience_type": TrainingAudience.AudienceType.DEMO_ROLE,
                "privilege_rank": 10,
                "is_internal": False,
            },
            {
                "slug": "interns-new-grads",
                "name": "Student access",
                "short_label": "Student",
                "audience_type": TrainingAudience.AudienceType.DEMO_ROLE,
                "privilege_rank": 20,
                "is_internal": True,
            },
            {
                "slug": "lateral-transfers",
                "name": "Instructor access",
                "short_label": "Instructor",
                "audience_type": TrainingAudience.AudienceType.DEMO_ROLE,
                "privilege_rank": 30,
                "is_internal": True,
            },
            {
                "slug": "traders-structurizers",
                "name": "Admin access",
                "short_label": "Admin",
                "audience_type": TrainingAudience.AudienceType.DEMO_ROLE,
                "privilege_rank": 40,
                "is_internal": True,
            },
        )
        result: dict[str, TrainingAudience] = {}
        for payload in payloads:
            audience, _created = TrainingAudience.objects.update_or_create(
                slug=payload["slug"],
                defaults=payload,
            )
            result[payload["slug"]] = audience
        return result

    def _create_teacher(self, *, index: int = 1) -> tuple[User, Lehrer]:
        user = User.objects.create_user(
            email=f"teacher{index}@example.com",
            username=f"teacher_{index}",
            password="TeacherPass12345",
        )
        teacher = Lehrer.objects.create(
            user=user,
            Nachname=f"Nachname{index}",
            Vorname=f"Vorname{index}",
            Schule_Email=f"teacher{index}@school.example.com",
            Private_Email=f"teacher{index}@private.example.com",
            KurzName=f"TCHR{index}",
        )
        return user, teacher

    def _create_admin_user(self, *, index: int = 1) -> User:
        return User.objects.create_user(
            email=f"admin{index}@example.com",
            username=f"admin_{index}",
            password="AdminPass12345",
            is_admin=True,
            is_staff=True,
        )

    def _assert_auth_cookies(self, response, *, scope: str) -> None:
        if scope == "staff":
            access_cookie = settings.ONLINE_STAFF_ACCESS_COOKIE_NAME
            refresh_cookie = settings.ONLINE_STAFF_REFRESH_COOKIE_NAME
        else:
            access_cookie = settings.ONLINE_STUDENT_ACCESS_COOKIE_NAME
            refresh_cookie = settings.ONLINE_STUDENT_REFRESH_COOKIE_NAME

        self.assertNotIn("auth", response.data)
        self.assertIn(access_cookie, response.cookies)
        self.assertIn(refresh_cookie, response.cookies)
        self.assertTrue(response.cookies[access_cookie].value)
        self.assertTrue(response.cookies[refresh_cookie].value)

    @override_settings(
        ONLINE_EMAIL_MODE="directus_flow",
        ONLINE_EMAIL_DIRECTUS_FLOW_URL="https://directus.kunstschuleberlin.de/flows/trigger/email-flow",
        ONLINE_EMAIL_DIRECTUS_TOKEN="online-email-token",
    )
    def test_send_online_email_directus_flow_appends_access_token_query(self):
        response_mock = Mock()
        response_mock.raise_for_status.return_value = None

        with patch("apps.online.services.email_service.requests.post", return_value=response_mock) as post_mock:
            result = send_online_email(
                recipient="student@example.com",
                subject="Subject",
                text_body="Body",
            )

        self.assertTrue(result)
        post_mock.assert_called_once()
        called_url = post_mock.call_args.kwargs["url"] if "url" in post_mock.call_args.kwargs else post_mock.call_args.args[0]
        self.assertIn("access_token=online-email-token", called_url)
        self.assertEqual(post_mock.call_args.kwargs["json"]["to"], "student@example.com")

    @override_settings(
        ONLINE_EMAIL_MODE="directus_flow",
        ONLINE_EMAIL_DIRECTUS_FLOW_URL="https://directus.kunstschuleberlin.de/flows/trigger/email-flow",
        ONLINE_EMAIL_DIRECTUS_TOKEN="",
    )
    def test_send_online_email_directus_flow_falls_back_to_directus_api_token_env(self):
        response_mock = Mock()
        response_mock.raise_for_status.return_value = None

        with patch.dict("os.environ", {"DIRECTUS_API_TOKEN": "fallback-directus-token"}, clear=False):
            with patch("apps.online.services.email_service.requests.post", return_value=response_mock) as post_mock:
                result = send_online_email(
                    recipient="student@example.com",
                    subject="Subject",
                    text_body="Body",
                )

        self.assertTrue(result)
        post_mock.assert_called_once()
        called_url = post_mock.call_args.kwargs["url"] if "url" in post_mock.call_args.kwargs else post_mock.call_args.args[0]
        self.assertIn("access_token=fallback-directus-token", called_url)

    @override_settings(
        ONLINE_EMAIL_MODE="directus_flow",
        ONLINE_COURSE_ACCESS_DIRECTUS_FLOW_URL="https://directus.kunstschuleberlin.de/flows/trigger/course-access-flow",
        ONLINE_EMAIL_DIRECTUS_TOKEN="course-access-token",
        ONLINE_STUDENT_PORTAL_URL="https://studentlist.kunstschuleberlin.de/student/login",
    )
    def test_send_course_access_email_directus_flow_sends_structured_payload(self):
        course = self._create_course(slug="welcome-course", trial_available=True, price_amount=Decimal("0.00"))
        user = User.objects.create_user(
            email="welcome.student@example.com",
            username="welcome_student",
            password="StrongPass12345",
        )
        profile = OnlineStudentProfile.objects.create(
            user=user,
            first_name="Angelina",
            last_name="Finogenova",
            preferred_language="de",
        )
        response_mock = Mock()
        response_mock.raise_for_status.return_value = None

        with patch("apps.online.services.email_service.requests.post", return_value=response_mock) as post_mock:
            result = send_course_access_email(profile=profile, course=course, is_trial=True)

        self.assertTrue(result)
        post_mock.assert_called_once()
        called_url = post_mock.call_args.kwargs["url"] if "url" in post_mock.call_args.kwargs else post_mock.call_args.args[0]
        called_payload = post_mock.call_args.kwargs["json"]
        self.assertIn("access_token=course-access-token", called_url)
        self.assertEqual(called_payload["to"], "welcome.student@example.com")
        self.assertTrue(called_payload["subject"])
        self.assertIn("welcome.student@example.com", called_payload["text"])
        self.assertTrue(called_payload["html"].startswith("<p>"))
        self.assertEqual(called_payload["data"]["to"], "welcome.student@example.com")
        self.assertEqual(called_payload["data"]["first_name"], "Angelina")
        self.assertEqual(called_payload["data"]["login"], "welcome.student@example.com")
        self.assertEqual(
            called_payload["data"]["portal_url"],
            "https://studentlist.kunstschuleberlin.de/student/login",
        )
        self.assertEqual(called_payload["data"]["course_title"], course.title_de)
        self.assertEqual(called_payload["data"]["mode"], "trial")

    def test_trial_signup_returns_existing_access_for_same_course_and_cohort(self):
        course = self._create_course(slug="trial-course", trial_available=True, price_amount=Decimal("0.00"))
        cohort = self._create_cohort(course=course, group_code="TRIAL_G1", capacity=5)

        payload = {
            "course_slug": course.slug,
            "cohort_id": cohort.id,
            "email": "trial.user@example.com",
            "password": "StrongPass12345",
            "first_name": "Trial",
            "last_name": "User",
            "preferred_language": "de",
            "idempotency_key": "trial-1",
        }

        first_response = self.client.post("/online/public/trial-signup/", payload, format="json")
        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(OnlineOrder.objects.filter(is_trial=True).count(), 1)

        second_payload = {**payload, "idempotency_key": "trial-2"}
        second_response = self.client.post("/online/public/trial-signup/", second_payload, format="json")
        self.assertEqual(second_response.status_code, status.HTTP_200_OK)
        self.assertTrue(second_response.data.get("alreadyProcessed"))
        self.assertEqual(second_response.data.get("enrollmentId"), first_response.data.get("enrollmentId"))
        self.assertEqual(OnlineOrder.objects.filter(is_trial=True).count(), 1)

    def test_trial_signup_blocks_second_trial_on_different_course(self):
        first_course = self._create_course(slug="trial-course-first", trial_available=True, price_amount=Decimal("0.00"))
        first_cohort = self._create_cohort(course=first_course, group_code="TRIAL_FIRST_G1", capacity=5)
        second_course = self._create_course(slug="trial-course-second", trial_available=True, price_amount=Decimal("0.00"))
        second_cohort = self._create_cohort(course=second_course, group_code="TRIAL_SECOND_G1", capacity=5)

        first_payload = {
            "course_slug": first_course.slug,
            "cohort_id": first_cohort.id,
            "email": "trial.user@example.com",
            "password": "StrongPass12345",
            "first_name": "Trial",
            "last_name": "User",
            "preferred_language": "de",
            "idempotency_key": "trial-first-1",
        }
        first_response = self.client.post("/online/public/trial-signup/", first_payload, format="json")
        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)

        second_payload = {
            **first_payload,
            "course_slug": second_course.slug,
            "cohort_id": second_cohort.id,
            "idempotency_key": "trial-second-1",
        }
        second_response = self.client.post("/online/public/trial-signup/", second_payload, format="json")

        self.assertEqual(second_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(second_response.data.get("detail"), "Free trial is already used for this account.")
        self.assertEqual(OnlineOrder.objects.filter(is_trial=True).count(), 1)

    def test_trial_signup_works_even_when_browser_has_admin_session_cookie(self):
        admin_user = User.objects.create_user(
            email="admin.session@example.com",
            username="admin_session",
            password="AdminPass12345",
            is_admin=True,
            is_staff=True,
        )
        course = self._create_course(slug="trial-session-course", trial_available=True, price_amount=Decimal("0.00"))
        cohort = self._create_cohort(course=course, group_code="TRIAL_SESSION_G1", capacity=5)

        client = APIClient(enforce_csrf_checks=True)
        self.assertTrue(client.login(email="admin.session@example.com", password="AdminPass12345"))

        payload = {
            "course_slug": course.slug,
            "cohort_id": cohort.id,
            "email": "trial.session.student@example.com",
            "password": "StrongPass12345",
            "first_name": "Trial",
            "last_name": "Session",
            "preferred_language": "de",
            "idempotency_key": "trial-session-idem-1",
        }
        response = client.post("/online/public/trial-signup/", payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            OnlineOrder.objects.filter(
                profile__user__email="trial.session.student@example.com",
                is_trial=True,
                status=OnlineOrder.STATUS_TRIAL,
            ).exists()
        )

    def test_mock_checkout_blocks_when_cohort_capacity_is_reached(self):
        course = self._create_course(slug="paid-course", trial_available=False, price_amount=Decimal("129.00"))
        cohort = self._create_cohort(course=course, group_code="PAID_G1", capacity=1)

        first_payload = {
            "course_slug": course.slug,
            "cohort_id": cohort.id,
            "email": "first.student@example.com",
            "password": "StrongPass12345",
            "first_name": "First",
            "last_name": "Student",
            "preferred_language": "de",
            "provider": "paypal",
            "accept_terms": True,
            "idempotency_key": "paid-1",
        }
        first_response = self.client.post("/online/public/checkout/mock/", first_payload, format="json")
        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)

        second_payload = {
            **first_payload,
            "email": "second.student@example.com",
            "idempotency_key": "paid-2",
        }
        second_response = self.client.post("/online/public/checkout/mock/", second_payload, format="json")
        self.assertEqual(second_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("cohort_id", second_response.data)

    def test_admin_can_change_session_status_and_completion_flag(self):
        admin_user = User.objects.create_user(
            email="admin.online@example.com",
            username="admin_online",
            password="AdminPass12345",
            is_admin=True,
        )
        course = self._create_course(slug="admin-course", trial_available=False, price_amount=Decimal("59.00"))
        cohort = self._create_cohort(course=course, group_code="ADMIN_G1", capacity=5)
        session = OnlineSession.objects.create(
            cohort=cohort,
            title="Session 1",
            starts_at=timezone.now() + timedelta(days=1),
            ends_at=timezone.now() + timedelta(days=1, hours=2),
            status=OnlineSession.STATUS_SCHEDULED,
            is_completed=False,
        )

        client = APIClient()
        client.force_authenticate(user=admin_user)
        to_live_response = client.patch(
            f"/online/admin/sessions/{session.id}/status/",
            {"status": OnlineSession.STATUS_LIVE},
            format="json",
        )
        self.assertEqual(to_live_response.status_code, status.HTTP_200_OK)

        response = client.patch(
            f"/online/admin/sessions/{session.id}/status/",
            {"status": OnlineSession.STATUS_ENDED},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        session.refresh_from_db()
        self.assertEqual(session.status, OnlineSession.STATUS_ENDED)
        self.assertTrue(session.is_completed)

    def test_admin_status_transition_rejects_invalid_jump(self):
        admin_user = User.objects.create_user(
            email="admin.invalid@example.com",
            username="admin_invalid",
            password="AdminPass12345",
            is_admin=True,
        )
        course = self._create_course(slug="invalid-transition", trial_available=False, price_amount=Decimal("79.00"))
        cohort = self._create_cohort(course=course, group_code="INVALID_G1", capacity=5)
        session = OnlineSession.objects.create(
            cohort=cohort,
            title="Session Jump",
            starts_at=timezone.now() + timedelta(days=1),
            ends_at=timezone.now() + timedelta(days=1, hours=2),
            status=OnlineSession.STATUS_SCHEDULED,
            is_completed=False,
        )

        client = APIClient()
        client.force_authenticate(user=admin_user)
        response = client.patch(
            f"/online/admin/sessions/{session.id}/status/",
            {"status": OnlineSession.STATUS_ENDED},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Invalid transition", response.data.get("status", ""))

    def test_admin_cannot_mark_second_session_live_in_same_cohort(self):
        admin_user = User.objects.create_user(
            email="admin.live.conflict@example.com",
            username="admin_live_conflict",
            password="AdminPass12345",
            is_admin=True,
        )
        course = self._create_course(slug="admin-live-guard", trial_available=False, price_amount=Decimal("79.00"))
        cohort = self._create_cohort(course=course, group_code="ADMIN_LIVE_G1", capacity=5)
        first_session = OnlineSession.objects.create(
            cohort=cohort,
            title="Live One",
            starts_at=timezone.now() - timedelta(minutes=30),
            ends_at=timezone.now() + timedelta(minutes=30),
            status=OnlineSession.STATUS_LIVE,
            is_completed=False,
        )
        second_session = OnlineSession.objects.create(
            cohort=cohort,
            title="Scheduled Two",
            starts_at=timezone.now() + timedelta(hours=1),
            ends_at=timezone.now() + timedelta(hours=3),
            status=OnlineSession.STATUS_SCHEDULED,
            is_completed=False,
        )

        client = APIClient()
        client.force_authenticate(user=admin_user)
        response = client.patch(
            f"/online/admin/sessions/{second_session.id}/status/",
            {"status": OnlineSession.STATUS_LIVE},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Another live session", response.data.get("detail", ""))
        first_session.refresh_from_db()
        second_session.refresh_from_db()
        self.assertEqual(first_session.status, OnlineSession.STATUS_LIVE)
        self.assertEqual(second_session.status, OnlineSession.STATUS_SCHEDULED)

    @override_settings(ONLINE_PAYMENT_MODE="free", ONLINE_ATTENDANCE_SYNC_MODE="demo")
    def test_admin_marking_session_ended_auto_syncs_attendance(self):
        admin_user = User.objects.create_user(
            email="admin.ended.sync@example.com",
            username="admin_ended_sync",
            password="AdminPass12345",
            is_admin=True,
        )
        course = self._create_course(slug="admin-end-sync", trial_available=False, price_amount=Decimal("79.00"))
        cohort = self._create_cohort(course=course, group_code="ADMIN_END_SYNC_G1", capacity=5)
        session = OnlineSession.objects.create(
            cohort=cohort,
            title="Admin End Sync",
            starts_at=timezone.now() - timedelta(hours=2),
            ends_at=timezone.now() - timedelta(minutes=5),
            status=OnlineSession.STATUS_LIVE,
            is_completed=False,
        )

        checkout_payload = {
            "course_slug": course.slug,
            "cohort_id": cohort.id,
            "email": "admin.end.sync.student@example.com",
            "password": "StrongPass12345",
            "first_name": "Admin",
            "last_name": "Sync",
            "preferred_language": "de",
            "accept_terms": True,
            "idempotency_key": "admin-end-sync-start-1",
        }
        self.assertEqual(
            self.client.post("/online/public/checkout/start/", checkout_payload, format="json").status_code,
            status.HTTP_201_CREATED,
        )

        client = APIClient()
        client.force_authenticate(user=admin_user)
        response = client.patch(
            f"/online/admin/sessions/{session.id}/status/",
            {"status": OnlineSession.STATUS_ENDED},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(response.data.get("sync"))

        session.refresh_from_db()
        self.assertEqual(session.status, OnlineSession.STATUS_ENDED)
        self.assertTrue(session.is_completed)
        self.assertIsNotNone(session.attendance_synced_at)

    def test_generate_missing_sessions_for_cohort_uses_course_lessons_count(self):
        course = self._create_course(slug="session-generator-course", trial_available=False, price_amount=Decimal("79.00"))
        course.lessons_count = 4
        course.save(update_fields=["lessons_count", "updated_at"])
        cohort = self._create_cohort(course=course, group_code="GENERATOR_G1", capacity=6)
        cohort.start_date = timezone.localdate() + timedelta(days=3)
        cohort.save(update_fields=["start_date", "updated_at"])

        OnlineSession.objects.create(
            cohort=cohort,
            title="Lektion 1",
            starts_at=timezone.now() + timedelta(days=1),
            ends_at=timezone.now() + timedelta(days=1, hours=2),
            status=OnlineSession.STATUS_SCHEDULED,
            sort_order=1,
            is_completed=False,
        )

        result = generate_missing_sessions_for_cohort(cohort)

        self.assertEqual(result.created_count, 3)
        self.assertEqual(result.final_count, 4)
        self.assertEqual(cohort.sessions.count(), 4)
        self.assertEqual(
            list(cohort.sessions.order_by("sort_order").values_list("sort_order", flat=True)),
            [1, 2, 3, 4],
        )

    def test_generate_missing_sessions_requires_start_date_for_empty_cohort(self):
        course = self._create_course(slug="session-generator-empty", trial_available=False, price_amount=Decimal("49.00"))
        course.lessons_count = 3
        course.save(update_fields=["lessons_count", "updated_at"])
        cohort = self._create_cohort(course=course, group_code="GENERATOR_EMPTY_G1", capacity=6)

        with self.assertRaises(SessionGenerationError):
            generate_missing_sessions_for_cohort(cohort)

    def test_generate_missing_sessions_falls_back_to_default_duration_for_broken_source_session(self):
        course = self._create_course(
            slug="session-generator-duration-guard",
            trial_available=False,
            price_amount=Decimal("59.00"),
        )
        course.lessons_count = 3
        course.save(update_fields=["lessons_count", "updated_at"])
        cohort = self._create_cohort(course=course, group_code="GENERATOR_DURATION_G1", capacity=6)
        cohort.start_date = timezone.localdate() + timedelta(days=3)
        cohort.save(update_fields=["start_date", "updated_at"])

        starts_at = timezone.now() + timedelta(days=1)
        OnlineSession.objects.create(
            cohort=cohort,
            title="Lektion 1",
            starts_at=starts_at,
            ends_at=starts_at + timedelta(days=6, hours=2),
            status=OnlineSession.STATUS_SCHEDULED,
            sort_order=1,
            is_completed=False,
        )

        generate_missing_sessions_for_cohort(cohort)

        generated_sessions = list(cohort.sessions.order_by("sort_order"))
        self.assertEqual(len(generated_sessions), 3)
        self.assertEqual(
            generated_sessions[1].ends_at - generated_sessions[1].starts_at,
            timedelta(hours=2),
        )
        self.assertEqual(
            generated_sessions[2].ends_at - generated_sessions[2].starts_at,
            timedelta(hours=2),
        )

    def test_admin_course_list_and_detail_include_course_level_stats(self):
        admin_user = User.objects.create_user(
            email="course.dashboard.admin@example.com",
            username="course_dashboard_admin",
            password="AdminPass12345",
            is_admin=True,
        )
        teacher_user, teacher = self._create_teacher(index=512)
        course = self._create_course(slug="course-dashboard", trial_available=False, price_amount=Decimal("89.00"))
        course.lessons_count = 2
        course.save(update_fields=["lessons_count", "updated_at"])
        cohort = self._create_cohort(course=course, group_code="COURSE_DASH_G1", capacity=8, teacher=teacher)
        cohort.start_date = timezone.localdate() + timedelta(days=1)
        cohort.save(update_fields=["teacher", "start_date", "updated_at"])

        first_session = OnlineSession.objects.create(
            cohort=cohort,
            title="Session 1",
            starts_at=timezone.now() + timedelta(days=1),
            ends_at=timezone.now() + timedelta(days=1, hours=2),
            status=OnlineSession.STATUS_SCHEDULED,
            sort_order=1,
            is_completed=False,
        )
        second_session = OnlineSession.objects.create(
            cohort=cohort,
            title="Session 2",
            starts_at=timezone.now() + timedelta(days=8),
            ends_at=timezone.now() + timedelta(days=8, hours=2),
            status=OnlineSession.STATUS_SCHEDULED,
            sort_order=2,
            is_completed=False,
        )

        checkout_payload = {
            "course_slug": course.slug,
            "cohort_id": cohort.id,
            "email": "course.dashboard.student@example.com",
            "password": "StrongPass12345",
            "first_name": "Course",
            "last_name": "Student",
            "preferred_language": "de",
            "accept_terms": True,
            "idempotency_key": "course-dashboard-1",
        }
        checkout_response = self.client.post("/online/public/checkout/mock/", checkout_payload, format="json")
        self.assertEqual(checkout_response.status_code, status.HTTP_201_CREATED)
        enrollment = OnlineEnrollment.objects.get(profile__user__email="course.dashboard.student@example.com")
        OnlineAttendance.objects.create(
            enrollment=enrollment,
            session=first_session,
            status=OnlineAttendance.STATUS_PRESENT,
        )

        admin_client = APIClient()
        admin_client.force_authenticate(user=admin_user)

        list_response = admin_client.get("/online/admin/courses/", {"q": teacher.Vorname})
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertTrue(any(item["id"] == course.id for item in list_response.data.get("results", [])))

        detail_response = admin_client.get(f"/online/admin/courses/{course.id}/")
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.data["id"], course.id)
        self.assertEqual(detail_response.data["cohortsCount"], 1)
        self.assertEqual(detail_response.data["sessionsSummary"]["total"], 2)
        self.assertEqual(detail_response.data["studentsCount"], 1)
        self.assertEqual(len(detail_response.data["cohorts"]), 1)
        self.assertEqual(len(detail_response.data["sessions"]), 2)
        self.assertEqual(detail_response.data["sessions"][1]["id"], second_session.id)
        self.assertEqual(detail_response.data["audiences"], [])

    def test_admin_course_manager_page_renders(self):
        admin_user = User.objects.create_superuser(
            email="course.manager.admin@example.com",
            password="AdminPass12345",
            username="course_manager_admin",
        )
        course = self._create_course(slug="manager-course", trial_available=False, price_amount=Decimal("59.00"))
        cohort = self._create_cohort(course=course, group_code="MANAGER_G1", capacity=5)
        cohort.start_date = timezone.localdate() + timedelta(days=2)
        cohort.save(update_fields=["start_date", "updated_at"])

        self.client.force_login(admin_user)
        response = self.client.get("/admin/online/onlinecourse/manager/", {"course": course.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertContains(response, "Online Course Manager")
        self.assertContains(response, course.title_de)
        self.assertContains(response, cohort.group_code)

    def test_admin_can_open_session_and_trigger_attendance_sync(self):
        _, teacher = self._create_teacher(index=21)
        admin_user = self._create_admin_user(index=21)
        course = self._create_course(slug="admin-open-course", trial_available=False, price_amount=Decimal("89.00"))
        cohort = self._create_cohort(course=course, group_code="ADMIN_OPEN_G1", capacity=8, teacher=teacher)
        session = OnlineSession.objects.create(
            cohort=cohort,
            title="Admin Live Session",
            starts_at=timezone.now() + timedelta(hours=2),
            ends_at=timezone.now() + timedelta(hours=4),
            status=OnlineSession.STATUS_SCHEDULED,
            join_url="https://teams.microsoft.com/admin-live",
            is_completed=False,
        )

        admin_client = APIClient()
        admin_client.force_authenticate(user=admin_user)

        open_response = admin_client.post(f"/online/admin/sessions/{session.id}/open/", format="json")
        self.assertEqual(open_response.status_code, status.HTTP_200_OK)
        self.assertEqual(open_response.data["status"], OnlineSession.STATUS_LIVE)
        self.assertEqual(open_response.data["joinUrl"], "https://teams.microsoft.com/admin-live")

        sync_response = admin_client.post(f"/online/admin/sessions/{session.id}/attendance/sync/", format="json")
        self.assertEqual(sync_response.status_code, status.HTTP_200_OK)
        self.assertIn(
            sync_response.data["sync"],
            {"manual_noop", "manual_demo", "graph", "graph_not_configured_demo", "graph_error_demo"},
        )
        session.refresh_from_db()
        self.assertIsNotNone(session.attendance_synced_at)

        detail_response = admin_client.get(f"/online/admin/cohorts/{cohort.id}/")
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        session_payload = next(item for item in detail_response.data["sessions"] if item["id"] == session.id)
        self.assertEqual(session_payload["joinUrl"], "https://teams.microsoft.com/admin-live")

    def test_admin_session_list_supports_filters_and_returns_operational_fields(self):
        _, teacher = self._create_teacher(index=23)
        admin_user = self._create_admin_user(index=23)
        course = self._create_course(slug="admin-session-list", trial_available=False, price_amount=Decimal("89.00"))
        other_course = self._create_course(slug="admin-session-list-other", trial_available=False, price_amount=Decimal("59.00"))
        cohort = self._create_cohort(course=course, group_code="ADMIN_LIST_G1", capacity=8, teacher=teacher)
        other_cohort = self._create_cohort(course=other_course, group_code="ADMIN_LIST_G2", capacity=8, teacher=teacher)
        session = OnlineSession.objects.create(
            cohort=cohort,
            title="Primary Session",
            starts_at=timezone.now() + timedelta(hours=6),
            ends_at=timezone.now() + timedelta(hours=8),
            status=OnlineSession.STATUS_SCHEDULED,
            join_url="https://teams.microsoft.com/list-primary",
            recording_url="https://videos.example.com/list-primary.mp4",
            attendance_synced_at=timezone.now(),
            is_completed=False,
        )
        OnlineSession.objects.create(
            cohort=other_cohort,
            title="Secondary Session",
            starts_at=timezone.now() + timedelta(days=1),
            ends_at=timezone.now() + timedelta(days=1, hours=2),
            status=OnlineSession.STATUS_ENDED,
            join_url="",
            recording_url="",
            is_completed=True,
        )

        checkout_payload = {
            "course_slug": course.slug,
            "cohort_id": cohort.id,
            "email": "admin.session.list.student@example.com",
            "password": "StrongPass12345",
            "first_name": "Admin",
            "last_name": "List",
            "preferred_language": "de",
            "accept_terms": True,
            "idempotency_key": "admin-session-list-1",
        }
        checkout_response = self.client.post("/online/public/checkout/mock/", checkout_payload, format="json")
        self.assertEqual(checkout_response.status_code, status.HTTP_201_CREATED)
        enrollment = OnlineEnrollment.objects.get(profile__user__email="admin.session.list.student@example.com")
        OnlineAttendance.objects.create(
            enrollment=enrollment,
            session=session,
            status=OnlineAttendance.STATUS_PRESENT,
        )

        admin_client = APIClient()
        admin_client.force_authenticate(user=admin_user)
        response = admin_client.get(
            "/online/admin/sessions/",
            {
                "course_id": course.id,
                "cohort_id": cohort.id,
                "status": OnlineSession.STATUS_SCHEDULED,
                "teacher_id": teacher.id,
                "attendance_synced": "true",
                "has_join_url": "true",
                "has_recording": "true",
                "q": "Primary",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        payload = response.data["results"][0]
        self.assertEqual(payload["id"], session.id)
        self.assertEqual(payload["courseId"], course.id)
        self.assertEqual(payload["cohortId"], cohort.id)
        self.assertEqual(payload["teacherId"], teacher.id)
        self.assertEqual(payload["teacherName"], f"{teacher.Vorname} {teacher.Nachname}")
        self.assertEqual(payload["joinUrl"], "https://teams.microsoft.com/list-primary")
        self.assertEqual(payload["recordingUrl"], "https://videos.example.com/list-primary.mp4")
        self.assertEqual(payload["attendanceSummary"]["present"], 1)
        self.assertEqual(payload["attendanceSummary"]["unknown"], 0)
        self.assertIsNotNone(payload["attendanceSyncedAt"])

    def test_admin_bulk_session_action_reports_partial_failures(self):
        _, teacher = self._create_teacher(index=24)
        admin_user = self._create_admin_user(index=24)
        course = self._create_course(slug="admin-bulk-actions", trial_available=False, price_amount=Decimal("89.00"))
        cohort = self._create_cohort(course=course, group_code="ADMIN_BULK_G1", capacity=8, teacher=teacher)
        first_session = OnlineSession.objects.create(
            cohort=cohort,
            title="Bulk Session One",
            starts_at=timezone.now() + timedelta(hours=2),
            ends_at=timezone.now() + timedelta(hours=4),
            status=OnlineSession.STATUS_SCHEDULED,
            join_url="https://teams.microsoft.com/bulk-one",
            is_completed=False,
        )
        second_session = OnlineSession.objects.create(
            cohort=cohort,
            title="Bulk Session Two",
            starts_at=timezone.now() + timedelta(hours=5),
            ends_at=timezone.now() + timedelta(hours=7),
            status=OnlineSession.STATUS_SCHEDULED,
            join_url="https://teams.microsoft.com/bulk-two",
            is_completed=False,
        )

        admin_client = APIClient()
        admin_client.force_authenticate(user=admin_user)
        response = admin_client.post(
            "/online/admin/sessions/bulk/",
            {
                "action": "open",
                "sessionIds": [first_session.id, second_session.id],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["processedCount"], 2)
        self.assertEqual(response.data["succeededCount"], 1)
        self.assertEqual(response.data["failedCount"], 1)
        first_result = response.data["results"][0]
        second_result = response.data["results"][1]
        self.assertTrue(first_result["ok"])
        self.assertEqual(first_result["session"]["status"], OnlineSession.STATUS_LIVE)
        self.assertFalse(second_result["ok"])
        self.assertIn("Another live session", second_result["error"])

        first_session.refresh_from_db()
        second_session.refresh_from_db()
        self.assertEqual(first_session.status, OnlineSession.STATUS_LIVE)
        self.assertEqual(second_session.status, OnlineSession.STATUS_SCHEDULED)

    def test_admin_open_session_auto_creates_join_url_when_missing(self):
        _, teacher = self._create_teacher(index=22)
        admin_user = self._create_admin_user(index=22)
        course = self._create_course(slug="admin-auto-create", trial_available=False, price_amount=Decimal("89.00"))
        cohort = self._create_cohort(course=course, group_code="ADMIN_AUTO_G1", capacity=8, teacher=teacher)
        session = OnlineSession.objects.create(
            cohort=cohort,
            title="Admin Auto Create Session",
            starts_at=timezone.now() + timedelta(hours=2),
            ends_at=timezone.now() + timedelta(hours=4),
            status=OnlineSession.STATUS_SCHEDULED,
            join_url="",
            is_completed=False,
        )

        admin_client = APIClient()
        admin_client.force_authenticate(user=admin_user)

        def _mock_create(*, session):
            session.join_url = "https://teams.microsoft.com/l/meetup-join/admin-auto-created"
            session.provider_meeting_id = "admin_meeting_1"
            session.save(update_fields=["join_url", "provider_meeting_id", "updated_at"])
            return None

        with patch("apps.online.views.create_online_meeting_for_session", side_effect=_mock_create):
            open_response = admin_client.post(f"/online/admin/sessions/{session.id}/open/", format="json")

        self.assertEqual(open_response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            open_response.data["joinUrl"],
            "https://teams.microsoft.com/l/meetup-join/admin-auto-created",
        )
        self.assertEqual(open_response.data["status"], OnlineSession.STATUS_LIVE)

    @override_settings(ONLINE_PAYMENT_MODE="free", ONLINE_ATTENDANCE_SYNC_MODE="demo")
    def test_admin_can_end_live_session_and_auto_sync_attendance(self):
        _, teacher = self._create_teacher(index=23)
        admin_user = self._create_admin_user(index=23)
        course = self._create_course(slug="admin-end-course", trial_available=False, price_amount=Decimal("89.00"))
        cohort = self._create_cohort(course=course, group_code="ADMIN_END_G1", capacity=8, teacher=teacher)
        session = OnlineSession.objects.create(
            cohort=cohort,
            title="Admin Live Session To End",
            starts_at=timezone.now() - timedelta(hours=1),
            ends_at=timezone.now() - timedelta(minutes=5),
            status=OnlineSession.STATUS_LIVE,
            join_url="https://teams.microsoft.com/admin-live-to-end",
            is_completed=False,
        )

        checkout_payload = {
            "course_slug": course.slug,
            "cohort_id": cohort.id,
            "email": "admin.end.student@example.com",
            "password": "StrongPass12345",
            "first_name": "Admin",
            "last_name": "End",
            "preferred_language": "de",
            "accept_terms": True,
            "idempotency_key": "admin-end-start-1",
        }
        checkout_response = self.client.post("/online/public/checkout/start/", checkout_payload, format="json")
        self.assertEqual(checkout_response.status_code, status.HTTP_201_CREATED)

        admin_client = APIClient()
        admin_client.force_authenticate(user=admin_user)
        end_response = admin_client.post(f"/online/admin/sessions/{session.id}/end/", format="json")

        self.assertEqual(end_response.status_code, status.HTTP_200_OK)
        self.assertEqual(end_response.data["status"], OnlineSession.STATUS_ENDED)
        self.assertIsNotNone(end_response.data.get("sync"))

        session.refresh_from_db()
        cohort.refresh_from_db()
        self.assertEqual(session.status, OnlineSession.STATUS_ENDED)
        self.assertTrue(session.is_completed)
        self.assertIsNotNone(session.attendance_synced_at)
        self.assertEqual(cohort.status, OnlineCohort.STATUS_FINISHED)

        attendance = OnlineAttendance.objects.get(session=session)
        self.assertEqual(attendance.status, OnlineAttendance.STATUS_ABSENT)

    def test_teacher_can_open_session_and_trigger_attendance_sync(self):
        teacher_user, teacher = self._create_teacher(index=11)
        course = self._create_course(slug="teacher-course", trial_available=False, price_amount=Decimal("89.00"))
        cohort = self._create_cohort(course=course, group_code="TEACH_G1", capacity=8, teacher=teacher)
        session = OnlineSession.objects.create(
            cohort=cohort,
            title="Live Session",
            starts_at=timezone.now() + timedelta(hours=2),
            ends_at=timezone.now() + timedelta(hours=4),
            status=OnlineSession.STATUS_SCHEDULED,
            join_url="https://teams.microsoft.com/",
            is_completed=False,
        )

        client = APIClient()
        client.force_authenticate(user=teacher_user)

        open_response = client.post(f"/online/teacher/sessions/{session.id}/open/", format="json")
        self.assertEqual(open_response.status_code, status.HTTP_200_OK)
        self.assertEqual(open_response.data["status"], OnlineSession.STATUS_LIVE)

        sync_response = client.post(f"/online/teacher/sessions/{session.id}/attendance/sync/", format="json")
        self.assertEqual(sync_response.status_code, status.HTTP_200_OK)
        self.assertIn(
            sync_response.data["sync"],
            {"manual_noop", "manual_demo", "graph", "graph_not_configured_demo", "graph_error_demo"},
        )
        session.refresh_from_db()
        self.assertIsNotNone(session.attendance_synced_at)

    def test_teacher_workspace_returns_profile_courses_materials_and_recordings(self):
        teacher_user, teacher = self._create_teacher(index=41)
        course = self._create_course(slug="teacher-workspace-course", trial_available=False, price_amount=Decimal("89.00"))
        cohort = self._create_cohort(course=course, group_code="TEACH_WS_G1", capacity=8, teacher=teacher)
        OnlineCourseMaterial.objects.create(
            course=course,
            title="Curator Guide",
            description="Operational notes",
            material_type=OnlineCourseMaterial.MATERIAL_RESOURCE,
            language="en",
            link_url="https://example.com/guide.pdf",
            is_active=True,
        )
        session = OnlineSession.objects.create(
            cohort=cohort,
            title="Recorded Session",
            starts_at=timezone.now() + timedelta(days=1),
            ends_at=timezone.now() + timedelta(days=1, hours=2),
            status=OnlineSession.STATUS_SCHEDULED,
            join_url="https://teams.microsoft.com/teacher-workspace",
            recording_url="https://example.com/recording.mp4",
            is_completed=False,
        )

        client = APIClient()
        client.force_authenticate(user=teacher_user)
        response = client.get("/online/teacher/workspace/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["profile"]["firstName"], teacher.Vorname)
        self.assertEqual(response.data["summary"]["courses"], 1)
        self.assertEqual(len(response.data["courses"]), 1)
        self.assertEqual(response.data["courses"][0]["slug"], course.slug)
        self.assertEqual(len(response.data["cohorts"]), 1)
        self.assertEqual(response.data["materials"][0]["title"], "Curator Guide")
        self.assertEqual(response.data["recordings"][0]["id"], session.id)
        self.assertEqual(response.data["upcomingSessions"][0]["id"], session.id)

    def test_teacher_can_update_own_profile(self):
        teacher_user, teacher = self._create_teacher(index=42)
        client = APIClient()
        client.force_authenticate(user=teacher_user)

        response = client.patch(
            "/online/teacher/profile/",
            {
                "firstName": "Updated",
                "lastName": "Teacher",
                "privateEmail": "updated.private@example.com",
                "phone": "+49123456789",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        teacher.refresh_from_db()
        teacher_user.refresh_from_db()
        self.assertEqual(teacher.Vorname, "Updated")
        self.assertEqual(teacher.Nachname, "Teacher")
        self.assertEqual(teacher.Private_Email, "updated.private@example.com")
        self.assertEqual(teacher.Telefonnummer, "+49123456789")
        self.assertEqual(teacher_user.first_name, "Updated")
        self.assertEqual(teacher_user.last_name, "Teacher")

    @override_settings(ONLINE_FEEDBACK_RECEIVER_EMAIL="support@example.com")
    def test_teacher_can_submit_feedback_message(self):
        teacher_user, teacher = self._create_teacher(index=43)
        client = APIClient()
        client.force_authenticate(user=teacher_user)

        with patch("apps.online.views.send_feedback_notification", return_value=True) as send_mock:
            response = client.post(
                "/online/teacher/feedback/",
                {
                    "subject": "Need updated slides",
                    "message": "The cohort needs refreshed material before the next live session.",
                },
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        feedback = OnlineFeedbackMessage.objects.get(id=response.data["id"])
        self.assertEqual(feedback.full_name, f"{teacher.Vorname} {teacher.Nachname}")
        self.assertEqual(feedback.email, teacher.Schule_Email)
        self.assertEqual(feedback.source_page, "teacher_workspace")
        send_mock.assert_called_once()

    def test_teacher_cannot_open_second_live_session_in_same_cohort(self):
        teacher_user, teacher = self._create_teacher(index=311)
        course = self._create_course(slug="teacher-live-guard", trial_available=False, price_amount=Decimal("89.00"))
        cohort = self._create_cohort(course=course, group_code="TEACH_LIVE_G1", capacity=8, teacher=teacher)
        live_session = OnlineSession.objects.create(
            cohort=cohort,
            title="Already Live",
            starts_at=timezone.now() - timedelta(minutes=15),
            ends_at=timezone.now() + timedelta(minutes=45),
            status=OnlineSession.STATUS_LIVE,
            join_url="https://teams.microsoft.com/live-existing",
            is_completed=False,
        )
        scheduled_session = OnlineSession.objects.create(
            cohort=cohort,
            title="Next Session",
            starts_at=timezone.now() + timedelta(hours=2),
            ends_at=timezone.now() + timedelta(hours=4),
            status=OnlineSession.STATUS_SCHEDULED,
            join_url="https://teams.microsoft.com/live-next",
            is_completed=False,
        )

        client = APIClient()
        client.force_authenticate(user=teacher_user)
        response = client.post(f"/online/teacher/sessions/{scheduled_session.id}/open/", format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Another live session", response.data.get("detail", ""))
        live_session.refresh_from_db()
        scheduled_session.refresh_from_db()
        self.assertEqual(live_session.status, OnlineSession.STATUS_LIVE)
        self.assertEqual(scheduled_session.status, OnlineSession.STATUS_SCHEDULED)

    def test_teacher_open_session_auto_creates_join_url_when_missing(self):
        teacher_user, teacher = self._create_teacher(index=211)
        course = self._create_course(slug="teacher-auto-create", trial_available=False, price_amount=Decimal("89.00"))
        cohort = self._create_cohort(course=course, group_code="TEACH_AUTO_G1", capacity=8, teacher=teacher)
        session = OnlineSession.objects.create(
            cohort=cohort,
            title="Auto Create Session",
            starts_at=timezone.now() + timedelta(hours=2),
            ends_at=timezone.now() + timedelta(hours=4),
            status=OnlineSession.STATUS_SCHEDULED,
            join_url="",
            is_completed=False,
        )

        client = APIClient()
        client.force_authenticate(user=teacher_user)

        def _mock_create(*, session):
            session.join_url = "https://teams.microsoft.com/l/meetup-join/auto-created"
            session.provider_meeting_id = "meeting_auto_1"
            session.save(update_fields=["join_url", "provider_meeting_id", "updated_at"])
            return None

        with patch("apps.online.views.create_online_meeting_for_session", side_effect=_mock_create):
            open_response = client.post(f"/online/teacher/sessions/{session.id}/open/", format="json")

        self.assertEqual(open_response.status_code, status.HTTP_200_OK)
        self.assertEqual(open_response.data["joinUrl"], "https://teams.microsoft.com/l/meetup-join/auto-created")
        self.assertEqual(open_response.data["status"], OnlineSession.STATUS_LIVE)

        session.refresh_from_db()
        self.assertEqual(session.provider_meeting_id, "meeting_auto_1")
        self.assertEqual(session.join_url, "https://teams.microsoft.com/l/meetup-join/auto-created")

    def test_teacher_open_session_returns_error_when_auto_create_fails(self):
        teacher_user, teacher = self._create_teacher(index=212)
        course = self._create_course(slug="teacher-auto-create-fail", trial_available=False, price_amount=Decimal("89.00"))
        cohort = self._create_cohort(course=course, group_code="TEACH_AUTO_FAIL_G1", capacity=8, teacher=teacher)
        session = OnlineSession.objects.create(
            cohort=cohort,
            title="Auto Create Session Fail",
            starts_at=timezone.now() + timedelta(hours=2),
            ends_at=timezone.now() + timedelta(hours=4),
            status=OnlineSession.STATUS_SCHEDULED,
            join_url="",
            is_completed=False,
        )

        client = APIClient()
        client.force_authenticate(user=teacher_user)

        with patch(
            "apps.online.views.create_online_meeting_for_session",
            side_effect=GraphSyncRequestError("Access denied"),
        ):
            open_response = client.post(f"/online/teacher/sessions/{session.id}/open/", format="json")

        self.assertEqual(open_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("auto-create failed", open_response.data.get("detail", ""))

    @override_settings(ONLINE_PAYMENT_MODE="free", ONLINE_ATTENDANCE_SYNC_MODE="demo")
    def test_teacher_can_end_live_session_and_auto_sync_attendance(self):
        teacher_user, teacher = self._create_teacher(index=213)
        course = self._create_course(slug="teacher-end-course", trial_available=False, price_amount=Decimal("89.00"))
        cohort = self._create_cohort(course=course, group_code="TEACH_END_G1", capacity=8, teacher=teacher)
        session = OnlineSession.objects.create(
            cohort=cohort,
            title="Live Session To End",
            starts_at=timezone.now() - timedelta(hours=1),
            ends_at=timezone.now() - timedelta(minutes=5),
            status=OnlineSession.STATUS_LIVE,
            join_url="https://teams.microsoft.com/live-to-end",
            is_completed=False,
        )

        checkout_payload = {
            "course_slug": course.slug,
            "cohort_id": cohort.id,
            "email": "teacher.end.student@example.com",
            "password": "StrongPass12345",
            "first_name": "Teacher",
            "last_name": "End",
            "preferred_language": "de",
            "accept_terms": True,
            "idempotency_key": "teacher-end-start-1",
        }
        checkout_response = self.client.post("/online/public/checkout/start/", checkout_payload, format="json")
        self.assertEqual(checkout_response.status_code, status.HTTP_201_CREATED)

        teacher_client = APIClient()
        teacher_client.force_authenticate(user=teacher_user)
        end_response = teacher_client.post(f"/online/teacher/sessions/{session.id}/end/", format="json")

        self.assertEqual(end_response.status_code, status.HTTP_200_OK)
        self.assertEqual(end_response.data["status"], OnlineSession.STATUS_ENDED)
        self.assertIsNotNone(end_response.data.get("sync"))

        session.refresh_from_db()
        cohort.refresh_from_db()
        self.assertEqual(session.status, OnlineSession.STATUS_ENDED)
        self.assertTrue(session.is_completed)
        self.assertIsNotNone(session.attendance_synced_at)
        self.assertEqual(cohort.status, OnlineCohort.STATUS_FINISHED)

        attendance = OnlineAttendance.objects.get(session=session)
        self.assertEqual(attendance.status, OnlineAttendance.STATUS_ABSENT)

    @override_settings(
        ONLINE_PAYMENT_MODE="free",
        ONLINE_ATTENDANCE_SYNC_MODE="graph",
        ONLINE_GRAPH_CLIENT_SECRET="",
    )
    def test_teacher_graph_sync_falls_back_when_not_configured(self):
        teacher_user, teacher = self._create_teacher(index=111)
        course = self._create_course(slug="graph-fallback-course", trial_available=False, price_amount=Decimal("89.00"))
        cohort = self._create_cohort(course=course, group_code="GRAPH_FB_G1", capacity=8, teacher=teacher)
        session = OnlineSession.objects.create(
            cohort=cohort,
            title="Graph Fallback Session",
            starts_at=timezone.now() + timedelta(hours=2),
            ends_at=timezone.now() + timedelta(hours=4),
            status=OnlineSession.STATUS_LIVE,
            join_url="https://teams.microsoft.com/l/meetup-join/graph-fallback",
            is_completed=False,
        )

        checkout_payload = {
            "course_slug": course.slug,
            "cohort_id": cohort.id,
            "email": "graph.fallback.student@example.com",
            "password": "StrongPass12345",
            "first_name": "Graph",
            "last_name": "Fallback",
            "preferred_language": "de",
            "accept_terms": True,
            "idempotency_key": "graph-fallback-start-1",
        }
        checkout_response = self.client.post("/online/public/checkout/start/", checkout_payload, format="json")
        self.assertEqual(checkout_response.status_code, status.HTTP_201_CREATED)

        teacher_client = APIClient()
        teacher_client.force_authenticate(user=teacher_user)
        sync_response = teacher_client.post(f"/online/teacher/sessions/{session.id}/attendance/sync/", format="json")
        self.assertEqual(sync_response.status_code, status.HTTP_200_OK)
        self.assertIn(sync_response.data["sync"], {"graph_not_configured_demo", "graph_error_demo", "graph"})

    @override_settings(ONLINE_PAYMENT_MODE="free", ONLINE_ATTENDANCE_SYNC_MODE="demo")
    def test_student_join_marks_attendance_and_admin_report_reflects_presence(self):
        teacher_user, teacher = self._create_teacher(index=12)
        course = self._create_course(slug="join-report-course", trial_available=False, price_amount=Decimal("79.00"))
        cohort = self._create_cohort(course=course, group_code="JOIN_REPORT_G1", capacity=6, teacher=teacher)
        session = OnlineSession.objects.create(
            cohort=cohort,
            title="Join Report Session",
            starts_at=timezone.now() + timedelta(hours=2),
            ends_at=timezone.now() + timedelta(hours=4),
            status=OnlineSession.STATUS_SCHEDULED,
            join_url="https://teams.microsoft.com/join-report",
            is_completed=False,
        )

        checkout_payload = {
            "course_slug": course.slug,
            "cohort_id": cohort.id,
            "email": "join.report.student@example.com",
            "password": "StrongPass12345",
            "first_name": "Join",
            "last_name": "Report",
            "preferred_language": "de",
            "accept_terms": True,
            "idempotency_key": "join-report-start-1",
        }
        checkout_response = self.client.post("/online/public/checkout/start/", checkout_payload, format="json")
        self.assertEqual(checkout_response.status_code, status.HTTP_201_CREATED)
        self._assert_auth_cookies(checkout_response, scope="student")

        join_response = self.client.post(f"/online/student/sessions/{session.id}/join/", format="json")
        self.assertEqual(join_response.status_code, status.HTTP_200_OK)
        self.assertEqual(join_response.data["attendanceStatus"], OnlineAttendance.STATUS_PRESENT)

        attendance = OnlineAttendance.objects.filter(session=session).first()
        self.assertIsNotNone(attendance)
        assert attendance is not None
        self.assertEqual(attendance.status, OnlineAttendance.STATUS_PRESENT)
        self.assertIsNotNone(attendance.joined_at)

        admin_user = User.objects.create_user(
            email="join.report.admin@example.com",
            username="join_report_admin",
            password="AdminPass12345",
            is_admin=True,
        )
        admin_client = APIClient()
        admin_client.force_authenticate(user=admin_user)
        detail_response = admin_client.get(f"/online/admin/cohorts/{cohort.id}/")
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)

        session_payload = next(item for item in detail_response.data["sessions"] if item["id"] == session.id)
        self.assertEqual(session_payload["attendanceSummary"]["present"], 1)

    @override_settings(ONLINE_PAYMENT_MODE="free", ONLINE_ATTENDANCE_SYNC_MODE="demo")
    def test_teacher_sync_for_ended_session_sets_absent_when_student_did_not_join(self):
        teacher_user, teacher = self._create_teacher(index=13)
        course = self._create_course(slug="ended-sync-course", trial_available=False, price_amount=Decimal("89.00"))
        cohort = self._create_cohort(course=course, group_code="ENDED_SYNC_G1", capacity=6, teacher=teacher)
        session = OnlineSession.objects.create(
            cohort=cohort,
            title="Ended Session",
            starts_at=timezone.now() - timedelta(hours=3),
            ends_at=timezone.now() - timedelta(hours=1),
            status=OnlineSession.STATUS_ENDED,
            join_url="https://teams.microsoft.com/ended-session",
            is_completed=True,
        )

        checkout_payload = {
            "course_slug": course.slug,
            "cohort_id": cohort.id,
            "email": "ended.sync.student@example.com",
            "password": "StrongPass12345",
            "first_name": "Ended",
            "last_name": "Sync",
            "preferred_language": "de",
            "accept_terms": True,
            "idempotency_key": "ended-sync-start-1",
        }
        checkout_response = self.client.post("/online/public/checkout/start/", checkout_payload, format="json")
        self.assertEqual(checkout_response.status_code, status.HTTP_201_CREATED)

        teacher_client = APIClient()
        teacher_client.force_authenticate(user=teacher_user)
        sync_response = teacher_client.post(f"/online/teacher/sessions/{session.id}/attendance/sync/", format="json")
        self.assertEqual(sync_response.status_code, status.HTTP_200_OK)
        self.assertEqual(sync_response.data["attendanceSummary"]["absent"], 1)

        attendance = OnlineAttendance.objects.filter(session=session).first()
        self.assertIsNotNone(attendance)
        assert attendance is not None
        self.assertEqual(attendance.status, OnlineAttendance.STATUS_ABSENT)

    @override_settings(ONLINE_PAYMENT_MODE="free")
    def test_checkout_start_free_mode_grants_access_without_webhook(self):
        course = self._create_course(slug="checkout-free", trial_available=False, price_amount=Decimal("159.00"))
        cohort = self._create_cohort(course=course, group_code="FREE_G1", capacity=5)

        payload = {
            "course_slug": course.slug,
            "cohort_id": cohort.id,
            "email": "free.student@example.com",
            "password": "StrongPass12345",
            "first_name": "Free",
            "last_name": "Student",
            "preferred_language": "de",
            "accept_terms": True,
            "idempotency_key": "free-order-1",
        }

        response = self.client.post("/online/public/checkout/start/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["status"], OnlineOrder.STATUS_PAID)
        self._assert_auth_cookies(response, scope="student")
        self.assertIn("checkoutUrl", response.data)

        order = OnlineOrder.objects.get(id=response.data["orderId"])
        self.assertEqual(order.status, OnlineOrder.STATUS_PAID)
        self.assertEqual(order.provider, OnlineOrder.PROVIDER_PAYPAL)
        self.assertEqual(
            OnlineEnrollment.objects.filter(order=order, status=OnlineEnrollment.STATUS_ACTIVE).count(),
            1,
        )

    @override_settings(ONLINE_PAYMENT_MODE="mock")
    def test_checkout_start_creates_pending_order_with_checkout_url(self):
        course = self._create_course(slug="checkout-start", trial_available=False, price_amount=Decimal("159.00"))
        cohort = self._create_cohort(course=course, group_code="START_G1", capacity=5)

        payload = {
            "course_slug": course.slug,
            "cohort_id": cohort.id,
            "email": "pending.student@example.com",
            "password": "StrongPass12345",
            "first_name": "Pending",
            "last_name": "Student",
            "preferred_language": "de",
            "provider": "paypal",
            "accept_terms": True,
            "idempotency_key": "start-order-1",
        }

        response = self.client.post("/online/public/checkout/start/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("checkoutUrl", response.data)
        self.assertEqual(response.data["status"], OnlineOrder.STATUS_PENDING)

        order = OnlineOrder.objects.get(id=response.data["orderId"])
        self.assertEqual(order.status, OnlineOrder.STATUS_PENDING)
        self.assertTrue(order.checkout_url)
        self.assertTrue(order.provider_payment_id)

    @override_settings(ONLINE_PAYMENT_MODE="mock")
    def test_payment_webhook_paid_is_idempotent_and_creates_enrollment(self):
        course = self._create_course(slug="webhook-paid", trial_available=False, price_amount=Decimal("99.00"))
        cohort = self._create_cohort(course=course, group_code="WEBHOOK_G1", capacity=3)

        start_payload = {
            "course_slug": course.slug,
            "cohort_id": cohort.id,
            "email": "webhook.student@example.com",
            "password": "StrongPass12345",
            "first_name": "Webhook",
            "last_name": "Student",
            "preferred_language": "de",
            "provider": "paypal",
            "accept_terms": True,
            "idempotency_key": "webhook-start-1",
        }
        start_response = self.client.post("/online/public/checkout/start/", start_payload, format="json")
        self.assertEqual(start_response.status_code, status.HTTP_201_CREATED)
        order = OnlineOrder.objects.get(id=start_response.data["orderId"])

        webhook_payload = {
            "eventId": "evt_paid_001",
            "orderId": order.id,
            "status": "paid",
            "providerPaymentId": order.provider_payment_id,
        }
        first_webhook = self.client.post("/online/webhooks/payments/paypal/", webhook_payload, format="json")
        self.assertEqual(first_webhook.status_code, status.HTTP_200_OK)
        self.assertFalse(first_webhook.data.get("alreadyProcessed", False))

        order.refresh_from_db()
        self.assertEqual(order.status, OnlineOrder.STATUS_PAID)
        self.assertEqual(OnlineEnrollment.objects.filter(order=order, status=OnlineEnrollment.STATUS_ACTIVE).count(), 1)

        second_webhook = self.client.post("/online/webhooks/payments/paypal/", webhook_payload, format="json")
        self.assertEqual(second_webhook.status_code, status.HTTP_200_OK)
        self.assertTrue(second_webhook.data.get("alreadyProcessed", False))
        self.assertEqual(OnlinePaymentEvent.objects.filter(provider="paypal", event_id="evt_paid_001").count(), 1)

    @override_settings(ONLINE_PAYMENT_WEBHOOK_REQUIRE_SIGNATURE=True, ONLINE_PAYMENT_WEBHOOK_SECRET="")
    def test_payment_webhook_rejects_missing_required_signature_secret(self):
        response = self.client.post(
            "/online/webhooks/payments/paypal/",
            {"eventId": "evt_unsigned"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @override_settings(ONLINE_PAYMENT_WEBHOOK_REQUIRE_SIGNATURE=True, ONLINE_PAYMENT_WEBHOOK_SECRET="webhook-secret")
    def test_payment_webhook_rejects_invalid_signature(self):
        response = self.client.post(
            "/online/webhooks/payments/paypal/",
            {"eventId": "evt_bad_signature"},
            format="json",
            HTTP_X_ONLINE_PAYMENT_SIGNATURE="wrong-secret",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    @override_settings(ONLINE_PAYMENT_MODE="mock")
    def test_checkout_status_returns_auth_after_paid_webhook(self):
        course = self._create_course(slug="status-paid", trial_available=False, price_amount=Decimal("119.00"))
        cohort = self._create_cohort(course=course, group_code="STATUS_G1", capacity=3)

        start_payload = {
            "course_slug": course.slug,
            "cohort_id": cohort.id,
            "email": "status.student@example.com",
            "password": "StrongPass12345",
            "first_name": "Status",
            "last_name": "Student",
            "preferred_language": "de",
            "provider": "paypal",
            "accept_terms": True,
            "idempotency_key": "status-start-1",
        }
        start_response = self.client.post("/online/public/checkout/start/", start_payload, format="json")
        self.assertEqual(start_response.status_code, status.HTTP_201_CREATED)
        order = OnlineOrder.objects.get(id=start_response.data["orderId"])

        self.client.post(
            "/online/webhooks/payments/paypal/",
            {
                "eventId": "evt_paid_002",
                "orderId": order.id,
                "status": "paid",
                "providerPaymentId": order.provider_payment_id,
            },
            format="json",
        )

        status_response = self.client.get(
            f"/online/public/checkout/status/{order.id}/",
            {"token": str(order.checkout_token)},
        )
        self.assertEqual(status_response.status_code, status.HTTP_200_OK)
        self.assertEqual(status_response.data["status"], OnlineOrder.STATUS_PAID)
        self._assert_auth_cookies(status_response, scope="student")

    @override_settings(ONLINE_PAYMENT_MODE="mock")
    def test_admin_refund_revokes_active_enrollment(self):
        course = self._create_course(slug="admin-refund", trial_available=False, price_amount=Decimal("149.00"))
        cohort = self._create_cohort(course=course, group_code="REFUND_G1", capacity=3)

        start_payload = {
            "course_slug": course.slug,
            "cohort_id": cohort.id,
            "email": "refund.student@example.com",
            "password": "StrongPass12345",
            "first_name": "Refund",
            "last_name": "Student",
            "preferred_language": "de",
            "provider": "paypal",
            "accept_terms": True,
            "idempotency_key": "refund-start-1",
        }
        start_response = self.client.post("/online/public/checkout/start/", start_payload, format="json")
        self.assertEqual(start_response.status_code, status.HTTP_201_CREATED)
        order = OnlineOrder.objects.get(id=start_response.data["orderId"])

        webhook_response = self.client.post(
            "/online/webhooks/payments/paypal/",
            {
                "eventId": "evt_paid_003",
                "orderId": order.id,
                "status": "paid",
                "providerPaymentId": order.provider_payment_id,
            },
            format="json",
        )
        self.assertEqual(webhook_response.status_code, status.HTTP_200_OK)

        admin_user = User.objects.create_user(
            email="refund.admin@example.com",
            username="refund_admin",
            password="AdminPass12345",
            is_admin=True,
        )
        admin_client = APIClient()
        admin_client.force_authenticate(user=admin_user)

        refund_response = admin_client.post(
            f"/online/admin/orders/{order.id}/refund/",
            {"reason": "manual test refund"},
            format="json",
        )
        self.assertEqual(refund_response.status_code, status.HTTP_200_OK)

        order.refresh_from_db()
        self.assertEqual(order.status, OnlineOrder.STATUS_REFUNDED)
        self.assertEqual(
            OnlineEnrollment.objects.filter(order=order, status=OnlineEnrollment.STATUS_REVOKED).count(),
            1,
        )

    @override_settings(ONLINE_PAYMENT_MODE="free")
    def test_magic_link_request_creates_token_for_existing_student(self):
        course = self._create_course(slug="magic-link-course", trial_available=False, price_amount=Decimal("129.00"))
        cohort = self._create_cohort(course=course, group_code="MAGIC_G1", capacity=3)

        checkout_payload = {
            "course_slug": course.slug,
            "cohort_id": cohort.id,
            "email": "magic.student@example.com",
            "password": "StrongPass12345",
            "first_name": "Magic",
            "last_name": "Student",
            "preferred_language": "de",
            "accept_terms": True,
            "idempotency_key": "magic-start-1",
        }
        start_response = self.client.post("/online/public/checkout/start/", checkout_payload, format="json")
        self.assertEqual(start_response.status_code, status.HTTP_201_CREATED)

        response = self.client.post(
            "/online/public/magic-link/request/",
            {"email": "magic.student@example.com"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data.get("emailSent", False))
        self.assertEqual(OnlineMagicLinkToken.objects.count(), 1)
        token_obj = OnlineMagicLinkToken.objects.first()
        self.assertIsNotNone(token_obj)
        self.assertGreater(token_obj.expires_at, timezone.now())

    @override_settings(ONLINE_PAYMENT_MODE="free")
    def test_magic_link_portal_sessions_and_calendar_endpoints(self):
        course = self._create_course(slug="portal-course", trial_available=False, price_amount=Decimal("149.00"))
        cohort = self._create_cohort(course=course, group_code="PORTAL_G1", capacity=3)
        session = OnlineSession.objects.create(
            cohort=cohort,
            title="Portal Session 1",
            starts_at=timezone.now() + timedelta(days=1),
            ends_at=timezone.now() + timedelta(days=1, hours=2),
            status=OnlineSession.STATUS_SCHEDULED,
            join_url="https://teams.microsoft.com/portal-lesson",
            is_completed=False,
        )

        checkout_payload = {
            "course_slug": course.slug,
            "cohort_id": cohort.id,
            "email": "portal.student@example.com",
            "password": "StrongPass12345",
            "first_name": "Portal",
            "last_name": "Student",
            "preferred_language": "de",
            "accept_terms": True,
            "idempotency_key": "portal-start-1",
        }
        start_response = self.client.post("/online/public/checkout/start/", checkout_payload, format="json")
        self.assertEqual(start_response.status_code, status.HTTP_201_CREATED)
        order = OnlineOrder.objects.get(id=start_response.data["orderId"])

        raw_token = "portal-token-001"
        OnlineMagicLinkToken.objects.create(
            profile=order.profile,
            cohort=cohort,
            token_hash=hashlib.sha256(raw_token.encode("utf-8")).hexdigest(),
            expires_at=timezone.now() + timedelta(hours=2),
        )

        portal_response = self.client.get("/online/public/portal/", {"token": raw_token})
        self.assertEqual(portal_response.status_code, status.HTTP_200_OK)
        self._assert_auth_cookies(portal_response, scope="student")
        self.assertEqual(len(portal_response.data.get("enrollments", [])), 1)

        sessions_response = self.client.get("/online/public/portal/sessions/", {"token": raw_token})
        self.assertEqual(sessions_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(sessions_response.data.get("results", [])), 1)
        self.assertEqual(sessions_response.data["results"][0]["title"], session.title)

        calendar_response = self.client.get("/online/public/portal/calendar.ics/", {"token": raw_token})
        self.assertEqual(calendar_response.status_code, status.HTTP_200_OK)
        self.assertIn("text/calendar", calendar_response["Content-Type"])
        self.assertIn("BEGIN:VCALENDAR", calendar_response.content.decode("utf-8"))
        self.assertIn("Portal Session 1", calendar_response.content.decode("utf-8"))

    @override_settings(ONLINE_PAYMENT_MODE="free")
    def test_admin_orders_list_and_detail(self):
        course = self._create_course(slug="admin-orders", trial_available=False, price_amount=Decimal("169.00"))
        cohort = self._create_cohort(course=course, group_code="ADMIN_ORDERS_G1", capacity=3)

        checkout_payload = {
            "course_slug": course.slug,
            "cohort_id": cohort.id,
            "email": "orders.student@example.com",
            "password": "StrongPass12345",
            "first_name": "Orders",
            "last_name": "Student",
            "preferred_language": "de",
            "accept_terms": True,
            "idempotency_key": "orders-start-1",
        }
        start_response = self.client.post("/online/public/checkout/start/", checkout_payload, format="json")
        self.assertEqual(start_response.status_code, status.HTTP_201_CREATED)
        order = OnlineOrder.objects.get(id=start_response.data["orderId"])

        admin_user = User.objects.create_user(
            email="orders.admin@example.com",
            username="orders_admin",
            password="AdminPass12345",
            is_admin=True,
        )
        admin_client = APIClient()
        admin_client.force_authenticate(user=admin_user)

        list_response = admin_client.get("/online/admin/orders/")
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertTrue(any(item["id"] == order.id for item in list_response.data.get("results", [])))

        detail_response = admin_client.get(f"/online/admin/orders/{order.id}/")
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.data["id"], order.id)
        self.assertGreaterEqual(len(detail_response.data.get("paymentEvents", [])), 1)

    @override_settings(ONLINE_PAYMENT_MODE="free")
    def test_send_online_session_reminders_command_creates_log(self):
        course = self._create_course(slug="reminder-course", trial_available=False, price_amount=Decimal("109.00"))
        cohort = self._create_cohort(course=course, group_code="REMINDER_G1", capacity=3)
        session = OnlineSession.objects.create(
            cohort=cohort,
            title="Reminder Session",
            starts_at=timezone.now() + timedelta(hours=24, minutes=5),
            ends_at=timezone.now() + timedelta(hours=26, minutes=5),
            status=OnlineSession.STATUS_SCHEDULED,
            join_url="https://teams.microsoft.com/reminder",
            is_completed=False,
        )

        checkout_payload = {
            "course_slug": course.slug,
            "cohort_id": cohort.id,
            "email": "reminder.student@example.com",
            "password": "StrongPass12345",
            "first_name": "Reminder",
            "last_name": "Student",
            "preferred_language": "de",
            "accept_terms": True,
            "idempotency_key": "reminder-start-1",
        }
        start_response = self.client.post("/online/public/checkout/start/", checkout_payload, format="json")
        self.assertEqual(start_response.status_code, status.HTTP_201_CREATED)
        order = OnlineOrder.objects.get(id=start_response.data["orderId"])
        enrollment = OnlineEnrollment.objects.get(order=order)

        call_command("send_online_session_reminders", "--hours", "24", "--window-minutes", "10")

        reminders = OnlineSessionReminder.objects.filter(
            enrollment=enrollment,
            session=session,
            hours_before=24,
        )
        self.assertEqual(reminders.count(), 1)
        self.assertTrue(reminders.first().email_sent)

    @override_settings(ONLINE_PAYMENT_MODE="free", ONLINE_ATTENDANCE_SYNC_MODE="demo")
    def test_sync_online_attendance_batch_sets_synced_timestamp(self):
        teacher_user, teacher = self._create_teacher(index=313)
        course = self._create_course(slug="batch-sync-course", trial_available=False, price_amount=Decimal("79.00"))
        cohort = self._create_cohort(course=course, group_code="BATCH_SYNC_G1", capacity=6, teacher=teacher)
        session = OnlineSession.objects.create(
            cohort=cohort,
            title="Batch Sync Session",
            starts_at=timezone.now() - timedelta(hours=4),
            ends_at=timezone.now() - timedelta(hours=2),
            status=OnlineSession.STATUS_ENDED,
            join_url="https://teams.microsoft.com/batch-sync",
            is_completed=True,
        )

        checkout_payload = {
            "course_slug": course.slug,
            "cohort_id": cohort.id,
            "email": "batch.sync.student@example.com",
            "password": "StrongPass12345",
            "first_name": "Batch",
            "last_name": "Sync",
            "preferred_language": "de",
            "accept_terms": True,
            "idempotency_key": "batch-sync-start-1",
        }
        checkout_response = self.client.post("/online/public/checkout/start/", checkout_payload, format="json")
        self.assertEqual(checkout_response.status_code, status.HTTP_201_CREATED)

        self.assertIsNone(session.attendance_synced_at)
        call_command(
            "sync_online_attendance_batch",
            "--lookback-hours",
            "24",
            "--retry-minutes",
            "0",
            "--limit",
            "20",
        )

        session.refresh_from_db()
        self.assertIsNotNone(session.attendance_synced_at)
        attendance = OnlineAttendance.objects.filter(session=session).first()
        self.assertIsNotNone(attendance)
        assert attendance is not None
        self.assertEqual(attendance.status, OnlineAttendance.STATUS_ABSENT)

    @override_settings(ONLINE_ATTENDANCE_SYNC_MODE="demo")
    def test_sync_online_attendance_batch_respects_retry_window(self):
        course = self._create_course(slug="batch-retry-course", trial_available=False, price_amount=Decimal("59.00"))
        cohort = self._create_cohort(course=course, group_code="BATCH_RETRY_G1", capacity=3)
        session = OnlineSession.objects.create(
            cohort=cohort,
            title="Batch Retry Session",
            starts_at=timezone.now() - timedelta(hours=4),
            ends_at=timezone.now() - timedelta(hours=2),
            status=OnlineSession.STATUS_ENDED,
            is_completed=True,
            attendance_synced_at=timezone.now(),
        )

        with patch("apps.online.management.commands.sync_online_attendance_batch.sync_session_attendance_and_stamp") as sync_mock:
            call_command(
                "sync_online_attendance_batch",
                "--lookback-hours",
                "24",
                "--retry-minutes",
                "30",
                "--limit",
                "20",
            )
        sync_mock.assert_not_called()
        session.refresh_from_db()
        self.assertIsNotNone(session.attendance_synced_at)

    @override_settings(ONLINE_PAYMENT_MODE="free", ONLINE_ATTENDANCE_SYNC_MODE="demo")
    def test_auto_end_online_sessions_command_ends_overdue_live_sessions(self):
        course = self._create_course(slug="auto-end-course", trial_available=False, price_amount=Decimal("59.00"))
        cohort = self._create_cohort(course=course, group_code="AUTO_END_G1", capacity=3)
        session = OnlineSession.objects.create(
            cohort=cohort,
            title="Auto End Session",
            starts_at=timezone.now() - timedelta(hours=3),
            ends_at=timezone.now() - timedelta(minutes=10),
            status=OnlineSession.STATUS_LIVE,
            is_completed=False,
            join_url="https://teams.microsoft.com/auto-end",
        )

        checkout_payload = {
            "course_slug": course.slug,
            "cohort_id": cohort.id,
            "email": "auto.end.student@example.com",
            "password": "StrongPass12345",
            "first_name": "Auto",
            "last_name": "End",
            "preferred_language": "de",
            "accept_terms": True,
            "idempotency_key": "auto-end-start-1",
        }
        self.assertEqual(
            self.client.post("/online/public/checkout/start/", checkout_payload, format="json").status_code,
            status.HTTP_201_CREATED,
        )

        call_command("auto_end_online_sessions", "--grace-minutes", "0", "--limit", "10")

        session.refresh_from_db()
        cohort.refresh_from_db()
        self.assertEqual(session.status, OnlineSession.STATUS_ENDED)
        self.assertTrue(session.is_completed)
        self.assertIsNotNone(session.attendance_synced_at)
        self.assertEqual(cohort.status, OnlineCohort.STATUS_FINISHED)

    @override_settings(ONLINE_PAYMENT_MODE="free", ONLINE_ATTENDANCE_SYNC_MODE="demo")
    def test_full_e2e_flow_registration_teacher_open_student_join_batch_and_admin_report(self):
        teacher_user, teacher = self._create_teacher(index=414)
        admin_user = User.objects.create_user(
            email="online.e2e.admin@example.com",
            username="online_e2e_admin",
            password="AdminPass12345",
            is_admin=True,
        )
        course = self._create_course(slug="e2e-flow-course", trial_available=False, price_amount=Decimal("99.00"))
        cohort = self._create_cohort(course=course, group_code="E2E_FLOW_G1", capacity=8, teacher=teacher)
        session = OnlineSession.objects.create(
            cohort=cohort,
            title="E2E Flow Session",
            starts_at=timezone.now() - timedelta(minutes=40),
            ends_at=timezone.now() - timedelta(minutes=10),
            status=OnlineSession.STATUS_SCHEDULED,
            join_url="",
            is_completed=False,
        )

        checkout_payload = {
            "course_slug": course.slug,
            "cohort_id": cohort.id,
            "email": "online.e2e.student@example.com",
            "password": "StrongPass12345",
            "first_name": "Online",
            "last_name": "E2E",
            "preferred_language": "de",
            "accept_terms": True,
            "idempotency_key": "e2e-flow-start-1",
        }
        checkout_response = self.client.post("/online/public/checkout/start/", checkout_payload, format="json")
        self.assertEqual(checkout_response.status_code, status.HTTP_201_CREATED)
        self._assert_auth_cookies(checkout_response, scope="student")

        login_response = self.client.post(
            "/online/public/auth/login/",
            {"identifier": checkout_payload["email"], "password": checkout_payload["password"]},
            format="json",
        )
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        self._assert_auth_cookies(login_response, scope="student")

        teacher_client = APIClient()
        teacher_client.force_authenticate(user=teacher_user)

        def _mock_create(*, session):
            session.join_url = "https://teams.microsoft.com/l/meetup-join/e2e-auto-created"
            session.provider_meeting_id = "e2e_meeting_1"
            session.save(update_fields=["join_url", "provider_meeting_id", "updated_at"])
            return None

        with patch("apps.online.views.create_online_meeting_for_session", side_effect=_mock_create):
            open_response = teacher_client.post(f"/online/teacher/sessions/{session.id}/open/", format="json")
        self.assertEqual(open_response.status_code, status.HTTP_200_OK)
        self.assertEqual(open_response.data["status"], OnlineSession.STATUS_LIVE)
        self.assertEqual(open_response.data["joinUrl"], "https://teams.microsoft.com/l/meetup-join/e2e-auto-created")

        join_response = self.client.post(f"/online/student/sessions/{session.id}/join/", format="json")
        self.assertEqual(join_response.status_code, status.HTTP_200_OK)
        self.assertEqual(join_response.data["attendanceStatus"], OnlineAttendance.STATUS_PRESENT)

        admin_client = APIClient()
        admin_client.force_authenticate(user=admin_user)
        end_response = admin_client.patch(
            f"/online/admin/sessions/{session.id}/status/",
            {"status": OnlineSession.STATUS_ENDED},
            format="json",
        )
        self.assertEqual(end_response.status_code, status.HTTP_200_OK)

        call_command(
            "sync_online_attendance_batch",
            "--session-id",
            str(session.id),
            "--retry-minutes",
            "0",
            "--limit",
            "10",
        )

        session.refresh_from_db()
        self.assertEqual(session.status, OnlineSession.STATUS_ENDED)
        self.assertTrue(session.is_completed)
        self.assertIsNotNone(session.attendance_synced_at)

        attendance = OnlineAttendance.objects.filter(session=session).first()
        self.assertIsNotNone(attendance)
        assert attendance is not None
        self.assertEqual(attendance.status, OnlineAttendance.STATUS_PRESENT)
        self.assertIsNotNone(attendance.joined_at)

        detail_response = admin_client.get(f"/online/admin/cohorts/{cohort.id}/")
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        session_payload = next(item for item in detail_response.data["sessions"] if item["id"] == session.id)
        self.assertEqual(session_payload["attendanceSummary"]["present"], 1)
        self.assertEqual(session_payload["attendanceSummary"]["absent"], 0)

    def test_setup_online_demo_flow_can_prepare_empty_join_url_for_auto_create(self):
        call_command(
            "setup_online_demo_flow",
            "--teacher-email",
            "setup.auto.teacher@example.com",
            "--course-slug",
            "setup-auto-create-course",
            "--cohort-code",
            "SETUP_AUTO_G1",
            "--students",
            "0",
            "--keep-join-url-empty",
            "--starts-in-minutes",
            "15",
            "--duration-minutes",
            "45",
        )

        session = (
            OnlineSession.objects.filter(cohort__group_code="SETUP_AUTO_G1")
            .order_by("-starts_at", "-id")
            .first()
        )
        self.assertIsNotNone(session)
        assert session is not None
        self.assertEqual(session.join_url or "", "")
        self.assertEqual(session.provider_meeting_id, "")

    def test_staff_login_returns_tokens_for_teacher(self):
        teacher_user, teacher = self._create_teacher()

        response = self.client.post(
            "/online/staff/auth/login/",
            {
                "identifier": teacher_user.email,
                "password": "TeacherPass12345",
                "role": "teacher",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self._assert_auth_cookies(response, scope="staff")
        self.assertEqual(response.data["profile"]["email"], teacher_user.email)
        self.assertTrue(response.data["profile"]["isTeacher"])
        self.assertFalse(response.data["profile"]["isAdmin"])
        self.assertEqual(response.data["profile"]["teacherId"], teacher.id)

    def test_staff_login_returns_tokens_for_admin(self):
        admin_user = self._create_admin_user()

        response = self.client.post(
            "/online/staff/auth/login/",
            {
                "identifier": admin_user.email,
                "password": "AdminPass12345",
                "role": "admin",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self._assert_auth_cookies(response, scope="staff")
        self.assertEqual(response.data["profile"]["email"], admin_user.email)
        self.assertFalse(response.data["profile"]["isTeacher"])
        self.assertTrue(response.data["profile"]["isAdmin"])
        self.assertIsNone(response.data["profile"]["teacherId"])

    def test_student_cookie_refresh_and_logout_endpoints_rotate_cookie_session(self):
        user = User.objects.create_user(
            email="cookie.student@example.com",
            username="cookie_student",
            password="StrongPass12345",
            first_name="Cookie",
            last_name="Student",
        )
        OnlineStudentProfile.objects.create(
            user=user,
            first_name="Cookie",
            last_name="Student",
            preferred_language="en",
        )

        client = APIClient(enforce_csrf_checks=True)
        login_response = client.post(
            "/online/public/auth/login/",
            {"identifier": user.email, "password": "StrongPass12345"},
            format="json",
        )
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        self._assert_auth_cookies(login_response, scope="student")

        csrf_token = client.cookies[settings.CSRF_COOKIE_NAME].value
        refresh_response = client.post(
            "/online/public/auth/refresh/",
            {},
            format="json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        self.assertEqual(refresh_response.status_code, status.HTTP_200_OK)
        self.assertIn(settings.ONLINE_STUDENT_ACCESS_COOKIE_NAME, refresh_response.cookies)
        self.assertNotIn("auth", refresh_response.data)

        logout_response = client.post(
            "/online/public/auth/logout/",
            {},
            format="json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        self.assertEqual(logout_response.status_code, status.HTTP_200_OK)

        me_response = client.get("/online/student/me/")
        self.assertEqual(me_response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_staff_cookie_refresh_and_logout_endpoints_use_staff_cookie_scope(self):
        admin_user = self._create_admin_user(index=27)
        client = APIClient(enforce_csrf_checks=True)

        login_response = client.post(
            "/online/staff/auth/login/",
            {"identifier": admin_user.email, "password": "AdminPass12345", "role": "admin"},
            format="json",
        )
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        self._assert_auth_cookies(login_response, scope="staff")

        csrf_token = client.cookies[settings.CSRF_COOKIE_NAME].value
        refresh_response = client.post(
            "/online/staff/auth/refresh/",
            {},
            format="json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        self.assertEqual(refresh_response.status_code, status.HTTP_200_OK)
        self.assertIn(settings.ONLINE_STAFF_ACCESS_COOKIE_NAME, refresh_response.cookies)
        self.assertNotIn("auth", refresh_response.data)

        logout_response = client.post(
            "/online/staff/auth/logout/",
            {},
            format="json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )
        self.assertEqual(logout_response.status_code, status.HTTP_200_OK)

        me_response = client.get("/online/staff/auth/me/")
        self.assertEqual(me_response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_staff_me_returns_teacher_profile(self):
        teacher_user, teacher = self._create_teacher(index=2)
        client = APIClient()
        client.force_authenticate(user=teacher_user)

        response = client.get("/online/staff/auth/me/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], teacher_user.email)
        self.assertTrue(response.data["isTeacher"])
        self.assertFalse(response.data["isAdmin"])
        self.assertEqual(response.data["teacherId"], teacher.id)

    def test_admin_user_directory_includes_curator_role_and_assignment_counts(self):
        admin_user = self._create_admin_user(index=9)
        teacher_user, teacher = self._create_teacher(index=9)
        course = self._create_course(slug="curator-directory-course", trial_available=False, price_amount=Decimal("89.00"))
        self._create_cohort(course=course, group_code="CURATOR_DIR_G1", capacity=8, teacher=teacher)

        student_user = User.objects.create_user(
            email="directory.student@example.com",
            username="directory_student",
            password="StrongPass12345",
            first_name="Directory",
            last_name="Student",
        )
        OnlineStudentProfile.objects.create(
            user=student_user,
            first_name="Directory",
            last_name="Student",
            preferred_language="en",
        )

        client = APIClient()
        client.force_authenticate(user=admin_user)
        response = client.get("/online/admin/users/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        teacher_payload = next(item for item in response.data["results"] if item["id"] == teacher_user.id)
        student_payload = next(item for item in response.data["results"] if item["id"] == student_user.id)
        self.assertTrue(teacher_payload["isCurator"])
        self.assertEqual(teacher_payload["assignedCohortsCount"], 1)
        self.assertEqual(teacher_payload["assignedCoursesCount"], 1)
        self.assertEqual(teacher_payload["curatorProfile"]["shortName"], teacher.KurzName)
        self.assertTrue(student_payload["isStudent"])
        self.assertFalse(student_payload["isCurator"])

    def test_admin_can_create_curator_for_existing_user(self):
        admin_user = self._create_admin_user(index=10)
        candidate = User.objects.create_user(
            email="candidate.curator@example.com",
            username="candidate_curator",
            password="StrongPass12345",
            first_name="Legacy",
            last_name="Teacher",
        )

        client = APIClient()
        client.force_authenticate(user=admin_user)
        response = client.post(
            "/online/admin/curators/",
            {
                "userId": candidate.id,
                "firstName": "Olivia",
                "lastName": "Stone",
                "schoolEmail": "olivia.stone@academy.example.com",
                "privateEmail": "olivia.private@example.com",
                "phone": "+49 123 456",
                "shortName": "ostn",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        teacher = Lehrer.objects.get(user=candidate)
        candidate.refresh_from_db()
        self.assertEqual(teacher.Vorname, "Olivia")
        self.assertEqual(teacher.Nachname, "Stone")
        self.assertEqual(teacher.Schule_Email, "olivia.stone@academy.example.com")
        self.assertEqual(teacher.KurzName, "OSTN")
        self.assertEqual(candidate.first_name, "Olivia")
        self.assertEqual(candidate.last_name, "Stone")
        self.assertEqual(response.data["assignedCohortsCount"], 0)

    def test_admin_can_onboard_new_curator_user(self):
        admin_user = self._create_admin_user(index=101)

        client = APIClient()
        client.force_authenticate(user=admin_user)
        response = client.post(
            "/online/admin/curator-onboarding/",
            {
                "email": "new.curator@example.com",
                "temporaryPassword": "TempPass12345",
                "firstName": "Nora",
                "lastName": "Bishop",
                "schoolEmail": "nora.bishop@academy.example.com",
                "privateEmail": "nora.private@example.com",
                "phone": "+49 999 111",
                "shortName": "nbis",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email="new.curator@example.com")
        teacher = Lehrer.objects.get(user=user)
        self.assertTrue(user.check_password("TempPass12345"))
        self.assertEqual(user.first_name, "Nora")
        self.assertEqual(user.last_name, "Bishop")
        self.assertEqual(teacher.Schule_Email, "nora.bishop@academy.example.com")
        self.assertEqual(teacher.Private_Email, "nora.private@example.com")
        self.assertEqual(teacher.KurzName, "NBIS")
        self.assertEqual(response.data["userId"], user.id)
        self.assertEqual(response.data["assignedCohortsCount"], 0)

    def test_admin_onboarding_rejects_duplicate_user_email(self):
        admin_user = self._create_admin_user(index=102)
        User.objects.create_user(
            email="existing.curator@example.com",
            username="existing_curator",
            password="StrongPass12345",
            first_name="Existing",
            last_name="Curator",
        )

        client = APIClient()
        client.force_authenticate(user=admin_user)
        response = client.post(
            "/online/admin/curator-onboarding/",
            {
                "email": "existing.curator@example.com",
                "temporaryPassword": "TempPass12345",
                "firstName": "Nora",
                "lastName": "Bishop",
                "schoolEmail": "nora.duplicate@academy.example.com",
                "privateEmail": "",
                "phone": "",
                "shortName": "NDUP",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["email"], "A user with this email already exists.")

    def test_admin_can_reset_curator_temporary_password(self):
        admin_user = self._create_admin_user(index=103)
        teacher_user, _teacher = self._create_teacher(index=103)

        client = APIClient()
        client.force_authenticate(user=admin_user)
        response = client.post(
            f"/online/admin/users/{teacher_user.id}/temporary-password/",
            {"temporaryPassword": "NewTempPass123"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        teacher_user.refresh_from_db()
        self.assertTrue(teacher_user.check_password("NewTempPass123"))

        login_response = self.client.post(
            "/online/staff/auth/login/",
            {"identifier": teacher_user.email, "password": "NewTempPass123", "role": "teacher"},
            format="json",
        )
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)

    def test_admin_can_deactivate_and_reactivate_curator_user(self):
        admin_user = self._create_admin_user(index=104)
        teacher_user, _teacher = self._create_teacher(index=104)

        client = APIClient()
        client.force_authenticate(user=admin_user)
        deactivate_response = client.patch(
            f"/online/admin/users/{teacher_user.id}/status/",
            {"isActive": False},
            format="json",
        )

        self.assertEqual(deactivate_response.status_code, status.HTTP_200_OK)
        teacher_user.refresh_from_db()
        self.assertFalse(teacher_user.is_active)

        denied_login_response = self.client.post(
            "/online/staff/auth/login/",
            {"identifier": teacher_user.email, "password": "TeacherPass12345", "role": "teacher"},
            format="json",
        )
        self.assertEqual(denied_login_response.status_code, status.HTTP_400_BAD_REQUEST)

        reactivate_response = client.patch(
            f"/online/admin/users/{teacher_user.id}/status/",
            {"isActive": True},
            format="json",
        )
        self.assertEqual(reactivate_response.status_code, status.HTTP_200_OK)
        teacher_user.refresh_from_db()
        self.assertTrue(teacher_user.is_active)

    def test_admin_cannot_manage_admin_account_from_curator_panel(self):
        admin_user = self._create_admin_user(index=105)
        second_admin = self._create_admin_user(index=106)

        client = APIClient()
        client.force_authenticate(user=admin_user)

        password_response = client.post(
            f"/online/admin/users/{second_admin.id}/temporary-password/",
            {"temporaryPassword": "AnotherPass123"},
            format="json",
        )
        self.assertEqual(password_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(password_response.data["detail"], "Admin accounts cannot be managed from this panel.")

        status_response = client.patch(
            f"/online/admin/users/{second_admin.id}/status/",
            {"isActive": False},
            format="json",
        )
        self.assertEqual(status_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(status_response.data["detail"], "Admin accounts cannot be managed from this panel.")

    def test_admin_can_update_curator_profile(self):
        admin_user = self._create_admin_user(index=11)
        teacher_user, teacher = self._create_teacher(index=11)

        client = APIClient()
        client.force_authenticate(user=admin_user)
        response = client.patch(
            f"/online/admin/curators/{teacher.id}/",
            {
                "firstName": "Amelia",
                "lastName": "Brown",
                "schoolEmail": "amelia.brown@academy.example.com",
                "shortName": "ABRO",
                "phone": "+49 555 111",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        teacher.refresh_from_db()
        teacher_user.refresh_from_db()
        self.assertEqual(teacher.Vorname, "Amelia")
        self.assertEqual(teacher.Nachname, "Brown")
        self.assertEqual(teacher.Schule_Email, "amelia.brown@academy.example.com")
        self.assertEqual(teacher.KurzName, "ABRO")
        self.assertEqual(teacher.Telefonnummer, "+49 555 111")
        self.assertEqual(teacher_user.first_name, "Amelia")
        self.assertEqual(teacher_user.last_name, "Brown")

    def test_admin_can_assign_and_unassign_curator_from_cohort(self):
        admin_user = self._create_admin_user(index=12)
        _teacher_user, teacher = self._create_teacher(index=12)
        course = self._create_course(slug="curator-assignment-course", trial_available=False, price_amount=Decimal("129.00"))
        cohort = self._create_cohort(course=course, group_code="CURATOR_ASSIGN_G1", capacity=8)

        client = APIClient()
        client.force_authenticate(user=admin_user)
        assign_response = client.patch(
            f"/online/admin/cohorts/{cohort.id}/curator/",
            {"curatorId": teacher.id},
            format="json",
        )

        self.assertEqual(assign_response.status_code, status.HTTP_200_OK)
        cohort.refresh_from_db()
        self.assertEqual(cohort.teacher_id, teacher.id)
        self.assertEqual(assign_response.data["cohort"]["teacherId"], teacher.id)

        unassign_response = client.patch(
            f"/online/admin/cohorts/{cohort.id}/curator/",
            {"curatorId": None},
            format="json",
        )
        self.assertEqual(unassign_response.status_code, status.HTTP_200_OK)
        cohort.refresh_from_db()
        self.assertIsNone(cohort.teacher_id)
        self.assertIsNone(unassign_response.data["cohort"]["teacherId"])

    def test_admin_cannot_delete_curator_with_assigned_cohort(self):
        admin_user = self._create_admin_user(index=13)
        _teacher_user, teacher = self._create_teacher(index=13)
        course = self._create_course(slug="curator-delete-guard", trial_available=False, price_amount=Decimal("149.00"))
        self._create_cohort(course=course, group_code="CURATOR_DELETE_G1", capacity=8, teacher=teacher)

        client = APIClient()
        client.force_authenticate(user=admin_user)
        response = client.delete(f"/online/admin/curators/{teacher.id}/")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["detail"],
            "Curator cannot be removed while cohorts are assigned. Unassign cohorts first.",
        )
        self.assertTrue(Lehrer.objects.filter(id=teacher.id).exists())

    @override_settings(ONLINE_GOOGLE_CLIENT_ID="google-client-id-for-tests")
    @patch("apps.online.views.requests.get")
    def test_google_checkout_trial_returns_auth_and_creates_trial_order(self, mock_google_get):
        mock_google_get.return_value.status_code = status.HTTP_200_OK
        mock_google_get.return_value.json.return_value = {
            "iss": "https://accounts.google.com",
            "aud": "google-client-id-for-tests",
            "email": "google.trial.student@example.com",
            "email_verified": "true",
            "given_name": "Google",
            "family_name": "Student",
            "sub": "google-sub-1",
        }

        course = self._create_course(slug="google-trial-course", trial_available=True, price_amount=Decimal("0.00"))
        cohort = self._create_cohort(course=course, group_code="GOOGLE_TRIAL_G1", capacity=5)

        payload = {
            "credential": "mock-google-id-token",
            "mode": "trial",
            "course_slug": course.slug,
            "cohort_id": cohort.id,
            "preferred_language": "de",
            "idempotency_key": "google-trial-idem-1",
        }
        response = self.client.post("/online/public/auth/google/checkout/", payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self._assert_auth_cookies(response, scope="student")
        self.assertEqual(response.data["profile"]["email"], "google.trial.student@example.com")
        self.assertTrue(
            OnlineOrder.objects.filter(
                profile__user__email="google.trial.student@example.com",
                status=OnlineOrder.STATUS_TRIAL,
                is_trial=True,
            ).exists()
        )
        self.assertTrue(
            OnlineEnrollment.objects.filter(
                profile__user__email="google.trial.student@example.com",
                status=OnlineEnrollment.STATUS_TRIAL,
            ).exists()
        )

    @override_settings(ONLINE_GOOGLE_CLIENT_ID="google-client-id-for-tests")
    @patch("apps.online.views.requests.get")
    def test_google_checkout_trial_returns_existing_access_for_same_course(self, mock_google_get):
        mock_google_get.return_value.status_code = status.HTTP_200_OK
        mock_google_get.return_value.json.return_value = {
            "iss": "https://accounts.google.com",
            "aud": "google-client-id-for-tests",
            "email": "google.retry.student@example.com",
            "email_verified": "true",
            "given_name": "Google",
            "family_name": "Retry",
            "sub": "google-sub-retry-1",
        }

        course = self._create_course(slug="google-retry-course", trial_available=True, price_amount=Decimal("0.00"))
        cohort = self._create_cohort(course=course, group_code="GOOGLE_RETRY_G1", capacity=5)
        payload = {
            "credential": "mock-google-id-token",
            "mode": "trial",
            "course_slug": course.slug,
            "cohort_id": cohort.id,
            "preferred_language": "de",
        }

        first_response = self.client.post("/online/public/auth/google/checkout/", payload, format="json")
        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)

        second_response = self.client.post("/online/public/auth/google/checkout/", payload, format="json")
        self.assertEqual(second_response.status_code, status.HTTP_200_OK)
        self.assertTrue(second_response.data.get("alreadyProcessed"))
        self.assertEqual(second_response.data.get("enrollmentId"), first_response.data.get("enrollmentId"))
        self.assertEqual(
            OnlineOrder.objects.filter(
                profile__user__email="google.retry.student@example.com",
                is_trial=True,
            ).count(),
            1,
        )

    @override_settings(ONLINE_GOOGLE_CLIENT_ID="google-client-id-for-tests")
    @patch("apps.online.views.requests.get")
    def test_google_checkout_trial_works_even_when_browser_has_admin_session_cookie(self, mock_google_get):
        mock_google_get.return_value.status_code = status.HTTP_200_OK
        mock_google_get.return_value.json.return_value = {
            "iss": "https://accounts.google.com",
            "aud": "google-client-id-for-tests",
            "email": "google.session.student@example.com",
            "email_verified": "true",
            "given_name": "Google",
            "family_name": "Session",
            "sub": "google-sub-session-1",
        }

        admin_user = User.objects.create_user(
            email="admin.google.session@example.com",
            username="admin_google_session",
            password="AdminPass12345",
            is_admin=True,
            is_staff=True,
        )
        course = self._create_course(slug="google-session-course", trial_available=True, price_amount=Decimal("0.00"))
        cohort = self._create_cohort(course=course, group_code="GOOGLE_SESSION_G1", capacity=5)

        client = APIClient(enforce_csrf_checks=True)
        self.assertTrue(client.login(email="admin.google.session@example.com", password="AdminPass12345"))

        payload = {
            "credential": "mock-google-id-token",
            "mode": "trial",
            "course_slug": course.slug,
            "cohort_id": cohort.id,
            "preferred_language": "de",
            "idempotency_key": "google-session-idem-1",
        }
        response = client.post("/online/public/auth/google/checkout/", payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            OnlineOrder.objects.filter(
                profile__user__email="google.session.student@example.com",
                status=OnlineOrder.STATUS_TRIAL,
                is_trial=True,
            ).exists()
        )

    @override_settings(ONLINE_PAYMENT_MODE="free")
    def test_checkout_start_rejects_inactive_existing_user(self):
        course = self._create_course(slug="inactive-checkout-course", trial_available=False, price_amount=Decimal("129.00"))
        cohort = self._create_cohort(course=course, group_code="INACTIVE_CHECKOUT_G1", capacity=5)

        User.objects.create_user(
            email="inactive.checkout.student@example.com",
            username="inactive_checkout_student",
            password="StrongPass12345",
            first_name="Inactive",
            last_name="Checkout",
            is_active=False,
        )

        payload = {
            "course_slug": course.slug,
            "cohort_id": cohort.id,
            "email": "inactive.checkout.student@example.com",
            "password": "StrongPass12345",
            "first_name": "Inactive",
            "last_name": "Checkout",
            "preferred_language": "de",
            "accept_terms": True,
            "idempotency_key": "inactive-checkout-idem-1",
        }
        response = self.client.post("/online/public/checkout/start/", payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["detail"], "User account is inactive.")
        self.assertFalse(OnlineOrder.objects.filter(profile__user__email="inactive.checkout.student@example.com").exists())

    @override_settings(ONLINE_GOOGLE_CLIENT_ID="google-client-id-for-tests")
    @patch("apps.online.views.requests.get")
    def test_google_checkout_rejects_inactive_existing_user(self, mock_google_get):
        mock_google_get.return_value.status_code = status.HTTP_200_OK
        mock_google_get.return_value.json.return_value = {
            "iss": "https://accounts.google.com",
            "aud": "google-client-id-for-tests",
            "email": "inactive.google.student@example.com",
            "email_verified": "true",
            "given_name": "Inactive",
            "family_name": "Google",
            "sub": "google-inactive-sub-1",
        }

        course = self._create_course(slug="inactive-google-course", trial_available=True, price_amount=Decimal("0.00"))
        cohort = self._create_cohort(course=course, group_code="INACTIVE_GOOGLE_G1", capacity=5)

        User.objects.create_user(
            email="inactive.google.student@example.com",
            username="inactive_google_student",
            password="StrongPass12345",
            first_name="Inactive",
            last_name="Google",
            is_active=False,
        )

        payload = {
            "credential": "mock-google-id-token",
            "mode": "trial",
            "course_slug": course.slug,
            "cohort_id": cohort.id,
            "preferred_language": "de",
            "idempotency_key": "inactive-google-idem-1",
        }
        response = self.client.post("/online/public/auth/google/checkout/", payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["detail"], "User account is inactive.")
        self.assertFalse(OnlineOrder.objects.filter(profile__user__email="inactive.google.student@example.com").exists())

    @override_settings(ONLINE_GOOGLE_CLIENT_ID="google-client-id-for-tests", ONLINE_PAYMENT_MODE="free")
    @patch("apps.online.views.requests.get")
    def test_google_checkout_paid_free_mode_returns_auth_and_creates_active_enrollment(self, mock_google_get):
        mock_google_get.return_value.status_code = status.HTTP_200_OK
        mock_google_get.return_value.json.return_value = {
            "iss": "https://accounts.google.com",
            "aud": "google-client-id-for-tests",
            "email": "google.paid.student@example.com",
            "email_verified": "true",
            "given_name": "Google",
            "family_name": "Paid",
            "sub": "google-sub-paid-1",
        }

        course = self._create_course(slug="google-paid-course", trial_available=False, price_amount=Decimal("149.00"))
        cohort = self._create_cohort(course=course, group_code="GOOGLE_PAID_G1", capacity=5)

        payload = {
            "credential": "mock-google-id-token",
            "mode": "paid",
            "course_slug": course.slug,
            "cohort_id": cohort.id,
            "preferred_language": "de",
            "accept_terms": True,
            "idempotency_key": "google-paid-idem-1",
        }
        response = self.client.post("/online/public/auth/google/checkout/", payload, format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self._assert_auth_cookies(response, scope="student")
        self.assertEqual(response.data["status"], OnlineOrder.STATUS_PAID)
        self.assertTrue(
            OnlineOrder.objects.filter(
                profile__user__email="google.paid.student@example.com",
                status=OnlineOrder.STATUS_PAID,
                is_trial=False,
            ).exists()
        )
        self.assertTrue(
            OnlineEnrollment.objects.filter(
                profile__user__email="google.paid.student@example.com",
                status=OnlineEnrollment.STATUS_ACTIVE,
            ).exists()
        )

    @override_settings(ONLINE_GOOGLE_CLIENT_ID="google-client-id-for-tests")
    @patch("apps.online.views.requests.get")
    def test_google_login_returns_auth_for_existing_online_profile(self, mock_google_get):
        mock_google_get.return_value.status_code = status.HTTP_200_OK
        mock_google_get.return_value.json.return_value = {
            "iss": "https://accounts.google.com",
            "aud": "google-client-id-for-tests",
            "email": "google.login.student@example.com",
            "email_verified": "true",
            "given_name": "Google",
            "family_name": "Login",
            "sub": "google-sub-2",
        }

        user = User.objects.create_user(
            email="google.login.student@example.com",
            username="google_login_student",
            password="StrongPass12345",
            first_name="Google",
            last_name="Login",
        )
        OnlineStudentProfile.objects.create(
            user=user,
            first_name="Google",
            last_name="Login",
            phone="",
            preferred_language="de",
            is_trial_user=False,
        )

        response = self.client.post(
            "/online/public/auth/google/login/",
            {"credential": "mock-google-id-token"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self._assert_auth_cookies(response, scope="student")
        self.assertEqual(response.data["profile"]["email"], "google.login.student@example.com")

    def test_student_dashboard_includes_only_entitled_learning_content(self):
        user = User.objects.create_user(
            email="dashboard.learning@example.com",
            username="dashboard_learning",
            password="StrongPass12345",
        )
        profile = OnlineStudentProfile.objects.create(
            user=user,
            first_name="Dashboard",
            last_name="Learning",
            preferred_language="en",
        )
        course = self._create_course(slug="dashboard-quant", trial_available=False, price_amount=Decimal("299.00"))
        cohort = self._create_cohort(course=course, group_code="DASHBOARD_QA_G1", capacity=10)
        OnlineEnrollment.objects.create(
            profile=profile,
            course=course,
            cohort=cohort,
            status=OnlineEnrollment.STATUS_ACTIVE,
        )

        audience = TrainingAudience.objects.create(
            slug="institutional-skills",
            name="Institutional Skills",
            is_internal=True,
        )
        TrainingUserAudienceGrant.objects.create(user=user, audience=audience)

        public_content = TrainingContentItem.objects.create(
            slug="public-learning-note",
            name="Public Learning Note",
            content_kind=TrainingContentItem.ContentKind.ARTICLE,
            status=TrainingContentItem.Status.PUBLISHED,
            access_scope=TrainingContentItem.AccessScope.PUBLIC,
            course=course,
        )
        internal_content = TrainingContentItem.objects.create(
            slug="institutional-learning-note",
            name="Institutional Learning Note",
            content_kind=TrainingContentItem.ContentKind.ARTICLE,
            status=TrainingContentItem.Status.PUBLISHED,
            access_scope=TrainingContentItem.AccessScope.ENTITLED,
            course=course,
        )
        TrainingContentAudiencePolicy.objects.create(content_item=internal_content, audience=audience)

        client = APIClient()
        client.force_authenticate(user=user)
        response = client.get("/online/student/dashboard/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        learning_slugs = {item["slug"] for item in response.data["learningContent"]}
        self.assertEqual(learning_slugs, {public_content.slug, internal_content.slug})
        self.assertEqual(response.data["enrollments"][0]["course"]["audiences"], [])

    def test_student_dashboard_hides_internal_learning_content_for_external_enrolled_user(self):
        course = self._create_course(slug="external-dashboard-course", trial_available=False, price_amount=Decimal("199.00"))
        cohort = self._create_cohort(course=course, group_code="EXTERNAL_DASHBOARD_G1", capacity=10)

        internal_audience = TrainingAudience.objects.create(
            slug="institutional-skills-external-test",
            name="Institutional Skills",
            is_internal=True,
        )

        internal_content = TrainingContentItem.objects.create(
            slug="external-dashboard-internal-note",
            name="Internal Note",
            content_kind=TrainingContentItem.ContentKind.ARTICLE,
            status=TrainingContentItem.Status.PUBLISHED,
            access_scope=TrainingContentItem.AccessScope.ENTITLED,
            course=course,
        )
        TrainingContentAudiencePolicy.objects.create(content_item=internal_content, audience=internal_audience)
        public_content = TrainingContentItem.objects.create(
            slug="external-dashboard-public-note",
            name="Public Note",
            content_kind=TrainingContentItem.ContentKind.ARTICLE,
            status=TrainingContentItem.Status.PUBLISHED,
            access_scope=TrainingContentItem.AccessScope.PUBLIC,
            course=course,
        )

        user = User.objects.create_user(
            email="external.dashboard.user@example.com",
            username="external_dashboard_user",
            password="StrongPass12345",
        )
        profile = OnlineStudentProfile.objects.create(
            user=user,
            first_name="External",
            last_name="Dashboard",
            preferred_language="en",
        )
        OnlineEnrollment.objects.create(
            profile=profile,
            course=course,
            cohort=cohort,
            status=OnlineEnrollment.STATUS_ACTIVE,
        )

        client = APIClient()
        client.force_authenticate(user=user)
        response = client.get("/online/student/dashboard/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        learning_slugs = {item["slug"] for item in response.data["learningContent"]}
        self.assertEqual(learning_slugs, {public_content.slug})

    def test_student_dashboard_returns_empty_learning_content_when_training_content_is_absent(self):
        user = User.objects.create_user(
            email="dashboard.no.learning@example.com",
            username="dashboard_no_learning",
            password="StrongPass12345",
        )
        profile = OnlineStudentProfile.objects.create(
            user=user,
            first_name="No",
            last_name="Learning",
            preferred_language="en",
        )
        course = self._create_course(slug="dashboard-empty-learning", trial_available=False, price_amount=Decimal("129.00"))
        cohort = self._create_cohort(course=course, group_code="DASHBOARD_EMPTY_G1", capacity=10)
        OnlineEnrollment.objects.create(
            profile=profile,
            course=course,
            cohort=cohort,
            status=OnlineEnrollment.STATUS_ACTIVE,
        )

        client = APIClient()
        client.force_authenticate(user=user)
        response = client.get("/online/student/dashboard/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["learningContent"], [])

    def test_student_access_endpoint_returns_accessible_enrollment_summary(self):
        demo_audiences = self._ensure_demo_audiences()
        user = User.objects.create_user(
            email="student.access.summary@example.com",
            username="student_access_summary",
            password="StrongPass12345",
        )
        profile = OnlineStudentProfile.objects.create(
            user=user,
            first_name="Access",
            last_name="Summary",
            preferred_language="en",
        )

        accessible_course = self._create_course(
            slug="access-summary-open-course",
            trial_available=False,
            price_amount=Decimal("149.00"),
        )
        accessible_cohort = self._create_cohort(course=accessible_course, group_code="ACCESS_SUMMARY_OPEN_G1", capacity=10)
        OnlineEnrollment.objects.create(
            profile=profile,
            course=accessible_course,
            cohort=accessible_cohort,
            status=OnlineEnrollment.STATUS_ACTIVE,
        )

        restricted_course = self._create_course(
            slug="access-summary-restricted-course",
            trial_available=False,
            price_amount=Decimal("149.00"),
        )
        restricted_cohort = self._create_cohort(
            course=restricted_course,
            group_code="ACCESS_SUMMARY_RESTRICTED_G1",
            capacity=10,
        )
        OnlineAccessPolicy.objects.create(
            content_object=restricted_course,
            audience=demo_audiences["lateral-transfers"],
        )
        TrainingUserAudienceGrant.objects.create(
            user=user,
            audience=demo_audiences["interns-new-grads"],
        )
        OnlineEnrollment.objects.create(
            profile=profile,
            course=restricted_course,
            cohort=restricted_cohort,
            status=OnlineEnrollment.STATUS_ACTIVE,
        )

        client = APIClient()
        client.force_authenticate(user=user)
        response = client.get("/online/student/access/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["hasAccessibleEnrollments"])
        self.assertEqual(response.data["dashboardUrl"], "/online/student/dashboard/")
        self.assertEqual(response.data["summary"]["totalEnrollments"], 2)
        self.assertEqual(response.data["summary"]["accessibleEnrollments"], 1)
        self.assertEqual(response.data["summary"]["accessibleCourses"], 1)

    def test_student_access_endpoint_returns_no_dashboard_when_all_enrollments_are_hidden(self):
        demo_audiences = self._ensure_demo_audiences()
        user = User.objects.create_user(
            email="student.access.hidden@example.com",
            username="student_access_hidden",
            password="StrongPass12345",
        )
        profile = OnlineStudentProfile.objects.create(
            user=user,
            first_name="Hidden",
            last_name="Access",
            preferred_language="en",
        )

        restricted_course = self._create_course(
            slug="access-hidden-restricted-course",
            trial_available=False,
            price_amount=Decimal("149.00"),
        )
        restricted_cohort = self._create_cohort(
            course=restricted_course,
            group_code="ACCESS_HIDDEN_RESTRICTED_G1",
            capacity=10,
        )
        OnlineAccessPolicy.objects.create(
            content_object=restricted_course,
            audience=demo_audiences["lateral-transfers"],
        )
        TrainingUserAudienceGrant.objects.create(
            user=user,
            audience=demo_audiences["interns-new-grads"],
        )
        OnlineEnrollment.objects.create(
            profile=profile,
            course=restricted_course,
            cohort=restricted_cohort,
            status=OnlineEnrollment.STATUS_ACTIVE,
        )

        client = APIClient()
        client.force_authenticate(user=user)
        response = client.get("/online/student/access/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["hasAccessibleEnrollments"])
        self.assertIsNone(response.data["dashboardUrl"])
        self.assertEqual(response.data["summary"]["totalEnrollments"], 1)
        self.assertEqual(response.data["summary"]["accessibleEnrollments"], 0)
        self.assertEqual(response.data["summary"]["accessibleCourses"], 0)


class OnlineWorkspaceCatalogTests(OnlineSprintOneTests):
    def test_public_workspace_list_returns_seeded_group_and_shared_cards(self):
        response = self.client.get("/online/public/workspaces/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        slugs = {item["slug"] for item in response.data["results"]}
        self.assertIn("berlin", slugs)
        self.assertIn("finance", slugs)
        self.assertIn("academy-resources", slugs)

    def test_public_workspace_detail_returns_seeded_content_sections(self):
        response = self.client.get("/online/public/workspaces/berlin/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["slug"], "berlin")
        self.assertEqual(response.data["kind"], OnlineWorkspace.KIND_GROUP)
        self.assertIn("courses", response.data["availableSections"])
        self.assertGreaterEqual(len(response.data["courses"]), 1)
        self.assertGreaterEqual(len(response.data["assignments"]), 1)
        self.assertGreaterEqual(len(response.data["recordings"]), 1)
        self.assertGreaterEqual(len(response.data["materials"]), 1)

    @override_settings(TRAINING_AI_ENABLED=True, TRAINING_AI_PROVIDER="demo")
    def test_public_course_finder_returns_ai_summary_and_recommendations(self):
        self._create_course(
            slug="public-course-finder-python-basics",
            title_de="Python Basics",
            title_en="Python Basics",
            short_description_de="Beginner Python path.",
            short_description_en="Beginner Python path with structured practice.",
            description_de="Structured Python course.",
            description_en="Structured Python course with guided lessons and practice.",
            trial_available=False,
            price_amount=Decimal("0.00"),
        )
        provider = Mock()
        provider.provider_name = "test-provider"
        provider.model_name = "test-model"
        provider.generate_answer.return_value = Mock(
            short_answer="Start with Python Basics.",
            detailed_answer="Start with Python Basics, then open the learning library for recordings and materials.",
            follow_up_prompts=["Show me beginner-friendly practice."],
            resolution_status="resolved",
        )

        with patch("apps.online.views.get_training_ai_provider", return_value=provider):
            response = self.client.post(
                "/online/public/course-finder/ask/",
                {"query": "I need beginner Python practice"},
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["answer"],
            "Start with Python Basics, then open the learning library for recordings and materials.",
        )
        self.assertEqual(response.data["provider"], "test-provider")
        self.assertEqual(response.data["model"], "test-model")
        self.assertTrue(response.data["recommendations"])
        self.assertIn(
            "Python Basics",
            {item["title"] for item in response.data["recommendations"]},
        )
        provider.generate_answer.assert_called_once()
        self.assertTrue(provider.generate_answer.call_args.kwargs["context_chunks"])

    def test_public_workspace_detail_exposes_join_targets_for_linked_course_cards(self):
        course = self._create_course(
            slug="workspace-linked-course",
            trial_available=False,
            price_amount=Decimal("0.00"),
        )
        cohort = self._create_cohort(course=course, group_code="WORKSPACE_LINKED_G1", capacity=12)
        workspace = OnlineWorkspace.objects.create(
            slug="workspace-linked",
            title="Linked Workspace",
            subtitle="Group X",
            summary="Linked summary",
            icon_key="finance",
            kind=OnlineWorkspace.KIND_GROUP,
            sort_order=999,
            show_on_homepage=True,
            is_published=True,
        )
        OnlineWorkspaceContentItem.objects.create(
            workspace=workspace,
            section=OnlineWorkspaceContentItem.SECTION_COURSES,
            title="Linked card",
            description="Linked course card.",
            linked_course=course,
            linked_cohort=cohort,
            sort_order=10,
            is_active=True,
        )

        response = self.client.get(f"/online/public/workspaces/{workspace.slug}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["courses"]), 1)
        self.assertEqual(response.data["courses"][0]["linkedCourseId"], course.id)
        self.assertEqual(response.data["courses"][0]["linkedCohortId"], cohort.id)
        self.assertTrue(response.data["courses"][0]["joinEnabled"])

    def test_public_workspace_detail_exposes_demo_role_catalog_and_restricted_cards(self):
        demo_audiences = self._ensure_demo_audiences()
        course = self._create_course(
            slug="workspace-role-protected-course",
            trial_available=False,
            price_amount=Decimal("0.00"),
        )
        cohort = self._create_cohort(course=course, group_code="WORKSPACE_ROLE_G1", capacity=12)
        workspace = OnlineWorkspace.objects.create(
            slug="workspace-role-scope",
            title="Role Scope Workspace",
            subtitle="Group X",
            summary="Role-based workspace summary",
            icon_key="finance",
            kind=OnlineWorkspace.KIND_GROUP,
            sort_order=1000,
            show_on_homepage=True,
            is_published=True,
        )
        item = OnlineWorkspaceContentItem.objects.create(
            workspace=workspace,
            section=OnlineWorkspaceContentItem.SECTION_COURSES,
            title="Protected card",
            description="Protected course card.",
            linked_course=course,
            linked_cohort=cohort,
            sort_order=10,
            is_active=True,
        )
        OnlineAccessPolicy.objects.create(content_object=item, audience=demo_audiences["lateral-transfers"])

        user = User.objects.create_user(
            email="workspace.role@example.com",
            username="workspace_role_user",
            password="StrongPass12345",
        )
        TrainingUserAudienceGrant.objects.create(
            user=user,
            audience=demo_audiences["interns-new-grads"],
        )
        client = APIClient()
        client.force_authenticate(user=user)

        response = client.get(f"/online/public/workspaces/{workspace.slug}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["activeRole"]["slug"], "interns-new-grads")
        self.assertEqual(len(response.data["roleCatalog"]), 4)
        self.assertFalse(response.data["courses"][0]["isAccessible"])
        self.assertFalse(response.data["courses"][0]["joinEnabled"])
        self.assertIn("lateral-transfers", response.data["courses"][0]["requiredAudienceSlugs"])
        self.assertIn("Contact an administrator", response.data["courses"][0]["accessMessage"])

    def test_public_workspace_detail_resolves_active_role_from_bearer_token(self):
        demo_audiences = self._ensure_demo_audiences()
        workspace = OnlineWorkspace.objects.create(
            slug="workspace-auth-role",
            title="Authenticated role workspace",
            subtitle="Group Auth",
            summary="Workspace summary",
            icon_key="berlin",
            kind=OnlineWorkspace.KIND_GROUP,
            sort_order=1001,
            show_on_homepage=True,
            is_published=True,
        )
        OnlineWorkspaceContentItem.objects.create(
            workspace=workspace,
            section=OnlineWorkspaceContentItem.SECTION_MATERIALS,
            title="Authenticated material",
            description="Material that proves the role chip flow.",
            sort_order=10,
            is_active=True,
        )

        user = User.objects.create_user(
            email="workspace.jwt.role@example.com",
            username="workspace_jwt_role_user",
            password="StrongPass12345",
        )
        TrainingUserAudienceGrant.objects.create(
            user=user,
            audience=demo_audiences["traders-structurizers"],
        )
        access_token = str(RefreshToken.for_user(user).access_token)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

        response = client.get(f"/online/public/workspaces/{workspace.slug}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["activeRole"]["slug"], "traders-structurizers")

    def test_admin_can_create_update_and_delete_workspace_and_content_items(self):
        admin_user = self._create_admin_user(index=91)
        demo_audiences = self._ensure_demo_audiences()
        client = APIClient()
        client.force_authenticate(user=admin_user)
        course = self._create_course(slug="treasury-foundations", trial_available=False, price_amount=Decimal("0.00"))
        cohort = self._create_cohort(course=course, group_code="TREASURY_G1", capacity=24)

        create_workspace_response = client.post(
            "/online/admin/workspaces/",
            {
                "slug": "treasury",
                "title": "Treasury",
                "subtitle": "Group 9",
                "summary": "Treasury-focused academy section.",
                "iconKey": "finance",
                "kind": "group",
                "sortOrder": 190,
                "showOnHomepage": True,
                "isPublished": True,
                "audienceIds": [demo_audiences["interns-new-grads"].id],
            },
            format="json",
        )
        self.assertEqual(create_workspace_response.status_code, status.HTTP_201_CREATED)
        workspace_id = create_workspace_response.data["id"]
        self.assertEqual(
            create_workspace_response.data["audienceIds"],
            [demo_audiences["interns-new-grads"].id],
        )

        create_item_response = client.post(
            f"/online/admin/workspaces/{workspace_id}/items/",
            {
                "section": "courses",
                "title": "Treasury Foundations",
                "description": "Introductory treasury content.",
                "previewImageUrl": "/images/lesson_1.jpeg",
                "assetUrl": "",
                "linkedCourseId": course.id,
                "linkedCohortId": cohort.id,
                "primaryMeta": "4 modules",
                "secondaryMeta": "Group cohort",
                "publishedOn": "2026-03-28",
                "sortOrder": 10,
                "isActive": True,
                "audienceIds": [demo_audiences["lateral-transfers"].id],
            },
            format="json",
        )
        self.assertEqual(create_item_response.status_code, status.HTTP_201_CREATED)
        item_id = create_item_response.data["id"]
        self.assertEqual(create_item_response.data["linkedCourseId"], course.id)
        self.assertEqual(create_item_response.data["linkedCohortId"], cohort.id)
        self.assertEqual(create_item_response.data["linkedCourseSlug"], course.slug)
        self.assertEqual(create_item_response.data["linkedCohortCode"], cohort.group_code)
        self.assertEqual(
            create_item_response.data["audienceIds"],
            [demo_audiences["lateral-transfers"].id],
        )

        update_workspace_response = client.patch(
            f"/online/admin/workspaces/{workspace_id}/",
            {
                "title": "Treasury and Funding",
                "showOnHomepage": False,
                "audienceIds": [demo_audiences["external-users"].id],
            },
            format="json",
        )
        self.assertEqual(update_workspace_response.status_code, status.HTTP_200_OK)
        self.assertEqual(update_workspace_response.data["title"], "Treasury and Funding")
        self.assertFalse(update_workspace_response.data["showOnHomepage"])
        self.assertEqual(
            update_workspace_response.data["audienceIds"],
            [demo_audiences["external-users"].id],
        )

        update_item_response = client.patch(
            f"/online/admin/workspace-items/{item_id}/",
            {"secondaryMeta": "Open access", "isActive": False},
            format="json",
        )
        self.assertEqual(update_item_response.status_code, status.HTTP_200_OK)
        self.assertEqual(update_item_response.data["secondaryMeta"], "Open access")
        self.assertFalse(update_item_response.data["isActive"])

        list_items_response = client.get(f"/online/admin/workspaces/{workspace_id}/items/", {"section": "courses"})
        self.assertEqual(list_items_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_items_response.data["results"]), 1)

        delete_item_response = client.delete(f"/online/admin/workspace-items/{item_id}/")
        self.assertEqual(delete_item_response.status_code, status.HTTP_204_NO_CONTENT)

        delete_workspace_response = client.delete(f"/online/admin/workspaces/{workspace_id}/")
        self.assertEqual(delete_workspace_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(OnlineWorkspace.objects.filter(id=workspace_id).exists())
        self.assertFalse(OnlineWorkspaceContentItem.objects.filter(id=item_id).exists())

    def test_student_can_join_workspace_course_item_and_dashboard_admin_reflect_enrollment(self):
        course = self._create_course(
            slug="workspace-join-course",
            trial_available=False,
            price_amount=Decimal("0.00"),
        )
        cohort = self._create_cohort(course=course, group_code="WORKSPACE_JOIN_G1", capacity=8)
        workspace = OnlineWorkspace.objects.create(
            slug="workspace-join",
            title="Join Workspace",
            subtitle="Group Join",
            summary="Join summary",
            icon_key="berlin",
            kind=OnlineWorkspace.KIND_GROUP,
            sort_order=1010,
            show_on_homepage=True,
            is_published=True,
        )
        item = OnlineWorkspaceContentItem.objects.create(
            workspace=workspace,
            section=OnlineWorkspaceContentItem.SECTION_COURSES,
            title="Joinable course card",
            description="Joinable course card.",
            linked_course=course,
            linked_cohort=cohort,
            sort_order=10,
            is_active=True,
        )
        user = User.objects.create_user(
            email="workspace.join.student@example.com",
            username="workspace_join_student",
            password="StrongPass12345",
        )
        profile = OnlineStudentProfile.objects.create(
            user=user,
            first_name="Workspace",
            last_name="Student",
            preferred_language="en",
        )
        student_client = APIClient()
        student_client.force_authenticate(user=user)

        join_response = student_client.post(
            f"/online/student/workspace-course-items/{item.id}/join/",
            {},
            format="json",
        )

        self.assertEqual(join_response.status_code, status.HTTP_200_OK)
        self.assertFalse(join_response.data["alreadyJoined"])
        enrollment = OnlineEnrollment.objects.get(profile=profile, cohort=cohort)
        self.assertEqual(enrollment.course_id, course.id)
        self.assertEqual(enrollment.status, OnlineEnrollment.STATUS_ACTIVE)

        second_join_response = student_client.post(
            f"/online/student/workspace-course-items/{item.id}/join/",
            {},
            format="json",
        )
        self.assertEqual(second_join_response.status_code, status.HTTP_200_OK)
        self.assertTrue(second_join_response.data["alreadyJoined"])
        self.assertEqual(OnlineEnrollment.objects.filter(profile=profile, cohort=cohort).count(), 1)

        dashboard_response = student_client.get("/online/student/dashboard/")
        self.assertEqual(dashboard_response.status_code, status.HTTP_200_OK)
        dashboard_course_slugs = {row["course"]["slug"] for row in dashboard_response.data["enrollments"]}
        self.assertIn(course.slug, dashboard_course_slugs)

        admin_user = self._create_admin_user(index=92)
        admin_client = APIClient()
        admin_client.force_authenticate(user=admin_user)
        admin_detail_response = admin_client.get(f"/online/admin/cohorts/{cohort.id}/")

        self.assertEqual(admin_detail_response.status_code, status.HTTP_200_OK)
        learner_emails = {row["email"] for row in admin_detail_response.data["students"]}
        self.assertIn(user.email, learner_emails)

    def test_workspace_join_is_denied_when_demo_role_policy_blocks_the_item(self):
        demo_audiences = self._ensure_demo_audiences()
        course = self._create_course(
            slug="workspace-join-role-guarded",
            trial_available=False,
            price_amount=Decimal("0.00"),
        )
        cohort = self._create_cohort(course=course, group_code="WORKSPACE_ROLE_JOIN_G1", capacity=8)
        workspace = OnlineWorkspace.objects.create(
            slug="workspace-role-join",
            title="Role Join Workspace",
            subtitle="Group Guard",
            summary="Guarded join summary",
            icon_key="berlin",
            kind=OnlineWorkspace.KIND_GROUP,
            sort_order=1011,
            show_on_homepage=True,
            is_published=True,
        )
        item = OnlineWorkspaceContentItem.objects.create(
            workspace=workspace,
            section=OnlineWorkspaceContentItem.SECTION_COURSES,
            title="Guarded course card",
            description="Guarded course card.",
            linked_course=course,
            linked_cohort=cohort,
            sort_order=10,
            is_active=True,
        )
        OnlineAccessPolicy.objects.create(content_object=item, audience=demo_audiences["lateral-transfers"])

        user = User.objects.create_user(
            email="workspace.role.denied@example.com",
            username="workspace_role_denied",
            password="StrongPass12345",
        )
        TrainingUserAudienceGrant.objects.create(
            user=user,
            audience=demo_audiences["interns-new-grads"],
        )
        OnlineStudentProfile.objects.create(
            user=user,
            first_name="Denied",
            last_name="User",
            preferred_language="en",
        )
        student_client = APIClient()
        student_client.force_authenticate(user=user)

        join_response = student_client.post(
            f"/online/student/workspace-course-items/{item.id}/join/",
            {},
            format="json",
        )

        self.assertEqual(join_response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("Contact an administrator", join_response.data["detail"])
        self.assertEqual(OnlineEnrollment.objects.filter(cohort=cohort).count(), 0)

    def test_student_dashboard_hides_role_restricted_enrollments(self):
        demo_audiences = self._ensure_demo_audiences()
        course = self._create_course(
            slug="dashboard-role-hidden-course",
            trial_available=False,
            price_amount=Decimal("0.00"),
        )
        cohort = self._create_cohort(course=course, group_code="DASHBOARD_ROLE_G1", capacity=8)
        OnlineAccessPolicy.objects.create(
            content_object=course,
            audience=demo_audiences["lateral-transfers"],
        )
        user = User.objects.create_user(
            email="dashboard.role.hidden@example.com",
            username="dashboard_role_hidden",
            password="StrongPass12345",
        )
        TrainingUserAudienceGrant.objects.create(
            user=user,
            audience=demo_audiences["interns-new-grads"],
        )
        profile = OnlineStudentProfile.objects.create(
            user=user,
            first_name="Hidden",
            last_name="Dashboard",
            preferred_language="en",
        )
        OnlineEnrollment.objects.create(
            profile=profile,
            course=course,
            cohort=cohort,
            status=OnlineEnrollment.STATUS_ACTIVE,
        )

        client = APIClient()
        client.force_authenticate(user=user)
        response = client.get("/online/student/dashboard/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["enrollments"], [])

    def test_student_dashboard_includes_course_role_labels(self):
        demo_audiences = self._ensure_demo_audiences()
        course = self._create_course(
            slug="dashboard-role-labels-course",
            trial_available=False,
            price_amount=Decimal("0.00"),
        )
        cohort = self._create_cohort(course=course, group_code="DASHBOARD_ROLE_LABELS_G1", capacity=8)
        OnlineAccessPolicy.objects.create(
            content_object=course,
            audience=demo_audiences["interns-new-grads"],
        )
        user = User.objects.create_user(
            email="dashboard.role.labels@example.com",
            username="dashboard_role_labels",
            password="StrongPass12345",
        )
        TrainingUserAudienceGrant.objects.create(
            user=user,
            audience=demo_audiences["interns-new-grads"],
        )
        profile = OnlineStudentProfile.objects.create(
            user=user,
            first_name="Role",
            last_name="Labels",
            preferred_language="en",
        )
        OnlineEnrollment.objects.create(
            profile=profile,
            course=course,
            cohort=cohort,
            status=OnlineEnrollment.STATUS_ACTIVE,
        )

        client = APIClient()
        client.force_authenticate(user=user)
        response = client.get("/online/student/dashboard/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["enrollments"][0]["course"]["audiences"],
            [
                {
                    "id": demo_audiences["interns-new-grads"].id,
                    "slug": "interns-new-grads",
                    "name": "Student access",
                    "shortLabel": "Student",
                }
            ],
        )


class OnlineCourseBuilderTests(OnlineSprintOneTests):
    def test_admin_course_template_endpoint_bootstraps_default_templates_when_missing(self):
        admin_user = self._create_admin_user(index=200)
        OnlineCourseTemplate.objects.all().delete()

        client = APIClient()
        client.force_authenticate(user=admin_user)
        response = client.get("/online/admin/course-templates/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data["results"]), 3)
        self.assertTrue(OnlineCourseTemplate.objects.filter(slug="blank-structured-course").exists())

    def test_admin_can_create_structured_course_and_student_dashboard_exposes_lesson_plan(self):
        admin_user = self._create_admin_user(index=201)
        demo_audiences = self._ensure_demo_audiences()
        notebook_content = TrainingContentItem.objects.create(
            slug="course-builder-notebook",
            name="Course Builder Notebook",
            description="Notebook seed.",
            content_kind=TrainingContentItem.ContentKind.NOTEBOOK,
            status=TrainingContentItem.Status.PUBLISHED,
            access_scope=TrainingContentItem.AccessScope.AUTHENTICATED,
        )
        intro_library_item = OnlineCourseContentLibraryItem.objects.create(
            section_type=OnlineCourseContentLibraryItem.SECTION_INTRODUCTION,
            title="Welcome brief",
            description="Introductory overview",
            library_group="Introduction",
            asset_type=OnlineCourseContentLibraryItem.ASSET_TEXT,
            language=OnlineCourse.LOCALE_EN,
            body_markdown="## Welcome",
            is_active=True,
        )
        main_document = SimpleUploadedFile("market-overview.pdf", b"%PDF-1.4 test", content_type="application/pdf")
        main_library_item = OnlineCourseContentLibraryItem.objects.create(
            section_type=OnlineCourseContentLibraryItem.SECTION_MAIN,
            title="Market overview deck",
            description="Primary reading pack",
            library_group="Main content",
            asset_type=OnlineCourseContentLibraryItem.ASSET_DOCUMENT,
            language=OnlineCourse.LOCALE_EN,
            file_asset=main_document,
            is_active=True,
        )

        admin_client = APIClient()
        admin_client.force_authenticate(user=admin_user)
        create_response = admin_client.post(
            "/online/admin/course-builder/courses/",
            {
                "slug": "structured-quant-course",
                "titleDe": "Structured Quant Course",
                "titleEn": "Structured Quant Course",
                "shortDescriptionDe": "Structured short",
                "shortDescriptionEn": "Structured short",
                "descriptionDe": "Structured description",
                "descriptionEn": "Structured description",
                "trialAvailable": False,
                "priceAmount": "199.00",
                "currency": "EUR",
                "isSubscription": False,
                "isPublished": True,
                "audienceIds": [demo_audiences["interns-new-grads"].id],
                "lessons": [
                    {
                        "title": "Lesson 1",
                        "description": "Lesson intro",
                        "sortOrder": 1,
                        "sections": [
                            {
                                "sectionType": "introduction",
                                "title": "Introduction",
                                "description": "Intro section",
                                "sortOrder": 10,
                                "items": [
                                    {
                                        "sourceLibraryItemId": intro_library_item.id,
                                        "assetType": "text",
                                        "language": "en",
                                        "sortOrder": 1,
                                    }
                                ],
                            },
                            {
                                "sectionType": "main",
                                "title": "Main content",
                                "description": "Main section",
                                "sortOrder": 20,
                                "items": [
                                    {
                                        "sourceLibraryItemId": main_library_item.id,
                                        "assetType": "document",
                                        "language": "en",
                                        "sortOrder": 1,
                                    },
                                    {
                                        "title": "Notebook lab",
                                        "description": "Hands-on exercise",
                                        "assetType": "notebook",
                                        "language": "en",
                                        "linkedTrainingContentId": notebook_content.id,
                                        "audienceIds": [demo_audiences["lateral-transfers"].id],
                                        "sortOrder": 2,
                                    },
                                ],
                            },
                            {
                                "sectionType": "conclusion",
                                "title": "Conclusion",
                                "description": "Conclusion section",
                                "sortOrder": 30,
                                "items": [
                                    {
                                        "title": "Homework note",
                                        "description": "Read the recap and prepare questions.",
                                        "assetType": "text",
                                        "language": "en",
                                        "bodyMarkdown": "Complete the homework.",
                                        "sortOrder": 1,
                                    }
                                ],
                            },
                        ],
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        course = OnlineCourse.objects.get(slug="structured-quant-course")
        self.assertEqual(course.lessons_count, 1)
        self.assertEqual(course.structured_lessons.count(), 1)
        self.assertEqual(create_response.data["structureSummary"]["itemsCount"], 4)
        self.assertEqual(len(create_response.data["lessons"]), 1)
        self.assertEqual(create_response.data["audienceIds"], [demo_audiences["interns-new-grads"].id])
        self.assertEqual(
            create_response.data["lessons"][0]["sections"][1]["items"][1]["audienceIds"],
            [demo_audiences["lateral-transfers"].id],
        )

        teacher_user, teacher = self._create_teacher(index=202)
        cohort = self._create_cohort(course=course, group_code="STRUCTURED_Q1", teacher=teacher)
        student_user = User.objects.create_user(
            email="structured.student@example.com",
            username="structured_student",
            password="StrongPass12345",
        )
        TrainingUserAudienceGrant.objects.create(
            user=student_user,
            audience=demo_audiences["interns-new-grads"],
        )
        student_profile = OnlineStudentProfile.objects.create(
            user=student_user,
            first_name="Structured",
            last_name="Student",
            preferred_language="en",
        )
        OnlineEnrollment.objects.create(
            profile=student_profile,
            course=course,
            cohort=cohort,
            status=OnlineEnrollment.STATUS_ACTIVE,
        )

        student_client = APIClient()
        student_client.force_authenticate(user=student_user)
        dashboard_response = student_client.get("/online/student/dashboard/")

        self.assertEqual(dashboard_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(dashboard_response.data["enrollments"]), 1)
        self.assertEqual(len(dashboard_response.data["enrollments"][0]["lessonPlan"]), 1)
        projected_material_titles = {item["title"] for item in dashboard_response.data["enrollments"][0]["materials"]}
        self.assertTrue(any("Lesson 1" in title for title in projected_material_titles))

        teacher_client = APIClient()
        teacher_client.force_authenticate(user=teacher_user)
        workspace_response = teacher_client.get("/online/teacher/workspace/")

        self.assertEqual(workspace_response.status_code, status.HTTP_200_OK)
        self.assertIn(str(course.id), {str(key) for key in workspace_response.data["lessonPlansByCourse"].keys()})
        self.assertGreaterEqual(len(workspace_response.data["materials"]), 1)

    def test_admin_can_patch_legacy_lesson_to_main_only_section(self):
        admin_user = self._create_admin_user(index=215)
        client = APIClient()
        client.force_authenticate(user=admin_user)
        create_response = client.post(
            "/online/admin/course-builder/courses/",
            {
                "slug": "legacy-three-section-course",
                "titleDe": "Legacy three section course",
                "titleEn": "Legacy three section course",
                "shortDescriptionDe": "Short",
                "shortDescriptionEn": "Short",
                "descriptionDe": "Description",
                "descriptionEn": "Description",
                "trialAvailable": False,
                "priceAmount": "0.00",
                "currency": "EUR",
                "isSubscription": False,
                "isPublished": True,
                "lessons": [
                    {
                        "title": "Legacy lesson",
                        "description": "Created with the old section layout.",
                        "sortOrder": 1,
                        "sections": [
                            {
                                "sectionType": "introduction",
                                "title": "Introduction",
                                "description": "",
                                "sortOrder": 10,
                                "items": [
                                    {
                                        "title": "Intro note",
                                        "description": "",
                                        "assetType": "text",
                                        "activityType": "text",
                                        "language": "en",
                                        "bodyMarkdown": "Intro",
                                        "sortOrder": 1,
                                    }
                                ],
                            },
                            {
                                "sectionType": "main",
                                "title": "Main content",
                                "description": "",
                                "sortOrder": 20,
                                "items": [
                                    {
                                        "title": "Main note",
                                        "description": "",
                                        "assetType": "text",
                                        "activityType": "text",
                                        "language": "en",
                                        "bodyMarkdown": "Main",
                                        "sortOrder": 1,
                                    }
                                ],
                            },
                            {
                                "sectionType": "conclusion",
                                "title": "Conclusion",
                                "description": "",
                                "sortOrder": 30,
                                "items": [
                                    {
                                        "title": "Conclusion note",
                                        "description": "",
                                        "assetType": "text",
                                        "activityType": "text",
                                        "language": "en",
                                        "bodyMarkdown": "Conclusion",
                                        "sortOrder": 1,
                                    }
                                ],
                            },
                        ],
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        course = OnlineCourse.objects.get(slug="legacy-three-section-course")
        module = course.modules.get()
        lesson = course.structured_lessons.get()
        main_section = lesson.sections.get(section_type="main")
        self.assertEqual(lesson.sections.count(), 3)

        patch_response = client.patch(
            f"/online/admin/course-builder/courses/{course.id}/",
            {
                "modules": [
                    {
                        "id": module.id,
                        "title": module.title,
                        "description": module.description,
                        "moduleType": module.module_type,
                        "weekNumber": module.week_number,
                        "sortOrder": module.sort_order,
                        "isActive": module.is_active,
                        "lessons": [
                            {
                                "id": lesson.id,
                                "title": "Legacy lesson updated",
                                "description": "Only main content remains.",
                                "sortOrder": 1,
                                "isActive": True,
                                "sections": [
                                    {
                                        "id": main_section.id,
                                        "sectionType": "main",
                                        "title": "Main content",
                                        "description": "Single section",
                                        "sortOrder": 10,
                                        "isActive": True,
                                        "items": [
                                            {
                                                "title": "Updated main note",
                                                "description": "",
                                                "assetType": "text",
                                                "activityType": "text",
                                                "language": "en",
                                                "bodyMarkdown": "Main only",
                                                "sortOrder": 1,
                                            }
                                        ],
                                    }
                                ],
                            }
                        ],
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(patch_response.status_code, status.HTTP_200_OK)
        lesson.refresh_from_db()
        sections = list(lesson.sections.order_by("sort_order", "id"))
        self.assertEqual(len(sections), 1)
        self.assertEqual(sections[0].section_type, "main")
        self.assertEqual(sections[0].items.count(), 1)
        self.assertEqual(patch_response.data["lessons"][0]["sections"][0]["sectionType"], "main")
        self.assertEqual(len(patch_response.data["lessons"][0]["sections"]), 1)

    def test_admin_can_create_course_with_modules_payload_and_student_receives_course_structure_tree(self):
        admin_user = self._create_admin_user(index=209)
        notebook_content = TrainingContentItem.objects.create(
            slug="module-builder-notebook",
            name="Module Builder Notebook",
            description="Notebook for module payload test.",
            content_kind=TrainingContentItem.ContentKind.NOTEBOOK,
            status=TrainingContentItem.Status.PUBLISHED,
            access_scope=TrainingContentItem.AccessScope.AUTHENTICATED,
            supports_inline_lab=True,
        )

        client = APIClient()
        client.force_authenticate(user=admin_user)
        response = client.post(
            "/online/admin/course-builder/courses/",
            {
                "slug": "module-payload-course",
                "titleDe": "Module payload course",
                "titleEn": "Module payload course",
                "shortDescriptionDe": "Short",
                "shortDescriptionEn": "Short",
                "descriptionDe": "Description",
                "descriptionEn": "Description",
                "trialAvailable": False,
                "priceAmount": "0.00",
                "currency": "EUR",
                "isPublished": True,
                "modules": [
                    {
                        "title": "Module 1 (Week 1)",
                        "description": "Main module",
                        "moduleType": "module",
                        "weekNumber": 1,
                        "sortOrder": 10,
                        "lessons": [
                            {
                                "title": "Lesson 1",
                                "description": "Lesson description",
                                "sortOrder": 1,
                                "sections": [
                                    {
                                        "sectionType": "introduction",
                                        "title": "Introduction",
                                        "description": "",
                                        "sortOrder": 10,
                                        "items": [
                                            {
                                                "title": "Intro text",
                                                "description": "",
                                                "assetType": "text",
                                                "activityType": "text",
                                                "language": "en",
                                                "bodyMarkdown": "Intro",
                                                "sortOrder": 1,
                                            }
                                        ],
                                    },
                                    {
                                        "sectionType": "main",
                                        "title": "Main content",
                                        "description": "",
                                        "sortOrder": 20,
                                        "items": [
                                            {
                                                "title": "Video item",
                                                "description": "",
                                                "assetType": "link",
                                                "activityType": "video",
                                                "language": "en",
                                                "externalUrl": "https://example.com/video",
                                                "sortOrder": 1,
                                            },
                                            {
                                                "title": "Quiz item",
                                                "description": "",
                                                "assetType": "text",
                                                "activityType": "quiz",
                                                "language": "en",
                                                "bodyMarkdown": "- Q1",
                                                "sortOrder": 2,
                                            },
                                            {
                                                "title": "Assignment item",
                                                "description": "",
                                                "assetType": "notebook",
                                                "activityType": "assignment",
                                                "language": "en",
                                                "linkedTrainingContentId": notebook_content.id,
                                                "sortOrder": 3,
                                            },
                                        ],
                                    },
                                    {
                                        "sectionType": "conclusion",
                                        "title": "Conclusion",
                                        "description": "",
                                        "sortOrder": 30,
                                        "items": [],
                                    },
                                ],
                            }
                        ],
                    },
                    {
                        "title": "Final Project / Exam",
                        "description": "Final assessment",
                        "moduleType": "final_assessment",
                        "sortOrder": 20,
                        "lessons": [
                            {
                                "title": "Final project",
                                "description": "Final",
                                "sortOrder": 1,
                                "sections": [
                                    {"sectionType": "introduction", "title": "Introduction", "description": "", "sortOrder": 10, "items": []},
                                    {"sectionType": "main", "title": "Main content", "description": "", "sortOrder": 20, "items": []},
                                    {"sectionType": "conclusion", "title": "Conclusion", "description": "", "sortOrder": 30, "items": []},
                                ],
                            }
                        ],
                    },
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        course = OnlineCourse.objects.get(slug="module-payload-course")
        self.assertEqual(course.modules.count(), 2)
        self.assertTrue(course.modules.filter(module_type=OnlineCourseModule.MODULE_TYPE_FINAL).exists())
        self.assertEqual(response.data["structureSummary"]["modulesCount"], 2)
        self.assertEqual(response.data["structureSummary"]["finalAssessmentModulesCount"], 1)

        teacher_user, teacher = self._create_teacher(index=209)
        cohort = self._create_cohort(course=course, group_code="MODULE_TREE_G1", teacher=teacher)
        student_user = User.objects.create_user(
            email="module.tree.student@example.com",
            username="module_tree_student",
            password="StrongPass12345",
        )
        student_profile = OnlineStudentProfile.objects.create(
            user=student_user,
            first_name="Module",
            last_name="Tree",
            preferred_language="en",
        )
        OnlineEnrollment.objects.create(
            profile=student_profile,
            course=course,
            cohort=cohort,
            status=OnlineEnrollment.STATUS_ACTIVE,
        )

        student_client = APIClient()
        student_client.force_authenticate(user=student_user)
        dashboard_response = student_client.get("/online/student/dashboard/")

        self.assertEqual(dashboard_response.status_code, status.HTTP_200_OK)
        structure = dashboard_response.data["enrollments"][0]["courseStructure"]
        self.assertEqual(len(structure["modules"]), 2)
        self.assertEqual(structure["finalAssessment"]["moduleType"], "final_assessment")
        first_lesson = structure["modules"][0]["lessons"][0]
        main_items = first_lesson["sections"][1]["items"]
        self.assertEqual({item["activityType"] for item in main_items}, {"video", "quiz", "assignment"})
        interactive_lesson = first_lesson["interactiveLesson"]
        self.assertEqual(interactive_lesson["lessonTitle"], "Lesson 1")
        self.assertGreaterEqual(len(interactive_lesson["steps"]), 4)
        self.assertEqual(
            [step["kind"] for step in interactive_lesson["steps"][:4]],
            ["theory", "video", "quiz", "practice"],
        )
        self.assertEqual(interactive_lesson["demoVariantKey"], f"interactive-lesson-{first_lesson['id']}")

    def test_admin_can_import_coursera_like_payload_and_link_training_content(self):
        admin_user = self._create_admin_user(index=210)
        notebook_content = TrainingContentItem.objects.create(
            slug="coursera-import-notebook",
            name="Coursera Import Notebook",
            description="Notebook for import endpoint.",
            content_kind=TrainingContentItem.ContentKind.NOTEBOOK,
            status=TrainingContentItem.Status.PUBLISHED,
            access_scope=TrainingContentItem.AccessScope.AUTHENTICATED,
            supports_inline_lab=True,
        )

        client = APIClient()
        client.force_authenticate(user=admin_user)
        response = client.post(
            "/online/admin/course-builder/import/",
            {
                "source": "coursera_json",
                "payload": {
                    "title": "Imported Coursera Course",
                    "modules": [
                        {
                            "title": "Module 1 (Week 1)",
                            "lessons": [
                                {
                                    "title": "Lesson 1",
                                    "contentItems": [
                                        {"type": "video", "title": "Video", "url": "https://example.com/video"},
                                        {"type": "reading", "title": "Reading", "text": "Read chapter 1"},
                                        {"type": "quiz", "title": "Quiz", "questions": [{"question": "Q1"}]},
                                        {
                                            "type": "assignment",
                                            "title": "Notebook task",
                                            "trainingContentId": notebook_content.id,
                                            "instructions": "Solve notebook tasks",
                                        },
                                    ],
                                }
                            ],
                        }
                    ],
                    "finalAssessment": {
                        "title": "Final Project / Exam",
                        "description": "Final",
                        "instructions": "Submit final notebook",
                    },
                },
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["titleEn"], "Imported Coursera Course")
        self.assertGreaterEqual(len(response.data["modules"]), 2)
        self.assertTrue(any(module["moduleType"] == "final_assessment" for module in response.data["modules"]))

        course = OnlineCourse.objects.get(id=response.data["id"])
        assignment_item = (
            course.structured_lessons.filter(
                sections__items__activity_type="assignment",
                sections__items__linked_training_content_id__isnull=False,
            )
            .values_list("sections__items__linked_training_content_id", flat=True)
            .first()
        )
        self.assertEqual(assignment_item, notebook_content.id)

    def test_admin_course_library_crud_supports_notebook_and_document_assets(self):
        admin_user = self._create_admin_user(index=203)
        demo_audiences = self._ensure_demo_audiences()
        notebook_content = TrainingContentItem.objects.create(
            slug="library-notebook",
            name="Library Notebook",
            description="Notebook option",
            content_kind=TrainingContentItem.ContentKind.NOTEBOOK,
            status=TrainingContentItem.Status.PUBLISHED,
            access_scope=TrainingContentItem.AccessScope.AUTHENTICATED,
        )
        client = APIClient()
        client.force_authenticate(user=admin_user)
        upload = SimpleUploadedFile("intro.pdf", b"%PDF-1.4 intro", content_type="application/pdf")

        create_response = client.post(
            "/online/admin/course-library/",
            {
                "sectionType": "main",
                "title": "Main PDF",
                "description": "PDF asset",
                "libraryGroup": "Main content",
                "assetType": "document",
                "language": "en",
                "file": upload,
                "audienceIds": [demo_audiences["interns-new-grads"].id],
                "sortOrder": 3,
                "isActive": True,
            },
        )
        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        item_id = create_response.data["id"]
        self.assertEqual(create_response.data["audienceIds"], [demo_audiences["interns-new-grads"].id])
        self.assertIn(f"/api/online/media/course-library/{item_id}/file/", create_response.data["fileUrl"])
        file_response = client.get(create_response.data["fileUrl"])
        self.assertEqual(file_response.status_code, status.HTTP_200_OK)

        notebook_response = client.post(
            "/online/admin/course-library/",
            {
                "sectionType": "main",
                "title": "Notebook asset",
                "description": "Notebook entry",
                "libraryGroup": "Notebook library",
                "assetType": "notebook",
                "language": "en",
                "trainingContentId": notebook_content.id,
                "audienceIds": [demo_audiences["lateral-transfers"].id],
                "sortOrder": 4,
                "isActive": True,
            },
            format="json",
        )
        self.assertEqual(notebook_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(notebook_response.data["trainingContentId"], notebook_content.id)
        self.assertEqual(notebook_response.data["audienceIds"], [demo_audiences["lateral-transfers"].id])

        list_response = client.get("/online/admin/course-library/", {"section_type": "main"})
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(list_response.data["results"]), 2)

        delete_response = client.delete(f"/online/admin/course-library/{item_id}/")
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)

    def test_course_section_item_file_download_requires_enrollment(self):
        course = self._create_course(slug="secure-course-files", trial_available=True, price_amount=Decimal("0.00"))
        lesson = OnlineCourseLesson.objects.create(course=course, title="Secure lesson", sort_order=1, is_active=True)
        section = OnlineCourseLessonSection.objects.create(
            lesson=lesson,
            section_type=OnlineCourseContentLibraryItem.SECTION_MAIN,
            title="Main",
            sort_order=1,
            is_active=True,
        )
        item = OnlineCourseLessonSectionItem.objects.create(
            section=section,
            title="Private handout",
            asset_type=OnlineCourseContentLibraryItem.ASSET_DOCUMENT,
            activity_type=OnlineCourseLessonSectionItem.ACTIVITY_TEXT,
            sort_order=1,
            is_active=True,
        )
        item.file_asset.save(
            "private-handout.pdf",
            SimpleUploadedFile("private-handout.pdf", b"%PDF private", content_type="application/pdf"),
            save=True,
        )
        cohort = OnlineCohort.objects.create(
            course=course,
            name="Secure cohort",
            group_code="SECURE_FILES",
            status=OnlineCohort.STATUS_OPEN,
        )
        enrolled_user = User.objects.create_user(
            username="secure-file-student",
            email="secure-file-student@example.com",
            password="secret",
        )
        enrolled_profile = OnlineStudentProfile.objects.create(
            user=enrolled_user,
            first_name="Secure",
            last_name="Student",
        )
        OnlineEnrollment.objects.create(profile=enrolled_profile, course=course, cohort=cohort)
        other_user = User.objects.create_user(
            username="other-file-student",
            email="other-file-student@example.com",
            password="secret",
        )
        OnlineStudentProfile.objects.create(user=other_user, first_name="Other", last_name="Student")

        file_url = f"/api/online/media/course-section-items/{item.id}/file/"
        enrolled_client = APIClient()
        enrolled_client.force_authenticate(user=enrolled_user)
        enrolled_response = enrolled_client.get(file_url)
        self.assertEqual(enrolled_response.status_code, status.HTTP_200_OK)

        other_client = APIClient()
        other_client.force_authenticate(user=other_user)
        other_response = other_client.get(file_url)
        self.assertEqual(other_response.status_code, status.HTTP_404_NOT_FOUND)

    def test_admin_course_library_accepts_uploaded_video_for_link_asset(self):
        admin_user = self._create_admin_user(index=213)
        client = APIClient()
        client.force_authenticate(user=admin_user)
        upload = SimpleUploadedFile("lesson-video.mp4", b"video-bytes", content_type="video/mp4")

        response = client.post(
            "/online/admin/course-library/",
            {
                "sectionType": "main",
                "title": "Lesson video",
                "description": "Uploaded video walkthrough",
                "libraryGroup": "Generated lesson videos",
                "assetType": "link",
                "language": "en",
                "file": upload,
                "sortOrder": 1,
                "isActive": True,
            },
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["assetType"], "link")
        self.assertTrue(response.data["fileUrl"])

    @override_settings(TRAINING_AI_ENABLED=False)
    def test_admin_can_generate_structured_lesson_document_from_source_text(self):
        admin_user = self._create_admin_user(index=214)
        client = APIClient()
        client.force_authenticate(user=admin_user)

        response = client.post(
            "/online/admin/course-builder/lessons/generate/",
            {
                "title": "Python Variables",
                "description": "Intro to variables and simple value storage.",
                "language": "en",
                "sourceText": (
                    "Variables let you store values under a readable name.\n\n"
                    "Use descriptive names, assign with `=`, and update values carefully.\n\n"
                    "- Create variables with clear names.\n"
                    "- Reassign values when the state changes.\n"
                    "- Review the lesson before moving to practice."
                ),
                "videoDescription": "Walk through creating and updating variables in a short coding demo.",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["meta"]["mode"], "fallback")
        document = response.data["document"]
        self.assertEqual(document["title"], "Python Variables")
        self.assertEqual(len(document["sections"]), 1)
        self.assertEqual(document["sections"][0]["sectionType"], "main")
        items = document["sections"][0]["items"]
        self.assertEqual(items[0]["title"], "Theory")
        self.assertEqual(items[2]["activityType"], "video")
        self.assertEqual(items[3]["activityType"], "quiz")
        self.assertEqual(len(items[3]["structuredData"]["questions"]), 3)
        self.assertEqual(
            items[4]["structuredData"]["practiceMode"],
            "code_editor",
        )
        self.assertEqual(
            items[4]["structuredData"]["grader"]["type"],
            "python_function_check",
        )

    @override_settings(
        TRAINING_AI_ENABLED=True,
        COURSE_BUILDER_AI_ORCHESTRATOR="legacy",
        TRAINING_AI_PROVIDER="demo",
    )
    def test_admin_lesson_generation_legacy_orchestrator_uses_existing_provider(self):
        admin_user = self._create_admin_user(index=216)
        client = APIClient()
        client.force_authenticate(user=admin_user)
        provider = Mock()
        provider.provider_name = "legacy-test-provider"
        provider.model_name = "legacy-test-model"
        provider.generate_answer.return_value = Mock(
            short_answer="Legacy short answer.",
            detailed_answer=(
                "## Theory\n\n- Legacy generated theory.\n\n"
                "## Concept\n\n- Legacy generated concept.\n\n"
                "## Wrap-up\n\n- Legacy generated summary."
            ),
            follow_up_prompts=[],
            resolution_status="resolved",
        )

        with patch("apps.online.services.lesson_generator.get_training_ai_provider", return_value=provider):
            response = client.post(
                "/online/admin/course-builder/lessons/generate/",
                {
                    "title": "Python Variables",
                    "description": "Intro to variables.",
                    "language": "en",
                    "sourceText": "Variables store values under readable names.\n\nUse assignment carefully.",
                },
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["meta"]["mode"], "ai")
        self.assertEqual(response.data["meta"]["provider"], "legacy-test-provider")
        self.assertEqual(response.data["meta"]["model"], "legacy-test-model")
        self.assertEqual(response.data["meta"]["orchestrator"], "legacy")
        provider.generate_answer.assert_called_once()

    @override_settings(
        TRAINING_AI_ENABLED=True,
        COURSE_BUILDER_AI_ORCHESTRATOR="agents",
        TRAINING_AI_API_KEY="test-key",
        TRAINING_AI_CHAT_MODEL="gpt-test",
    )
    def test_admin_lesson_generation_agents_orchestrator_returns_generated_document(self):
        admin_user = self._create_admin_user(index=217)
        client = APIClient()
        client.force_authenticate(user=admin_user)
        agents_blueprint = {
            "description": "Generated by Agents SDK.",
            "theoryMarkdown": "## Theory\n\n- Agent theory.",
            "conceptMarkdown": "## Concept\n\n- Agent concept.",
            "summaryMarkdown": "## Wrap-up\n\n- Agent summary.",
            "quiz": {
                "prompt": "What should a variable name do?",
                "title": "Variables check",
                "questions": [
                    {
                        "id": "q1",
                        "prompt": "What should a variable name do?",
                        "options": [
                            {"id": "a", "label": "Describe the stored value.", "isCorrect": True},
                            {"id": "b", "label": "Hide the stored value.", "isCorrect": False},
                        ],
                        "successMessage": "Correct.",
                        "errorMessage": "Try again.",
                        "explanationMarkdown": "## Why this is correct\n\n- Names should be readable.",
                    }
                ],
                "successMessage": "Correct.",
                "errorMessage": "Some answers are still incorrect.",
                "explanationMarkdown": "",
            },
            "practice": {
                "title": "Agent practice",
                "description": "Complete the variable summary.",
                "contentMarkdown": "## Practice\n\n- Return a variable summary.",
                "starterCode": "def build_summary():\n    return {}\n",
                "hint": "Use a readable key.",
                "solution": "def build_summary():\n    return {'name': 'total'}\n",
                "grader": {"type": "python_function_check", "function_name": "build_summary"},
            },
            "provider": "openai-agents",
            "model": "gpt-test",
            "orchestrator": "agents",
        }

        with patch(
            "apps.online.services.lesson_generator.generate_course_builder_lesson_blueprint_with_agents",
            return_value=agents_blueprint,
        ) as agents_mock, patch("apps.online.services.lesson_generator.get_training_ai_provider") as legacy_provider_mock:
            response = client.post(
                "/online/admin/course-builder/lessons/generate/",
                {
                    "title": "Python Variables",
                    "description": "Intro to variables.",
                    "language": "en",
                    "sourceText": "Variables store values under readable names.\n\nUse assignment carefully.",
                },
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["meta"]["mode"], "ai")
        self.assertEqual(response.data["meta"]["provider"], "openai-agents")
        self.assertEqual(response.data["meta"]["model"], "gpt-test")
        self.assertEqual(response.data["meta"]["orchestrator"], "agents")
        self.assertEqual(response.data["document"]["sections"][0]["items"][4]["title"], "Agent practice")
        agents_mock.assert_called_once()
        legacy_provider_mock.assert_not_called()

    @override_settings(
        TRAINING_AI_ENABLED=True,
        COURSE_BUILDER_AI_ORCHESTRATOR="agents",
        TRAINING_AI_PROVIDER="demo",
    )
    def test_admin_lesson_generation_agents_failure_falls_back_to_legacy_provider(self):
        admin_user = self._create_admin_user(index=218)
        client = APIClient()
        client.force_authenticate(user=admin_user)
        provider = Mock()
        provider.provider_name = "legacy-after-agents-error"
        provider.model_name = "legacy-model"
        provider.generate_answer.return_value = Mock(
            short_answer="Fallback short answer.",
            detailed_answer=(
                "## Theory\n\n- Fallback theory.\n\n"
                "## Concept\n\n- Fallback concept.\n\n"
                "## Wrap-up\n\n- Fallback summary."
            ),
            follow_up_prompts=[],
            resolution_status="resolved",
        )

        with patch(
            "apps.online.services.lesson_generator.generate_course_builder_lesson_blueprint_with_agents",
            side_effect=CourseBuilderAgentsError("agents failed"),
        ), patch("apps.online.services.lesson_generator.get_training_ai_provider", return_value=provider):
            response = client.post(
                "/online/admin/course-builder/lessons/generate/",
                {
                    "title": "Python Variables",
                    "description": "Intro to variables.",
                    "language": "en",
                    "sourceText": "Variables store values under readable names.\n\nUse assignment carefully.",
                },
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["meta"]["mode"], "ai")
        self.assertEqual(response.data["meta"]["provider"], "legacy-after-agents-error")
        self.assertEqual(response.data["meta"]["orchestrator"], "legacy")
        provider.generate_answer.assert_called_once()

    @override_settings(
        TRAINING_AI_ENABLED=False,
        TRAINING_AI_BASE_URL="https://ai.example/v1",
        TRAINING_AI_API_KEY="test-key",
        TRAINING_AI_TRANSCRIPTION_MODEL="whisper-test",
    )
    def test_admin_can_generate_structured_lesson_document_from_uploaded_video(self):
        admin_user = self._create_admin_user(index=215)
        client = APIClient()
        client.force_authenticate(user=admin_user)
        upload = SimpleUploadedFile("variables.mp4", b"video-bytes", content_type="video/mp4")
        transcription_response = Mock()
        transcription_response.json.return_value = {
            "text": (
                "Variables store values under readable names. "
                "The lesson explains assignment with equals and shows how to update a value safely."
            )
        }
        transcription_response.raise_for_status.return_value = None

        with patch("apps.online.services.video_lesson_generation.shutil.which", return_value=None), patch(
            "apps.online.services.video_lesson_generation.requests.post",
            return_value=transcription_response,
        ) as post_mock:
            response = client.post(
                "/online/admin/course-builder/lessons/generate-from-video/",
                {
                    "title": "Python Variables",
                    "description": "Intro to variables from a source video.",
                    "language": "en",
                    "videoDescription": "Watch variables being created and updated.",
                    "videoFile": upload,
                },
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["meta"]["mode"], "fallback")
        self.assertEqual(response.data["meta"]["source"], "video_transcript")
        self.assertEqual(response.data["meta"]["transcriptionModel"], "whisper-test")
        self.assertGreater(response.data["meta"]["transcriptCharacters"], 20)
        self.assertTrue(response.data["transcriptText"].startswith("Variables store values"))
        post_mock.assert_called_once()
        self.assertEqual(post_mock.call_args.args[0], "https://ai.example/v1/audio/transcriptions")

        video_item = OnlineCourseContentLibraryItem.objects.get(id=response.data["meta"]["videoLibraryItemId"])
        self.assertEqual(video_item.title, "Python Variables video")
        self.assertTrue(video_item.file_asset.name)

        items = response.data["document"]["sections"][0]["items"]
        video_items = [item for item in items if item["activityType"] == "video"]
        self.assertEqual(len(video_items), 1)
        self.assertEqual(video_items[0]["sourceLibraryItemId"], video_item.id)
        self.assertTrue(video_items[0]["externalUrl"])

    def test_admin_can_patch_course_builder_course_without_full_payload(self):
        admin_user = self._create_admin_user(index=204)
        course = self._create_course(
            slug="course-builder-partial-update",
            trial_available=False,
            price_amount=Decimal("25.00"),
        )

        client = APIClient()
        client.force_authenticate(user=admin_user)
        response = client.patch(
            f"/online/admin/course-builder/courses/{course.id}/",
            {
                "isPublished": False,
                "titleEn": "Updated course title",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        course.refresh_from_db()
        self.assertFalse(course.is_published)
        self.assertEqual(course.title_en, "Updated course title")

    def test_admin_can_move_course_into_review_and_get_governance_audit_entries(self):
        admin_user = self._create_admin_user(index=2041)
        course = self._create_course(
            slug="course-builder-governance",
            trial_available=False,
            price_amount=Decimal("25.00"),
        )

        client = APIClient()
        client.force_authenticate(user=admin_user)
        response = client.patch(
            f"/online/admin/course-builder/courses/{course.id}/",
            {
                "lifecycleStatus": "in_review",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        course.refresh_from_db()
        self.assertEqual(course.lifecycle_status, OnlineCourse.LIFECYCLE_IN_REVIEW)
        self.assertFalse(course.is_published)
        self.assertEqual(response.data["governance"]["lifecycleStatus"], "in_review")
        self.assertEqual(response.data["governance"]["lifecycleLabel"], "In review")
        self.assertTrue(
            OnlineCourseApproval.objects.filter(
                course=course,
                action=OnlineCourseApproval.ACTION_SUBMITTED,
                to_status=OnlineCourse.LIFECYCLE_IN_REVIEW,
            ).exists()
        )
        self.assertTrue(
            OnlineAuditEvent.objects.filter(
                course=course,
                event_type="course.lifecycle.changed",
            ).exists()
        )

    def test_admin_can_create_course_builder_course_in_draft_with_governance_payload(self):
        admin_user = self._create_admin_user(index=2042)

        client = APIClient()
        client.force_authenticate(user=admin_user)
        response = client.post(
            "/online/admin/course-builder/courses/",
            {
                "slug": "governed-course-create",
                "titleEn": "Governed Course",
                "titleDe": "Governed Course",
                "shortDescriptionEn": "Short description",
                "shortDescriptionDe": "Short description",
                "descriptionEn": "Long description",
                "descriptionDe": "Long description",
                "priceAmount": "0.00",
                "currency": "EUR",
                "isSubscription": False,
                "isPublished": False,
                "lifecycleStatus": "draft",
                "geoCity": "Berlin",
                "geoCountry": "DE",
                "modules": [
                    {
                        "title": "Module 1",
                        "description": "Module description",
                        "moduleType": "module",
                        "weekNumber": 1,
                        "sortOrder": 10,
                        "isActive": True,
                        "lessons": [
                            {
                                "title": "Lesson 1",
                                "description": "Lesson description",
                                "sortOrder": 1,
                                "isActive": True,
                                "sections": [
                                    {
                                        "sectionType": "introduction",
                                        "title": "Intro",
                                        "description": "",
                                        "sortOrder": 10,
                                        "isActive": True,
                                        "items": [],
                                    },
                                    {
                                        "sectionType": "main",
                                        "title": "Main",
                                        "description": "",
                                        "sortOrder": 20,
                                        "isActive": True,
                                        "items": [],
                                    },
                                    {
                                        "sectionType": "conclusion",
                                        "title": "Wrap",
                                        "description": "",
                                        "sortOrder": 30,
                                        "isActive": True,
                                        "items": [],
                                    },
                                ],
                            }
                        ],
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["lifecycleStatus"], "draft")
        self.assertEqual(response.data["governance"]["lifecycleStatus"], "draft")
        self.assertFalse(response.data["governance"]["isPubliclyVisible"])
        created_course = OnlineCourse.objects.get(slug="governed-course-create")
        self.assertEqual(created_course.lifecycle_status, OnlineCourse.LIFECYCLE_DRAFT)
        self.assertFalse(created_course.is_published)
        self.assertEqual(response.data["governance"]["versionsCount"], 1)
        self.assertEqual(response.data["governance"]["latestVersion"]["versionNumber"], 1)
        self.assertTrue(
            OnlineAuditEvent.objects.filter(
                course=created_course,
                event_type="course.created",
            ).exists()
        )

    def test_admin_cannot_publish_course_when_release_checks_fail(self):
        admin_user = self._create_admin_user(index=2043)
        client = APIClient()
        client.force_authenticate(user=admin_user)

        create_response = client.post(
            "/online/admin/course-builder/courses/",
            {
                "slug": "blocked-release-course",
                "titleEn": "Blocked release",
                "titleDe": "Blocked release",
                "shortDescriptionEn": "Short description",
                "shortDescriptionDe": "Short description",
                "descriptionEn": "Long description",
                "descriptionDe": "Long description",
                "priceAmount": "0.00",
                "currency": "EUR",
                "isSubscription": False,
                "isPublished": False,
                "lifecycleStatus": "draft",
                "modules": [
                    {
                        "title": "Module 1",
                        "description": "Module description",
                        "moduleType": "module",
                        "weekNumber": 1,
                        "sortOrder": 10,
                        "lessons": [
                            {
                                "title": "Lesson 1",
                                "description": "Lesson description",
                                "sortOrder": 1,
                                "sections": [
                                    {"sectionType": "introduction", "title": "Intro", "description": "", "sortOrder": 10, "items": []},
                                    {"sectionType": "main", "title": "Main", "description": "", "sortOrder": 20, "items": []},
                                    {"sectionType": "conclusion", "title": "Wrap", "description": "", "sortOrder": 30, "items": []},
                                ],
                            }
                        ],
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        course = OnlineCourse.objects.get(slug="blocked-release-course")

        publish_response = client.patch(
            f"/online/admin/course-builder/courses/{course.id}/",
            {"lifecycleStatus": "published"},
            format="json",
        )

        self.assertEqual(publish_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Publish is blocked", publish_response.data["detail"])
        self.assertFalse(publish_response.data["releaseReadiness"]["isReadyForPublish"])
        course.refresh_from_db()
        self.assertEqual(course.lifecycle_status, OnlineCourse.LIFECYCLE_DRAFT)
        self.assertFalse(course.is_published)
        self.assertEqual(OnlineCourseVersion.objects.filter(course=course).count(), 1)

    def test_admin_can_publish_ready_course_and_capture_version_snapshot(self):
        admin_user = self._create_admin_user(index=2044)
        demo_audiences = self._ensure_demo_audiences()
        client = APIClient()
        client.force_authenticate(user=admin_user)

        create_response = client.post(
            "/online/admin/course-builder/courses/",
            {
                "slug": "publish-ready-course",
                "titleEn": "Publish ready course",
                "titleDe": "Publish ready course",
                "shortDescriptionEn": "Short description",
                "shortDescriptionDe": "Short description",
                "descriptionEn": "Long description",
                "descriptionDe": "Long description",
                "priceAmount": "0.00",
                "currency": "EUR",
                "isSubscription": False,
                "isPublished": False,
                "lifecycleStatus": "draft",
                "audienceIds": [demo_audiences["interns-new-grads"].id],
                "modules": [
                    {
                        "title": "Module 1",
                        "description": "Module description",
                        "moduleType": "module",
                        "weekNumber": 1,
                        "sortOrder": 10,
                        "lessons": [
                            {
                                "title": "Lesson 1",
                                "description": "Lesson description",
                                "sortOrder": 1,
                                "sections": [
                                    {
                                        "sectionType": "introduction",
                                        "title": "Intro",
                                        "description": "",
                                        "sortOrder": 10,
                                        "items": [
                                            {
                                                "title": "Theory",
                                                "description": "",
                                                "assetType": "text",
                                                "activityType": "text",
                                                "language": "en",
                                                "bodyMarkdown": "## Intro",
                                                "sortOrder": 1,
                                            }
                                        ],
                                    },
                                    {
                                        "sectionType": "main",
                                        "title": "Main",
                                        "description": "",
                                        "sortOrder": 20,
                                        "items": [
                                            {
                                                "title": "Video",
                                                "description": "",
                                                "assetType": "link",
                                                "activityType": "video",
                                                "language": "en",
                                                "externalUrl": "https://example.com/video",
                                                "sortOrder": 1,
                                            }
                                        ],
                                    },
                                    {
                                        "sectionType": "conclusion",
                                        "title": "Wrap",
                                        "description": "",
                                        "sortOrder": 30,
                                        "items": [
                                            {
                                                "title": "Summary",
                                                "description": "",
                                                "assetType": "text",
                                                "activityType": "text",
                                                "language": "en",
                                                "bodyMarkdown": "Done",
                                                "sortOrder": 1,
                                            }
                                        ],
                                    },
                                ],
                            }
                        ],
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        course = OnlineCourse.objects.get(slug="publish-ready-course")

        publish_response = client.patch(
            f"/online/admin/course-builder/courses/{course.id}/",
            {"lifecycleStatus": "published"},
            format="json",
        )

        self.assertEqual(publish_response.status_code, status.HTTP_200_OK)
        course.refresh_from_db()
        self.assertEqual(course.lifecycle_status, OnlineCourse.LIFECYCLE_PUBLISHED)
        self.assertTrue(course.is_published)
        self.assertTrue(publish_response.data["governance"]["readiness"]["isReadyForPublish"])
        self.assertEqual(publish_response.data["governance"]["versionsCount"], 2)
        self.assertEqual(publish_response.data["governance"]["latestVersion"]["versionNumber"], 2)
        self.assertTrue(
            OnlineCourseApproval.objects.filter(
                course=course,
                to_status=OnlineCourse.LIFECYCLE_PUBLISHED,
            ).exists()
        )
        self.assertEqual(OnlineCourseVersion.objects.filter(course=course).count(), 2)

    def test_admin_can_create_delivery_cohort_and_assign_curator_from_course_builder(self):
        admin_user = self._create_admin_user(index=205)
        _teacher_user, teacher = self._create_teacher(index=205)
        course = self._create_course(
            slug="course-builder-delivery",
            trial_available=False,
            price_amount=Decimal("55.00"),
        )

        client = APIClient()
        client.force_authenticate(user=admin_user)
        response = client.post(
            f"/online/admin/course-builder/courses/{course.id}/delivery/",
            {
                "groupCode": "DELIVERY_G1",
                "groupName": "Delivery Group 1",
                "capacity": 18,
                "timezone": "Europe/Berlin",
                "status": "open",
                "isPublic": True,
                "curatorId": teacher.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        cohort = OnlineCohort.objects.get(group_code="DELIVERY_G1")
        self.assertEqual(cohort.course_id, course.id)
        self.assertEqual(cohort.teacher_id, teacher.id)
        self.assertEqual(response.data["cohort"]["teacherId"], teacher.id)
        self.assertEqual(response.data["curator"]["id"], teacher.id)

        update_response = client.post(
            f"/online/admin/course-builder/courses/{course.id}/delivery/",
            {
                "cohortId": cohort.id,
                "groupName": "Delivery Group Prime",
                "status": "running",
                "isPublic": False,
                "curatorId": None,
            },
            format="json",
        )

        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        cohort.refresh_from_db()
        self.assertEqual(cohort.name, "Delivery Group Prime")
        self.assertEqual(cohort.status, OnlineCohort.STATUS_RUNNING)
        self.assertFalse(cohort.is_public)
        self.assertIsNone(cohort.teacher_id)

    def test_admin_can_seed_builder_sessions_for_delivery_cohort(self):
        admin_user = self._create_admin_user(index=206)
        course = self._create_course(
            slug="course-builder-session-seed",
            trial_available=False,
            price_amount=Decimal("65.00"),
        )
        course.lessons_count = 2
        course.save(update_fields=["lessons_count", "updated_at"])
        upsert_course_structure(
            course,
            [
                {
                    "title": "Foundations of CVA",
                    "description": "Introductory session.",
                    "sort_order": 1,
                    "is_active": True,
                    "sections": [
                        {"section_type": "introduction", "title": "Introduction", "description": "", "sort_order": 10, "is_active": True, "items": []},
                        {"section_type": "main", "title": "Main content", "description": "", "sort_order": 20, "is_active": True, "items": []},
                        {"section_type": "conclusion", "title": "Conclusion", "description": "", "sort_order": 30, "is_active": True, "items": []},
                    ],
                },
                {
                    "title": "Risk workshop",
                    "description": "Hands-on lab.",
                    "sort_order": 2,
                    "is_active": True,
                    "sections": [
                        {"section_type": "introduction", "title": "Introduction", "description": "", "sort_order": 10, "is_active": True, "items": []},
                        {"section_type": "main", "title": "Main content", "description": "", "sort_order": 20, "is_active": True, "items": []},
                        {"section_type": "conclusion", "title": "Conclusion", "description": "", "sort_order": 30, "is_active": True, "items": []},
                    ],
                },
            ],
        )
        cohort = self._create_cohort(course=course, group_code="BUILDER_SEED_G1", capacity=12)

        client = APIClient()
        client.force_authenticate(user=admin_user)
        response = client.post(
            f"/online/admin/course-builder/courses/{course.id}/sessions/",
            {
                "cohortId": cohort.id,
                "sessions": [
                    {
                        "title": "",
                        "description": "",
                        "startsAt": (timezone.now() + timedelta(days=3)).isoformat(),
                        "endsAt": (timezone.now() + timedelta(days=3, hours=2)).isoformat(),
                    },
                    {
                        "title": "Custom workshop",
                        "description": "Custom recap",
                        "startsAt": (timezone.now() + timedelta(days=10)).isoformat(),
                        "endsAt": (timezone.now() + timedelta(days=10, hours=2)).isoformat(),
                    },
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        created_sessions = list(OnlineSession.objects.filter(cohort=cohort).order_by("sort_order"))
        self.assertEqual(len(created_sessions), 2)
        self.assertEqual(created_sessions[0].title, "Foundations of CVA")
        self.assertIn("Introductory session.", created_sessions[0].description)
        self.assertIn("Introduction", created_sessions[0].description)
        self.assertIn("Main content", created_sessions[0].description)
        self.assertIn("Conclusion", created_sessions[0].description)
        self.assertEqual(created_sessions[1].title, "Custom workshop")
        self.assertEqual(response.data["createdCount"], 2)
        self.assertEqual(response.data["remainingSlots"], 0)
        self.assertEqual(len(response.data["sessions"]), 2)

    def test_builder_session_seed_uses_section_summaries_when_lesson_metadata_is_sparse(self):
        admin_user = self._create_admin_user(index=208)
        course = self._create_course(
            slug="course-builder-section-summary-seed",
            trial_available=False,
            price_amount=Decimal("68.00"),
        )
        course.lessons_count = 1
        course.save(update_fields=["lessons_count", "updated_at"])
        upsert_course_structure(
            course,
            [
                {
                    "title": "",
                    "description": "",
                    "sort_order": 1,
                    "is_active": True,
                    "sections": [
                        {"section_type": "introduction", "title": "Meet the curator", "description": "Context and expectations.", "sort_order": 10, "is_active": True, "items": []},
                        {"section_type": "main", "title": "Quant workshop", "description": "Notebook walkthrough.", "sort_order": 20, "is_active": True, "items": []},
                        {"section_type": "conclusion", "title": "Wrap-up", "description": "Next steps and self-study.", "sort_order": 30, "is_active": True, "items": []},
                    ],
                }
            ],
        )
        cohort = self._create_cohort(course=course, group_code="BUILDER_SECTION_G1", capacity=10)

        client = APIClient()
        client.force_authenticate(user=admin_user)
        response = client.post(
            f"/online/admin/course-builder/courses/{course.id}/sessions/",
            {
                "cohortId": cohort.id,
                "sessions": [
                    {
                        "title": "",
                        "description": "",
                        "startsAt": (timezone.now() + timedelta(days=5)).isoformat(),
                        "endsAt": (timezone.now() + timedelta(days=5, hours=2)).isoformat(),
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        session = OnlineSession.objects.get(cohort=cohort)
        self.assertEqual(session.title, "Meet the curator")
        self.assertIn("Meet the curator: Context and expectations.", session.description)
        self.assertIn("Quant workshop: Notebook walkthrough.", session.description)
        self.assertIn("Wrap-up: Next steps and self-study.", session.description)

    def _create_student_interactive_lesson_fixture(self, *, index: int, slug: str):
        course = self._create_course(
            slug=slug,
            trial_available=False,
            price_amount=Decimal("72.00"),
        )
        course.lessons_count = 1
        course.save(update_fields=["lessons_count", "updated_at"])

        notebook_content = TrainingContentItem.objects.create(
            slug=f"{slug}-notebook",
            name=f"{slug} Notebook",
            description="Notebook for dedicated lesson workspace tests.",
            content_kind=TrainingContentItem.ContentKind.NOTEBOOK,
            status=TrainingContentItem.Status.PUBLISHED,
            access_scope=TrainingContentItem.AccessScope.AUTHENTICATED,
            supports_inline_lab=True,
        )

        upsert_course_structure(
            course,
            modules_data=[
                {
                    "title": "Week 1 - Python Foundations",
                    "description": "Kick-off module for the dedicated lesson workspace.",
                    "moduleType": "module",
                    "weekNumber": 1,
                    "sortOrder": 1,
                    "isActive": True,
                    "lessons": [
                        {
                            "title": "Getting Started with Python",
                            "description": "Guided lesson flow for the student workspace.",
                            "sortOrder": 1,
                            "isActive": True,
                            "sections": [
                                {
                                    "sectionType": "introduction",
                                    "title": "Introduction",
                                    "description": "",
                                    "sortOrder": 10,
                                    "isActive": True,
                                    "items": [
                                        {
                                            "title": "Welcome brief",
                                            "description": "Orientation for the lesson.",
                                            "assetType": "text",
                                            "activityType": "text",
                                            "language": "en",
                                            "bodyMarkdown": "## Welcome\n\n- Understand how the lesson is structured.\n- Review the examples before you write code.",
                                            "sortOrder": 1,
                                            "isActive": True,
                                        }
                                    ],
                                },
                                {
                                    "sectionType": "main",
                                    "title": "Core concepts",
                                    "description": "",
                                    "sortOrder": 20,
                                    "isActive": True,
                                    "items": [
                                        {
                                            "title": "Core reading",
                                            "description": "Main concept notes.",
                                            "assetType": "text",
                                            "activityType": "text",
                                            "language": "en",
                                            "bodyMarkdown": "## Variables\n\n- Variables store values.\n- Choose descriptive names for your data.",
                                            "sortOrder": 1,
                                            "isActive": True,
                                        },
                                        {
                                            "title": "Walkthrough video",
                                            "description": "Watch the guided explanation.",
                                            "assetType": "link",
                                            "activityType": "video",
                                            "language": "en",
                                            "externalUrl": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                                            "sortOrder": 2,
                                            "isActive": True,
                                        },
                                        {
                                            "title": "Checkpoint quiz",
                                            "description": "Quick checkpoint before practice.",
                                            "assetType": "text",
                                            "activityType": "quiz",
                                            "language": "en",
                                            "bodyMarkdown": "- What is the main purpose of a variable?\n- A variable stores a value that can be reused.\n- Descriptive names make code easier to follow.",
                                            "sortOrder": 3,
                                            "isActive": True,
                                        },
                                        {
                                            "title": "Practice notebook",
                                            "description": "Apply the concept in the lab.",
                                            "assetType": "notebook",
                                            "activityType": "assignment",
                                            "language": "en",
                                            "bodyMarkdown": "Complete the notebook after reviewing the theory and video.",
                                            "linkedTrainingContentId": notebook_content.id,
                                            "sortOrder": 4,
                                            "isActive": True,
                                        },
                                    ],
                                },
                                {
                                    "sectionType": "conclusion",
                                    "title": "Wrap-up",
                                    "description": "",
                                    "sortOrder": 30,
                                    "isActive": True,
                                    "items": [
                                        {
                                            "title": "Wrap-up notes",
                                            "description": "Close the lesson with the main takeaways.",
                                            "assetType": "text",
                                            "activityType": "text",
                                            "language": "en",
                                            "bodyMarkdown": "## Wrap-up\n\n- Review the main concept in your own words.\n- Prepare for the next practice task.",
                                            "sortOrder": 1,
                                            "isActive": True,
                                        }
                                    ],
                                },
                            ],
                        }
                    ],
                }
            ],
        )

        cohort = self._create_cohort(course=course, group_code=f"LESSON_{index}_G1", capacity=10)
        student_user = User.objects.create_user(
            email=f"lesson.workspace.student{index}@example.com",
            username=f"lesson_workspace_student_{index}",
            password="StrongPass12345",
        )
        student_profile = OnlineStudentProfile.objects.create(
            user=student_user,
            first_name="Lesson",
            last_name="Workspace",
            preferred_language="en",
        )
        OnlineEnrollment.objects.create(
            profile=student_profile,
            course=course,
            cohort=cohort,
            status=OnlineEnrollment.STATUS_ACTIVE,
        )

        lesson = course.structured_lessons.order_by("sort_order", "id").first()
        client = APIClient()
        client.force_authenticate(user=student_user)
        return client, lesson

    def test_student_lesson_detail_endpoint_returns_dedicated_interactive_payload(self):
        client, lesson = self._create_student_interactive_lesson_fixture(
            index=206,
            slug="student-lesson-detail-endpoint",
        )

        response = client.get(f"/online/student/lessons/{lesson.id}/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["lesson"]["id"], lesson.id)
        self.assertEqual(response.data["module"]["title"], "Week 1 - Python Foundations")
        self.assertEqual(response.data["lesson"]["interactiveLesson"]["lessonTitle"], "Getting Started with Python")
        self.assertEqual(
            [step["kind"] for step in response.data["lesson"]["interactiveLesson"]["steps"]],
            ["theory", "theory", "video", "quiz", "practice", "summary"],
        )
        quiz_step = response.data["lesson"]["interactiveLesson"]["steps"][3]
        practice_step = response.data["lesson"]["interactiveLesson"]["steps"][4]
        self.assertEqual(len(quiz_step["quiz"]["questions"]), 3)
        self.assertEqual(practice_step["practiceMode"], "code_editor")
        self.assertIn("build_profile", practice_step["starterCode"])
        self.assertIn("What is a variable?", response.data["lesson"]["interactiveLesson"]["steps"][1]["contentMarkdown"])
        self.assertEqual(response.data["completion"]["status"], "in_progress")
        self.assertEqual(response.data["lesson"]["progress"]["progressPercent"], 0)

    def test_student_can_persist_lesson_progress_and_unlock_attestation_state(self):
        client, lesson = self._create_student_interactive_lesson_fixture(
            index=207,
            slug="student-lesson-progress-sync",
        )

        lesson_response = client.get(f"/online/student/lessons/{lesson.id}/")
        self.assertEqual(lesson_response.status_code, status.HTTP_200_OK)
        step_ids = [step["id"] for step in lesson_response.data["lesson"]["interactiveLesson"]["steps"]]
        enrollment = OnlineEnrollment.objects.get(course=lesson.course)

        response = client.post(
            f"/online/student/lessons/{lesson.id}/progress/",
            {
                "activeStepId": step_ids[-1],
                "completedStepIds": step_ids,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["progress"]["progressPercent"], 100)
        self.assertEqual(response.data["progress"]["completedStepIds"], step_ids)
        self.assertEqual(response.data["completion"]["status"], "ready_for_attestation")
        self.assertEqual(response.data["completion"]["progressPercent"], 100)
        self.assertTrue(response.data["completion"]["requirements"]["completionMet"])
        self.assertFalse(response.data["completion"]["requirements"]["attestationMet"])

        stored_progress = OnlineLessonProgress.objects.get(enrollment=enrollment, lesson=lesson)
        self.assertEqual(stored_progress.progress_percent, 100)
        self.assertIsNotNone(stored_progress.completed_at)

        refreshed_detail = client.get(f"/online/student/lessons/{lesson.id}/")
        self.assertEqual(refreshed_detail.status_code, status.HTTP_200_OK)
        self.assertEqual(refreshed_detail.data["lesson"]["progress"]["progressPercent"], 100)
        self.assertEqual(refreshed_detail.data["completion"]["status"], "ready_for_attestation")

    def test_student_can_submit_attestation_and_receive_completion_evidence(self):
        client, lesson = self._create_student_interactive_lesson_fixture(
            index=208,
            slug="student-lesson-attestation",
        )

        lesson_response = client.get(f"/online/student/lessons/{lesson.id}/")
        self.assertEqual(lesson_response.status_code, status.HTTP_200_OK)
        step_ids = [step["id"] for step in lesson_response.data["lesson"]["interactiveLesson"]["steps"]]
        enrollment = OnlineEnrollment.objects.get(course=lesson.course)

        progress_response = client.post(
            f"/online/student/lessons/{lesson.id}/progress/",
            {
                "activeStepId": step_ids[-1],
                "completedStepIds": step_ids,
            },
            format="json",
        )
        self.assertEqual(progress_response.status_code, status.HTTP_200_OK)
        self.assertEqual(progress_response.data["completion"]["status"], "ready_for_attestation")

        attestation_response = client.post(
            f"/online/student/enrollments/{enrollment.id}/attestation/",
            {
                "fullName": "Lesson Workspace",
                "agreed": True,
            },
            format="json",
        )

        self.assertEqual(attestation_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(attestation_response.data["completion"]["status"], "completed")
        self.assertIsNotNone(attestation_response.data["attestation"])
        self.assertIsNotNone(attestation_response.data["evidence"])

        attestation = OnlineEnrollmentAttestation.objects.get(enrollment=enrollment)
        evidence = OnlineCompletionEvidence.objects.get(enrollment=enrollment)
        enrollment.refresh_from_db()

        self.assertEqual(attestation.full_name, "Lesson Workspace")
        self.assertEqual(evidence.status, OnlineCompletionEvidence.STATUS_ISSUED)
        self.assertEqual(evidence.completion_percent, 100)
        self.assertEqual(enrollment.status, OnlineEnrollment.STATUS_COMPLETED)
        self.assertIsNotNone(enrollment.completed_at)

    def test_student_lesson_detail_uses_structured_item_data_for_quiz_and_code_practice(self):
        course = self._create_course(
            slug="structured-generated-lesson",
            trial_available=False,
            price_amount=Decimal("0.00"),
        )
        upsert_course_structure(
            course,
            None,
            modules_data=[
                {
                    "title": "Module 1",
                    "description": "Generated module",
                    "moduleType": "module",
                    "weekNumber": 1,
                    "sortOrder": 10,
                    "lessons": [
                        {
                            "title": "Structured lesson",
                            "description": "Generated from admin builder",
                            "sortOrder": 1,
                            "sections": [
                                {
                                    "sectionType": "introduction",
                                    "title": "Introduction",
                                    "description": "",
                                    "sortOrder": 10,
                                    "items": [
                                        {
                                            "title": "Theory",
                                            "description": "Theory step",
                                            "assetType": "text",
                                            "activityType": "text",
                                            "language": "en",
                                            "bodyMarkdown": "## Theory\n\n- Variables store values.\n- Names should be descriptive.",
                                            "sortOrder": 1,
                                        }
                                    ],
                                },
                                {
                                    "sectionType": "main",
                                    "title": "Main content",
                                    "description": "",
                                    "sortOrder": 20,
                                    "items": [
                                        {
                                            "title": "Concept",
                                            "description": "Concept step",
                                            "assetType": "text",
                                            "activityType": "text",
                                            "language": "en",
                                            "bodyMarkdown": "## Concept\n\n- Assign values with `=`.\n- Reassign when the state changes.",
                                            "sortOrder": 1,
                                        },
                                        {
                                            "title": "Video walkthrough",
                                            "description": "Watch the demo",
                                            "assetType": "link",
                                            "activityType": "video",
                                            "language": "en",
                                            "externalUrl": "https://example.com/video.mp4",
                                            "bodyMarkdown": "## Video\n\nWatch a short demo.",
                                            "sortOrder": 2,
                                        },
                                    ],
                                },
                                {
                                    "sectionType": "conclusion",
                                    "title": "Conclusion",
                                    "description": "",
                                    "sortOrder": 30,
                                    "items": [
                                        {
                                            "title": "Knowledge check",
                                            "description": "Quiz step",
                                            "assetType": "text",
                                            "activityType": "quiz",
                                            "language": "en",
                                            "bodyMarkdown": "## Quiz\n\n- Answer the questions below.",
                                            "structuredData": {
                                                "questions": [
                                                    {
                                                        "id": "q1",
                                                        "prompt": "What is a variable used for?",
                                                        "options": [
                                                            {"id": "a", "label": "To store a value", "isCorrect": True},
                                                            {"id": "b", "label": "To delete code", "isCorrect": False},
                                                            {"id": "c", "label": "To skip review", "isCorrect": False},
                                                        ],
                                                        "explanationMarkdown": "### Explanation\n\nVariables store values for later use.",
                                                    },
                                                    {
                                                        "id": "q2",
                                                        "prompt": "How do you assign a value in Python?",
                                                        "options": [
                                                            {"id": "a", "label": "With the `=` operator", "isCorrect": True},
                                                            {"id": "b", "label": "With `==` only", "isCorrect": False},
                                                            {"id": "c", "label": "With `print()`", "isCorrect": False},
                                                        ],
                                                        "explanationMarkdown": "### Explanation\n\nUse `=` to assign a value.",
                                                    },
                                                ]
                                            },
                                            "sortOrder": 1,
                                        },
                                        {
                                            "title": "Practice lab",
                                            "description": "Complete the function",
                                            "assetType": "text",
                                            "activityType": "assignment",
                                            "language": "en",
                                            "bodyMarkdown": "## Practice\n\nReturn the correct lesson summary dictionary.",
                                            "structuredData": {
                                                "practiceMode": "code_editor",
                                                "starterCode": (
                                                    "def build_variable_summary():\n"
                                                    "    return {\n"
                                                    '        \"lesson\": \"\",\n'
                                                    '        \"concepts\": [],\n'
                                                    "    }\n"
                                                ),
                                                "hint": "Use the lesson title and both core concepts.",
                                                "solution": (
                                                    "def build_variable_summary():\n"
                                                    "    return {\n"
                                                    '        \"lesson\": \"Structured lesson\",\n'
                                                    '        \"concepts\": [\"Variables store values.\", \"Assign values with =.\"],\n'
                                                    "    }\n"
                                                ),
                                                "grader": {
                                                    "type": "python_function_check",
                                                    "function_name": "build_variable_summary",
                                                    "cases": [
                                                        {
                                                            "label": "Returns the expected summary",
                                                            "args": [],
                                                            "expected": {
                                                                "lesson": "Structured lesson",
                                                                "concepts": [
                                                                    "Variables store values.",
                                                                    "Assign values with =.",
                                                                ],
                                                            },
                                                        }
                                                    ],
                                                },
                                            },
                                            "sortOrder": 2,
                                        },
                                        {
                                            "title": "Wrap-up",
                                            "description": "Summary step",
                                            "assetType": "text",
                                            "activityType": "text",
                                            "language": "en",
                                            "bodyMarkdown": "## Wrap-up\n\n- Review the key ideas.\n- Continue to the next lesson.",
                                            "sortOrder": 3,
                                        },
                                    ],
                                },
                            ],
                        }
                    ],
                }
            ],
        )

        cohort = self._create_cohort(course=course, group_code="STRUCTURED_DATA_G1")
        student_user = User.objects.create_user(
            email="structured.lesson.student@example.com",
            username="structured_lesson_student",
            password="StrongPass12345",
        )
        student_profile = OnlineStudentProfile.objects.create(
            user=student_user,
            first_name="Structured",
            last_name="Lesson",
            preferred_language="en",
        )
        OnlineEnrollment.objects.create(
            profile=student_profile,
            course=course,
            cohort=cohort,
            status=OnlineEnrollment.STATUS_ACTIVE,
        )
        lesson = course.structured_lessons.order_by("sort_order", "id").first()

        client = APIClient()
        client.force_authenticate(user=student_user)
        lesson_response = client.get(f"/online/student/lessons/{lesson.id}/")

        self.assertEqual(lesson_response.status_code, status.HTTP_200_OK)
        interactive_lesson = lesson_response.data["lesson"]["interactiveLesson"]
        self.assertEqual(
            [step["kind"] for step in interactive_lesson["steps"]],
            ["theory", "theory", "video", "quiz", "practice", "summary"],
        )
        quiz_step = interactive_lesson["steps"][3]
        practice_step = interactive_lesson["steps"][4]
        self.assertEqual(len(quiz_step["quiz"]["questions"]), 2)
        self.assertEqual(practice_step["practiceMode"], "code_editor")
        self.assertIn("build_variable_summary", practice_step["starterCode"])

        grader_response = client.post(
            f"/online/student/lessons/{lesson.id}/grader/check/",
            {
                "stepId": practice_step["id"],
                "code": practice_step["solution"],
            },
            format="json",
        )

        self.assertEqual(grader_response.status_code, status.HTTP_200_OK)
        self.assertEqual(grader_response.data["status"], "success")
        self.assertTrue(all(check["passed"] for check in grader_response.data["checks"]))

    def test_student_lesson_detail_supports_legacy_bitcoin_lesson_alias(self):
        course = self._create_course(
            slug="financial-time-series-forecasting-lab",
            trial_available=False,
            price_amount=Decimal("0.00"),
        )
        course.lessons_count = 1
        course.save(update_fields=["lessons_count", "updated_at"])

        notebook_content = TrainingContentItem.objects.create(
            slug="financial-time-series-forecasting-lab-bitcoin-case",
            name="Financial Time-Series Forecasting Lab",
            description="Notebook for the Bitcoin case lesson.",
            body_markdown="## Bitcoin case\n\n- Mention leakage risk.\n- This is educational, not investment advice.",
            content_kind=TrainingContentItem.ContentKind.NOTEBOOK,
            status=TrainingContentItem.Status.PUBLISHED,
            access_scope=TrainingContentItem.AccessScope.AUTHENTICATED,
            supports_inline_lab=True,
            course=course,
        )

        upsert_course_structure(
            course,
            None,
            modules_data=[
                {
                    "title": "Week 1 - Financial Time-Series",
                    "description": "Notebook-first learning path.",
                    "moduleType": "module",
                    "weekNumber": 1,
                    "sortOrder": 1,
                    "isActive": True,
                    "lessons": [
                        {
                            "title": "Bitcoin Case: Forecasting with JupyterLab",
                            "description": "Guided walkthrough with a notebook lab.",
                            "sortOrder": 1,
                            "isActive": True,
                            "sections": [
                                {
                                    "sectionType": "introduction",
                                    "title": "Theory",
                                    "description": "",
                                    "sortOrder": 10,
                                    "items": [
                                        {
                                            "title": "Context",
                                            "description": "Why time-aware validation matters.",
                                            "assetType": "text",
                                            "activityType": "text",
                                            "language": "en",
                                            "bodyMarkdown": "## Forecasting context\n\n- Use only historical information.\n- Review leakage before modeling.",
                                            "sortOrder": 1,
                                        }
                                    ],
                                },
                                {
                                    "sectionType": "main",
                                    "title": "Practice",
                                    "description": "",
                                    "sortOrder": 20,
                                    "items": [
                                        {
                                            "title": "Notebook practice",
                                            "description": "Open the Bitcoin case notebook.",
                                            "assetType": "notebook",
                                            "activityType": "assignment",
                                            "language": "en",
                                            "bodyMarkdown": "Run the notebook and validate the workflow.",
                                            "linkedTrainingContentId": notebook_content.id,
                                            "sortOrder": 1,
                                        }
                                    ],
                                },
                                {
                                    "sectionType": "conclusion",
                                    "title": "Summary",
                                    "description": "",
                                    "sortOrder": 30,
                                    "items": [
                                        {
                                            "title": "Summary",
                                            "description": "Wrap-up notes.",
                                            "assetType": "text",
                                            "activityType": "text",
                                            "language": "en",
                                            "bodyMarkdown": "## Summary\n\n- Mention limitations.\n- Avoid trading claims.",
                                            "sortOrder": 1,
                                        }
                                    ],
                                },
                            ],
                        }
                    ],
                }
            ],
        )

        cohort = self._create_cohort(course=course, group_code="BTC_ALIAS_G1")
        student_user = User.objects.create_user(
            email="bitcoin.alias.student@example.com",
            username="bitcoin_alias_student",
            password="StrongPass12345",
        )
        student_profile = OnlineStudentProfile.objects.create(
            user=student_user,
            first_name="Bitcoin",
            last_name="Alias",
            preferred_language="en",
        )
        OnlineEnrollment.objects.create(
            profile=student_profile,
            course=course,
            cohort=cohort,
            status=OnlineEnrollment.STATUS_ACTIVE,
        )
        lesson = course.structured_lessons.get(title="Bitcoin Case: Forecasting with JupyterLab")

        client = APIClient()
        client.force_authenticate(user=student_user)

        response = client.get("/online/student/lessons/158/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["lesson"]["id"], lesson.id)
        self.assertEqual(response.data["lesson"]["title"], "Bitcoin Case: Forecasting with JupyterLab")
        self.assertTrue(response.data["lesson"]["interactiveLesson"]["steps"])
        self.assertIn(
            "Bitcoin Case: Forecasting with JupyterLab",
            response.data["lesson"]["interactiveLesson"]["lessonTitle"],
        )

    @override_settings(TRAINING_AI_ENABLED=True, TRAINING_AI_PROVIDER="demo")
    def test_student_lesson_ai_endpoint_uses_lesson_context_and_prompt_type(self):
        client, lesson = self._create_student_interactive_lesson_fixture(
            index=205,
            slug="student-lesson-ai-endpoint",
        )
        provider = Mock()
        provider.provider_name = "test-provider"
        provider.model_name = "test-model"
        provider.generate_answer.return_value = Mock(
            short_answer="Short lesson answer.",
            detailed_answer="Detailed lesson answer.",
            follow_up_prompts=["Explain the quiz again."],
            resolution_status="resolved",
        )

        with patch("apps.online.views.get_training_ai_provider", return_value=provider):
            response = client.post(
                f"/online/student/lessons/{lesson.id}/ai/ask/",
                {
                    "stepId": f"lesson-{lesson.id}-quiz",
                    "promptType": "simple_summary",
                    "question": "Explain the quiz step in simple words.",
                },
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["answer"], "Detailed lesson answer.")
        self.assertEqual(response.data["followUpPrompts"], ["Explain the quiz again."])
        self.assertEqual(response.data["provider"], "test-provider")
        self.assertEqual(response.data["model"], "test-model")
        provider.generate_answer.assert_called_once()
        self.assertEqual(provider.generate_answer.call_args.kwargs["prompt_type"], "simple_summary")
        self.assertTrue(provider.generate_answer.call_args.kwargs["context_chunks"])

    def test_student_lesson_grader_endpoint_checks_code_editor_step(self):
        client, lesson = self._create_student_interactive_lesson_fixture(
            index=204,
            slug="student-lesson-grader-endpoint",
        )

        lesson_response = client.get(f"/online/student/lessons/{lesson.id}/")
        self.assertEqual(lesson_response.status_code, status.HTTP_200_OK)
        practice_step = next(
            step
            for step in lesson_response.data["lesson"]["interactiveLesson"]["steps"]
            if step["eyebrow"] == "Practice"
        )

        response = client.post(
            f"/online/student/lessons/{lesson.id}/grader/check/",
            {
                "stepId": practice_step["id"],
                "code": practice_step["solution"],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "success")
        self.assertTrue(all(check["passed"] for check in response.data["checks"]))

    def test_admin_builder_session_seed_rejects_overflow_beyond_course_lessons(self):
        admin_user = self._create_admin_user(index=207)
        course = self._create_course(
            slug="course-builder-session-overflow",
            trial_available=False,
            price_amount=Decimal("75.00"),
        )
        course.lessons_count = 1
        course.save(update_fields=["lessons_count", "updated_at"])
        cohort = self._create_cohort(course=course, group_code="BUILDER_OVERFLOW_G1", capacity=8)

        client = APIClient()
        client.force_authenticate(user=admin_user)
        response = client.post(
            f"/online/admin/course-builder/courses/{course.id}/sessions/",
            {
                "cohortId": cohort.id,
                "sessions": [
                    {
                        "title": "Session 1",
                        "description": "",
                        "startsAt": (timezone.now() + timedelta(days=2)).isoformat(),
                        "endsAt": (timezone.now() + timedelta(days=2, hours=2)).isoformat(),
                    },
                    {
                        "title": "Session 2",
                        "description": "",
                        "startsAt": (timezone.now() + timedelta(days=9)).isoformat(),
                        "endsAt": (timezone.now() + timedelta(days=9, hours=2)).isoformat(),
                    },
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("at most 1 more session", response.data["detail"])

    def test_admin_can_manage_scope_assignments(self):
        admin_user = self._create_admin_user(index=208)
        target_user = User.objects.create_user(
            email="scope.assignee@example.com",
            username="scope_assignee",
            password="StrongPass12345",
            first_name="Scope",
            last_name="Owner",
        )
        course = self._create_course(
            slug="scope-managed-course",
            trial_available=False,
            price_amount=Decimal("95.00"),
        )
        cohort = self._create_cohort(course=course, group_code="SCOPE_G1", capacity=12)

        client = APIClient()
        client.force_authenticate(user=admin_user)

        create_response = client.post(
            "/online/admin/scope-assignments/",
            {
                "userId": target_user.id,
                "role": "delivery_manager",
                "scopeType": "cohort",
                "courseId": course.id,
                "cohortId": cohort.id,
                "note": "Primary delivery escalation owner.",
                "isPrimary": True,
            },
            format="json",
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        assignment_id = create_response.data["id"]
        assignment = OnlineScopeAssignment.objects.get(id=assignment_id)
        self.assertEqual(assignment.scope_key, f"cohort:{cohort.id}")
        self.assertTrue(assignment.is_primary)

        patch_response = client.patch(
            f"/online/admin/scope-assignments/{assignment_id}/",
            {"isActive": False},
            format="json",
        )
        self.assertEqual(patch_response.status_code, status.HTTP_200_OK)
        self.assertFalse(patch_response.data["isActive"])

        list_response = client.get(f"/online/admin/scope-assignments/?user_id={target_user.id}")
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_response.data["results"]), 1)
        self.assertEqual(list_response.data["results"][0]["scopeLabel"], f"{course.title_en} / {cohort.group_code}")

        delete_response = client.delete(f"/online/admin/scope-assignments/{assignment_id}/")
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(OnlineScopeAssignment.objects.filter(id=assignment_id).exists())
        self.assertGreaterEqual(OnlineAuditEvent.objects.filter(event_type__startswith="scope_assignment.").count(), 2)

    def test_admin_enterprise_summary_returns_identity_scope_and_learning_signals(self):
        admin_user = self._create_admin_user(index=209)
        target_user = User.objects.create_user(
            email="enterprise.learner@example.com",
            username="enterprise_learner",
            password="StrongPass12345",
        )
        profile = OnlineStudentProfile.objects.create(
            user=target_user,
            first_name="Enterprise",
            last_name="Learner",
            preferred_language="en",
        )
        course = self._create_course(
            slug="enterprise-summary-course",
            trial_available=False,
            price_amount=Decimal("125.00"),
        )
        cohort = self._create_cohort(course=course, group_code="ENTERPRISE_G1", capacity=10)
        cohort.end_date = timezone.localdate() - timedelta(days=1)
        cohort.save(update_fields=["end_date", "updated_at"])
        enrollment = OnlineEnrollment.objects.create(
            profile=profile,
            course=course,
            cohort=cohort,
            status=OnlineEnrollment.STATUS_ACTIVE,
        )
        enrollment.started_at = timezone.now() - timedelta(days=10)
        enrollment.save(update_fields=["started_at"])
        OnlineScopeAssignment.objects.create(
            user=admin_user,
            role=OnlineScopeAssignment.ROLE_COMPLIANCE_MANAGER,
            scope_type=OnlineScopeAssignment.SCOPE_COURSE,
            scope_key=f"course:{course.id}",
            course=course,
            note="Compliance owner",
            is_primary=True,
            created_by=admin_user,
        )

        client = APIClient()
        client.force_authenticate(user=admin_user)
        response = client.get(f"/online/admin/enterprise-summary/?course_id={course.id}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["courseId"], course.id)
        self.assertGreaterEqual(response.data["identity"]["totalProviders"], 1)
        self.assertEqual(response.data["scopedAccess"]["complianceManagerAssignments"], 1)
        self.assertEqual(response.data["learning"]["activeEnrollments"], 1)
        self.assertEqual(response.data["compliance"]["publishBlockedCourses"], 1)
        self.assertEqual(response.data["atRiskLearners"][0]["enrollmentId"], enrollment.id)
        self.assertIn("Cohort ended before completion", response.data["atRiskLearners"][0]["riskReasons"])

    def test_default_identity_provider_seed_is_available(self):
        local_provider = OnlineIdentityProvider.objects.filter(slug="local-password").first()
        microsoft_provider = OnlineIdentityProvider.objects.filter(slug="microsoft-entra").first()

        self.assertIsNotNone(local_provider)
        self.assertIsNotNone(microsoft_provider)
        self.assertEqual(local_provider.provider_type, OnlineIdentityProvider.PROVIDER_LOCAL_PASSWORD)
        self.assertTrue(local_provider.is_enabled)

    @override_settings(
        ONLINE_MICROSOFT_CLIENT_ID="client-id",
        ONLINE_MICROSOFT_CLIENT_SECRET="client-secret",
        ONLINE_MICROSOFT_TENANT_ID="tenant-id",
        ONLINE_MICROSOFT_SCOPES=["openid", "profile", "email"],
    )
    def test_microsoft_sso_start_uses_unified_registered_callback_uri(self):
        response = self.client.get(
            "/online/staff/auth/microsoft/start/?role=teacher&next=/teacher/home&login=/teacher/login"
        )

        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertIn("https://login.microsoftonline.com/tenant-id/oauth2/v2.0/authorize", response["Location"])
        self.assertIn("redirect_uri=http%3A%2F%2Ftestserver%2Fapi%2Fauth%2Fmicrosoft%2Fcallback%2F", response["Location"])
        self.assertIn("scope=openid+profile+email", response["Location"])

    @override_settings(
        ONLINE_MICROSOFT_CLIENT_ID="client-id",
        ONLINE_MICROSOFT_CLIENT_SECRET="client-secret",
        ONLINE_MICROSOFT_TENANT_ID="tenant-id",
    )
    @patch("apps.online.views.algorithms", SimpleNamespace())
    @patch("apps.online.views._microsoft_oidc_jwks")
    @patch("apps.online.views.jwt.get_unverified_header")
    def test_microsoft_token_verification_handles_missing_crypto_backend(self, header_mock, jwks_mock):
        header_mock.return_value = {"kid": "microsoft-key-id"}
        jwks_mock.return_value = {"keys": [{"kid": "microsoft-key-id"}]}

        payload, error = online_views._verify_microsoft_id_token("header.payload.signature", nonce="nonce-value")

        self.assertIsNone(payload)
        self.assertEqual(error, "Microsoft token is invalid.")

    @override_settings(
        ONLINE_MICROSOFT_AUTO_PROVISION_STUDENTS=True,
        ONLINE_MICROSOFT_STUDENT_EMAILS=[],
        ONLINE_MICROSOFT_DEFAULT_STUDENT_LANGUAGE="en",
    )
    def test_microsoft_student_lookup_auto_provisions_student_profile(self):
        payload = {
            "tid": "tenant-id",
            "oid": "student-object-id",
            "sub": "student-subject",
            "email": "Student.Test@kunstschuleberlin.de",
            "name": "Student Test",
        }

        user, error = online_views._microsoft_user_lookup(role=online_views.SSO_ROLE_STUDENT, payload=payload)

        self.assertIsNone(error)
        self.assertIsNotNone(user)
        self.assertEqual(user.email, "student.test@kunstschuleberlin.de")
        self.assertFalse(user.has_usable_password())
        profile = OnlineStudentProfile.objects.get(user=user)
        self.assertEqual(profile.first_name, "Student")
        self.assertEqual(profile.last_name, "Test")
        self.assertEqual(profile.preferred_language, "en")

    @override_settings(ONLINE_MICROSOFT_TEACHER_EMAILS=["teacher.test@kunstschuleberlin.de"])
    def test_microsoft_teacher_lookup_requires_allowlist_and_creates_curator_profile(self):
        payload = {
            "tid": "tenant-id",
            "oid": "teacher-object-id",
            "sub": "teacher-subject",
            "email": "teacher.test@kunstschuleberlin.de",
            "name": "Teacher Test",
        }

        user, error = online_views._microsoft_user_lookup(role=online_views.SSO_ROLE_TEACHER, payload=payload)

        self.assertIsNone(error)
        self.assertIsNotNone(user)
        teacher = Lehrer.objects.get(user=user)
        self.assertEqual(teacher.Schule_Email, "teacher.test@kunstschuleberlin.de")
        self.assertTrue(OnlineInstructorProfile.objects.filter(teacher=teacher).exists())

    @override_settings(
        ONLINE_MICROSOFT_CLIENT_ID="client-id",
        ONLINE_MICROSOFT_CLIENT_SECRET="client-secret",
        ONLINE_MICROSOFT_TENANT_ID="tenant-id",
        ONLINE_MICROSOFT_SCOPES=["openid", "profile", "email"],
        ONLINE_MICROSOFT_TEACHER_EMAILS=["teacher.callback@kunstschuleberlin.de"],
    )
    @patch("apps.online.views._verify_microsoft_id_token")
    @patch("apps.online.views.requests.post")
    def test_microsoft_unified_callback_provisions_teacher_and_sets_staff_cookie(self, post_mock, verify_mock):
        state = online_views._build_sso_state(
            scope=online_views.AUTH_SCOPE_STAFF,
            role=online_views.SSO_ROLE_TEACHER,
            next_path="/teacher/home",
            login_path="/teacher/login",
            nonce="nonce-value",
        )
        token_response = Mock()
        token_response.raise_for_status.return_value = None
        token_response.json.return_value = {"id_token": "microsoft-id-token"}
        post_mock.return_value = token_response
        verify_mock.return_value = (
            {
                "tid": "tenant-id",
                "oid": "teacher-callback-object-id",
                "sub": "teacher-callback-subject",
                "email": "teacher.callback@kunstschuleberlin.de",
                "name": "Teacher Callback",
            },
            None,
        )

        response = self.client.get("/api/auth/microsoft/callback/", {"state": state, "code": "auth-code"})

        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertEqual(response["Location"], "/teacher/home")
        self.assertIn(settings.ONLINE_STAFF_ACCESS_COOKIE_NAME, response.cookies)
        token_request = post_mock.call_args.kwargs["data"]
        self.assertEqual(token_request["redirect_uri"], "http://testserver/api/auth/microsoft/callback/")
        teacher = Lehrer.objects.get(Schule_Email="teacher.callback@kunstschuleberlin.de")
        self.assertTrue(OnlineIdentityLink.objects.filter(user=teacher.user, subject="tenant-id:teacher-callback-object-id").exists())

    @override_settings(ONLINE_MICROSOFT_ADMIN_EMAILS=[])
    def test_microsoft_admin_lookup_rejects_unassigned_admin_account(self):
        payload = {
            "tid": "tenant-id",
            "oid": "admin-object-id",
            "sub": "admin-subject",
            "email": "admin.test@kunstschuleberlin.de",
            "name": "Admin Test",
        }

        user, error = online_views._microsoft_user_lookup(role=online_views.SSO_ROLE_ADMIN, payload=payload)

        self.assertIsNone(user)
        self.assertEqual(error, "Admin access must be assigned inside Learning Hub.")

    @override_settings(ONLINE_MICROSOFT_ADMIN_EMAILS=["admin.test@kunstschuleberlin.de"])
    def test_microsoft_admin_lookup_creates_admin_from_allowlist(self):
        payload = {
            "tid": "tenant-id",
            "oid": "admin-object-id",
            "sub": "admin-subject",
            "email": "admin.test@kunstschuleberlin.de",
            "name": "Admin Test",
        }

        user, error = online_views._microsoft_user_lookup(role=online_views.SSO_ROLE_ADMIN, payload=payload)

        self.assertIsNone(error)
        self.assertIsNotNone(user)
        self.assertTrue(user.is_admin)
        self.assertTrue(user.is_staff)

    def test_admin_catalog_search_and_attribute_registry_cover_new_catalog_entities(self):
        admin_user = self._create_admin_user(index=210)
        course = self._create_course(
            slug="python-risk-catalog",
            trial_available=False,
            price_amount=Decimal("59.00"),
            title_en="Python Risk Foundations",
            short_description_en="Python foundations for analysts.",
            description_en="Course for analyst onboarding and internal Python readiness.",
        )
        course.provider_type = OnlineCourse.PROVIDER_COURSERA
        course.course_origin = OnlineCourse.ORIGIN_EXTERNAL_SYNCED
        course.course_type = OnlineCourse.COURSE_TYPE_VIDEO
        course.delivery_model = OnlineCourse.DELIVERY_SELF_PACED
        course.difficulty_level = OnlineCourse.DIFFICULTY_BEGINNER
        course.confidentiality_level = OnlineCourse.CONFIDENTIALITY_RESTRICTED
        course.knowledge_domain = "Python"
        course.target_audience = "Analysts"
        course.average_rating = Decimal("4.80")
        course.ratings_count = 18
        course.tags = ["python", "risk"]
        course.skills = ["variables", "output"]
        course.save()

        student_user = User.objects.create_user(
            email="catalog.student@example.com",
            username="catalog_student",
            password="StrongPass12345",
        )
        student_profile = OnlineStudentProfile.objects.create(
            user=student_user,
            first_name="Catalog",
            last_name="Student",
            department="Risk",
            job_title="Analyst",
            preferred_language="en",
        )

        _teacher_user, teacher = self._create_teacher(index=210)
        OnlineInstructorProfile.objects.create(
            teacher=teacher,
            department="Risk",
            job_title="Python Instructor",
            bio="Risk and Python instruction.",
            expertise_areas=["python", "risk"],
            can_publish=True,
        )

        program = OnlineLearningProgram.objects.create(
            slug="risk-onboarding",
            title="Risk onboarding",
            assignment_mode=OnlineLearningProgram.ASSIGNMENT_HYBRID,
            target_audience="Analysts",
            created_by=admin_user,
        )
        OnlineLearningProgramCourse.objects.create(
            program=program,
            course=course,
            sort_order=1,
            is_required=True,
        )
        source = OnlineKnowledgeSource.objects.create(
            slug="risk-python-kb",
            title="Risk Python KB",
            source_type=OnlineKnowledgeSource.SOURCE_UPLOAD,
            linked_course=course,
            owner=admin_user,
        )
        OnlineKnowledgeDocument.objects.create(
            source=source,
            title="Python risk reference",
            document_type=OnlineKnowledgeDocument.DOC_MARKDOWN,
            language="en",
            body_markdown="Risk knowledge base note.",
            is_active=True,
        )

        client = APIClient()
        client.force_authenticate(user=admin_user)

        definition_response = client.post(
            "/online/admin/catalog/attributes/",
            {
                "slug": "compliance-tier",
                "entityType": "course",
                "label": "Compliance tier",
                "dataType": "single_select",
                "options": ["standard", "restricted"],
                "isFilterable": True,
                "isSearchable": True,
            },
            format="json",
        )
        self.assertEqual(definition_response.status_code, status.HTTP_201_CREATED)
        definition_id = definition_response.data["id"]

        value_response = client.post(
            "/online/admin/catalog/attribute-values/",
            {
                "definitionId": definition_id,
                "entityType": "course",
                "objectId": course.id,
                "valueJson": {"value": "restricted"},
            },
            format="json",
        )
        self.assertEqual(value_response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            OnlineCatalogAttributeValue.objects.filter(definition_id=definition_id, object_id=course.id).exists()
        )

        search_response = client.get(
            "/online/admin/catalog/search/",
            {
                "q": "risk",
                "providerType": "coursera",
                "knowledgeDomain": "Python",
            },
        )
        self.assertEqual(search_response.status_code, status.HTTP_200_OK)
        self.assertEqual(search_response.data["courses"][0]["id"], course.id)
        self.assertEqual(search_response.data["students"][0]["id"], student_profile.id)
        self.assertEqual(search_response.data["instructors"][0]["department"], "Risk")
        self.assertEqual(search_response.data["programs"][0]["id"], program.id)
        self.assertEqual(search_response.data["knowledgeDocuments"][0]["sourceTitle"], "Risk Python KB")

    def test_admin_student_and_instructor_profile_endpoints_support_updates(self):
        admin_user = self._create_admin_user(index=211)
        student_user = User.objects.create_user(
            email="student.registry@example.com",
            username="student_registry",
            password="StrongPass12345",
        )
        student_profile = OnlineStudentProfile.objects.create(
            user=student_user,
            first_name="Student",
            last_name="Registry",
            preferred_language="en",
        )
        _teacher_user, teacher = self._create_teacher(index=211)

        client = APIClient()
        client.force_authenticate(user=admin_user)

        student_patch = client.patch(
            f"/online/admin/student-profiles/{student_profile.id}/",
            {
                "employeeId": "EMP-211",
                "department": "Finance",
                "teamName": "Market Risk",
                "jobTitle": "Junior Analyst",
                "managerName": "Alice Manager",
                "employmentStatus": "active",
            },
            format="json",
        )
        self.assertEqual(student_patch.status_code, status.HTTP_200_OK)
        student_profile.refresh_from_db()
        self.assertEqual(student_profile.department, "Finance")
        self.assertEqual(student_profile.team_name, "Market Risk")

        instructor_create = client.post(
            "/online/admin/instructor-profiles/",
            {
                "teacherId": teacher.id,
                "department": "Academy",
                "jobTitle": "Lead Instructor",
                "bio": "Teaches Python and delivery practices.",
                "expertiseAreas": ["python", "delivery"],
                "spokenLanguages": ["English"],
                "canAuthor": True,
                "canReview": True,
                "canPublish": False,
                "canGenerateWithAi": True,
                "canManageAssessments": True,
            },
            format="json",
        )
        self.assertEqual(instructor_create.status_code, status.HTTP_201_CREATED)
        profile_id = instructor_create.data["id"]

        instructor_patch = client.patch(
            f"/online/admin/instructor-profiles/{profile_id}/",
            {
                "canPublish": True,
                "spokenLanguages": ["English", "German"],
            },
            format="json",
        )
        self.assertEqual(instructor_patch.status_code, status.HTTP_200_OK)
        instructor_profile = OnlineInstructorProfile.objects.get(id=profile_id)
        self.assertTrue(instructor_profile.can_publish)
        self.assertEqual(instructor_profile.spoken_languages, ["English", "German"])

    def test_admin_can_create_learning_program_and_assign_it_to_student(self):
        admin_user = self._create_admin_user(index=212)
        course = self._create_course(
            slug="program-python-core",
            trial_available=False,
            price_amount=Decimal("89.00"),
            title_en="Program Python Core",
        )
        student_user = User.objects.create_user(
            email="program.student@example.com",
            username="program_student",
            password="StrongPass12345",
        )
        student_profile = OnlineStudentProfile.objects.create(
            user=student_user,
            first_name="Program",
            last_name="Student",
            preferred_language="en",
        )

        client = APIClient()
        client.force_authenticate(user=admin_user)

        program_response = client.post(
            "/online/admin/programs/",
            {
                "slug": "python-core-track",
                "title": "Python core track",
                "description": "Standard program for Python onboarding.",
                "targetAudience": "Students",
                "assignmentMode": "hybrid",
                "recommendationPrompt": "Recommend when a learner needs Python foundations.",
                "isActive": True,
                "programCourses": [
                    {
                        "courseId": course.id,
                        "sortOrder": 1,
                        "isRequired": True,
                        "unlockRule": "immediate",
                        "minCompletionPercent": 100,
                    }
                ],
            },
            format="json",
        )
        self.assertEqual(program_response.status_code, status.HTTP_201_CREATED)
        program_id = program_response.data["id"]
        self.assertEqual(program_response.data["programCourses"][0]["courseId"], course.id)

        assignment_response = client.post(
            "/online/admin/program-assignments/",
            {
                "profileId": student_profile.id,
                "programId": program_id,
                "source": "ai_recommendation",
                "aiReason": "Matched role and skill gap.",
            },
            format="json",
        )
        self.assertEqual(assignment_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(assignment_response.data["profileId"], student_profile.id)

        list_response = client.get(f"/online/admin/program-assignments/?profile_id={student_profile.id}")
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_response.data["results"]), 1)
        self.assertEqual(list_response.data["results"][0]["programId"], program_id)
        self.assertTrue(
            OnlineStudentProgramAssignment.objects.filter(profile=student_profile, program_id=program_id).exists()
        )

    def test_admin_can_manage_external_providers_and_knowledge_documents(self):
        admin_user = self._create_admin_user(index=213)
        course = self._create_course(
            slug="knowledge-python-core",
            trial_available=False,
            price_amount=Decimal("49.00"),
            title_en="Knowledge Python Core",
        )

        client = APIClient()
        client.force_authenticate(user=admin_user)

        provider_response = client.post(
            "/online/admin/external-providers/",
            {
                "slug": "linkedin-learning-main",
                "displayName": "LinkedIn Learning Main",
                "providerType": "linkedin_learning",
                "importMode": "api",
                "baseUrl": "https://www.linkedin.com/learning",
                "apiBaseUrl": "https://api.linkedin.com/learning",
                "isEnabled": True,
                "syncStatus": "ready",
                "verificationMessage": "Connector validated.",
            },
            format="json",
        )
        self.assertEqual(provider_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(provider_response.data["providerType"], "linkedin_learning")
        self.assertTrue(OnlineExternalCatalogProvider.objects.filter(slug="linkedin-learning-main").exists())

        source_response = client.post(
            "/online/admin/knowledge-sources/",
            {
                "slug": "python-kb-source",
                "title": "Python KB Source",
                "description": "Uploaded notes and transcripts.",
                "sourceType": "upload",
                "linkedCourseId": course.id,
                "isActive": True,
                "isIndexed": False,
            },
            format="json",
        )
        self.assertEqual(source_response.status_code, status.HTTP_201_CREATED)
        source_id = source_response.data["id"]

        document_response = client.post(
            "/online/admin/knowledge-documents/",
            {
                "sourceId": source_id,
                "title": "Python reference transcript",
                "description": "Transcript excerpt for AI retrieval.",
                "documentType": "transcript",
                "language": "en",
                "transcriptText": "Variables store values. Functions group reusable code.",
                "isActive": True,
            },
            format="json",
        )
        self.assertEqual(document_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(document_response.data["sourceId"], source_id)

        list_response = client.get(f"/online/admin/knowledge-documents/?source_id={source_id}")
        self.assertEqual(list_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_response.data["results"]), 1)
        self.assertEqual(list_response.data["results"][0]["title"], "Python reference transcript")
