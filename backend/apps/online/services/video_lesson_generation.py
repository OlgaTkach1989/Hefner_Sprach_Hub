from __future__ import annotations

from dataclasses import dataclass
import mimetypes
from pathlib import Path
import shutil
import subprocess
import tempfile

import requests
from django.conf import settings
from django.core.files.uploadedfile import UploadedFile

from apps.online.models import OnlineCourse, OnlineCourseContentLibraryItem
from apps.online.services.lesson_generator import generate_course_builder_lesson_document


class VideoLessonGenerationError(RuntimeError):
    pass


@dataclass(frozen=True)
class VideoLessonGenerationResult:
    document: dict
    meta: dict
    transcript_text: str
    video_library_item: OnlineCourseContentLibraryItem


def generate_course_builder_lesson_from_video(
    *,
    lesson_title: str,
    lesson_description: str = "",
    video_file: UploadedFile,
    language: str = OnlineCourse.LOCALE_EN,
    course_title: str = "",
    module_title: str = "",
    video_description: str = "",
    video_url: str = "",
    video_public_url: str = "",
) -> VideoLessonGenerationResult:
    normalized_language = language if language in {OnlineCourse.LOCALE_DE, OnlineCourse.LOCALE_EN} else OnlineCourse.LOCALE_EN
    normalized_title = str(lesson_title or "").strip() or "Generated video lesson"
    normalized_video_description = str(video_description or "").strip()

    video_item = OnlineCourseContentLibraryItem.objects.create(
        section_type=OnlineCourseContentLibraryItem.SECTION_MAIN,
        title=f"{normalized_title} video",
        description=normalized_video_description or "Uploaded source video for generated lesson.",
        library_group="Generated lesson videos",
        asset_type=OnlineCourseContentLibraryItem.ASSET_LINK,
        language=normalized_language,
        body_markdown="",
        external_url=str(video_url or "").strip(),
        file_asset=video_file,
        sort_order=10,
        is_active=True,
    )

    try:
        transcript_text = transcribe_uploaded_video(
            video_item=video_item,
            language=normalized_language,
        )
        if not transcript_text.strip():
            raise VideoLessonGenerationError("The transcription provider returned an empty transcript.")

        resolved_video_url = video_public_url or video_item.external_url or _file_url(video_item)
        generation_result = generate_course_builder_lesson_document(
            lesson_title=normalized_title,
            lesson_description=lesson_description,
            source_text=transcript_text,
            language=normalized_language,
            course_title=course_title,
            module_title=module_title,
            video_url=resolved_video_url,
            video_description=normalized_video_description or "Video lesson source.",
        )
        document = generation_result["document"]
        _attach_video_library_reference(
            document=document,
            video_url=resolved_video_url,
            video_description=normalized_video_description,
            source_library_item_id=video_item.id,
        )
    except Exception:
        video_item.delete()
        raise

    return VideoLessonGenerationResult(
        document=document,
        meta={
            **generation_result.get("meta", {}),
            "source": "video_transcript",
            "transcriptionProvider": "openai-compatible",
            "transcriptionModel": _transcription_model_name(),
            "transcriptCharacters": len(transcript_text),
            "videoLibraryItemId": video_item.id,
        },
        transcript_text=transcript_text,
        video_library_item=video_item,
    )


def transcribe_uploaded_video(*, video_item: OnlineCourseContentLibraryItem, language: str) -> str:
    if not video_item.file_asset:
        raise VideoLessonGenerationError("Video file was not saved.")
    try:
        source_path = Path(video_item.file_asset.path)
    except NotImplementedError as exc:
        raise VideoLessonGenerationError("Video transcription requires local file storage.") from exc
    if not source_path.exists():
        raise VideoLessonGenerationError("Saved video file was not found.")

    audio_path: Path | None = None
    transcription_path = source_path
    try:
        audio_path = _extract_audio_with_ffmpeg(source_path)
        if audio_path is not None:
            transcription_path = audio_path
        return _transcribe_file(transcription_path, language=language)
    finally:
        if audio_path is not None:
            try:
                audio_path.unlink(missing_ok=True)
            except OSError:
                pass


def _transcribe_file(path: Path, *, language: str) -> str:
    base_url = str(getattr(settings, "TRAINING_AI_BASE_URL", "") or "").strip().rstrip("/")
    api_key = str(getattr(settings, "TRAINING_AI_API_KEY", "") or "").strip()
    model = _transcription_model_name()
    timeout_seconds = int(getattr(settings, "TRAINING_AI_TRANSCRIPTION_TIMEOUT_SECONDS", 180) or 180)
    if not base_url or not api_key or not model:
        raise VideoLessonGenerationError("Video transcription provider is not configured.")

    mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    data = {"model": model}
    if language in {OnlineCourse.LOCALE_DE, OnlineCourse.LOCALE_EN}:
        data["language"] = language

    try:
        with path.open("rb") as file_handle:
            response = requests.post(
                f"{base_url}/audio/transcriptions",
                headers={"Authorization": f"Bearer {api_key}"},
                data=data,
                files={"file": (path.name, file_handle, mime_type)},
                timeout=timeout_seconds,
            )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise VideoLessonGenerationError(f"Video transcription failed: {exc}") from exc

    try:
        payload = response.json()
    except ValueError as exc:
        raise VideoLessonGenerationError("Video transcription returned invalid JSON.") from exc
    transcript = str(payload.get("text") or "").strip()
    return transcript


def _extract_audio_with_ffmpeg(source_path: Path) -> Path | None:
    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        return None
    temp_file = tempfile.NamedTemporaryFile(prefix="lesson-video-", suffix=".mp3", delete=False)
    temp_path = Path(temp_file.name)
    temp_file.close()
    command = [
        ffmpeg_path,
        "-y",
        "-i",
        str(source_path),
        "-vn",
        "-acodec",
        "libmp3lame",
        "-ar",
        "16000",
        "-ac",
        "1",
        str(temp_path),
    ]
    try:
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=180)
    except (OSError, subprocess.SubprocessError):
        temp_path.unlink(missing_ok=True)
        return None
    return temp_path if temp_path.exists() and temp_path.stat().st_size > 0 else None


def _attach_video_library_reference(
    *,
    document: dict,
    video_url: str,
    video_description: str,
    source_library_item_id: int,
) -> None:
    sections = document.get("sections") if isinstance(document.get("sections"), list) else []
    for section in sections:
        if not isinstance(section, dict):
            continue
        items = section.get("items") if isinstance(section.get("items"), list) else []
        for item in items:
            if not isinstance(item, dict):
                continue
            if item.get("activityType") != "video":
                continue
            item["sourceLibraryItemId"] = source_library_item_id
            if video_url:
                item["externalUrl"] = video_url
            if video_description:
                item["description"] = video_description
            return


def _transcription_model_name() -> str:
    return str(getattr(settings, "TRAINING_AI_TRANSCRIPTION_MODEL", "") or "whisper-1").strip()


def _file_url(item: OnlineCourseContentLibraryItem) -> str:
    if not item.file_asset:
        return ""
    return f"/api/online/media/course-library/{item.id}/file/"
