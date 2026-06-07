from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from django.core.files.base import File
from django.db.models import Prefetch
from django.utils import timezone

from apps.online.models import (
    OnlineCohort,
    OnlineCourse,
    OnlineCourseContentLibraryItem,
    OnlineCourseLesson,
    OnlineCourseModule,
    OnlineCourseLessonSection,
    OnlineCourseLessonSectionItem,
    OnlineCourseMaterial,
    OnlineCourseTemplate,
    OnlineCourseTemplateLesson,
    OnlineWorkspace,
    OnlineWorkspaceContentItem,
)
from apps.employees.models import Lehrer
from apps.online.services.access import (
    online_access_policy_audience_ids_for_instance,
    online_object_is_accessible_to_user,
    sync_online_access_policies_for_instance,
)
from apps.online.services.governance import build_course_governance_payload
from apps.online.services.interactive_lesson_overrides import apply_interactive_lesson_override
from apps.training.models import TrainingContentItem, TrainingCourseRoleAssignment
from apps.training.services.access import content_item_is_visible_to_user

SECTION_ORDER = {
    OnlineCourseLessonSection.SECTION_INTRODUCTION: 10,
    OnlineCourseLessonSection.SECTION_MAIN: 20,
    OnlineCourseLessonSection.SECTION_CONCLUSION: 30,
}

SECTION_DEFAULT_TITLES = {
    OnlineCourseLessonSection.SECTION_INTRODUCTION: "Introduction",
    OnlineCourseLessonSection.SECTION_MAIN: "Main content",
    OnlineCourseLessonSection.SECTION_CONCLUSION: "Conclusion",
}

ACTIVITY_TYPE_BY_ASSET_TYPE = {
    OnlineCourseLessonSectionItem.ASSET_LINK: OnlineCourseLessonSectionItem.ACTIVITY_VIDEO,
    OnlineCourseLessonSectionItem.ASSET_NOTEBOOK: OnlineCourseLessonSectionItem.ACTIVITY_ASSIGNMENT,
    OnlineCourseLessonSectionItem.ASSET_TEXT: OnlineCourseLessonSectionItem.ACTIVITY_TEXT,
    OnlineCourseLessonSectionItem.ASSET_DOCUMENT: OnlineCourseLessonSectionItem.ACTIVITY_TEXT,
}

DEFAULT_COURSE_TEMPLATES: tuple[dict[str, Any], ...] = (
    {
        "slug": "blank-structured-course",
        "title": "Blank structured course",
        "description": "A clean course shell with a single main content lesson flow.",
        "default_lessons_count": 1,
        "sort_order": 10,
        "lessons": (
            {
                "title": "Lesson 1",
                "description": "Foundation lesson shell.",
                "sort_order": 10,
            },
        ),
    },
    {
        "slug": "notebook-intensive-track",
        "title": "Notebook-intensive track",
        "description": "A practical course shape with hands-on main content and notebook-heavy delivery.",
        "default_lessons_count": 3,
        "sort_order": 20,
        "lessons": (
            {
                "title": "Orientation and environment setup",
                "description": "Introduce the topic, environment, and first notebook.",
                "sort_order": 10,
                "main_title": "Notebook walkthrough",
            },
            {
                "title": "Core quantitative workflow",
                "description": "Primary calculations, practical notebook steps, and review checkpoints.",
                "sort_order": 20,
                "main_title": "Core notebook and documents",
            },
            {
                "title": "Independent practice and recap",
                "description": "Wrap-up, recap, and self-study assignment.",
                "sort_order": 30,
                "conclusion_title": "Homework and next steps",
            },
        ),
    },
    {
        "slug": "recording-and-reading-track",
        "title": "Recording and reading track",
        "description": "A content-first course shape for documents, recordings, and guided reflection.",
        "default_lessons_count": 2,
        "sort_order": 30,
        "lessons": (
            {
                "title": "Guided orientation",
                "description": "Brief introduction, key documents, and supporting recording.",
                "sort_order": 10,
            },
            {
                "title": "Consolidation and follow-up",
                "description": "Main reading pack, recap, and independent follow-up.",
                "sort_order": 20,
            },
        ),
    },
)


def section_sort_order(section_type: str) -> int:
    return SECTION_ORDER.get(section_type, 999)


def section_default_title(section_type: str) -> str:
    return SECTION_DEFAULT_TITLES.get(section_type, section_type.title())


def ensure_lesson_sections(lesson: OnlineCourseLesson) -> None:
    existing_section_types = set(lesson.sections.values_list("section_type", flat=True))
    missing_section_types = [OnlineCourseLessonSection.SECTION_MAIN]
    for section_type in missing_section_types:
        if section_type in existing_section_types:
            continue
        OnlineCourseLessonSection.objects.create(
            lesson=lesson,
            section_type=section_type,
            title=section_default_title(section_type),
            description="",
            sort_order=section_sort_order(section_type),
            is_active=True,
        )


def ensure_course_modules(course: OnlineCourse) -> None:
    has_module = OnlineCourseModule.objects.filter(course=course, is_active=True).exists()
    if not has_module:
        OnlineCourseModule.objects.create(
            course=course,
            title="Module 1 (Week 1)",
            description="Default module for structured course delivery.",
            module_type=OnlineCourseModule.MODULE_TYPE_STANDARD,
            week_number=1,
            sort_order=10,
            is_active=True,
        )
    fallback_module = (
        OnlineCourseModule.objects.filter(course=course, is_active=True)
        .order_by("sort_order", "id")
        .first()
    )
    if fallback_module is None:
        return
    OnlineCourseLesson.objects.filter(course=course, module__isnull=True).update(module=fallback_module)


def ensure_default_course_templates() -> None:
    for template_data in DEFAULT_COURSE_TEMPLATES:
        if OnlineCourseTemplate.objects.filter(slug=template_data["slug"]).exists():
            continue
        lesson_rows = template_data["lessons"]
        template = OnlineCourseTemplate.objects.create(
            slug=template_data["slug"],
            title=template_data["title"],
            description=template_data["description"],
            default_lessons_count=template_data["default_lessons_count"],
            sort_order=template_data["sort_order"],
            is_active=True,
        )
        OnlineCourseTemplateLesson.objects.bulk_create(
            [
                OnlineCourseTemplateLesson(
                    template=template,
                    title=lesson["title"],
                    description=lesson["description"],
                    introduction_title=lesson.get("introduction_title", "Introduction"),
                    introduction_description=lesson.get("introduction_description", ""),
                    main_title=lesson.get("main_title", "Main content"),
                    main_description=lesson.get("main_description", ""),
                    conclusion_title=lesson.get("conclusion_title", "Conclusion"),
                    conclusion_description=lesson.get("conclusion_description", ""),
                    sort_order=lesson["sort_order"],
                )
                for lesson in lesson_rows
            ]
        )


def _structure_prefetch():
    item_queryset = (
        OnlineCourseLessonSectionItem.objects.select_related(
            "source_library_item",
            "linked_training_content",
        )
        .order_by("sort_order", "id")
    )
    section_queryset = (
        OnlineCourseLessonSection.objects.prefetch_related(
            Prefetch("items", queryset=item_queryset, to_attr="prefetched_items"),
        )
        .order_by("sort_order", "id")
    )
    lesson_queryset = (
        OnlineCourseLesson.objects.select_related("module")
        .prefetch_related(
            Prefetch("sections", queryset=section_queryset, to_attr="prefetched_sections"),
        )
        .order_by("module__sort_order", "module__id", "sort_order", "id")
    )
    module_queryset = (
        OnlineCourseModule.objects.prefetch_related(
            Prefetch("lessons", queryset=lesson_queryset, to_attr="prefetched_lessons"),
        )
        .order_by("sort_order", "id")
    )
    return (
        Prefetch("structured_lessons", queryset=lesson_queryset, to_attr="prefetched_lessons"),
        Prefetch("modules", queryset=module_queryset, to_attr="prefetched_modules"),
    )


def structured_course_queryset(course_ids: Iterable[int]):
    ids = list(dict.fromkeys(course_ids))
    if not ids:
        return OnlineCourse.objects.none()
    return OnlineCourse.objects.filter(id__in=ids).prefetch_related(*_structure_prefetch())


def _section_item_file_url(item: OnlineCourseLessonSectionItem, request=None) -> str:
    if not item.file_asset:
        return ""
    url = f"/api/online/media/course-section-items/{item.id}/file/"
    if request is not None:
        return request.build_absolute_uri(url)
    return url


def serialize_section_item(item: OnlineCourseLessonSectionItem, request=None) -> dict[str, Any]:
    file_url = _section_item_file_url(item, request=request)
    training_content = item.linked_training_content
    return {
        "id": item.id,
        "title": item.title,
        "description": item.description,
        "assetType": item.asset_type,
        "activityType": item.activity_type,
        "language": item.language,
        "bodyMarkdown": item.body_markdown,
        "structuredData": item.structured_data or {},
        "externalUrl": item.external_url,
        "fileUrl": file_url,
        "sortOrder": item.sort_order,
        "isActive": item.is_active,
        "trainingContent": (
            {
                "id": training_content.id,
                "slug": training_content.slug,
                "name": training_content.name,
                "contentKind": training_content.content_kind,
                "sourceUrl": training_content.source_url,
            }
            if training_content
            else None
        ),
        "sourceLibraryItemId": item.source_library_item_id,
        "audienceIds": online_access_policy_audience_ids_for_instance(item),
    }


def _preferred_course_title(course: OnlineCourse | None) -> str:
    if course is None:
        return ""
    return course.title_en or course.title_de or ""


def _section_item_link(item_payload: dict[str, Any]) -> str:
    training_content = item_payload.get("trainingContent") or {}
    return str(
        item_payload.get("externalUrl")
        or item_payload.get("fileUrl")
        or training_content.get("sourceUrl")
        or ""
    ).strip()


def _unique_text_rows(values: Iterable[str]) -> list[str]:
    rows: list[str] = []
    seen: set[str] = set()
    for raw_value in values:
        value = str(raw_value or "").strip()
        if not value:
            continue
        normalized = value.casefold()
        if normalized in seen:
            continue
        seen.add(normalized)
        rows.append(value)
    return rows


def _extract_markdown_bullets(body_markdown: str) -> list[str]:
    bullets: list[str] = []
    for row in str(body_markdown or "").splitlines():
        trimmed = row.strip()
        if trimmed.startswith("- "):
            bullets.append(trimmed[2:].strip())
    return _unique_text_rows(bullets)


def _normalize_quiz_options(raw_options: Iterable[Any]) -> list[dict[str, Any]]:
    options: list[dict[str, Any]] = []
    for index, raw_option in enumerate(raw_options, start=1):
        if isinstance(raw_option, dict):
            label = str(raw_option.get("label") or raw_option.get("text") or raw_option.get("value") or "").strip()
            option_id = str(raw_option.get("id") or f"option-{index}").strip() or f"option-{index}"
            is_correct = bool(
                raw_option.get("isCorrect")
                or raw_option.get("is_correct")
                or raw_option.get("correct")
            )
        else:
            label = str(raw_option or "").strip()
            option_id = f"option-{index}"
            is_correct = index == 1
        if not label:
            continue
        options.append(
            {
                "id": option_id,
                "label": label,
                "isCorrect": is_correct,
            }
        )
    return options


def _build_structured_quiz_payload(quiz_item: dict[str, Any]) -> dict[str, Any] | None:
    structured_data = quiz_item.get("structuredData") or {}
    if not isinstance(structured_data, dict):
        return None

    raw_questions = structured_data.get("questions")
    if not isinstance(raw_questions, list):
        return None

    questions: list[dict[str, Any]] = []
    for index, raw_question in enumerate(raw_questions, start=1):
        if not isinstance(raw_question, dict):
            continue
        prompt = str(raw_question.get("prompt") or raw_question.get("question") or "").strip()
        options = _normalize_quiz_options(raw_question.get("options") or [])
        if not prompt or len(options) < 2 or not any(option.get("isCorrect") for option in options):
            continue
        questions.append(
            {
                "id": str(raw_question.get("id") or raw_question.get("questionId") or f"q{index}").strip() or f"q{index}",
                "prompt": prompt,
                "options": options,
                "successMessage": str(raw_question.get("successMessage") or "Correct.").strip() or "Correct.",
                "errorMessage": (
                    str(raw_question.get("errorMessage") or "Not quite. Review the lesson and try again.").strip()
                    or "Not quite. Review the lesson and try again."
                ),
                "explanationMarkdown": str(
                    raw_question.get("explanationMarkdown") or raw_question.get("explanation") or ""
                ).strip(),
            }
        )

    if not questions:
        return None

    return {
        "prompt": str(structured_data.get("prompt") or questions[0]["prompt"]).strip() or questions[0]["prompt"],
        "questions": questions,
        "successMessage": str(structured_data.get("successMessage") or "Correct.").strip() or "Correct.",
        "errorMessage": (
            str(structured_data.get("errorMessage") or "Some answers are still incorrect.").strip()
            or "Some answers are still incorrect."
        ),
        "explanationMarkdown": str(structured_data.get("explanationMarkdown") or "").strip(),
    }


def _build_structured_practice_payload(practice_item: dict[str, Any]) -> dict[str, Any]:
    structured_data = practice_item.get("structuredData") or {}
    if not isinstance(structured_data, dict):
        return {}

    practice_mode = str(structured_data.get("practiceMode") or "").strip().lower()
    starter_code = str(structured_data.get("starterCode") or "").strip()
    if practice_mode != "code_editor" or not starter_code:
        return {}

    grader = structured_data.get("grader") if isinstance(structured_data.get("grader"), dict) else {}
    return {
        "practiceMode": "code_editor",
        "starterCode": starter_code,
        "hint": str(structured_data.get("hint") or "").strip(),
        "solution": str(structured_data.get("solution") or "").strip(),
        "grader": grader,
    }


def _build_interactive_resource_links(items_payload: Iterable[dict[str, Any]]) -> list[dict[str, str]]:
    links: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for item in items_payload:
        url = _section_item_link(item)
        if not url:
            continue

        activity_type = item.get("activityType")
        asset_type = item.get("assetType")
        if activity_type == OnlineCourseLessonSectionItem.ACTIVITY_VIDEO:
            kind = "video"
        elif asset_type == OnlineCourseLessonSectionItem.ASSET_DOCUMENT:
            kind = "document"
        elif asset_type == OnlineCourseLessonSectionItem.ASSET_NOTEBOOK:
            kind = "notebook"
        else:
            kind = "external"

        label = str(item.get("title") or "Lesson resource").strip() or "Lesson resource"
        key = (label, url)
        if key in seen:
            continue
        seen.add(key)
        links.append(
            {
                "id": f"resource-{item.get('id') or len(links) + 1}",
                "label": label,
                "url": url,
                "kind": kind,
            }
        )

    return links


def _compose_interactive_markdown(
    items_payload: Iterable[dict[str, Any]],
    *,
    fallback_heading: str = "",
    fallback_copy: str = "",
) -> str:
    blocks: list[str] = []
    if fallback_heading:
        blocks.append(f"## {fallback_heading}")

    for item in items_payload:
        title = str(item.get("title") or "").strip()
        description = str(item.get("description") or "").strip()
        body_markdown = str(item.get("bodyMarkdown") or "").strip()
        has_copy = bool(description or body_markdown)

        if title and has_copy:
            blocks.append(f"### {title}")
        if description:
            blocks.append(description)
        if body_markdown:
            blocks.append(body_markdown)
        if not has_copy and _section_item_link(item):
            label = title or "this lesson resource"
            blocks.append(f"Use the attached source for **{label}** to review the original material.")

    if fallback_copy:
        blocks.append(fallback_copy)

    return "\n\n".join(_unique_text_rows(blocks))


def _build_interactive_quiz_payload(
    *,
    lesson_title: str,
    module_title: str,
    course_title: str,
    quiz_item: dict[str, Any],
    theory_items: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    structured_payload = _build_structured_quiz_payload(quiz_item)
    if structured_payload is not None:
        return structured_payload

    theory_points: list[str] = []
    for item in theory_items:
        theory_points.extend(_extract_markdown_bullets(str(item.get("bodyMarkdown") or "")))
        description = str(item.get("description") or "").strip()
        if description:
            theory_points.append(description)

    normalized_points = _unique_text_rows(theory_points)
    correct_label = (
        normalized_points[0]
        if normalized_points
        else f"Understand the core objective of {lesson_title} before moving to practice."
    )
    distractor_pool = [
        f"Skip the preparation for {lesson_title} and start delivery immediately.",
        "Ignore the main assumption and validate nothing before submission.",
        "Treat controls and review as optional after the final output is already shared.",
        f"Use only {module_title or course_title or 'the course'} title as context without checking the lesson material.",
    ]

    option_labels = _unique_text_rows([correct_label, *distractor_pool])[:4]
    while len(option_labels) < 4:
        option_labels.append(f"Fallback review option {len(option_labels) + 1}")

    question_rows = _extract_markdown_bullets(str(quiz_item.get("bodyMarkdown") or ""))
    follow_up_rows = question_rows[1:3]

    return {
        "prompt": question_rows[0] if question_rows else f"What is the main focus of {lesson_title}?",
        "options": [
            {
                "id": f"quiz-{quiz_item.get('id') or lesson_title}-{index + 1}",
                "label": option_label,
                "isCorrect": index == 0,
            }
            for index, option_label in enumerate(option_labels)
        ],
        "successMessage": f"Correct. This matches the main focus of {lesson_title}.",
        "errorMessage": "Not quite. Re-check the theory points before continuing.",
        "explanationMarkdown": (
            "\n".join(f"- {row}" for row in follow_up_rows)
            if follow_up_rows
            else "Use the lesson brief, the core concept block, and the video before retrying."
        ),
    }


def _build_interactive_lesson_payload(
    lesson_payload: dict[str, Any],
    *,
    course_title: str = "",
    module_title: str = "",
) -> dict[str, Any]:
    lesson_title = str(lesson_payload.get("title") or "Lesson").strip() or "Lesson"
    sections = lesson_payload.get("sections") or []

    intro_items: list[dict[str, Any]] = []
    theory_items: list[dict[str, Any]] = []
    conclusion_items: list[dict[str, Any]] = []
    video_item: dict[str, Any] | None = None
    quiz_item: dict[str, Any] | None = None
    practice_item: dict[str, Any] | None = None
    all_items: list[dict[str, Any]] = []

    for section in sections:
        section_type = section.get("sectionType")
        for item in section.get("items") or []:
            all_items.append(item)
            activity_type = item.get("activityType")
            if activity_type == OnlineCourseLessonSectionItem.ACTIVITY_VIDEO and video_item is None:
                video_item = item
                continue
            if activity_type == OnlineCourseLessonSectionItem.ACTIVITY_QUIZ and quiz_item is None:
                quiz_item = item
                continue
            if activity_type == OnlineCourseLessonSectionItem.ACTIVITY_ASSIGNMENT and practice_item is None:
                practice_item = item
                continue
            if section_type == OnlineCourseLessonSection.SECTION_INTRODUCTION:
                intro_items.append(item)
            elif section_type == OnlineCourseLessonSection.SECTION_CONCLUSION:
                conclusion_items.append(item)
            else:
                theory_items.append(item)

    theory_markdown = _compose_interactive_markdown(
        intro_items,
        fallback_heading=f"{lesson_title} overview",
        fallback_copy=f"Start the lesson with the main orientation for {lesson_title}.",
    )
    core_markdown = _compose_interactive_markdown(
        theory_items,
        fallback_heading=f"{lesson_title} core concept",
        fallback_copy=f"Use this block as the main guided explanation for {lesson_title}.",
    )
    summary_markdown = _compose_interactive_markdown(
        conclusion_items,
        fallback_heading=f"{lesson_title} wrap-up",
        fallback_copy="Capture the main outcome before moving to the next lesson.",
    )

    steps: list[dict[str, Any]] = []
    if theory_markdown:
        steps.append(
            {
                "id": f"lesson-{lesson_payload.get('id')}-overview",
                "kind": "theory",
                "title": "Overview",
                "eyebrow": "Theory",
                "description": f"Orientation and framing for {lesson_title}.",
                "contentMarkdown": theory_markdown,
                "sourceItemId": intro_items[0].get("id") if intro_items else None,
                "resourceLinks": _build_interactive_resource_links(intro_items),
            }
        )

    if core_markdown and theory_items:
        steps.append(
            {
                "id": f"lesson-{lesson_payload.get('id')}-concept",
                "kind": "theory",
                "title": "Core Concept",
                "eyebrow": "Concept",
                "description": f"Main lesson explanation for {lesson_title}.",
                "contentMarkdown": core_markdown,
                "sourceItemId": theory_items[0].get("id"),
                "resourceLinks": _build_interactive_resource_links(theory_items),
            }
        )

    if video_item is not None:
        steps.append(
            {
                "id": f"lesson-{lesson_payload.get('id')}-video",
                "kind": "video",
                "title": "Video Walkthrough",
                "eyebrow": "Video",
                "description": video_item.get("title") or f"Watch the guided explanation for {lesson_title}.",
                "contentMarkdown": _compose_interactive_markdown(
                    [video_item],
                    fallback_copy="Watch the walkthrough, then move back to the notebook or theory if you need a recap.",
                ),
                "sourceItemId": video_item.get("id"),
                "videoUrl": _section_item_link(video_item),
                "resourceLinks": _build_interactive_resource_links([video_item]),
            }
        )

    if quiz_item is not None:
        steps.append(
            {
                "id": f"lesson-{lesson_payload.get('id')}-quiz",
                "kind": "quiz",
                "title": "Knowledge Check",
                "eyebrow": "Quiz",
                "description": "Short checkpoint before practice.",
                "contentMarkdown": str(quiz_item.get("description") or "").strip(),
                "sourceItemId": quiz_item.get("id"),
                "resourceLinks": _build_interactive_resource_links([quiz_item]),
                "quiz": _build_interactive_quiz_payload(
                    lesson_title=lesson_title,
                    module_title=module_title,
                    course_title=course_title,
                    quiz_item=quiz_item,
                    theory_items=[*intro_items, *theory_items],
                ),
            }
        )

    if practice_item is not None:
        practice_title = str(practice_item.get("title") or "").strip() or "Notebook practice"
        practice_content = str(practice_item.get("bodyMarkdown") or "").strip()
        if not practice_content:
            practice_content = (
                f"Use the notebook task for **{lesson_title}** as the practical example for this lesson.\n\n"
                "Review the theory and quiz first, then launch the runtime and submit your notebook."
            )
        practice_step = {
            "id": f"lesson-{lesson_payload.get('id')}-practice",
            "kind": "practice",
            "title": "Practice Lab",
            "eyebrow": "Practice",
            "description": practice_title,
            "contentMarkdown": practice_content,
            "sourceItemId": practice_item.get("id"),
            "resourceLinks": _build_interactive_resource_links([practice_item]),
        }
        practice_step.update(_build_structured_practice_payload(practice_item))
        steps.append(practice_step)

    if summary_markdown:
        steps.append(
            {
                "id": f"lesson-{lesson_payload.get('id')}-summary",
                "kind": "summary",
                "title": "Wrap-Up",
                "eyebrow": "Summary",
                "description": f"Close the lesson and prepare for the next block in {module_title or course_title or 'the course'}.",
                "contentMarkdown": summary_markdown,
                "sourceItemId": conclusion_items[0].get("id") if conclusion_items else None,
                "resourceLinks": _build_interactive_resource_links(conclusion_items),
            }
        )

    if not steps:
        steps.append(
            {
                "id": f"lesson-{lesson_payload.get('id')}-fallback",
                "kind": "theory",
                "title": "Lesson Brief",
                "eyebrow": "Theory",
                "description": f"Auto-generated lesson flow for {lesson_title}.",
                "contentMarkdown": (
                    lesson_payload.get("description")
                    or f"This lesson does not have structured assets yet, so the interactive flow is using the lesson description as a placeholder for {lesson_title}."
                ),
                "sourceItemId": None,
                "resourceLinks": [],
            }
        )

    theory_points: list[str] = []
    for item in [*intro_items, *theory_items, *conclusion_items]:
        theory_points.extend(_extract_markdown_bullets(str(item.get("bodyMarkdown") or "")))

    outcomes = _unique_text_rows(
        [
            *theory_points[:2],
            f"Complete the practical example for {lesson_title}.",
            "Use the checkpoint quiz before moving forward.",
        ]
    )[:4]

    interactive_lesson = {
        "courseTitle": course_title,
        "moduleTitle": module_title,
        "lessonTitle": lesson_title,
        "estimatedMinutes": max(20, len(steps) * 8),
        "demoVariantKey": f"interactive-lesson-{lesson_payload.get('id')}",
        "outcomes": outcomes,
        "resources": _build_interactive_resource_links(all_items),
        "steps": steps,
    }
    return apply_interactive_lesson_override(
        lesson_payload=lesson_payload,
        interactive_lesson=interactive_lesson,
    )


def _serialize_section(section: OnlineCourseLessonSection, request=None) -> dict[str, Any]:
    items = getattr(section, "prefetched_items", None)
    if items is None:
        items = list(section.items.filter(is_active=True).select_related("source_library_item", "linked_training_content"))
    items_payload = [
        serialize_section_item(item, request=request)
        for item in items
        if item.is_active and _section_item_visible_to_user(item, request=request)
    ]
    return {
        "id": section.id,
        "sectionType": section.section_type,
        "title": section.title,
        "description": section.description,
        "sortOrder": section.sort_order,
        "isActive": section.is_active,
        "items": items_payload,
    }


def _section_item_visible_to_user(item: OnlineCourseLessonSectionItem, request=None) -> bool:
    if request is None:
        return True
    user = getattr(request, "user", None)
    if not online_object_is_accessible_to_user(item, user):
        return False
    if item.linked_training_content_id and not content_item_is_visible_to_user(item.linked_training_content, user):
        return False
    return True


def _load_lesson_sections(lesson: OnlineCourseLesson) -> list[OnlineCourseLessonSection]:
    sections = getattr(lesson, "prefetched_sections", None)
    if sections is not None:
        return [section for section in sections if section.is_active]
    return list(
        lesson.sections.filter(is_active=True)
        .prefetch_related(
            Prefetch(
                "items",
                queryset=OnlineCourseLessonSectionItem.objects.select_related(
                    "source_library_item",
                    "linked_training_content",
                ).order_by("sort_order", "id"),
                to_attr="prefetched_items",
            )
        )
        .order_by("sort_order", "id")
    )


def _serialize_lesson_payload(
    lesson: OnlineCourseLesson,
    *,
    request=None,
    module: OnlineCourseModule | None = None,
    course: OnlineCourse | None = None,
) -> dict[str, Any]:
    sections = _load_lesson_sections(lesson)
    linked_module = module or getattr(lesson, "module", None)
    lesson_payload = {
        "id": lesson.id,
        "title": lesson.title,
        "description": lesson.description,
        "sortOrder": lesson.sort_order,
        "isActive": lesson.is_active,
        "moduleId": linked_module.id if linked_module else None,
        "moduleTitle": linked_module.title if linked_module else "",
        "moduleSortOrder": linked_module.sort_order if linked_module else 0,
        "moduleType": linked_module.module_type if linked_module else OnlineCourseModule.MODULE_TYPE_STANDARD,
        "startsAt": lesson.starts_at,
        "endsAt": lesson.ends_at,
        "sections": [_serialize_section(section, request=request) for section in sections if section.is_active],
    }
    lesson_payload["interactiveLesson"] = _build_interactive_lesson_payload(
        lesson_payload,
        course_title=_preferred_course_title(course or getattr(lesson, "course", None)),
        module_title=str(linked_module.title if linked_module else ""),
    )
    return lesson_payload


def _ordered_active_lessons_for_course(course: OnlineCourse) -> list[OnlineCourseLesson]:
    lessons = getattr(course, "prefetched_lessons", None)
    if lessons is not None:
        return [lesson for lesson in lessons if lesson.is_active]
    return list(
        OnlineCourseLesson.objects.filter(course=course, is_active=True)
        .select_related("module")
        .prefetch_related(
            Prefetch(
                "sections",
                queryset=OnlineCourseLessonSection.objects.prefetch_related(
                    Prefetch(
                        "items",
                        queryset=OnlineCourseLessonSectionItem.objects.select_related(
                            "source_library_item",
                            "linked_training_content",
                        ).order_by("sort_order", "id"),
                        to_attr="prefetched_items",
                    )
                )
                .order_by("sort_order", "id"),
                to_attr="prefetched_sections",
            )
        )
        .order_by("module__sort_order", "module__id", "sort_order", "id")
    )


def build_course_lessons_payload(course: OnlineCourse, request=None) -> list[dict[str, Any]]:
    lessons = _ordered_active_lessons_for_course(course)
    return [_serialize_lesson_payload(lesson, request=request, course=course) for lesson in lessons]


def build_course_modules_payload(course: OnlineCourse, request=None) -> list[dict[str, Any]]:
    prefetched_modules = getattr(course, "prefetched_modules", None)
    if prefetched_modules is not None:
        modules = [module for module in prefetched_modules if module.is_active]
    else:
        modules = list(
            OnlineCourseModule.objects.filter(course=course, is_active=True)
            .prefetch_related(
                Prefetch(
                    "lessons",
                    queryset=OnlineCourseLesson.objects.filter(is_active=True)
                    .prefetch_related(
                        Prefetch(
                            "sections",
                            queryset=OnlineCourseLessonSection.objects.prefetch_related(
                                Prefetch(
                                    "items",
                                    queryset=OnlineCourseLessonSectionItem.objects.select_related(
                                        "source_library_item",
                                        "linked_training_content",
                                    ).order_by("sort_order", "id"),
                                    to_attr="prefetched_items",
                                )
                            )
                            .order_by("sort_order", "id"),
                            to_attr="prefetched_sections",
                        )
                    )
                    .order_by("sort_order", "id"),
                    to_attr="prefetched_lessons",
                )
            )
            .order_by("sort_order", "id")
        )

    payload: list[dict[str, Any]] = []
    for module in modules:
        module_lessons = getattr(module, "prefetched_lessons", None)
        if module_lessons is None:
            module_lessons = list(
                module.lessons.filter(is_active=True)
                .select_related("module")
                .prefetch_related(
                    Prefetch(
                        "sections",
                        queryset=OnlineCourseLessonSection.objects.prefetch_related(
                            Prefetch(
                                "items",
                                queryset=OnlineCourseLessonSectionItem.objects.select_related(
                                    "source_library_item",
                                    "linked_training_content",
                                ).order_by("sort_order", "id"),
                                to_attr="prefetched_items",
                            )
                        )
                        .order_by("sort_order", "id"),
                        to_attr="prefetched_sections",
                    )
                )
                .order_by("sort_order", "id")
            )

        lessons_payload = [
            _serialize_lesson_payload(lesson, request=request, module=module, course=course)
            for lesson in module_lessons
            if lesson.is_active
        ]
        content_items_total = sum(
            len(section["items"])
            for lesson in lessons_payload
            for section in lesson["sections"]
        )
        payload.append(
            {
                "id": module.id,
                "title": module.title,
                "description": module.description,
                "moduleType": module.module_type,
                "weekNumber": module.week_number,
                "startsAt": module.starts_at,
                "endsAt": module.ends_at,
                "sortOrder": module.sort_order,
                "isActive": module.is_active,
                "lessonsCount": len(lessons_payload),
                "itemsCount": content_items_total,
                "lessons": lessons_payload,
            }
        )

    unassigned_lessons = [
        lesson
        for lesson in _ordered_active_lessons_for_course(course)
        if getattr(lesson, "module_id", None) is None
    ]
    if unassigned_lessons:
        lessons_payload = [
            _serialize_lesson_payload(lesson, request=request, module=None, course=course)
            for lesson in unassigned_lessons
        ]
        payload.append(
            {
                "id": None,
                "title": "Ungrouped",
                "description": "",
                "moduleType": OnlineCourseModule.MODULE_TYPE_STANDARD,
                "weekNumber": None,
                "startsAt": None,
                "endsAt": None,
                "sortOrder": 9999,
                "isActive": True,
                "lessonsCount": len(lessons_payload),
                "itemsCount": sum(
                    len(section["items"])
                    for lesson in lessons_payload
                    for section in lesson["sections"]
                ),
                "lessons": lessons_payload,
            }
        )

    return payload


def build_course_lessons_map(course_ids: Iterable[int], request=None) -> dict[int, list[dict[str, Any]]]:
    lessons_map: dict[int, list[dict[str, Any]]] = {}
    for course in structured_course_queryset(course_ids):
        lessons_map[course.id] = build_course_lessons_payload(course, request=request)
    return lessons_map


def build_course_modules_map(course_ids: Iterable[int], request=None) -> dict[int, list[dict[str, Any]]]:
    modules_map: dict[int, list[dict[str, Any]]] = {}
    for course in structured_course_queryset(course_ids):
        modules_map[course.id] = build_course_modules_payload(course, request=request)
    return modules_map


def annotate_lessons_payload_with_sessions(
    lessons_payload: list[dict[str, Any]],
    sessions: Iterable[Any],
    *,
    group_code: str = "",
    group_name: str = "",
) -> list[dict[str, Any]]:
    ordered_sessions = sorted(
        list(sessions),
        key=lambda session: (
            int(getattr(session, "sort_order", 0) or 0),
            getattr(session, "starts_at", None),
            int(getattr(session, "id", 0) or 0),
        ),
    )

    for index, lesson in enumerate(lessons_payload):
        session = ordered_sessions[index] if index < len(ordered_sessions) else None
        lesson["sessionId"] = getattr(session, "id", None) if session else None
        lesson["sessionTitle"] = getattr(session, "title", "") if session else ""
        lesson["sessionStatus"] = getattr(session, "status", "") if session else ""
        lesson["startsAt"] = getattr(session, "starts_at", None) if session else lesson.get("startsAt")
        lesson["endsAt"] = getattr(session, "ends_at", None) if session else lesson.get("endsAt")
        lesson["joinUrl"] = getattr(session, "join_url", "") if session else ""
        lesson["recordingUrl"] = getattr(session, "recording_url", "") if session else ""
        lesson["groupCode"] = group_code or ""
        lesson["groupName"] = group_name or ""

    return lessons_payload


def annotate_modules_payload_with_sessions(
    modules_payload: list[dict[str, Any]],
    sessions: Iterable[Any],
    *,
    group_code: str = "",
    group_name: str = "",
) -> list[dict[str, Any]]:
    flattened_lessons = [lesson for module in modules_payload for lesson in module.get("lessons", [])]
    annotate_lessons_payload_with_sessions(
        flattened_lessons,
        sessions,
        group_code=group_code,
        group_name=group_name,
    )

    for module in modules_payload:
        lesson_rows = module.get("lessons", [])
        scheduled_lessons = [lesson for lesson in lesson_rows if lesson.get("startsAt")]
        module["startsAt"] = scheduled_lessons[0].get("startsAt") if scheduled_lessons else module.get("startsAt")
        module["endsAt"] = scheduled_lessons[-1].get("endsAt") if scheduled_lessons else module.get("endsAt")
        module["groupCode"] = group_code or ""
        module["groupName"] = group_name or ""

    return modules_payload


def _structured_items_for_material_projection(course: OnlineCourse, request=None) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    lesson_payload = build_course_lessons_payload(course, request=request)
    for lesson in lesson_payload:
        module_sort = int(lesson.get("moduleSortOrder") or 0)
        module_title = str(lesson.get("moduleTitle") or "").strip()
        for section in lesson["sections"]:
            for item in section["items"]:
                link_url = (
                    item["externalUrl"]
                    or item["fileUrl"]
                    or ((item["trainingContent"] or {}).get("sourceUrl") if item["trainingContent"] else "")
                    or ""
                )
                items.append(
                    {
                        "id": f"structured-{item['id']}",
                        "title": (
                            f"{module_title} · {lesson['title']} · {section['title']} · {item['title']}"
                            if module_title
                            else f"{lesson['title']} · {section['title']} · {item['title']}"
                        ),
                        "description": item["description"],
                        "material_type": OnlineCourseMaterial.MATERIAL_RESOURCE,
                        "language": item["language"],
                        "link_url": link_url or None,
                        "sort_order": (
                            module_sort * 10000
                            + lesson["sortOrder"] * 100
                            + section["sortOrder"]
                            + item["sortOrder"]
                        ),
                        "sourceType": "structured",
                        "assetType": item["assetType"],
                    }
                )
    return items


def build_course_material_projection(course: OnlineCourse, request=None) -> list[dict[str, Any]]:
    user = getattr(request, "user", None)
    legacy_materials = [
        {
            "id": item.id,
            "title": item.title,
            "description": item.description,
            "material_type": item.material_type,
            "language": item.language,
            "link_url": item.link_url,
            "sort_order": item.sort_order,
            "sourceType": "legacy",
            "assetType": item.material_type,
            "audienceIds": online_access_policy_audience_ids_for_instance(item),
        }
        for item in course.materials.filter(is_active=True).order_by("sort_order", "id")
        if request is None or online_object_is_accessible_to_user(item, user)
    ]
    structured_materials = _structured_items_for_material_projection(course, request=request)
    return sorted(
        [*legacy_materials, *structured_materials],
        key=lambda item: (item["sort_order"], str(item["id"])),
    )


def build_course_material_projection_map(course_ids: Iterable[int], request=None) -> dict[int, list[dict[str, Any]]]:
    material_map: dict[int, list[dict[str, Any]]] = {}
    for course in structured_course_queryset(course_ids):
        material_map[course.id] = build_course_material_projection(course, request=request)
    return material_map


def summarize_course_structure(course: OnlineCourse, request=None) -> dict[str, Any]:
    modules = build_course_modules_payload(course, request=request)
    lessons = [lesson for module in modules for lesson in module["lessons"]]
    items_total = 0
    notebook_items = 0
    document_items = 0
    quiz_items = 0
    assignment_items = 0
    video_items = 0
    for lesson in lessons:
        for section in lesson["sections"]:
            for item in section["items"]:
                items_total += 1
                if item["assetType"] == OnlineCourseLessonSectionItem.ASSET_NOTEBOOK:
                    notebook_items += 1
                if item["assetType"] == OnlineCourseLessonSectionItem.ASSET_DOCUMENT:
                    document_items += 1
                if item["activityType"] == OnlineCourseLessonSectionItem.ACTIVITY_QUIZ:
                    quiz_items += 1
                if item["activityType"] == OnlineCourseLessonSectionItem.ACTIVITY_ASSIGNMENT:
                    assignment_items += 1
                if item["activityType"] == OnlineCourseLessonSectionItem.ACTIVITY_VIDEO:
                    video_items += 1

    final_assessment_modules = [module for module in modules if module["moduleType"] == OnlineCourseModule.MODULE_TYPE_FINAL]
    return {
        "modulesCount": len(modules),
        "lessonsCount": len(lessons),
        "itemsCount": items_total,
        "notebookItemsCount": notebook_items,
        "documentItemsCount": document_items,
        "videoItemsCount": video_items,
        "quizItemsCount": quiz_items,
        "assignmentItemsCount": assignment_items,
        "finalAssessmentModulesCount": len(final_assessment_modules),
        "hasStructuredOutline": len(lessons) > 0,
    }


def build_course_structure_summary_map(course_ids: Iterable[int], request=None) -> dict[int, dict[str, Any]]:
    summary_map: dict[int, dict[str, Any]] = {}
    for course in structured_course_queryset(course_ids):
        summary_map[course.id] = summarize_course_structure(course, request=request)
    return summary_map


def build_course_template_payload(template: OnlineCourseTemplate) -> dict[str, Any]:
    lessons = list(template.lessons.order_by("sort_order", "id"))
    lessons_payload = [
        {
            "title": lesson.title,
            "description": lesson.description,
            "sortOrder": lesson.sort_order,
            "sections": [
                {
                    "sectionType": OnlineCourseLessonSection.SECTION_MAIN,
                    "title": lesson.main_title,
                    "description": lesson.main_description,
                    "sortOrder": 10,
                    "items": [],
                },
            ],
        }
        for lesson in lessons
    ]
    return {
        "id": template.id,
        "slug": template.slug,
        "title": template.title,
        "description": template.description,
        "defaultLessonsCount": template.default_lessons_count,
        "lessons": lessons_payload,
        "modules": [
            {
                "title": "Module 1 (Week 1)",
                "description": "Template module",
                "moduleType": OnlineCourseModule.MODULE_TYPE_STANDARD,
                "weekNumber": 1,
                "sortOrder": 10,
                "isActive": True,
                "lessons": lessons_payload,
            }
        ],
    }


def clone_library_file_to_section_item(
    source_item: OnlineCourseContentLibraryItem,
    target_item: OnlineCourseLessonSectionItem,
) -> None:
    if not source_item.file_asset:
        return
    source_item.file_asset.open("rb")
    try:
        file_name = Path(source_item.file_asset.name).name
        target_item.file_asset.save(file_name, File(source_item.file_asset.file), save=False)
    finally:
        source_item.file_asset.close()


def _section_item_snapshot_from_library(source_item: OnlineCourseContentLibraryItem) -> dict[str, Any]:
    default_activity_type = ACTIVITY_TYPE_BY_ASSET_TYPE.get(
        source_item.asset_type,
        OnlineCourseLessonSectionItem.ACTIVITY_TEXT,
    )
    return {
        "title": source_item.title,
        "description": source_item.description,
        "asset_type": source_item.asset_type,
        "activity_type": default_activity_type,
        "language": source_item.language,
        "body_markdown": source_item.body_markdown,
        "external_url": source_item.external_url,
        "linked_training_content": source_item.training_content,
        "structured_data": {},
    }


def _empty_section_payload(section_type: str) -> dict[str, Any]:
    return {
        "sectionType": section_type,
        "title": section_default_title(section_type),
        "description": "",
        "sortOrder": section_sort_order(section_type),
        "isActive": True,
        "items": [],
    }


def _import_activity_to_builder_item(activity: dict[str, Any], *, index: int) -> tuple[str, dict[str, Any]]:
    raw_type = str(activity.get("type") or activity.get("kind") or "text").strip().lower()
    title = str(activity.get("title") or activity.get("name") or f"Item {index}").strip() or f"Item {index}"
    description = str(activity.get("description") or activity.get("summary") or "").strip()
    language = str(activity.get("language") or "en").strip().lower()
    if language not in {OnlineCourse.LOCALE_DE, OnlineCourse.LOCALE_EN}:
        language = OnlineCourse.LOCALE_EN

    item_payload: dict[str, Any] = {
        "title": title,
        "description": description,
        "language": language,
        "sortOrder": index,
        "isActive": True,
    }

    if raw_type in {"video"}:
        item_payload.update(
            {
                "assetType": OnlineCourseLessonSectionItem.ASSET_LINK,
                "activityType": OnlineCourseLessonSectionItem.ACTIVITY_VIDEO,
                "externalUrl": str(activity.get("url") or activity.get("video_url") or "").strip(),
                "bodyMarkdown": "",
            }
        )
        return OnlineCourseLessonSection.SECTION_MAIN, item_payload

    if raw_type in {"quiz", "test"}:
        question_rows = activity.get("questions") if isinstance(activity.get("questions"), list) else []
        if question_rows:
            questions_markdown = "\n".join(
                f"- {str(question.get('question') or question.get('prompt') or '').strip()}"
                for question in question_rows
                if str(question.get("question") or question.get("prompt") or "").strip()
            )
        else:
            questions_markdown = ""
        item_payload.update(
            {
                "assetType": OnlineCourseLessonSectionItem.ASSET_TEXT,
                "activityType": OnlineCourseLessonSectionItem.ACTIVITY_QUIZ,
                "bodyMarkdown": questions_markdown or str(activity.get("text") or "").strip(),
                "externalUrl": "",
            }
        )
        return OnlineCourseLessonSection.SECTION_MAIN, item_payload

    if raw_type in {"assignment", "project", "exam", "final_project", "final_exam"}:
        notebook_id = activity.get("trainingContentId") or activity.get("linkedTrainingContentId")
        item_payload.update(
            {
                "activityType": OnlineCourseLessonSectionItem.ACTIVITY_ASSIGNMENT,
                "assetType": (
                    OnlineCourseLessonSectionItem.ASSET_NOTEBOOK
                    if notebook_id
                    else OnlineCourseLessonSectionItem.ASSET_LINK
                ),
                "linkedTrainingContentId": notebook_id,
                "externalUrl": str(activity.get("url") or activity.get("assignment_url") or "").strip(),
                "bodyMarkdown": str(activity.get("instructions") or activity.get("text") or "").strip(),
            }
        )
        return OnlineCourseLessonSection.SECTION_MAIN, item_payload

    item_payload.update(
        {
            "assetType": OnlineCourseLessonSectionItem.ASSET_TEXT,
            "activityType": OnlineCourseLessonSectionItem.ACTIVITY_TEXT,
            "bodyMarkdown": str(activity.get("text") or activity.get("content") or "").strip(),
            "externalUrl": "",
        }
    )
    return OnlineCourseLessonSection.SECTION_MAIN, item_payload


def build_modules_from_import_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        return []

    raw_modules = payload.get("modules")
    if not isinstance(raw_modules, list):
        course_payload = payload.get("course")
        if isinstance(course_payload, dict):
            raw_modules = course_payload.get("modules")
    if not isinstance(raw_modules, list):
        raw_lessons = payload.get("lessons")
        if not isinstance(raw_lessons, list):
            course_payload = payload.get("course")
            if isinstance(course_payload, dict):
                raw_lessons = course_payload.get("lessons")
        if isinstance(raw_lessons, list):
            raw_modules = [
                {
                    "title": "Module 1 (Week 1)",
                    "description": "",
                    "lessons": raw_lessons,
                }
            ]
        else:
            return []

    modules_output: list[dict[str, Any]] = []
    for module_index, raw_module in enumerate(raw_modules, start=1):
        if not isinstance(raw_module, dict):
            continue
        module_title = str(
            raw_module.get("title")
            or raw_module.get("name")
            or f"Module {module_index} (Week {module_index})"
        ).strip() or f"Module {module_index} (Week {module_index})"
        module_description = str(raw_module.get("description") or raw_module.get("summary") or "").strip()
        module_lessons_raw = raw_module.get("lessons")
        if not isinstance(module_lessons_raw, list):
            module_lessons_raw = raw_module.get("units") if isinstance(raw_module.get("units"), list) else []

        module_lessons: list[dict[str, Any]] = []
        for lesson_index, raw_lesson in enumerate(module_lessons_raw, start=1):
            if not isinstance(raw_lesson, dict):
                continue
            lesson_title = str(raw_lesson.get("title") or raw_lesson.get("name") or f"Lesson {lesson_index}").strip() or f"Lesson {lesson_index}"
            lesson_description = str(raw_lesson.get("description") or raw_lesson.get("summary") or "").strip()
            raw_activities = raw_lesson.get("contentItems")
            if not isinstance(raw_activities, list):
                raw_activities = raw_lesson.get("items") if isinstance(raw_lesson.get("items"), list) else []
            if not isinstance(raw_activities, list):
                raw_activities = raw_lesson.get("activities") if isinstance(raw_lesson.get("activities"), list) else []

            main_section = _empty_section_payload(OnlineCourseLessonSection.SECTION_MAIN)
            main_section["sortOrder"] = 10
            main_section["items"].append(
                {
                    "title": f"{lesson_title} overview",
                    "description": "Lesson orientation and expected outcomes.",
                    "assetType": OnlineCourseLessonSectionItem.ASSET_TEXT,
                    "activityType": OnlineCourseLessonSectionItem.ACTIVITY_TEXT,
                    "language": OnlineCourse.LOCALE_EN,
                    "bodyMarkdown": lesson_description or "Overview and context for this lesson.",
                    "externalUrl": "",
                    "sortOrder": 1,
                    "isActive": True,
                }
            )

            for activity_index, activity in enumerate(raw_activities, start=1):
                if not isinstance(activity, dict):
                    continue
                _section_type, item_payload = _import_activity_to_builder_item(activity, index=activity_index)
                main_section["items"].append(item_payload)

            for item_index, section_item in enumerate(main_section["items"], start=1):
                section_item["sortOrder"] = item_index

            module_lessons.append(
                {
                    "title": lesson_title,
                    "description": lesson_description,
                    "sortOrder": lesson_index,
                    "isActive": True,
                    "sections": [main_section],
                }
            )

        modules_output.append(
            {
                "title": module_title,
                "description": module_description,
                "moduleType": OnlineCourseModule.MODULE_TYPE_STANDARD,
                "weekNumber": module_index,
                "sortOrder": module_index * 10,
                "isActive": True,
                "lessons": module_lessons,
            }
        )

    final_assessment = payload.get("finalAssessment") or payload.get("final_assessment")
    if isinstance(final_assessment, dict):
        title = str(final_assessment.get("title") or "Final Project / Exam").strip() or "Final Project / Exam"
        description = str(final_assessment.get("description") or "").strip()
        final_lesson = {
            "title": title,
            "description": description,
            "sortOrder": 1,
            "isActive": True,
            "sections": [_empty_section_payload(OnlineCourseLessonSection.SECTION_MAIN)],
        }
        final_lesson["sections"][0]["sortOrder"] = 10
        final_lesson["sections"][0]["items"] = [
            {
                "title": "Final scope",
                "description": "Expected project scope and submission rules.",
                "assetType": OnlineCourseLessonSectionItem.ASSET_TEXT,
                "activityType": OnlineCourseLessonSectionItem.ACTIVITY_TEXT,
                "language": OnlineCourse.LOCALE_EN,
                "bodyMarkdown": description or "Complete final project and submit evidence.",
                "externalUrl": "",
                "sortOrder": 1,
                "isActive": True,
            },
            {
                "title": "Final assignment",
                "description": "Submit final project or complete the final exam.",
                "assetType": OnlineCourseLessonSectionItem.ASSET_TEXT,
                "activityType": OnlineCourseLessonSectionItem.ACTIVITY_ASSIGNMENT,
                "language": OnlineCourse.LOCALE_EN,
                "bodyMarkdown": str(final_assessment.get("instructions") or "").strip(),
                "externalUrl": str(final_assessment.get("url") or "").strip(),
                "sortOrder": 2,
                "isActive": True,
            }
        ]
        modules_output.append(
            {
                "title": title,
                "description": description,
                "moduleType": OnlineCourseModule.MODULE_TYPE_FINAL,
                "weekNumber": None,
                "sortOrder": (len(modules_output) + 1) * 10,
                "isActive": True,
                "lessons": [final_lesson],
            }
        )

    return modules_output


def _normalize_module_rows(
    *,
    lessons_data: list[dict[str, Any]] | None,
    modules_data: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    if modules_data:
        return modules_data
    if lessons_data:
        return [
            {
                "title": "Module 1 (Week 1)",
                "description": "",
                "moduleType": OnlineCourseModule.MODULE_TYPE_STANDARD,
                "weekNumber": 1,
                "sortOrder": 10,
                "isActive": True,
                "lessons": lessons_data,
            }
        ]
    return []


def upsert_course_structure(
    course: OnlineCourse,
    lessons_data: list[dict[str, Any]] | None = None,
    *,
    modules_data: list[dict[str, Any]] | None = None,
) -> None:
    normalized_modules = _normalize_module_rows(lessons_data=lessons_data, modules_data=modules_data)

    existing_modules = {
        module.id: module
        for module in OnlineCourseModule.objects.filter(course=course)
    }
    existing_lessons = {
        lesson.id: lesson
        for lesson in OnlineCourseLesson.objects.filter(course=course).prefetch_related("sections__items")
    }
    kept_module_ids: list[int] = []
    kept_lesson_ids: list[int] = []

    for module_index, module_data in enumerate(normalized_modules, start=1):
        module = existing_modules.get(module_data.get("id"))
        if module is None:
            module = OnlineCourseModule(course=course)
        week_number = module_data.get("week_number") or module_data.get("weekNumber")
        module.title = (
            module_data.get("title")
            or f"Module {module_index} (Week {week_number or module_index})"
        )
        module.description = module_data.get("description", "")
        module.module_type = (
            module_data.get("module_type")
            or module_data.get("moduleType")
            or OnlineCourseModule.MODULE_TYPE_STANDARD
        )
        module.week_number = week_number
        module.starts_at = module_data.get("starts_at") or module_data.get("startsAt")
        module.ends_at = module_data.get("ends_at") or module_data.get("endsAt")
        module.sort_order = module_data.get("sort_order") or module_data.get("sortOrder") or module_index * 10
        module.is_active = module_data.get("is_active", module_data.get("isActive", True))
        module.save()
        kept_module_ids.append(module.id)

        lesson_rows = module_data.get("lessons") or []
        for lesson_index, lesson_data in enumerate(lesson_rows, start=1):
            lesson = existing_lessons.get(lesson_data.get("id"))
            if lesson is None:
                lesson = OnlineCourseLesson(course=course, module=module)
            lesson.module = module
            lesson.title = lesson_data["title"]
            lesson.description = lesson_data.get("description", "")
            lesson.starts_at = lesson_data.get("starts_at") or lesson_data.get("startsAt")
            lesson.ends_at = lesson_data.get("ends_at") or lesson_data.get("endsAt")
            lesson.sort_order = lesson_data.get("sort_order") or lesson_data.get("sortOrder") or lesson_index
            lesson.is_active = lesson_data.get("is_active", lesson_data.get("isActive", True))
            lesson.save()
            kept_lesson_ids.append(lesson.id)
            ensure_lesson_sections(lesson)

            existing_sections_by_type = {
                section.section_type: section for section in lesson.sections.all()
            }
            kept_section_ids: list[int] = []
            for section_data in lesson_data["sections"]:
                section_type = section_data["section_type"] if "section_type" in section_data else section_data["sectionType"]
                section = existing_sections_by_type.get(section_type)
                if section is None:
                    section = OnlineCourseLessonSection(lesson=lesson, section_type=section_type)
                section.title = section_data.get("title") or section_default_title(section_type)
                section.description = section_data.get("description", "")
                section.sort_order = section_data.get("sort_order") or section_data.get("sortOrder") or section_sort_order(section_type)
                section.is_active = section_data.get("is_active", section_data.get("isActive", True))
                section.save()
                kept_section_ids.append(section.id)

                existing_items = {item.id: item for item in section.items.all()}
                kept_item_ids: list[int] = []
                for item_index, item_data in enumerate(section_data.get("items", []), start=1):
                    source_library_item = (
                        item_data.get("source_library_item")
                        or item_data.get("sourceLibraryItem")
                        or item_data.get("sourceLibraryItemId")
                    )
                    if isinstance(source_library_item, int):
                        source_library_item = OnlineCourseContentLibraryItem.objects.filter(id=source_library_item).first()

                    linked_training_content = (
                        item_data.get("linked_training_content")
                        or item_data.get("linkedTrainingContent")
                        or item_data.get("linkedTrainingContentId")
                    )
                    if isinstance(linked_training_content, int):
                        linked_training_content = TrainingContentItem.objects.filter(id=linked_training_content).first()
                    if linked_training_content is None and source_library_item and source_library_item.training_content_id:
                        linked_training_content = source_library_item.training_content

                    item = existing_items.get(item_data.get("id"))
                    is_new_item = item is None
                    if item is None:
                        item = OnlineCourseLessonSectionItem(section=section)
                    previous_source_library_item_id = item.source_library_item_id

                    snapshot = _section_item_snapshot_from_library(source_library_item) if source_library_item else {}
                    item.source_library_item = source_library_item
                    item.linked_training_content = linked_training_content or snapshot.get("linked_training_content")
                    item.title = item_data.get("title") or snapshot.get("title") or "Untitled item"
                    item.description = item_data.get("description", snapshot.get("description", ""))
                    item.asset_type = item_data.get("asset_type") or item_data.get("assetType") or snapshot.get("asset_type") or item.asset_type
                    item.activity_type = (
                        item_data.get("activity_type")
                        or item_data.get("activityType")
                        or snapshot.get("activity_type")
                        or ACTIVITY_TYPE_BY_ASSET_TYPE.get(item.asset_type, OnlineCourseLessonSectionItem.ACTIVITY_TEXT)
                    )
                    item.language = item_data.get("language") or snapshot.get("language") or item.language
                    item.body_markdown = item_data.get("body_markdown", item_data.get("bodyMarkdown", snapshot.get("body_markdown", "")))
                    item.structured_data = item_data.get(
                        "structured_data",
                        item_data.get("structuredData", snapshot.get("structured_data", {})),
                    ) or {}
                    item.external_url = item_data.get("external_url", item_data.get("externalUrl", snapshot.get("external_url", "")))
                    item.sort_order = item_data.get("sort_order") or item_data.get("sortOrder") or item_index
                    item.is_active = item_data.get("is_active", item_data.get("isActive", True))

                    should_clone_library_file = bool(
                        source_library_item
                        and source_library_item.file_asset
                        and (is_new_item or previous_source_library_item_id != source_library_item.id or not item.file_asset)
                    )
                    item.save()
                    if should_clone_library_file:
                        clone_library_file_to_section_item(source_library_item, item)
                        item.save(update_fields=["file_asset", "updated_at"])
                    if "audienceIds" in item_data:
                        sync_online_access_policies_for_instance(
                            instance=item,
                            audience_ids=item_data.get("audienceIds") or [],
                        )
                    kept_item_ids.append(item.id)

                section.items.exclude(id__in=kept_item_ids).delete()

            lesson.sections.exclude(id__in=kept_section_ids).delete()

    course.structured_lessons.exclude(id__in=kept_lesson_ids).delete()
    if kept_module_ids:
        course.modules.exclude(id__in=kept_module_ids).delete()
    else:
        course.modules.all().delete()
    course.lessons_count = len(kept_lesson_ids)
    course.save(update_fields=["lessons_count", "updated_at"])


def build_course_instructor_ids(course: OnlineCourse) -> list[int]:
    teacher_ids = (
        Lehrer.objects.filter(
            user__training_course_roles__course=course,
            user__training_course_roles__role=TrainingCourseRoleAssignment.Role.INSTRUCTOR,
        )
        .values_list("id", flat=True)
        .distinct()
        .order_by("id")
    )
    return list(teacher_ids)


def build_course_workspace_ids(course: OnlineCourse) -> list[int]:
    workspace_ids = (
        OnlineWorkspaceContentItem.objects.filter(
            linked_course=course,
            section=OnlineWorkspaceContentItem.SECTION_COURSES,
            is_active=True,
        )
        .values_list("workspace_id", flat=True)
        .distinct()
        .order_by("workspace_id")
    )
    return list(workspace_ids)


def sync_course_instructor_assignments(
    *,
    course: OnlineCourse,
    teacher_ids: Iterable[int],
) -> list[int]:
    selected_teachers = list(
        Lehrer.objects.select_related("user")
        .filter(id__in=list(dict.fromkeys(int(teacher_id) for teacher_id in teacher_ids if teacher_id)))
        .order_by("id")
    )
    selected_user_ids = {teacher.user_id for teacher in selected_teachers if teacher.user_id}
    current_assignments = list(
        TrainingCourseRoleAssignment.objects.filter(
            course=course,
            role=TrainingCourseRoleAssignment.Role.INSTRUCTOR,
        )
    )
    current_by_user_id = {assignment.user_id: assignment for assignment in current_assignments}

    for assignment in current_assignments:
        if assignment.user_id not in selected_user_ids:
            assignment.delete()

    for index, teacher in enumerate(selected_teachers):
        assignment = current_by_user_id.get(teacher.user_id)
        if assignment is None:
            assignment = TrainingCourseRoleAssignment(
                user=teacher.user,
                course=course,
                role=TrainingCourseRoleAssignment.Role.INSTRUCTOR,
            )
        assignment.is_primary = index == 0
        assignment.response_sla_hours = 24
        assignment.save()

    return [teacher.id for teacher in selected_teachers]


def sync_course_workspace_placements(
    *,
    course: OnlineCourse,
    workspace_ids: Iterable[int],
    linked_cohort: OnlineCohort | None = None,
) -> list[int]:
    normalized_workspace_ids = list(dict.fromkeys(int(workspace_id) for workspace_id in workspace_ids if workspace_id))
    workspaces = list(OnlineWorkspace.objects.filter(id__in=normalized_workspace_ids).order_by("sort_order", "id"))
    workspace_id_set = {workspace.id for workspace in workspaces}
    course_audience_ids = online_access_policy_audience_ids_for_instance(course)

    existing_items = list(
        OnlineWorkspaceContentItem.objects.filter(
            linked_course=course,
            section=OnlineWorkspaceContentItem.SECTION_COURSES,
        ).order_by("workspace_id", "sort_order", "id")
    )
    existing_by_workspace_id: dict[int, OnlineWorkspaceContentItem] = {}
    duplicate_item_ids: list[int] = []
    for item in existing_items:
        if item.workspace_id not in existing_by_workspace_id:
            existing_by_workspace_id[item.workspace_id] = item
        else:
            duplicate_item_ids.append(item.id)
    if duplicate_item_ids:
        OnlineWorkspaceContentItem.objects.filter(id__in=duplicate_item_ids).delete()

    for item in existing_by_workspace_id.values():
        if item.workspace_id not in workspace_id_set:
            item.delete()

    for workspace in workspaces:
        item = existing_by_workspace_id.get(workspace.id)
        if item is None:
            last_sort_order = (
                workspace.content_items.filter(section=OnlineWorkspaceContentItem.SECTION_COURSES)
                .order_by("-sort_order", "-id")
                .values_list("sort_order", flat=True)
                .first()
                or 0
            )
            item = OnlineWorkspaceContentItem(
                workspace=workspace,
                section=OnlineWorkspaceContentItem.SECTION_COURSES,
                sort_order=last_sort_order + 10,
            )
        item.title = course.title_en or course.title_de
        item.description = course.short_description_en or course.short_description_de
        item.preview_image_url = course.hero_image_url or ""
        item.asset_url = ""
        item.linked_course = course
        if linked_cohort is not None:
            item.linked_cohort = linked_cohort
        item.primary_meta = "Interactive lesson path"
        item.secondary_meta = "Guided lesson · Notebook · AI"
        if item.published_on is None:
            item.published_on = timezone.localdate()
        item.is_active = True
        item.save()
        sync_online_access_policies_for_instance(instance=item, audience_ids=course_audience_ids)

    return [workspace.id for workspace in workspaces]


def build_course_builder_payload(course: OnlineCourse, request=None) -> dict[str, Any]:
    modules_payload = build_course_modules_payload(course, request=request)
    lessons_payload = [lesson for module in modules_payload for lesson in module["lessons"]]
    return {
        "id": course.id,
        "slug": course.slug,
        "titleDe": course.title_de,
        "titleEn": course.title_en,
        "shortDescriptionDe": course.short_description_de,
        "shortDescriptionEn": course.short_description_en,
        "descriptionDe": course.description_de,
        "descriptionEn": course.description_en,
        "startsAt": course.starts_at,
        "endsAt": course.ends_at,
        "lessonsCount": course.lessons_count,
        "trialAvailable": course.trial_available,
        "priceAmount": str(course.price_amount),
        "currency": course.currency,
        "isSubscription": course.is_subscription,
        "isPublished": course.is_published,
        "lifecycleStatus": course.lifecycle_status,
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
        "metadataJson": course.metadata_json or {},
        "customFields": course.custom_fields or {},
        "requiredCompletionPercent": course.required_completion_percent,
        "requiredAttendancePercent": course.required_attendance_percent,
        "requiresAttestation": course.requires_attestation,
        "completionRule": {
            "requiredCompletionPercent": course.required_completion_percent,
            "requiredAttendancePercent": course.required_attendance_percent,
            "requiresAttestation": course.requires_attestation,
        },
        "heroImageUrl": course.hero_image_url or "",
        "seoTitleDe": course.seo_title_de,
        "seoTitleEn": course.seo_title_en,
        "seoDescriptionDe": course.seo_description_de,
        "seoDescriptionEn": course.seo_description_en,
        "geoCity": course.geo_city,
        "geoCountry": course.geo_country,
        "audienceIds": online_access_policy_audience_ids_for_instance(course),
        "instructorIds": build_course_instructor_ids(course),
        "workspaceIds": build_course_workspace_ids(course),
        "governance": build_course_governance_payload(course, include_history=True),
        "modules": modules_payload,
        "lessons": lessons_payload,
        "structureSummary": summarize_course_structure(course, request=request),
    }
