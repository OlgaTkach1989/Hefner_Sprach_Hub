from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Sequence
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.db import transaction

from apps.online.models import OnlineCohort, OnlineSession

DEFAULT_SESSION_DURATION = timedelta(hours=2)
DEFAULT_SESSION_INTERVAL = timedelta(days=7)
DEFAULT_SESSION_START_TIME = time(hour=18, minute=0)
MAX_REASONABLE_SESSION_DURATION = timedelta(hours=12)


class SessionGenerationError(ValueError):
    pass


@dataclass(slots=True)
class SessionGenerationResult:
    cohort_id: int
    target_count: int
    existing_count: int
    created_count: int

    @property
    def final_count(self) -> int:
        return self.existing_count + self.created_count


@dataclass(slots=True)
class BuilderSessionSeedInput:
    title: str
    description: str
    starts_at: datetime
    ends_at: datetime


@dataclass(slots=True)
class BuilderSessionSeedResult:
    cohort_id: int
    course_id: int
    existing_count: int
    created_sessions: list[OnlineSession]
    remaining_slots: int

    @property
    def created_count(self) -> int:
        return len(self.created_sessions)


def _cohort_zoneinfo(cohort: OnlineCohort) -> ZoneInfo:
    try:
        return ZoneInfo((cohort.timezone or "Europe/Berlin").strip() or "Europe/Berlin")
    except ZoneInfoNotFoundError:
        return ZoneInfo("Europe/Berlin")


def _normalize_duration(duration: timedelta) -> timedelta:
    if duration.total_seconds() <= 0:
        return DEFAULT_SESSION_DURATION
    if duration > MAX_REASONABLE_SESSION_DURATION:
        return DEFAULT_SESSION_DURATION
    return duration


def _normalize_interval(interval: timedelta) -> timedelta:
    return interval if interval.total_seconds() > 0 else DEFAULT_SESSION_INTERVAL


def _initial_session_start(cohort: OnlineCohort) -> datetime:
    if not cohort.start_date:
        raise SessionGenerationError("Set cohort start date before generating sessions for an empty cohort.")
    return datetime.combine(cohort.start_date, DEFAULT_SESSION_START_TIME, tzinfo=_cohort_zoneinfo(cohort))


def _lesson_section_summary(section) -> str:
    title = str(section.title or "").strip()
    description = str(section.description or "").strip()
    if description:
        return f"{title}: {description}" if title else description
    prefetched_items = getattr(section, "_prefetched_objects_cache", {}).get("items")
    if prefetched_items is not None:
        item_count = sum(1 for item in prefetched_items if getattr(item, "is_active", False))
    else:
        item_count = section.items.filter(is_active=True).count()
    if title and item_count:
        return f"{title}: {item_count} asset{'s' if item_count != 1 else ''}"
    return title


def _lesson_blueprints_for_course(cohort: OnlineCohort) -> list[tuple[str, str]]:
    lessons = list(
        cohort.course.structured_lessons.filter(is_active=True)
        .select_related("module")
        .prefetch_related("sections__items")
        .order_by("module__sort_order", "module__id", "sort_order", "id")
    )
    blueprints: list[tuple[str, str]] = []
    for lesson in lessons:
        lesson_title = str(lesson.title or "").strip()
        lesson_description = str(lesson.description or "").strip()
        active_sections = list(lesson.sections.filter(is_active=True).order_by("sort_order", "id"))
        section_summary = " | ".join(
            summary
            for summary in (
                _lesson_section_summary(section)
                for section in active_sections
            )
            if summary
        )
        if lesson_description and section_summary:
            composed_description = f"{lesson_description} {section_summary}"
        else:
            composed_description = lesson_description or section_summary
        if not lesson_title:
            lesson_title = (
                next(
                    (
                        str(section.title or "").strip()
                        for section in active_sections
                        if str(section.title or "").strip()
                    ),
                    "",
                )
                or ""
            )
        blueprints.append((lesson_title, composed_description))
    return blueprints


def _default_session_copy(*, lesson_blueprints: Sequence[tuple[str, str]], slot_index: int) -> tuple[str, str]:
    if slot_index - 1 < len(lesson_blueprints):
        lesson_title, lesson_description = lesson_blueprints[slot_index - 1]
        if lesson_title:
            return lesson_title, lesson_description
    return f"Lesson {slot_index}", "Live lesson with guided walkthrough and follow-up discussion."


def create_builder_sessions_for_cohort(
    *,
    cohort: OnlineCohort,
    sessions: Sequence[BuilderSessionSeedInput],
) -> BuilderSessionSeedResult:
    if not sessions:
        raise SessionGenerationError("Add at least one session before saving the delivery schedule.")

    existing_sessions = list(cohort.sessions.order_by("sort_order", "starts_at", "id"))
    existing_count = len(existing_sessions)
    target_count = max(1, int(cohort.course.lessons_count or 0))
    remaining_slots = max(0, target_count - existing_count)
    if remaining_slots <= 0:
        raise SessionGenerationError("This cohort already has the full lesson schedule.")
    if len(sessions) > remaining_slots:
        raise SessionGenerationError(
            f"You can create at most {remaining_slots} more session(s) for this course."
        )

    next_sort_order = (max((session.sort_order for session in existing_sessions), default=0) or 0) + 1
    lesson_blueprints = _lesson_blueprints_for_course(cohort)
    created_ids: list[int] = []

    with transaction.atomic():
        for offset, session_input in enumerate(sessions, start=1):
            slot_index = existing_count + offset
            default_title, default_description = _default_session_copy(
                lesson_blueprints=lesson_blueprints,
                slot_index=slot_index,
            )
            session = OnlineSession.objects.create(
                cohort=cohort,
                title=session_input.title.strip() or default_title,
                description=session_input.description.strip() or default_description,
                starts_at=session_input.starts_at,
                ends_at=session_input.ends_at,
                status=OnlineSession.STATUS_SCHEDULED,
                join_url="",
                sort_order=next_sort_order,
                is_completed=False,
            )
            created_ids.append(session.id)
            next_sort_order += 1

    created_sessions = list(
        OnlineSession.objects.select_related("cohort", "cohort__course", "cohort__teacher")
        .filter(id__in=created_ids)
        .order_by("sort_order", "starts_at", "id")
    )
    final_remaining_slots = max(0, target_count - (existing_count + len(created_sessions)))
    return BuilderSessionSeedResult(
        cohort_id=cohort.id,
        course_id=cohort.course_id,
        existing_count=existing_count,
        created_sessions=created_sessions,
        remaining_slots=final_remaining_slots,
    )


def generate_missing_sessions_for_cohort(cohort: OnlineCohort) -> SessionGenerationResult:
    target_count = max(1, int(cohort.course.lessons_count or 0))
    existing_sessions = list(cohort.sessions.order_by("sort_order", "starts_at", "id"))
    existing_count = len(existing_sessions)
    if existing_count >= target_count:
        return SessionGenerationResult(
            cohort_id=cohort.id,
            target_count=target_count,
            existing_count=existing_count,
            created_count=0,
        )

    if existing_sessions:
        last_session = existing_sessions[-1]
        next_sort_order = max(session.sort_order for session in existing_sessions) + 1
        duration = _normalize_duration(last_session.ends_at - last_session.starts_at)
        if len(existing_sessions) >= 2:
            interval = _normalize_interval(last_session.starts_at - existing_sessions[-2].starts_at)
        else:
            interval = DEFAULT_SESSION_INTERVAL
        next_start = last_session.starts_at + interval
    else:
        next_sort_order = 1
        duration = DEFAULT_SESSION_DURATION
        interval = DEFAULT_SESSION_INTERVAL
        next_start = _initial_session_start(cohort)

    sessions_to_create = []
    for index in range(existing_count + 1, target_count + 1):
        starts_at = next_start
        ends_at = starts_at + duration
        sessions_to_create.append(
            OnlineSession(
                cohort=cohort,
                title=f"Lektion {index}",
                description="Live-Unterricht mit Uebung und Feedback.",
                starts_at=starts_at,
                ends_at=ends_at,
                status=OnlineSession.STATUS_SCHEDULED,
                join_url="",
                sort_order=next_sort_order,
                is_completed=False,
            )
        )
        next_sort_order += 1
        next_start = next_start + interval

    with transaction.atomic():
        OnlineSession.objects.bulk_create(sessions_to_create)

    return SessionGenerationResult(
        cohort_id=cohort.id,
        target_count=target_count,
        existing_count=existing_count,
        created_count=len(sessions_to_create),
    )
