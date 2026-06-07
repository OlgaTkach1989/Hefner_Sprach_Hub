from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.employees.models import Lehrer
from apps.online.models import (
    OnlineCohort,
    OnlineCourse,
    OnlineCourseMaterial,
    OnlineEnrollment,
    OnlineSession,
    OnlineStudentProfile,
    OnlineWorkspace,
)
from apps.online.services.course_structure import (
    sync_course_instructor_assignments,
    sync_course_workspace_placements,
    upsert_course_structure,
)
from apps.training.demo_bitcoin_course_spec import (
    BTC_USD_DAILY_DATASET_CSV,
    CONCEPT_MARKDOWN,
    COURSE_DESCRIPTION,
    COURSE_HERO_IMAGE_URL,
    COURSE_SHORT_DESCRIPTION,
    COURSE_SLUG,
    COURSE_TITLE,
    LESSON_DESCRIPTION,
    LESSON_TITLE,
    MODULE_DESCRIPTION,
    MODULE_TITLE,
    NOTEBOOK_ASSIGNMENT_CODE,
    NOTEBOOK_CONTENT_SLUG,
    NOTEBOOK_FILENAME,
    NOTEBOOK_GRADER_CONFIG,
    NOTEBOOK_HINTS,
    PRACTICE_MARKDOWN,
    QUIZ_PAYLOAD,
    SUMMARY_MARKDOWN,
    THEORY_MARKDOWN,
    VIDEO_URL,
    bitcoin_case_starter_notebook,
)
from apps.training.models import (
    TrainingContentItem,
    TrainingNotebookLabHint,
    TrainingNotebookLabProfile,
)
from apps.training.services.knowledge_base import ensure_training_content_indexed
from apps.training.services.notebook_assignments import sync_course_library_for_notebook_content
from apps.training.services.notebook_storage import runtime_content_root, store_runtime_notebook_text

User = get_user_model()


class Command(BaseCommand):
    help = (
        "Seed a JupyterLab mini-course for educational Bitcoin time-series forecasting with "
        "a local dataset snapshot, workflow-based grading, and lesson flow integration."
    )

    def add_arguments(self, parser):
        parser.add_argument("--student-email", dest="student_email", default="mailpit.student@example.com")
        parser.add_argument("--teacher-email", dest="teacher_email", default="teacher@learning-hub.local")

    def handle(self, *args, **options):
        teacher = self._resolve_teacher(str(options.get("teacher_email") or "").strip())
        course_start = datetime.combine(date.today() - timedelta(days=1), time(18, 0)).replace(
            tzinfo=ZoneInfo("Europe/Berlin")
        )
        course = OnlineCourse.objects.update_or_create(
            slug=COURSE_SLUG,
            defaults={
                "title_de": COURSE_TITLE,
                "title_en": COURSE_TITLE,
                "short_description_de": COURSE_SHORT_DESCRIPTION,
                "short_description_en": COURSE_SHORT_DESCRIPTION,
                "description_de": COURSE_DESCRIPTION,
                "description_en": COURSE_DESCRIPTION,
                "lessons_count": 1,
                "trial_available": False,
                "price_amount": Decimal("0.00"),
                "currency": "EUR",
                "is_subscription": False,
                "is_published": True,
                "lifecycle_status": OnlineCourse.LIFECYCLE_PUBLISHED,
                "provider_type": OnlineCourse.PROVIDER_INTERNAL,
                "course_origin": OnlineCourse.ORIGIN_INTERNAL_AUTHORED,
                "course_type": OnlineCourse.COURSE_TYPE_INTERACTIVE,
                "delivery_model": OnlineCourse.DELIVERY_HYBRID,
                "difficulty_level": OnlineCourse.DIFFICULTY_INTERMEDIATE,
                "confidentiality_level": OnlineCourse.CONFIDENTIALITY_INTERNAL,
                "knowledge_domain": "Financial analytics",
                "target_audience": "Learners who need a reviewable Jupyter workflow for time-series modeling",
                "estimated_duration_minutes": 55,
                "average_rating": Decimal("4.80"),
                "ratings_count": 12,
                "is_mandatory": False,
                "is_recommended": True,
                "provider_course_id": NOTEBOOK_ASSIGNMENT_CODE,
                "external_url": "",
                "tags": ["bitcoin", "time-series", "forecasting", "jupyterlab", "risk-awareness"],
                "skills": ["pandas", "feature engineering", "validation discipline", "forecast interpretation"],
                "metadata_json": {
                    "labMode": "jupyter",
                    "datasetType": "local_snapshot",
                    "demoScenario": "bitcoin_case",
                },
                "custom_fields": {
                    "caseStudy": "Bitcoin",
                    "validationStyle": "time_based",
                },
                "required_completion_percent": 100,
                "required_attendance_percent": 0,
                "requires_attestation": False,
                "hero_image_url": COURSE_HERO_IMAGE_URL,
                "seo_title_de": COURSE_TITLE,
                "seo_title_en": COURSE_TITLE,
                "seo_description_de": COURSE_SHORT_DESCRIPTION,
                "seo_description_en": COURSE_SHORT_DESCRIPTION,
                "geo_city": "Berlin",
                "geo_country": "DE",
                "starts_at": course_start,
                "ends_at": course_start + timedelta(days=14),
            },
        )[0]

        notebook_content = self._upsert_training_content(course=course)
        notebook_library_item = sync_course_library_for_notebook_content(content_item=notebook_content)

        upsert_course_structure(course, modules_data=self._build_modules_payload(notebook_library_item=notebook_library_item))
        self._upsert_materials(course=course)

        cohort = OnlineCohort.objects.update_or_create(
            group_code="BTC_FORECAST_G1",
            defaults={
                "course": course,
                "teacher": teacher,
                "name": f"{COURSE_TITLE} - Group 1",
                "capacity": 30,
                "timezone": "Europe/Berlin",
                "start_date": date.today() - timedelta(days=1),
                "end_date": date.today() + timedelta(days=27),
                "status": OnlineCohort.STATUS_OPEN,
                "is_public": True,
            },
        )[0]
        self._upsert_session(cohort=cohort, lesson_title=LESSON_TITLE, lesson_description=LESSON_DESCRIPTION)
        sync_course_instructor_assignments(course=course, teacher_ids=[teacher.id] if teacher else [])
        sync_course_workspace_placements(
            course=course,
            workspace_ids=self._resolve_workspace_ids(),
            linked_cohort=cohort,
        )
        self._enroll_student_if_present(course=course, cohort=cohort, student_email=str(options.get("student_email") or "").strip())

        self.stdout.write(self.style.SUCCESS(f"Jupyter mini-course ready: {course.slug}"))

    def _resolve_teacher(self, teacher_email: str) -> Lehrer | None:
        if teacher_email:
            teacher = Lehrer.objects.select_related("user").filter(user__email__iexact=teacher_email).first()
            if teacher is not None:
                return teacher
        return Lehrer.objects.select_related("user").order_by("id").first()

    def _upsert_training_content(self, *, course: OnlineCourse) -> TrainingContentItem:
        content_item = TrainingContentItem.objects.update_or_create(
            slug=NOTEBOOK_CONTENT_SLUG,
            defaults={
                "name": "Bitcoin forecasting notebook lab",
                "description": "JupyterLab practice for a time-aware Bitcoin forecasting workflow.",
                "body_markdown": PRACTICE_MARKDOWN,
                "content_kind": TrainingContentItem.ContentKind.NOTEBOOK,
                "status": TrainingContentItem.Status.PUBLISHED,
                "access_scope": TrainingContentItem.AccessScope.AUTHENTICATED,
                "difficulty": TrainingContentItem.Difficulty.INTERMEDIATE,
                "course": course,
                "source_url": "",
                "estimated_minutes": 35,
                "is_repeatable_on_demand": True,
                "supports_inline_lab": True,
                "search_keywords": "bitcoin, jupyterlab, time series, forecasting, leakage, baseline",
                "published_at": timezone.now(),
            },
        )[0]

        stored_notebook = store_runtime_notebook_text(
            content_slug=content_item.slug,
            filename=NOTEBOOK_FILENAME,
            text=json.dumps(bitcoin_case_starter_notebook(), ensure_ascii=False, indent=2),
        )
        self._write_runtime_dataset_file(content_slug=content_item.slug)
        lab_profile, _created = TrainingNotebookLabProfile.objects.update_or_create(
            content_item=content_item,
            defaults={
                "runtime_backend": TrainingNotebookLabProfile.RuntimeBackend.JUPYTERHUB,
                "grader_backend": TrainingNotebookLabProfile.GraderBackend.CUSTOM,
                "runtime_image": "",
                "notebook_path": stored_notebook.notebook_path,
                "launch_path": f"/lab/tree/{stored_notebook.notebook_path}",
                "assignment_code": NOTEBOOK_ASSIGNMENT_CODE,
                "pass_threshold_percent": 70,
                "max_attempts": 5,
                "grader_config": NOTEBOOK_GRADER_CONFIG,
                "allow_gpu": False,
                "allow_network": False,
                "max_session_minutes": 120,
                "is_active": True,
            },
        )
        lab_profile.hints.all().delete()
        TrainingNotebookLabHint.objects.bulk_create(
            [
                TrainingNotebookLabHint(
                    lab_profile=lab_profile,
                    title=str(hint["title"]),
                    body_markdown=str(hint["bodyMarkdown"]),
                    availability_mode=str(hint["availabilityMode"]),
                    min_attempt_number=int(hint["minAttemptNumber"]),
                    max_score_percent=int(hint["maxScorePercent"]),
                    sort_order=int(hint["sortOrder"]),
                    is_active=True,
                )
                for hint in NOTEBOOK_HINTS
            ]
        )
        ensure_training_content_indexed(content_item)
        return content_item

    def _write_runtime_dataset_file(self, *, content_slug: str) -> None:
        runtime_dir = (runtime_content_root() / "labs" / content_slug).resolve()
        runtime_dir.mkdir(parents=True, exist_ok=True)
        dataset_path = (runtime_dir / "btc_usd_daily.csv").resolve()
        dataset_path.write_text(BTC_USD_DAILY_DATASET_CSV + "\n", encoding="utf-8")

    def _build_modules_payload(self, *, notebook_library_item) -> list[dict]:
        lesson_start = datetime.combine(date.today() - timedelta(days=1), time(18, 0)).replace(
            tzinfo=ZoneInfo("Europe/Berlin")
        )
        lesson_end = lesson_start + timedelta(hours=2)
        return [
            {
                "title": MODULE_TITLE,
                "description": MODULE_DESCRIPTION,
                "moduleType": "module",
                "weekNumber": 1,
                "startsAt": lesson_start,
                "endsAt": lesson_start + timedelta(days=7),
                "sortOrder": 10,
                "isActive": True,
                "lessons": [
                    {
                        "title": LESSON_TITLE,
                        "description": LESSON_DESCRIPTION,
                        "startsAt": lesson_start,
                        "endsAt": lesson_end,
                        "sortOrder": 1,
                        "isActive": True,
                        "sections": [
                            {
                                "sectionType": "introduction",
                                "title": "Introduction",
                                "description": "Orientation and lesson objectives.",
                                "sortOrder": 10,
                                "isActive": True,
                                "items": [
                                    {
                                        "title": "Theory overview",
                                        "description": "Context, scope, and why the lesson matters.",
                                        "assetType": "text",
                                        "activityType": "text",
                                        "language": "en",
                                        "bodyMarkdown": THEORY_MARKDOWN,
                                        "externalUrl": "",
                                        "sortOrder": 1,
                                        "isActive": True,
                                    }
                                ],
                            },
                            {
                                "sectionType": "main",
                                "title": "Main content",
                                "description": "Concept notes, walkthrough, quiz, and notebook lab.",
                                "sortOrder": 20,
                                "isActive": True,
                                "items": [
                                    {
                                        "title": "Concept notes",
                                        "description": "Why leakage, baselines, and interpretation matter in a forecasting workflow.",
                                        "assetType": "text",
                                        "activityType": "text",
                                        "language": "en",
                                        "bodyMarkdown": CONCEPT_MARKDOWN,
                                        "externalUrl": "",
                                        "sortOrder": 1,
                                        "isActive": True,
                                    },
                                    {
                                        "title": "Walkthrough video",
                                        "description": "Short Python and notebook refresher before the forecasting lab.",
                                        "assetType": "link",
                                        "activityType": "video",
                                        "language": "en",
                                        "bodyMarkdown": (
                                            "Use this short refresher to align on notebook workflow, pandas basics, and reproducible delivery habits "
                                            "before you launch the JupyterLab step."
                                        ),
                                        "externalUrl": VIDEO_URL,
                                        "sortOrder": 2,
                                        "isActive": True,
                                    },
                                    {
                                        "title": "Knowledge check",
                                        "description": "Quick checkpoint before the notebook opens.",
                                        "assetType": "text",
                                        "activityType": "quiz",
                                        "language": "en",
                                        "bodyMarkdown": "Check the main controls before moving into JupyterLab.",
                                        "structuredData": QUIZ_PAYLOAD,
                                        "externalUrl": "",
                                        "sortOrder": 3,
                                        "isActive": True,
                                    },
                                    {
                                        "sourceLibraryItem": notebook_library_item.id if notebook_library_item else None,
                                        "title": "Bitcoin forecasting notebook",
                                        "description": "Hands-on JupyterLab assignment with a local BTC dataset snapshot.",
                                        "assetType": "notebook",
                                        "activityType": "assignment",
                                        "language": "en",
                                        "bodyMarkdown": PRACTICE_MARKDOWN,
                                        "externalUrl": notebook_library_item.external_url if notebook_library_item else "",
                                        "linkedTrainingContentId": notebook_library_item.training_content_id if notebook_library_item else None,
                                        "sortOrder": 4,
                                        "isActive": True,
                                    },
                                ],
                            },
                            {
                                "sectionType": "conclusion",
                                "title": "Conclusion",
                                "description": "Risk note and next step.",
                                "sortOrder": 30,
                                "isActive": True,
                                "items": [
                                    {
                                        "title": "Summary and limitations",
                                        "description": "Close the lesson with model-risk framing.",
                                        "assetType": "text",
                                        "activityType": "text",
                                        "language": "en",
                                        "bodyMarkdown": SUMMARY_MARKDOWN,
                                        "externalUrl": "",
                                        "sortOrder": 1,
                                        "isActive": True,
                                    }
                                ],
                            },
                        ],
                    }
                ],
            }
        ]

    def _upsert_materials(self, *, course: OnlineCourse) -> None:
        OnlineCourseMaterial.objects.update_or_create(
            course=course,
            title="Dataset and workflow note",
            language=OnlineCourse.LOCALE_EN,
            material_type=OnlineCourseMaterial.MATERIAL_RESOURCE,
            defaults={
                "description": "Fixed BTC/USD snapshot and notebook workflow notes for reproducible forecasting practice.",
                "link_url": "",
                "sort_order": 10,
                "is_active": True,
            },
        )
        OnlineCourseMaterial.objects.update_or_create(
            course=course,
            title="Model-risk note",
            language=OnlineCourse.LOCALE_EN,
            material_type=OnlineCourseMaterial.MATERIAL_CONDITION,
            defaults={
                "description": "The notebook is educational only and should not be treated as investment advice.",
                "link_url": "",
                "sort_order": 20,
                "is_active": True,
            },
        )
        OnlineCourseMaterial.objects.update_or_create(
            course=course,
            title="Walkthrough recording",
            language=OnlineCourse.LOCALE_EN,
            material_type=OnlineCourseMaterial.MATERIAL_RECORDING,
            defaults={
                "description": "Notebook workflow refresher linked from the video step.",
                "link_url": VIDEO_URL,
                "sort_order": 30,
                "is_active": True,
            },
        )

    def _upsert_session(self, *, cohort: OnlineCohort, lesson_title: str, lesson_description: str) -> None:
        starts_at = datetime.combine(date.today() - timedelta(days=1), time(18, 0)).replace(
            tzinfo=ZoneInfo("Europe/Berlin")
        )
        OnlineSession.objects.update_or_create(
            cohort=cohort,
            sort_order=1,
            defaults={
                "title": lesson_title,
                "description": lesson_description,
                "starts_at": starts_at,
                "ends_at": starts_at + timedelta(hours=2),
                "status": OnlineSession.STATUS_SCHEDULED,
                "join_url": "https://teams.microsoft.com/",
                "recording_url": VIDEO_URL,
                "is_completed": False,
            },
        )

    def _resolve_workspace_ids(self) -> list[int]:
        requested_slugs = ("berlin", "finance")
        workspace_ids = list(
            OnlineWorkspace.objects.filter(slug__in=requested_slugs, is_published=True)
            .order_by("sort_order", "id")
            .values_list("id", flat=True)
        )
        if workspace_ids:
            return workspace_ids
        fallback = (
            OnlineWorkspace.objects.filter(is_published=True)
            .order_by("sort_order", "id")
            .values_list("id", flat=True)
            .first()
        )
        return [fallback] if fallback else []

    def _enroll_student_if_present(self, *, course: OnlineCourse, cohort: OnlineCohort, student_email: str) -> None:
        if not student_email:
            return
        user = User.objects.filter(email__iexact=student_email).first()
        if user is None:
            return
        profile, _created = OnlineStudentProfile.objects.get_or_create(
            user=user,
            defaults={
                "first_name": user.first_name or "Demo",
                "last_name": user.last_name or "Student",
                "preferred_language": OnlineCourse.LOCALE_EN,
            },
        )
        OnlineEnrollment.objects.update_or_create(
            profile=profile,
            course=course,
            cohort=cohort,
            defaults={"status": OnlineEnrollment.STATUS_ACTIVE},
        )
