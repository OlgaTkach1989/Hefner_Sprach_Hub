from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode, urlparse, parse_qsl, urlunparse
from uuid import uuid4

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.online.models import OnlineEnrollment, OnlineOrder, OnlinePaymentEvent
from apps.online.services.email_service import send_course_access_email


@dataclass
class CheckoutSessionData:
    checkout_url: str
    provider_payment_id: str
    external_reference: str


def get_payment_mode() -> str:
    return str(getattr(settings, "ONLINE_PAYMENT_MODE", "mock")).strip().lower()


def _append_query(url: str, extra_query: dict[str, str]) -> str:
    parts = urlparse(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query.update(extra_query)
    return urlunparse(parts._replace(query=urlencode(query)))


def build_checkout_session(*, order: OnlineOrder, api_root_url: str) -> CheckoutSessionData:
    mode = get_payment_mode()
    if mode != "mock":
        raise ValueError(f"Unsupported ONLINE_PAYMENT_MODE='{mode}'. Supported in code: mock.")

    provider_payment_id = f"mockpay_{order.id}_{uuid4().hex[:12]}"
    external_reference = f"online_order_{order.id}"
    checkout_url = _append_query(
        f"{api_root_url.rstrip('/')}/public/checkout/provider/mock/{order.checkout_token}/",
        {
            "provider": order.provider,
            "result": "paid",
        },
    )
    return CheckoutSessionData(
        checkout_url=checkout_url,
        provider_payment_id=provider_payment_id,
        external_reference=external_reference,
    )


def _event_status_from_payload(payload: dict[str, Any]) -> str:
    raw = str(
        payload.get("status")
        or payload.get("payment_status")
        or payload.get("event_type")
        or payload.get("eventType")
        or ""
    ).strip().lower()
    if raw in {"paid", "succeeded", "success"}:
        return OnlinePaymentEvent.STATUS_PAID
    if raw in {"failed", "failure", "canceled", "cancelled"}:
        return OnlinePaymentEvent.STATUS_FAILED
    if raw in {"refunded", "chargeback"}:
        return OnlinePaymentEvent.STATUS_REFUNDED
    if raw in {"pending", "processing", "requires_action"}:
        return OnlinePaymentEvent.STATUS_PENDING
    return OnlinePaymentEvent.STATUS_UNKNOWN


def _resolve_order_from_payload(payload: dict[str, Any]) -> OnlineOrder:
    order_id_raw = payload.get("orderId") or payload.get("order_id")
    if order_id_raw:
        try:
            return OnlineOrder.objects.select_related("profile", "course", "cohort").get(id=int(order_id_raw))
        except (TypeError, ValueError, OnlineOrder.DoesNotExist):
            pass

    checkout_token_raw = payload.get("checkoutToken") or payload.get("checkout_token")
    if checkout_token_raw:
        try:
            return OnlineOrder.objects.select_related("profile", "course", "cohort").get(checkout_token=checkout_token_raw)
        except OnlineOrder.DoesNotExist:
            pass

    provider_payment_id = str(payload.get("providerPaymentId") or payload.get("provider_payment_id") or "").strip()
    if provider_payment_id:
        try:
            return OnlineOrder.objects.select_related("profile", "course", "cohort").get(provider_payment_id=provider_payment_id)
        except OnlineOrder.DoesNotExist:
            pass

    raise ValueError("Order not found for payment event.")


@transaction.atomic
def process_payment_event(
    *,
    provider: str,
    event_id: str,
    payload: dict[str, Any],
    signature_valid: bool,
) -> dict[str, Any]:
    order = _resolve_order_from_payload(payload)
    event_status = _event_status_from_payload(payload)
    event_type = str(payload.get("eventType") or payload.get("event_type") or "").strip()
    provider_payment_id = str(payload.get("providerPaymentId") or payload.get("provider_payment_id") or "").strip()

    try:
        payment_event = OnlinePaymentEvent.objects.create(
            order=order,
            provider=provider,
            event_id=event_id,
            event_type=event_type,
            status=event_status,
            provider_payment_id=provider_payment_id,
            signature_valid=signature_valid,
            raw_payload=payload,
        )
    except IntegrityError:
        return {
            "alreadyProcessed": True,
            "orderId": order.id,
            "orderStatus": order.status,
        }

    if provider_payment_id and order.provider_payment_id != provider_payment_id:
        order.provider_payment_id = provider_payment_id

    email_sent = False
    reason = str(payload.get("reason") or payload.get("message") or "").strip()

    if event_status == OnlinePaymentEvent.STATUS_PAID:
        was_paid_before = order.status == OnlineOrder.STATUS_PAID
        order.status = OnlineOrder.STATUS_PAID
        if not order.paid_at:
            order.paid_at = timezone.now()
        order.paid_event_id = payment_event.event_id
        order.payment_failure_reason = ""
        order.save(
            update_fields=[
                "provider_payment_id",
                "status",
                "paid_at",
                "paid_event_id",
                "payment_failure_reason",
                "updated_at",
            ]
        )

        enrollment, created = OnlineEnrollment.objects.get_or_create(
            profile=order.profile,
            cohort=order.cohort,
            defaults={
                "course": order.course,
                "order": order,
                "status": OnlineEnrollment.STATUS_ACTIVE,
            },
        )
        if not created:
            enrollment.order = order
            enrollment.status = OnlineEnrollment.STATUS_ACTIVE
            enrollment.save(update_fields=["order", "status"])

        if not was_paid_before:
            email_sent = send_course_access_email(profile=order.profile, course=order.course, is_trial=False)

    elif event_status == OnlinePaymentEvent.STATUS_FAILED:
        if order.status not in {OnlineOrder.STATUS_PAID, OnlineOrder.STATUS_REFUNDED}:
            order.status = OnlineOrder.STATUS_FAILED
            order.payment_failure_reason = reason
            order.save(update_fields=["provider_payment_id", "status", "payment_failure_reason", "updated_at"])

    elif event_status == OnlinePaymentEvent.STATUS_REFUNDED:
        if order.status != OnlineOrder.STATUS_REFUNDED:
            order.status = OnlineOrder.STATUS_REFUNDED
            if not order.refunded_at:
                order.refunded_at = timezone.now()
            order.save(update_fields=["provider_payment_id", "status", "refunded_at", "updated_at"])
        order.enrollments.filter(
            status__in=(
                OnlineEnrollment.STATUS_ACTIVE,
                OnlineEnrollment.STATUS_TRIAL,
                OnlineEnrollment.STATUS_SUSPENDED,
            )
        ).update(status=OnlineEnrollment.STATUS_REVOKED)

    elif event_status == OnlinePaymentEvent.STATUS_PENDING:
        if order.status not in {OnlineOrder.STATUS_PAID, OnlineOrder.STATUS_REFUNDED}:
            order.status = OnlineOrder.STATUS_PENDING
            order.save(update_fields=["provider_payment_id", "status", "updated_at"])

    return {
        "alreadyProcessed": False,
        "eventStatus": event_status,
        "orderId": order.id,
        "orderStatus": order.status,
        "emailSent": email_sent,
    }


def build_mock_result_redirect_url(*, order: OnlineOrder, provider_result: str) -> str:
    success_url = str(
        getattr(settings, "ONLINE_PUBLIC_CHECKOUT_SUCCESS_URL", "http://localhost:5182/success")
    ).strip()
    cancel_url_template = str(
        getattr(settings, "ONLINE_PUBLIC_CHECKOUT_CANCEL_URL", "http://localhost:5182/checkout/{slug}")
    ).strip()

    if provider_result == "cancel":
        return cancel_url_template.replace("{slug}", order.course.slug)

    return _append_query(
        success_url,
        {
            "order": str(order.id),
            "token": str(order.checkout_token),
        },
    )
