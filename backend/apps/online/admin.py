from django.contrib import admin, messages
from django.db.models import Count, Q
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html

from .models import (
    OnlineAttendance,
    OnlineCohort,
    OnlineCourse,
    OnlineCourseFaq,
    OnlineCourseMaterial,
    OnlineEnrollment,
    OnlineFeedbackMessage,
    OnlineMagicLinkToken,
    OnlineOrder,
    OnlinePaymentEvent,
    OnlineSessionReminder,
    OnlineSession,
    OnlineStudentProfile,
    OnlineSupportMessage,
    OnlineWorkspace,
    OnlineWorkspaceContentItem,
)
from .services.session_generation import SessionGenerationError, generate_missing_sessions_for_cohort
from .services.stats import (
    ONLINE_DASHBOARD_ENROLLMENT_STATUSES,
    cohort_seats_left,
    course_card_payload,
    course_detail_payload,
    nearest_session_for_cohort,
)


class DisableBulkDeleteMixin:
    """Keep object-level delete available, but avoid bulk hard-delete from changelists."""

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions


class OnlineCourseFaqInline(admin.TabularInline):
    model = OnlineCourseFaq
    extra = 0
    fields = ("sort_order", "question_de", "question_en", "is_active")
    ordering = ("sort_order", "id")


class OnlineCourseMaterialInline(admin.TabularInline):
    model = OnlineCourseMaterial
    extra = 0
    fields = ("sort_order", "title", "material_type", "language", "is_active", "link_url")
    ordering = ("sort_order", "id")


class OnlineWorkspaceContentItemInline(admin.TabularInline):
    model = OnlineWorkspaceContentItem
    extra = 0
    fields = (
        "section",
        "sort_order",
        "title",
        "linked_course",
        "linked_cohort",
        "primary_meta",
        "secondary_meta",
        "published_on",
        "is_active",
    )
    ordering = ("section", "sort_order", "id")


class OnlineCohortInline(admin.TabularInline):
    model = OnlineCohort
    extra = 0
    fields = (
        "group_code",
        "name",
        "teacher",
        "status",
        "is_public",
        "capacity",
        "start_date",
        "end_date",
    )
    ordering = ("start_date", "id")
    show_change_link = True


class OnlineSessionInline(admin.TabularInline):
    model = OnlineSession
    extra = 0
    fields = (
        "sort_order",
        "title",
        "starts_at",
        "ends_at",
        "status",
        "is_completed",
        "join_url",
    )
    ordering = ("sort_order", "starts_at", "id")


@admin.register(OnlineCourse)
class OnlineCourseAdmin(DisableBulkDeleteMixin, admin.ModelAdmin):
    change_list_template = "admin/online/onlinecourse/change_list.html"
    list_display = (
        "id",
        "slug",
        "title_de",
        "price_amount",
        "currency",
        "trial_available",
        "is_published",
        "cohorts_total",
        "sessions_total",
        "students_total",
    )
    search_fields = ("slug", "title_de", "title_en")
    list_filter = ("is_published", "trial_available", "currency")
    readonly_fields = ("stats_overview", "deletion_policy")
    prepopulated_fields = {"slug": ("title_de",)}
    inlines = (OnlineCourseFaqInline, OnlineCourseMaterialInline, OnlineCohortInline)
    actions = ("archive_selected_courses", "publish_selected_courses")
    fieldsets = (
        (
            "Course content",
            {
                "fields": (
                    "slug",
                    ("title_de", "title_en"),
                    ("short_description_de", "short_description_en"),
                    ("description_de", "description_en"),
                    ("lessons_count", "trial_available", "is_subscription"),
                    ("price_amount", "currency"),
                    "hero_image_url",
                )
            },
        ),
        (
            "Visibility and SEO",
            {
                "fields": (
                    "is_published",
                    ("seo_title_de", "seo_title_en"),
                    ("seo_description_de", "seo_description_en"),
                    ("geo_city", "geo_country"),
                )
            },
        ),
        ("Operations", {"fields": ("stats_overview", "deletion_policy")}),
    )

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "manager/",
                self.admin_site.admin_view(self.course_manager_view),
                name="online_course_manager",
            )
        ]
        return custom_urls + urls

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["course_manager_url"] = reverse("admin:online_course_manager")
        return super().changelist_view(request, extra_context=extra_context)

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .annotate(
                _cohorts_total=Count("cohorts", distinct=True),
                _sessions_total=Count("cohorts__sessions", distinct=True),
                _students_total=Count(
                    "enrollments",
                    filter=Q(enrollments__status__in=ONLINE_DASHBOARD_ENROLLMENT_STATUSES),
                    distinct=True,
                ),
            )
        )

    def cohorts_total(self, obj: OnlineCourse):
        return getattr(obj, "_cohorts_total", 0)

    cohorts_total.short_description = "Cohorts"
    cohorts_total.admin_order_field = "_cohorts_total"

    def sessions_total(self, obj: OnlineCourse):
        return getattr(obj, "_sessions_total", 0)

    sessions_total.short_description = "Sessions"
    sessions_total.admin_order_field = "_sessions_total"

    def students_total(self, obj: OnlineCourse):
        return getattr(obj, "_students_total", 0)

    students_total.short_description = "Students"
    students_total.admin_order_field = "_students_total"

    def stats_overview(self, obj: OnlineCourse):
        if not obj.pk:
            return "Save the course first to manage cohorts, sessions and statistics."
        return format_html(
            "Cohorts: <strong>{}</strong><br>"
            "Sessions: <strong>{}</strong><br>"
            "Students with access: <strong>{}</strong>",
            self.cohorts_total(obj),
            self.sessions_total(obj),
            self.students_total(obj),
        )

    stats_overview.short_description = "Stats overview"

    def deletion_policy(self, obj: OnlineCourse):
        if not obj.pk:
            return "New course. Hard delete is available until registrations or orders exist."
        if self._has_related_activity(obj):
            return "Archived only. Use 'Archive selected courses' or uncheck 'is published'."
        return "No registrations/orders detected. Hard delete is allowed."

    deletion_policy.short_description = "Deletion policy"

    def _has_related_activity(self, obj: OnlineCourse) -> bool:
        return obj.orders.exists() or obj.enrollments.exists()

    def has_delete_permission(self, request, obj=None):
        allowed = super().has_delete_permission(request, obj)
        if not allowed or obj is None:
            return allowed
        return not self._has_related_activity(obj)

    @admin.action(description="Archive selected courses")
    def archive_selected_courses(self, request, queryset):
        updated = queryset.update(is_published=False, updated_at=timezone.now())
        self.message_user(request, f"Archived {updated} course(s).", level=messages.SUCCESS)

    @admin.action(description="Publish selected courses")
    def publish_selected_courses(self, request, queryset):
        updated = queryset.update(is_published=True, updated_at=timezone.now())
        self.message_user(request, f"Published {updated} course(s).", level=messages.SUCCESS)

    def course_manager_view(self, request):
        manager_url = reverse("admin:online_course_manager")
        if request.method == "POST":
            action = (request.POST.get("action") or "").strip()
            if action == "generate_sessions":
                cohort_id = (request.POST.get("cohort_id") or "").strip()
                if cohort_id.isdigit():
                    cohort = (
                        OnlineCohort.objects.select_related("course")
                        .filter(id=int(cohort_id))
                        .first()
                    )
                    if cohort:
                        try:
                            result = generate_missing_sessions_for_cohort(cohort)
                        except SessionGenerationError as exc:
                            self.message_user(request, str(exc), level=messages.ERROR)
                        else:
                            if result.created_count > 0:
                                self.message_user(
                                    request,
                                    (
                                        f"{cohort.group_code}: created {result.created_count} session(s). "
                                        f"Total is now {result.final_count} / {result.target_count}."
                                    ),
                                    level=messages.SUCCESS,
                                )
                            else:
                                self.message_user(
                                    request,
                                    f"{cohort.group_code}: already has {result.final_count} / {result.target_count} sessions.",
                                    level=messages.INFO,
                                )
                        return HttpResponseRedirect(f"{manager_url}?course={cohort.course_id}")
                self.message_user(request, "Cohort not found for session generation.", level=messages.ERROR)
                return HttpResponseRedirect(manager_url)

        courses = list(OnlineCourse.objects.all().order_by("title_de", "id"))
        selected_course = None
        selected_course_id = (request.GET.get("course") or "").strip()
        if selected_course_id.isdigit():
            selected_course = next((item for item in courses if item.id == int(selected_course_id)), None)
        if selected_course is None and courses:
            selected_course = courses[0]

        selected_course_payload = course_detail_payload(selected_course) if selected_course else None
        course_cards = [course_card_payload(item) for item in courses]

        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": "Online Course Manager",
            "subtitle": "Centralized course, cohort and schedule control",
            "course_manager_url": manager_url,
            "course_list_url": reverse("admin:online_onlinecourse_changelist"),
            "cohort_list_url": reverse("admin:online_onlinecohort_changelist"),
            "courses": course_cards,
            "selected_course": selected_course_payload,
            "selected_course_id": selected_course.id if selected_course else None,
        }
        return TemplateResponse(request, "admin/online/course_manager.html", context)


@admin.register(OnlineCourseFaq)
class OnlineCourseFaqAdmin(admin.ModelAdmin):
    list_display = ("id", "course", "sort_order", "is_active")
    search_fields = ("question_de", "question_en", "course__slug")
    list_filter = ("is_active", "course")


@admin.register(OnlineCourseMaterial)
class OnlineCourseMaterialAdmin(admin.ModelAdmin):
    list_display = ("id", "course", "title", "material_type", "language", "is_active")
    search_fields = ("title", "course__slug")
    list_filter = ("material_type", "language", "is_active")


@admin.register(OnlineWorkspace)
class OnlineWorkspaceAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "kind", "slug", "sort_order", "show_on_homepage", "is_published")
    search_fields = ("title", "subtitle", "slug", "summary")
    list_filter = ("kind", "show_on_homepage", "is_published")
    ordering = ("sort_order", "id")
    inlines = (OnlineWorkspaceContentItemInline,)


@admin.register(OnlineWorkspaceContentItem)
class OnlineWorkspaceContentItemAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "workspace",
        "section",
        "title",
        "linked_course",
        "linked_cohort",
        "sort_order",
        "published_on",
        "is_active",
    )
    search_fields = ("title", "description", "workspace__title", "workspace__slug")
    list_filter = ("section", "is_active", "workspace")
    ordering = ("workspace", "section", "sort_order", "id")


@admin.register(OnlineCohort)
class OnlineCohortAdmin(DisableBulkDeleteMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "group_code",
        "name",
        "course",
        "teacher",
        "status",
        "capacity",
        "seats_left",
        "is_public",
        "sessions_total",
        "students_total",
    )
    search_fields = ("group_code", "name", "course__slug", "teacher__Vorname", "teacher__Nachname")
    list_filter = ("status", "is_public", "course")
    inlines = (OnlineSessionInline,)
    readonly_fields = ("stats_overview", "deletion_policy")
    actions = (
        "generate_missing_sessions",
        "hide_selected_cohorts",
        "make_selected_cohorts_public",
        "mark_selected_cohorts_finished",
    )
    fieldsets = (
        (
            "Cohort setup",
            {
                "fields": (
                    "course",
                    "teacher",
                    ("group_code", "name"),
                    ("status", "is_public"),
                    ("capacity", "timezone"),
                    ("start_date", "end_date"),
                )
            },
        ),
        ("Operations", {"fields": ("stats_overview", "deletion_policy")}),
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("course", "teacher")
            .annotate(
                _sessions_total=Count("sessions", distinct=True),
                _students_total=Count(
                    "enrollments",
                    filter=Q(enrollments__status__in=ONLINE_DASHBOARD_ENROLLMENT_STATUSES),
                    distinct=True,
                ),
            )
        )

    def sessions_total(self, obj: OnlineCohort):
        return getattr(obj, "_sessions_total", 0)

    sessions_total.short_description = "Sessions"
    sessions_total.admin_order_field = "_sessions_total"

    def students_total(self, obj: OnlineCohort):
        return getattr(obj, "_students_total", 0)

    students_total.short_description = "Students"
    students_total.admin_order_field = "_students_total"

    def seats_left(self, obj: OnlineCohort):
        return cohort_seats_left(obj)

    seats_left.short_description = "Seats left"

    def stats_overview(self, obj: OnlineCohort):
        if not obj.pk:
            return "Save the cohort first to manage sessions and statistics."
        next_session = nearest_session_for_cohort(obj)
        next_session_value = next_session.starts_at.strftime("%Y-%m-%d %H:%M") if next_session else "-"
        return format_html(
            "Sessions: <strong>{}</strong><br>"
            "Students with access: <strong>{}</strong><br>"
            "Seats left: <strong>{}</strong><br>"
            "Next session: <strong>{}</strong>",
            self.sessions_total(obj),
            self.students_total(obj),
            self.seats_left(obj),
            next_session_value,
        )

    stats_overview.short_description = "Stats overview"

    def deletion_policy(self, obj: OnlineCohort):
        if not obj.pk:
            return "New cohort. Hard delete is available until enrollments or orders exist."
        if self._has_related_activity(obj):
            return "Archive only. Remove from public flow with 'is public = False' and optionally mark as finished."
        return "No enrollments/orders detected. Hard delete is allowed."

    deletion_policy.short_description = "Deletion policy"

    def _has_related_activity(self, obj: OnlineCohort) -> bool:
        return obj.orders.exists() or obj.enrollments.exists()

    def has_delete_permission(self, request, obj=None):
        allowed = super().has_delete_permission(request, obj)
        if not allowed or obj is None:
            return allowed
        return not self._has_related_activity(obj)

    @admin.action(description="Generate missing sessions up to course lessons count")
    def generate_missing_sessions(self, request, queryset):
        created_total = 0
        processed = 0
        for cohort in queryset.select_related("course").order_by("course__title_de", "group_code"):
            try:
                result = generate_missing_sessions_for_cohort(cohort)
            except SessionGenerationError as exc:
                self.message_user(
                    request,
                    f"{cohort.group_code}: {exc}",
                    level=messages.ERROR,
                )
                continue

            processed += 1
            created_total += result.created_count
            level = messages.SUCCESS if result.created_count > 0 else messages.INFO
            self.message_user(
                request,
                (
                    f"{cohort.group_code}: {result.created_count} session(s) created. "
                    f"Current total {result.final_count} / {result.target_count}."
                ),
                level=level,
            )

        if processed:
            self.message_user(
                request,
                f"Session generation finished for {processed} cohort(s); created {created_total} new session(s) in total.",
                level=messages.SUCCESS,
            )

    @admin.action(description="Hide selected cohorts from public catalog")
    def hide_selected_cohorts(self, request, queryset):
        updated = queryset.update(is_public=False, updated_at=timezone.now())
        self.message_user(request, f"Hid {updated} cohort(s) from public catalog.", level=messages.SUCCESS)

    @admin.action(description="Make selected cohorts public")
    def make_selected_cohorts_public(self, request, queryset):
        updated = queryset.update(is_public=True, updated_at=timezone.now())
        self.message_user(request, f"Made {updated} cohort(s) public.", level=messages.SUCCESS)

    @admin.action(description="Mark selected cohorts as finished and hide them from public catalog")
    def mark_selected_cohorts_finished(self, request, queryset):
        updated = queryset.update(
            status=OnlineCohort.STATUS_FINISHED,
            is_public=False,
            updated_at=timezone.now(),
        )
        self.message_user(request, f"Finished {updated} cohort(s).", level=messages.SUCCESS)


@admin.register(OnlineSession)
class OnlineSessionAdmin(DisableBulkDeleteMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "cohort",
        "title",
        "starts_at",
        "ends_at",
        "status",
        "is_completed",
        "provider_meeting_id",
        "attendance_synced_at",
    )
    search_fields = ("title", "cohort__group_code", "cohort__name", "provider_meeting_id")
    list_filter = ("status", "is_completed", "cohort")
    readonly_fields = ("deletion_policy",)
    actions = ("cancel_selected_sessions",)

    def _has_related_activity(self, obj: OnlineSession) -> bool:
        return obj.attendance_records.exists() or obj.reminders.exists()

    def has_delete_permission(self, request, obj=None):
        allowed = super().has_delete_permission(request, obj)
        if not allowed or obj is None:
            return allowed
        return not self._has_related_activity(obj)

    def deletion_policy(self, obj: OnlineSession):
        if not obj.pk:
            return "New session. Hard delete is available until attendance or reminders exist."
        if self._has_related_activity(obj):
            return "Archive behavior only. Mark session canceled or ended instead of deleting it."
        return "No attendance/reminders detected. Hard delete is allowed."

    deletion_policy.short_description = "Deletion policy"

    @admin.action(description="Cancel selected sessions")
    def cancel_selected_sessions(self, request, queryset):
        updated = queryset.update(
            status=OnlineSession.STATUS_CANCELED,
            is_completed=False,
            updated_at=timezone.now(),
        )
        self.message_user(request, f"Canceled {updated} session(s).", level=messages.SUCCESS)


@admin.register(OnlineStudentProfile)
class OnlineStudentProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "first_name", "last_name", "preferred_language", "is_trial_user")
    search_fields = ("user__email", "first_name", "last_name")
    list_filter = ("preferred_language", "is_trial_user")


@admin.register(OnlineOrder)
class OnlineOrderAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "profile",
        "course",
        "provider",
        "status",
        "amount",
        "currency",
        "is_trial",
        "paid_at",
        "refunded_at",
        "provider_payment_id",
    )
    search_fields = (
        "profile__user__email",
        "course__slug",
        "external_reference",
        "idempotency_key",
        "provider_payment_id",
        "paid_event_id",
    )
    list_filter = ("provider", "status", "is_trial")


@admin.register(OnlineEnrollment)
class OnlineEnrollmentAdmin(admin.ModelAdmin):
    list_display = ("id", "profile", "course", "cohort", "status", "started_at")
    search_fields = ("profile__user__email", "course__slug", "cohort__group_code")
    list_filter = ("status", "course")


@admin.register(OnlineAttendance)
class OnlineAttendanceAdmin(admin.ModelAdmin):
    list_display = ("id", "enrollment", "session", "status", "attended_seconds", "updated_at")
    search_fields = ("enrollment__profile__user__email", "session__title")
    list_filter = ("status",)


@admin.register(OnlineFeedbackMessage)
class OnlineFeedbackMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "email", "subject", "course", "preferred_language", "is_resolved", "created_at")
    search_fields = ("email", "subject", "message")
    list_filter = ("is_resolved", "preferred_language", "course")


@admin.register(OnlineSupportMessage)
class OnlineSupportMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "profile", "sender_type", "is_read", "created_at")
    search_fields = ("profile__user__email", "message")
    list_filter = ("sender_type", "is_read")


@admin.register(OnlinePaymentEvent)
class OnlinePaymentEventAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "provider", "event_id", "status", "provider_payment_id", "processed_at")
    search_fields = ("event_id", "provider_payment_id", "order__id")
    list_filter = ("provider", "status", "signature_valid")


@admin.register(OnlineMagicLinkToken)
class OnlineMagicLinkTokenAdmin(admin.ModelAdmin):
    list_display = ("id", "profile", "cohort", "expires_at", "revoked_at", "last_used_at", "created_at")
    search_fields = ("profile__user__email", "cohort__group_code", "token_hash")
    list_filter = ("revoked_at",)


@admin.register(OnlineSessionReminder)
class OnlineSessionReminderAdmin(admin.ModelAdmin):
    list_display = ("id", "enrollment", "session", "hours_before", "email_sent", "sent_at")
    search_fields = ("enrollment__profile__user__email", "session__title")
    list_filter = ("hours_before", "email_sent")
