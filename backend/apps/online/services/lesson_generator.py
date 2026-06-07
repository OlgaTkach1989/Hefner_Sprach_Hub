from __future__ import annotations

import logging
import re
from typing import Any, Iterable

from django.conf import settings

from apps.online.models import OnlineCourseLessonSection, OnlineCourseLessonSectionItem
from apps.online.services.course_agents_orchestrator import (
    CourseBuilderAgentsError,
    generate_course_builder_lesson_blueprint_with_agents,
)
from apps.training.services.ai_assistant import training_ai_enabled
from apps.training.services.ai_provider import (
    TrainingAiContextChunk,
    TrainingAiProviderError,
    get_training_ai_provider,
)


logger = logging.getLogger(__name__)


def generate_course_builder_lesson_document(
    *,
    lesson_title: str,
    lesson_description: str = "",
    source_text: str,
    language: str = "en",
    course_title: str = "",
    module_title: str = "",
    video_url: str = "",
    video_description: str = "",
) -> dict[str, Any]:
    normalized_title = str(lesson_title or "").strip() or "Generated lesson"
    normalized_description = str(lesson_description or "").strip()
    normalized_source_text = _normalize_whitespace(source_text)
    normalized_video_url = str(video_url or "").strip()
    normalized_video_description = _normalize_whitespace(video_description)
    normalized_language = language if language in {"de", "en"} else "en"

    context_chunks = _build_context_chunks(
        lesson_title=normalized_title,
        source_text=normalized_source_text,
        video_description=normalized_video_description,
    )

    blueprint = _build_fallback_blueprint(
        lesson_title=normalized_title,
        lesson_description=normalized_description,
        source_text=normalized_source_text,
        video_description=normalized_video_description,
        video_url=normalized_video_url,
        course_title=course_title,
        module_title=module_title,
    )
    generation_meta = {
        "mode": "fallback",
        "provider": "deterministic",
        "model": "structured-template-v1",
    }

    if context_chunks and training_ai_enabled():
        orchestrator_mode = _course_builder_ai_orchestrator_mode()
        ai_blueprint = None
        if orchestrator_mode == "agents":
            ai_blueprint = _build_agents_blueprint(
                lesson_title=normalized_title,
                lesson_description=normalized_description,
                source_text=normalized_source_text,
                course_title=course_title,
                module_title=module_title,
                context_chunks=context_chunks,
                fallback_blueprint=blueprint,
            )

        if ai_blueprint is None:
            ai_blueprint = _build_ai_blueprint(
                lesson_title=normalized_title,
                lesson_description=normalized_description,
                source_text=normalized_source_text,
                course_title=course_title,
                module_title=module_title,
                context_chunks=context_chunks,
                fallback_blueprint=blueprint,
            )

        if ai_blueprint is not None:
            blueprint = {
                **blueprint,
                **{key: value for key, value in ai_blueprint.items() if value},
                "quiz": ai_blueprint.get("quiz") or blueprint["quiz"],
                "practice": ai_blueprint.get("practice") or blueprint["practice"],
            }
            generation_meta = {
                "mode": "ai",
                "provider": ai_blueprint.get("provider") or "unknown",
                "model": ai_blueprint.get("model") or "unknown",
                "orchestrator": ai_blueprint.get("orchestrator") or "legacy",
            }

    return {
        "document": _blueprint_to_document(
            blueprint=blueprint,
            language=normalized_language,
            video_url=normalized_video_url,
            video_description=normalized_video_description,
        ),
        "meta": generation_meta,
    }


def _build_agents_blueprint(
    *,
    lesson_title: str,
    lesson_description: str,
    source_text: str,
    course_title: str,
    module_title: str,
    context_chunks: list[TrainingAiContextChunk],
    fallback_blueprint: dict[str, Any],
) -> dict[str, Any] | None:
    try:
        return generate_course_builder_lesson_blueprint_with_agents(
            lesson_title=lesson_title,
            lesson_description=lesson_description,
            source_text=source_text,
            course_title=course_title,
            module_title=module_title,
            context_chunks=context_chunks,
            fallback_blueprint=fallback_blueprint,
        )
    except CourseBuilderAgentsError as exc:
        logger.info("Course Builder Agents SDK orchestration skipped: %s", exc)
        return None
    except Exception:
        logger.exception("Course Builder Agents SDK orchestration failed unexpectedly.")
        return None


def _course_builder_ai_orchestrator_mode() -> str:
    mode = str(getattr(settings, "COURSE_BUILDER_AI_ORCHESTRATOR", "legacy") or "legacy").strip().lower()
    return "agents" if mode == "agents" else "legacy"


def _build_context_chunks(
    *,
    lesson_title: str,
    source_text: str,
    video_description: str,
) -> list[TrainingAiContextChunk]:
    chunks: list[TrainingAiContextChunk] = []
    paragraphs = [paragraph for paragraph in re.split(r"\n\s*\n+", source_text) if paragraph.strip()]
    if not paragraphs:
        paragraphs = _split_sentences(source_text)

    for index, paragraph in enumerate(paragraphs[:4], start=1):
        normalized_paragraph = _normalize_whitespace(paragraph)
        if not normalized_paragraph:
            continue
        chunks.append(
            TrainingAiContextChunk(
                content_slug=f"{_slugify_for_id(lesson_title)}-source-{index}",
                content_name=lesson_title,
                section_title=f"Source block {index}",
                citation_label=f"Source block {index}",
                text=normalized_paragraph,
                snippet=normalized_paragraph[:180],
                source_url=None,
            )
        )

    if video_description:
        chunks.append(
            TrainingAiContextChunk(
                content_slug=f"{_slugify_for_id(lesson_title)}-video",
                content_name=lesson_title,
                section_title="Video context",
                citation_label="Video context",
                text=video_description,
                snippet=video_description[:180],
                source_url=None,
            )
        )

    return chunks


def _build_ai_blueprint(
    *,
    lesson_title: str,
    lesson_description: str,
    source_text: str,
    course_title: str,
    module_title: str,
    context_chunks: list[TrainingAiContextChunk],
    fallback_blueprint: dict[str, Any],
) -> dict[str, Any] | None:
    try:
        provider = get_training_ai_provider()
    except TrainingAiProviderError:
        return None

    content_name = lesson_title
    scope_label = module_title or course_title or "the course"
    try:
        blueprint_answer = provider.generate_answer(
            content_name=content_name,
            prompt_type="ask",
            question=(
                f"Draft a compact interactive lesson blueprint inside {scope_label}. "
                "Return markdown only with exactly these headings: ## Theory, ## Concept, ## Wrap-up. "
                "Under each heading write 2-4 concise bullets grounded in the supplied source content. "
                "Do not include quiz JSON, code fences, or extra headings."
            ),
            context_chunks=context_chunks,
        )
    except TrainingAiProviderError:
        return None

    generated_markdown = blueprint_answer.detailed_answer or blueprint_answer.short_answer
    return {
        "description": lesson_description or fallback_blueprint["description"],
        "theoryMarkdown": _section_markdown_from_ai(
            generated_markdown,
            heading="Theory",
            fallback=fallback_blueprint["theoryMarkdown"],
        ),
        "conceptMarkdown": _section_markdown_from_ai(
            generated_markdown,
            heading="Concept",
            fallback=fallback_blueprint["conceptMarkdown"],
        ),
        "summaryMarkdown": _section_markdown_from_ai(
            generated_markdown,
            heading="Wrap-up",
            fallback=fallback_blueprint["summaryMarkdown"],
        ),
        "quiz": fallback_blueprint["quiz"],
        "provider": provider.provider_name,
        "model": provider.model_name,
        "sourceText": source_text,
    }


def _build_fallback_blueprint(
    *,
    lesson_title: str,
    lesson_description: str,
    source_text: str,
    video_description: str,
    video_url: str,
    course_title: str,
    module_title: str,
) -> dict[str, Any]:
    paragraphs = [paragraph for paragraph in re.split(r"\n\s*\n+", source_text) if paragraph.strip()]
    key_points = _extract_key_points(source_text)
    theory_points = key_points[:3] or [f"Understand the main goal of {lesson_title}.", "Prepare to apply the concept in practice."]
    concept_points = key_points[1:5] if len(key_points) > 1 else key_points[:4]
    if not concept_points:
        concept_points = [
            f"Define the central idea behind {lesson_title}.",
            "Connect the explanation to a concrete learner action.",
        ]

    overview_paragraph = _normalize_whitespace(paragraphs[0]) if paragraphs else ""
    concept_paragraph = _normalize_whitespace(paragraphs[1]) if len(paragraphs) > 1 else ""
    lesson_scope = module_title or course_title or "the course"

    theory_markdown = "\n\n".join(
        part
        for part in [
            "## Theory",
            overview_paragraph or lesson_description or f"Start {lesson_title} with a short orientation and a clear success target.",
            "### What to focus on",
            "\n".join(f"- {point}" for point in theory_points),
        ]
        if part
    )
    concept_markdown = "\n\n".join(
        part
        for part in [
            "## Concept",
            concept_paragraph or f"This step explains the core concept behind {lesson_title} and connects it to work in {lesson_scope}.",
            "### Core ideas",
            "\n".join(f"- {point}" for point in concept_points),
        ]
        if part
    )
    summary_markdown = "\n\n".join(
        [
            "## Wrap-up",
            "\n".join(
                f"- {point}"
                for point in _unique_rows(
                    [
                        *concept_points[:2],
                        f"Use the practice step to reinforce {lesson_title}.",
                        "Review the walkthrough before moving to the next lesson.",
                    ]
                )[:4]
            ),
        ]
    )

    return {
        "title": lesson_title,
        "description": lesson_description or overview_paragraph or f"Generated lesson flow for {lesson_title}.",
        "theoryMarkdown": theory_markdown,
        "conceptMarkdown": concept_markdown,
        "summaryMarkdown": summary_markdown,
        "quiz": _build_fallback_quiz_payload(lesson_title=lesson_title, key_points=concept_points or theory_points),
        "practice": _build_fallback_practice_payload(
            lesson_title=lesson_title,
            key_points=concept_points or theory_points,
            video_description=video_description,
            video_url=video_url,
        ),
    }


def _blueprint_to_document(
    *,
    blueprint: dict[str, Any],
    language: str,
    video_url: str,
    video_description: str,
) -> dict[str, Any]:
    practice_payload = blueprint.get("practice") if isinstance(blueprint.get("practice"), dict) else {}
    practice_markdown = str(
        practice_payload.get("contentMarkdown")
        or practice_payload.get("instructionsMarkdown")
        or ""
    ).strip()
    quiz_payload = blueprint.get("quiz") if isinstance(blueprint.get("quiz"), dict) else {}

    items = [
        {
            "title": "Theory",
            "description": "Orientation, context, and success criteria.",
            "assetType": OnlineCourseLessonSectionItem.ASSET_TEXT,
            "activityType": OnlineCourseLessonSectionItem.ACTIVITY_TEXT,
            "language": language,
            "bodyMarkdown": str(blueprint.get("theoryMarkdown") or "").strip(),
            "externalUrl": "",
            "structuredData": {},
            "sortOrder": 1,
            "isActive": True,
        },
        {
            "title": "Concept",
            "description": "Core lesson explanation.",
            "assetType": OnlineCourseLessonSectionItem.ASSET_TEXT,
            "activityType": OnlineCourseLessonSectionItem.ACTIVITY_TEXT,
            "language": language,
            "bodyMarkdown": str(blueprint.get("conceptMarkdown") or "").strip(),
            "externalUrl": "",
            "structuredData": {},
            "sortOrder": 2,
            "isActive": True,
        },
        {
            "title": "Video walkthrough",
            "description": video_description or "Guided walkthrough for this lesson.",
            "assetType": OnlineCourseLessonSectionItem.ASSET_LINK,
            "activityType": OnlineCourseLessonSectionItem.ACTIVITY_VIDEO,
            "language": language,
            "bodyMarkdown": _build_video_markdown(video_description=video_description),
            "externalUrl": video_url,
            "structuredData": {},
            "sortOrder": 3,
            "isActive": True,
        },
        {
            "title": "Knowledge check",
            "description": "Answer all questions before moving to practice.",
            "assetType": OnlineCourseLessonSectionItem.ASSET_TEXT,
            "activityType": OnlineCourseLessonSectionItem.ACTIVITY_QUIZ,
            "language": language,
            "bodyMarkdown": _build_quiz_markdown(quiz_payload),
            "externalUrl": "",
            "structuredData": quiz_payload,
            "sortOrder": 4,
            "isActive": True,
        },
        {
            "title": str(practice_payload.get("title") or "Practice lab").strip() or "Practice lab",
            "description": str(practice_payload.get("description") or "Interactive code task.").strip() or "Interactive code task.",
            "assetType": OnlineCourseLessonSectionItem.ASSET_TEXT,
            "activityType": OnlineCourseLessonSectionItem.ACTIVITY_ASSIGNMENT,
            "language": language,
            "bodyMarkdown": practice_markdown,
            "externalUrl": "",
            "structuredData": {
                "practiceMode": "code_editor",
                "starterCode": str(practice_payload.get("starterCode") or "").strip(),
                "hint": str(practice_payload.get("hint") or "").strip(),
                "solution": str(practice_payload.get("solution") or "").strip(),
                "grader": practice_payload.get("grader") if isinstance(practice_payload.get("grader"), dict) else {},
            },
            "sortOrder": 5,
            "isActive": True,
        },
        {
            "title": "Wrap-up",
            "description": "Close the lesson and prepare for the next step.",
            "assetType": OnlineCourseLessonSectionItem.ASSET_TEXT,
            "activityType": OnlineCourseLessonSectionItem.ACTIVITY_TEXT,
            "language": language,
            "bodyMarkdown": str(blueprint.get("summaryMarkdown") or "").strip(),
            "externalUrl": "",
            "structuredData": {},
            "sortOrder": 6,
            "isActive": True,
        },
    ]

    return {
        "title": str(blueprint.get("title") or "").strip(),
        "description": str(blueprint.get("description") or "").strip(),
        "sections": [
            {
                "sectionType": OnlineCourseLessonSection.SECTION_MAIN,
                "title": "Main content",
                "description": "Complete lesson flow.",
                "sortOrder": 10,
                "isActive": True,
                "items": items,
            },
        ],
    }


def _quiz_payload_from_ai_quiz(quiz) -> dict[str, Any]:
    questions = []
    for question in getattr(quiz, "questions", []) or []:
        options = []
        for option in question.options:
            option_id = str(option.get("id") or "").strip()
            label = str(option.get("label") or "").strip()
            if not option_id or not label:
                continue
            options.append(
                {
                    "id": option_id,
                    "label": label,
                    "isCorrect": option_id == question.correct_option_id,
                }
            )
        if len(options) < 2 or not any(option["isCorrect"] for option in options):
            continue
        questions.append(
            {
                "id": str(question.question_id or f"q{len(questions) + 1}").strip() or f"q{len(questions) + 1}",
                "prompt": str(question.prompt or "").strip(),
                "options": options,
                "successMessage": "Correct.",
                "errorMessage": "Not quite. Review the lesson and try again.",
                "explanationMarkdown": _ensure_markdown(question.explanation, "Explanation"),
            }
        )

    if not questions:
        return _build_fallback_quiz_payload(lesson_title=getattr(quiz, "title", "") or "Lesson", key_points=[])

    return {
        "prompt": questions[0]["prompt"],
        "title": str(getattr(quiz, "title", "") or "Knowledge check").strip() or "Knowledge check",
        "questions": questions,
        "successMessage": "Correct.",
        "errorMessage": "Some answers are still incorrect.",
        "explanationMarkdown": "",
    }


def _build_fallback_quiz_payload(*, lesson_title: str, key_points: Iterable[str]) -> dict[str, Any]:
    normalized_points = [point for point in _unique_rows(key_points) if point][:3]
    if not normalized_points:
        normalized_points = [f"Understand the main goal of {lesson_title}.", "Review the core explanation before practice."]
    while len(normalized_points) < 3:
        normalized_points.append(f"Connect {lesson_title} to a concrete learner action before moving on.")

    questions = []
    for index, point in enumerate(normalized_points[:3], start=1):
        distractors = _unique_rows(
            [
                f"Skip the preparation for {lesson_title} and move directly to the final answer.",
                "Ignore the lesson context and work only from assumptions.",
                "Treat review and validation as optional after submitting the output.",
            ]
        )[:3]
        options = [
            {"id": "a", "label": point, "isCorrect": True},
            {"id": "b", "label": distractors[0], "isCorrect": False},
            {"id": "c", "label": distractors[1], "isCorrect": False},
            {"id": "d", "label": distractors[2], "isCorrect": False},
        ]
        questions.append(
            {
                "id": f"q{index}",
                "prompt": f"Which statement best matches {lesson_title} ({index})?",
                "options": options,
                "successMessage": "Correct.",
                "errorMessage": "Not quite. Review the lesson and try again.",
                "explanationMarkdown": f"### Why this is correct\n\n- {point}",
            }
        )

    return {
        "prompt": questions[0]["prompt"],
        "title": f"{lesson_title} knowledge check",
        "questions": questions,
        "successMessage": "Correct.",
        "errorMessage": "Some answers are still incorrect.",
        "explanationMarkdown": "",
    }


def _build_fallback_practice_payload(
    *,
    lesson_title: str,
    key_points: Iterable[str],
    video_description: str,
    video_url: str,
) -> dict[str, Any]:
    normalized_points = [point for point in _unique_rows(key_points) if point][:3]
    if not normalized_points:
        normalized_points = [f"Summarize the lesson goal for {lesson_title}."]

    function_name = _function_name_from_title(lesson_title)
    expected_result = {
        "lesson": lesson_title,
        "concepts": normalized_points[:2],
        "video_focus": video_description or ("Review the attached walkthrough." if video_url else "No video attached yet."),
    }
    starter_code = (
        f"def {function_name}():\n"
        "    \"\"\"Return a structured summary for this lesson.\"\"\"\n"
        "    # TODO: replace the placeholder values with the correct summary.\n"
        "    return {\n"
        '        "lesson": "",\n'
        '        "concepts": [],\n'
        '        "video_focus": "",\n'
        "    }\n"
    )
    solution = (
        f"def {function_name}():\n"
        "    return {\n"
        f'        "lesson": {expected_result["lesson"]!r},\n'
        f'        "concepts": {expected_result["concepts"]!r},\n'
        f'        "video_focus": {expected_result["video_focus"]!r},\n'
        "    }\n"
    )
    instructions_markdown = "\n\n".join(
        [
            "## Practice",
            f"Implement `{function_name}()` so it returns a dictionary with the lesson name, the main concepts, and the video focus.",
            "### Required keys",
            "- `lesson`",
            "- `concepts`",
            "- `video_focus`",
            "### Concepts to include",
            "\n".join(f"- {point}" for point in normalized_points),
        ]
    )
    return {
        "title": "Practice lab",
        "description": "Use the editor to complete the coding task.",
        "contentMarkdown": instructions_markdown,
        "starterCode": starter_code,
        "hint": f"Use `{lesson_title}` as the lesson name and include these concepts: {', '.join(normalized_points[:2])}.",
        "solution": solution,
        "grader": {
            "type": "python_function_check",
            "function_name": function_name,
            "cases": [
                {
                    "label": "Returns the expected lesson summary",
                    "args": [],
                    "expected": expected_result,
                }
            ],
        },
    }


def _build_video_markdown(*, video_description: str) -> str:
    if not video_description:
        return "## Video\n\nUse this step for the walkthrough or recorded explanation linked to the lesson."
    return "\n\n".join(
        [
            "## Video",
            video_description,
        ]
    )


def _build_quiz_markdown(quiz_payload: dict[str, Any]) -> str:
    title = str(quiz_payload.get("title") or "Knowledge check").strip() or "Knowledge check"
    prompts = [
        f"- {str(question.get('prompt') or '').strip()}"
        for question in (quiz_payload.get("questions") or [])
        if str(question.get("prompt") or "").strip()
    ]
    return "\n\n".join(part for part in [f"## {title}", "\n".join(prompts)] if part)


def _extract_key_points(source_text: str) -> list[str]:
    bullet_points = [
        row.strip()[2:].strip()
        for row in str(source_text or "").splitlines()
        if row.strip().startswith("- ")
    ]
    if bullet_points:
        return _unique_rows(bullet_points)

    sentences = _split_sentences(source_text)
    return _unique_rows(sentence.strip() for sentence in sentences if sentence.strip())[:6]


def _split_sentences(value: str) -> list[str]:
    normalized = _normalize_whitespace(value)
    if not normalized:
        return []
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", normalized) if part.strip()]


def _ensure_markdown(value: str, heading: str) -> str:
    normalized = _normalize_whitespace(value)
    if not normalized:
        return f"## {heading}"
    if re.search(r"^#{1,6}\s", normalized, re.MULTILINE):
        return normalized
    if normalized.startswith("- "):
        return f"## {heading}\n\n{normalized}"
    return f"## {heading}\n\n{normalized}"


def _section_markdown_from_ai(value: str, *, heading: str, fallback: str) -> str:
    normalized = _normalize_whitespace(value)
    if not normalized:
        return fallback

    pattern = re.compile(
        rf"^##\s+{re.escape(heading)}\s*$" r"(?P<body>.*?)(?=^##\s+|\Z)",
        re.IGNORECASE | re.MULTILINE | re.DOTALL,
    )
    match = pattern.search(normalized)
    if not match:
        return fallback

    body = match.group("body").strip()
    if not body:
        return fallback
    return _ensure_markdown(f"## {heading}\n\n{body}", heading)


def _function_name_from_title(value: str) -> str:
    tokens = [token for token in re.split(r"[^a-zA-Z0-9]+", value.lower()) if token]
    suffix = "_".join(tokens[:3]) or "lesson_summary"
    return f"build_{suffix}_summary"


def _slugify_for_id(value: str) -> str:
    tokens = [token for token in re.split(r"[^a-zA-Z0-9]+", value.lower()) if token]
    return "-".join(tokens[:6]) or "lesson"


def _normalize_whitespace(value: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", str(value or "").replace("\r\n", "\n")).strip()


def _unique_rows(values: Iterable[str]) -> list[str]:
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
