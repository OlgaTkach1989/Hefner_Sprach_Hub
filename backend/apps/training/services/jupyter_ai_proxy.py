from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import re
import time
import uuid

from django.conf import settings

from apps.training.models import TrainingContentItem
from apps.training.services.ai_assistant import training_ai_enabled
from apps.training.services.ai_provider import (
    TrainingAiContextChunk,
    TrainingAiProviderError,
    build_default_follow_up_prompts,
    get_training_ai_provider,
)
from apps.training.services.knowledge_base import retrieve_training_knowledge_matches


_QUERY_TOKEN_RE = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_\-']+")


class TrainingJupyterAiProxyError(RuntimeError):
    pass


@dataclass(frozen=True)
class ResolvedJupyterAiProxyRequest:
    question: str
    requested_model: str


@dataclass(frozen=True)
class _ScoredContextChunk:
    chunk: TrainingAiContextChunk
    score: float
    priority: int


def build_internal_jupyter_ai_proxy_token(*, content_slug: str, expires_at_epoch: int) -> str:
    secret = _signing_secret()
    if not secret:
        raise TrainingJupyterAiProxyError("Jupyter AI signing secret is not configured.")
    normalized_slug = str(content_slug or "").strip()
    expiry_value = int(expires_at_epoch or 0)
    if not normalized_slug or expiry_value <= 0:
        raise TrainingJupyterAiProxyError("Jupyter AI proxy token payload is incomplete.")
    message = f"{normalized_slug}:{expiry_value}"
    signature = hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{expiry_value}.{signature}"


def validate_internal_jupyter_ai_proxy_token(*, content_slug: str, token: str) -> None:
    normalized_slug = str(content_slug or "").strip()
    raw_token = str(token or "").strip()
    if not normalized_slug or not raw_token:
        raise TrainingJupyterAiProxyError("Jupyter AI proxy token is missing.")
    try:
        expiry_part, signature_part = raw_token.split(".", 1)
        expires_at_epoch = int(expiry_part)
    except (ValueError, TypeError) as exc:
        raise TrainingJupyterAiProxyError("Jupyter AI proxy token format is invalid.") from exc
    grace_seconds = training_jupyter_ai_proxy_token_grace_seconds()
    if expires_at_epoch <= int(time.time()) - grace_seconds:
        raise TrainingJupyterAiProxyError("Jupyter AI proxy token is expired.")
    expected_token = build_internal_jupyter_ai_proxy_token(
        content_slug=normalized_slug,
        expires_at_epoch=expires_at_epoch,
    )
    _expected_expiry, expected_signature = expected_token.split(".", 1)
    if not hmac.compare_digest(signature_part, expected_signature):
        raise TrainingJupyterAiProxyError("Jupyter AI proxy token signature is invalid.")


def resolve_internal_jupyter_ai_proxy_request(payload: dict) -> ResolvedJupyterAiProxyRequest:
    if not isinstance(payload, dict):
        raise TrainingJupyterAiProxyError("Jupyter AI request payload must be an object.")
    messages = payload.get("messages")
    if not isinstance(messages, list) or not messages:
        raise TrainingJupyterAiProxyError("Jupyter AI request must include messages.")

    requested_model = str(payload.get("model") or "").strip()
    question = ""
    for message in reversed(messages):
        if not isinstance(message, dict):
            continue
        if str(message.get("role") or "").strip().lower() != "user":
            continue
        question = _flatten_message_content(message.get("content"))
        if question:
            break

    if not question:
        raise TrainingJupyterAiProxyError("Jupyter AI request does not contain a user question.")
    return ResolvedJupyterAiProxyRequest(question=question, requested_model=requested_model)


def build_internal_jupyter_ai_models_payload(*, content_item: TrainingContentItem) -> dict[str, object]:
    provider = get_training_ai_provider()
    model_name = provider.model_name or str(getattr(settings, "TRAINING_AI_CHAT_MODEL", "") or "").strip() or "demo-extractive-v1"
    return {
        "object": "list",
        "data": [
            {
                "id": model_name,
                "object": "model",
                "owned_by": f"learning-hub-{provider.provider_name}",
                "permission": [],
                "contentSlug": content_item.slug,
            }
        ],
    }


def build_internal_jupyter_ai_chat_completion(
    *,
    content_item: TrainingContentItem,
    question: str,
    requested_model: str = "",
) -> dict[str, object]:
    if not training_ai_enabled():
        raise TrainingJupyterAiProxyError("Training AI assistant is disabled.")

    normalized_question = str(question or "").strip()
    if not normalized_question:
        raise TrainingJupyterAiProxyError("Question is required.")

    context_limit = max(3, int(getattr(settings, "TRAINING_AI_MAX_CONTEXT_CHUNKS", 5) or 5))
    notebook_matches = retrieve_training_knowledge_matches(
        content_items=[content_item],
        query=normalized_question,
        limit=context_limit,
        preferred_content_item_id=content_item.id,
    )

    scored_chunks: list[_ScoredContextChunk] = [
        _ScoredContextChunk(
            chunk=_context_chunk_from_match(match),
            score=match.score + 0.25,
            priority=30,
        )
        for match in notebook_matches
    ]

    sibling_content_items, manual_lesson_chunks = _related_lesson_context_chunks(
        content_item=content_item,
        question=normalized_question,
    )
    if sibling_content_items:
        sibling_matches = retrieve_training_knowledge_matches(
            content_items=sibling_content_items,
            query=normalized_question,
            limit=max(2, min(context_limit, 4)),
            preferred_content_item_id=content_item.id,
        )
        scored_chunks.extend(
            _ScoredContextChunk(
                chunk=_context_chunk_from_match(match),
                score=match.score + 0.12,
                priority=20,
            )
            for match in sibling_matches
        )
    scored_chunks.extend(manual_lesson_chunks)

    context_chunks = _dedupe_ranked_context_chunks(
        scored_chunks,
        limit=max(context_limit * 2, context_limit + 4),
    )

    provider = get_training_ai_provider()
    try:
        answer = provider.generate_answer(
            content_name=content_item.name,
            question=normalized_question,
            prompt_type="ask",
            context_chunks=context_chunks,
        )
    except TrainingAiProviderError as exc:
        raise TrainingJupyterAiProxyError(str(exc)) from exc

    citations = [
        scored.chunk.citation_label
        for scored in sorted(scored_chunks, key=lambda item: (item.score, item.priority), reverse=True)
        if str(scored.chunk.citation_label or "").strip()
    ][:3]
    assistant_text_parts = [answer.short_answer.strip(), answer.detailed_answer.strip()]
    if citations:
        assistant_text_parts.append("References:\n" + "\n".join(f"- {label}" for label in citations))
    follow_ups = answer.follow_up_prompts or build_default_follow_up_prompts(question=normalized_question, prompt_type="ask")
    if follow_ups:
        assistant_text_parts.append("Suggested follow-ups:\n" + "\n".join(f"- {item}" for item in follow_ups[:3]))

    assistant_text = "\n\n".join(part for part in assistant_text_parts if part)
    resolved_model = requested_model or provider.model_name or "demo-extractive-v1"
    created_at = int(time.time())
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex}",
        "object": "chat.completion",
        "created": created_at,
        "model": resolved_model,
        "choices": [
            {
                "index": 0,
                "finish_reason": "stop",
                "message": {
                    "role": "assistant",
                    "content": assistant_text,
                },
            }
        ],
        "usage": {
            "prompt_tokens": max(1, len(normalized_question.split())),
            "completion_tokens": max(1, len(assistant_text.split())),
            "total_tokens": max(2, len(normalized_question.split()) + len(assistant_text.split())),
        },
    }


def _related_lesson_context_chunks(
    *,
    content_item: TrainingContentItem,
    question: str,
) -> tuple[list[TrainingContentItem], list[_ScoredContextChunk]]:
    if not content_item.id:
        return [], []

    from apps.online.models import OnlineCourseLessonSectionItem

    notebook_section_items = list(
        content_item.online_course_section_items.select_related(
            "section__lesson__course",
            "section__lesson__module",
            "source_library_item__training_content",
            "linked_training_content",
        )
        .filter(
            is_active=True,
            section__is_active=True,
            section__lesson__is_active=True,
        )
        .order_by("section__lesson_id", "section__sort_order", "sort_order", "id")
    )
    if not notebook_section_items:
        return [], []

    lesson_ids = {item.section.lesson_id for item in notebook_section_items if item.section_id and item.section.lesson_id}
    sibling_items = list(
        OnlineCourseLessonSectionItem.objects.select_related(
            "section__lesson__course",
            "section__lesson__module",
            "source_library_item__training_content",
            "linked_training_content",
        )
        .filter(
            section__lesson_id__in=lesson_ids,
            is_active=True,
            section__is_active=True,
            section__lesson__is_active=True,
        )
        .order_by("section__lesson_id", "section__sort_order", "sort_order", "id")
    )
    items_by_lesson_id: dict[int, list] = {}
    for sibling in sibling_items:
        items_by_lesson_id.setdefault(sibling.section.lesson_id, []).append(sibling)

    related_training_items: dict[int, TrainingContentItem] = {}
    manual_chunks: list[_ScoredContextChunk] = []
    seen_lesson_ids: set[int] = set()

    for notebook_item in notebook_section_items:
        lesson = notebook_item.section.lesson
        module = getattr(lesson, "module", None)
        lesson_siblings = items_by_lesson_id.get(lesson.id, [])
        if lesson.id not in seen_lesson_ids:
            scope_chunk = _build_lesson_scope_chunk(
                notebook_content=content_item,
                lesson=lesson,
                module=module,
                notebook_item=notebook_item,
                sibling_items=lesson_siblings,
            )
            if scope_chunk is not None:
                manual_chunks.append(
                    _ScoredContextChunk(
                        chunk=scope_chunk,
                        score=_manual_context_score(question=question, chunk=scope_chunk) + 0.3,
                        priority=25,
                    )
                )
            seen_lesson_ids.add(lesson.id)

        for sibling in lesson_siblings:
            if sibling.id == notebook_item.id:
                continue
            manual_chunk = _build_section_item_context_chunk(
                notebook_content=content_item,
                lesson=lesson,
                module=module,
                section_item=sibling,
            )
            if manual_chunk is not None:
                manual_chunks.append(
                    _ScoredContextChunk(
                        chunk=manual_chunk,
                        score=_manual_context_score(question=question, chunk=manual_chunk),
                        priority=10,
                    )
                )
            for related_item in _related_training_items_for_section_item(sibling):
                if related_item.id and related_item.id != content_item.id:
                    related_training_items.setdefault(related_item.id, related_item)

    return list(related_training_items.values()), manual_chunks


def _build_lesson_scope_chunk(*, notebook_content: TrainingContentItem, lesson, module, notebook_item, sibling_items) -> TrainingAiContextChunk | None:
    course = getattr(lesson, "course", None)
    notebook_prompt = _clean_text(getattr(notebook_content, "body_markdown", ""))
    sibling_summaries = [
        sibling.title
        for sibling in sibling_items
        if str(getattr(sibling, "title", "") or "").strip() and sibling.id != getattr(notebook_item, "id", None)
    ][:4]
    chunk_lines = [
        f"Course: {_clean_text(getattr(course, 'title_en', '') or getattr(course, 'title_de', ''))}",
        f"Module: {_clean_text(getattr(module, 'title', ''))}" if module else "",
        f"Module summary: {_clean_text(getattr(module, 'description', ''))}" if module else "",
        f"Lesson: {_clean_text(getattr(lesson, 'title', ''))}",
        f"Lesson summary: {_clean_text(getattr(lesson, 'description', ''))}",
        f"Notebook assignment: {_clean_text(getattr(notebook_item, 'title', ''))}",
        f"Notebook summary: {_clean_text(getattr(notebook_item, 'description', ''))}",
        notebook_prompt,
        ("Lesson package includes: " + ", ".join(sibling_summaries)) if sibling_summaries else "",
    ]
    chunk_text = "\n".join(line for line in chunk_lines if line).strip()
    if not chunk_text:
        return None
    lesson_title = _clean_text(getattr(lesson, "title", "")) or notebook_content.name
    lesson_snippet = _clean_text(getattr(lesson, "description", "")) or _clean_text(getattr(notebook_item, "description", ""))
    return TrainingAiContextChunk(
        content_slug=notebook_content.slug,
        content_name=notebook_content.name,
        section_title="Lesson scope",
        citation_label=f"Lesson scope • {lesson_title}",
        text=chunk_text,
        snippet=lesson_snippet,
        source_url=str(getattr(notebook_content, "source_url", "") or "").strip() or None,
    )


def _build_section_item_context_chunk(*, notebook_content: TrainingContentItem, lesson, module, section_item) -> TrainingAiContextChunk | None:
    source_library_item = getattr(section_item, "source_library_item", None)
    source_url = str(
        getattr(section_item, "external_url", "")
        or getattr(source_library_item, "external_url", "")
        or ""
    ).strip()
    file_name = ""
    file_asset = getattr(section_item, "file_asset", None)
    if file_asset and getattr(file_asset, "name", ""):
        file_name = str(file_asset.name).replace("\\", "/").split("/")[-1]
    elif source_library_item is not None:
        source_file = getattr(source_library_item, "file_asset", None)
        if source_file and getattr(source_file, "name", ""):
            file_name = str(source_file.name).replace("\\", "/").split("/")[-1]

    chunk_lines = [
        f"Course: {_clean_text(getattr(getattr(lesson, 'course', None), 'title_en', '') or getattr(getattr(lesson, 'course', None), 'title_de', ''))}",
        f"Module: {_clean_text(getattr(module, 'title', ''))}" if module else "",
        f"Lesson: {_clean_text(getattr(lesson, 'title', ''))}",
        f"Section: {_clean_text(getattr(section_item.section, 'title', ''))}",
        f"Item: {_clean_text(getattr(section_item, 'title', ''))}",
        f"Item summary: {_clean_text(getattr(section_item, 'description', ''))}",
        f"Section summary: {_clean_text(getattr(section_item.section, 'description', ''))}",
        f"Approved lesson notes: {_clean_text(getattr(section_item, 'body_markdown', ''))}",
        f"Library notes: {_clean_text(getattr(source_library_item, 'body_markdown', ''))}" if source_library_item is not None else "",
        f"Library summary: {_clean_text(getattr(source_library_item, 'description', ''))}" if source_library_item is not None else "",
        f"Attached lesson document: {file_name}" if file_name else "",
        f"Linked resource: {source_url}" if source_url else "",
    ]
    chunk_text = "\n".join(line for line in chunk_lines if line).strip()
    if not chunk_text:
        return None
    lesson_title = _clean_text(getattr(lesson, "title", "")) or notebook_content.name
    item_title = _clean_text(getattr(section_item, "title", "")) or "Lesson item"
    return TrainingAiContextChunk(
        content_slug=notebook_content.slug,
        content_name=notebook_content.name,
        section_title=_clean_text(getattr(section_item.section, "title", "")) or "Lesson material",
        citation_label=f"{lesson_title} • {item_title}",
        text=chunk_text,
        snippet=_clean_text(getattr(section_item, "description", "")) or item_title,
        source_url=source_url or None,
    )


def _related_training_items_for_section_item(section_item) -> list[TrainingContentItem]:
    related_items: list[TrainingContentItem] = []
    linked_item = getattr(section_item, "linked_training_content", None)
    if linked_item is not None:
        related_items.append(linked_item)
    source_library_item = getattr(section_item, "source_library_item", None)
    library_training_item = getattr(source_library_item, "training_content", None) if source_library_item is not None else None
    if library_training_item is not None:
        related_items.append(library_training_item)
    deduped: dict[int, TrainingContentItem] = {}
    for related_item in related_items:
        if related_item.id:
            deduped.setdefault(related_item.id, related_item)
    return list(deduped.values())


def _manual_context_score(*, question: str, chunk: TrainingAiContextChunk) -> float:
    normalized_question = str(question or "").strip().lower()
    if not normalized_question:
        return 0.05
    text = " ".join(
        part
        for part in (
            chunk.citation_label,
            chunk.section_title,
            chunk.snippet,
            chunk.text,
        )
        if str(part or "").strip()
    ).lower()
    if not text:
        return 0.0
    query_tokens = {token.lower() for token in _QUERY_TOKEN_RE.findall(normalized_question)}
    overlap = sum(1 for token in query_tokens if token in text)
    coverage = (overlap / max(len(query_tokens), 1)) * 1.6
    phrase_bonus = 1.0 if normalized_question in text else 0.0
    return coverage + phrase_bonus


def _dedupe_ranked_context_chunks(
    scored_chunks: list[_ScoredContextChunk],
    *,
    limit: int,
) -> list[TrainingAiContextChunk]:
    ordered = sorted(
        scored_chunks,
        key=lambda item: (item.score, item.priority, len(item.chunk.text or "")),
        reverse=True,
    )
    unique_chunks: list[TrainingAiContextChunk] = []
    seen_keys: set[tuple[str, str, str]] = set()
    for scored in ordered:
        chunk = scored.chunk
        signature = (
            str(chunk.content_slug or "").strip(),
            str(chunk.citation_label or "").strip(),
            str(chunk.text or "").strip(),
        )
        if signature in seen_keys:
            continue
        seen_keys.add(signature)
        unique_chunks.append(chunk)
        if len(unique_chunks) >= limit:
            break
    return unique_chunks


def _flatten_message_content(value) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        chunks: list[str] = []
        for item in value:
            if isinstance(item, str):
                chunks.append(item.strip())
                continue
            if not isinstance(item, dict):
                continue
            raw_text = ""
            if item.get("type") == "text":
                raw_text = str(item.get("text") or "").strip()
            else:
                raw_text = str(item.get("content") or item.get("text") or "").strip()
            if raw_text:
                chunks.append(raw_text)
        return "\n".join(chunk for chunk in chunks if chunk).strip()
    return str(value or "").strip()


def _context_chunk_from_match(match) -> TrainingAiContextChunk:
    chunk = match.chunk
    content_item = chunk.content_item
    return TrainingAiContextChunk(
        content_slug=content_item.slug,
        content_name=content_item.name,
        section_title=chunk.section_title,
        citation_label=chunk.citation_label,
        text=chunk.chunk_text,
        snippet=chunk.snippet,
        source_url="",
    )


def _clean_text(value: str) -> str:
    return " ".join(str(value or "").split()).strip()


def _signing_secret() -> str:
    return str(getattr(settings, "TRAINING_JUPYTERHUB_SHARED_SECRET", "") or "").strip()


def training_jupyter_ai_proxy_token_grace_seconds() -> int:
    raw_value = int(getattr(settings, "TRAINING_JUPYTER_SESSION_API_TOKEN_GRACE_SECONDS", 30 * 24 * 60 * 60) or 0)
    return max(0, min(raw_value, 90 * 24 * 60 * 60))
