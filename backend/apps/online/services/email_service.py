import logging
import os
from html import escape
from typing import Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import requests
from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection

from apps.online.models import OnlineCourse, OnlineSession, OnlineStudentProfile

logger = logging.getLogger(__name__)


def _get_setting(name: str, default=None):
    return getattr(settings, name, default)


def _append_access_token(url: str, token: str) -> str:
    parts = urlparse(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["access_token"] = token
    return urlunparse(parts._replace(query=urlencode(query)))


def _get_directus_flow_token() -> str:
    return str(_get_setting("ONLINE_EMAIL_DIRECTUS_TOKEN", "") or os.getenv("DIRECTUS_API_TOKEN", "")).strip()


def _post_directus_flow(flow_url: str, payload: dict) -> bool:
    token = _get_directus_flow_token()
    headers = {"Content-Type": "application/json"}
    if token:
        flow_url = _append_access_token(flow_url, token)

    try:
        response = requests.post(flow_url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        return True
    except requests.RequestException as exc:
        response = getattr(exc, "response", None)
        if response is not None:
            logger.error(
                "Directus flow email failed: status=%s body=%s",
                response.status_code,
                response.text[:500],
            )
        else:
            logger.error("Directus flow email failed: %s", exc)
        return False


def _send_via_directus_flow(
    recipient: str,
    subject: str,
    text_body: str,
    html_body: Optional[str] = None,
) -> bool:
    flow_url = _get_setting("ONLINE_EMAIL_DIRECTUS_FLOW_URL", "")
    if not flow_url:
        logger.warning("ONLINE_EMAIL_DIRECTUS_FLOW_URL is empty. Directus email send skipped.")
        return False

    payload = {
        "to": recipient,
        "subject": subject,
        "text": text_body,
        "html": html_body or "",
    }
    return _post_directus_flow(flow_url, payload)


def _send_course_access_via_directus_flow(
    profile: OnlineStudentProfile,
    course: OnlineCourse,
    *,
    is_trial: bool,
) -> bool:
    flow_url = _get_setting("ONLINE_COURSE_ACCESS_DIRECTUS_FLOW_URL", "")
    if not flow_url:
        return False

    subject, text_body, html_body = _build_course_access_message(profile=profile, course=course, is_trial=is_trial)
    locale = profile.preferred_language or "de"
    payload = {
        "to": profile.user.email,
        "subject": subject,
        "text": text_body,
        "html": html_body,
        "data": {
            "to": profile.user.email,
            "first_name": profile.first_name,
            "last_name": profile.last_name,
            "login": profile.user.email,
            "portal_url": _get_setting("ONLINE_STUDENT_PORTAL_URL", "http://localhost:5180/login"),
            "preferred_language": locale,
            "course_title": course.localized_title(locale),
            "course_slug": course.slug,
            "mode": "trial" if is_trial else "paid",
        }
    }
    return _post_directus_flow(flow_url, payload)


def _render_html_from_text(text_body: str) -> str:
    paragraphs = [segment.strip() for segment in text_body.split("\n\n") if segment.strip()]
    if not paragraphs:
        return ""
    return "".join(f"<p>{escape(paragraph).replace(chr(10), '<br>')}</p>" for paragraph in paragraphs)


def _build_course_access_message(
    *,
    profile: OnlineStudentProfile,
    course: OnlineCourse,
    is_trial: bool,
) -> tuple[str, str, str]:
    portal_url = _get_setting("ONLINE_STUDENT_PORTAL_URL", "http://localhost:5180/login")
    mode_text_de = "Probestunde" if is_trial else "Bezahlter Kurs"
    mode_text_en = "Trial lesson" if is_trial else "Paid course"
    locale = profile.preferred_language or "de"

    if locale == "en":
        subject = f"Your online access is ready: {course.title_en}"
        text_body = (
            f"Hello {profile.first_name},\n\n"
            f"Your enrollment is active.\n"
            f"Course: {course.title_en}\n"
            f"Type: {mode_text_en}\n"
            f"Login: {profile.user.email}\n"
            f"Portal: {portal_url}\n\n"
            "Password was set during registration. If needed, use password reset.\n"
        )
    else:
        subject = f"Ihr Online-Zugang ist bereit: {course.title_de}"
        text_body = (
            f"Hallo {profile.first_name},\n\n"
            f"Ihre Teilnahme wurde aktiviert.\n"
            f"Kurs: {course.title_de}\n"
            f"Typ: {mode_text_de}\n"
            f"Login: {profile.user.email}\n"
            f"Portal: {portal_url}\n\n"
            "Das Passwort wurde bei der Registrierung gesetzt. Bei Bedarf nutzen Sie den Passwort-Reset.\n"
        )

    return subject, text_body, _render_html_from_text(text_body)


def _send_via_smtp(
    recipient: str,
    subject: str,
    text_body: str,
    html_body: Optional[str] = None,
) -> bool:
    host = _get_setting("ONLINE_EMAIL_HOST", "")
    port = int(_get_setting("ONLINE_EMAIL_PORT", 587))
    username = _get_setting("ONLINE_EMAIL_HOST_USER", "")
    password = _get_setting("ONLINE_EMAIL_HOST_PASSWORD", "")
    use_tls = bool(_get_setting("ONLINE_EMAIL_USE_TLS", True))
    from_email = _get_setting("ONLINE_EMAIL_FROM_EMAIL", "") or _get_setting("DEFAULT_FROM_EMAIL", "")

    if not host or not username or not password or not from_email:
        logger.warning("SMTP credentials are incomplete. SMTP email send skipped.")
        return False

    try:
        connection = get_connection(
            host=host,
            port=port,
            username=username,
            password=password,
            use_tls=use_tls,
            fail_silently=False,
        )
        message = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=from_email,
            to=[recipient],
            connection=connection,
        )
        if html_body:
            message.attach_alternative(html_body, "text/html")
        message.send()
        return True
    except Exception as exc:
        logger.error("SMTP email failed: %s", exc)
        return False


def send_online_email(
    recipient: str,
    subject: str,
    text_body: str,
    html_body: Optional[str] = None,
) -> bool:
    mode = str(_get_setting("ONLINE_EMAIL_MODE", "console")).lower().strip()
    if mode == "directus_flow":
        return _send_via_directus_flow(recipient, subject, text_body, html_body)
    if mode == "smtp":
        return _send_via_smtp(recipient, subject, text_body, html_body)

    logger.info(
        "ONLINE_EMAIL_MODE=%s. Console fallback email payload: to=%s subject=%s",
        mode,
        recipient,
        subject,
    )
    return True


def send_course_access_email(
    profile: OnlineStudentProfile,
    course: OnlineCourse,
    is_trial: bool,
) -> bool:
    mode = str(_get_setting("ONLINE_EMAIL_MODE", "console")).lower().strip()
    if mode == "directus_flow":
        directus_sent = _send_course_access_via_directus_flow(profile, course, is_trial=is_trial)
        if directus_sent:
            return True

    subject, text_body, html_body = _build_course_access_message(profile=profile, course=course, is_trial=is_trial)

    return send_online_email(
        recipient=profile.user.email,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
    )


def send_feedback_notification(
    sender_email: str,
    sender_name: str,
    subject: str,
    message: str,
) -> bool:
    recipient = _get_setting("ONLINE_FEEDBACK_RECEIVER_EMAIL", "")
    if not recipient:
        logger.warning("ONLINE_FEEDBACK_RECEIVER_EMAIL is empty. Feedback email send skipped.")
        return False

    body = (
        "New online feedback message\n\n"
        f"From: {sender_name} <{sender_email}>\n"
        f"Subject: {subject}\n\n"
        f"{message}\n"
    )
    return send_online_email(
        recipient=recipient,
        subject=f"[Online Feedback] {subject}",
        text_body=body,
    )


def send_magic_link_email(
    profile: OnlineStudentProfile,
    portal_link: str,
) -> bool:
    locale = profile.preferred_language or "de"
    if locale == "en":
        subject = "Your magic link to online course portal"
        text_body = (
            f"Hello {profile.first_name},\n\n"
            "Use the secure link below to open your online course portal:\n"
            f"{portal_link}\n\n"
            "The link is time-limited. If it expires, request a new one.\n"
        )
    else:
        subject = "Ihr Magic-Link zum Online-Kursportal"
        text_body = (
            f"Hallo {profile.first_name},\n\n"
            "Mit dem sicheren Link unten oeffnen Sie Ihr Online-Kursportal:\n"
            f"{portal_link}\n\n"
            "Der Link ist zeitlich begrenzt. Wenn er ablaeuft, fordern Sie bitte einen neuen an.\n"
        )

    return send_online_email(
        recipient=profile.user.email,
        subject=subject,
        text_body=text_body,
    )


def send_session_reminder_email(
    profile: OnlineStudentProfile,
    session: OnlineSession,
    *,
    hours_before: int,
) -> bool:
    locale = profile.preferred_language or "de"
    join_url = session.join_url or "-"
    starts_text = session.starts_at.strftime("%Y-%m-%d %H:%M")
    if locale == "en":
        subject = f"Reminder: lesson starts in {hours_before}h"
        text_body = (
            f"Hello {profile.first_name},\n\n"
            f"This is a reminder that your online lesson \"{session.title}\" starts in about {hours_before} hour(s).\n"
            f"Start time: {starts_text}\n"
            f"Join link: {join_url}\n\n"
            "See you in class.\n"
        )
    else:
        subject = f"Erinnerung: Unterricht startet in {hours_before} Std."
        text_body = (
            f"Hallo {profile.first_name},\n\n"
            f"Das ist eine Erinnerung: Ihr Online-Unterricht \"{session.title}\" startet in ca. {hours_before} Stunde(n).\n"
            f"Startzeit: {starts_text}\n"
            f"Teilnahmelink: {join_url}\n\n"
            "Bis gleich im Unterricht.\n"
        )

    return send_online_email(
        recipient=profile.user.email,
        subject=subject,
        text_body=text_body,
    )
