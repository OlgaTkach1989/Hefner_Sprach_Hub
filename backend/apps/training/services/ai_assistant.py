from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.training.models import (
    TrainingAiConversation,
    TrainingAiMessage,
    TrainingAiQuizAttempt,
    TrainingContentItem,
    TrainingCourseRoleAssignment,
)
from apps.training.services.access import content_item_is_visible_to_user
from apps.training.services.ai_provider import (
    TrainingAiContextChunk,
    TrainingAiProviderError,
    build_default_follow_up_prompts,
    get_training_ai_provider,
)
from apps.training.services.knowledge_base import (
    TrainingKnowledgeMatch,
    retrieve_training_knowledge_matches,
)


class TrainingAiError(RuntimeError):
    pass


@dataclass(frozen=True)
class TrainingAiAskResult:
    conversation: TrainingAiConversation
    assistant_message: TrainingAiMessage
    user_message: TrainingAiMessage
    response_payload: dict[str, Any]


@dataclass(frozen=True)
class TrainingAiQuizSubmissionResult:
    quiz_attempt: TrainingAiQuizAttempt
    response_payload: dict[str, Any]


def training_ai_enabled() -> bool:
    return bool(getattr(settings, "TRAINING_AI_ENABLED", True))


def training_ai_question_max_chars() -> int:
    raw = int(getattr(settings, "TRAINING_AI_QUESTION_MAX_CHARS", 1200) or 1200)
    return max(80, min(raw, 5000))


def build_or_get_training_ai_conversation(
    *,
    user,
    content_item: TrainingContentItem,
    conversation_public_id: str = "",
) -> TrainingAiConversation:
    if conversation_public_id:
        conversation = (
            TrainingAiConversation.objects.select_related("content_item")
            .filter(public_id=conversation_public_id, user=user)
            .first()
        )
        if conversation is not None:
            if conversation.content_item_id and conversation.content_item_id != content_item.id:
                raise TrainingAiError("Conversation does not belong to the selected content item.")
            return conversation

    conversation = (
        TrainingAiConversation.objects.select_related("content_item")
        .filter(user=user, content_item=content_item, status=TrainingAiConversation.Status.ACTIVE)
        .order_by("-last_activity_at", "-id")
        .first()
    )
    if conversation is not None:
        return conversation

    return TrainingAiConversation.objects.create(
        user=user,
        content_item=content_item,
        title=content_item.name[:180],
        status=TrainingAiConversation.Status.ACTIVE,
    )


def list_training_ai_messages_for_user(*, user, content_item: TrainingContentItem) -> tuple[TrainingAiConversation | None, list[TrainingAiMessage]]:
    conversation = (
        TrainingAiConversation.objects.select_related("content_item")
        .filter(user=user, content_item=content_item, status=TrainingAiConversation.Status.ACTIVE)
        .order_by("-last_activity_at", "-id")
        .first()
    )
    if conversation is None:
        return None, []
    messages = list(conversation.messages.select_related("content_item").order_by("created_at", "id"))
    return conversation, messages


@transaction.atomic
def ask_training_ai(
    *,
    user,
    content_item: TrainingContentItem,
    question: str,
    prompt_type: str,
    conversation_public_id: str = "",
) -> TrainingAiAskResult:
    if not training_ai_enabled():
        raise TrainingAiError("AI assistant is disabled.")

    normalized_question = str(question or "").strip()
    if not normalized_question:
        raise TrainingAiError("Question is required.")
    if len(normalized_question) > training_ai_question_max_chars():
        raise TrainingAiError("Question is too long.")

    conversation = build_or_get_training_ai_conversation(
        user=user,
        content_item=content_item,
        conversation_public_id=conversation_public_id,
    )
    candidate_items = _candidate_content_items_for_ai(user=user, content_item=content_item)
    matches = retrieve_training_knowledge_matches(
        content_items=candidate_items,
        query=normalized_question,
        limit=int(getattr(settings, "TRAINING_AI_MAX_CONTEXT_CHUNKS", 5) or 5),
        preferred_content_item_id=content_item.id,
    )
    context_chunks = [_context_chunk_from_match(match) for match in matches]

    provider = get_training_ai_provider()
    user_message = TrainingAiMessage.objects.create(
        conversation=conversation,
        content_item=content_item,
        role=TrainingAiMessage.Role.USER,
        prompt_type=_coerce_prompt_type(prompt_type),
        body=normalized_question,
        provider=provider.provider_name,
        model_name=provider.model_name,
        resolution_status=TrainingAiMessage.ResolutionStatus.RESOLVED,
    )

    try:
        answer = provider.generate_answer(
            content_name=content_item.name,
            question=normalized_question,
            prompt_type=_coerce_prompt_type(prompt_type),
            context_chunks=context_chunks,
        )
    except TrainingAiProviderError as exc:
        raise TrainingAiError(str(exc)) from exc

    citations = [_citation_payload_from_match(match) for match in matches]
    resolution_status = _coerce_resolution_status(answer.resolution_status)
    escalation_payload = _build_escalation_payload(content_item=content_item) if resolution_status == TrainingAiMessage.ResolutionStatus.ESCALATE else None
    response_payload = {
        "shortAnswer": answer.short_answer,
        "detailedAnswer": answer.detailed_answer,
        "citations": citations,
        "followUpPrompts": answer.follow_up_prompts,
        "resolutionStatus": resolution_status,
        "needsEscalation": escalation_payload is not None,
        "escalation": escalation_payload,
        "provider": provider.provider_name,
        "model": provider.model_name,
    }
    assistant_message = TrainingAiMessage.objects.create(
        conversation=conversation,
        content_item=content_item,
        role=TrainingAiMessage.Role.ASSISTANT,
        prompt_type=_coerce_prompt_type(prompt_type),
        body=answer.short_answer or answer.detailed_answer,
        payload=response_payload,
        citations=citations,
        provider=provider.provider_name,
        model_name=provider.model_name,
        resolution_status=resolution_status,
    )
    _touch_conversation(conversation=conversation, question=normalized_question)
    return TrainingAiAskResult(
        conversation=conversation,
        assistant_message=assistant_message,
        user_message=user_message,
        response_payload=response_payload,
    )


@transaction.atomic
def generate_training_ai_quiz(
    *,
    user,
    content_item: TrainingContentItem,
    conversation_public_id: str = "",
    question_count: int = 4,
) -> TrainingAiQuizAttempt:
    if not training_ai_enabled():
        raise TrainingAiError("AI assistant is disabled.")

    conversation = build_or_get_training_ai_conversation(
        user=user,
        content_item=content_item,
        conversation_public_id=conversation_public_id,
    )
    matches = retrieve_training_knowledge_matches(
        content_items=[content_item],
        query=content_item.name + " " + (content_item.description or ""),
        limit=max(3, min(question_count + 1, 6)),
        preferred_content_item_id=content_item.id,
    )
    context_chunks = [_context_chunk_from_match(match) for match in matches]
    provider = get_training_ai_provider()
    quiz = provider.generate_quiz(
        content_name=content_item.name,
        context_chunks=context_chunks,
        question_count=max(3, min(question_count, 5)),
    )
    quiz_payload = {
        "title": quiz.title,
        "questions": [
            {
                "questionId": question.question_id,
                "prompt": question.prompt,
                "options": question.options,
                "correctOptionId": question.correct_option_id,
                "explanation": question.explanation,
            }
            for question in quiz.questions
        ],
        "provider": provider.provider_name,
        "model": provider.model_name,
    }
    return TrainingAiQuizAttempt.objects.create(
        user=user,
        content_item=content_item,
        conversation=conversation,
        status=TrainingAiQuizAttempt.Status.GENERATED,
        title=quiz.title[:180],
        quiz_payload=quiz_payload,
        max_score=len(quiz.questions),
    )


@transaction.atomic
def submit_training_ai_quiz(*, user, quiz_public_id: str, answers: list[dict[str, str]]) -> TrainingAiQuizSubmissionResult:
    quiz_attempt = (
        TrainingAiQuizAttempt.objects.select_related("content_item", "conversation")
        .filter(public_id=quiz_public_id, user=user)
        .first()
    )
    if quiz_attempt is None:
        raise TrainingAiError("Quiz was not found.")
    if quiz_attempt.status != TrainingAiQuizAttempt.Status.GENERATED:
        raise TrainingAiError("Quiz has already been submitted.")

    raw_questions = list((quiz_attempt.quiz_payload or {}).get("questions") or [])
    if not raw_questions:
        raise TrainingAiError("Quiz payload is empty.")

    answers_by_question = {
        str(answer.get("questionId") or "").strip(): str(answer.get("selectedOptionId") or "").strip()
        for answer in answers
        if str(answer.get("questionId") or "").strip()
    }

    scored_questions = []
    correct_answers_count = 0
    for question in raw_questions:
        question_id = str(question.get("questionId") or "").strip()
        selected_option_id = answers_by_question.get(question_id, "")
        correct_option_id = str(question.get("correctOptionId") or "").strip()
        is_correct = bool(selected_option_id and selected_option_id == correct_option_id)
        if is_correct:
            correct_answers_count += 1
        scored_questions.append(
            {
                "questionId": question_id,
                "selectedOptionId": selected_option_id,
                "correctOptionId": correct_option_id,
                "isCorrect": is_correct,
            }
        )

    quiz_attempt.status = TrainingAiQuizAttempt.Status.COMPLETED
    quiz_attempt.submitted_answers = scored_questions
    quiz_attempt.score = correct_answers_count
    quiz_attempt.correct_answers_count = correct_answers_count
    quiz_attempt.max_score = len(raw_questions)
    quiz_attempt.submitted_at = timezone.now()
    quiz_attempt.save(
        update_fields=(
            "status",
            "submitted_answers",
            "score",
            "correct_answers_count",
            "max_score",
            "submitted_at",
            "updated_at",
        )
    )

    response_payload = build_training_ai_quiz_response_payload(quiz_attempt)
    return TrainingAiQuizSubmissionResult(quiz_attempt=quiz_attempt, response_payload=response_payload)


def build_training_ai_quiz_response_payload(quiz_attempt: TrainingAiQuizAttempt) -> dict[str, Any]:
    raw_questions = list((quiz_attempt.quiz_payload or {}).get("questions") or [])
    scored_by_question = {
        str(item.get("questionId") or "").strip(): item
        for item in (quiz_attempt.submitted_answers or [])
    }
    response_questions = []
    for raw_question in raw_questions:
        question_id = str(raw_question.get("questionId") or "").strip()
        question_payload = {
            "questionId": question_id,
            "prompt": str(raw_question.get("prompt") or "").strip(),
            "options": raw_question.get("options") or [],
            "explanation": str(raw_question.get("explanation") or "").strip(),
        }
        if quiz_attempt.status == TrainingAiQuizAttempt.Status.COMPLETED:
            scored = scored_by_question.get(question_id, {})
            question_payload.update(
                {
                    "selectedOptionId": str(scored.get("selectedOptionId") or "").strip(),
                    "correctOptionId": str(scored.get("correctOptionId") or "").strip(),
                    "isCorrect": bool(scored.get("isCorrect")),
                }
            )
        response_questions.append(question_payload)

    return {
        "publicId": str(quiz_attempt.public_id),
        "status": quiz_attempt.status,
        "title": str(quiz_attempt.title or (quiz_attempt.quiz_payload or {}).get("title") or "").strip(),
        "contentSlug": quiz_attempt.content_item.slug,
        "contentName": quiz_attempt.content_item.name,
        "score": quiz_attempt.score,
        "maxScore": quiz_attempt.max_score,
        "correctAnswersCount": quiz_attempt.correct_answers_count,
        "submittedAt": quiz_attempt.submitted_at.isoformat() if quiz_attempt.submitted_at else None,
        "questions": response_questions,
    }


def build_training_ai_conversation_payload(conversation: TrainingAiConversation, messages: list[TrainingAiMessage]) -> dict[str, Any]:
    return {
        "conversation": {
            "publicId": str(conversation.public_id),
            "title": conversation.title,
            "status": conversation.status,
            "contentSlug": conversation.content_item.slug if conversation.content_item_id else None,
            "contentName": conversation.content_item.name if conversation.content_item_id else None,
            "lastActivityAt": conversation.last_activity_at.isoformat(),
        },
        "messages": [
            {
                "id": message.id,
                "role": message.role,
                "promptType": message.prompt_type,
                "body": message.body,
                "payload": message.payload if message.role == TrainingAiMessage.Role.ASSISTANT else None,
                "citations": message.citations if message.role == TrainingAiMessage.Role.ASSISTANT else [],
                "resolutionStatus": message.resolution_status,
                "createdAt": message.created_at.isoformat(),
            }
            for message in messages
        ],
    }


def _candidate_content_items_for_ai(*, user, content_item: TrainingContentItem) -> list[TrainingContentItem]:
    candidate_items = [content_item]
    cross_references = getattr(content_item, "_prefetched_objects_cache", {}).get("outgoing_references")
    if cross_references is None:
        cross_references = list(content_item.outgoing_references.select_related("to_item"))
    for reference in cross_references:
        if content_item_is_visible_to_user(reference.to_item, user):
            candidate_items.append(reference.to_item)
    unique_items: list[TrainingContentItem] = []
    seen_ids: set[int] = set()
    for item in candidate_items:
        if item.id in seen_ids:
            continue
        seen_ids.add(item.id)
        unique_items.append(item)
    return unique_items


def _context_chunk_from_match(match: TrainingKnowledgeMatch) -> TrainingAiContextChunk:
    return TrainingAiContextChunk(
        content_slug=match.chunk.content_item.slug,
        content_name=match.chunk.content_item.name,
        section_title=match.chunk.section_title,
        citation_label=match.chunk.citation_label,
        text=_sanitize_context_text(match.chunk.chunk_text),
        snippet=match.chunk.snippet,
        source_url=match.chunk.content_item.source_url,
    )


def _citation_payload_from_match(match: TrainingKnowledgeMatch) -> dict[str, Any]:
    return {
        "contentSlug": match.chunk.content_item.slug,
        "contentName": match.chunk.content_item.name,
        "sectionTitle": match.chunk.section_title,
        "citationLabel": match.chunk.citation_label,
        "quoteSnippet": _build_quote_snippet(match.chunk.chunk_text),
        "sourceUrl": match.chunk.content_item.source_url,
    }


def _build_quote_snippet(text: str, *, max_words: int = 24) -> str:
    words = str(text or "").split()
    if len(words) <= max_words:
        return " ".join(words)
    return " ".join(words[:max_words]).rstrip() + " ..."


def _sanitize_context_text(text: str) -> str:
    sanitized_lines = []
    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        lowered = line.lower()
        if lowered.startswith("system:") or lowered.startswith("assistant:") or lowered.startswith("ignore previous"):
            continue
        sanitized_lines.append(line)
    return "\n".join(line for line in sanitized_lines if line).strip()


def _touch_conversation(*, conversation: TrainingAiConversation, question: str) -> None:
    conversation.last_user_prompt = str(question or "")[:255]
    if not conversation.title:
        conversation.title = str(question or "")[:180]
    conversation.save(update_fields=("last_user_prompt", "title", "last_activity_at", "updated_at"))


def _build_escalation_payload(*, content_item: TrainingContentItem) -> dict[str, Any]:
    assignment = (
        TrainingCourseRoleAssignment.objects.select_related("course")
        .filter(course=content_item.course, role=TrainingCourseRoleAssignment.Role.OWNER)
        .order_by("-is_primary", "response_sla_hours", "id")
        .first()
    )
    if assignment is None:
        return {
            "targetRole": "support",
            "responseSlaHours": 24,
            "message": "Escalate this question to support or the temporary course owner queue.",
        }
    return {
        "targetRole": "course_owner",
        "responseSlaHours": assignment.response_sla_hours,
        "courseSlug": assignment.course.slug,
        "message": "The assistant suggests escalation to the course owner because approved context was insufficient.",
    }


def _coerce_prompt_type(prompt_type: str) -> str:
    allowed = {choice for choice, _label in TrainingAiMessage.PromptType.choices}
    normalized = str(prompt_type or "").strip()
    return normalized if normalized in allowed else TrainingAiMessage.PromptType.ASK


def _coerce_resolution_status(value: str) -> str:
    allowed = {choice for choice, _label in TrainingAiMessage.ResolutionStatus.choices}
    normalized = str(value or "").strip()
    return normalized if normalized in allowed else TrainingAiMessage.ResolutionStatus.PARTIAL
