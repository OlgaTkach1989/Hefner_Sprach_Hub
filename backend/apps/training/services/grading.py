from __future__ import annotations

import ast
import hashlib
import json
import re
import shutil
import subprocess
import uuid
from dataclasses import dataclass
from decimal import Decimal
from html import escape
from pathlib import Path

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.training.models import (
    TrainingAuditEvent,
    TrainingGradebookEntry,
    TrainingGraderJob,
    TrainingLabSubmission,
    TrainingLabSubmissionArtifact,
    TrainingNotebookLabProfile,
)
from apps.training.services.audit import log_training_audit_event
from apps.training.services.jupyter_auth import build_training_jupyter_username
from apps.training.services.lab_repeatability import repeatable_lab_reentry_enabled

SAFE_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9._-]+$")


class TrainingGradingError(Exception):
    """Base error for grading flow."""


@dataclass(frozen=True)
class TrainingGradingResult:
    score: Decimal | None
    max_score: Decimal | None
    passed: bool | None
    feedback_markdown: str
    feedback_payload: dict[str, object]
    artifacts: list[dict[str, object]]
    result_payload: dict[str, object]


@dataclass(frozen=True)
class StoredSubmissionArtifactPayload:
    storage_path: str
    checksum: str
    size_bytes: int
    media_type: str
    metadata: dict[str, object]


def training_grader_runtime_enabled() -> bool:
    return bool(getattr(settings, "TRAINING_GRADER_RUNTIME_ENABLED", False))


def preview_lab_submission(
    *,
    content_item,
    notebook_upload: UploadedFile | None = None,
    response_text: str = "",
) -> dict[str, object]:
    if not training_grader_runtime_enabled():
        raise TrainingGradingError("Training grader runtime is disabled.")
    try:
        lab_profile = content_item.lab_profile
    except TrainingNotebookLabProfile.DoesNotExist as exc:
        raise TrainingGradingError("Notebook runtime profile is missing.") from exc
    if not lab_profile.is_active:
        raise TrainingGradingError("Notebook runtime profile is inactive.")
    if lab_profile.grader_backend == TrainingNotebookLabProfile.GraderBackend.NONE:
        raise TrainingGradingError("Notebook content does not have a configured grader backend.")

    config = dict(lab_profile.grader_config or {})
    mode = str(config.get("mode") or "demo").strip().lower()
    if mode != "custom_rules":
        raise TrainingGradingError("Notebook validation preview is only available for custom_rules assignments.")

    normalized_response_text = str(response_text or "").strip()
    if notebook_upload is None and not normalized_response_text:
        raise TrainingGradingError("Notebook upload or text answer is required.")

    if notebook_upload is not None:
        notebook_bytes = _read_uploaded_notebook_bytes(notebook_upload)
        notebook_payload = _read_notebook_payload_from_bytes(notebook_bytes)
        sources = _build_custom_rule_sources_from_notebook_payload(notebook_payload)
        submission_mode = TrainingLabSubmission.SubmissionMode.NOTEBOOK
    else:
        sources = _build_custom_rule_sources_from_text(normalized_response_text)
        submission_mode = TrainingLabSubmission.SubmissionMode.TEXT_ANSWER

    result = _build_custom_rules_result_from_sources(
        submission_mode=submission_mode,
        lab_profile=lab_profile,
        config=config,
        code_sources=sources["code_sources"],
        markdown_sources=sources["markdown_sources"],
        all_code=sources["all_code"],
        all_markdown=sources["all_markdown"],
        extracted_assignments=sources["extracted_assignments"],
        defined_functions=sources["defined_functions"],
        assigned_names=sources["assigned_names"],
        output_text=sources["output_text"],
        content_slug=content_item.slug,
    )
    return {
        "score": str(result.score) if result.score is not None else None,
        "maxScore": str(result.max_score) if result.max_score is not None else None,
        "passed": result.passed,
        "feedbackMarkdown": result.feedback_markdown,
        "feedbackPayload": result.feedback_payload,
    }


def create_lab_submission(
    *,
    user,
    content_item,
    notebook_upload: UploadedFile | None,
    response_text: str = "",
    client_checksum: str = "",
    launch_token=None,
) -> TrainingLabSubmission:
    if not training_grader_runtime_enabled():
        raise TrainingGradingError("Training grader runtime is disabled.")
    if content_item.content_kind != content_item.ContentKind.NOTEBOOK:
        raise TrainingGradingError("Only notebook content can be submitted for grading.")
    normalized_response_text = str(response_text or "").strip()
    if notebook_upload is None and not normalized_response_text:
        raise TrainingGradingError("Notebook upload or text answer is required.")

    try:
        lab_profile = content_item.lab_profile
    except TrainingNotebookLabProfile.DoesNotExist as exc:
        raise TrainingGradingError("Notebook runtime profile is missing.") from exc

    if not lab_profile.is_active:
        raise TrainingGradingError("Notebook runtime profile is inactive.")
    if lab_profile.grader_backend == TrainingNotebookLabProfile.GraderBackend.NONE:
        raise TrainingGradingError("Notebook content does not have a configured grader backend.")
    if lab_profile.max_attempts:
        gradebook_entry = (
            TrainingGradebookEntry.objects.filter(user=user, content_item=content_item)
            .only("attempts_count", "passed")
            .first()
        )
        attempts_count = gradebook_entry.attempts_count if gradebook_entry else 0
        if attempts_count >= lab_profile.max_attempts and not repeatable_lab_reentry_enabled(
            content_item=content_item,
            gradebook_entry=gradebook_entry,
        ):
            raise TrainingGradingError("Maximum number of notebook attempts has been reached.")

    canonical_notebook_path = _canonical_notebook_path(lab_profile)
    public_id = uuid.uuid4()
    attempt_number = TrainingLabSubmission.objects.filter(user=user, content_item=content_item).count() + 1
    stored_notebook = None
    submission_mode = TrainingLabSubmission.SubmissionMode.TEXT_ANSWER
    if notebook_upload is not None:
        stored_notebook = _store_uploaded_notebook_artifact(
            public_id=public_id,
            lab_profile=lab_profile,
            notebook_upload=notebook_upload,
            client_checksum=client_checksum,
        )
        submission_mode = TrainingLabSubmission.SubmissionMode.NOTEBOOK
    try:
        with transaction.atomic():
            submission = TrainingLabSubmission.objects.create(
                public_id=public_id,
                user=user,
                content_item=content_item,
                launch_token=launch_token,
                attempt_number=attempt_number,
                status=TrainingLabSubmission.Status.QUEUED,
                submission_mode=submission_mode,
                grader_backend=lab_profile.grader_backend,
                source_path=stored_notebook.storage_path if stored_notebook else "",
                notebook_path=canonical_notebook_path,
                response_text=normalized_response_text,
                checksum=stored_notebook.checksum if stored_notebook else "",
                submitted_at=timezone.now(),
            )
            if stored_notebook is not None:
                TrainingLabSubmissionArtifact.objects.create(
                    submission=submission,
                    artifact_kind=TrainingLabSubmissionArtifact.ArtifactKind.NOTEBOOK,
                    storage_path=stored_notebook.storage_path,
                    media_type=stored_notebook.media_type,
                    checksum=stored_notebook.checksum,
                    size_bytes=stored_notebook.size_bytes,
                    metadata=stored_notebook.metadata,
                )
            TrainingGraderJob.objects.create(
                submission=submission,
                backend=lab_profile.grader_backend,
                status=TrainingGraderJob.Status.QUEUED,
                available_at=timezone.now(),
            )
            _sync_gradebook_after_submission(submission=submission)
            return submission
    except Exception:
        if stored_notebook is not None:
            _delete_submission_storage(public_id=public_id)
        raise


def grade_submission_now(*, submission: TrainingLabSubmission, worker_name: str = "training-inline-submit") -> TrainingLabSubmission:
    grader_job = (
        TrainingGraderJob.objects.select_related("submission__content_item__lab_profile", "submission__user")
        .prefetch_related("submission__artifacts")
        .filter(submission=submission)
        .first()
    )
    if grader_job is None:
        raise TrainingGradingError("Grader job is missing for the submission.")
    if not _acquire_grader_job(job=grader_job, worker_name=worker_name):
        grader_job.refresh_from_db()
        return grader_job.submission
    grader_job.refresh_from_db()
    try:
        result = _run_grader_job(grader_job)
        return apply_grading_result(
            submission=grader_job.submission,
            score=result.score,
            max_score=result.max_score,
            passed=result.passed,
            feedback_markdown=result.feedback_markdown,
            feedback_payload=result.feedback_payload,
            artifacts=result.artifacts,
            worker_name=worker_name,
            result_payload=result.result_payload,
        )
    except TrainingGradingError as exc:
        mark_grader_job_failed(job=grader_job, error_message=str(exc), worker_name=worker_name)
        raise


def process_pending_grader_jobs(*, limit: int = 20, worker_name: str = "training-grader-worker") -> dict[str, int]:
    processed = 0
    succeeded = 0
    failed = 0

    queued_jobs = list(
        TrainingGraderJob.objects.select_related("submission__content_item__lab_profile", "submission__user")
        .prefetch_related("submission__artifacts")
        .filter(status=TrainingGraderJob.Status.QUEUED, available_at__lte=timezone.now())
        .order_by("priority", "available_at", "id")[: max(1, limit)]
    )
    for queued_job in queued_jobs:
        if not _acquire_grader_job(job=queued_job, worker_name=worker_name):
            continue
        processed += 1
        queued_job.refresh_from_db()
        try:
            result = _run_grader_job(queued_job)
            apply_grading_result(
                submission=queued_job.submission,
                score=result.score,
                max_score=result.max_score,
                passed=result.passed,
                feedback_markdown=result.feedback_markdown,
                feedback_payload=result.feedback_payload,
                artifacts=result.artifacts,
                worker_name=worker_name,
                result_payload=result.result_payload,
            )
            succeeded += 1
        except TrainingGradingError as exc:
            mark_grader_job_failed(job=queued_job, error_message=str(exc), worker_name=worker_name)
            failed += 1

    return {
        "processed": processed,
        "succeeded": succeeded,
        "failed": failed,
    }


@transaction.atomic
def apply_grading_result(
    *,
    submission: TrainingLabSubmission,
    score: Decimal | None,
    max_score: Decimal | None,
    passed: bool | None,
    feedback_markdown: str = "",
    feedback_payload: dict[str, object] | None = None,
    artifacts: list[dict[str, object]] | None = None,
    worker_name: str = "",
    result_payload: dict[str, object] | None = None,
) -> TrainingLabSubmission:
    now = timezone.now()
    raw_feedback_payload = feedback_payload or {}
    artifacts = artifacts or []
    result_payload = result_payload or {}
    feedback_payload = _sanitize_student_feedback_payload(
        raw_feedback_payload,
        score=score,
        max_score=max_score,
        passed=passed,
        grader_backend=submission.grader_backend,
    )

    submission.status = TrainingLabSubmission.Status.GRADED
    submission.score = _decimal_or_none(score)
    submission.max_score = _decimal_or_none(max_score)
    submission.passed = bool(passed) if passed is not None else None
    submission.feedback_markdown = feedback_markdown
    submission.feedback_payload = feedback_payload
    submission.graded_at = now
    submission.save(
        update_fields=[
            "status",
            "score",
            "max_score",
            "passed",
            "feedback_markdown",
            "feedback_payload",
            "graded_at",
            "updated_at",
        ]
    )
    _store_submission_artifacts(submission=submission, artifacts=artifacts)
    _sync_gradebook_after_grade(submission=submission)

    grader_job = getattr(submission, "grader_job", None)
    if grader_job is not None:
        grader_job.status = TrainingGraderJob.Status.SUCCEEDED
        grader_job.finished_at = now
        grader_job.locked_at = grader_job.locked_at or now
        grader_job.worker_name = worker_name[:120]
        grader_job.error_message = ""
        grader_job.result_payload = result_payload
        grader_job.save(
            update_fields=[
                "status",
                "finished_at",
                "locked_at",
                "worker_name",
                "error_message",
                "result_payload",
                "updated_at",
            ]
        )
    log_training_audit_event(
        event_type=TrainingAuditEvent.EventType.GRADING_RESULT_APPLIED,
        category=TrainingAuditEvent.Category.GRADING,
        actor=submission.user,
        target_user=submission.user,
        content_item=submission.content_item,
        submission=submission,
        launch_token=submission.launch_token,
        metadata={
            "graderBackend": submission.grader_backend,
            "score": str(submission.score) if submission.score is not None else "",
            "maxScore": str(submission.max_score) if submission.max_score is not None else "",
            "passed": submission.passed,
            "workerName": worker_name[:120],
            "resultPayload": result_payload,
        },
    )
    if submission.passed:
        try:
            from apps.training.services.online_lesson_sync import sync_training_content_practice_completion

            sync_training_content_practice_completion(
                user=submission.user,
                content_item=submission.content_item,
            )
        except Exception:
            # Keep grading durable even if lesson progress sync fails.
            pass
    return submission


def apply_grader_webhook_result(
    *,
    submission_public_id,
    score,
    max_score,
    passed,
    feedback_markdown: str = "",
    feedback_payload: dict[str, object] | None = None,
    artifacts: list[dict[str, object]] | None = None,
) -> TrainingLabSubmission:
    submission = (
        TrainingLabSubmission.objects.select_related("content_item", "grader_job")
        .prefetch_related("artifacts")
        .filter(public_id=submission_public_id)
        .first()
    )
    if submission is None:
        raise TrainingGradingError("Submission was not found.")
    grader_job = getattr(submission, "grader_job", None)
    if (
        submission.status == TrainingLabSubmission.Status.GRADED
        and submission.graded_at is not None
        and grader_job is not None
        and grader_job.status == TrainingGraderJob.Status.SUCCEEDED
    ):
        return submission
    normalized_feedback_payload = dict(feedback_payload or {})
    if artifacts:
        normalized_feedback_payload["externalArtifactsIgnored"] = len(artifacts)
    return apply_grading_result(
        submission=submission,
        score=_decimal_or_none(score),
        max_score=_decimal_or_none(max_score),
        passed=passed,
        feedback_markdown=feedback_markdown,
        feedback_payload=normalized_feedback_payload,
        artifacts=[],
        worker_name="grader-webhook",
        result_payload={"mode": "webhook"},
    )


@transaction.atomic
def mark_grader_job_failed(*, job: TrainingGraderJob, error_message: str, worker_name: str) -> None:
    now = timezone.now()
    job.status = TrainingGraderJob.Status.FAILED
    job.finished_at = now
    job.locked_at = job.locked_at or now
    job.worker_name = worker_name[:120]
    job.error_message = error_message
    job.save(update_fields=["status", "finished_at", "locked_at", "worker_name", "error_message", "updated_at"])
    submission = job.submission
    submission.status = TrainingLabSubmission.Status.FAILED
    submission.feedback_markdown = error_message
    submission.save(update_fields=["status", "feedback_markdown", "updated_at"])
    log_training_audit_event(
        event_type=TrainingAuditEvent.EventType.GRADING_JOB_FAILED,
        category=TrainingAuditEvent.Category.GRADING,
        outcome=TrainingAuditEvent.Outcome.FAILED,
        actor=submission.user,
        target_user=submission.user,
        content_item=submission.content_item,
        submission=submission,
        launch_token=submission.launch_token,
        metadata={
            "graderBackend": submission.grader_backend,
            "workerName": worker_name[:120],
            "errorMessage": error_message,
        },
    )


def _acquire_grader_job(*, job: TrainingGraderJob, worker_name: str) -> bool:
    updated = (
        TrainingGraderJob.objects.filter(id=job.id, status=TrainingGraderJob.Status.QUEUED)
        .update(
            status=TrainingGraderJob.Status.RUNNING,
            locked_at=timezone.now(),
            worker_name=worker_name[:120],
            attempts_count=F("attempts_count") + 1,
        )
    )
    return updated == 1


def _run_grader_job(job: TrainingGraderJob) -> TrainingGradingResult:
    submission = job.submission
    try:
        lab_profile = submission.content_item.lab_profile
    except TrainingNotebookLabProfile.DoesNotExist as exc:
        raise TrainingGradingError("Notebook runtime profile is missing.") from exc

    config = dict(lab_profile.grader_config or {})
    mode = str(config.get("mode") or "demo").strip().lower()
    if mode == "demo":
        return _run_demo_grader(submission=submission, lab_profile=lab_profile, config=config)
    if mode == "custom_rules":
        return _run_custom_rules_grader(submission=submission, lab_profile=lab_profile, config=config)
    if mode == "nbgrader_cli":
        return _run_nbgrader_cli(submission=submission, lab_profile=lab_profile, config=config)
    raise TrainingGradingError(f"Unsupported grader mode: {mode}")


def _run_demo_grader(
    *,
    submission: TrainingLabSubmission,
    lab_profile: TrainingNotebookLabProfile,
    config: dict[str, object],
) -> TrainingGradingResult:
    max_score = _decimal_or_none(config.get("maxScore")) or Decimal("100")
    score = _decimal_or_none(config.get("demoScore")) or max_score
    pass_threshold = _decimal_or_none(config.get("passThreshold")) or Decimal("70")
    passed = bool(config.get("demoPassed")) if "demoPassed" in config else score >= pass_threshold
    feedback_markdown = str(config.get("feedbackMarkdown") or "Demo grading completed successfully.").strip()
    feedback_payload = {
        "mode": "demo",
        "graderBackend": lab_profile.grader_backend,
        "passThreshold": str(pass_threshold),
    }
    return TrainingGradingResult(
        score=score,
        max_score=max_score,
        passed=passed,
        feedback_markdown=feedback_markdown,
        feedback_payload=feedback_payload,
        artifacts=[],
        result_payload={"mode": "demo"},
    )


def _run_custom_rules_grader(
    *,
    submission: TrainingLabSubmission,
    lab_profile: TrainingNotebookLabProfile,
    config: dict[str, object],
) -> TrainingGradingResult:
    if submission.submission_mode == TrainingLabSubmission.SubmissionMode.TEXT_ANSWER:
        normalized_response = str(submission.response_text or "").strip()
        if not normalized_response:
            raise TrainingGradingError("Text answer is empty.")
        sources = _build_custom_rule_sources_from_text(normalized_response)
    else:
        notebook_artifact = submission.artifacts.filter(
            artifact_kind=TrainingLabSubmissionArtifact.ArtifactKind.NOTEBOOK
        ).first()
        storage_path = (notebook_artifact.storage_path if notebook_artifact else submission.source_path) or ""
        if not storage_path:
            raise TrainingGradingError("Notebook artifact was not found for grading.")

        media_root = _media_root_path()
        notebook_file = (media_root / storage_path).resolve()
        notebook_file.relative_to(media_root)
        if not notebook_file.exists():
            raise TrainingGradingError("Notebook artifact file is missing from storage.")

        try:
            notebook_payload = _read_notebook_payload_from_bytes(notebook_file.read_bytes())
        except Exception as exc:
            raise TrainingGradingError("Notebook artifact is not valid JSON.") from exc
        sources = _build_custom_rule_sources_from_notebook_payload(notebook_payload)

    return _build_custom_rules_result_from_sources(
        submission_mode=submission.submission_mode,
        lab_profile=lab_profile,
        config=config,
        code_sources=sources["code_sources"],
        markdown_sources=sources["markdown_sources"],
        all_code=sources["all_code"],
        all_markdown=sources["all_markdown"],
        extracted_assignments=sources["extracted_assignments"],
        defined_functions=sources["defined_functions"],
        assigned_names=sources["assigned_names"],
        output_text=sources["output_text"],
        content_slug=submission.content_item.slug,
        student_id=build_training_jupyter_username(submission.user),
    )


def _build_custom_rules_result_from_sources(
    *,
    submission_mode: str,
    lab_profile: TrainingNotebookLabProfile,
    config: dict[str, object],
    code_sources: list[str],
    markdown_sources: list[str],
    all_code: str,
    all_markdown: str,
    extracted_assignments: dict[str, Decimal],
    defined_functions: set[str],
    assigned_names: set[str],
    output_text: str,
    content_slug: str,
    student_id: str = "notebook-preview",
) -> TrainingGradingResult:
    text_submission_mode = submission_mode == TrainingLabSubmission.SubmissionMode.TEXT_ANSWER
    checks = config.get("textSubmissionChecks") if text_submission_mode else config.get("checks")
    if not isinstance(checks, list) or not checks:
        raise TrainingGradingError(
            "custom_rules mode requires grader_config.textSubmissionChecks for text answers."
            if text_submission_mode
            else "custom_rules mode requires grader_config.checks."
        )

    max_score = _decimal_or_none(config.get("maxScore")) or Decimal("100")
    total_possible_points = Decimal("0")
    earned_points = Decimal("0")
    passed_checks = 0
    rubric: list[dict[str, object]] = []
    feedback_highlights: list[str] = []
    recommended_hint_ids: list[int] = []

    for index, raw_check in enumerate(checks, start=1):
        if not isinstance(raw_check, dict):
            continue
        label = str(raw_check.get("label") or raw_check.get("id") or f"Check {index}").strip()
        points = _decimal_or_none(raw_check.get("points")) or Decimal("0")
        total_possible_points += points
        kind = str(raw_check.get("kind") or "").strip()
        success, detail = _evaluate_custom_rule_check(
            raw_check,
            code_sources=code_sources,
            markdown_sources=markdown_sources,
            all_code=all_code,
            all_markdown=all_markdown,
            extracted_assignments=extracted_assignments,
            defined_functions=defined_functions,
            assigned_names=assigned_names,
            output_text=output_text,
        )
        if success:
            earned_points += points
            passed_checks += 1
            if detail:
                feedback_highlights.append(detail)
        else:
            failure_detail = str(raw_check.get("failureMessage") or detail or f"{label} still needs work.").strip()
            if failure_detail:
                feedback_highlights.append(failure_detail)
            for hint_id in raw_check.get("hintIds") or []:
                try:
                    normalized_hint_id = int(hint_id)
                except (TypeError, ValueError):
                    continue
                if normalized_hint_id not in recommended_hint_ids:
                    recommended_hint_ids.append(normalized_hint_id)
        rubric.append(
            {
                "label": label,
                "score": str(points if success else Decimal("0")),
                "maxScore": str(points),
                "passed": success,
                "detail": detail or "",
                "kind": kind,
            }
        )

    if total_possible_points <= 0:
        total_possible_points = max_score
        if earned_points > max_score:
            earned_points = max_score
    elif max_score > 0:
        earned_points = ((earned_points / total_possible_points) * max_score).quantize(Decimal("0.01"))

    pass_threshold = Decimal(str(lab_profile.pass_threshold_percent))
    score_percent = Decimal("0")
    if max_score > 0:
        score_percent = ((earned_points / max_score) * Decimal("100")).quantize(Decimal("0.01"))
    passed = score_percent >= pass_threshold
    assignment_code = str(config.get("assignmentId") or lab_profile.assignment_code or content_slug)
    feedback_markdown = _default_feedback_markdown_from_payload(
        payload={
            "rubric": rubric,
            "tests": {"passed": passed_checks, "total": len(rubric)},
        },
        score=earned_points,
        max_score=max_score,
        passed=passed,
        pass_threshold_percent=lab_profile.pass_threshold_percent,
    )
    feedback_payload = {
        "mode": "custom_rules",
        "submissionMode": submission_mode,
        "summary": {
            "assignmentCode": assignment_code,
            "scorePercent": str(score_percent),
            "passThresholdPercent": lab_profile.pass_threshold_percent,
        },
        "rubric": rubric,
        "tests": {"passed": passed_checks, "total": len(rubric)},
        "feedbackHighlights": feedback_highlights[:8],
        "recommendedHintIds": recommended_hint_ids,
    }
    feedback_html = _build_default_feedback_html(
        payload=feedback_payload,
        assignment_id=assignment_code,
        student_id=student_id,
        feedback_markdown=feedback_markdown,
        score=earned_points,
        max_score=max_score,
        passed=passed,
        pass_threshold_percent=lab_profile.pass_threshold_percent,
    )
    return TrainingGradingResult(
        score=earned_points,
        max_score=max_score,
        passed=passed,
        feedback_markdown=feedback_markdown,
        feedback_payload=feedback_payload,
        artifacts=[
            {
                "artifactKind": TrainingLabSubmissionArtifact.ArtifactKind.FEEDBACK_HTML,
                "artifactName": "feedback.html",
                "mediaType": "text/html; charset=utf-8",
                "inlineText": feedback_html,
            },
            {
                "artifactKind": TrainingLabSubmissionArtifact.ArtifactKind.JSON_REPORT,
                "artifactName": "result.json",
                "mediaType": "application/json",
                "inlineJson": feedback_payload,
            },
        ],
        result_payload=feedback_payload,
    )


def _build_custom_rule_sources_from_text(response_text: str) -> dict[str, object]:
    normalized_response = str(response_text or "").strip()
    return {
        "code_sources": [normalized_response],
        "markdown_sources": [normalized_response],
        "all_code": normalized_response,
        "all_markdown": normalized_response,
        "extracted_assignments": {},
        "defined_functions": set(),
        "assigned_names": set(),
        "output_text": normalized_response,
    }


def _build_custom_rule_sources_from_notebook_payload(notebook_payload: dict[str, object]) -> dict[str, object]:
    cells = list(notebook_payload.get("cells") or [])
    code_sources = [
        _normalize_cell_source(cell.get("source"))
        for cell in cells
        if isinstance(cell, dict) and str(cell.get("cell_type") or "") == "code"
    ]
    markdown_sources = [
        _normalize_cell_source(cell.get("source"))
        for cell in cells
        if isinstance(cell, dict) and str(cell.get("cell_type") or "") == "markdown"
    ]
    return {
        "code_sources": code_sources,
        "markdown_sources": markdown_sources,
        "all_code": "\n\n".join(code_sources),
        "all_markdown": "\n\n".join(markdown_sources),
        "extracted_assignments": _extract_numeric_assignments(code_sources),
        "defined_functions": _extract_defined_functions(code_sources),
        "assigned_names": _extract_assigned_names(code_sources),
        "output_text": _extract_notebook_output_text(cells),
    }


def _run_nbgrader_cli(
    *,
    submission: TrainingLabSubmission,
    lab_profile: TrainingNotebookLabProfile,
    config: dict[str, object],
) -> TrainingGradingResult:
    assignment_source = (
        str(config.get("assignmentId") or "").strip()
        or str(lab_profile.assignment_code or "").strip()
        or submission.content_item.slug.replace("-", "_")
    )
    assignment_id = _require_safe_identifier(assignment_source, label="assignmentId")

    configured_course_root = str(config.get("courseRoot") or "").strip()
    approved_course_root = str(getattr(settings, "TRAINING_NBGRADER_COURSE_ROOT", "") or "").strip()
    course_root_value = configured_course_root or approved_course_root
    if not course_root_value:
        raise TrainingGradingError("nbgrader_cli mode requires grader_config.courseRoot or TRAINING_NBGRADER_COURSE_ROOT.")
    course_root = _resolve_course_root(course_root_value, approved_root=approved_course_root or None)

    nbgrader_bin = str(getattr(settings, "TRAINING_NBGRADER_BIN", "nbgrader") or "nbgrader").strip()
    student_id = _require_safe_identifier(
        str(config.get("studentId") or build_training_jupyter_username(submission.user)).strip(),
        label="studentId",
    )
    notebook_path = _canonical_notebook_path(lab_profile)
    notebook_name = _sanitize_filename(Path(notebook_path).name)
    notebook_stem = Path(notebook_name).stem

    result_json_path_template = str(config.get("resultJsonPath") or "").strip()
    if not result_json_path_template:
        raise TrainingGradingError("nbgrader_cli mode requires grader_config.resultJsonPath for score extraction.")

    _stage_submission_notebook_for_nbgrader(
        submission=submission,
        course_root=course_root,
        student_id=student_id,
        assignment_id=assignment_id,
        notebook_name=notebook_name,
    )
    _run_command(
        [nbgrader_bin, "autograde", assignment_id, "--student", student_id],
        cwd=str(course_root),
    )
    generate_feedback = bool(config.get("generateFeedback", False))
    if generate_feedback:
        _run_command(
            [nbgrader_bin, "generate_feedback", assignment_id, "--student", student_id],
            cwd=str(course_root),
        )

    resolved_result_path = _resolve_course_relative_path(
        course_root=course_root,
        raw_path=result_json_path_template,
        student_id=student_id,
        assignment_id=assignment_id,
        notebook_name=notebook_name,
        notebook_stem=notebook_stem,
    )
    if not resolved_result_path.exists():
        payload = _build_nbgrader_result_payload_from_gradebook(
            course_root=course_root,
            assignment_id=assignment_id,
            student_id=student_id,
            notebook_name=notebook_name,
            pass_threshold_percent=lab_profile.pass_threshold_percent,
        )
        resolved_result_path.parent.mkdir(parents=True, exist_ok=True)
        resolved_result_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    result_json_text = resolved_result_path.read_text(encoding="utf-8")
    try:
        payload = json.loads(result_json_text)
    except json.JSONDecodeError as exc:
        raise TrainingGradingError("nbgrader result file is not valid JSON.") from exc

    feedback_path_template = str(
        config.get("feedbackHtmlPath") or f"feedback/{student_id}/{assignment_id}/{notebook_stem}.html"
    ).strip()
    resolved_feedback_path = _resolve_course_relative_path(
        course_root=course_root,
        raw_path=feedback_path_template,
        student_id=student_id,
        assignment_id=assignment_id,
        notebook_name=notebook_name,
        notebook_stem=notebook_stem,
    )

    score = _decimal_or_none(payload.get("score"))
    max_score = _decimal_or_none(payload.get("maxScore"))
    passed = payload.get("passed")
    feedback_markdown = str(payload.get("feedbackMarkdown") or "").strip()
    artifacts: list[dict[str, object]] = [
        {
            "artifactKind": TrainingLabSubmissionArtifact.ArtifactKind.JSON_REPORT,
            "artifactName": "result.json",
            "mediaType": "application/json",
            "inlineText": result_json_text,
            "metadata": {
                "mode": "nbgrader_cli",
                "assignmentId": assignment_id,
                "studentId": student_id,
                "sourcePath": str(resolved_result_path.relative_to(course_root)),
            },
        }
    ]
    if not feedback_markdown:
        feedback_markdown = _default_feedback_markdown_from_payload(
            payload=payload,
            score=score,
            max_score=max_score,
            passed=passed,
            pass_threshold_percent=lab_profile.pass_threshold_percent,
        )

    feedback_html = ""
    if resolved_feedback_path.exists():
        feedback_html = resolved_feedback_path.read_text(encoding="utf-8")
    else:
        feedback_html = _build_default_feedback_html(
            payload=payload,
            assignment_id=assignment_id,
            student_id=student_id,
            feedback_markdown=feedback_markdown,
            score=score,
            max_score=max_score,
            passed=passed,
            pass_threshold_percent=lab_profile.pass_threshold_percent,
        )
        resolved_feedback_path.parent.mkdir(parents=True, exist_ok=True)
        resolved_feedback_path.write_text(feedback_html, encoding="utf-8")

    artifacts.append(
        {
            "artifactKind": TrainingLabSubmissionArtifact.ArtifactKind.FEEDBACK_HTML,
            "artifactName": f"{notebook_stem}.html",
            "mediaType": "text/html; charset=utf-8",
            "inlineText": feedback_html,
            "metadata": {
                "mode": "nbgrader_cli",
                "assignmentId": assignment_id,
                "studentId": student_id,
                "sourcePath": str(resolved_feedback_path.relative_to(course_root)),
            },
        }
    )

    return TrainingGradingResult(
        score=score,
        max_score=max_score,
        passed=bool(passed) if passed is not None else None,
        feedback_markdown=feedback_markdown,
        feedback_payload=payload,
        artifacts=artifacts,
        result_payload={
            "mode": "nbgrader_cli",
            "assignmentId": assignment_id,
            "studentId": student_id,
            "resultJsonPath": str(resolved_result_path),
            "feedbackHtmlPath": str(resolved_feedback_path) if resolved_feedback_path.exists() else "",
        },
    )


def _run_command(command: list[str], *, cwd: str) -> None:
    completed = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=int(getattr(settings, "TRAINING_GRADER_COMMAND_TIMEOUT_SECONDS", 600) or 600),
        check=False,
    )
    if completed.returncode == 0:
        return
    stderr = (completed.stderr or "").strip()
    stdout = (completed.stdout or "").strip()
    raise TrainingGradingError(stderr or stdout or f"Command failed with exit code {completed.returncode}.")


def _canonical_notebook_path(lab_profile: TrainingNotebookLabProfile) -> str:
    canonical_notebook_path = str(lab_profile.notebook_path or "").strip()
    if not canonical_notebook_path:
        raise TrainingGradingError("Notebook runtime profile does not define a notebook path.")
    return canonical_notebook_path


def _store_uploaded_notebook_artifact(
    *,
    public_id,
    lab_profile: TrainingNotebookLabProfile,
    notebook_upload: UploadedFile | None,
    client_checksum: str,
) -> StoredSubmissionArtifactPayload:
    if notebook_upload is None:
        raise TrainingGradingError("A notebook .ipynb file is required for submission.")

    notebook_bytes = _read_uploaded_notebook_bytes(notebook_upload)
    checksum = hashlib.sha256(notebook_bytes).hexdigest()
    normalized_client_checksum = client_checksum.strip().lower()
    if normalized_client_checksum and normalized_client_checksum != checksum:
        raise TrainingGradingError("Notebook checksum does not match the uploaded file.")

    canonical_notebook_path = _canonical_notebook_path(lab_profile)
    canonical_filename = _sanitize_filename(Path(canonical_notebook_path).name)
    stored_notebook = _write_submission_storage_bytes(
        public_id=public_id,
        storage_parts=("input",),
        artifact_name=canonical_filename,
        content_bytes=notebook_bytes,
        media_type=_resolve_notebook_media_type(getattr(notebook_upload, "content_type", "")),
        metadata={
            "artifactRole": "submission_input",
            "canonicalNotebookPath": canonical_notebook_path,
            "canonicalFilename": canonical_filename,
            "originalFilename": Path(str(getattr(notebook_upload, "name", "") or "")).name,
        },
    )
    return StoredSubmissionArtifactPayload(
        storage_path=stored_notebook.storage_path,
        checksum=checksum,
        size_bytes=stored_notebook.size_bytes,
        media_type=stored_notebook.media_type,
        metadata={**stored_notebook.metadata, "sha256": checksum},
    )


def _read_uploaded_notebook_bytes(notebook_upload: UploadedFile) -> bytes:
    max_upload_bytes = int(getattr(settings, "TRAINING_SUBMISSION_MAX_UPLOAD_BYTES", 10 * 1024 * 1024) or 10 * 1024 * 1024)
    chunks: list[bytes] = []
    total_size = 0
    for chunk in notebook_upload.chunks():
        total_size += len(chunk)
        if total_size > max_upload_bytes:
            raise TrainingGradingError("Notebook file is too large.")
        chunks.append(chunk)
    if total_size <= 0:
        raise TrainingGradingError("Notebook file is empty.")

    notebook_bytes = b"".join(chunks)
    try:
        payload = json.loads(notebook_bytes.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise TrainingGradingError("Notebook file must be UTF-8 encoded.") from exc
    except json.JSONDecodeError as exc:
        raise TrainingGradingError("Notebook file is not valid JSON.") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("cells"), list):
        raise TrainingGradingError("Notebook file does not look like a valid .ipynb document.")
    return notebook_bytes


def _read_notebook_payload_from_bytes(notebook_bytes: bytes) -> dict[str, object]:
    try:
        payload = json.loads(notebook_bytes.decode("utf-8"))
    except UnicodeDecodeError as exc:
        raise TrainingGradingError("Notebook file must be UTF-8 encoded.") from exc
    except json.JSONDecodeError as exc:
        raise TrainingGradingError("Notebook file is not valid JSON.") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("cells"), list):
        raise TrainingGradingError("Notebook file does not look like a valid .ipynb document.")
    return payload


def _resolve_notebook_media_type(content_type: str) -> str:
    normalized = str(content_type or "").strip().lower()
    if normalized in {"application/json", "application/x-ipynb+json"}:
        return normalized
    return "application/x-ipynb+json"


def _resolve_course_root(course_root_value: str, *, approved_root: str | None = None) -> Path:
    course_root = Path(course_root_value).expanduser().resolve()
    if approved_root:
        approved_path = Path(approved_root).expanduser().resolve()
        try:
            course_root.relative_to(approved_path)
        except ValueError as exc:
            raise TrainingGradingError("nbgrader course root must stay within the approved root.") from exc
    course_root.mkdir(parents=True, exist_ok=True)
    return course_root


def _resolve_course_relative_path(course_root: Path, raw_path: str, **format_values: str) -> Path:
    formatted_path = raw_path.format(**format_values).strip()
    if not formatted_path:
        raise TrainingGradingError("Resolved nbgrader artifact path is empty.")
    candidate_path = Path(formatted_path)
    if not candidate_path.is_absolute():
        candidate_path = course_root / candidate_path
    resolved_path = candidate_path.resolve()
    try:
        resolved_path.relative_to(course_root)
    except ValueError as exc:
        raise TrainingGradingError("nbgrader artifact path must stay within the course root.") from exc
    return resolved_path


def _stage_submission_notebook_for_nbgrader(
    *,
    submission: TrainingLabSubmission,
    course_root: Path,
    student_id: str,
    assignment_id: str,
    notebook_name: str,
) -> Path:
    source_path = _resolve_submission_notebook_file_path(submission)
    target_path = (
        course_root
        / "submitted"
        / _require_safe_identifier(student_id, label="studentId")
        / _require_safe_identifier(assignment_id, label="assignmentId")
        / _sanitize_filename(notebook_name)
    ).resolve()
    try:
        target_path.relative_to(course_root)
    except ValueError as exc:
        raise TrainingGradingError("Resolved nbgrader submission path is invalid.") from exc
    target_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, target_path)
    return target_path


def _resolve_submission_notebook_file_path(submission: TrainingLabSubmission) -> Path:
    notebook_artifact = submission.get_primary_notebook_artifact()
    relative_path = str(
        (notebook_artifact.storage_path if notebook_artifact is not None else submission.source_path) or ""
    ).strip()
    if not relative_path:
        raise TrainingGradingError("Submission notebook artifact is missing.")
    return _resolve_media_relative_path(relative_path)


def _resolve_media_relative_path(relative_path: str) -> Path:
    media_root = _media_root_path()
    resolved_path = (media_root / relative_path).resolve()
    try:
        resolved_path.relative_to(media_root)
    except ValueError as exc:
        raise TrainingGradingError("Submission artifact path is invalid.") from exc
    if not resolved_path.exists():
        raise TrainingGradingError("Submission artifact file was not found.")
    return resolved_path


def _submission_storage_prefix() -> Path:
    prefix = str(getattr(settings, "TRAINING_SUBMISSION_STORAGE_PREFIX", "training/submissions") or "training/submissions").strip().strip("/")
    return Path(prefix)


def _media_root_path() -> Path:
    return Path(getattr(settings, "MEDIA_ROOT")).resolve()


def _sanitize_filename(filename: str) -> str:
    normalized = Path(filename).name.strip()
    if not normalized:
        return "artifact.bin"
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", normalized)
    return sanitized or "artifact.bin"


def _require_safe_identifier(value: str, *, label: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise TrainingGradingError(f"nbgrader {label} is required.")
    if not SAFE_IDENTIFIER_RE.fullmatch(normalized):
        raise TrainingGradingError(f"nbgrader {label} contains unsafe characters.")
    return normalized


def _delete_submission_storage(*, public_id) -> None:
    submission_root = (_media_root_path() / _submission_storage_prefix() / str(public_id)).resolve()
    media_root = _media_root_path()
    try:
        submission_root.relative_to(media_root)
    except ValueError:
        return
    if submission_root.exists():
        shutil.rmtree(submission_root, ignore_errors=True)


def _write_submission_storage_bytes(
    *,
    public_id,
    storage_parts: tuple[str, ...],
    artifact_name: str,
    content_bytes: bytes,
    media_type: str,
    metadata: dict[str, object] | None = None,
) -> StoredSubmissionArtifactPayload:
    sanitized_parts = [_sanitize_filename(part) for part in storage_parts if str(part).strip()]
    relative_path = _submission_storage_prefix() / str(public_id)
    for part in sanitized_parts:
        relative_path /= part
    relative_path /= _sanitize_filename(artifact_name)
    media_root = _media_root_path()
    target_path = (media_root / relative_path).resolve()
    try:
        target_path.relative_to(media_root)
    except ValueError as exc:
        raise TrainingGradingError("Submission storage path is invalid.") from exc
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_bytes(content_bytes)
    checksum = hashlib.sha256(content_bytes).hexdigest()
    return StoredSubmissionArtifactPayload(
        storage_path=relative_path.as_posix(),
        checksum=checksum,
        size_bytes=len(content_bytes),
        media_type=media_type.strip()[:120] or "application/octet-stream",
        metadata=dict(metadata or {}),
    )


def _sync_gradebook_after_submission(*, submission: TrainingLabSubmission) -> None:
    entry, _ = TrainingGradebookEntry.objects.get_or_create(
        user=submission.user,
        content_item=submission.content_item,
        defaults={
            "attempts_count": submission.attempt_number,
            "latest_submission": submission,
        },
    )
    update_fields: list[str] = []
    if entry.attempts_count < submission.attempt_number:
        entry.attempts_count = submission.attempt_number
        update_fields.append("attempts_count")
    if entry.latest_submission_id != submission.id:
        entry.latest_submission = submission
        update_fields.append("latest_submission")
    if update_fields:
        entry.save(update_fields=[*update_fields, "updated_at"])


def _sync_gradebook_after_grade(*, submission: TrainingLabSubmission) -> None:
    entry, _ = TrainingGradebookEntry.objects.get_or_create(
        user=submission.user,
        content_item=submission.content_item,
    )
    entry.latest_submission = submission
    entry.attempts_count = max(entry.attempts_count, submission.attempt_number)
    entry.latest_score = submission.score
    entry.max_score = submission.max_score
    entry.completed_at = submission.graded_at

    if submission.score is not None and (entry.best_score is None or submission.score > entry.best_score):
        entry.best_score = submission.score
        entry.best_submission = submission
    if submission.passed is not None:
        entry.passed = bool(entry.passed or submission.passed)
    entry.save()


@transaction.atomic
def _store_submission_artifacts(*, submission: TrainingLabSubmission, artifacts: list[dict[str, object]]) -> None:
    if not artifacts:
        return
    for artifact in artifacts:
        inline_text = artifact.get("inlineText")
        inline_json = artifact.get("inlineJson")
        if inline_json is not None:
            artifact_bytes = json.dumps(inline_json, ensure_ascii=False, indent=2).encode("utf-8")
            media_type = str(artifact.get("mediaType") or "application/json").strip()
        elif isinstance(inline_text, str):
            artifact_bytes = inline_text.encode("utf-8")
            media_type = str(artifact.get("mediaType") or "text/plain; charset=utf-8").strip()
        else:
            continue

        artifact_kind = _normalize_artifact_kind(
            str(artifact.get("artifactKind") or TrainingLabSubmissionArtifact.ArtifactKind.ATTACHMENT).strip()
        )
        artifact_name = str(artifact.get("artifactName") or f"{artifact_kind}.bin").strip()
        stored_artifact = _write_submission_storage_bytes(
            public_id=submission.public_id,
            storage_parts=("artifacts", artifact_kind),
            artifact_name=artifact_name,
            content_bytes=artifact_bytes,
            media_type=media_type,
            metadata=dict(artifact.get("metadata") or {}),
        )
        TrainingLabSubmissionArtifact.objects.create(
            submission=submission,
            artifact_kind=artifact_kind,
            storage_path=stored_artifact.storage_path,
            media_type=stored_artifact.media_type,
            checksum=stored_artifact.checksum,
            size_bytes=stored_artifact.size_bytes,
            metadata=stored_artifact.metadata,
        )


def _normalize_artifact_kind(value: str) -> str:
    valid_kinds = {choice for choice, _ in TrainingLabSubmissionArtifact.ArtifactKind.choices}
    if value in valid_kinds:
        return value
    return TrainingLabSubmissionArtifact.ArtifactKind.ATTACHMENT


def _sanitize_student_feedback_payload(
    payload: dict[str, object],
    *,
    score,
    max_score,
    passed,
    grader_backend: str,
) -> dict[str, object]:
    sanitized_payload: dict[str, object] = {
        "graderBackend": grader_backend,
    }
    if "mode" in payload and payload.get("mode") not in (None, ""):
        sanitized_payload["mode"] = payload.get("mode")
    if score not in (None, ""):
        sanitized_payload["score"] = str(score)
    if max_score not in (None, ""):
        sanitized_payload["maxScore"] = str(max_score)
    if passed is not None:
        sanitized_payload["passed"] = bool(passed)
    if payload.get("summary") and isinstance(payload.get("summary"), dict):
        sanitized_payload["summary"] = payload.get("summary")
    if payload.get("rubric") and isinstance(payload.get("rubric"), list):
        sanitized_payload["rubric"] = payload.get("rubric")
    if payload.get("tests") and isinstance(payload.get("tests"), dict):
        sanitized_payload["tests"] = payload.get("tests")
    if payload.get("feedbackHighlights") and isinstance(payload.get("feedbackHighlights"), list):
        sanitized_payload["feedbackHighlights"] = payload.get("feedbackHighlights")
    if payload.get("recommendedHintIds") and isinstance(payload.get("recommendedHintIds"), list):
        sanitized_payload["recommendedHintIds"] = payload.get("recommendedHintIds")
    if payload.get("artifacts") and isinstance(payload.get("artifacts"), dict):
        sanitized_payload["artifacts"] = payload.get("artifacts")
    if payload.get("externalArtifactsIgnored"):
        sanitized_payload["externalArtifactsIgnored"] = payload.get("externalArtifactsIgnored")
    return sanitized_payload


def _evaluate_custom_rule_check(
    raw_check: dict[str, object],
    *,
    code_sources: list[str],
    markdown_sources: list[str],
    all_code: str,
    all_markdown: str,
    extracted_assignments: dict[str, Decimal],
    defined_functions: set[str],
    assigned_names: set[str],
    output_text: str,
) -> tuple[bool, str]:
    kind = str(raw_check.get("kind") or "").strip()
    needle = str(raw_check.get("needle") or "").strip()
    label = str(raw_check.get("label") or raw_check.get("id") or "Check").strip()

    if kind == "code_contains":
        if needle and needle in all_code:
            return True, str(raw_check.get("successMessage") or f"{label} is present.").strip()
        return False, str(raw_check.get("failureMessage") or f"Add the required code snippet for {label}.").strip()

    if kind == "markdown_contains":
        if needle and needle.lower() in all_markdown.lower():
            return True, str(raw_check.get("successMessage") or f"{label} is documented.").strip()
        return False, str(raw_check.get("failureMessage") or f"Add the required explanation for {label}.").strip()

    if kind == "forbidden_text":
        if needle and needle.lower() not in (all_code + "\n" + all_markdown).lower():
            return True, str(raw_check.get("successMessage") or f"{label} has been cleaned up.").strip()
        return False, str(raw_check.get("failureMessage") or f"Remove the placeholder '{needle}' from the notebook.").strip()

    if kind == "required_function":
        function_name = str(raw_check.get("functionName") or needle).strip()
        if function_name and function_name in defined_functions:
            return True, str(raw_check.get("successMessage") or f"{function_name} is defined.").strip()
        return False, str(raw_check.get("failureMessage") or f"Define the required function '{function_name}'.").strip()

    if kind == "required_assignment":
        variable_name = str(raw_check.get("variable") or raw_check.get("assignment") or needle).strip()
        if variable_name and variable_name in assigned_names:
            return True, str(raw_check.get("successMessage") or f"{variable_name} is assigned.").strip()
        return (
            False,
            str(
                raw_check.get("failureMessage")
                or f"Create an assignment for '{variable_name}' in the notebook."
            ).strip(),
        )

    if kind == "numeric_assignment":
        variable_name = str(raw_check.get("variable") or needle).strip()
        expected = _decimal_or_none(raw_check.get("expected"))
        tolerance = _decimal_or_none(raw_check.get("tolerance")) or Decimal("0")
        actual = extracted_assignments.get(variable_name)
        if variable_name and actual is not None and expected is not None and abs(actual - expected) <= tolerance:
            return (
                True,
                str(
                    raw_check.get("successMessage")
                    or f"{variable_name} is within tolerance ({actual} vs {expected})."
                ).strip(),
            )
        return (
            False,
            str(
                raw_check.get("failureMessage")
                or f"Set {variable_name} to the expected value within tolerance."
            ).strip(),
        )

    if kind == "output_contains":
        case_sensitive = bool(raw_check.get("caseSensitive"))
        haystack = output_text if case_sensitive else output_text.lower()
        search_text = needle if case_sensitive else needle.lower()
        if search_text and search_text in haystack:
            return True, str(raw_check.get("successMessage") or f"{label} is visible in the notebook output.").strip()
        return (
            False,
            str(
                raw_check.get("failureMessage")
                or f"Run the notebook and show '{needle}' in the saved output."
            ).strip(),
        )

    return False, f"Unsupported check kind: {kind or 'unknown'}"


def _normalize_cell_source(source) -> str:
    if isinstance(source, list):
        return "".join(str(part) for part in source)
    return str(source or "")


def _extract_defined_functions(code_sources: list[str]) -> set[str]:
    functions: set[str] = set()
    for source in code_sources:
        try:
            module = ast.parse(source)
        except SyntaxError:
            continue
        for node in ast.walk(module):
            if isinstance(node, ast.FunctionDef):
                functions.add(node.name)
    return functions


def _extract_assigned_names(code_sources: list[str]) -> set[str]:
    assigned_names: set[str] = set()
    for source in code_sources:
        try:
            module = ast.parse(source)
        except SyntaxError:
            continue
        for node in ast.walk(module):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        assigned_names.add(target.id)
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                assigned_names.add(node.target.id)
    return assigned_names


def _extract_notebook_output_text(cells: list[dict[str, object]]) -> str:
    chunks: list[str] = []
    for cell in cells:
        if not isinstance(cell, dict) or str(cell.get("cell_type") or "") != "code":
            continue
        for output in list(cell.get("outputs") or []):
            if not isinstance(output, dict):
                continue
            text = output.get("text")
            if isinstance(text, list):
                chunks.append("".join(str(part) for part in text))
            elif text:
                chunks.append(str(text))

            data = output.get("data")
            if isinstance(data, dict):
                plain = data.get("text/plain")
                if isinstance(plain, list):
                    chunks.append("".join(str(part) for part in plain))
                elif plain:
                    chunks.append(str(plain))
    return "\n".join(chunk for chunk in chunks if chunk).strip()


def _extract_numeric_assignments(code_sources: list[str]) -> dict[str, Decimal]:
    values: dict[str, Decimal] = {}
    for source in code_sources:
        try:
            module = ast.parse(source)
        except SyntaxError:
            continue
        for node in module.body:
            if not isinstance(node, ast.Assign) or len(node.targets) != 1:
                continue
            target = node.targets[0]
            if not isinstance(target, ast.Name):
                continue
            resolved = _evaluate_numeric_expr(node.value, names=values)
            if resolved is None:
                continue
            values[target.id] = resolved
    return values


def _evaluate_numeric_expr(node: ast.AST, *, names: dict[str, Decimal]) -> Decimal | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return Decimal(str(node.value))
    if isinstance(node, ast.Name):
        return names.get(node.id)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        operand = _evaluate_numeric_expr(node.operand, names=names)
        return -operand if operand is not None else None
    if isinstance(node, ast.BinOp):
        left = _evaluate_numeric_expr(node.left, names=names)
        right = _evaluate_numeric_expr(node.right, names=names)
        if left is None or right is None:
            return None
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            if right == 0:
                return None
            return left / right
        if isinstance(node.op, ast.Pow):
            try:
                exponent = int(right)
            except Exception:
                return None
            if exponent < 0 or exponent > 8:
                return None
            return left ** exponent
    return None


def _build_nbgrader_result_payload_from_gradebook(
    *,
    course_root: Path,
    assignment_id: str,
    student_id: str,
    notebook_name: str,
    pass_threshold_percent: int,
) -> dict[str, object]:
    gradebook_path = (course_root / "gradebook.db").resolve()
    if not gradebook_path.exists():
        raise TrainingGradingError("nbgrader gradebook database was not found after autograde.")
    try:
        from nbgrader.api import Gradebook  # type: ignore
    except Exception as exc:
        raise TrainingGradingError("nbgrader is not installed in the grading runtime.") from exc

    db_url = f"sqlite:///{gradebook_path}"
    try:
        gradebook = Gradebook(db_url)
    except TypeError:
        gradebook = Gradebook(str(gradebook_path))

    try:
        try:
            submission = gradebook.find_submission(assignment_id, student_id)
        except Exception:
            submission = gradebook.find_submission(student_id, assignment_id)
        submission_dict = submission.to_dict() if hasattr(submission, "to_dict") else {}
    except Exception as exc:
        raise TrainingGradingError("nbgrader did not record a submission result in the gradebook.") from exc
    finally:
        close_method = getattr(gradebook, "close", None)
        if callable(close_method):
            close_method()

    score = _decimal_or_none(submission_dict.get("score"))
    max_score = _decimal_or_none(submission_dict.get("max_score"))
    notebook_rows = list(submission_dict.get("notebooks") or [])
    rubric: list[dict[str, object]] = []
    tests_total = 0
    tests_passed = 0
    for row in notebook_rows:
        if not isinstance(row, dict):
            continue
        notebook_score = _decimal_or_none(row.get("score"))
        notebook_max_score = _decimal_or_none(row.get("max_score"))
        rubric.append(
            {
                "label": str(row.get("name") or notebook_name),
                "score": str(notebook_score) if notebook_score is not None else "",
                "maxScore": str(notebook_max_score) if notebook_max_score is not None else "",
                "needsManualGrade": bool(row.get("needs_manual_grade")),
            }
        )
        tests_total += 1
        if notebook_max_score in (None, Decimal("0")):
            continue
        if notebook_score is not None and notebook_score >= notebook_max_score:
            tests_passed += 1

    if max_score in (None, Decimal("0")):
        max_score = sum((_decimal_or_none(row.get("max_score")) or Decimal("0")) for row in notebook_rows)
    if score is None:
        score = sum((_decimal_or_none(row.get("score")) or Decimal("0")) for row in notebook_rows)

    score_percent = None
    if score is not None and max_score not in (None, Decimal("0")):
        score_percent = (score / max_score) * Decimal("100")
    passed = bool(score_percent is not None and score_percent >= Decimal(str(pass_threshold_percent)))
    feedback_highlights = []
    if passed:
        feedback_highlights.append("The notebook passed the automated checks and is ready for review.")
    else:
        feedback_highlights.append("One or more notebook checks did not pass yet.")
        feedback_highlights.append("Review the failing calculation steps and re-run the notebook before submitting again.")

    feedback_markdown = _default_feedback_markdown_from_payload(
        payload={
            "rubric": rubric,
            "tests": {
                "passed": tests_passed,
                "total": tests_total,
            },
        },
        score=score,
        max_score=max_score,
        passed=passed,
        pass_threshold_percent=pass_threshold_percent,
    )
    return {
        "mode": "nbgrader_cli",
        "score": str(score) if score is not None else "",
        "maxScore": str(max_score) if max_score is not None else "",
        "passed": passed,
        "feedbackMarkdown": feedback_markdown,
        "summary": {
            "assignmentCode": assignment_id,
            "studentId": student_id,
            "passThresholdPercent": pass_threshold_percent,
            "scorePercent": str(score_percent.quantize(Decimal('0.01'))) if score_percent is not None else "",
            "needsManualGrade": bool(submission_dict.get("needs_manual_grade")),
        },
        "rubric": rubric,
        "tests": {
            "passed": tests_passed,
            "total": tests_total,
        },
        "feedbackHighlights": feedback_highlights,
        "artifacts": {
            "gradebookDbPath": str(gradebook_path),
        },
    }


def _default_feedback_markdown_from_payload(
    *,
    payload: dict[str, object],
    score,
    max_score,
    passed,
    pass_threshold_percent: int,
) -> str:
    tests_payload = payload.get("tests") if isinstance(payload.get("tests"), dict) else {}
    rubric = payload.get("rubric") if isinstance(payload.get("rubric"), list) else []
    lines = [
        f"Score: {score if score not in (None, '') else '-'} / {max_score if max_score not in (None, '') else '-'}",
        f"Pass threshold: {pass_threshold_percent}%",
        f"Result: {'Passed' if passed else 'Not passed yet'}",
    ]
    if tests_payload:
        lines.append(
            f"Checks passed: {tests_payload.get('passed', 0)} / {tests_payload.get('total', 0)}"
        )
    if rubric:
        lines.append("")
        lines.append("Rubric:")
        for item in rubric:
            if not isinstance(item, dict):
                continue
            lines.append(
                f"- {item.get('label') or 'Notebook'}: {item.get('score') or '-'} / {item.get('maxScore') or '-'}"
            )
    return "\n".join(lines)


def _build_default_feedback_html(
    *,
    payload: dict[str, object],
    assignment_id: str,
    student_id: str,
    feedback_markdown: str,
    score,
    max_score,
    passed,
    pass_threshold_percent: int,
) -> str:
    rubric_rows = payload.get("rubric") if isinstance(payload.get("rubric"), list) else []
    tests_payload = payload.get("tests") if isinstance(payload.get("tests"), dict) else {}
    highlights = payload.get("feedbackHighlights") if isinstance(payload.get("feedbackHighlights"), list) else []
    rubric_html = "".join(
        f"<tr><td>{escape(str(item.get('label') or 'Notebook'))}</td><td>{escape(str(item.get('score') or '-'))}</td><td>{escape(str(item.get('maxScore') or '-'))}</td></tr>"
        for item in rubric_rows
        if isinstance(item, dict)
    )
    highlights_html = "".join(f"<li>{escape(str(item))}</li>" for item in highlights)
    body_html = "".join(f"<p>{escape(line)}</p>" for line in feedback_markdown.splitlines() if line.strip())
    result_badge = "Passed" if passed else "Needs revision"
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{escape(assignment_id)} feedback</title>
    <style>
      body {{ font-family: Arial, sans-serif; padding: 32px; color: #123955; background: #f5f8fb; }}
      .card {{ background: #fff; border: 1px solid #d8e3ef; border-radius: 18px; padding: 24px; margin-bottom: 20px; }}
      .pill {{ display: inline-block; padding: 8px 12px; border-radius: 999px; background: #e8f0f8; color: #123955; font-weight: 700; }}
      h1, h2 {{ margin: 0 0 12px; }}
      table {{ width: 100%; border-collapse: collapse; }}
      th, td {{ padding: 10px 12px; border-bottom: 1px solid #d8e3ef; text-align: left; }}
      ul {{ margin: 0; padding-left: 20px; }}
    </style>
  </head>
  <body>
    <section class="card">
      <span class="pill">{escape(result_badge)}</span>
      <h1>{escape(assignment_id)}</h1>
      <p>Student: {escape(student_id)}</p>
      <p>Score: {escape(str(score if score not in (None, '') else '-'))} / {escape(str(max_score if max_score not in (None, '') else '-'))}</p>
      <p>Pass threshold: {escape(str(pass_threshold_percent))}%</p>
      <p>Checks passed: {escape(str(tests_payload.get('passed', 0)))} / {escape(str(tests_payload.get('total', 0)))}</p>
    </section>
    <section class="card">
      <h2>Feedback summary</h2>
      {body_html}
    </section>
    <section class="card">
      <h2>Rubric</h2>
      <table>
        <thead><tr><th>Notebook</th><th>Score</th><th>Max score</th></tr></thead>
        <tbody>{rubric_html or '<tr><td colspan="3">No rubric data available.</td></tr>'}</tbody>
      </table>
    </section>
    <section class="card">
      <h2>Highlights</h2>
      <ul>{highlights_html or '<li>No highlights were generated for this attempt.</li>'}</ul>
    </section>
  </body>
</html>"""


def _decimal_or_none(value) -> Decimal | None:
    if value in (None, ""):
        return None
    return Decimal(str(value))
