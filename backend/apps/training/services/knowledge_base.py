from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
import re
from typing import Iterable, Sequence

from django.conf import settings
from django.db import DatabaseError, connection
from django.utils import timezone

from apps.training.models import TrainingContentItem, TrainingKnowledgeChunk


_WHITESPACE_RE = re.compile(r"\s+")
_TOKEN_RE = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_\-']+")
_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+(?P<title>.+?)\s*$")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class TrainingKnowledgeMatch:
    chunk: TrainingKnowledgeChunk
    score: float
    lexical_score: float
    semantic_score: float


def training_ai_vector_dimensions() -> int:
    raw = int(getattr(settings, "TRAINING_AI_VECTOR_DIMENSIONS", 256) or 256)
    return max(32, min(raw, 1024))


def training_ai_index_chunk_size() -> int:
    raw = int(getattr(settings, "TRAINING_AI_INDEX_CHUNK_SIZE", 900) or 900)
    return max(250, min(raw, 4000))


def training_ai_index_chunk_overlap() -> int:
    raw = int(getattr(settings, "TRAINING_AI_INDEX_CHUNK_OVERLAP", 120) or 120)
    return max(0, min(raw, 1200))


def build_training_content_source_text(content_item: TrainingContentItem) -> str:
    parts = [
        str(content_item.name or "").strip(),
        str(content_item.description or "").strip(),
        str(content_item.body_markdown or "").strip(),
    ]
    combined = "\n\n".join(part for part in parts if part)
    return _normalize_whitespace(combined)


def build_training_query_embedding(text: str) -> list[float]:
    return build_demo_embedding(text, dimensions=training_ai_vector_dimensions())


def build_demo_embedding(text: str, *, dimensions: int) -> list[float]:
    if dimensions <= 0:
        return []

    tokens = _tokenize(text)
    if not tokens:
        return [0.0] * dimensions

    vector = [0.0] * dimensions
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = digest[0] % dimensions
        sign = 1.0 if digest[1] % 2 == 0 else -1.0
        weight = 1.0 + min(len(token), 12) / 12.0
        vector[index] += sign * weight

    norm = math.sqrt(sum(component * component for component in vector))
    if norm <= 0:
        return [0.0] * dimensions
    return [round(component / norm, 8) for component in vector]


def ensure_training_knowledge_index_for_items(content_items: Iterable[TrainingContentItem]) -> None:
    for content_item in content_items:
        ensure_training_content_indexed(content_item)


def deactivate_training_content_index(content_item: TrainingContentItem) -> int:
    deactivated = content_item.knowledge_chunks.filter(is_active=True).update(is_active=False, updated_at=timezone.now())
    if content_item.knowledge_indexed_at is not None:
        content_item.knowledge_indexed_at = None
        TrainingContentItem.objects.filter(pk=content_item.pk).update(knowledge_indexed_at=None)
    return deactivated


def ensure_training_content_indexed(content_item: TrainingContentItem) -> list[TrainingKnowledgeChunk]:
    source_text = build_training_content_source_text(content_item)
    if not source_text:
        deactivate_training_content_index(content_item)
        return []

    source_checksum = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
    existing_chunks = list(
        content_item.knowledge_chunks.filter(
            source_checksum=source_checksum,
            is_active=True,
        ).order_by("chunk_index", "id")
    )
    if existing_chunks:
        _touch_training_content_index(content_item)
        return existing_chunks

    content_item.knowledge_chunks.all().delete()
    chunk_specs = _build_chunk_specs(
        text=source_text,
        chunk_size=training_ai_index_chunk_size(),
        chunk_overlap=training_ai_index_chunk_overlap(),
    )
    if not chunk_specs:
        return []

    chunks_to_create: list[TrainingKnowledgeChunk] = []
    for chunk_index, chunk_spec in enumerate(chunk_specs):
        chunk_text = chunk_spec["text"]
        embedding = build_demo_embedding(chunk_text, dimensions=training_ai_vector_dimensions())
        chunks_to_create.append(
            TrainingKnowledgeChunk(
                content_item=content_item,
                chunk_index=chunk_index,
                section_title=chunk_spec["sectionTitle"],
                citation_label=chunk_spec["citationLabel"],
                chunk_text=chunk_text,
                snippet=_build_snippet(chunk_text),
                source_checksum=source_checksum,
                chunk_checksum=hashlib.sha256(chunk_text.encode("utf-8")).hexdigest(),
                token_count=len(_tokenize(chunk_text)),
                embedding_vector=embedding,
                embedding_model="demo-hash-v1",
                embedding_dimensions=len(embedding),
                is_active=True,
            )
        )

    created_chunks = TrainingKnowledgeChunk.objects.bulk_create(chunks_to_create)
    _sync_pgvector_embeddings(created_chunks)
    _touch_training_content_index(content_item)
    return list(
        content_item.knowledge_chunks.filter(
            source_checksum=source_checksum,
            is_active=True,
        ).order_by("chunk_index", "id")
    )


def retrieve_training_knowledge_matches(
    *,
    content_items: Sequence[TrainingContentItem],
    query: str,
    limit: int,
    preferred_content_item_id: int | None = None,
) -> list[TrainingKnowledgeMatch]:
    eligible_items = [item for item in content_items if build_training_content_source_text(item)]
    if not eligible_items:
        return []

    ensure_training_knowledge_index_for_items(eligible_items)
    content_item_ids = [item.id for item in eligible_items]
    queryset = (
        TrainingKnowledgeChunk.objects.select_related("content_item", "content_item__course")
        .filter(content_item_id__in=content_item_ids, is_active=True)
        .order_by("content_item_id", "chunk_index", "id")
    )
    chunks = list(queryset)
    if not chunks:
        return []

    query_text = _normalize_whitespace(query)
    query_vector = build_training_query_embedding(query_text)

    chunks_by_id = {chunk.id: chunk for chunk in chunks}
    ranked_chunk_ids = _rank_chunks_by_pgvector(
        content_item_ids=content_item_ids,
        query_vector=query_vector,
        limit=max(limit * 3, limit),
    )
    ranked_candidates = [chunks_by_id[chunk_id] for chunk_id in ranked_chunk_ids if chunk_id in chunks_by_id]
    if not ranked_candidates:
        ranked_candidates = chunks

    query_tokens = set(_tokenize(query_text))
    matches: list[TrainingKnowledgeMatch] = []
    for chunk in ranked_candidates:
        lexical_score = _lexical_score(query_tokens, chunk.chunk_text, chunk.section_title)
        semantic_score = _cosine_similarity(query_vector, _coerce_embedding_vector(chunk.embedding_vector))
        preferred_bonus = 0.12 if preferred_content_item_id and chunk.content_item_id == preferred_content_item_id else 0.0
        score = semantic_score * 0.72 + lexical_score * 0.28 + preferred_bonus
        if not query_text:
            score = preferred_bonus + (0.03 / max(1, chunk.chunk_index + 1))
        matches.append(
            TrainingKnowledgeMatch(
                chunk=chunk,
                score=score,
                lexical_score=lexical_score,
                semantic_score=semantic_score,
            )
        )

    matches.sort(
        key=lambda item: (
            item.score,
            item.semantic_score,
            item.lexical_score,
            -item.chunk.chunk_index,
        ),
        reverse=True,
    )
    return matches[:limit]


def _build_chunk_specs(*, text: str, chunk_size: int, chunk_overlap: int) -> list[dict[str, str]]:
    sections = _split_markdown_sections(text)
    chunk_specs: list[dict[str, str]] = []
    for section_title, section_text in sections:
        paragraphs = _split_into_paragraph_units(section_text, chunk_size=chunk_size)
        current = ""
        for paragraph in paragraphs:
            next_candidate = paragraph if not current else f"{current}\n\n{paragraph}"
            if current and len(next_candidate) > chunk_size:
                chunk_specs.append(
                    {
                        "sectionTitle": section_title,
                        "citationLabel": section_title or "Training section",
                        "text": current,
                    }
                )
                current = _with_overlap(previous_text=current, next_text=paragraph, overlap=chunk_overlap)
                continue
            current = next_candidate
        if current:
            chunk_specs.append(
                {
                    "sectionTitle": section_title,
                    "citationLabel": section_title or "Training section",
                    "text": current,
                }
            )
    return [spec for spec in chunk_specs if spec["text"].strip()]


def _split_markdown_sections(text: str) -> list[tuple[str, str]]:
    lines = text.splitlines()
    sections: list[tuple[str, list[str]]] = []
    current_title = ""
    current_lines: list[str] = []
    for line in lines:
        heading_match = _HEADING_RE.match(line)
        if heading_match:
            if current_lines:
                sections.append((current_title, current_lines))
            current_title = _normalize_whitespace(heading_match.group("title"))
            current_lines = []
            continue
        current_lines.append(line)
    if current_lines:
        sections.append((current_title, current_lines))

    if not sections:
        return [("", text)]
    return [
        (title, _normalize_whitespace("\n".join(section_lines)))
        for title, section_lines in sections
        if _normalize_whitespace("\n".join(section_lines))
    ]


def _split_into_paragraph_units(text: str, *, chunk_size: int) -> list[str]:
    paragraphs = [
        _normalize_whitespace(paragraph)
        for paragraph in re.split(r"\n\s*\n", text)
        if _normalize_whitespace(paragraph)
    ]
    units: list[str] = []
    for paragraph in paragraphs:
        if len(paragraph) <= chunk_size:
            units.append(paragraph)
            continue
        sentences = [part.strip() for part in _SENTENCE_SPLIT_RE.split(paragraph) if part.strip()]
        if not sentences:
            units.append(paragraph[:chunk_size])
            continue
        current = ""
        for sentence in sentences:
            candidate = sentence if not current else f"{current} {sentence}"
            if current and len(candidate) > chunk_size:
                units.append(current)
                current = sentence
                continue
            current = candidate
        if current:
            units.append(current)
    return units


def _with_overlap(*, previous_text: str, next_text: str, overlap: int) -> str:
    if overlap <= 0:
        return next_text
    normalized_previous = _normalize_whitespace(previous_text)
    tail = normalized_previous[-overlap:].strip()
    if not tail:
        return next_text
    return f"{tail}\n\n{next_text}"


def _build_snippet(text: str, *, max_length: int = 180) -> str:
    normalized = _normalize_whitespace(text)
    if len(normalized) <= max_length:
        return normalized
    return normalized[: max_length - 1].rstrip() + "..."


def _touch_training_content_index(content_item: TrainingContentItem) -> None:
    content_item.knowledge_indexed_at = timezone.now()
    TrainingContentItem.objects.filter(pk=content_item.pk).update(knowledge_indexed_at=content_item.knowledge_indexed_at)


def _normalize_whitespace(value: str) -> str:
    return _WHITESPACE_RE.sub(" ", str(value or "")).strip()


def _tokenize(text: str) -> list[str]:
    return [token.lower() for token in _TOKEN_RE.findall(str(text or "").lower())]


def _lexical_score(query_tokens: set[str], chunk_text: str, section_title: str) -> float:
    if not query_tokens:
        return 0.0
    chunk_tokens = set(_tokenize(chunk_text))
    if not chunk_tokens:
        return 0.0
    overlap = len(query_tokens & chunk_tokens) / max(1, len(query_tokens))
    title_tokens = set(_tokenize(section_title))
    title_overlap = len(query_tokens & title_tokens) / max(1, len(query_tokens)) if title_tokens else 0.0
    return min(1.0, overlap * 0.8 + title_overlap * 0.2)


def _coerce_embedding_vector(value: object) -> list[float]:
    if not isinstance(value, list):
        return []
    vector: list[float] = []
    for item in value:
        try:
            vector.append(float(item))
        except (TypeError, ValueError):
            vector.append(0.0)
    return vector


def _cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if not left or not right:
        return 0.0
    dimension = min(len(left), len(right))
    if dimension <= 0:
        return 0.0
    numerator = sum(float(left[index]) * float(right[index]) for index in range(dimension))
    left_norm = math.sqrt(sum(float(left[index]) * float(left[index]) for index in range(dimension)))
    right_norm = math.sqrt(sum(float(right[index]) * float(right[index]) for index in range(dimension)))
    if left_norm <= 0 or right_norm <= 0:
        return 0.0
    return max(-1.0, min(1.0, numerator / (left_norm * right_norm)))


def _rank_chunks_by_pgvector(*, content_item_ids: list[int], query_vector: list[float], limit: int) -> list[int]:
    if not _pgvector_enabled() or not content_item_ids or not query_vector:
        return []
    vector_literal = "[" + ",".join(f"{value:.8f}" for value in query_vector) + "]"
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id
                FROM training_knowledge_chunk
                WHERE is_active = TRUE
                  AND content_item_id = ANY(%s)
                  AND embedding_vector_pg IS NOT NULL
                ORDER BY embedding_vector_pg <=> %s::vector ASC
                LIMIT %s
                """,
                [content_item_ids, vector_literal, limit],
            )
            return [int(row[0]) for row in cursor.fetchall()]
    except DatabaseError:
        return []


def _sync_pgvector_embeddings(chunks: Sequence[TrainingKnowledgeChunk]) -> None:
    if not _pgvector_enabled() or not chunks:
        return
    rows = []
    for chunk in chunks:
        vector = _coerce_embedding_vector(chunk.embedding_vector)
        if not vector:
            continue
        vector_literal = "[" + ",".join(f"{value:.8f}" for value in vector) + "]"
        rows.append((vector_literal, chunk.id))
    if not rows:
        return
    try:
        with connection.cursor() as cursor:
            cursor.executemany(
                "UPDATE training_knowledge_chunk SET embedding_vector_pg = %s::vector WHERE id = %s",
                rows,
            )
    except DatabaseError:
        return


def _pgvector_enabled() -> bool:
    if connection.vendor != "postgresql":
        return False
    return bool(getattr(settings, "TRAINING_AI_PGVECTOR_ENABLED", True))
