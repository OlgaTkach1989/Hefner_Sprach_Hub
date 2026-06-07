from __future__ import annotations

import hashlib
import json
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import parse_qs, urlparse
from unittest.mock import Mock, patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.management import call_command
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

from apps.employees.models import Lehrer
from apps.online.models import (
    OnlineCohort,
    OnlineCourse,
    OnlineCourseContentLibraryItem,
    OnlineCourseLesson,
    OnlineCourseLessonSection,
    OnlineCourseLessonSectionItem,
    OnlineCourseModule,
    OnlineEnrollment,
    OnlineLessonProgress,
    OnlineStudentProfile,
)
from apps.training.models import (
    TrainingAiConversation,
    TrainingAiMessage,
    TrainingAiQuizAttempt,
    TrainingAssetClass,
    TrainingAuditEvent,
    TrainingAudience,
    TrainingContentAudiencePolicy,
    TrainingContentCrossReference,
    TrainingContentItem,
    TrainingContentSyncEvent,
    TrainingCourseRoleAssignment,
    TrainingGradebookEntry,
    TrainingGraderJob,
    TrainingJupyterLoginToken,
    TrainingKnowledgeChunk,
    TrainingLabLaunchToken,
    TrainingLabSubmission,
    TrainingLabSubmissionArtifact,
    TrainingNotebookLabHint,
    TrainingNotebookLabProfile,
    TrainingTopic,
    TrainingUserAudienceGrant,
)
from apps.training.demo_bitcoin_course_spec import COURSE_SLUG, NOTEBOOK_CONTENT_SLUG, NOTEBOOK_GRADER_CONFIG
from apps.training.services.access import (
    active_audience_slugs_for_user,
    content_item_is_visible_to_user,
    primary_demo_role_for_user,
)
from apps.training.services.ai_provider import OpenAiCompatibleTrainingAiProvider
from apps.training.services.grading import process_pending_grader_jobs
from apps.training.services.jupyter_ai_proxy import build_internal_jupyter_ai_proxy_token
from apps.training.services.notebook_actions import build_internal_notebook_action_token
from apps.training.services.jupyter_auth import build_training_jupyter_username
from apps.training.services.knowledge_base import ensure_training_content_indexed
from apps.training.services.notebook_storage import runtime_content_root
from apps.training.views import TrainingAdminAiAnalyticsThrottle, TrainingDirectusSyncThrottle

User = get_user_model()


def build_notebook_upload(
    *,
    name: str = "submission.ipynb",
    source: str = "print('hello')",
    outputs: list[dict] | None = None,
) -> tuple[SimpleUploadedFile, str]:
    payload = {
        "cells": [
            {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": outputs or [],
                "source": [source],
            }
        ],
        "metadata": {},
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    content = json.dumps(payload).encode("utf-8")
    checksum = hashlib.sha256(content).hexdigest()
    return (
        SimpleUploadedFile(name=name, content=content, content_type="application/x-ipynb+json"),
        checksum,
    )


class TrainingAccessServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="student@example.com",
            username="student_user",
            password="StrongPass12345",
        )
        self.external_user = User.objects.create_user(
            email="external@example.com",
            username="external_user",
            password="StrongPass12345",
        )
        self.course = OnlineCourse.objects.create(
            slug="quant-cva",
            title_de="Quant CVA",
            title_en="Quant CVA",
            short_description_de="Kurz",
            short_description_en="Short",
            description_de="Beschreibung",
            description_en="Description",
            lessons_count=8,
            trial_available=False,
            price_amount=Decimal("999.00"),
            currency="EUR",
        )
        self.cohort = OnlineCohort.objects.create(
            course=self.course,
            name="CVA Cohort",
            group_code="CVA-1",
            capacity=20,
            timezone="Europe/Berlin",
            status=OnlineCohort.STATUS_OPEN,
            is_public=False,
        )
        for user in (self.user, self.external_user):
            profile = OnlineStudentProfile.objects.create(
                user=user,
                first_name="Test",
                last_name="User",
                preferred_language="en",
            )
            OnlineEnrollment.objects.create(
                profile=profile,
                course=self.course,
                cohort=self.cohort,
                status=OnlineEnrollment.STATUS_ACTIVE,
            )

        self.institutional = TrainingAudience.objects.create(
            slug="institutional-skills",
            name="Institutional Skills",
            is_internal=True,
        )
        self.trader = TrainingAudience.objects.create(
            slug="trader",
            name="Trader",
            is_internal=True,
        )
        TrainingUserAudienceGrant.objects.create(user=self.user, audience=self.institutional)
        TrainingUserAudienceGrant.objects.create(user=self.user, audience=self.trader)
        TrainingUserAudienceGrant.objects.create(
            user=self.external_user,
            audience=self.trader,
            expires_at=timezone.now() - timedelta(days=1),
        )

    def test_entitled_content_requires_matching_audience_grant(self):
        content = TrainingContentItem.objects.create(
            slug="institutional-ops-cva",
            name="Institutional CVA Ops",
            content_kind=TrainingContentItem.ContentKind.ARTICLE,
            status=TrainingContentItem.Status.PUBLISHED,
            access_scope=TrainingContentItem.AccessScope.ENTITLED,
            course=self.course,
        )
        TrainingContentAudiencePolicy.objects.create(content_item=content, audience=self.institutional)

        self.assertTrue(content_item_is_visible_to_user(content, self.user))
        self.assertFalse(content_item_is_visible_to_user(content, self.external_user))

    def test_all_match_mode_requires_all_audiences(self):
        content = TrainingContentItem.objects.create(
            slug="quant-stack-overview",
            name="Quant Stack Overview",
            content_kind=TrainingContentItem.ContentKind.ARTICLE,
            status=TrainingContentItem.Status.PUBLISHED,
            access_scope=TrainingContentItem.AccessScope.ENTITLED,
            audience_match_mode=TrainingContentItem.AudienceMatchMode.ALL,
            course=self.course,
        )
        TrainingContentAudiencePolicy.objects.create(content_item=content, audience=self.institutional)
        TrainingContentAudiencePolicy.objects.create(content_item=content, audience=self.trader)

        self.assertTrue(content_item_is_visible_to_user(content, self.user))
        self.assertFalse(content_item_is_visible_to_user(content, self.external_user))

    def test_course_bound_entitled_content_without_audience_policy_is_visible_to_enrolled_student(self):
        content = TrainingContentItem.objects.create(
            slug="cva-core-notes",
            name="CVA Core Notes",
            content_kind=TrainingContentItem.ContentKind.ARTICLE,
            status=TrainingContentItem.Status.PUBLISHED,
            access_scope=TrainingContentItem.AccessScope.ENTITLED,
            course=self.course,
        )

        self.assertTrue(content_item_is_visible_to_user(content, self.user))
        self.assertTrue(content_item_is_visible_to_user(content, self.external_user))


class TrainingDemoRoleHierarchyTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="demo.role@example.com",
            username="demo_role_user",
            password="StrongPass12345",
        )
        self.external_users, _ = TrainingAudience.objects.update_or_create(
            slug="external-users",
            defaults={
                "name": "Guest access",
                "short_label": "Guest",
                "audience_type": TrainingAudience.AudienceType.DEMO_ROLE,
                "privilege_rank": 10,
                "is_internal": False,
            },
        )
        self.interns, _ = TrainingAudience.objects.update_or_create(
            slug="interns-new-grads",
            defaults={
                "name": "Student access",
                "short_label": "Student",
                "audience_type": TrainingAudience.AudienceType.DEMO_ROLE,
                "privilege_rank": 20,
                "is_internal": True,
            },
        )
        self.lateral, _ = TrainingAudience.objects.update_or_create(
            slug="lateral-transfers",
            defaults={
                "name": "Instructor access",
                "short_label": "Instructor",
                "audience_type": TrainingAudience.AudienceType.DEMO_ROLE,
                "privilege_rank": 30,
                "is_internal": True,
            },
        )
        self.traders, _ = TrainingAudience.objects.update_or_create(
            slug="traders-structurizers",
            defaults={
                "name": "Admin access",
                "short_label": "Admin",
                "audience_type": TrainingAudience.AudienceType.DEMO_ROLE,
                "privilege_rank": 40,
                "is_internal": True,
            },
        )

    def test_highest_demo_role_expands_visible_role_catalog(self):
        TrainingUserAudienceGrant.objects.create(user=self.user, audience=self.traders)

        self.assertEqual(primary_demo_role_for_user(self.user), self.traders)
        self.assertEqual(
            active_audience_slugs_for_user(self.user),
            {
                "external-users",
                "interns-new-grads",
                "lateral-transfers",
                "traders-structurizers",
            },
        )


class TrainingApiTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="student.api@example.com",
            username="student_api_user",
            password="StrongPass12345",
        )
        self.external_user = User.objects.create_user(
            email="external.api@example.com",
            username="external_api_user",
            password="StrongPass12345",
        )
        self.owner = User.objects.create_user(
            email="owner.api@example.com",
            username="owner_api_user",
            password="StrongPass12345",
        )
        self.course = OnlineCourse.objects.create(
            slug="markets-qa",
            title_de="Markets QA",
            title_en="Markets QA",
            short_description_de="Kurz",
            short_description_en="Short",
            description_de="Beschreibung",
            description_en="Description",
            lessons_count=10,
            trial_available=False,
            price_amount=Decimal("1499.00"),
            currency="EUR",
        )
        self.cohort = OnlineCohort.objects.create(
            course=self.course,
            name="Markets QA Cohort",
            group_code="MQA-1",
            capacity=20,
            timezone="Europe/Berlin",
            status=OnlineCohort.STATUS_OPEN,
            is_public=False,
        )
        self.asset_class = TrainingAssetClass.objects.create(slug="credit", name="Credit")
        self.topic = TrainingTopic.objects.create(slug="cva", name="CVA")
        self.institutional = TrainingAudience.objects.create(
            slug="institutional-skills",
            name="Institutional Skills",
            is_internal=True,
        )
        self.external_audience = TrainingAudience.objects.create(
            slug="external-client",
            name="External Client",
            is_internal=False,
        )
        for user in (self.user, self.external_user):
            profile = OnlineStudentProfile.objects.create(
                user=user,
                first_name="API",
                last_name="User",
                preferred_language="en",
            )
            OnlineEnrollment.objects.create(
                profile=profile,
                course=self.course,
                cohort=self.cohort,
                status=OnlineEnrollment.STATUS_ACTIVE,
            )

        TrainingUserAudienceGrant.objects.create(user=self.user, audience=self.institutional)
        TrainingUserAudienceGrant.objects.create(user=self.external_user, audience=self.external_audience)
        TrainingCourseRoleAssignment.objects.create(
            user=self.owner,
            course=self.course,
            role=TrainingCourseRoleAssignment.Role.OWNER,
            is_primary=True,
            response_sla_hours=8,
        )

        self.public_content = TrainingContentItem.objects.create(
            slug="public-cva-overview",
            name="Public CVA Overview",
            description="Open to everyone",
            content_kind=TrainingContentItem.ContentKind.ARTICLE,
            status=TrainingContentItem.Status.PUBLISHED,
            access_scope=TrainingContentItem.AccessScope.PUBLIC,
            course=self.course,
        )
        self.public_content.asset_classes.add(self.asset_class)
        self.public_content.topics.add(self.topic)

        self.internal_lab = TrainingContentItem.objects.create(
            slug="institutional-cva-lab",
            name="Institutional CVA Lab",
            description="Internal notebook",
            body_markdown="Lab instructions",
            content_kind=TrainingContentItem.ContentKind.NOTEBOOK,
            status=TrainingContentItem.Status.PUBLISHED,
            access_scope=TrainingContentItem.AccessScope.ENTITLED,
            course=self.course,
            supports_inline_lab=True,
        )
        self.internal_lab.asset_classes.add(self.asset_class)
        self.internal_lab.topics.add(self.topic)
        TrainingContentAudiencePolicy.objects.create(content_item=self.internal_lab, audience=self.institutional)
        TrainingNotebookLabProfile.objects.create(
            content_item=self.internal_lab,
            runtime_backend=TrainingNotebookLabProfile.RuntimeBackend.JUPYTERHUB,
            grader_backend=TrainingNotebookLabProfile.GraderBackend.NBGRADER,
            runtime_image="quant/cva:1.0",
            notebook_path="labs/cva/intro.ipynb",
            launch_path="/user-redirect/lab/tree/labs/cva/intro.ipynb",
        )
        TrainingContentCrossReference.objects.create(
            from_item=self.internal_lab,
            to_item=self.public_content,
            relation_type=TrainingContentCrossReference.RelationType.PREREQUISITE,
        )

    def test_anonymous_content_list_returns_only_public_items(self):
        response = self.client.get("/api/training/content/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["slug"], "public-cva-overview")
        audit_event = TrainingAuditEvent.objects.get(event_type=TrainingAuditEvent.EventType.CONTENT_LIST_VIEWED)
        self.assertEqual(audit_event.category, TrainingAuditEvent.Category.CONTENT)
        self.assertEqual(audit_event.outcome, TrainingAuditEvent.Outcome.SUCCEEDED)
        self.assertEqual(audit_event.metadata["resultCount"], 1)

    def test_entitled_student_sees_internal_lab(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/training/content/?course=markets-qa&asset_class=credit&topic=cva")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        returned_slugs = {item["slug"] for item in response.data["results"]}
        self.assertEqual(returned_slugs, {"public-cva-overview", "institutional-cva-lab"})

    def test_external_student_cannot_load_internal_content_detail(self):
        self.client.force_authenticate(user=self.external_user)

        response = self.client.get("/api/training/content/institutional-cva-lab/")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        audit_event = TrainingAuditEvent.objects.get(event_type=TrainingAuditEvent.EventType.CONTENT_ACCESS_DENIED)
        self.assertEqual(audit_event.outcome, TrainingAuditEvent.Outcome.DENIED)
        self.assertEqual(audit_event.actor, self.external_user)
        self.assertEqual(audit_event.content_item, self.internal_lab)

    def test_detail_endpoint_includes_lab_contract_and_cross_references(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/training/content/institutional-cva-lab/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["lab"]["runtime_backend"], "jupyterhub")
        self.assertEqual(response.data["lab"]["grader_backend"], "nbgrader")
        self.assertEqual(response.data["cross_references"][0]["slug"], "public-cva-overview")

    def test_me_entitlements_returns_audiences_and_course_roles(self):
        demo_role = TrainingAudience.objects.create(
            slug="interns-new-grads-demo",
            name="Student access",
            short_label="Student",
            audience_type=TrainingAudience.AudienceType.DEMO_ROLE,
            privilege_rank=20,
            is_internal=True,
        )
        TrainingUserAudienceGrant.objects.create(user=self.owner, audience=demo_role)
        self.client.force_authenticate(user=self.owner)

        response = self.client.get("/api/training/me/entitlements/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["courseRoles"][0]["role"], TrainingCourseRoleAssignment.Role.OWNER)
        self.assertEqual(response.data["courseRoles"][0]["response_sla_hours"], 8)
        self.assertEqual(response.data["activeDemoRole"]["slug"], demo_role.slug)
        self.assertIn(demo_role.slug, response.data["assignedAudienceSlugs"])
        self.assertGreaterEqual(len(response.data["demoRoleCatalog"]), 1)


class TrainingAdminApiTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin_user = User.objects.create_user(
            email="admin.training@example.com",
            username="admin_training",
            password="StrongPass12345",
            is_admin=True,
            is_staff=True,
        )
        self.student_user = User.objects.create_user(
            email="student.training@example.com",
            username="student_training",
            password="StrongPass12345",
        )
        self.course = OnlineCourse.objects.create(
            slug="training-admin-course",
            title_de="Training Admin",
            title_en="Training Admin",
            short_description_de="Kurz",
            short_description_en="Short",
            description_de="Beschreibung",
            description_en="Description",
            lessons_count=6,
            trial_available=False,
            price_amount=Decimal("499.00"),
            currency="EUR",
        )
        self.audience = TrainingAudience.objects.create(
            slug="intern",
            name="Intern",
            is_internal=True,
        )

    def _create_curator_user(self, *, index: int) -> tuple[User, Lehrer]:
        user = User.objects.create_user(
            email=f"curator.training{index}@example.com",
            username=f"curator_training_{index}",
            password="StrongPass12345",
        )
        curator = Lehrer.objects.create(
            user=user,
            Nachname=f"Curator{index}",
            Vorname=f"Training{index}",
            Schule_Email=f"curator{index}@school.example.com",
            Private_Email=f"curator{index}@private.example.com",
            KurzName=f"CUR{index}",
        )
        return user, curator

    def test_student_cannot_access_training_admin_audiences(self):
        self.client.force_authenticate(user=self.student_user)

        response = self.client.get("/api/training/admin/audiences/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_create_audience(self):
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.post(
            "/api/training/admin/audiences/",
            {
                "slug": "external-client",
                "name": "External Client",
                "description": "External audience",
                "is_internal": False,
                "is_active": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(TrainingAudience.objects.filter(slug="external-client").exists())

    def test_admin_duplicate_audience_grant_is_rejected(self):
        self.client.force_authenticate(user=self.admin_user)
        TrainingUserAudienceGrant.objects.create(user=self.student_user, audience=self.audience)

        response = self.client.post(
            "/api/training/admin/user-audience-grants/",
            {
                "user_id": self.student_user.id,
                "audience_id": self.audience.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["detail"], "This user already has the selected audience grant.")

    def test_admin_can_create_primary_course_owner_assignment(self):
        self.client.force_authenticate(user=self.admin_user)
        curator_user, _curator = self._create_curator_user(index=1)

        response = self.client.post(
            "/api/training/admin/course-role-assignments/",
            {
                "user_id": curator_user.id,
                "course_id": self.course.id,
                "role": TrainingCourseRoleAssignment.Role.OWNER,
                "is_primary": True,
                "response_sla_hours": 12,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        assignment = TrainingCourseRoleAssignment.objects.get()
        self.assertTrue(assignment.is_primary)
        self.assertEqual(assignment.response_sla_hours, 12)
        self.assertEqual(assignment.user, curator_user)

    def test_admin_can_create_instructor_assignment_for_curator(self):
        self.client.force_authenticate(user=self.admin_user)
        curator_user, _curator = self._create_curator_user(index=2)

        response = self.client.post(
            "/api/training/admin/course-role-assignments/",
            {
                "user_id": curator_user.id,
                "course_id": self.course.id,
                "role": TrainingCourseRoleAssignment.Role.INSTRUCTOR,
                "is_primary": False,
                "response_sla_hours": 24,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        assignment = TrainingCourseRoleAssignment.objects.get()
        self.assertEqual(assignment.role, TrainingCourseRoleAssignment.Role.INSTRUCTOR)
        self.assertEqual(assignment.user, curator_user)

    def test_admin_rejects_instructor_assignment_for_non_curator_user(self):
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.post(
            "/api/training/admin/course-role-assignments/",
            {
                "user_id": self.student_user.id,
                "course_id": self.course.id,
                "role": TrainingCourseRoleAssignment.Role.INSTRUCTOR,
                "is_primary": False,
                "response_sla_hours": 24,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Instructor assignments require curator access.", str(response.data))

    def test_admin_rejects_owner_assignment_for_inactive_user(self):
        self.client.force_authenticate(user=self.admin_user)
        inactive_curator_user, _curator = self._create_curator_user(index=3)
        inactive_curator_user.is_active = False
        inactive_curator_user.save(update_fields=["is_active"])

        response = self.client.post(
            "/api/training/admin/course-role-assignments/",
            {
                "user_id": inactive_curator_user.id,
                "course_id": self.course.id,
                "role": TrainingCourseRoleAssignment.Role.OWNER,
                "is_primary": True,
                "response_sla_hours": 12,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Inactive users cannot receive course role assignments.", str(response.data))

    def test_admin_can_filter_course_role_assignments_by_user_and_role(self):
        reviewer_user = User.objects.create_user(
            email="reviewer.training@example.com",
            username="reviewer_training",
            password="StrongPass12345",
        )
        TrainingCourseRoleAssignment.objects.create(
            user=self.student_user,
            course=self.course,
            role=TrainingCourseRoleAssignment.Role.OWNER,
            is_primary=True,
            response_sla_hours=8,
        )
        TrainingCourseRoleAssignment.objects.create(
            user=reviewer_user,
            course=self.course,
            role=TrainingCourseRoleAssignment.Role.REVIEWER,
            is_primary=False,
            response_sla_hours=24,
        )
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.get(
            f"/api/training/admin/course-role-assignments/?user_id={self.student_user.id}&role={TrainingCourseRoleAssignment.Role.OWNER}"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["user"]["email"], self.student_user.email)
        self.assertEqual(response.data["results"][0]["role"], TrainingCourseRoleAssignment.Role.OWNER)

    def test_new_primary_owner_assignment_demotes_existing_primary_owner(self):
        current_owner, _current_curator = self._create_curator_user(index=4)
        next_owner, _next_curator = self._create_curator_user(index=5)
        existing_assignment = TrainingCourseRoleAssignment.objects.create(
            user=current_owner,
            course=self.course,
            role=TrainingCourseRoleAssignment.Role.OWNER,
            is_primary=True,
            response_sla_hours=6,
        )
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.post(
            "/api/training/admin/course-role-assignments/",
            {
                "user_id": next_owner.id,
                "course_id": self.course.id,
                "role": TrainingCourseRoleAssignment.Role.OWNER,
                "is_primary": True,
                "response_sla_hours": 4,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        existing_assignment.refresh_from_db()
        new_assignment = TrainingCourseRoleAssignment.objects.get(user=next_owner, course=self.course)
        self.assertFalse(existing_assignment.is_primary)
        self.assertTrue(new_assignment.is_primary)

    def test_admin_reports_overview_returns_operational_counts(self):
        notebook = TrainingContentItem.objects.create(
            slug="reports-notebook",
            name="Reports Notebook",
            content_kind=TrainingContentItem.ContentKind.NOTEBOOK,
            status=TrainingContentItem.Status.PUBLISHED,
            access_scope=TrainingContentItem.AccessScope.ENTITLED,
            course=self.course,
        )
        TrainingAuditEvent.objects.create(
            category=TrainingAuditEvent.Category.ADMIN,
            event_type=TrainingAuditEvent.EventType.ADMIN_COURSE_ROLE_CREATED,
            outcome=TrainingAuditEvent.Outcome.FAILED,
            actor=self.admin_user,
            actor_email=self.admin_user.email,
            course=self.course,
            content_item=notebook,
            request_path="/api/training/admin/course-role-assignments/",
        )
        TrainingAuditEvent.objects.create(
            category=TrainingAuditEvent.Category.CONTENT,
            event_type=TrainingAuditEvent.EventType.CONTENT_ACCESS_DENIED,
            outcome=TrainingAuditEvent.Outcome.DENIED,
            actor=self.student_user,
            actor_email=self.student_user.email,
            course=self.course,
            content_item=notebook,
            request_path="/api/training/content/reports-notebook/",
        )
        TrainingContentSyncEvent.objects.create(
            content_item=notebook,
            source=TrainingContentSyncEvent.Source.DIRECTUS,
            event_type=TrainingContentSyncEvent.EventType.UPSERT,
            status=TrainingContentSyncEvent.Status.FAILED,
            external_source_id="reports-sync-1",
            content_slug=notebook.slug,
            detail="Sync failed for overview.",
        )
        submission = TrainingLabSubmission.objects.create(
            user=self.student_user,
            content_item=notebook,
            grader_backend=TrainingNotebookLabProfile.GraderBackend.NBGRADER,
            status=TrainingLabSubmission.Status.FAILED,
            attempt_number=1,
            submitted_at=timezone.now(),
        )
        TrainingGraderJob.objects.create(
            submission=submission,
            backend=TrainingNotebookLabProfile.GraderBackend.NBGRADER,
            status=TrainingGraderJob.Status.FAILED,
            priority=100,
            attempts_count=1,
            available_at=timezone.now() - timedelta(minutes=10),
            finished_at=timezone.now(),
            worker_name="grader-worker-1",
            error_message="Execution failed",
        )
        TrainingAiConversation.objects.create(
            user=self.student_user,
            content_item=notebook,
            title="Open escalation",
            governance_status=TrainingAiConversation.GovernanceStatus.OPEN,
            status=TrainingAiConversation.Status.ACTIVE,
            last_activity_at=timezone.now(),
        )
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.get(f"/api/training/admin/reports/overview/?course_id={self.course.id}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["failedAuditEvents"], 1)
        self.assertEqual(response.data["deniedAuditEvents"], 1)
        self.assertEqual(response.data["failedSyncEvents"], 1)
        self.assertEqual(response.data["failedGraderJobs"], 1)
        self.assertEqual(response.data["unresolvedAiConversations"], 1)

    def test_admin_reports_lists_filter_recent_exceptions(self):
        notebook = TrainingContentItem.objects.create(
            slug="reports-notebook-list",
            name="Reports Notebook List",
            content_kind=TrainingContentItem.ContentKind.NOTEBOOK,
            status=TrainingContentItem.Status.PUBLISHED,
            access_scope=TrainingContentItem.AccessScope.ENTITLED,
            course=self.course,
        )
        failing_audit = TrainingAuditEvent.objects.create(
            category=TrainingAuditEvent.Category.GRADING,
            event_type=TrainingAuditEvent.EventType.GRADING_JOB_FAILED,
            outcome=TrainingAuditEvent.Outcome.FAILED,
            actor=self.admin_user,
            actor_email=self.admin_user.email,
            course=self.course,
            content_item=notebook,
            request_path="/api/training/internal/grading/report/",
        )
        denied_audit = TrainingAuditEvent.objects.create(
            category=TrainingAuditEvent.Category.CONTENT,
            event_type=TrainingAuditEvent.EventType.CONTENT_ACCESS_DENIED,
            outcome=TrainingAuditEvent.Outcome.DENIED,
            actor=self.student_user,
            actor_email=self.student_user.email,
            course=self.course,
            content_item=notebook,
            request_path="/api/training/content/reports-notebook-list/",
        )
        sync_event = TrainingContentSyncEvent.objects.create(
            content_item=notebook,
            source=TrainingContentSyncEvent.Source.DIRECTUS,
            event_type=TrainingContentSyncEvent.EventType.UPSERT,
            status=TrainingContentSyncEvent.Status.FAILED,
            external_source_id="reports-sync-2",
            content_slug=notebook.slug,
            detail="Sync failed for listing.",
        )
        submission = TrainingLabSubmission.objects.create(
            user=self.student_user,
            content_item=notebook,
            grader_backend=TrainingNotebookLabProfile.GraderBackend.NBGRADER,
            status=TrainingLabSubmission.Status.FAILED,
            attempt_number=2,
            submitted_at=timezone.now(),
        )
        grader_job = TrainingGraderJob.objects.create(
            submission=submission,
            backend=TrainingNotebookLabProfile.GraderBackend.NBGRADER,
            status=TrainingGraderJob.Status.FAILED,
            priority=90,
            attempts_count=2,
            available_at=timezone.now() - timedelta(minutes=20),
            finished_at=timezone.now(),
            worker_name="grader-worker-2",
            error_message="Feedback export failed",
        )
        self.client.force_authenticate(user=self.admin_user)

        audit_response = self.client.get(
            f"/api/training/admin/reports/audit-events/?course_id={self.course.id}&outcome=failed&limit=10"
        )
        denied_response = self.client.get(
            f"/api/training/admin/reports/audit-events/?course_id={self.course.id}&outcome=denied&limit=10"
        )
        sync_response = self.client.get(
            f"/api/training/admin/reports/sync-events/?course_id={self.course.id}&status=failed&limit=10"
        )
        grader_response = self.client.get(
            f"/api/training/admin/reports/grader-jobs/?course_id={self.course.id}&status=failed&limit=10"
        )

        self.assertEqual(audit_response.status_code, status.HTTP_200_OK)
        self.assertEqual(denied_response.status_code, status.HTTP_200_OK)
        self.assertEqual(sync_response.status_code, status.HTTP_200_OK)
        self.assertEqual(grader_response.status_code, status.HTTP_200_OK)
        self.assertEqual(audit_response.data["results"][0]["eventId"], str(failing_audit.event_id))
        self.assertEqual(denied_response.data["results"][0]["eventId"], str(denied_audit.event_id))
        self.assertEqual(sync_response.data["results"][0]["id"], sync_event.id)
        self.assertEqual(grader_response.data["results"][0]["id"], grader_job.id)

    def test_admin_overview_returns_governance_gaps(self):
        self.client.force_authenticate(user=self.admin_user)
        TrainingContentItem.objects.create(
            slug="governance-gap-item",
            name="Governance Gap Item",
            content_kind=TrainingContentItem.ContentKind.ARTICLE,
            status=TrainingContentItem.Status.PUBLISHED,
            access_scope=TrainingContentItem.AccessScope.ENTITLED,
            course=self.course,
        )

        response = self.client.get(f"/api/training/admin/overview/?course_id={self.course.id}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["contentWithoutOwner"], 1)
        self.assertEqual(response.data["internalContentWithoutAudiencePolicy"], 1)

    def test_admin_can_lookup_users(self):
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.get("/api/training/admin/users/?q=student.training")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["email"], self.student_user.email)
        self.assertEqual(response.data["results"][0]["fullName"], self.student_user.email)

    def test_admin_grant_records_granted_by_actor(self):
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.post(
            "/api/training/admin/user-audience-grants/",
            {
                "user_id": self.student_user.id,
                "audience_id": self.audience.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        grant = TrainingUserAudienceGrant.objects.get(user=self.student_user, audience=self.audience)
        self.assertEqual(grant.granted_by, self.admin_user)
        self.assertEqual(response.data["grantedBy"]["email"], self.admin_user.email)
        audit_event = TrainingAuditEvent.objects.get(event_type=TrainingAuditEvent.EventType.ADMIN_AUDIENCE_GRANT_CREATED)
        self.assertEqual(audit_event.actor, self.admin_user)
        self.assertEqual(audit_event.target_user, self.student_user)
        self.assertEqual(audit_event.metadata["audienceSlug"], self.audience.slug)


class TrainingLabLaunchApiTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="lab.user@example.com",
            username="lab_user",
            password="StrongPass12345",
        )
        self.external_user = User.objects.create_user(
            email="lab.external@example.com",
            username="lab_external",
            password="StrongPass12345",
        )
        self.course = OnlineCourse.objects.create(
            slug="lab-course",
            title_de="Lab Course",
            title_en="Lab Course",
            short_description_de="Kurz",
            short_description_en="Short",
            description_de="Beschreibung",
            description_en="Description",
            lessons_count=5,
            trial_available=False,
            price_amount=Decimal("799.00"),
            currency="EUR",
        )
        self.cohort = OnlineCohort.objects.create(
            course=self.course,
            name="Lab Cohort",
            group_code="LAB-1",
            capacity=15,
            timezone="Europe/Berlin",
            status=OnlineCohort.STATUS_OPEN,
            is_public=False,
        )
        for user in (self.user, self.external_user):
            profile = OnlineStudentProfile.objects.create(
                user=user,
                first_name="Lab",
                last_name="User",
                preferred_language="en",
            )
            OnlineEnrollment.objects.create(
                profile=profile,
                course=self.course,
                cohort=self.cohort,
                status=OnlineEnrollment.STATUS_ACTIVE,
            )

        self.internal_audience = TrainingAudience.objects.create(
            slug="institutional-skills",
            name="Institutional Skills",
            is_internal=True,
        )
        TrainingUserAudienceGrant.objects.create(user=self.user, audience=self.internal_audience)
        self.notebook_content = TrainingContentItem.objects.create(
            slug="cva-notebook",
            name="CVA Notebook",
            content_kind=TrainingContentItem.ContentKind.NOTEBOOK,
            status=TrainingContentItem.Status.PUBLISHED,
            access_scope=TrainingContentItem.AccessScope.ENTITLED,
            course=self.course,
            supports_inline_lab=True,
        )
        TrainingContentAudiencePolicy.objects.create(content_item=self.notebook_content, audience=self.internal_audience)
        TrainingNotebookLabProfile.objects.create(
            content_item=self.notebook_content,
            runtime_backend=TrainingNotebookLabProfile.RuntimeBackend.JUPYTERHUB,
            grader_backend=TrainingNotebookLabProfile.GraderBackend.NBGRADER,
            runtime_image="quant/cva:1.0",
            notebook_path="labs/cva.ipynb",
            launch_path="/lab/tree/labs/cva.ipynb",
        )
        self.article_content = TrainingContentItem.objects.create(
            slug="cva-article",
            name="CVA Article",
            content_kind=TrainingContentItem.ContentKind.ARTICLE,
            status=TrainingContentItem.Status.PUBLISHED,
            access_scope=TrainingContentItem.AccessScope.PUBLIC,
        )

    @override_settings(
        TRAINING_NOTEBOOK_RUNTIME_ENABLED=True,
        TRAINING_JUPYTERHUB_BASE_URL="https://labs.example.com",
        TRAINING_JUPYTERHUB_SERVICE_TOKEN="internal-jupyterhub-token",
        TRAINING_JUPYTERHUB_SHARED_SECRET="shared-secret",
        TRAINING_LAB_LAUNCH_TTL_SECONDS=300,
    )
    def test_entitled_user_can_launch_and_internal_service_can_resolve(self):
        self.client.force_authenticate(user=self.user)

        launch_response = self.client.post("/api/training/labs/cva-notebook/launch/", format="json")

        self.assertEqual(launch_response.status_code, status.HTTP_201_CREATED)
        self.assertIn("training_launch_token=", launch_response.data["launchUrl"])
        signed_token = launch_response.data["launchToken"]
        token_id = launch_response.data["tokenId"]
        self.assertTrue(TrainingLabLaunchToken.objects.filter(token_id=token_id, status=TrainingLabLaunchToken.Status.ISSUED).exists())

        resolve_response = self.client.post(
            "/api/training/internal/labs/resolve-launch/",
            {"launchToken": signed_token},
            format="json",
            HTTP_AUTHORIZATION="Bearer internal-jupyterhub-token",
        )

        self.assertEqual(resolve_response.status_code, status.HTTP_200_OK)
        self.assertEqual(resolve_response.data["lab"]["runtimeBackend"], "jupyterhub")
        self.assertEqual(resolve_response.data["content"]["slug"], "cva-notebook")
        token_row = TrainingLabLaunchToken.objects.get(token_id=token_id)
        self.assertEqual(token_row.status, TrainingLabLaunchToken.Status.CONSUMED)
        self.assertIsNotNone(token_row.consumed_at)
        audit_event = TrainingAuditEvent.objects.get(event_type=TrainingAuditEvent.EventType.LAB_LAUNCH_ISSUED)
        self.assertEqual(audit_event.actor, self.user)
        self.assertEqual(audit_event.launch_token, token_row)

    @override_settings(
        TRAINING_NOTEBOOK_RUNTIME_ENABLED=True,
        TRAINING_JUPYTERHUB_SERVICE_TOKEN="internal-jupyterhub-token",
        TRAINING_JUPYTERHUB_SHARED_SECRET="shared-secret",
    )
    def test_user_without_matching_audience_cannot_launch_lab(self):
        self.client.force_authenticate(user=self.external_user)

        response = self.client.post("/api/training/labs/cva-notebook/launch/", format="json")

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @override_settings(TRAINING_NOTEBOOK_RUNTIME_ENABLED=False)
    def test_runtime_disabled_returns_service_unavailable(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post("/api/training/labs/cva-notebook/launch/", format="json")

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)

    @override_settings(TRAINING_NOTEBOOK_RUNTIME_ENABLED=True, TRAINING_JUPYTERHUB_EGRESS_ENABLED=False)
    def test_launch_rejects_network_enabled_lab_when_egress_is_disabled(self):
        self.client.force_authenticate(user=self.user)
        lab_profile = self.notebook_content.lab_profile
        lab_profile.allow_network = True
        lab_profile.save(update_fields=["allow_network", "updated_at"])

        response = self.client.post("/api/training/labs/cva-notebook/launch/", format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["detail"],
            "Network-enabled notebook runtime is not available in this deployment.",
        )

    @override_settings(
        TRAINING_NOTEBOOK_RUNTIME_ENABLED=True,
        TRAINING_JUPYTERHUB_BASE_URL="https://labs.example.com",
        TRAINING_JUPYTERHUB_EGRESS_ENABLED=True,
        TRAINING_MAX_LAB_SESSION_MINUTES_CAP=180,
    )
    def test_launch_contract_returns_effective_runtime_policy(self):
        self.client.force_authenticate(user=self.user)
        lab_profile = self.notebook_content.lab_profile
        lab_profile.allow_network = True
        lab_profile.max_session_minutes = 600
        lab_profile.save(update_fields=["allow_network", "max_session_minutes", "updated_at"])

        response = self.client.post("/api/training/labs/cva-notebook/launch/", format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["runtime"]["allowNetwork"])
        self.assertFalse(response.data["runtime"]["allowGpu"])
        self.assertEqual(response.data["runtime"]["maxSessionMinutes"], 180)
        self.assertIn("sessionExpiresAt", response.data["runtime"])

    @override_settings(TRAINING_NOTEBOOK_RUNTIME_ENABLED=True)
    def test_non_notebook_content_cannot_launch(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post("/api/training/labs/cva-article/launch/", format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @override_settings(
        TRAINING_NOTEBOOK_RUNTIME_ENABLED=True,
        TRAINING_JUPYTERHUB_SERVICE_TOKEN="internal-jupyterhub-token",
        TRAINING_JUPYTERHUB_SHARED_SECRET="shared-secret",
    )
    def test_resolve_rejects_tampered_token_and_wrong_service_token(self):
        self.client.force_authenticate(user=self.user)
        launch_response = self.client.post("/api/training/labs/cva-notebook/launch/", format="json")
        signed_token = launch_response.data["launchToken"] + "tamper"

        wrong_service_response = self.client.post(
            "/api/training/internal/labs/resolve-launch/",
            {"launchToken": signed_token},
            format="json",
            HTTP_AUTHORIZATION="Bearer wrong-token",
        )
        self.assertEqual(wrong_service_response.status_code, status.HTTP_403_FORBIDDEN)

        invalid_token_response = self.client.post(
            "/api/training/internal/labs/resolve-launch/",
            {"launchToken": signed_token},
            format="json",
            HTTP_AUTHORIZATION="Bearer internal-jupyterhub-token",
        )
        self.assertEqual(invalid_token_response.status_code, status.HTTP_400_BAD_REQUEST)

    @override_settings(
        TRAINING_NOTEBOOK_RUNTIME_ENABLED=True,
        TRAINING_JUPYTERHUB_SERVICE_TOKEN="internal-jupyterhub-token",
        TRAINING_JUPYTERHUB_SHARED_SECRET="shared-secret",
    )
    def test_resolve_rejects_expired_token_record(self):
        self.client.force_authenticate(user=self.user)
        launch_response = self.client.post("/api/training/labs/cva-notebook/launch/", format="json")
        token_id = launch_response.data["tokenId"]
        signed_token = launch_response.data["launchToken"]
        token_row = TrainingLabLaunchToken.objects.get(token_id=token_id)
        token_row.expires_at = timezone.now() - timedelta(minutes=1)
        token_row.save(update_fields=["expires_at", "updated_at"])

        resolve_response = self.client.post(
            "/api/training/internal/labs/resolve-launch/",
            {"launchToken": signed_token},
            format="json",
            HTTP_AUTHORIZATION="Bearer internal-jupyterhub-token",
        )

        self.assertEqual(resolve_response.status_code, status.HTTP_400_BAD_REQUEST)
        token_row.refresh_from_db()
        self.assertEqual(token_row.status, TrainingLabLaunchToken.Status.EXPIRED)


class TrainingJupyterGatewayTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="jupyter.user@example.com",
            username="jupyter_user",
            password="StrongPass12345",
        )
        self.course = OnlineCourse.objects.create(
            slug="jupyter-course",
            title_de="Jupyter Course",
            title_en="Jupyter Course",
            short_description_de="Kurz",
            short_description_en="Short",
            description_de="Beschreibung",
            description_en="Description",
            lessons_count=4,
            trial_available=False,
            price_amount=Decimal("899.00"),
            currency="EUR",
        )
        self.cohort = OnlineCohort.objects.create(
            course=self.course,
            name="Jupyter Cohort",
            group_code="JUP-1",
            capacity=12,
            timezone="Europe/Berlin",
            status=OnlineCohort.STATUS_OPEN,
            is_public=False,
        )
        profile = OnlineStudentProfile.objects.create(
            user=self.user,
            first_name="Jupyter",
            last_name="Student",
            preferred_language="en",
        )
        OnlineEnrollment.objects.create(
            profile=profile,
            course=self.course,
            cohort=self.cohort,
            status=OnlineEnrollment.STATUS_ACTIVE,
        )
        self.audience = TrainingAudience.objects.create(
            slug="quant-internal",
            name="Quant Internal",
            is_internal=True,
        )
        TrainingUserAudienceGrant.objects.create(user=self.user, audience=self.audience)
        self.notebook_content = TrainingContentItem.objects.create(
            slug="cva-jupyter-lab",
            name="CVA Jupyter Lab",
            content_kind=TrainingContentItem.ContentKind.NOTEBOOK,
            status=TrainingContentItem.Status.PUBLISHED,
            access_scope=TrainingContentItem.AccessScope.ENTITLED,
            course=self.course,
            supports_inline_lab=True,
        )
        TrainingContentAudiencePolicy.objects.create(content_item=self.notebook_content, audience=self.audience)
        TrainingNotebookLabProfile.objects.create(
            content_item=self.notebook_content,
            runtime_backend=TrainingNotebookLabProfile.RuntimeBackend.JUPYTERHUB,
            grader_backend=TrainingNotebookLabProfile.GraderBackend.NBGRADER,
            runtime_image="quant/cva:1.0",
            notebook_path="labs/cva/intro.ipynb",
            launch_path="/lab/tree/labs/cva/intro.ipynb",
        )

    @override_settings(
        TRAINING_NOTEBOOK_RUNTIME_ENABLED=True,
        TRAINING_JUPYTERHUB_BASE_URL="https://labs.example.com/lab",
        TRAINING_JUPYTERHUB_SERVICE_TOKEN="internal-jupyterhub-token",
        TRAINING_JUPYTERHUB_SHARED_SECRET="shared-secret",
        TRAINING_JUPYTER_LOGIN_TTL_SECONDS=180,
        TRAINING_JUPYTERHUB_FORCE_LOGOUT_BEFORE_LOGIN=True,
        TRAINING_JUPYTERHUB_EGRESS_ENABLED=True,
        TRAINING_MAX_LAB_SESSION_MINUTES_CAP=90,
    )
    def test_launch_gateway_redirects_to_hub_login_and_exchange_resolves_auth_state(self):
        self.client.force_authenticate(user=self.user)
        lab_profile = self.notebook_content.lab_profile
        lab_profile.allow_network = True
        lab_profile.max_session_minutes = 150
        lab_profile.save(update_fields=["allow_network", "max_session_minutes", "updated_at"])

        launch_response = self.client.post("/api/training/labs/cva-jupyter-lab/launch/", format="json")

        self.assertEqual(launch_response.status_code, status.HTTP_201_CREATED)
        launch_url = launch_response.data["launchUrl"]
        self.assertIn("/lab/launch/", launch_url)

        parsed_launch_url = urlparse(launch_url)
        gateway_response = self.client.get(f"{parsed_launch_url.path}?{parsed_launch_url.query}")

        self.assertEqual(gateway_response.status_code, status.HTTP_302_FOUND)
        redirect_url = gateway_response["Location"]
        self.assertIn("/lab/hub/logout", redirect_url)

        parsed_redirect = urlparse(redirect_url)
        login_path = parse_qs(parsed_redirect.query)["next"][0]
        parsed_login_path = urlparse(login_path)
        login_token = parse_qs(parsed_login_path.query)["login_token"][0]

        self.assertEqual(TrainingJupyterLoginToken.objects.filter(status=TrainingJupyterLoginToken.Status.ISSUED).count(), 1)

        exchange_response = self.client.post(
            "/api/training/internal/labs/exchange-jupyter-login/",
            {"login_token": login_token},
            format="json",
            HTTP_AUTHORIZATION="Bearer internal-jupyterhub-token",
        )

        self.assertEqual(exchange_response.status_code, status.HTTP_200_OK)
        self.assertTrue(exchange_response.data["name"].startswith("student-"))
        self.assertEqual(exchange_response.data["authState"]["trainingContent"]["slug"], "cva-jupyter-lab")
        self.assertTrue(exchange_response.data["authState"]["trainingContent"]["allowNetwork"])
        self.assertEqual(exchange_response.data["authState"]["trainingContent"]["maxSessionMinutes"], 90)
        self.assertTrue(exchange_response.data["authState"]["trainingContent"]["sessionExpiresAt"])
        login_token_row = TrainingJupyterLoginToken.objects.get()
        self.assertEqual(login_token_row.status, TrainingJupyterLoginToken.Status.CONSUMED)
        launch_token_row = TrainingLabLaunchToken.objects.get(token_id=launch_response.data["tokenId"])
        self.assertEqual(launch_token_row.status, TrainingLabLaunchToken.Status.CONSUMED)
        exchange_audit = TrainingAuditEvent.objects.get(event_type=TrainingAuditEvent.EventType.JUPYTER_LOGIN_EXCHANGED)
        self.assertEqual(exchange_audit.actor, self.user)
        self.assertEqual(exchange_audit.jupyter_login_token, login_token_row)

    @override_settings(
        TRAINING_NOTEBOOK_RUNTIME_ENABLED=True,
        TRAINING_JUPYTERHUB_BASE_URL="https://labs.example.com/lab",
        TRAINING_JUPYTERHUB_SERVICE_TOKEN="internal-jupyterhub-token",
        TRAINING_JUPYTERHUB_SHARED_SECRET="shared-secret",
        TRAINING_JUPYTER_LOGIN_TTL_SECONDS=180,
        TRAINING_JUPYTERHUB_FORCE_LOGOUT_BEFORE_LOGIN=False,
        TRAINING_JUPYTERHUB_EGRESS_ENABLED=True,
        TRAINING_MAX_LAB_SESSION_MINUTES_CAP=90,
    )
    def test_launch_gateway_redirects_directly_to_hub_login_when_logout_handoff_disabled(self):
        self.client.force_authenticate(user=self.user)

        launch_response = self.client.post("/api/training/labs/cva-jupyter-lab/launch/", format="json")

        self.assertEqual(launch_response.status_code, status.HTTP_201_CREATED)
        parsed_launch_url = urlparse(launch_response.data["launchUrl"])
        gateway_response = self.client.get(f"{parsed_launch_url.path}?{parsed_launch_url.query}")

        self.assertEqual(gateway_response.status_code, status.HTTP_302_FOUND)
        redirect_url = gateway_response["Location"]
        self.assertIn("/lab/hub/login", redirect_url)
        self.assertNotIn("/lab/hub/logout", redirect_url)

        parsed_redirect = urlparse(redirect_url)
        login_query = parse_qs(parsed_redirect.query)
        self.assertIn("login_token", login_query)
        self.assertIn("next", login_query)

    @override_settings(
        TRAINING_NOTEBOOK_RUNTIME_ENABLED=True,
        TRAINING_JUPYTERHUB_BASE_URL="https://labs.example.com/lab",
        TRAINING_JUPYTERHUB_SERVICE_TOKEN="internal-jupyterhub-token",
        TRAINING_JUPYTERHUB_SHARED_SECRET="shared-secret",
        TRAINING_JUPYTER_LOGIN_TTL_SECONDS=180,
    )
    def test_launch_exchange_marks_repeatable_passed_notebook_for_workspace_reset(self):
        self.client.force_authenticate(user=self.user)
        TrainingGradebookEntry.objects.create(
            user=self.user,
            content_item=self.notebook_content,
            attempts_count=5,
            passed=True,
        )

        launch_response = self.client.post("/api/training/labs/cva-jupyter-lab/launch/", format="json")
        self.assertEqual(launch_response.status_code, status.HTTP_201_CREATED)

        parsed_launch_url = urlparse(launch_response.data["launchUrl"])
        gateway_response = self.client.get(f"{parsed_launch_url.path}?{parsed_launch_url.query}")
        self.assertEqual(gateway_response.status_code, status.HTTP_302_FOUND)

        redirect_url = gateway_response["Location"]
        parsed_redirect = urlparse(redirect_url)
        login_token = parse_qs(parsed_redirect.query)["login_token"][0]

        exchange_response = self.client.post(
            "/api/training/internal/labs/exchange-jupyter-login/",
            {"login_token": login_token},
            format="json",
            HTTP_AUTHORIZATION="Bearer internal-jupyterhub-token",
        )

        self.assertEqual(exchange_response.status_code, status.HTTP_200_OK)
        self.assertTrue(exchange_response.data["authState"]["trainingContent"]["forceNotebookReset"])

    @override_settings(
        TRAINING_NOTEBOOK_RUNTIME_ENABLED=True,
        TRAINING_JUPYTERHUB_BASE_URL="https://labs.example.com/lab",
        TRAINING_JUPYTERHUB_SERVICE_TOKEN="internal-jupyterhub-token",
        TRAINING_JUPYTERHUB_SHARED_SECRET="shared-secret",
        TRAINING_JUPYTER_LOGIN_TTL_SECONDS=180,
        TRAINING_JUPYTERHUB_GPU_RUNTIME_ENABLED=False,
    )
    def test_launch_gateway_rejects_gpu_lab_when_gpu_runtime_is_disabled(self):
        self.client.force_authenticate(user=self.user)
        lab_profile = self.notebook_content.lab_profile
        lab_profile.allow_gpu = True
        lab_profile.save(update_fields=["allow_gpu", "updated_at"])

        response = self.client.post("/api/training/labs/cva-jupyter-lab/launch/", format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["detail"],
            "GPU-enabled notebook runtime is not available in this deployment.",
        )


class TrainingInternalJupyterAiProxyTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.course = OnlineCourse.objects.create(
            slug="proxy-course",
            title_de="Proxy Course",
            title_en="Proxy Course",
            short_description_de="Kurz",
            short_description_en="Short",
            description_de="Beschreibung",
            description_en="Description",
            lessons_count=1,
            trial_available=False,
            price_amount=Decimal("0.00"),
            currency="EUR",
        )
        self.content_item = TrainingContentItem.objects.create(
            slug="proxy-notebook",
            name="Proxy Notebook",
            description="Notebook for internal Jupyter AI proxy tests.",
            body_markdown=(
                "Market risk controls should quantify stressed exposure first. "
                "The control buffer then applies hedge ratio and loss factor."
            ),
            content_kind=TrainingContentItem.ContentKind.NOTEBOOK,
            status=TrainingContentItem.Status.PUBLISHED,
            access_scope=TrainingContentItem.AccessScope.AUTHENTICATED,
            course=self.course,
            supports_inline_lab=True,
        )
        self.module = OnlineCourseModule.objects.create(
            course=self.course,
            title="Module 1 (Week 1) - Python Basics",
            description="Runtime setup, syntax, and the first computational habits.",
            module_type=OnlineCourseModule.MODULE_TYPE_STANDARD,
            week_number=1,
            sort_order=10,
            is_active=True,
        )
        self.lesson = OnlineCourseLesson.objects.create(
            module=self.module,
            course=self.course,
            title="Getting Started with Python",
            description="Kernel setup, syntax basics, and the first notebook run.",
            sort_order=10,
            is_active=True,
        )
        self.introduction_section = OnlineCourseLessonSection.objects.create(
            lesson=self.lesson,
            section_type=OnlineCourseLessonSection.SECTION_INTRODUCTION,
            title="Introduction",
            description="Orientation and expected outcomes.",
            sort_order=10,
            is_active=True,
        )
        self.main_section = OnlineCourseLessonSection.objects.create(
            lesson=self.lesson,
            section_type=OnlineCourseLessonSection.SECTION_MAIN,
            title="Main content",
            description="Presentation, reading, and practical notebook.",
            sort_order=20,
            is_active=True,
        )
        self.intro_library = OnlineCourseContentLibraryItem.objects.create(
            section_type=OnlineCourseContentLibraryItem.SECTION_INTRODUCTION,
            title="Python setup orientation",
            description="Environment setup and notebook expectations.",
            library_group="proxy-course-week-1",
            asset_type=OnlineCourseContentLibraryItem.ASSET_DOCUMENT,
            language=OnlineCourse.LOCALE_EN,
            body_markdown=(
                "## Lesson focus\n"
                "- Environment in this lesson means the Python runtime and kernel setup used to run notebook code.\n"
                "- Confirm the interpreter version and keep the execution trace reproducible."
            ),
            is_active=True,
            sort_order=10,
        )
        self.reading_library = OnlineCourseContentLibraryItem.objects.create(
            section_type=OnlineCourseContentLibraryItem.SECTION_MAIN,
            title="Reading pack",
            description="Reference notes about reproducible runtime setup.",
            library_group="proxy-course-week-1",
            asset_type=OnlineCourseContentLibraryItem.ASSET_TEXT,
            language=OnlineCourse.LOCALE_EN,
            body_markdown=(
                "## Reading focus\n"
                "- A Python environment includes the runtime, kernel, interpreter version, and package assumptions.\n"
                "- Reproducible notebooks record these details before analysis starts."
            ),
            is_active=True,
            sort_order=20,
        )
        OnlineCourseLessonSectionItem.objects.create(
            section=self.introduction_section,
            source_library_item=self.intro_library,
            title="Getting Started with Python - Overview",
            description="Context and environment setup deck.",
            asset_type=OnlineCourseContentLibraryItem.ASSET_DOCUMENT,
            activity_type=OnlineCourseLessonSectionItem.ACTIVITY_TEXT,
            language=OnlineCourse.LOCALE_EN,
            body_markdown=(
                "## Overview\n"
                "This lesson explains how the notebook environment maps to the active kernel, runtime, and interpreter."
            ),
            sort_order=10,
            is_active=True,
        )
        OnlineCourseLessonSectionItem.objects.create(
            section=self.main_section,
            source_library_item=self.reading_library,
            title="Getting Started with Python - Reading",
            description="Reference notes and setup checklist.",
            asset_type=OnlineCourseContentLibraryItem.ASSET_TEXT,
            activity_type=OnlineCourseLessonSectionItem.ACTIVITY_TEXT,
            language=OnlineCourse.LOCALE_EN,
            body_markdown=(
                "## Runtime notes\n"
                "- The notebook environment is the execution context for your code.\n"
                "- Capture the interpreter version before you start."
            ),
            sort_order=20,
            is_active=True,
        )
        OnlineCourseLessonSectionItem.objects.create(
            section=self.main_section,
            title="Getting Started with Python - Notebook Assignment",
            description="Hands-on task in Jupyter Notebook.",
            asset_type=OnlineCourseContentLibraryItem.ASSET_NOTEBOOK,
            activity_type=OnlineCourseLessonSectionItem.ACTIVITY_ASSIGNMENT,
            language=OnlineCourse.LOCALE_EN,
            linked_training_content=self.content_item,
            sort_order=30,
            is_active=True,
        )
        ensure_training_content_indexed(self.content_item)

    @override_settings(
        TRAINING_AI_ENABLED=True,
        TRAINING_AI_PROVIDER="demo",
        TRAINING_JUPYTERHUB_SHARED_SECRET="shared-secret",
    )
    def test_internal_proxy_returns_openai_compatible_chat_completion(self):
        signed_token = build_internal_jupyter_ai_proxy_token(
            content_slug=self.content_item.slug,
            expires_at_epoch=int(timezone.now().timestamp()) + 300,
        )

        response = self.client.post(
            f"/api/training/internal/openai/{self.content_item.slug}/chat/completions",
            {
                "model": "demo-extractive-v1",
                "messages": [
                    {"role": "system", "content": "You help with notebook tasks."},
                    {"role": "user", "content": "How do I derive the control buffer?"},
                ],
            },
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {signed_token}",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["object"], "chat.completion")
        self.assertEqual(response.data["choices"][0]["message"]["role"], "assistant")
        assistant_content = response.data["choices"][0]["message"]["content"].lower()
        self.assertTrue(assistant_content)
        self.assertIn("references:", assistant_content)

    @override_settings(
        TRAINING_AI_ENABLED=True,
        TRAINING_AI_PROVIDER="demo",
        TRAINING_JUPYTERHUB_SHARED_SECRET="shared-secret",
    )
    def test_internal_proxy_rejects_invalid_token(self):
        response = self.client.get(
            f"/api/training/internal/openai/{self.content_item.slug}/models",
            HTTP_AUTHORIZATION="Bearer invalid-token",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @override_settings(
        TRAINING_AI_ENABLED=True,
        TRAINING_AI_PROVIDER="demo",
        TRAINING_JUPYTERHUB_SHARED_SECRET="shared-secret",
    )
    def test_internal_proxy_uses_related_lesson_context_for_notebook_questions(self):
        signed_token = build_internal_jupyter_ai_proxy_token(
            content_slug=self.content_item.slug,
            expires_at_epoch=int(timezone.now().timestamp()) + 300,
        )

        response = self.client.post(
            f"/api/training/internal/openai/{self.content_item.slug}/chat/completions",
            {
                "model": "demo-extractive-v1",
                "messages": [
                    {"role": "user", "content": "Explain the lesson topic environment in one concise paragraph."},
                ],
            },
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {signed_token}",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        assistant_content = response.data["choices"][0]["message"]["content"].lower()
        self.assertIn("environment", assistant_content)
        self.assertTrue("runtime" in assistant_content or "kernel" in assistant_content)
        self.assertIn("lesson scope", assistant_content)

    @override_settings(
        TRAINING_AI_ENABLED=True,
        TRAINING_AI_PROVIDER="demo",
        TRAINING_JUPYTERHUB_SHARED_SECRET="shared-secret",
        TRAINING_JUPYTER_SESSION_API_TOKEN_GRACE_SECONDS=3600,
    )
    def test_internal_proxy_accepts_recently_expired_token_within_grace(self):
        signed_token = build_internal_jupyter_ai_proxy_token(
            content_slug=self.content_item.slug,
            expires_at_epoch=int(timezone.now().timestamp()) - 60,
        )

        response = self.client.post(
            f"/api/training/internal/openai/{self.content_item.slug}/chat/completions",
            {
                "model": "demo-extractive-v1",
                "messages": [
                    {"role": "user", "content": "Summarize the notebook goal."},
                ],
            },
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {signed_token}",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["object"], "chat.completion")


class TrainingGradebookApiTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="gradebook.user@example.com",
            username="gradebook_user",
            password="StrongPass12345",
        )
        self.course = OnlineCourse.objects.create(
            slug="gradebook-course",
            title_de="Gradebook Course",
            title_en="Gradebook Course",
            short_description_de="Kurz",
            short_description_en="Short",
            description_de="Beschreibung",
            description_en="Description",
            lessons_count=7,
            trial_available=False,
            price_amount=Decimal("999.00"),
            currency="EUR",
        )
        self.cohort = OnlineCohort.objects.create(
            course=self.course,
            name="Gradebook Cohort",
            group_code="GRD-1",
            capacity=15,
            timezone="Europe/Berlin",
            status=OnlineCohort.STATUS_OPEN,
            is_public=False,
        )
        profile = OnlineStudentProfile.objects.create(
            user=self.user,
            first_name="Gradebook",
            last_name="Student",
            preferred_language="en",
        )
        OnlineEnrollment.objects.create(
            profile=profile,
            course=self.course,
            cohort=self.cohort,
            status=OnlineEnrollment.STATUS_ACTIVE,
        )
        self.audience = TrainingAudience.objects.create(
            slug="quant-lab",
            name="Quant Lab",
            is_internal=True,
        )
        TrainingUserAudienceGrant.objects.create(user=self.user, audience=self.audience)
        self.notebook_content = TrainingContentItem.objects.create(
            slug="cva-gradebook-lab",
            name="CVA Gradebook Lab",
            content_kind=TrainingContentItem.ContentKind.NOTEBOOK,
            status=TrainingContentItem.Status.PUBLISHED,
            access_scope=TrainingContentItem.AccessScope.ENTITLED,
            course=self.course,
            supports_inline_lab=True,
        )
        TrainingContentAudiencePolicy.objects.create(content_item=self.notebook_content, audience=self.audience)
        TrainingNotebookLabProfile.objects.create(
            content_item=self.notebook_content,
            runtime_backend=TrainingNotebookLabProfile.RuntimeBackend.JUPYTERHUB,
            grader_backend=TrainingNotebookLabProfile.GraderBackend.NBGRADER,
            runtime_image="quant/cva:1.0",
            notebook_path="labs/cva/gradebook.ipynb",
            launch_path="/lab/tree/labs/cva/gradebook.ipynb",
            grader_config={
                "mode": "demo",
                "maxScore": "100",
                "demoScore": "88",
                "passThreshold": "70",
                "feedbackMarkdown": "Demo grading completed successfully.",
            },
        )

    @override_settings(TRAINING_GRADER_RUNTIME_ENABLED=True)
    def test_submission_is_processed_by_worker_and_visible_in_gradebook(self):
        self.client.force_authenticate(user=self.user)
        notebook_upload, checksum = build_notebook_upload(name="gradebook-upload.ipynb")

        submission_response = self.client.post(
            "/api/training/labs/cva-gradebook-lab/submissions/",
            {
                "notebook": notebook_upload,
                "client_checksum": checksum,
            },
            format="multipart",
        )

        self.assertEqual(submission_response.status_code, status.HTTP_201_CREATED)
        submission = TrainingLabSubmission.objects.get(public_id=submission_response.data["public_id"])
        self.assertEqual(submission.status, TrainingLabSubmission.Status.QUEUED)
        self.assertTrue(submission_response.data["hasNotebookArtifact"])
        self.assertEqual(submission_response.data["notebookArtifactFilename"], "gradebook.ipynb")
        notebook_artifact = submission.get_primary_notebook_artifact()
        self.assertIsNotNone(notebook_artifact)
        self.assertEqual(notebook_artifact.artifact_kind, TrainingLabSubmissionArtifact.ArtifactKind.NOTEBOOK)
        self.assertEqual(notebook_artifact.checksum, checksum)
        self.assertEqual(TrainingGraderJob.objects.filter(submission=submission, status=TrainingGraderJob.Status.QUEUED).count(), 1)

        call_command("process_training_grader_jobs", limit=10, worker_name="training-test-worker")

        submission.refresh_from_db()
        self.assertEqual(submission.status, TrainingLabSubmission.Status.GRADED)
        self.assertEqual(submission.score, Decimal("88"))
        self.assertTrue(submission.passed)

        gradebook_entry = TrainingGradebookEntry.objects.get(user=self.user, content_item=self.notebook_content)
        self.assertEqual(gradebook_entry.attempts_count, 1)
        self.assertEqual(gradebook_entry.latest_score, Decimal("88"))
        self.assertEqual(gradebook_entry.best_score, Decimal("88"))
        self.assertTrue(gradebook_entry.passed)

        gradebook_response = self.client.get("/api/training/gradebook/?course=gradebook-course")

        self.assertEqual(gradebook_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(gradebook_response.data["results"]), 1)
        self.assertEqual(gradebook_response.data["results"][0]["latest_score"], "88.00")
        self.assertTrue(
            TrainingAuditEvent.objects.filter(
                event_type=TrainingAuditEvent.EventType.SUBMISSION_CREATED,
                submission=submission,
            ).exists()
        )
        self.assertTrue(
            TrainingAuditEvent.objects.filter(
                event_type=TrainingAuditEvent.EventType.GRADING_RESULT_APPLIED,
                submission=submission,
            ).exists()
        )

    @override_settings(TRAINING_GRADER_RUNTIME_ENABLED=True, TRAINING_GRADER_WEBHOOK_SECRET="grader-secret")
    def test_internal_grader_report_updates_submission(self):
        self.client.force_authenticate(user=self.user)
        submission = TrainingLabSubmission.objects.create(
            user=self.user,
            content_item=self.notebook_content,
            attempt_number=1,
            status=TrainingLabSubmission.Status.RUNNING,
            grader_backend=TrainingNotebookLabProfile.GraderBackend.NBGRADER,
            source_path="labs/cva/gradebook.ipynb",
            notebook_path="labs/cva/gradebook.ipynb",
            submitted_at=timezone.now(),
        )
        TrainingGraderJob.objects.create(
            submission=submission,
            backend=TrainingNotebookLabProfile.GraderBackend.NBGRADER,
            status=TrainingGraderJob.Status.RUNNING,
            available_at=timezone.now(),
            locked_at=timezone.now(),
        )

        response = self.client.post(
            "/api/training/internal/grading/report/",
            {
                "submissionId": str(submission.public_id),
                "score": "91.50",
                "maxScore": "100",
                "passed": True,
                "feedbackMarkdown": "Autograde complete.",
                "feedbackPayload": {"mode": "webhook", "hiddenTests": ["internal-only"]},
            },
            format="json",
            HTTP_AUTHORIZATION="Bearer grader-secret",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        submission.refresh_from_db()
        self.assertEqual(submission.status, TrainingLabSubmission.Status.GRADED)
        self.assertEqual(submission.score, Decimal("91.50"))
        self.assertTrue(submission.passed)
        self.assertNotIn("hiddenTests", submission.feedback_payload)
        self.assertEqual(submission.feedback_payload["mode"], "webhook")

        repeated_response = self.client.post(
            "/api/training/internal/grading/report/",
            {
                "submissionId": str(submission.public_id),
                "score": "10",
                "maxScore": "100",
                "passed": False,
                "feedbackMarkdown": "Should be ignored.",
                "feedbackPayload": {"mode": "webhook", "hiddenTests": ["still-hidden"]},
            },
            format="json",
            HTTP_AUTHORIZATION="Bearer grader-secret",
        )

        self.assertEqual(repeated_response.status_code, status.HTTP_200_OK)
        submission.refresh_from_db()
        self.assertEqual(submission.score, Decimal("91.50"))
        self.assertEqual(submission.feedback_markdown, "Autograde complete.")

    @override_settings(TRAINING_GRADER_RUNTIME_ENABLED=True)
    def test_submission_rejects_checksum_mismatch(self):
        self.client.force_authenticate(user=self.user)
        notebook_upload, _ = build_notebook_upload(name="gradebook-upload.ipynb")

        response = self.client.post(
            "/api/training/labs/cva-gradebook-lab/submissions/",
            {
                "notebook": notebook_upload,
                "client_checksum": "deadbeef",
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data["detail"],
            "Notebook checksum does not match the uploaded file.",
        )
        rejection_audit = TrainingAuditEvent.objects.get(event_type=TrainingAuditEvent.EventType.SUBMISSION_REJECTED)
        self.assertEqual(rejection_audit.actor, self.user)
        self.assertEqual(rejection_audit.content_item, self.notebook_content)

    @override_settings(TRAINING_GRADER_RUNTIME_ENABLED=True)
    def test_submission_rejects_invalid_notebook_payload(self):
        self.client.force_authenticate(user=self.user)
        invalid_upload = SimpleUploadedFile(
            name="gradebook.ipynb",
            content=b"not-json",
            content_type="application/x-ipynb+json",
        )

        response = self.client.post(
            "/api/training/labs/cva-gradebook-lab/submissions/",
            {"notebook": invalid_upload},
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["detail"], "Notebook file is not valid JSON.")

    @override_settings(TRAINING_GRADER_RUNTIME_ENABLED=True)
    def test_nbgrader_cli_stages_uploaded_notebook_and_persists_artifacts(self):
        self.client.force_authenticate(user=self.user)
        lab_profile = self.notebook_content.lab_profile
        lab_profile.grader_config = {
            "mode": "nbgrader_cli",
            "assignmentId": "cva_assignment",
            "resultJsonPath": "autograde-results/{student_id}/{assignment_id}/result.json",
            "feedbackHtmlPath": "feedback/{student_id}/{assignment_id}/{notebook_stem}.html",
        }
        lab_profile.save(update_fields=["grader_config", "updated_at"])
        notebook_upload, checksum = build_notebook_upload(
            name="cva-gradebook.ipynb",
            source="print('nbgrader-ready')",
        )

        with TemporaryDirectory() as media_root, TemporaryDirectory() as course_root:
            with override_settings(MEDIA_ROOT=media_root, TRAINING_NBGRADER_COURSE_ROOT=course_root):
                submission_response = self.client.post(
                    "/api/training/labs/cva-gradebook-lab/submissions/",
                    {
                        "notebook": notebook_upload,
                        "client_checksum": checksum,
                    },
                    format="multipart",
                )
                self.assertEqual(submission_response.status_code, status.HTTP_201_CREATED)
                submission = TrainingLabSubmission.objects.get(public_id=submission_response.data["public_id"])
                student_id = build_training_jupyter_username(self.user)
                staged_notebook_path = (
                    Path(course_root) / "submitted" / student_id / "cva_assignment" / "gradebook.ipynb"
                )
                result_json_path = (
                    Path(course_root) / "autograde-results" / student_id / "cva_assignment" / "result.json"
                )
                feedback_html_path = (
                    Path(course_root) / "feedback" / student_id / "cva_assignment" / "gradebook.html"
                )

                def fake_run_command(command: list[str], *, cwd: str) -> None:
                    self.assertEqual(Path(cwd).resolve(), Path(course_root).resolve())
                    result_json_path.parent.mkdir(parents=True, exist_ok=True)
                    feedback_html_path.parent.mkdir(parents=True, exist_ok=True)
                    result_json_path.write_text(
                        json.dumps(
                            {
                                "score": "95",
                                "maxScore": "100",
                                "passed": True,
                                "feedbackMarkdown": "nbgrader pipeline completed.",
                            }
                        ),
                        encoding="utf-8",
                    )
                    feedback_html_path.write_text("<html><body>Feedback</body></html>", encoding="utf-8")

                with patch("apps.training.services.grading._run_command", side_effect=fake_run_command):
                    call_command("process_training_grader_jobs", limit=10, worker_name="training-test-worker")

                submission.refresh_from_db()
                self.assertEqual(submission.status, TrainingLabSubmission.Status.GRADED)
                self.assertEqual(submission.score, Decimal("95"))
                self.assertTrue(submission.passed)
                self.assertTrue(staged_notebook_path.exists())
                self.assertIn("nbgrader-ready", staged_notebook_path.read_text(encoding="utf-8"))

                artifacts = list(submission.artifacts.order_by("artifact_kind", "id"))
                self.assertEqual(len(artifacts), 3)
                self.assertEqual(
                    [artifact.artifact_kind for artifact in artifacts],
                    [
                        TrainingLabSubmissionArtifact.ArtifactKind.FEEDBACK_HTML,
                        TrainingLabSubmissionArtifact.ArtifactKind.JSON_REPORT,
                        TrainingLabSubmissionArtifact.ArtifactKind.NOTEBOOK,
                    ],
                )
                for artifact in artifacts:
                    self.assertNotIn(str(Path(course_root)), artifact.storage_path)
                    self.assertTrue((Path(media_root) / artifact.storage_path).exists())

    @override_settings(TRAINING_GRADER_RUNTIME_ENABLED=True)
    def test_nbgrader_cli_rejects_course_root_outside_approved_root(self):
        self.client.force_authenticate(user=self.user)
        lab_profile = self.notebook_content.lab_profile
        notebook_upload, checksum = build_notebook_upload(name="cva-gradebook.ipynb")

        with TemporaryDirectory() as media_root, TemporaryDirectory() as approved_root, TemporaryDirectory() as escaped_root:
            lab_profile.grader_config = {
                "mode": "nbgrader_cli",
                "assignmentId": "cva_assignment",
                "courseRoot": escaped_root,
                "resultJsonPath": "autograde-results/{student_id}/{assignment_id}/result.json",
            }
            lab_profile.save(update_fields=["grader_config", "updated_at"])

            with override_settings(MEDIA_ROOT=media_root, TRAINING_NBGRADER_COURSE_ROOT=approved_root):
                submission_response = self.client.post(
                    "/api/training/labs/cva-gradebook-lab/submissions/",
                    {
                        "notebook": notebook_upload,
                        "client_checksum": checksum,
                    },
                    format="multipart",
                )
                self.assertEqual(submission_response.status_code, status.HTTP_201_CREATED)
                submission = TrainingLabSubmission.objects.get(public_id=submission_response.data["public_id"])

                call_command("process_training_grader_jobs", limit=10, worker_name="training-test-worker")

                submission.refresh_from_db()
                self.assertEqual(submission.status, TrainingLabSubmission.Status.FAILED)
                self.assertIn("approved root", submission.feedback_markdown)


class TrainingInternalNotebookActionsTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="notebook.actions@example.com",
            username="notebook_actions_user",
            password="StrongPass12345",
        )
        self.course = OnlineCourse.objects.create(
            slug="notebook-actions-course",
            title_de="Notebook Actions Course",
            title_en="Notebook Actions Course",
            short_description_de="Kurz",
            short_description_en="Short",
            description_de="Beschreibung",
            description_en="Description",
            lessons_count=1,
            trial_available=False,
            price_amount=Decimal("0.00"),
            currency="EUR",
        )
        self.cohort = OnlineCohort.objects.create(
            course=self.course,
            name="Notebook Actions Cohort",
            group_code="NBA-1",
            capacity=15,
            timezone="Europe/Berlin",
            status=OnlineCohort.STATUS_OPEN,
            is_public=False,
        )
        profile = OnlineStudentProfile.objects.create(
            user=self.user,
            first_name="Notebook",
            last_name="Student",
            preferred_language="en",
        )
        self.enrollment = OnlineEnrollment.objects.create(
            profile=profile,
            course=self.course,
            cohort=self.cohort,
            status=OnlineEnrollment.STATUS_ACTIVE,
        )
        self.content_item = TrainingContentItem.objects.create(
            slug="notebook-actions-lab",
            name="Notebook Actions Lab",
            description="Notebook action integration test lab.",
            body_markdown="Validation and submit actions should work from JupyterLab.",
            content_kind=TrainingContentItem.ContentKind.NOTEBOOK,
            status=TrainingContentItem.Status.PUBLISHED,
            access_scope=TrainingContentItem.AccessScope.AUTHENTICATED,
            course=self.course,
            supports_inline_lab=True,
        )
        TrainingNotebookLabProfile.objects.create(
            content_item=self.content_item,
            runtime_backend=TrainingNotebookLabProfile.RuntimeBackend.JUPYTERHUB,
            grader_backend=TrainingNotebookLabProfile.GraderBackend.CUSTOM,
            runtime_image="quant/bitcoin:1.0",
            notebook_path="labs/bitcoin/bitcoin_case_forecasting_lab.ipynb",
            launch_path="/lab/tree/labs/bitcoin/bitcoin_case_forecasting_lab.ipynb",
            grader_config=NOTEBOOK_GRADER_CONFIG,
        )
        self.module = OnlineCourseModule.objects.create(
            course=self.course,
            title="Module 1 (Week 1) - Bitcoin Case",
            description="Time-aware validation and notebook workflow.",
            module_type=OnlineCourseModule.MODULE_TYPE_STANDARD,
            week_number=1,
            sort_order=10,
            is_active=True,
        )
        self.lesson = OnlineCourseLesson.objects.create(
            module=self.module,
            course=self.course,
            title="Bitcoin Case: Forecasting with JupyterLab",
            description="Build a compact time-series workflow.",
            sort_order=10,
            is_active=True,
        )
        self.main_section = OnlineCourseLessonSection.objects.create(
            lesson=self.lesson,
            section_type=OnlineCourseLessonSection.SECTION_MAIN,
            title="Main content",
            description="Practice content",
            sort_order=10,
            is_active=True,
        )
        OnlineCourseLessonSectionItem.objects.create(
            section=self.main_section,
            title="Notebook practice",
            description="Hands-on Bitcoin case notebook.",
            asset_type=OnlineCourseContentLibraryItem.ASSET_NOTEBOOK,
            activity_type=OnlineCourseLessonSectionItem.ACTIVITY_ASSIGNMENT,
            language=OnlineCourse.LOCALE_EN,
            linked_training_content=self.content_item,
            sort_order=10,
            is_active=True,
        )

    def _signed_token(self) -> str:
        return build_internal_notebook_action_token(
            content_slug=self.content_item.slug,
            user_id=self.user.id,
            expires_at_epoch=int(timezone.now().timestamp()) + 300,
        )

    def _passing_notebook_upload(self) -> tuple[SimpleUploadedFile, str]:
        payload = {
            "cells": [
                {
                    "cell_type": "code",
                    "execution_count": 1,
                    "metadata": {},
                    "outputs": [
                        {
                            "name": "stdout",
                            "output_type": "stream",
                            "text": [
                                "Rows: 18\n",
                                "Baseline MAE: 715.00\n",
                                "Rolling MAE: 1406.67\n",
                                "Next forecast: 50066.67\n",
                            ],
                        }
                    ],
                    "source": [
                        "feature_frame['lag_1'] = feature_frame['close'].shift(1)\n",
                        "feature_frame['rolling_mean_3'] = feature_frame['close'].shift(1).rolling(3).mean()\n",
                    ],
                },
                {
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": [
                        "This conclusion mentions leakage and states clearly that the notebook is not investment advice."
                    ],
                },
            ],
            "metadata": {},
            "nbformat": 4,
            "nbformat_minor": 5,
        }
        content = json.dumps(payload).encode("utf-8")
        checksum = hashlib.sha256(content).hexdigest()
        return (
            SimpleUploadedFile(
                name="bitcoin_case_forecasting_lab.ipynb",
                content=content,
                content_type="application/x-ipynb+json",
            ),
            checksum,
        )

    @override_settings(
        TRAINING_GRADER_RUNTIME_ENABLED=True,
        TRAINING_JUPYTERHUB_SHARED_SECRET="shared-secret",
    )
    def test_internal_notebook_validate_returns_preview(self):
        notebook_upload, _checksum = self._passing_notebook_upload()

        response = self.client.post(
            f"/api/training/internal/notebook-actions/{self.content_item.slug}/validate/",
            {"notebook": notebook_upload},
            format="multipart",
            HTTP_AUTHORIZATION=f"Bearer {self._signed_token()}",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["validation"]["passed"])
        self.assertEqual(response.data["validation"]["feedbackPayload"]["tests"]["passed"], 9)
        self.assertIsNone(response.data["hint"])

    @override_settings(
        TRAINING_GRADER_RUNTIME_ENABLED=True,
        TRAINING_JUPYTERHUB_SHARED_SECRET="shared-secret",
        TRAINING_JUPYTER_SESSION_API_TOKEN_GRACE_SECONDS=3600,
    )
    def test_internal_notebook_validate_accepts_recently_expired_token_within_grace(self):
        notebook_upload, _checksum = self._passing_notebook_upload()
        signed_token = build_internal_notebook_action_token(
            content_slug=self.content_item.slug,
            user_id=self.user.id,
            expires_at_epoch=int(timezone.now().timestamp()) - 60,
        )

        response = self.client.post(
            f"/api/training/internal/notebook-actions/{self.content_item.slug}/validate/",
            {"notebook": notebook_upload},
            format="multipart",
            HTTP_AUTHORIZATION=f"Bearer {signed_token}",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["validation"]["passed"])

    @override_settings(
        TRAINING_GRADER_RUNTIME_ENABLED=True,
        TRAINING_JUPYTERHUB_SHARED_SECRET="shared-secret",
        TRAINING_JUPYTER_SESSION_API_TOKEN_GRACE_SECONDS=30,
    )
    def test_internal_notebook_validate_rejects_expired_token_beyond_grace(self):
        notebook_upload, _checksum = self._passing_notebook_upload()
        signed_token = build_internal_notebook_action_token(
            content_slug=self.content_item.slug,
            user_id=self.user.id,
            expires_at_epoch=int(timezone.now().timestamp()) - 60,
        )

        response = self.client.post(
            f"/api/training/internal/notebook-actions/{self.content_item.slug}/validate/",
            {"notebook": notebook_upload},
            format="multipart",
            HTTP_AUTHORIZATION=f"Bearer {signed_token}",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(response.data["detail"], "Notebook action token is expired.")

    @override_settings(
        TRAINING_GRADER_RUNTIME_ENABLED=True,
        TRAINING_JUPYTERHUB_SHARED_SECRET="shared-secret",
    )
    def test_internal_notebook_submit_marks_practice_complete(self):
        notebook_upload, checksum = self._passing_notebook_upload()

        response = self.client.post(
            f"/api/training/internal/notebook-actions/{self.content_item.slug}/submit/",
            {"notebook": notebook_upload, "client_checksum": checksum},
            format="multipart",
            HTTP_AUTHORIZATION=f"Bearer {self._signed_token()}",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["passed"])
        progress = OnlineLessonProgress.objects.get(enrollment=self.enrollment, lesson=self.lesson)
        self.assertIn(f"lesson-{self.lesson.id}-practice", progress.completed_step_ids)
        self.assertEqual(progress.progress_percent, 33)

    @override_settings(
        TRAINING_AI_ENABLED=True,
        TRAINING_JUPYTERHUB_SHARED_SECRET="shared-secret",
    )
    def test_internal_notebook_ask_returns_ai_answer_payload(self):
        response = self.client.post(
            f"/api/training/internal/notebook-actions/{self.content_item.slug}/ask/",
            {"question": "What should I mention in the conclusion?"},
            format="json",
            HTTP_AUTHORIZATION=f"Bearer {self._signed_token()}",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["answer"]["shortAnswer"])
        self.assertTrue(response.data["answer"]["detailedAnswer"])
        self.assertTrue(response.data["conversationId"])
        self.assertEqual(TrainingAiConversation.objects.count(), 1)
        self.assertEqual(TrainingAiMessage.objects.filter(role=TrainingAiMessage.Role.USER).count(), 1)
        self.assertEqual(TrainingAiMessage.objects.filter(role=TrainingAiMessage.Role.ASSISTANT).count(), 1)


class TrainingOpenAiProviderTests(TestCase):
    @override_settings(
        TRAINING_AI_PROVIDER="openai",
        TRAINING_AI_BASE_URL="https://api.openai.com/v1",
        TRAINING_AI_API_KEY="test-key",
        TRAINING_AI_CHAT_MODEL="gpt-5-mini",
        TRAINING_AI_TEMPERATURE=None,
    )
    def test_openai_provider_omits_temperature_when_not_configured(self):
        provider = OpenAiCompatibleTrainingAiProvider()
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "short_answer": "Short answer",
                                "detailed_answer": "Detailed answer",
                                "follow_up_prompts": ["Next"],
                                "resolution_status": "resolved",
                            }
                        )
                    }
                }
            ]
        }

        with patch("apps.training.services.ai_provider.requests.post", return_value=response) as mocked_post:
            provider.generate_answer(
                content_name="Market Risk Basics",
                question="What matters most?",
                prompt_type="ask",
                context_chunks=[],
            )

        payload = mocked_post.call_args.kwargs["json"]
        self.assertNotIn("temperature", payload)
        self.assertEqual(payload["model"], "gpt-5-mini")
        self.assertEqual(payload["response_format"], {"type": "json_object"})

    @override_settings(
        TRAINING_AI_PROVIDER="openai",
        TRAINING_AI_BASE_URL="https://api.openai.com/v1",
        TRAINING_AI_API_KEY="test-key",
        TRAINING_AI_CHAT_MODEL="gpt-4.1-mini",
        TRAINING_AI_TEMPERATURE=0.2,
    )
    def test_openai_provider_includes_temperature_when_explicitly_configured(self):
        provider = OpenAiCompatibleTrainingAiProvider()
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "short_answer": "Short answer",
                                "detailed_answer": "Detailed answer",
                                "follow_up_prompts": ["Next"],
                                "resolution_status": "resolved",
                            }
                        )
                    }
                }
            ]
        }

        with patch("apps.training.services.ai_provider.requests.post", return_value=response) as mocked_post:
            provider.generate_answer(
                content_name="Market Risk Basics",
                question="What matters most?",
                prompt_type="ask",
                context_chunks=[],
            )

        payload = mocked_post.call_args.kwargs["json"]
        self.assertEqual(payload["temperature"], 0.2)


class TrainingAiApiTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="student.ai@example.com",
            username="student_ai_user",
            password="StrongPass12345",
        )
        self.course = OnlineCourse.objects.create(
            slug="investment-analysis",
            title_de="Investment Analysis",
            title_en="Investment Analysis",
            short_description_de="Kurz",
            short_description_en="Short",
            description_de="Beschreibung",
            description_en="Description",
            lessons_count=6,
            trial_available=False,
            price_amount=Decimal("1299.00"),
            currency="EUR",
        )
        self.cohort = OnlineCohort.objects.create(
            course=self.course,
            name="Investment Analysis Cohort",
            group_code="IA-1",
            capacity=20,
            timezone="Europe/Berlin",
            status=OnlineCohort.STATUS_OPEN,
            is_public=False,
        )
        profile = OnlineStudentProfile.objects.create(
            user=self.user,
            first_name="Student",
            last_name="AI",
            preferred_language="en",
        )
        OnlineEnrollment.objects.create(
            profile=profile,
            course=self.course,
            cohort=self.cohort,
            status=OnlineEnrollment.STATUS_ACTIVE,
        )
        self.internal_audience = TrainingAudience.objects.create(
            slug="institutional-skills",
            name="Institutional Skills",
            is_internal=True,
        )
        self.visible_content = TrainingContentItem.objects.create(
            slug="fundamentals-of-investment-analysis",
            name="Fundamentals of Investment Analysis",
            description="A demo module about classic value investing principles.",
            body_markdown=(
                "## Margin of Safety\n"
                "Margin of safety means leaving room for estimation error and uncertainty before committing capital.\n\n"
                "## Investment versus Speculation\n"
                "Investment relies on disciplined analysis and downside protection, while speculation leans on short-term price moves.\n\n"
                "## Risk Review\n"
                "A sound process reviews downside scenarios, valuation gaps, and concentration risks before acting."
            ),
            content_kind=TrainingContentItem.ContentKind.ARTICLE,
            status=TrainingContentItem.Status.PUBLISHED,
            access_scope=TrainingContentItem.AccessScope.ENTITLED,
            course=self.course,
            source_url="https://example.com/fundamentals",
        )
        self.hidden_content = TrainingContentItem.objects.create(
            slug="institutional-risk-controls",
            name="Institutional Risk Controls",
            description="Hidden internal material.",
            body_markdown="## Internal Controls\nThis section describes internal infrastructure and control design.",
            content_kind=TrainingContentItem.ContentKind.ARTICLE,
            status=TrainingContentItem.Status.PUBLISHED,
            access_scope=TrainingContentItem.AccessScope.ENTITLED,
            course=self.course,
        )
        TrainingContentAudiencePolicy.objects.create(
            content_item=self.hidden_content,
            audience=self.internal_audience,
        )
        TrainingContentCrossReference.objects.create(
            from_item=self.visible_content,
            to_item=self.hidden_content,
            relation_type=TrainingContentCrossReference.RelationType.RELATED,
        )

    def test_anonymous_user_cannot_access_ai_ask_endpoint(self):
        response = self.client.post(
            "/api/training/ai/ask/",
            {
                "contentSlug": self.visible_content.slug,
                "question": "What is margin of safety?",
            },
            format="json",
        )
        self.assertIn(response.status_code, {status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN})

    def test_ai_ask_returns_visible_citations_only_and_persists_conversation(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/api/training/ai/ask/",
            {
                "contentSlug": self.visible_content.slug,
                "question": "What is margin of safety?",
                "promptType": "ask",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data["response"]["shortAnswer"])
        citations = response.data["response"]["citations"]
        self.assertGreaterEqual(len(citations), 1)
        self.assertTrue(all(item["contentSlug"] != self.hidden_content.slug for item in citations))
        self.assertEqual(TrainingAiConversation.objects.count(), 1)
        self.assertEqual(TrainingAiMessage.objects.filter(role=TrainingAiMessage.Role.USER).count(), 1)
        self.assertEqual(TrainingAiMessage.objects.filter(role=TrainingAiMessage.Role.ASSISTANT).count(), 1)
        self.assertGreaterEqual(TrainingKnowledgeChunk.objects.filter(content_item=self.visible_content).count(), 1)
        self.assertEqual(TrainingKnowledgeChunk.objects.filter(content_item=self.hidden_content).count(), 0)

        conversation_response = self.client.get(
            f"/api/training/ai/conversation/?content={self.visible_content.slug}"
        )
        self.assertEqual(conversation_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(conversation_response.data["messages"]), 2)
        self.assertEqual(
            TrainingAuditEvent.objects.filter(
                event_type=TrainingAuditEvent.EventType.AI_RESPONSE_GENERATED
            ).count(),
            1,
        )

    def test_hidden_content_cannot_be_queried_through_ai_endpoint(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            "/api/training/ai/ask/",
            {
                "contentSlug": self.hidden_content.slug,
                "question": "Show me internal controls.",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_ai_quiz_generation_and_submit_are_scored_server_side(self):
        self.client.force_authenticate(user=self.user)
        generate_response = self.client.post(
            "/api/training/ai/quizzes/generate/",
            {
                "contentSlug": self.visible_content.slug,
                "questionCount": 3,
            },
            format="json",
        )
        self.assertEqual(generate_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(generate_response.data["status"], TrainingAiQuizAttempt.Status.GENERATED)
        self.assertEqual(len(generate_response.data["questions"]), 3)
        self.assertTrue(
            all("correctOptionId" not in question for question in generate_response.data["questions"])
        )

        quiz_id = generate_response.data["publicId"]
        submit_response = self.client.post(
            f"/api/training/ai/quizzes/{quiz_id}/submit/",
            {
                "answers": [
                    {
                        "questionId": question["questionId"],
                        "selectedOptionId": "a",
                    }
                    for question in generate_response.data["questions"]
                ]
            },
            format="json",
        )
        self.assertEqual(submit_response.status_code, status.HTTP_200_OK)
        self.assertEqual(submit_response.data["status"], TrainingAiQuizAttempt.Status.COMPLETED)
        self.assertEqual(submit_response.data["score"], submit_response.data["maxScore"])
        self.assertTrue(
            all("correctOptionId" in question for question in submit_response.data["questions"])
        )
        self.assertEqual(
            TrainingAuditEvent.objects.filter(
                event_type=TrainingAuditEvent.EventType.AI_QUIZ_SUBMITTED
            ).count(),
            1,
        )


class TrainingAiAdminGovernanceApiTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin_user = User.objects.create_user(
            email="admin.ai.gov@example.com",
            username="admin_ai_gov",
            password="StrongPass12345",
            is_admin=True,
            is_staff=True,
        )
        self.owner_user = User.objects.create_user(
            email="owner.ai.gov@example.com",
            username="owner_ai_gov",
            password="StrongPass12345",
        )
        self.student_user = User.objects.create_user(
            email="student.ai.gov@example.com",
            username="student_ai_gov",
            password="StrongPass12345",
        )
        self.course = OnlineCourse.objects.create(
            slug="ai-governance-course",
            title_de="AI Governance",
            title_en="AI Governance",
            short_description_de="Kurz",
            short_description_en="Short",
            description_de="Beschreibung",
            description_en="Description",
            lessons_count=4,
            trial_available=False,
            price_amount=Decimal("799.00"),
            currency="EUR",
        )
        self.content = TrainingContentItem.objects.create(
            slug="ai-governance-fundamentals",
            name="AI Governance Fundamentals",
            description="Core content used to exercise the admin AI queue.",
            body_markdown=(
                "## Margin of safety\n"
                "A margin of safety cushions model error and protects capital allocation decisions."
            ),
            content_kind=TrainingContentItem.ContentKind.ARTICLE,
            status=TrainingContentItem.Status.PUBLISHED,
            access_scope=TrainingContentItem.AccessScope.ENTITLED,
            course=self.course,
        )
        self.draft_content = TrainingContentItem.objects.create(
            slug="ai-governance-draft",
            name="AI Governance Draft",
            description="Draft content should not be indexed from the admin rebuild endpoint.",
            body_markdown="Draft content should remain outside the published knowledge index.",
            content_kind=TrainingContentItem.ContentKind.ARTICLE,
            status=TrainingContentItem.Status.DRAFT,
            access_scope=TrainingContentItem.AccessScope.ENTITLED,
            course=self.course,
        )
        TrainingCourseRoleAssignment.objects.create(
            user=self.owner_user,
            course=self.course,
            role=TrainingCourseRoleAssignment.Role.OWNER,
            is_primary=True,
            response_sla_hours=6,
        )
        self.open_conversation = self._create_ai_conversation(
            title="Need more detail",
            latest_prompt="How should I interpret margin of safety for downside control?",
            governance_status=TrainingAiConversation.GovernanceStatus.OPEN,
            assistant_resolution=TrainingAiMessage.ResolutionStatus.PARTIAL,
        )
        self.in_review_conversation = self._create_ai_conversation(
            title="Need owner follow-up",
            latest_prompt="Please connect valuation buffers to risk governance.",
            governance_status=TrainingAiConversation.GovernanceStatus.IN_REVIEW,
            assistant_resolution=TrainingAiMessage.ResolutionStatus.ESCALATE,
            assigned_to=self.owner_user,
        )
        self.resolved_conversation = self._create_ai_conversation(
            title="Already resolved",
            latest_prompt="Summarize the investment process.",
            governance_status=TrainingAiConversation.GovernanceStatus.RESOLVED,
            assistant_resolution=TrainingAiMessage.ResolutionStatus.RESOLVED,
            resolved_by=self.admin_user,
            resolved_at=timezone.now(),
        )
        self.archived_conversation = self._create_ai_conversation(
            title="Archived queue item",
            latest_prompt="Internal note that should stay archived.",
            governance_status=TrainingAiConversation.GovernanceStatus.ARCHIVED,
            assistant_resolution=TrainingAiMessage.ResolutionStatus.PARTIAL,
            status_value=TrainingAiConversation.Status.ARCHIVED,
        )

    def _create_ai_conversation(
        self,
        *,
        title: str,
        latest_prompt: str,
        governance_status: str,
        assistant_resolution: str,
        assigned_to=None,
        resolved_by=None,
        resolved_at=None,
        status_value: str = TrainingAiConversation.Status.ACTIVE,
    ) -> TrainingAiConversation:
        conversation = TrainingAiConversation.objects.create(
            user=self.student_user,
            content_item=self.content,
            title=title,
            status=status_value,
            governance_status=governance_status,
            last_user_prompt=latest_prompt,
            assigned_to=assigned_to,
            resolved_by=resolved_by,
            resolved_at=resolved_at,
        )
        TrainingAiMessage.objects.create(
            conversation=conversation,
            content_item=self.content,
            role=TrainingAiMessage.Role.USER,
            body=latest_prompt,
        )
        TrainingAiMessage.objects.create(
            conversation=conversation,
            content_item=self.content,
            role=TrainingAiMessage.Role.ASSISTANT,
            body=(
                "The AI assistant provided a concise summary and flagged whether a course owner should review it."
            ),
            resolution_status=assistant_resolution,
        )
        return conversation

    def test_non_admin_cannot_access_ai_governance_endpoints(self):
        self.client.force_authenticate(user=self.student_user)
        endpoints = [
            ("get", "/api/training/admin/ai/overview/"),
            ("get", "/api/training/admin/ai/analytics/"),
            ("get", "/api/training/admin/ai/conversations/"),
            ("patch", f"/api/training/admin/ai/conversations/{self.open_conversation.public_id}/", {"governance_status": "resolved"}),
            ("post", "/api/training/admin/ai/rebuild-index/", {"course_id": self.course.id}),
        ]

        for method_name, path, *payload in endpoints:
            response = getattr(self.client, method_name)(
                path,
                payload[0] if payload else None,
                format="json",
            )
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_non_admin_ai_analytics_denied_attempt_is_audited(self):
        self.client.force_authenticate(user=self.student_user)

        response = self.client.get(f"/api/training/admin/ai/analytics/?course_id={self.course.id}")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        audit_event = TrainingAuditEvent.objects.get(
            event_type=TrainingAuditEvent.EventType.ADMIN_AI_ANALYTICS_VIEWED,
            outcome=TrainingAuditEvent.Outcome.DENIED,
        )
        self.assertEqual(audit_event.actor, self.student_user)
        self.assertEqual(audit_event.metadata["courseId"], str(self.course.id))

    @patch.object(
        TrainingAdminAiAnalyticsThrottle,
        "THROTTLE_RATES",
        {
            **settings.REST_FRAMEWORK.get("DEFAULT_THROTTLE_RATES", {}),
            "training_admin_ai_analytics": "1/min",
        },
    )
    def test_admin_ai_analytics_rate_limit_is_enforced(self):
        cache.clear()
        self.client.force_authenticate(user=self.admin_user)

        first_response = self.client.get(f"/api/training/admin/ai/analytics/?course_id={self.course.id}")
        second_response = self.client.get(f"/api/training/admin/ai/analytics/?course_id={self.course.id}")

        self.assertEqual(first_response.status_code, status.HTTP_200_OK)
        self.assertEqual(second_response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_admin_ai_overview_returns_metrics_without_raw_queue_payload(self):
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.get(f"/api/training/admin/ai/overview/?course_id={self.course.id}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["courseId"], self.course.id)
        self.assertEqual(response.data["aiConversations"], 4)
        self.assertEqual(response.data["unresolvedQueueCount"], 2)
        self.assertEqual(response.data["assignedQueueCount"], 1)
        self.assertEqual(response.data["resolvedConversations"], 1)
        self.assertEqual(response.data["archivedConversations"], 1)
        self.assertNotIn("latestUserPrompt", response.data)
        audit_event = TrainingAuditEvent.objects.get(
            event_type=TrainingAuditEvent.EventType.ADMIN_AI_OVERVIEW_VIEWED
        )
        self.assertEqual(audit_event.actor, self.admin_user)
        self.assertEqual(audit_event.metadata["courseId"], self.course.id)

    def test_admin_ai_queue_returns_only_open_or_in_review_partial_items(self):
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.get(f"/api/training/admin/ai/conversations/?course_id={self.course.id}&limit=10")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        returned_ids = {item["publicId"] for item in response.data["results"]}
        self.assertEqual(
            returned_ids,
            {
                str(self.open_conversation.public_id),
                str(self.in_review_conversation.public_id),
            },
        )
        self.assertTrue(
            all(item["latestResolutionStatus"] in {"partial", "escalate"} for item in response.data["results"])
        )
        self.assertTrue(all(item["governanceStatus"] in {"open", "in_review"} for item in response.data["results"]))

    def test_admin_can_assign_and_resolve_ai_queue_item(self):
        self.client.force_authenticate(user=self.admin_user)

        in_review_response = self.client.patch(
            f"/api/training/admin/ai/conversations/{self.open_conversation.public_id}/",
            {
                "assigned_to_id": self.owner_user.id,
                "governance_status": TrainingAiConversation.GovernanceStatus.IN_REVIEW,
                "resolution_note": "Escalated to the primary course owner for follow-up.",
            },
            format="json",
        )
        self.assertEqual(in_review_response.status_code, status.HTTP_200_OK)
        self.assertEqual(in_review_response.data["assignedTo"]["id"], self.owner_user.id)
        self.assertEqual(
            in_review_response.data["governanceStatus"],
            TrainingAiConversation.GovernanceStatus.IN_REVIEW,
        )

        resolved_response = self.client.patch(
            f"/api/training/admin/ai/conversations/{self.open_conversation.public_id}/",
            {
                "governance_status": TrainingAiConversation.GovernanceStatus.RESOLVED,
                "resolution_note": "Owner response delivered to the learner.",
            },
            format="json",
        )
        self.assertEqual(resolved_response.status_code, status.HTTP_200_OK)
        self.open_conversation.refresh_from_db()
        self.assertEqual(self.open_conversation.assigned_to, self.owner_user)
        self.assertEqual(self.open_conversation.governance_status, TrainingAiConversation.GovernanceStatus.RESOLVED)
        self.assertEqual(self.open_conversation.resolved_by, self.admin_user)
        self.assertIsNotNone(self.open_conversation.resolved_at)
        audit_events = TrainingAuditEvent.objects.filter(
            event_type=TrainingAuditEvent.EventType.ADMIN_AI_CONVERSATION_UPDATED
        )
        self.assertEqual(audit_events.count(), 2)

    def test_admin_patch_rejects_invalid_ai_governance_transition(self):
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.patch(
            f"/api/training/admin/ai/conversations/{self.archived_conversation.public_id}/",
            {"governance_status": TrainingAiConversation.GovernanceStatus.OPEN},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["detail"], "Invalid AI governance state transition.")

    def test_admin_rebuild_index_only_reindexes_published_content(self):
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.post(
            "/api/training/admin/ai/rebuild-index/",
            {"course_id": self.course.id},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["rebuiltContentItems"], 1)
        self.assertGreaterEqual(response.data["rebuiltChunks"], 1)
        self.assertGreaterEqual(TrainingKnowledgeChunk.objects.filter(content_item=self.content).count(), 1)
        self.assertEqual(TrainingKnowledgeChunk.objects.filter(content_item=self.draft_content).count(), 0)
        audit_event = TrainingAuditEvent.objects.get(
            event_type=TrainingAuditEvent.EventType.ADMIN_AI_INDEX_REBUILT
        )
        self.assertEqual(audit_event.actor, self.admin_user)
        self.assertEqual(audit_event.metadata["rebuiltContentItems"], 1)

    def test_admin_ai_analytics_returns_operational_metrics(self):
        self.client.force_authenticate(user=self.admin_user)
        ensure_training_content_indexed(self.content)
        self.content.authoring_source = TrainingContentItem.AuthoringSource.DIRECTUS
        self.content.last_synced_at = timezone.now()
        self.content.body_markdown = f"{self.content.body_markdown}\n\nUpdated after indexing."
        self.content.save(update_fields=["authoring_source", "last_synced_at", "body_markdown", "updated_at"])
        self.draft_content.authoring_source = TrainingContentItem.AuthoringSource.DIRECTUS
        self.draft_content.last_synced_at = timezone.now()
        self.draft_content.save(update_fields=["authoring_source", "last_synced_at", "updated_at"])

        for event_type in (
            TrainingAuditEvent.EventType.AI_QUESTION_ASKED,
            TrainingAuditEvent.EventType.AI_RESPONSE_FAILED,
            TrainingAuditEvent.EventType.AI_ESCALATION_SUGGESTED,
            TrainingAuditEvent.EventType.AI_QUIZ_SUBMIT_FAILED,
            TrainingAuditEvent.EventType.ADMIN_AI_INDEX_REBUILT,
        ):
            TrainingAuditEvent.objects.create(
                category=(
                    TrainingAuditEvent.Category.AI
                    if event_type.startswith("ai.")
                    else TrainingAuditEvent.Category.ADMIN
                ),
                event_type=event_type,
                actor=self.admin_user,
                actor_email=self.admin_user.email,
                course=self.course,
                content_item=self.content,
            )
        TrainingContentSyncEvent.objects.create(
            content_item=self.content,
            source=TrainingContentSyncEvent.Source.DIRECTUS,
            event_type=TrainingContentSyncEvent.EventType.UPSERT,
            status=TrainingContentSyncEvent.Status.FAILED,
            external_source_id="directus-analytics-failed",
            content_slug=self.content.slug,
            detail="Failed sync for analytics",
        )

        response = self.client.get(f"/api/training/admin/ai/analytics/?course_id={self.course.id}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["courseId"], self.course.id)
        self.assertEqual(response.data["aiQuestionsLast7Days"], 1)
        self.assertEqual(response.data["aiFailuresLast7Days"], 1)
        self.assertEqual(response.data["quizFailuresLast7Days"], 1)
        self.assertEqual(response.data["escalationsLast7Days"], 1)
        self.assertEqual(response.data["directusManagedContentItems"], 2)
        self.assertEqual(response.data["directusItemsWithoutOwner"], 2)
        self.assertEqual(response.data["staleIndexedPublishedItems"], 1)
        self.assertEqual(response.data["directusSyncFailuresLast7Days"], 1)
        self.assertIsNotNone(response.data["lastDirectusSyncAt"])
        self.assertIsNotNone(response.data["lastKnowledgeRefreshAt"])
        audit_event = TrainingAuditEvent.objects.get(
            event_type=TrainingAuditEvent.EventType.ADMIN_AI_ANALYTICS_VIEWED
        )
        self.assertEqual(audit_event.actor, self.admin_user)


class TrainingDirectusSyncApiTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner_user = User.objects.create_user(
            email="owner.directus@example.com",
            username="owner_directus",
            password="StrongPass12345",
        )
        self.course = OnlineCourse.objects.create(
            slug="directus-sync-course",
            title_de="Directus Sync",
            title_en="Directus Sync",
            short_description_de="Kurz",
            short_description_en="Short",
            description_de="Beschreibung",
            description_en="Description",
            lessons_count=3,
            trial_available=False,
            price_amount=Decimal("399.00"),
            currency="EUR",
        )
        self.audience = TrainingAudience.objects.create(
            slug="institutional-skills",
            name="Institutional Skills",
            is_internal=True,
        )
        self.reference_item = TrainingContentItem.objects.create(
            slug="reference-faq",
            name="Reference FAQ",
            description="Existing FAQ item for cross references.",
            body_markdown="Reference FAQ body",
            content_kind=TrainingContentItem.ContentKind.FAQ,
            status=TrainingContentItem.Status.PUBLISHED,
            access_scope=TrainingContentItem.AccessScope.ENTITLED,
            course=self.course,
        )

    @override_settings(TRAINING_DIRECTUS_SYNC_TOKEN="sync-secret")
    def test_directus_sync_requires_service_token(self):
        response = self.client.post(
            "/api/training/internal/directus/content-sync/",
            {"operation": "upsert", "slug": "missing-token", "name": "Missing token"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        audit_event = TrainingAuditEvent.objects.get(
            event_type=TrainingAuditEvent.EventType.DIRECTUS_SYNC_FAILED,
            outcome=TrainingAuditEvent.Outcome.DENIED,
        )
        self.assertTrue(audit_event.metadata["denied"])

    @override_settings(TRAINING_DIRECTUS_SYNC_TOKEN="sync-secret")
    @patch.object(
        TrainingDirectusSyncThrottle,
        "THROTTLE_RATES",
        {
            **settings.REST_FRAMEWORK.get("DEFAULT_THROTTLE_RATES", {}),
            "training_directus_sync": "1/min",
        },
    )
    def test_directus_sync_rate_limit_is_enforced(self):
        cache.clear()

        first_response = self.client.post(
            "/api/training/internal/directus/content-sync/",
            {"operation": "upsert", "slug": "rate-limit-1", "name": "Rate limit"},
            format="json",
            HTTP_AUTHORIZATION="Bearer sync-secret",
        )
        second_response = self.client.post(
            "/api/training/internal/directus/content-sync/",
            {"operation": "upsert", "slug": "rate-limit-2", "name": "Rate limit 2"},
            format="json",
            HTTP_AUTHORIZATION="Bearer sync-secret",
        )

        self.assertEqual(first_response.status_code, status.HTTP_200_OK)
        self.assertEqual(second_response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    @override_settings(TRAINING_DIRECTUS_SYNC_TOKEN="sync-secret")
    def test_directus_sync_upserts_published_content_and_rebuilds_index(self):
        response = self.client.post(
            "/api/training/internal/directus/content-sync/",
            {
                "operation": "upsert",
                "externalId": "directus-asset-1",
                "slug": "directus-cva-primer",
                "name": "Directus CVA Primer",
                "description": "Synced from Directus.",
                "bodyMarkdown": "## CVA\nCVA represents expected credit adjustment over the life of a trade.",
                "contentKind": "article",
                "status": "published",
                "accessScope": "entitled",
                "courseSlug": self.course.slug,
                "ownerEmail": self.owner_user.email,
                "assetClasses": [{"slug": "credit", "name": "Credit"}],
                "topics": ["cva"],
                "audienceSlugs": [self.audience.slug],
                "crossReferences": [{"slug": self.reference_item.slug, "relationType": "related"}],
            },
            format="json",
            HTTP_AUTHORIZATION="Bearer sync-secret",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["action"], "created")
        self.assertEqual(response.data["indexAction"], "rebuilt")
        self.assertGreaterEqual(response.data["indexedChunks"], 1)
        content_item = TrainingContentItem.objects.get(slug="directus-cva-primer")
        self.assertEqual(content_item.authoring_source, TrainingContentItem.AuthoringSource.DIRECTUS)
        self.assertEqual(content_item.authoring_source_id, "directus-asset-1")
        self.assertEqual(content_item.owner, self.owner_user)
        self.assertEqual(content_item.course, self.course)
        self.assertEqual(content_item.asset_classes.count(), 1)
        self.assertEqual(content_item.topics.count(), 1)
        self.assertEqual(content_item.audience_policies.count(), 1)
        self.assertEqual(content_item.outgoing_references.count(), 1)
        self.assertGreaterEqual(content_item.knowledge_chunks.filter(is_active=True).count(), 1)
        audit_event = TrainingAuditEvent.objects.get(
            event_type=TrainingAuditEvent.EventType.DIRECTUS_SYNC_APPLIED
        )
        self.assertEqual(audit_event.content_item, content_item)
        self.assertEqual(audit_event.metadata["indexAction"], "rebuilt")

    @override_settings(TRAINING_DIRECTUS_SYNC_TOKEN="sync-secret")
    def test_directus_sync_draft_deactivates_existing_index(self):
        content_item = TrainingContentItem.objects.create(
            slug="directus-draft-item",
            name="Directus Draft Item",
            description="Published before sync downgrade.",
            body_markdown="## Body\nPublished content before draft transition.",
            content_kind=TrainingContentItem.ContentKind.ARTICLE,
            status=TrainingContentItem.Status.PUBLISHED,
            access_scope=TrainingContentItem.AccessScope.ENTITLED,
            course=self.course,
            authoring_source=TrainingContentItem.AuthoringSource.DIRECTUS,
            authoring_source_id="directus-draft-1",
        )
        ensure_training_content_indexed(content_item)
        self.assertGreaterEqual(content_item.knowledge_chunks.filter(is_active=True).count(), 1)

        response = self.client.post(
            "/api/training/internal/directus/content-sync/",
            {
                "operation": "upsert",
                "externalId": "directus-draft-1",
                "slug": content_item.slug,
                "name": content_item.name,
                "description": content_item.description,
                "bodyMarkdown": content_item.body_markdown,
                "contentKind": content_item.content_kind,
                "status": "draft",
                "accessScope": content_item.access_scope,
                "courseSlug": self.course.slug,
            },
            format="json",
            HTTP_AUTHORIZATION="Bearer sync-secret",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["indexAction"], "deactivated")
        content_item.refresh_from_db()
        self.assertEqual(content_item.status, TrainingContentItem.Status.DRAFT)
        self.assertEqual(content_item.knowledge_chunks.filter(is_active=True).count(), 0)

    @override_settings(TRAINING_DIRECTUS_SYNC_TOKEN="sync-secret")
    def test_directus_sync_rejects_unknown_audience_slug(self):
        response = self.client.post(
            "/api/training/internal/directus/content-sync/",
            {
                "operation": "upsert",
                "slug": "bad-audience-item",
                "name": "Bad Audience Item",
                "bodyMarkdown": "Body",
                "contentKind": "article",
                "status": "published",
                "audienceSlugs": ["missing-audience"],
            },
            format="json",
            HTTP_AUTHORIZATION="Bearer sync-secret",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Unknown audience slugs", response.data["detail"])
        audit_event = TrainingAuditEvent.objects.get(
            event_type=TrainingAuditEvent.EventType.DIRECTUS_SYNC_FAILED
        )
        self.assertIn("Unknown audience slugs", audit_event.metadata["reason"])

    @override_settings(TRAINING_DIRECTUS_SYNC_TOKEN="sync-secret")
    def test_directus_sync_cannot_overwrite_manual_content_by_slug_only(self):
        TrainingContentItem.objects.create(
            slug="manual-credit-note",
            name="Manual Credit Note",
            description="Manually managed content",
            body_markdown="Body",
            content_kind=TrainingContentItem.ContentKind.ARTICLE,
            status=TrainingContentItem.Status.PUBLISHED,
            access_scope=TrainingContentItem.AccessScope.ENTITLED,
            course=self.course,
            authoring_source=TrainingContentItem.AuthoringSource.MANUAL,
        )

        response = self.client.post(
            "/api/training/internal/directus/content-sync/",
            {
                "operation": "upsert",
                "slug": "manual-credit-note",
                "name": "Manual Credit Note",
                "bodyMarkdown": "Updated by Directus",
                "contentKind": "article",
                "status": "published",
            },
            format="json",
            HTTP_AUTHORIZATION="Bearer sync-secret",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("cannot overwrite manually managed content", response.data["detail"])


class TrainingNotebookAssignmentFlowTests(APITestCase):
    def setUp(self):
        self.temp_media_root = TemporaryDirectory()
        self.addCleanup(self.temp_media_root.cleanup)
        self.override = override_settings(
            MEDIA_ROOT=self.temp_media_root.name,
            TRAINING_GRADER_RUNTIME_ENABLED=True,
            TRAINING_NOTEBOOK_RUNTIME_ENABLED=True,
        )
        self.override.enable()
        self.addCleanup(self.override.disable)

        self.admin_client = APIClient()
        self.student_client = APIClient()

        self.admin_user = User.objects.create_user(
            email="admin.notebooks@example.com",
            username="admin_notebooks",
            password="StrongPass12345",
            is_admin=True,
            is_staff=True,
        )
        self.student_user = User.objects.create_user(
            email="student.notebooks@example.com",
            username="student_notebooks",
            password="StrongPass12345",
        )
        self.admin_client.force_authenticate(user=self.admin_user)
        self.student_client.force_authenticate(user=self.student_user)

        self.course = OnlineCourse.objects.create(
            slug="notebook-admin-course",
            title_de="Notebook Admin Course",
            title_en="Notebook Admin Course",
            short_description_de="Kurz",
            short_description_en="Short",
            description_de="Beschreibung",
            description_en="Description",
            lessons_count=3,
            trial_available=False,
            price_amount=Decimal("699.00"),
            currency="EUR",
        )
        self.cohort = OnlineCohort.objects.create(
            course=self.course,
            name="Notebook Cohort",
            group_code="NBK-1",
            capacity=12,
            timezone="Europe/Berlin",
            status=OnlineCohort.STATUS_OPEN,
            is_public=False,
        )
        profile = OnlineStudentProfile.objects.create(
            user=self.student_user,
            first_name="Notebook",
            last_name="Student",
            preferred_language="en",
        )
        OnlineEnrollment.objects.create(
            profile=profile,
            course=self.course,
            cohort=self.cohort,
            status=OnlineEnrollment.STATUS_ACTIVE,
        )

        self.asset_class = TrainingAssetClass.objects.create(slug="rates", name="Rates")
        self.topic = TrainingTopic.objects.create(slug="duration", name="Duration")
        self.demo_role = TrainingAudience.objects.create(
            slug="interns-new-grads-notebook-tests",
            name="Student access",
            short_label="Student",
            audience_type=TrainingAudience.AudienceType.DEMO_ROLE,
            privilege_rank=20,
            is_internal=True,
        )
        TrainingUserAudienceGrant.objects.create(user=self.student_user, audience=self.demo_role)

    def _assignment_payload(self, *, slug: str = "duration-lab") -> dict[str, object]:
        return {
            "slug": slug,
            "name": "Bond duration lab",
            "description": "Work with duration and scenario shocks.",
            "body_markdown": "## Objective\nUse the starter notebook to analyse a bond shock scenario.",
            "status": "published",
            "access_scope": "entitled",
            "difficulty": "intermediate",
            "course_id": self.course.id,
            "owner_id": self.admin_user.id,
            "estimated_minutes": 50,
            "is_repeatable_on_demand": True,
            "supports_inline_lab": True,
            "asset_class_ids": [self.asset_class.id],
            "topic_ids": [self.topic.id],
            "audience_ids": [self.demo_role.id],
            "lab": {
                "runtimeBackend": "jupyterhub",
                "graderBackend": "custom",
                "runtimeImage": "quants/base:demo",
                "notebookPath": f"training/runtime-content/{slug}/starter.ipynb",
                "launchPath": f"/lab/tree/training/runtime-content/{slug}/starter.ipynb",
                "assignmentCode": slug.replace("-", "_"),
                "passThresholdPercent": 70,
                "maxAttempts": 3,
                "allowGpu": False,
                "allowNetwork": False,
                "maxSessionMinutes": 120,
                "isActive": True,
                "graderConfig": {
                    "mode": "custom_rules",
                    "maxScore": "100",
                    "checks": [
                        {
                            "id": "check-price",
                            "label": "Assign price",
                            "kind": "code_contains",
                            "points": "50",
                            "needle": "price = 42",
                            "successMessage": "Price variable is present.",
                            "failureMessage": "Define price = 42 in the notebook.",
                            "hintIds": [],
                        },
                        {
                            "id": "check-helper",
                            "label": "Define hedge_ratio",
                            "kind": "required_function",
                            "points": "50",
                            "functionName": "hedge_ratio",
                            "successMessage": "Function found.",
                            "failureMessage": "Add a hedge_ratio function.",
                            "hintIds": [1],
                        },
                    ],
                },
            },
            "hints": [
                {
                    "title": "Start with the bond price variable",
                    "body_markdown": "Define `price = 42` before you work on the helper function.",
                    "availability_mode": "after_failure",
                    "min_attempt_number": 1,
                    "max_score_percent": 100,
                    "sort_order": 10,
                    "is_active": True,
                }
            ],
        }

    def _create_notebook_assignment(self, *, slug: str = "duration-lab") -> TrainingContentItem:
        response = self.admin_client.post(
            "/api/training/admin/notebook-assignments/",
            self._assignment_payload(slug=slug),
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        return TrainingContentItem.objects.get(id=response.data["id"])

    def test_admin_can_crud_notebook_assignment_and_sync_library(self):
        create_response = self.admin_client.post(
            "/api/training/admin/notebook-assignments/",
            self._assignment_payload(),
            format="json",
        )

        self.assertEqual(create_response.status_code, status.HTTP_201_CREATED)
        content_item = TrainingContentItem.objects.get(id=create_response.data["id"])
        self.assertEqual(content_item.content_kind, TrainingContentItem.ContentKind.NOTEBOOK)
        self.assertTrue(OnlineCourseContentLibraryItem.objects.filter(training_content=content_item).exists())
        self.assertEqual(content_item.lab_profile.hints.count(), 1)
        self.assertEqual(
            content_item.lab_profile.grader_config["checks"][1]["hintIds"],
            [content_item.lab_profile.hints.first().id],
        )

        update_response = self.admin_client.patch(
            f"/api/training/admin/notebook-assignments/{content_item.id}/",
            {
                **self._assignment_payload(),
                "name": "Updated duration lab",
                "hints": [
                    {
                        "title": "Updated hint",
                        "body_markdown": "Use a helper function for the hedge ratio.",
                        "availability_mode": "after_attempt",
                        "min_attempt_number": 1,
                        "max_score_percent": 100,
                        "sort_order": 20,
                        "is_active": True,
                    }
                ],
            },
            format="json",
        )

        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        content_item.refresh_from_db()
        self.assertEqual(content_item.name, "Updated duration lab")
        self.assertEqual(content_item.lab_profile.hints.first().title, "Updated hint")

        delete_response = self.admin_client.delete(f"/api/training/admin/notebook-assignments/{content_item.id}/")
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(TrainingContentItem.objects.filter(id=content_item.id).exists())

    def test_admin_can_upload_starter_notebook_into_runtime_storage(self):
        notebook, checksum = build_notebook_upload(source="price = 42\nprint(price)")

        response = self.admin_client.post(
            "/api/training/admin/notebook-assignments/upload-starter/",
            {"content_slug": "duration-lab", "notebook": notebook},
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        stored_file = Path(settings.MEDIA_ROOT) / response.data["storagePath"]
        self.assertTrue(stored_file.exists())
        self.assertEqual(response.data["checksum"], checksum)
        self.assertTrue(response.data["notebookPath"].endswith(".ipynb"))

    def test_student_submission_runs_custom_rules_and_exposes_hints_and_artifacts(self):
        content_item = self._create_notebook_assignment()
        notebook, _checksum = build_notebook_upload(source="price = 42\nprint(price)")

        submit_response = self.student_client.post(
            f"/api/training/labs/{content_item.slug}/submissions/",
            {"notebook": notebook},
            format="multipart",
        )

        self.assertEqual(submit_response.status_code, status.HTTP_201_CREATED)
        processing_result = process_pending_grader_jobs(limit=10)
        self.assertEqual(processing_result["failed"], 0)

        detail_response = self.student_client.get(f"/api/training/content/{content_item.slug}/")
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.data["labSummary"]["attemptsRemaining"], 2)
        self.assertEqual(detail_response.data["labSummary"]["unlockedHintsCount"], 1)

        submissions_response = self.student_client.get(f"/api/training/labs/{content_item.slug}/submissions/")
        self.assertEqual(submissions_response.status_code, status.HTTP_200_OK)
        submission_payload = submissions_response.data["results"][0]
        self.assertEqual(submission_payload["status"], "graded")
        self.assertEqual(submission_payload["passed"], False)
        self.assertIsNotNone(submission_payload["feedbackReportUrl"])
        self.assertIsNotNone(submission_payload["jsonReportUrl"])
        self.assertTrue(submission_payload["feedback_payload"]["tests"])
        self.assertTrue(submission_payload["feedback_payload"]["feedbackHighlights"])

        hint = TrainingNotebookLabHint.objects.get(lab_profile=content_item.lab_profile)
        hint_response = self.student_client.post(
            f"/api/training/labs/{content_item.slug}/hints/{hint.id}/view/",
            format="json",
        )
        self.assertEqual(hint_response.status_code, status.HTTP_200_OK)
        self.assertTrue(
            TrainingAuditEvent.objects.filter(
                event_type=TrainingAuditEvent.EventType.LAB_HINT_VIEWED,
                content_item=content_item,
                actor=self.student_user,
            ).exists()
        )

    def test_student_can_submit_text_answer_for_quick_check(self):
        content_item = self._create_notebook_assignment(slug="quick-answer-lab")
        content_item.lab_profile.grader_config = {
            "mode": "custom_rules",
            "textSubmissionChecks": [
                {
                    "id": "metric",
                    "label": "Metric",
                    "kind": "output_contains",
                    "needle": "Score: 42.00",
                    "points": "60",
                    "failureMessage": "Include the metric in the answer.",
                },
                {
                    "id": "risk",
                    "label": "Risk note",
                    "kind": "markdown_contains",
                    "needle": "leakage",
                    "points": "40",
                    "failureMessage": "Mention leakage in the answer.",
                },
            ],
        }
        content_item.lab_profile.save(update_fields=["grader_config", "updated_at"])

        submit_response = self.student_client.post(
            f"/api/training/labs/{content_item.slug}/submissions/",
            {
                "answerText": "Score: 42.00\nLeakage should be avoided in the time split.",
            },
            format="json",
        )

        self.assertEqual(submit_response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(submit_response.data["submissionMode"], "text_answer")
        self.assertEqual(submit_response.data["status"], "graded")
        self.assertTrue(submit_response.data["passed"])
        self.assertTrue(submit_response.data["hasResponseText"])
        self.assertIn("Score: 42.00", submit_response.data["responseTextPreview"])

        feedback_path = urlparse(submit_response.data["feedbackReportUrl"]).path
        artifact_response = self.student_client.get(feedback_path)
        self.assertEqual(artifact_response.status_code, status.HTTP_200_OK)
        self.assertIn("sandbox", artifact_response["Content-Security-Policy"])
        self.assertEqual(artifact_response["X-Content-Type-Options"], "nosniff")
        list(artifact_response.streaming_content)
        artifact_response.close()

    def test_custom_rules_support_output_and_assignment_checks(self):
        content_item = self._create_notebook_assignment(slug="btc-output-lab")
        content_item.lab_profile.grader_config = {
            "mode": "custom_rules",
            "maxScore": "100",
            "checks": [
                {
                    "id": "assignment-present",
                    "label": "Forecast assignment",
                    "kind": "required_assignment",
                    "variable": "next_day_forecast",
                    "points": "40",
                    "failureMessage": "Create the next_day_forecast assignment.",
                },
                {
                    "id": "output-visible",
                    "label": "Rendered forecast output",
                    "kind": "output_contains",
                    "needle": "Next forecast: 50066.67",
                    "points": "40",
                    "failureMessage": "Run the notebook and keep the forecast output visible.",
                },
                {
                    "id": "rationale-note",
                    "label": "Notebook rationale",
                    "kind": "markdown_contains",
                    "needle": "educational",
                    "points": "20",
                    "failureMessage": "Explain that the notebook remains educational.",
                },
            ],
        }
        content_item.lab_profile.save(update_fields=["grader_config", "updated_at"])

        payload = {
            "cells": [
                {
                    "cell_type": "code",
                    "execution_count": 1,
                    "metadata": {},
                    "outputs": [
                        {
                            "name": "stdout",
                            "output_type": "stream",
                            "text": ["Next forecast: 50066.67\n"],
                        }
                    ],
                    "source": [
                        "next_day_forecast = 50066.67\n",
                        "print(f'Next forecast: {next_day_forecast:.2f}')\n",
                    ],
                },
                {
                    "cell_type": "markdown",
                    "metadata": {},
                    "source": [
                        "This notebook is educational and not investment advice.",
                    ],
                },
            ],
            "metadata": {},
            "nbformat": 4,
            "nbformat_minor": 5,
        }
        notebook = SimpleUploadedFile(
            name="btc-output-lab.ipynb",
            content=json.dumps(payload).encode("utf-8"),
            content_type="application/x-ipynb+json",
        )

        submit_response = self.student_client.post(
            f"/api/training/labs/{content_item.slug}/submissions/",
            {"notebook": notebook},
            format="multipart",
        )
        self.assertEqual(submit_response.status_code, status.HTTP_201_CREATED)

        processing_result = process_pending_grader_jobs(limit=10)
        self.assertEqual(processing_result["failed"], 0)

        submission = TrainingLabSubmission.objects.get(public_id=submit_response.data["public_id"])
        self.assertEqual(submission.status, TrainingLabSubmission.Status.GRADED)
        self.assertTrue(submission.passed)
        self.assertEqual(submission.score, Decimal("100.00"))
        self.assertEqual(submission.feedback_payload["tests"]["passed"], 3)

    def test_max_attempts_is_enforced_for_custom_rule_notebooks(self):
        content_item = self._create_notebook_assignment(slug="single-attempt-lab")
        content_item.lab_profile.max_attempts = 1
        content_item.lab_profile.save(update_fields=["max_attempts", "updated_at"])
        notebook, _checksum = build_notebook_upload(source="price = 42\nprint(price)")

        first_response = self.student_client.post(
            f"/api/training/labs/{content_item.slug}/submissions/",
            {"notebook": notebook},
            format="multipart",
        )
        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)
        process_pending_grader_jobs(limit=10)

        second_notebook, _second_checksum = build_notebook_upload(
            name="submission-2.ipynb",
            source="price = 42\nprint(price)",
        )
        second_response = self.student_client.post(
            f"/api/training/labs/{content_item.slug}/submissions/",
            {"notebook": second_notebook},
            format="multipart",
        )

        self.assertEqual(second_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Maximum number of notebook attempts has been reached.", second_response.data["detail"])

    def test_repeatable_passed_notebook_allows_additional_submissions_after_attempt_limit(self):
        content_item = self._create_notebook_assignment(slug="repeatable-passed-lab")
        content_item.lab_profile.max_attempts = 1
        content_item.lab_profile.save(update_fields=["max_attempts", "updated_at"])
        passing_source = "price = 42\n\ndef hedge_ratio():\n    return 1\n\nprint(price)\n"
        first_notebook, _checksum = build_notebook_upload(source=passing_source)

        first_response = self.student_client.post(
            f"/api/training/labs/{content_item.slug}/submissions/",
            {"notebook": first_notebook},
            format="multipart",
        )
        self.assertEqual(first_response.status_code, status.HTTP_201_CREATED)
        process_pending_grader_jobs(limit=10)

        detail_response = self.student_client.get(f"/api/training/content/{content_item.slug}/")
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertIsNone(detail_response.data["labSummary"]["attemptsRemaining"])
        self.assertTrue(detail_response.data["labSummary"]["gradebook"]["passed"])

        second_notebook, _second_checksum = build_notebook_upload(
            name="repeatable-second.ipynb",
            source=passing_source,
        )
        second_response = self.student_client.post(
            f"/api/training/labs/{content_item.slug}/submissions/",
            {"notebook": second_notebook},
            format="multipart",
        )

        self.assertEqual(second_response.status_code, status.HTTP_201_CREATED)


class TrainingBitcoinCaseSeedCommandTests(TestCase):
    def setUp(self):
        self.student_user = User.objects.create_user(
            email="mailpit.student@example.com",
            username="btc_student",
            password="StrongPass12345",
            first_name="Demo",
            last_name="Student",
        )

    def test_bitcoin_case_command_creates_course_and_runtime_dataset(self):
        with TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                call_command(
                    "seed_training_bitcoin_case_demo",
                    student_email=self.student_user.email,
                    teacher_email="",
                )

                course = OnlineCourse.objects.get(slug=COURSE_SLUG)
                content_item = TrainingContentItem.objects.get(slug=NOTEBOOK_CONTENT_SLUG)
                self.assertEqual(course.structured_lessons.count(), 1)
                self.assertTrue(content_item.supports_inline_lab)
                self.assertTrue(content_item.lab_profile.is_active)
                self.assertEqual(content_item.lab_profile.assignment_code, "bitcoin_case_forecasting_lab")
                self.assertTrue(
                    OnlineEnrollment.objects.filter(
                        course=course,
                        profile__user=self.student_user,
                        status=OnlineEnrollment.STATUS_ACTIVE,
                    ).exists()
                )
                dataset_path = runtime_content_root() / "labs" / NOTEBOOK_CONTENT_SLUG / "btc_usd_daily.csv"
                self.assertTrue(dataset_path.exists())
                self.assertIn("date,close,volume_usd_m", dataset_path.read_text(encoding="utf-8"))
