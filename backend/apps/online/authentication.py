from __future__ import annotations

from django.conf import settings
from rest_framework import exceptions
from rest_framework.authentication import CSRFCheck
from rest_framework_simplejwt.authentication import JWTAuthentication


class OnlineCookieJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        header = self.get_header(request)
        if header is not None:
            return super().authenticate(request)

        raw_token = None
        for cookie_name in self._cookie_names(request):
            cookie_value = request.COOKIES.get(cookie_name)
            if cookie_value:
                raw_token = cookie_value
                break

        if not raw_token:
            return None

        validated_token = self.get_validated_token(raw_token)
        self.enforce_csrf(request)
        return self.get_user(validated_token), validated_token

    def enforce_csrf(self, request) -> None:
        if request.method in {"GET", "HEAD", "OPTIONS", "TRACE"}:
            return

        check = CSRFCheck(lambda _: None)
        check.process_request(request)
        reason = check.process_view(request, None, (), {})
        if reason:
            raise exceptions.PermissionDenied(f"CSRF Failed: {reason}")

    @staticmethod
    def _cookie_names(request) -> tuple[str, ...]:
        student_cookie = str(getattr(settings, "ONLINE_STUDENT_ACCESS_COOKIE_NAME", "")).strip()
        staff_cookie = str(getattr(settings, "ONLINE_STAFF_ACCESS_COOKIE_NAME", "")).strip()
        path = str(getattr(request, "path", "") or "")
        requested_scope = str(request.headers.get("X-Online-Auth-Scope") or "").strip().lower()

        if requested_scope == "staff":
            prefers_staff_cookie = True
        elif requested_scope == "student":
            prefers_staff_cookie = False
        else:
            prefers_staff_cookie = any(
                segment in path
                for segment in (
                    "/staff/",
                    "/teacher/",
                    "/admin/",
                )
            )

        ordered = (staff_cookie, student_cookie) if prefers_staff_cookie else (student_cookie, staff_cookie)
        return tuple(cookie_name for cookie_name in ordered if cookie_name)
