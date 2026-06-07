from __future__ import annotations

from typing import Any

from django.contrib.contenttypes.models import ContentType
from django.db.models import Q

from apps.online.models import (
    OnlineCatalogAttributeDefinition,
    OnlineCatalogAttributeValue,
    OnlineCourse,
    OnlineInstructorProfile,
    OnlineKnowledgeDocument,
    OnlineLearningProgram,
    OnlineLearningProgramCourse,
    OnlineStudentProfile,
)


CATALOG_ENTITY_MODEL_MAP: dict[str, type] = {
    OnlineCatalogAttributeDefinition.ENTITY_COURSE: OnlineCourse,
    OnlineCatalogAttributeDefinition.ENTITY_STUDENT: OnlineStudentProfile,
    OnlineCatalogAttributeDefinition.ENTITY_INSTRUCTOR: OnlineInstructorProfile,
    OnlineCatalogAttributeDefinition.ENTITY_PROGRAM: OnlineLearningProgram,
    OnlineCatalogAttributeDefinition.ENTITY_KNOWLEDGE: OnlineKnowledgeDocument,
}


def resolve_catalog_entity_model(entity_type: str):
    return CATALOG_ENTITY_MODEL_MAP.get(entity_type)


def resolve_catalog_content_type(entity_type: str) -> ContentType:
    model = resolve_catalog_entity_model(entity_type)
    if model is None:
        raise ValueError("Unsupported entity type.")
    return ContentType.objects.get_for_model(model)


def sync_program_courses(*, program: OnlineLearningProgram, items_data: list[dict[str, Any]]) -> list[OnlineLearningProgramCourse]:
    existing_items = {item.id: item for item in program.program_courses.all()}
    kept_ids: list[int] = []
    synced_items: list[OnlineLearningProgramCourse] = []

    for index, item_data in enumerate(items_data, start=1):
        item = existing_items.get(item_data.get("id"))
        if item is None:
            item = OnlineLearningProgramCourse(program=program)
        item.course_id = item_data.get("course_id") or item_data.get("courseId")
        item.sort_order = item_data.get("sort_order") or item_data.get("sortOrder") or index * 10
        item.is_required = item_data.get("is_required", item_data.get("isRequired", True))
        item.unlock_rule = item_data.get("unlock_rule") or item_data.get("unlockRule") or OnlineLearningProgramCourse.UNLOCK_IMMEDIATE
        item.min_completion_percent = item_data.get(
            "min_completion_percent",
            item_data.get("minCompletionPercent", 0),
        ) or 0
        item.note = item_data.get("note", "")
        item.save()
        kept_ids.append(item.id)
        synced_items.append(item)

    program.program_courses.exclude(id__in=kept_ids).delete()
    return synced_items


def attribute_value_payload(value: OnlineCatalogAttributeValue) -> dict[str, Any]:
    return {
        "id": value.id,
        "definitionId": value.definition_id,
        "definitionSlug": value.definition.slug,
        "entityType": value.definition.entity_type,
        "objectId": value.object_id,
        "valueJson": value.value_json,
        "updatedAt": value.updated_at,
    }


def build_admin_catalog_search_payload(
    *,
    query: str = "",
    confidentiality_level: str = "",
    provider_type: str = "",
    course_type: str = "",
    difficulty_level: str = "",
    knowledge_domain: str = "",
    rating_min: float | None = None,
) -> dict[str, Any]:
    normalized_query = (query or "").strip().lower()
    courses_queryset = OnlineCourse.objects.all().order_by("title_en", "id")
    if confidentiality_level:
        courses_queryset = courses_queryset.filter(confidentiality_level=confidentiality_level)
    if provider_type:
        courses_queryset = courses_queryset.filter(provider_type=provider_type)
    if course_type:
        courses_queryset = courses_queryset.filter(course_type=course_type)
    if difficulty_level:
        courses_queryset = courses_queryset.filter(difficulty_level=difficulty_level)
    if knowledge_domain:
        courses_queryset = courses_queryset.filter(knowledge_domain__icontains=knowledge_domain)
    if rating_min is not None:
        courses_queryset = courses_queryset.filter(average_rating__gte=rating_min)
    if normalized_query:
        courses_queryset = courses_queryset.filter(
            Q(slug__icontains=normalized_query)
            | Q(title_de__icontains=normalized_query)
            | Q(title_en__icontains=normalized_query)
            | Q(short_description_de__icontains=normalized_query)
            | Q(short_description_en__icontains=normalized_query)
            | Q(description_de__icontains=normalized_query)
            | Q(description_en__icontains=normalized_query)
            | Q(knowledge_domain__icontains=normalized_query)
            | Q(target_audience__icontains=normalized_query)
            | Q(provider_course_id__icontains=normalized_query)
            | Q(external_url__icontains=normalized_query)
        ).distinct()

    courses = []
    for course in courses_queryset[:40]:
        if normalized_query and normalized_query not in " ".join(
            [
                course.slug.lower(),
                course.title_de.lower(),
                course.title_en.lower(),
                course.knowledge_domain.lower(),
                course.target_audience.lower(),
                " ".join(str(item).lower() for item in course.tags or []),
                " ".join(str(item).lower() for item in course.skills or []),
            ]
        ):
            continue
        courses.append(
            {
                "id": course.id,
                "slug": course.slug,
                "title": course.title_en or course.title_de,
                "providerType": course.provider_type,
                "courseType": course.course_type,
                "deliveryModel": course.delivery_model,
                "difficultyLevel": course.difficulty_level,
                "confidentialityLevel": course.confidentiality_level,
                "knowledgeDomain": course.knowledge_domain,
                "rating": float(course.average_rating),
                "estimatedDurationMinutes": course.estimated_duration_minutes,
                "isMandatory": course.is_mandatory,
                "isRecommended": course.is_recommended,
            }
        )

    students_queryset = OnlineStudentProfile.objects.select_related("user").order_by(
        "last_name",
        "first_name",
        "id",
    )
    if normalized_query:
        students_queryset = students_queryset.filter(
            Q(first_name__icontains=normalized_query)
            | Q(last_name__icontains=normalized_query)
            | Q(user__email__icontains=normalized_query)
            | Q(employee_id__icontains=normalized_query)
            | Q(department__icontains=normalized_query)
            | Q(team_name__icontains=normalized_query)
            | Q(job_title__icontains=normalized_query)
        )
    students = [
        {
            "id": profile.id,
            "fullName": f"{profile.first_name} {profile.last_name}".strip(),
            "email": profile.user.email,
            "department": profile.department,
            "teamName": profile.team_name,
            "jobTitle": profile.job_title,
            "employmentStatus": profile.employment_status,
        }
        for profile in students_queryset[:25]
    ]

    instructors_queryset = OnlineInstructorProfile.objects.select_related("teacher", "teacher__user").order_by(
        "teacher__Nachname",
        "teacher__Vorname",
        "id",
    )
    if normalized_query:
        instructors_queryset = instructors_queryset.filter(
            Q(teacher__Vorname__icontains=normalized_query)
            | Q(teacher__Nachname__icontains=normalized_query)
            | Q(teacher__Schule_Email__icontains=normalized_query)
            | Q(job_title__icontains=normalized_query)
            | Q(department__icontains=normalized_query)
            | Q(bio__icontains=normalized_query)
        )
    instructors = [
        {
            "id": profile.id,
            "teacherId": profile.teacher_id,
            "fullName": f"{profile.teacher.Vorname} {profile.teacher.Nachname}".strip(),
            "email": profile.teacher.Schule_Email,
            "department": profile.department,
            "jobTitle": profile.job_title,
            "expertiseAreas": profile.expertise_areas,
            "canAuthor": profile.can_author,
        }
        for profile in instructors_queryset[:25]
    ]

    knowledge_queryset = OnlineKnowledgeDocument.objects.select_related("source", "source__linked_course").order_by("title", "id")
    if normalized_query:
        knowledge_queryset = knowledge_queryset.filter(
            Q(title__icontains=normalized_query)
            | Q(description__icontains=normalized_query)
            | Q(body_markdown__icontains=normalized_query)
            | Q(transcript_text__icontains=normalized_query)
            | Q(source__title__icontains=normalized_query)
            | Q(source__external_url__icontains=normalized_query)
        )
    knowledge_documents = [
        {
            "id": document.id,
            "title": document.title,
            "sourceTitle": document.source.title,
            "documentType": document.document_type,
            "linkedCourseTitle": document.source.linked_course.title_en if document.source.linked_course else "",
            "isActive": document.is_active,
            "indexedAt": document.indexed_at,
        }
        for document in knowledge_queryset[:25]
    ]

    programs_queryset = OnlineLearningProgram.objects.all().order_by("title", "id")
    if normalized_query:
        programs_queryset = programs_queryset.filter(
            Q(title__icontains=normalized_query)
            | Q(description__icontains=normalized_query)
            | Q(target_audience__icontains=normalized_query)
        )
    programs = [
        {
            "id": program.id,
            "slug": program.slug,
            "title": program.title,
            "assignmentMode": program.assignment_mode,
            "targetAudience": program.target_audience,
            "coursesCount": program.program_courses.count(),
        }
        for program in programs_queryset[:25]
    ]

    return {
        "courses": courses,
        "students": students,
        "instructors": instructors,
        "knowledgeDocuments": knowledge_documents,
        "programs": programs,
    }
