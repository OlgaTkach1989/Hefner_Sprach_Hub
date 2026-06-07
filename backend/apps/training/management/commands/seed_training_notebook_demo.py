from __future__ import annotations

import json
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.employees.models import Lehrer
from apps.online.models import (
    OnlineCohort,
    OnlineCourse,
    OnlineCourseContentLibraryItem,
    OnlineCourseLesson,
    OnlineCourseLessonSection,
    OnlineCourseLessonSectionItem,
    OnlineCourseMaterial,
    OnlineEnrollment,
    OnlineSession,
    OnlineStudentProfile,
)
from apps.online.services.course_structure import ensure_lesson_sections
from apps.training.demo_notebook_specs import finance_demo_assignment_specs
from apps.training.models import (
    TrainingAssetClass,
    TrainingAudience,
    TrainingContentAudiencePolicy,
    TrainingContentItem,
    TrainingNotebookLabHint,
    TrainingNotebookLabProfile,
    TrainingTopic,
)
from apps.training.services.knowledge_base import ensure_training_content_indexed
from apps.training.services.notebook_assignments import sync_course_library_for_notebook_content
from apps.training.services.notebook_storage import store_runtime_notebook_text

User = get_user_model()


class Command(BaseCommand):
    help = "Seed a finance-oriented Jupyter notebook demo course with hints, grading config, and structured lessons."

    def add_arguments(self, parser):
        parser.add_argument("--student-email", dest="student_email", default="mailpit.student@example.com")
        parser.add_argument("--teacher-email", dest="teacher_email", default="teacher@learning-hub.local")

    def handle(self, *args, **options):
        course, _created = OnlineCourse.objects.update_or_create(
            slug="quant-finance-jupyter-labs",
            defaults={
                "title_de": "Quant Finance Jupyter Labs",
                "title_en": "Quant Finance Jupyter Labs",
                "short_description_de": "Finance notebook demo course",
                "short_description_en": "Finance notebook demo course",
                "description_de": "Interaktive Notebook-Reihe fuer CVA, Duration und FX-Forward-Pricing.",
                "description_en": "Interactive notebook track for CVA, duration, and FX forward pricing.",
                "lessons_count": 3,
                "trial_available": False,
                "price_amount": Decimal("0.00"),
                "currency": "EUR",
                "is_subscription": False,
            },
        )

        teacher = None
        teacher_email = str(options.get("teacher_email") or "").strip()
        if teacher_email:
            teacher = Lehrer.objects.filter(user__email__iexact=teacher_email).first()

        cohort_defaults = {
            "course": course,
            "teacher": teacher,
            "name": "Quant Finance Labs Cohort",
            "capacity": 40,
            "timezone": "Europe/Berlin",
            "status": OnlineCohort.STATUS_OPEN,
            "is_public": False,
        }
        cohort, _ = OnlineCohort.objects.update_or_create(
            group_code="QFL-1",
            defaults=cohort_defaults,
        )

        self._upsert_demo_roles()
        lesson_specs = finance_demo_assignment_specs()
        lesson_rows: list[OnlineCourseLesson] = []
        berlin_tz = ZoneInfo("Europe/Berlin")
        start_date = date.today() + timedelta(days=3)

        for index, spec in enumerate(lesson_specs, start=1):
            asset_class, _ = TrainingAssetClass.objects.get_or_create(
                slug=spec.asset_class_slug,
                defaults={"name": spec.asset_class_name},
            )
            topic, _ = TrainingTopic.objects.get_or_create(
                slug=spec.topic_slug,
                defaults={"name": spec.topic_name},
            )
            content_item = TrainingContentItem.objects.update_or_create(
                slug=spec.slug,
                defaults={
                    "name": spec.name,
                    "description": spec.description,
                    "body_markdown": spec.body_markdown,
                    "content_kind": TrainingContentItem.ContentKind.NOTEBOOK,
                    "status": TrainingContentItem.Status.PUBLISHED,
                    "access_scope": TrainingContentItem.AccessScope.ENTITLED,
                    "difficulty": TrainingContentItem.Difficulty.INTERMEDIATE,
                    "course": course,
                    "estimated_minutes": 25,
                    "is_repeatable_on_demand": True,
                    "supports_inline_lab": True,
                },
            )[0]
            content_item.asset_classes.set([asset_class])
            content_item.topics.set([topic])
            audience_ids = self._resolve_audience_ids_for_assignment(index=index)
            content_item.audience_policies.all().delete()
            TrainingContentAudiencePolicy.objects.bulk_create(
                [TrainingContentAudiencePolicy(content_item=content_item, audience_id=audience_id) for audience_id in audience_ids]
            )

            stored_notebook = store_runtime_notebook_text(
                content_slug=content_item.slug,
                filename=spec.notebook_filename,
                text=json.dumps(spec.starter_notebook, ensure_ascii=False, indent=2),
            )
            lab_profile, _ = TrainingNotebookLabProfile.objects.update_or_create(
                content_item=content_item,
                defaults={
                    "runtime_backend": TrainingNotebookLabProfile.RuntimeBackend.JUPYTERHUB,
                    "grader_backend": TrainingNotebookLabProfile.GraderBackend.CUSTOM,
                    "runtime_image": "",
                    "notebook_path": stored_notebook.notebook_path,
                    "launch_path": f"/lab/tree/{stored_notebook.notebook_path}",
                    "assignment_code": spec.assignment_code,
                    "pass_threshold_percent": 70,
                    "max_attempts": 5,
                    "grader_config": spec.grader_config,
                    "is_active": True,
                },
            )
            lab_profile.hints.all().delete()
            TrainingNotebookLabHint.objects.bulk_create(
                [
                    TrainingNotebookLabHint(
                        lab_profile=lab_profile,
                        title=hint["title"],
                        body_markdown=hint["bodyMarkdown"],
                        availability_mode=hint["availabilityMode"],
                        min_attempt_number=hint["minAttemptNumber"],
                        max_score_percent=hint["maxScorePercent"],
                        sort_order=hint["sortOrder"],
                        is_active=True,
                    )
                    for hint in spec.hints
                ]
            )
            ensure_training_content_indexed(content_item)
            library_item = sync_course_library_for_notebook_content(content_item=content_item)
            lesson_rows.append(
                self._upsert_lesson_structure(
                    course=course,
                    spec=spec,
                    lesson_index=index,
                    library_item=library_item,
                    linked_content=content_item,
                )
            )

        self._upsert_course_material(course)
        self._upsert_sessions(cohort=cohort, lessons=lesson_rows, timezone=berlin_tz, start_date=start_date)
        self._enroll_student_if_present(course=course, cohort=cohort, student_email=str(options.get("student_email") or "").strip())

        self.stdout.write(self.style.SUCCESS(f"Notebook demo course ready: {course.slug}"))

    def _resolve_audience_ids_for_assignment(self, *, index: int) -> list[int]:
        audience_slugs = {
            1: ["lateral-transfers"],
            2: ["interns-new-grads"],
            3: ["external-users"],
        }.get(index, ["external-users"])
        audience_ids = list(
            TrainingAudience.objects.filter(slug__in=audience_slugs).values_list("id", flat=True)
        )
        return audience_ids

    def _upsert_demo_roles(self) -> None:
        role_rows = (
            {
                "slug": "external-users",
                "name": "Guest access",
                "short_label": "Guest",
                "audience_type": TrainingAudience.AudienceType.DEMO_ROLE,
                "privilege_rank": 10,
                "is_internal": False,
                "description": "Guest viewers and trial users with the most limited academy access.",
            },
            {
                "slug": "interns-new-grads",
                "name": "Student access",
                "short_label": "Student",
                "audience_type": TrainingAudience.AudienceType.DEMO_ROLE,
                "privilege_rank": 20,
                "is_internal": True,
                "description": "Learners progressing through assigned lessons, quizzes, and practice labs.",
            },
            {
                "slug": "lateral-transfers",
                "name": "Instructor access",
                "short_label": "Instructor",
                "audience_type": TrainingAudience.AudienceType.DEMO_ROLE,
                "privilege_rank": 30,
                "is_internal": True,
                "description": "Instructors and cohort managers who deliver lessons and review learner progress.",
            },
            {
                "slug": "traders-structurizers",
                "name": "Admin access",
                "short_label": "Admin",
                "audience_type": TrainingAudience.AudienceType.DEMO_ROLE,
                "privilege_rank": 40,
                "is_internal": True,
                "description": "Administrators with full academy operations access and advanced content visibility.",
            },
        )
        for row in role_rows:
            TrainingAudience.objects.update_or_create(slug=row["slug"], defaults=row)

    def _upsert_lesson_structure(
        self,
        *,
        course: OnlineCourse,
        spec,
        lesson_index: int,
        library_item: OnlineCourseContentLibraryItem | None,
        linked_content: TrainingContentItem,
    ) -> OnlineCourseLesson:
        lesson, _ = OnlineCourseLesson.objects.update_or_create(
            course=course,
            sort_order=lesson_index * 10,
            defaults={
                "title": spec.lesson_title,
                "description": spec.lesson_description,
                "is_active": True,
            },
        )
        ensure_lesson_sections(lesson)
        intro_section = lesson.sections.get(section_type=OnlineCourseLessonSection.SECTION_INTRODUCTION)
        main_section = lesson.sections.get(section_type=OnlineCourseLessonSection.SECTION_MAIN)
        conclusion_section = lesson.sections.get(section_type=OnlineCourseLessonSection.SECTION_CONCLUSION)
        intro_section.title = spec.introduction_title
        intro_section.description = "Context and prerequisites"
        intro_section.save(update_fields=["title", "description", "updated_at"])
        main_section.title = "Notebook assignment"
        main_section.description = "Hands-on lab"
        main_section.save(update_fields=["title", "description", "updated_at"])
        conclusion_section.title = spec.conclusion_title
        conclusion_section.description = "Recap and next steps"
        conclusion_section.save(update_fields=["title", "description", "updated_at"])

        self._upsert_section_item(
            section=intro_section,
            sort_order=10,
            title=spec.introduction_title,
            description="Lesson introduction",
            asset_type=OnlineCourseLessonSectionItem.ASSET_TEXT,
            body_markdown=spec.introduction_body,
        )
        self._upsert_section_item(
            section=main_section,
            sort_order=10,
            title=spec.name,
            description=spec.description,
            asset_type=OnlineCourseLessonSectionItem.ASSET_NOTEBOOK,
            linked_training_content=linked_content,
            source_library_item=library_item,
        )
        self._upsert_section_item(
            section=conclusion_section,
            sort_order=10,
            title=spec.conclusion_title,
            description="Lesson conclusion",
            asset_type=OnlineCourseLessonSectionItem.ASSET_TEXT,
            body_markdown=spec.conclusion_body,
        )
        return lesson

    def _upsert_section_item(
        self,
        *,
        section: OnlineCourseLessonSection,
        sort_order: int,
        title: str,
        description: str,
        asset_type: str,
        body_markdown: str = "",
        linked_training_content: TrainingContentItem | None = None,
        source_library_item: OnlineCourseContentLibraryItem | None = None,
    ) -> None:
        OnlineCourseLessonSectionItem.objects.update_or_create(
            section=section,
            sort_order=sort_order,
            defaults={
                "title": title,
                "description": description,
                "asset_type": asset_type,
                "language": OnlineCourse.LOCALE_EN,
                "body_markdown": body_markdown,
                "linked_training_content": linked_training_content,
                "source_library_item": source_library_item,
                "is_active": True,
            },
        )

    def _upsert_course_material(self, course: OnlineCourse) -> None:
        OnlineCourseMaterial.objects.update_or_create(
            course=course,
            title="Quant notebook handbook",
            language=OnlineCourse.LOCALE_EN,
            material_type=OnlineCourseMaterial.MATERIAL_RESOURCE,
            defaults={
                "description": "Course guide for notebook delivery, submission expectations, and escalation workflow.",
                "link_url": "",
                "sort_order": 1,
                "is_active": True,
            },
        )

    def _upsert_sessions(
        self,
        *,
        cohort: OnlineCohort,
        lessons: list[OnlineCourseLesson],
        timezone: ZoneInfo,
        start_date: date,
    ) -> None:
        for index, lesson in enumerate(lessons, start=1):
            starts_at = datetime.combine(start_date + timedelta(days=(index - 1) * 7), time(18, 0)).replace(tzinfo=timezone)
            ends_at = starts_at + timedelta(hours=2)
            OnlineSession.objects.update_or_create(
                cohort=cohort,
                sort_order=index,
                defaults={
                    "title": lesson.title,
                    "description": lesson.description,
                    "starts_at": starts_at,
                    "ends_at": ends_at,
                    "status": OnlineSession.STATUS_SCHEDULED,
                    "join_url": "https://teams.microsoft.com/",
                    "is_completed": False,
                },
            )

    def _enroll_student_if_present(self, *, course: OnlineCourse, cohort: OnlineCohort, student_email: str) -> None:
        if not student_email:
            return
        user = User.objects.filter(email__iexact=student_email).first()
        if user is None:
            return
        profile, _ = OnlineStudentProfile.objects.get_or_create(
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
