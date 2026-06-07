from __future__ import annotations

import re

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from rest_framework import serializers

from apps.employees.models import Lehrer
from apps.online.models import (
    OnlineCohort,
    OnlineCourse,
    OnlineCourseFaq,
    OnlineCourseMaterial,
    OnlineEnrollment,
    OnlineFeedbackMessage,
    OnlineOrder,
    OnlineSession,
    OnlineStudentProfile,
    OnlineSupportMessage,
    OnlineWorkspace,
    OnlineWorkspaceContentItem,
)
from apps.online.services.access import (
    active_online_demo_role_payload_for_user,
    online_access_payload_for_instance,
    online_access_policy_audiences_for_instance,
    online_access_policy_audience_ids_for_instance,
    online_role_catalog_payload,
)
from apps.online.services.payment_service import get_payment_mode
from apps.online.services.stats import cohort_seats_left

User = get_user_model()
DUMMY_PASSWORD_HASH = make_password("learning-hub-dummy-password")


def resolve_workspace_join_target(
    item: OnlineWorkspaceContentItem,
) -> tuple[OnlineCourse | None, OnlineCohort | None]:
    linked_course = getattr(item, "linked_course", None)
    linked_cohort = getattr(item, "linked_cohort", None)

    if linked_cohort and linked_cohort.course_id:
        if linked_course is None:
            linked_course = linked_cohort.course
        if linked_course and linked_cohort.course_id == linked_course.id and linked_cohort.is_public:
            return linked_course, linked_cohort

    if linked_course is None or not linked_course.is_published:
        return None, None

    target_cohort = (
        OnlineCohort.objects.filter(course=linked_course, is_public=True)
        .order_by("start_date", "id")
        .first()
    )
    return linked_course, target_cohort


def _validate_strong_password(raw_password: str) -> None:
    if len(raw_password) < 10:
        raise serializers.ValidationError("Password must contain at least 10 characters.")
    if not re.search(r"[A-Za-z]", raw_password) or not re.search(r"[0-9]", raw_password):
        raise serializers.ValidationError("Password must contain letters and numbers.")
    try:
        validate_password(raw_password)
    except DjangoValidationError as exc:
        raise serializers.ValidationError(list(exc.messages))


class PublicCohortSerializer(serializers.ModelSerializer):
    seats_left = serializers.SerializerMethodField()

    class Meta:
        model = OnlineCohort
        fields = ("id", "name", "group_code", "capacity", "seats_left", "start_date", "status")

    def get_seats_left(self, obj: OnlineCohort) -> int:
        return cohort_seats_left(obj)


class PublicCourseFaqSerializer(serializers.ModelSerializer):
    question = serializers.SerializerMethodField()
    answer = serializers.SerializerMethodField()

    class Meta:
        model = OnlineCourseFaq
        fields = ("id", "question", "answer", "sort_order")

    def _locale(self) -> str:
        return self.context.get("locale", "de")

    def get_question(self, obj: OnlineCourseFaq) -> str:
        if self._locale() == "en":
            return obj.question_en
        return obj.question_de

    def get_answer(self, obj: OnlineCourseFaq) -> str:
        if self._locale() == "en":
            return obj.answer_en
        return obj.answer_de


class PublicCourseListSerializer(serializers.ModelSerializer):
    title = serializers.SerializerMethodField()
    short_description = serializers.SerializerMethodField()

    class Meta:
        model = OnlineCourse
        fields = (
            "id",
            "slug",
            "title",
            "short_description",
            "lessons_count",
            "trial_available",
            "price_amount",
            "currency",
            "is_subscription",
            "hero_image_url",
            "geo_city",
            "geo_country",
        )

    def _locale(self) -> str:
        return self.context.get("locale", "de")

    def get_title(self, obj: OnlineCourse) -> str:
        return obj.localized_title(self._locale())

    def get_short_description(self, obj: OnlineCourse) -> str:
        return obj.localized_short_description(self._locale())


class PublicCourseDetailSerializer(PublicCourseListSerializer):
    description = serializers.SerializerMethodField()
    faq_items = serializers.SerializerMethodField()
    cohorts = serializers.SerializerMethodField()
    seo_title = serializers.SerializerMethodField()
    seo_description = serializers.SerializerMethodField()

    class Meta(PublicCourseListSerializer.Meta):
        fields = PublicCourseListSerializer.Meta.fields + (
            "description",
            "faq_items",
            "cohorts",
            "seo_title",
            "seo_description",
        )

    def get_description(self, obj: OnlineCourse) -> str:
        return obj.localized_description(self._locale())

    def get_faq_items(self, obj: OnlineCourse):
        qs = obj.faqs.filter(is_active=True).order_by("sort_order", "id")
        return PublicCourseFaqSerializer(qs, many=True, context=self.context).data

    def get_cohorts(self, obj: OnlineCourse):
        qs = obj.cohorts.filter(is_public=True).order_by("start_date", "id")
        return PublicCohortSerializer(qs, many=True).data

    def get_seo_title(self, obj: OnlineCourse) -> str:
        if self._locale() == "en":
            return obj.seo_title_en or obj.title_en
        return obj.seo_title_de or obj.title_de

    def get_seo_description(self, obj: OnlineCourse) -> str:
        if self._locale() == "en":
            return obj.seo_description_en or obj.short_description_en
        return obj.seo_description_de or obj.short_description_de


class PublicWorkspaceCardSerializer(serializers.ModelSerializer):
    iconKey = serializers.CharField(source="icon_key")
    sortOrder = serializers.IntegerField(source="sort_order")
    showOnHomepage = serializers.BooleanField(source="show_on_homepage")
    isPublished = serializers.BooleanField(source="is_published")

    class Meta:
        model = OnlineWorkspace
        fields = (
            "id",
            "slug",
            "title",
            "subtitle",
            "summary",
            "iconKey",
            "kind",
            "sortOrder",
            "showOnHomepage",
            "isPublished",
        )


class PublicWorkspaceDetailSerializer(PublicWorkspaceCardSerializer):
    availableSections = serializers.SerializerMethodField()
    courses = serializers.SerializerMethodField()
    assignments = serializers.SerializerMethodField()
    recordings = serializers.SerializerMethodField()
    materials = serializers.SerializerMethodField()
    roleCatalog = serializers.SerializerMethodField()
    activeRole = serializers.SerializerMethodField()
    accessNotice = serializers.SerializerMethodField()

    class Meta(PublicWorkspaceCardSerializer.Meta):
        fields = PublicWorkspaceCardSerializer.Meta.fields + (
            "availableSections",
            "roleCatalog",
            "activeRole",
            "accessNotice",
            "courses",
            "assignments",
            "recordings",
            "materials",
        )

    def _items_for(self, obj: OnlineWorkspace, section: str):
        return [
            item
            for item in getattr(obj, "prefetched_public_items", list(obj.content_items.filter(is_active=True)))
            if item.section == section and item.is_active
        ]

    def _combined_access_payload(self, workspace: OnlineWorkspace, item: OnlineWorkspaceContentItem):
        request = self.context.get("request")
        workspace_access = online_access_payload_for_instance(workspace, getattr(request, "user", None))
        item_access = online_access_payload_for_instance(item, getattr(request, "user", None))
        required_labels = list(
            dict.fromkeys(
                [
                    *workspace_access["requiredAudienceLabels"],
                    *item_access["requiredAudienceLabels"],
                ]
            )
        )
        required_slugs = list(
            dict.fromkeys(
                [
                    *workspace_access["requiredAudienceSlugs"],
                    *item_access["requiredAudienceSlugs"],
                ]
            )
        )
        return {
            "isAccessible": bool(workspace_access["isAccessible"] and item_access["isAccessible"]),
            "requiredAudienceLabels": required_labels,
            "requiredAudienceSlugs": required_slugs,
            "accessMessage": item_access["accessMessage"] or workspace_access["accessMessage"],
        }

    def get_availableSections(self, obj: OnlineWorkspace):
        sections: list[str] = []
        for section, _label in OnlineWorkspaceContentItem.SECTION_CHOICES:
            if self._items_for(obj, section):
                sections.append(section)
        return sections

    def get_courses(self, obj: OnlineWorkspace):
        payload = []
        for item in self._items_for(obj, OnlineWorkspaceContentItem.SECTION_COURSES):
            linked_course, target_cohort = resolve_workspace_join_target(item)
            combined_access = self._combined_access_payload(obj, item)
            payload.append(
                {
                    "id": item.id,
                    "title": item.title,
                    "description": item.description,
                    "imageUrl": item.preview_image_url,
                    "duration": item.primary_meta,
                    "format": item.secondary_meta,
                    "startsAt": linked_course.starts_at.isoformat() if linked_course and linked_course.starts_at else "",
                    "endsAt": linked_course.ends_at.isoformat() if linked_course and linked_course.ends_at else "",
                    "linkedCourseId": linked_course.id if linked_course else None,
                    "linkedCourseSlug": linked_course.slug if linked_course else "",
                    "linkedCohortId": target_cohort.id if target_cohort else None,
                    "linkedGroupCode": target_cohort.group_code if target_cohort else "",
                    "joinEnabled": bool(linked_course and target_cohort and combined_access["isAccessible"]),
                    "isAccessible": combined_access["isAccessible"],
                    "requiredAudienceLabels": combined_access["requiredAudienceLabels"],
                    "requiredAudienceSlugs": combined_access["requiredAudienceSlugs"],
                    "accessMessage": combined_access["accessMessage"],
                }
            )
        return payload

    def get_assignments(self, obj: OnlineWorkspace):
        payload = []
        for item in self._items_for(obj, OnlineWorkspaceContentItem.SECTION_ASSIGNMENTS):
            combined_access = self._combined_access_payload(obj, item)
            payload.append(
                {
                    "id": item.id,
                    "title": item.title,
                    "description": item.description,
                    "notebookLabel": item.primary_meta,
                    "difficulty": item.secondary_meta,
                    "isAccessible": combined_access["isAccessible"],
                    "requiredAudienceLabels": combined_access["requiredAudienceLabels"],
                    "requiredAudienceSlugs": combined_access["requiredAudienceSlugs"],
                    "accessMessage": combined_access["accessMessage"],
                }
            )
        return payload

    def get_recordings(self, obj: OnlineWorkspace):
        payload = []
        for item in self._items_for(obj, OnlineWorkspaceContentItem.SECTION_RECORDINGS):
            combined_access = self._combined_access_payload(obj, item)
            payload.append(
                {
                    "id": item.id,
                    "title": item.title,
                    "description": item.description,
                    "date": item.published_on.isoformat() if item.published_on else "",
                    "duration": item.secondary_meta,
                    "thumbnailUrl": item.preview_image_url,
                    "videoUrl": item.asset_url,
                    "isAccessible": combined_access["isAccessible"],
                    "requiredAudienceLabels": combined_access["requiredAudienceLabels"],
                    "requiredAudienceSlugs": combined_access["requiredAudienceSlugs"],
                    "accessMessage": combined_access["accessMessage"],
                }
            )
        return payload

    def get_materials(self, obj: OnlineWorkspace):
        payload = []
        for item in self._items_for(obj, OnlineWorkspaceContentItem.SECTION_MATERIALS):
            combined_access = self._combined_access_payload(obj, item)
            payload.append(
                {
                    "id": item.id,
                    "title": item.title,
                    "description": item.description,
                    "date": item.published_on.isoformat() if item.published_on else "",
                    "category": item.primary_meta,
                    "documentUrl": item.asset_url,
                    "isAccessible": combined_access["isAccessible"],
                    "requiredAudienceLabels": combined_access["requiredAudienceLabels"],
                    "requiredAudienceSlugs": combined_access["requiredAudienceSlugs"],
                    "accessMessage": combined_access["accessMessage"],
                }
            )
        return payload

    def get_roleCatalog(self, obj: OnlineWorkspace):
        return online_role_catalog_payload()

    def get_activeRole(self, obj: OnlineWorkspace):
        request = self.context.get("request")
        return active_online_demo_role_payload_for_user(getattr(request, "user", None))

    def get_accessNotice(self, obj: OnlineWorkspace) -> str:
        return (
            "You can only use academy materials that match your assigned role. "
            "If you need more access, contact an administrator."
        )


class BaseOnlineSignupSerializer(serializers.Serializer):
    course_slug = serializers.SlugField()
    cohort_id = serializers.IntegerField(required=False)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    first_name = serializers.CharField(max_length=120)
    last_name = serializers.CharField(max_length=120)
    phone = serializers.CharField(max_length=50, required=False, allow_blank=True)
    preferred_language = serializers.ChoiceField(choices=("de", "en"), default="de")
    idempotency_key = serializers.CharField(max_length=120, required=False, allow_blank=True)

    def validate_password(self, value: str) -> str:
        _validate_strong_password(value)
        return value

    def validate(self, attrs):
        course_slug = attrs["course_slug"]
        course = OnlineCourse.objects.filter(slug=course_slug, is_published=True).first()
        if not course:
            raise serializers.ValidationError({"course_slug": "Course not found."})

        cohort_id = attrs.get("cohort_id")
        cohort_qs = OnlineCohort.objects.filter(course=course, is_public=True).order_by("start_date", "id")
        if cohort_id:
            cohort = cohort_qs.filter(id=cohort_id).first()
            if not cohort:
                raise serializers.ValidationError({"cohort_id": "Cohort not found for this course."})
        else:
            cohort = cohort_qs.filter(status__in=(OnlineCohort.STATUS_OPEN, OnlineCohort.STATUS_RUNNING)).first()
            cohort = cohort or cohort_qs.first()
            if not cohort:
                raise serializers.ValidationError({"cohort_id": "No cohort available for this course."})

        attrs["course"] = course
        attrs["cohort"] = cohort
        attrs["email"] = attrs["email"].strip().lower()
        attrs["first_name"] = attrs["first_name"].strip()
        attrs["last_name"] = attrs["last_name"].strip()
        return attrs


class TrialSignupSerializer(BaseOnlineSignupSerializer):
    def validate(self, attrs):
        attrs = super().validate(attrs)
        if not attrs["course"].trial_available:
            raise serializers.ValidationError({"course_slug": "Trial is not available for this course."})
        return attrs


class MockCheckoutSerializer(BaseOnlineSignupSerializer):
    provider = serializers.ChoiceField(choices=("paypal", "klarna", "sofort"), required=False)
    accept_terms = serializers.BooleanField()

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if attrs["course"].price_amount <= 0:
            raise serializers.ValidationError({"course_slug": "Paid checkout is not available for this course."})
        if not attrs["accept_terms"]:
            raise serializers.ValidationError({"accept_terms": "Terms must be accepted."})
        attrs["provider"] = attrs.get("provider") or OnlineOrder.PROVIDER_PAYPAL
        return attrs


class CheckoutStartSerializer(BaseOnlineSignupSerializer):
    provider = serializers.ChoiceField(choices=("paypal", "klarna", "sofort"), required=False)
    accept_terms = serializers.BooleanField()

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if attrs["course"].price_amount <= 0:
            raise serializers.ValidationError({"course_slug": "Paid checkout is not available for this course."})
        if not attrs["accept_terms"]:
            raise serializers.ValidationError({"accept_terms": "Terms must be accepted."})
        provider = attrs.get("provider")
        if get_payment_mode() == "free":
            attrs["provider"] = provider or OnlineOrder.PROVIDER_PAYPAL
        elif not provider:
            raise serializers.ValidationError({"provider": "Payment provider is required."})
        return attrs


class GoogleCheckoutSerializer(serializers.Serializer):
    credential = serializers.CharField(write_only=True, trim_whitespace=True)
    mode = serializers.ChoiceField(choices=("trial", "paid"), default="trial")
    course_slug = serializers.SlugField()
    cohort_id = serializers.IntegerField(required=False)
    provider = serializers.ChoiceField(choices=("paypal", "klarna", "sofort"), required=False)
    accept_terms = serializers.BooleanField(required=False, default=False)
    phone = serializers.CharField(max_length=50, required=False, allow_blank=True)
    preferred_language = serializers.ChoiceField(choices=("de", "en"), default="de")
    idempotency_key = serializers.CharField(max_length=120, required=False, allow_blank=True)

    def validate(self, attrs):
        course_slug = attrs["course_slug"]
        course = OnlineCourse.objects.filter(slug=course_slug, is_published=True).first()
        if not course:
            raise serializers.ValidationError({"course_slug": "Course not found."})

        cohort_id = attrs.get("cohort_id")
        cohort_qs = OnlineCohort.objects.filter(course=course, is_public=True).order_by("start_date", "id")
        if cohort_id:
            cohort = cohort_qs.filter(id=cohort_id).first()
            if not cohort:
                raise serializers.ValidationError({"cohort_id": "Cohort not found for this course."})
        else:
            cohort = cohort_qs.filter(status__in=(OnlineCohort.STATUS_OPEN, OnlineCohort.STATUS_RUNNING)).first()
            cohort = cohort or cohort_qs.first()
            if not cohort:
                raise serializers.ValidationError({"cohort_id": "No cohort available for this course."})

        mode = attrs.get("mode", "trial")
        if mode == "trial":
            if not course.trial_available:
                raise serializers.ValidationError({"course_slug": "Trial is not available for this course."})
        else:
            if course.price_amount <= 0:
                raise serializers.ValidationError({"course_slug": "Paid checkout is not available for this course."})
            if not attrs.get("accept_terms", False):
                raise serializers.ValidationError({"accept_terms": "Terms must be accepted."})
            provider = attrs.get("provider")
            if get_payment_mode() == "free":
                attrs["provider"] = provider or OnlineOrder.PROVIDER_PAYPAL
            elif not provider:
                raise serializers.ValidationError({"provider": "Payment provider is required."})

        attrs["course"] = course
        attrs["cohort"] = cohort
        attrs["idempotency_key"] = (attrs.get("idempotency_key") or "").strip()
        return attrs


class GoogleLoginSerializer(serializers.Serializer):
    credential = serializers.CharField(write_only=True, trim_whitespace=True)


class MagicLinkRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()
    course_slug = serializers.SlugField(required=False)

    def validate(self, attrs):
        attrs["email"] = attrs["email"].strip().lower()
        course_slug = attrs.get("course_slug")
        if course_slug:
            course = OnlineCourse.objects.filter(slug=course_slug, is_published=True).first()
            if not course:
                raise serializers.ValidationError({"course_slug": "Course not found."})
            attrs["course"] = course
        return attrs


class OnlineLoginSerializer(serializers.Serializer):
    identifier = serializers.CharField(max_length=180)
    password = serializers.CharField(trim_whitespace=False)

    def validate(self, attrs):
        identifier = attrs["identifier"].strip()
        password = attrs["password"]

        user = User.objects.filter(Q(email__iexact=identifier) | Q(username__iexact=identifier)).first()
        password_hash = user.password if user is not None else DUMMY_PASSWORD_HASH
        if not check_password(password, password_hash) or not user or not user.is_active:
            raise serializers.ValidationError({"detail": "Invalid credentials."})
        if not hasattr(user, "online_profile"):
            raise serializers.ValidationError({"identifier": "User is not registered for online courses."})

        attrs["user"] = user
        return attrs


class OnlineStaffLoginSerializer(serializers.Serializer):
    ROLE_ANY = "any"
    ROLE_TEACHER = "teacher"
    ROLE_ADMIN = "admin"

    identifier = serializers.CharField(max_length=180)
    password = serializers.CharField(trim_whitespace=False)
    role = serializers.ChoiceField(
        choices=(ROLE_ANY, ROLE_TEACHER, ROLE_ADMIN),
        required=False,
        default=ROLE_ANY,
    )

    def validate(self, attrs):
        identifier = attrs["identifier"].strip()
        password = attrs["password"]
        role = attrs.get("role", self.ROLE_ANY)

        user = User.objects.filter(Q(email__iexact=identifier) | Q(username__iexact=identifier)).first()
        password_hash = user.password if user is not None else DUMMY_PASSWORD_HASH
        if not check_password(password, password_hash) or not user or not user.is_active:
            raise serializers.ValidationError({"detail": "Invalid credentials."})

        is_teacher = hasattr(user, "lehrer_user")
        is_admin = bool(user.is_admin or user.is_superuser)
        if role == self.ROLE_TEACHER and not is_teacher:
            raise serializers.ValidationError({"role": "Teacher access required."})
        if role == self.ROLE_ADMIN and not is_admin:
            raise serializers.ValidationError({"role": "Admin access required."})
        if role == self.ROLE_ANY and not (is_teacher or is_admin):
            raise serializers.ValidationError({"identifier": "Staff access is not enabled for this user."})

        attrs["user"] = user
        return attrs


class OnlineStudentProfileSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email")
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = OnlineStudentProfile
        fields = (
            "email",
            "first_name",
            "last_name",
            "phone",
            "gender",
            "avatar_url",
            "preferred_language",
            "is_trial_user",
        )

    def get_avatar_url(self, obj: OnlineStudentProfile) -> str:
        if not obj.avatar:
            return ""
        url = f"/api/online/media/student-avatars/{obj.id}/"
        request = self.context.get("request")
        if request:
            return request.build_absolute_uri(url)
        return url


class OnlineStudentProfileUpdateSerializer(serializers.Serializer):
    MAX_AVATAR_SIZE_BYTES = 5 * 1024 * 1024
    ALLOWED_AVATAR_CONTENT_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}

    phone = serializers.CharField(max_length=50, required=False, allow_blank=True)
    gender = serializers.ChoiceField(choices=OnlineStudentProfile.GENDER_CHOICES, required=False)
    avatar = serializers.ImageField(required=False, allow_null=True)
    remove_avatar = serializers.BooleanField(required=False, default=False)

    def validate_avatar(self, value):
        if value is None:
            return value
        content_type = getattr(value, "content_type", "") or ""
        if content_type and content_type not in self.ALLOWED_AVATAR_CONTENT_TYPES:
            raise serializers.ValidationError("Unsupported image format. Use JPG, PNG, or WEBP.")
        if value.size > self.MAX_AVATAR_SIZE_BYTES:
            raise serializers.ValidationError("Avatar is too large. Maximum size is 5 MB.")
        return value


class OnlineTeacherProfileSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email")
    firstName = serializers.CharField(source="Vorname")
    lastName = serializers.CharField(source="Nachname")
    fullName = serializers.SerializerMethodField()
    schoolEmail = serializers.EmailField(source="Schule_Email")
    privateEmail = serializers.EmailField(source="Private_Email", allow_blank=True)
    phone = serializers.CharField(source="Telefonnummer", allow_blank=True, allow_null=True)
    shortName = serializers.CharField(source="KurzName")

    class Meta:
        model = Lehrer
        fields = (
            "id",
            "firstName",
            "lastName",
            "fullName",
            "schoolEmail",
            "privateEmail",
            "phone",
            "shortName",
            "email",
        )

    def get_fullName(self, obj: Lehrer) -> str:
        return f"{obj.Vorname} {obj.Nachname}".strip()


class OnlineTeacherProfileUpdateSerializer(serializers.Serializer):
    firstName = serializers.CharField(max_length=255, required=False)
    lastName = serializers.CharField(max_length=255, required=False)
    privateEmail = serializers.EmailField(required=False, allow_blank=True)
    phone = serializers.CharField(max_length=25, required=False, allow_blank=True)

    def validate(self, attrs):
        for key, value in list(attrs.items()):
            if isinstance(value, str):
                attrs[key] = value.strip()
        return attrs


class OnlineTeacherFeedbackCreateSerializer(serializers.Serializer):
    subject = serializers.CharField(max_length=220)
    message = serializers.CharField(max_length=4000)
    course_slug = serializers.SlugField(required=False, allow_blank=True)

    def validate_subject(self, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise serializers.ValidationError("Subject cannot be empty.")
        return cleaned

    def validate_message(self, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise serializers.ValidationError("Message cannot be empty.")
        return cleaned

    def validate(self, attrs):
        course_slug = (attrs.get("course_slug") or "").strip()
        if course_slug:
            course = OnlineCourse.objects.filter(slug=course_slug, is_published=True).first()
            if not course:
                raise serializers.ValidationError({"course_slug": "Course not found."})
            attrs["course"] = course
            attrs["course_slug"] = course_slug
        return attrs


class OnlineSessionSerializer(serializers.ModelSerializer):
    attendance_status = serializers.SerializerMethodField()
    attended_seconds = serializers.SerializerMethodField()

    class Meta:
        model = OnlineSession
        fields = (
            "id",
            "title",
            "description",
            "starts_at",
            "ends_at",
            "status",
            "join_url",
            "recording_url",
            "is_completed",
            "attendance_status",
            "attended_seconds",
        )

    def get_attendance_status(self, obj: OnlineSession):
        attendance_map = self.context.get("attendance_map", {})
        record = attendance_map.get(obj.id)
        return record.status if record else "unknown"

    def get_attended_seconds(self, obj: OnlineSession):
        attendance_map = self.context.get("attendance_map", {})
        record = attendance_map.get(obj.id)
        return record.attended_seconds if record else 0


class OnlineCourseMaterialSerializer(serializers.ModelSerializer):
    class Meta:
        model = OnlineCourseMaterial
        fields = ("id", "title", "description", "material_type", "language", "link_url", "sort_order")


class OnlineSupportMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = OnlineSupportMessage
        fields = ("id", "sender_type", "message", "is_read", "created_at")


class OnlineSupportMessageCreateSerializer(serializers.Serializer):
    enrollment_id = serializers.IntegerField(required=False)
    message = serializers.CharField(max_length=4000)

    def validate_message(self, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise serializers.ValidationError("Message cannot be empty.")
        return cleaned


class OnlineFeedbackCreateSerializer(serializers.Serializer):
    course_slug = serializers.SlugField(required=False)
    full_name = serializers.CharField(max_length=180)
    email = serializers.EmailField()
    subject = serializers.CharField(max_length=220)
    message = serializers.CharField(max_length=4000)
    preferred_language = serializers.ChoiceField(choices=("de", "en"), default="de")
    source_page = serializers.CharField(max_length=200, required=False, allow_blank=True)

    def validate(self, attrs):
        course_slug = attrs.get("course_slug")
        if course_slug:
            course = OnlineCourse.objects.filter(slug=course_slug).first()
            if not course:
                raise serializers.ValidationError({"course_slug": "Course not found."})
            attrs["course"] = course
        return attrs


class OnlineFeedbackSerializer(serializers.ModelSerializer):
    class Meta:
        model = OnlineFeedbackMessage
        fields = (
            "id",
            "full_name",
            "email",
            "subject",
            "message",
            "preferred_language",
            "source_page",
            "created_at",
        )


class OnlineAdminSessionStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=OnlineSession.STATUS_CHOICES)


class OnlineAdminCuratorCreateSerializer(serializers.Serializer):
    userId = serializers.IntegerField()
    firstName = serializers.CharField(max_length=255)
    lastName = serializers.CharField(max_length=255)
    schoolEmail = serializers.EmailField()
    privateEmail = serializers.EmailField(required=False, allow_blank=True)
    phone = serializers.CharField(max_length=25, required=False, allow_blank=True)
    shortName = serializers.CharField(max_length=20)

    def validate(self, attrs):
        for key, value in list(attrs.items()):
            if isinstance(value, str):
                attrs[key] = value.strip()
        attrs["shortName"] = attrs["shortName"].replace(" ", "").upper()
        return attrs


class OnlineAdminCuratorOnboardingSerializer(serializers.Serializer):
    email = serializers.EmailField()
    temporaryPassword = serializers.CharField(trim_whitespace=False)
    firstName = serializers.CharField(max_length=255)
    lastName = serializers.CharField(max_length=255)
    schoolEmail = serializers.EmailField()
    privateEmail = serializers.EmailField(required=False, allow_blank=True)
    phone = serializers.CharField(max_length=25, required=False, allow_blank=True)
    shortName = serializers.CharField(max_length=20)

    def validate_temporaryPassword(self, value: str) -> str:
        _validate_strong_password(value)
        return value

    def validate(self, attrs):
        for key, value in list(attrs.items()):
            if isinstance(value, str):
                attrs[key] = value.strip()
        attrs["email"] = attrs["email"].lower()
        attrs["shortName"] = attrs["shortName"].replace(" ", "").upper()
        return attrs


class OnlineAdminUserStatusSerializer(serializers.Serializer):
    isActive = serializers.BooleanField()


class OnlineAdminUserTemporaryPasswordSerializer(serializers.Serializer):
    temporaryPassword = serializers.CharField(trim_whitespace=False)

    def validate_temporaryPassword(self, value: str) -> str:
        _validate_strong_password(value)
        return value


class OnlineAdminCuratorUpdateSerializer(serializers.Serializer):
    firstName = serializers.CharField(max_length=255, required=False)
    lastName = serializers.CharField(max_length=255, required=False)
    schoolEmail = serializers.EmailField(required=False)
    privateEmail = serializers.EmailField(required=False, allow_blank=True)
    phone = serializers.CharField(max_length=25, required=False, allow_blank=True)
    shortName = serializers.CharField(max_length=20, required=False)

    def validate(self, attrs):
        for key, value in list(attrs.items()):
            if isinstance(value, str):
                attrs[key] = value.strip()
        if "shortName" in attrs:
            attrs["shortName"] = attrs["shortName"].replace(" ", "").upper()
        return attrs


class OnlineAdminCohortCuratorAssignmentSerializer(serializers.Serializer):
    curatorId = serializers.IntegerField(required=False, allow_null=True)


class OnlineAdminSessionListQuerySerializer(serializers.Serializer):
    q = serializers.CharField(required=False, allow_blank=True)
    course_id = serializers.IntegerField(required=False, min_value=1)
    cohort_id = serializers.IntegerField(required=False, min_value=1)
    teacher_id = serializers.IntegerField(required=False, min_value=1)
    status = serializers.ChoiceField(choices=OnlineSession.STATUS_CHOICES, required=False)
    starts_from = serializers.DateTimeField(required=False)
    starts_to = serializers.DateTimeField(required=False)
    attendance_synced = serializers.BooleanField(required=False)
    has_join_url = serializers.BooleanField(required=False)
    has_recording = serializers.BooleanField(required=False)

    def validate(self, attrs):
        if attrs.get("starts_from") and attrs.get("starts_to") and attrs["starts_from"] > attrs["starts_to"]:
            raise serializers.ValidationError({"starts_to": "starts_to must be greater than or equal to starts_from."})
        return attrs


class OnlineAdminSessionBulkActionSerializer(serializers.Serializer):
    ACTION_OPEN = "open"
    ACTION_END = "end"
    ACTION_SYNC = "sync"

    action = serializers.ChoiceField(choices=(ACTION_OPEN, ACTION_END, ACTION_SYNC))
    sessionIds = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
        max_length=100,
    )

    def validate_sessionIds(self, value: list[int]) -> list[int]:
        unique_ids = list(dict.fromkeys(value))
        if len(unique_ids) != len(value):
            return unique_ids
        return value


class OnlineAdminWorkspaceSerializer(serializers.ModelSerializer):
    iconKey = serializers.CharField(source="icon_key")
    sortOrder = serializers.IntegerField(source="sort_order")
    showOnHomepage = serializers.BooleanField(source="show_on_homepage")
    isPublished = serializers.BooleanField(source="is_published")
    activeItemsCount = serializers.SerializerMethodField()
    sectionCounts = serializers.SerializerMethodField()
    audienceIds = serializers.SerializerMethodField()
    audiences = serializers.SerializerMethodField()

    class Meta:
        model = OnlineWorkspace
        fields = (
            "id",
            "slug",
            "title",
            "subtitle",
            "summary",
            "iconKey",
            "kind",
            "sortOrder",
            "showOnHomepage",
            "isPublished",
            "audienceIds",
            "audiences",
            "activeItemsCount",
            "sectionCounts",
        )

    def get_activeItemsCount(self, obj: OnlineWorkspace) -> int:
        return int(getattr(obj, "active_items_count", obj.content_items.filter(is_active=True).count()))

    def get_sectionCounts(self, obj: OnlineWorkspace) -> dict[str, int]:
        prefetched_items = getattr(obj, "prefetched_content_items", None)
        if prefetched_items is None:
            items = list(obj.content_items.filter(is_active=True))
        else:
            items = [item for item in prefetched_items if item.is_active]
        counts = {section: 0 for section, _label in OnlineWorkspaceContentItem.SECTION_CHOICES}
        for item in items:
            counts[item.section] = counts.get(item.section, 0) + 1
        return counts

    def get_audienceIds(self, obj: OnlineWorkspace) -> list[int]:
        return online_access_policy_audience_ids_for_instance(obj)

    def get_audiences(self, obj: OnlineWorkspace) -> list[dict[str, object]]:
        return [
            {
                "id": audience.id,
                "slug": audience.slug,
                "name": audience.name,
                "shortLabel": audience.short_label or audience.name,
            }
            for audience in online_access_policy_audiences_for_instance(obj)
        ]


class OnlineAdminWorkspaceUpsertSerializer(serializers.ModelSerializer):
    iconKey = serializers.CharField(source="icon_key")
    sortOrder = serializers.IntegerField(source="sort_order", required=False)
    showOnHomepage = serializers.BooleanField(source="show_on_homepage", required=False)
    isPublished = serializers.BooleanField(source="is_published", required=False)
    audienceIds = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        allow_empty=True,
        write_only=True,
    )

    class Meta:
        model = OnlineWorkspace
        fields = (
            "slug",
            "title",
            "subtitle",
            "summary",
            "iconKey",
            "kind",
            "sortOrder",
            "showOnHomepage",
            "isPublished",
            "audienceIds",
        )


class OnlineAdminWorkspaceContentItemSerializer(serializers.ModelSerializer):
    previewImageUrl = serializers.CharField(source="preview_image_url", allow_blank=True, required=False)
    assetUrl = serializers.CharField(source="asset_url", allow_blank=True, required=False)
    primaryMeta = serializers.CharField(source="primary_meta", allow_blank=True, required=False)
    secondaryMeta = serializers.CharField(source="secondary_meta", allow_blank=True, required=False)
    publishedOn = serializers.DateField(source="published_on", allow_null=True, required=False)
    sortOrder = serializers.IntegerField(source="sort_order", required=False)
    isActive = serializers.BooleanField(source="is_active", required=False)
    workspaceId = serializers.IntegerField(source="workspace_id", read_only=True)
    linkedCourseId = serializers.IntegerField(source="linked_course_id", read_only=True)
    linkedCourseSlug = serializers.CharField(source="linked_course.slug", read_only=True, default="")
    linkedCohortId = serializers.IntegerField(source="linked_cohort_id", read_only=True)
    linkedCohortCode = serializers.CharField(source="linked_cohort.group_code", read_only=True, default="")
    audienceIds = serializers.SerializerMethodField()
    audiences = serializers.SerializerMethodField()

    class Meta:
        model = OnlineWorkspaceContentItem
        fields = (
            "id",
            "workspaceId",
            "section",
            "title",
            "description",
            "previewImageUrl",
            "assetUrl",
            "linkedCourseId",
            "linkedCourseSlug",
            "linkedCohortId",
            "linkedCohortCode",
            "audienceIds",
            "audiences",
            "primaryMeta",
            "secondaryMeta",
            "publishedOn",
            "sortOrder",
            "isActive",
        )

    def get_audienceIds(self, obj: OnlineWorkspaceContentItem) -> list[int]:
        return online_access_policy_audience_ids_for_instance(obj)

    def get_audiences(self, obj: OnlineWorkspaceContentItem) -> list[dict[str, object]]:
        return [
            {
                "id": audience.id,
                "slug": audience.slug,
                "name": audience.name,
                "shortLabel": audience.short_label or audience.name,
            }
            for audience in online_access_policy_audiences_for_instance(obj)
        ]


class OnlineAdminWorkspaceContentItemUpsertSerializer(OnlineAdminWorkspaceContentItemSerializer):
    linkedCourseId = serializers.PrimaryKeyRelatedField(
        source="linked_course",
        queryset=OnlineCourse.objects.all(),
        allow_null=True,
        required=False,
    )
    linkedCohortId = serializers.PrimaryKeyRelatedField(
        source="linked_cohort",
        queryset=OnlineCohort.objects.select_related("course").all(),
        allow_null=True,
        required=False,
    )
    audienceIds = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        allow_empty=True,
        write_only=True,
    )

    class Meta(OnlineAdminWorkspaceContentItemSerializer.Meta):
        fields = (
            "section",
            "title",
            "description",
            "previewImageUrl",
            "assetUrl",
            "linkedCourseId",
            "linkedCohortId",
            "audienceIds",
            "primaryMeta",
            "secondaryMeta",
            "publishedOn",
            "sortOrder",
            "isActive",
        )

    def validate(self, attrs):
        attrs = super().validate(attrs)

        section = attrs.get("section")
        linked_course = attrs.get("linked_course")
        linked_cohort = attrs.get("linked_cohort")
        instance = getattr(self, "instance", None)

        if section is None and instance is not None:
            section = instance.section
        if linked_course is None and instance is not None:
            linked_course = instance.linked_course
        if linked_cohort is None and instance is not None:
            linked_cohort = instance.linked_cohort

        if section != OnlineWorkspaceContentItem.SECTION_COURSES:
            attrs["linked_course"] = None
            attrs["linked_cohort"] = None
            return attrs

        if linked_cohort is not None:
            if not linked_cohort.is_public:
                raise serializers.ValidationError({"linkedCohortId": "Only public cohorts can be exposed for self-enrollment."})
            if linked_course is not None and linked_cohort.course_id != linked_course.id:
                raise serializers.ValidationError({"linkedCohortId": "Selected cohort does not belong to the chosen course."})
            if linked_course is None:
                attrs["linked_course"] = linked_cohort.course
                linked_course = linked_cohort.course

        if linked_course is not None and not linked_course.is_published:
            raise serializers.ValidationError({"linkedCourseId": "Only published courses can be linked to public course cards."})

        return attrs
