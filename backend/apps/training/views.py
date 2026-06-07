from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.db.models import Q
from django.http import FileResponse, Http404, HttpResponseRedirect
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle, UserRateThrottle
from rest_framework.views import APIView

from apps.online.permissions import IsOnlineAdmin
from apps.training.admin_serializers import (
    TrainingAdminAiAnalyticsSerializer,
    TrainingAdminAiConversationPatchSerializer,
    TrainingAdminAiConversationSerializer,
    TrainingAdminAiOverviewSerializer,
    TrainingAdminAiRebuildIndexSerializer,
    TrainingAdminAuditEventSerializer,
    TrainingAdminAudienceSerializer,
    TrainingAdminAudienceWriteSerializer,
    TrainingAdminContentSyncEventSerializer,
    TrainingAdminContentGovernanceSerializer,
    TrainingAdminCourseRoleAssignmentPatchSerializer,
    TrainingAdminCourseRoleAssignmentSerializer,
    TrainingAdminCourseRoleAssignmentWriteSerializer,
    TrainingAdminGraderJobSerializer,
    TrainingAdminNotebookAssignmentSerializer,
    TrainingAdminNotebookAssignmentWriteSerializer,
    TrainingAdminReportsOverviewSerializer,
    TrainingAdminUserLookupSerializer,
    TrainingAdminUserAudienceGrantPatchSerializer,
    TrainingAdminUserAudienceGrantSerializer,
    TrainingAdminUserAudienceGrantWriteSerializer,
)
from apps.training.models import (
    TrainingAiConversation,
    TrainingAiMessage,
    TrainingAssetClass,
    TrainingAuditEvent,
    TrainingAudience,
    TrainingContentItem,
    TrainingContentSyncEvent,
    TrainingCourseRoleAssignment,
    TrainingGraderJob,
    TrainingLabLaunchToken,
    TrainingLabSubmission,
    TrainingLabSubmissionArtifact,
    TrainingNotebookLabHint,
    TrainingNotebookLabProfile,
    TrainingTopic,
    TrainingUserAudienceGrant,
)
from apps.training.permissions import (
    IsTrainingDirectusService,
    IsTrainingGraderService,
    IsTrainingInternalService,
)
from apps.training.serializers import (
    TrainingAiAskSerializer,
    TrainingAiConversationResponseSerializer,
    TrainingAiQuizAttemptSerializer,
    TrainingAiQuizGenerateSerializer,
    TrainingAiQuizSubmitSerializer,
    TrainingAssetClassSerializer,
    TrainingAudienceSerializer,
    TrainingContentDetailSerializer,
    TrainingGradebookEntrySerializer,
    TrainingGraderWebhookResultSerializer,
    TrainingLabSubmissionCreateSerializer,
    TrainingLabSubmissionSerializer,
    TrainingContentListSerializer,
    TrainingCourseRoleAssignmentSerializer,
    TrainingDirectusSyncResponseSerializer,
    TrainingDirectusSyncSerializer,
    TrainingTopicSerializer,
)
from apps.training.services.ai_analytics import build_training_ai_admin_analytics
from apps.training.services.access import (
    accessible_course_ids_for_user,
    active_audience_slugs_for_user,
    base_content_queryset,
    content_item_is_visible_to_user,
    demo_role_catalog,
    granted_audiences_for_user,
    primary_demo_role_for_user,
    visible_content_items_for_user,
)
from apps.training.services.audit import log_training_audit_event
from apps.training.services.ai_assistant import (
    TrainingAiError,
    ask_training_ai,
    build_training_ai_conversation_payload,
    build_training_ai_quiz_response_payload,
    generate_training_ai_quiz,
    list_training_ai_messages_for_user,
    submit_training_ai_quiz,
    training_ai_enabled,
)
from apps.training.services.ai_governance import (
    TrainingAiGovernanceError,
    build_training_ai_governance_overview,
    rebuild_training_knowledge_index_for_admin,
    unresolved_training_ai_conversations_queryset,
    update_training_ai_conversation_governance,
)
from apps.training.services.directus_sync import (
    TrainingDirectusSyncError,
    record_failed_training_directus_sync,
    sync_training_content_from_directus,
)
from apps.training.services.grading import (
    TrainingGradingError,
    apply_grader_webhook_result,
    create_lab_submission,
    grade_submission_now,
    preview_lab_submission,
    training_grader_runtime_enabled,
)
from apps.training.services.governance import build_training_governance_overview, enforce_single_primary_course_role
from apps.training.services.jupyter_auth import (
    TrainingJupyterAuthError,
    TrainingJupyterLoginTokenInvalidError,
    build_jupyterhub_login_redirect_url,
    build_jupyter_login_contract,
    build_resolved_jupyter_login_contract,
    issue_jupyter_login_token,
    resolve_jupyter_login_token,
)
from apps.training.services.jupyter_ai_proxy import (
    TrainingJupyterAiProxyError,
    build_internal_jupyter_ai_chat_completion,
    build_internal_jupyter_ai_models_payload,
    resolve_internal_jupyter_ai_proxy_request,
    validate_internal_jupyter_ai_proxy_token,
)
from apps.training.services.lab_launch import (
    TrainingLabLaunchError,
    TrainingLabLaunchTokenInvalidError,
    build_lab_launch_contract,
    build_resolved_lab_contract,
    issue_lab_launch_token,
    resolve_lab_launch_token,
    training_lab_runtime_enabled,
)
from apps.training.services.notebook_actions import (
    TrainingNotebookActionError,
    validate_internal_notebook_action_token,
)
from apps.training.services.notebook_assignments import build_student_lab_summary
from apps.training.services.notebook_storage import store_runtime_notebook_bytes
from apps.training.services.reports import (
    build_training_admin_reports_overview,
    training_admin_audit_events_queryset,
    training_admin_content_sync_events_queryset,
    training_admin_grader_jobs_queryset,
)

User = get_user_model()


class TrainingAiAskThrottle(UserRateThrottle):
    scope = "training_ai_question"


class TrainingAiQuizThrottle(UserRateThrottle):
    scope = "training_ai_quiz"


class TrainingAdminAiAnalyticsThrottle(UserRateThrottle):
    scope = "training_admin_ai_analytics"


class TrainingDirectusSyncThrottle(SimpleRateThrottle):
    scope = "training_directus_sync"

    def get_cache_key(self, request, view):
        ident = self.get_ident(request)
        if not ident:
            return None
        return self.cache_format % {"scope": self.scope, "ident": ident}


class TrainingInternalNotebookAskSerializer(serializers.Serializer):
    question = serializers.CharField(max_length=5000)


def _internal_notebook_action_context_or_error(*, request, slug: str):
    content_item = base_content_queryset(include_references=True).filter(slug=slug).first()
    if content_item is None or content_item.content_kind != TrainingContentItem.ContentKind.NOTEBOOK:
        raise Http404("Notebook content was not found.")

    raw_authorization = str(request.headers.get("Authorization") or "")
    if not raw_authorization.startswith("Bearer "):
        raise TrainingNotebookActionError("Notebook action token is missing.")

    token = raw_authorization.removeprefix("Bearer ").strip()
    resolved = validate_internal_notebook_action_token(content_slug=slug, token=token)
    user = get_user_model().objects.filter(id=resolved.user_id, is_active=True).first()
    if user is None:
        raise TrainingNotebookActionError("Notebook action user was not found.")
    if not content_item_is_visible_to_user(content_item, user):
        raise TrainingNotebookActionError("Notebook content is not accessible for this user.")
    return user, content_item


def _require_internal_notebook_upload(request):
    notebook_upload = request.FILES.get("notebook")
    if notebook_upload is None:
        raise ValidationError({"detail": "Notebook file is required."})
    return notebook_upload


def _hint_payload(hint: TrainingNotebookLabHint | None) -> dict[str, object] | None:
    if hint is None:
        return None
    return {
        "id": hint.id,
        "title": hint.title,
        "bodyMarkdown": hint.body_markdown,
    }


def _preferred_preview_hint(*, content_item, recommended_hint_ids: list[int]) -> TrainingNotebookLabHint | None:
    try:
        lab_profile = content_item.lab_profile
    except TrainingNotebookLabProfile.DoesNotExist:
        return None
    hints = list(lab_profile.hints.filter(is_active=True).order_by("sort_order", "id"))
    if not hints:
        return None
    by_id = {hint.id: hint for hint in hints}
    for hint_id in recommended_hint_ids:
        if hint_id in by_id:
            return by_id[hint_id]
    return hints[0]


class TrainingContentListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        queryset = base_content_queryset(include_references=False).filter(status=TrainingContentItem.Status.PUBLISHED)

        query = str(request.query_params.get("q") or "").strip()
        if query:
            queryset = queryset.filter(
                Q(name__icontains=query)
                | Q(description__icontains=query)
                | Q(search_keywords__icontains=query)
            )

        content_kind = str(request.query_params.get("kind") or "").strip()
        if content_kind:
            queryset = queryset.filter(content_kind=content_kind)

        course_slug = str(request.query_params.get("course") or "").strip()
        if course_slug:
            queryset = queryset.filter(course__slug=course_slug)

        asset_class_slug = str(request.query_params.get("asset_class") or "").strip()
        if asset_class_slug:
            queryset = queryset.filter(asset_classes__slug=asset_class_slug)

        topic_slug = str(request.query_params.get("topic") or "").strip()
        if topic_slug:
            queryset = queryset.filter(topics__slug=topic_slug)

        visible_items = visible_content_items_for_user(request.user, base_queryset=queryset.distinct())
        log_training_audit_event(
            event_type=TrainingAuditEvent.EventType.CONTENT_LIST_VIEWED,
            category=TrainingAuditEvent.Category.CONTENT,
            request=request,
            metadata={
                "query": query,
                "contentKind": content_kind,
                "courseSlug": course_slug,
                "assetClassSlug": asset_class_slug,
                "topicSlug": topic_slug,
                "resultCount": len(visible_items),
            },
        )
        serializer = TrainingContentListSerializer(visible_items, many=True)
        return Response({"results": serializer.data})


class TrainingContentDetailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, slug: str):
        item = base_content_queryset(include_references=True).filter(slug=slug).first()
        if item is None:
            raise Http404("Content item not found.")

        audience_slugs = active_audience_slugs_for_user(request.user)
        accessible_course_ids = accessible_course_ids_for_user(request.user)
        is_visible = content_item_is_visible_to_user(
            item,
            request.user,
            audience_slugs=audience_slugs,
            accessible_course_ids=accessible_course_ids,
        )
        if not is_visible:
            log_training_audit_event(
                event_type=TrainingAuditEvent.EventType.CONTENT_ACCESS_DENIED,
                category=TrainingAuditEvent.Category.CONTENT,
                outcome=TrainingAuditEvent.Outcome.DENIED,
                request=request,
                content_item=item,
                metadata={
                    "slug": slug,
                    "audienceSlugs": sorted(audience_slugs),
                    "accessibleCourseIds": sorted(accessible_course_ids),
                },
            )
            raise Http404("Content item not found.")

        log_training_audit_event(
            event_type=TrainingAuditEvent.EventType.CONTENT_DETAIL_VIEWED,
            category=TrainingAuditEvent.Category.CONTENT,
            request=request,
            content_item=item,
            metadata={"slug": slug},
        )
        serializer = TrainingContentDetailSerializer(item, context={"request": request, "user": request.user})
        return Response(serializer.data)


class TrainingMeEntitlementsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        now = timezone.now()
        direct_audiences = granted_audiences_for_user(request.user)
        effective_audience_slugs = active_audience_slugs_for_user(request.user)
        primary_demo_role = primary_demo_role_for_user(request.user)
        audience_grants = (
            TrainingUserAudienceGrant.objects.select_related("audience")
            .filter(user=request.user, audience__is_active=True)
            .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
        )
        course_roles = (
            TrainingCourseRoleAssignment.objects.select_related("course")
            .filter(user=request.user)
            .order_by("course__slug", "role")
        )
        response_payload = {
            "userId": request.user.id,
            "email": request.user.email,
            "audiences": TrainingAudienceSerializer(direct_audiences, many=True).data,
            "courseRoles": TrainingCourseRoleAssignmentSerializer(course_roles, many=True).data,
            "accessibleCourseIds": sorted(accessible_course_ids_for_user(request.user)),
            "audienceSlugs": sorted(effective_audience_slugs),
            "assignedAudienceSlugs": sorted({grant.audience.slug for grant in audience_grants}),
            "demoRoleCatalog": TrainingAudienceSerializer(demo_role_catalog(), many=True).data,
            "activeDemoRole": (
                TrainingAudienceSerializer(primary_demo_role).data if primary_demo_role is not None else None
            ),
        }
        log_training_audit_event(
            event_type=TrainingAuditEvent.EventType.ENTITLEMENTS_VIEWED,
            category=TrainingAuditEvent.Category.ENTITLEMENT,
            request=request,
            metadata={
                "audiencesCount": audience_grants.count(),
                "courseRolesCount": course_roles.count(),
            },
        )
        return Response(response_payload)


class TrainingAiConversationView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [TrainingAiAskThrottle]

    def get(self, request):
        if not training_ai_enabled():
            return Response({"detail": "AI assistant is disabled."}, status=503)

        slug = str(request.query_params.get("content") or "").strip()
        if not slug:
            return Response({"detail": "content query parameter is required."}, status=400)
        item = _visible_content_or_404(request, slug=slug, include_references=True)
        conversation, messages = list_training_ai_messages_for_user(user=request.user, content_item=item)
        payload = {"conversation": None, "messages": []}
        if conversation is not None:
            payload = build_training_ai_conversation_payload(conversation, messages)
        log_training_audit_event(
            event_type=TrainingAuditEvent.EventType.AI_CONVERSATION_VIEWED,
            category=TrainingAuditEvent.Category.AI,
            request=request,
            actor=request.user,
            target_user=request.user,
            content_item=item,
            metadata={"slug": slug, "messagesCount": len(payload.get("messages") or [])},
        )
        serializer = TrainingAiConversationResponseSerializer(payload)
        return Response(serializer.data)


class TrainingAiAskView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [TrainingAiAskThrottle]

    def post(self, request):
        if not training_ai_enabled():
            return Response({"detail": "AI assistant is disabled."}, status=503)

        serializer = TrainingAiAskSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = _visible_content_or_404(
            request,
            slug=serializer.validated_data["contentSlug"],
            include_references=True,
        )

        try:
            result = ask_training_ai(
                user=request.user,
                content_item=item,
                question=serializer.validated_data["question"],
                prompt_type=serializer.validated_data.get("promptType", ""),
                conversation_public_id=str(serializer.validated_data.get("conversationId") or ""),
            )
        except TrainingAiError as exc:
            log_training_audit_event(
                event_type=TrainingAuditEvent.EventType.AI_RESPONSE_FAILED,
                category=TrainingAuditEvent.Category.AI,
                outcome=TrainingAuditEvent.Outcome.FAILED,
                request=request,
                actor=request.user,
                target_user=request.user,
                content_item=item,
                metadata={
                    "slug": item.slug,
                    "promptType": serializer.validated_data.get("promptType", ""),
                    "questionLength": len(serializer.validated_data["question"]),
                    "reason": str(exc),
                },
            )
            return Response({"detail": str(exc)}, status=400)

        log_training_audit_event(
            event_type=TrainingAuditEvent.EventType.AI_QUESTION_ASKED,
            category=TrainingAuditEvent.Category.AI,
            request=request,
            actor=request.user,
            target_user=request.user,
            content_item=item,
            metadata={
                "slug": item.slug,
                "promptType": serializer.validated_data.get("promptType", ""),
                "questionLength": len(serializer.validated_data["question"]),
                "conversationId": str(result.conversation.public_id),
            },
        )
        log_training_audit_event(
            event_type=TrainingAuditEvent.EventType.AI_RESPONSE_GENERATED,
            category=TrainingAuditEvent.Category.AI,
            request=request,
            actor=request.user,
            target_user=request.user,
            content_item=item,
            metadata={
                "slug": item.slug,
                "assistantMessageId": result.assistant_message.id,
                "citationsCount": len(result.response_payload.get("citations") or []),
                "resolutionStatus": result.response_payload.get("resolutionStatus") or "",
            },
        )
        if result.response_payload.get("needsEscalation"):
            log_training_audit_event(
                event_type=TrainingAuditEvent.EventType.AI_ESCALATION_SUGGESTED,
                category=TrainingAuditEvent.Category.AI,
                request=request,
                actor=request.user,
                target_user=request.user,
                content_item=item,
                metadata={
                    "slug": item.slug,
                    "conversationId": str(result.conversation.public_id),
                    "escalation": result.response_payload.get("escalation") or {},
                },
            )

        return Response(
            {
                "conversationId": str(result.conversation.public_id),
                "assistantMessageId": result.assistant_message.id,
                "response": result.response_payload,
            },
            status=201,
        )


class TrainingAiQuizGenerateView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [TrainingAiQuizThrottle]

    def post(self, request):
        if not training_ai_enabled():
            return Response({"detail": "AI assistant is disabled."}, status=503)

        serializer = TrainingAiQuizGenerateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = _visible_content_or_404(
            request,
            slug=serializer.validated_data["contentSlug"],
            include_references=True,
        )
        try:
            quiz_attempt = generate_training_ai_quiz(
                user=request.user,
                content_item=item,
                conversation_public_id=str(serializer.validated_data.get("conversationId") or ""),
                question_count=serializer.validated_data.get("questionCount", 4),
            )
        except TrainingAiError as exc:
            return Response({"detail": str(exc)}, status=400)
        log_training_audit_event(
            event_type=TrainingAuditEvent.EventType.AI_QUIZ_GENERATED,
            category=TrainingAuditEvent.Category.AI,
            request=request,
            actor=request.user,
            target_user=request.user,
            content_item=item,
            metadata={
                "slug": item.slug,
                "quizId": str(quiz_attempt.public_id),
                "questionCount": len((quiz_attempt.quiz_payload or {}).get("questions") or []),
            },
        )
        return Response(TrainingAiQuizAttemptSerializer(quiz_attempt).data, status=201)


class TrainingAiQuizSubmitView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [TrainingAiQuizThrottle]

    def post(self, request, quiz_public_id: str):
        serializer = TrainingAiQuizSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            result = submit_training_ai_quiz(
                user=request.user,
                quiz_public_id=quiz_public_id,
                answers=serializer.validated_data["answers"],
            )
        except TrainingAiError as exc:
            log_training_audit_event(
                event_type=TrainingAuditEvent.EventType.AI_QUIZ_SUBMIT_FAILED,
                category=TrainingAuditEvent.Category.AI,
                outcome=TrainingAuditEvent.Outcome.FAILED,
                request=request,
                actor=request.user,
                target_user=request.user,
                metadata={"quizId": quiz_public_id, "reason": str(exc)},
            )
            return Response({"detail": str(exc)}, status=400)

        log_training_audit_event(
            event_type=TrainingAuditEvent.EventType.AI_QUIZ_SUBMITTED,
            category=TrainingAuditEvent.Category.AI,
            request=request,
            actor=request.user,
            target_user=request.user,
            content_item=result.quiz_attempt.content_item,
            metadata={
                "quizId": str(result.quiz_attempt.public_id),
                "score": result.quiz_attempt.score,
                "maxScore": result.quiz_attempt.max_score,
            },
        )
        return Response(result.response_payload)


class TrainingAdminOverviewView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    def get(self, request):
        course_id = _optional_int_query_param(request, "course_id")
        return Response(build_training_governance_overview(course_id=course_id))


class TrainingAdminUserLookupView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    def get(self, request):
        queryset = User.objects.all().order_by("email", "id")
        query = str(request.query_params.get("q") or "").strip()
        if query:
            queryset = queryset.filter(
                Q(email__icontains=query)
                | Q(username__icontains=query)
                | Q(first_name__icontains=query)
                | Q(last_name__icontains=query)
            )
        limit = _bounded_positive_int_query_param(request, "limit", default=20, minimum=1, maximum=100)
        serializer = TrainingAdminUserLookupSerializer(queryset[:limit], many=True)
        return Response({"results": serializer.data})


class TrainingAdminAudienceListView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    def get(self, request):
        queryset = TrainingAudience.objects.all().order_by("name", "id")
        query = str(request.query_params.get("q") or "").strip()
        if query:
            queryset = queryset.filter(
                Q(name__icontains=query)
                | Q(slug__icontains=query)
                | Q(description__icontains=query)
            )
        serializer = TrainingAdminAudienceSerializer(queryset, many=True)
        return Response({"results": serializer.data})

    def post(self, request):
        serializer = TrainingAdminAudienceWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        audience = serializer.save()
        log_training_audit_event(
            event_type=TrainingAuditEvent.EventType.ADMIN_AUDIENCE_CREATED,
            category=TrainingAuditEvent.Category.ADMIN,
            request=request,
            actor=request.user,
            metadata={
                "audienceId": audience.id,
                "audienceSlug": audience.slug,
                "isInternal": audience.is_internal,
                "isActive": audience.is_active,
            },
        )
        return Response(TrainingAdminAudienceSerializer(audience).data, status=201)


class TrainingAdminAudienceDetailView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    def get(self, request, audience_id: int):
        audience = _admin_audience_or_404(audience_id)
        return Response(TrainingAdminAudienceSerializer(audience).data)

    def patch(self, request, audience_id: int):
        audience = _admin_audience_or_404(audience_id)
        serializer = TrainingAdminAudienceWriteSerializer(audience, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        audience = serializer.save()
        log_training_audit_event(
            event_type=TrainingAuditEvent.EventType.ADMIN_AUDIENCE_UPDATED,
            category=TrainingAuditEvent.Category.ADMIN,
            request=request,
            actor=request.user,
            metadata={
                "audienceId": audience.id,
                "audienceSlug": audience.slug,
                "isInternal": audience.is_internal,
                "isActive": audience.is_active,
            },
        )
        return Response(TrainingAdminAudienceSerializer(audience).data)

    def delete(self, request, audience_id: int):
        audience = _admin_audience_or_404(audience_id)
        if audience.user_grants.exists() or audience.content_policies.exists():
            return Response(
                {"detail": "Audience cannot be deleted while grants or content policies exist."},
                status=400,
            )
        deleted_audience_payload = {
            "audienceId": audience.id,
            "audienceSlug": audience.slug,
            "isInternal": audience.is_internal,
        }
        audience.delete()
        log_training_audit_event(
            event_type=TrainingAuditEvent.EventType.ADMIN_AUDIENCE_DELETED,
            category=TrainingAuditEvent.Category.ADMIN,
            request=request,
            actor=request.user,
            metadata=deleted_audience_payload,
        )
        return Response(status=204)


class TrainingAdminAssetClassListView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    def get(self, request):
        queryset = TrainingAssetClass.objects.filter(is_active=True).order_by("name", "id")
        return Response({"results": TrainingAssetClassSerializer(queryset, many=True).data})


class TrainingAdminTopicListView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    def get(self, request):
        queryset = TrainingTopic.objects.filter(is_active=True).select_related("parent").order_by("name", "id")
        return Response({"results": TrainingTopicSerializer(queryset, many=True).data})


class TrainingAdminCourseRoleAssignmentListView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    def get(self, request):
        queryset = TrainingCourseRoleAssignment.objects.select_related("course", "user").order_by(
            "course__slug",
            "role",
            "user__email",
        )
        course_id = _optional_int_query_param(request, "course_id")
        if course_id is not None:
            queryset = queryset.filter(course_id=course_id)
        user_id = _optional_int_query_param(request, "user_id")
        if user_id is not None:
            queryset = queryset.filter(user_id=user_id)
        role = str(request.query_params.get("role") or "").strip()
        if role:
            queryset = queryset.filter(role=role)
        query = str(request.query_params.get("q") or "").strip()
        if query:
            queryset = queryset.filter(
                Q(user__email__icontains=query)
                | Q(course__slug__icontains=query)
                | Q(course__title_de__icontains=query)
                | Q(course__title_en__icontains=query)
            )
        serializer = TrainingAdminCourseRoleAssignmentSerializer(queryset, many=True)
        return Response({"results": serializer.data})

    def post(self, request):
        serializer = TrainingAdminCourseRoleAssignmentWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            assignment = serializer.save()
        except IntegrityError:
            return Response(
                {"detail": "This user already has the selected role for the course."},
                status=400,
            )
        enforce_single_primary_course_role(assignment=assignment)
        assignment.refresh_from_db()
        log_training_audit_event(
            event_type=TrainingAuditEvent.EventType.ADMIN_COURSE_ROLE_CREATED,
            category=TrainingAuditEvent.Category.ADMIN,
            request=request,
            actor=request.user,
            target_user=assignment.user,
            course=assignment.course,
            metadata={
                "assignmentId": assignment.id,
                "role": assignment.role,
                "isPrimary": assignment.is_primary,
                "responseSlaHours": assignment.response_sla_hours,
            },
        )
        return Response(TrainingAdminCourseRoleAssignmentSerializer(assignment).data, status=201)


class TrainingAdminCourseRoleAssignmentDetailView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    def patch(self, request, assignment_id: int):
        assignment = _admin_role_assignment_or_404(assignment_id)
        serializer = TrainingAdminCourseRoleAssignmentPatchSerializer(assignment, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            assignment = serializer.save()
        except IntegrityError:
            return Response(
                {"detail": "This user already has the selected role for the course."},
                status=400,
            )
        enforce_single_primary_course_role(assignment=assignment)
        assignment.refresh_from_db()
        log_training_audit_event(
            event_type=TrainingAuditEvent.EventType.ADMIN_COURSE_ROLE_UPDATED,
            category=TrainingAuditEvent.Category.ADMIN,
            request=request,
            actor=request.user,
            target_user=assignment.user,
            course=assignment.course,
            metadata={
                "assignmentId": assignment.id,
                "role": assignment.role,
                "isPrimary": assignment.is_primary,
                "responseSlaHours": assignment.response_sla_hours,
            },
        )
        return Response(TrainingAdminCourseRoleAssignmentSerializer(assignment).data)

    def delete(self, request, assignment_id: int):
        assignment = _admin_role_assignment_or_404(assignment_id)
        deleted_assignment_payload = {
            "assignmentId": assignment.id,
            "role": assignment.role,
            "isPrimary": assignment.is_primary,
            "responseSlaHours": assignment.response_sla_hours,
        }
        target_user = assignment.user
        course = assignment.course
        assignment.delete()
        log_training_audit_event(
            event_type=TrainingAuditEvent.EventType.ADMIN_COURSE_ROLE_DELETED,
            category=TrainingAuditEvent.Category.ADMIN,
            request=request,
            actor=request.user,
            target_user=target_user,
            course=course,
            metadata=deleted_assignment_payload,
        )
        return Response(status=204)


class TrainingAdminUserAudienceGrantListView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    def get(self, request):
        queryset = TrainingUserAudienceGrant.objects.select_related("user", "audience").order_by(
            "user__email",
            "audience__name",
        )
        user_id = _optional_int_query_param(request, "user_id")
        if user_id is not None:
            queryset = queryset.filter(user_id=user_id)
        audience_id = _optional_int_query_param(request, "audience_id")
        if audience_id is not None:
            queryset = queryset.filter(audience_id=audience_id)
        active_only = _bool_query_param(request, "active_only", default=False)
        if active_only:
            queryset = queryset.filter(Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now()))
        query = str(request.query_params.get("q") or "").strip()
        if query:
            queryset = queryset.filter(
                Q(user__email__icontains=query)
                | Q(audience__slug__icontains=query)
                | Q(audience__name__icontains=query)
            )
        serializer = TrainingAdminUserAudienceGrantSerializer(queryset, many=True)
        return Response({"results": serializer.data})

    def post(self, request):
        serializer = TrainingAdminUserAudienceGrantWriteSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        try:
            grant = serializer.save()
        except IntegrityError:
            return Response(
                {"detail": "This user already has the selected audience grant."},
                status=400,
            )
        log_training_audit_event(
            event_type=TrainingAuditEvent.EventType.ADMIN_AUDIENCE_GRANT_CREATED,
            category=TrainingAuditEvent.Category.ADMIN,
            request=request,
            actor=request.user,
            target_user=grant.user,
            metadata={
                "grantId": grant.id,
                "audienceSlug": grant.audience.slug,
                "expiresAt": grant.expires_at.isoformat() if grant.expires_at else "",
            },
        )
        return Response(TrainingAdminUserAudienceGrantSerializer(grant).data, status=201)


class TrainingAdminUserAudienceGrantDetailView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    def patch(self, request, grant_id: int):
        grant = _admin_grant_or_404(grant_id)
        serializer = TrainingAdminUserAudienceGrantPatchSerializer(grant, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        grant = serializer.save()
        log_training_audit_event(
            event_type=TrainingAuditEvent.EventType.ADMIN_AUDIENCE_GRANT_UPDATED,
            category=TrainingAuditEvent.Category.ADMIN,
            request=request,
            actor=request.user,
            target_user=grant.user,
            metadata={
                "grantId": grant.id,
                "audienceSlug": grant.audience.slug,
                "expiresAt": grant.expires_at.isoformat() if grant.expires_at else "",
            },
        )
        return Response(TrainingAdminUserAudienceGrantSerializer(grant).data)

    def delete(self, request, grant_id: int):
        grant = _admin_grant_or_404(grant_id)
        deleted_grant_payload = {
            "grantId": grant.id,
            "audienceSlug": grant.audience.slug,
            "expiresAt": grant.expires_at.isoformat() if grant.expires_at else "",
        }
        target_user = grant.user
        grant.delete()
        log_training_audit_event(
            event_type=TrainingAuditEvent.EventType.ADMIN_AUDIENCE_GRANT_DELETED,
            category=TrainingAuditEvent.Category.ADMIN,
            request=request,
            actor=request.user,
            target_user=target_user,
            metadata=deleted_grant_payload,
        )
        return Response(status=204)


class TrainingAdminContentGovernanceListView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    def get(self, request):
        queryset = (
            TrainingContentItem.objects.select_related("course", "owner", "lab_profile")
            .prefetch_related("asset_classes", "topics", "audience_policies")
            .order_by("name", "id")
        )
        course_id = _optional_int_query_param(request, "course_id")
        if course_id is not None:
            queryset = queryset.filter(course_id=course_id)
        status_value = str(request.query_params.get("status") or "").strip()
        if status_value:
            queryset = queryset.filter(status=status_value)
        kind = str(request.query_params.get("kind") or "").strip()
        if kind:
            queryset = queryset.filter(content_kind=kind)
        query = str(request.query_params.get("q") or "").strip()
        if query:
            queryset = queryset.filter(
                Q(name__icontains=query)
                | Q(slug__icontains=query)
                | Q(description__icontains=query)
            )
        missing_only = _bool_query_param(request, "missing_only", default=False)
        serializer = TrainingAdminContentGovernanceSerializer(queryset, many=True)
        results = serializer.data
        if missing_only:
            results = [item for item in results if item["governanceFlags"]]
        return Response({"results": results})


class TrainingAdminNotebookAssignmentListView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    def get(self, request):
        queryset = (
            TrainingContentItem.objects.select_related("course", "owner", "lab_profile")
            .prefetch_related("asset_classes", "topics", "audience_policies", "lab_profile__hints", "online_course_library_items")
            .filter(content_kind=TrainingContentItem.ContentKind.NOTEBOOK)
            .order_by("name", "id")
        )
        course_id = _optional_int_query_param(request, "course_id")
        if course_id is not None:
            queryset = queryset.filter(course_id=course_id)
        status_value = str(request.query_params.get("status") or "").strip()
        if status_value:
            queryset = queryset.filter(status=status_value)
        query = str(request.query_params.get("q") or "").strip()
        if query:
            queryset = queryset.filter(
                Q(name__icontains=query)
                | Q(slug__icontains=query)
                | Q(description__icontains=query)
                | Q(search_keywords__icontains=query)
            )
        serializer = TrainingAdminNotebookAssignmentSerializer(queryset, many=True)
        return Response({"results": serializer.data})

    def post(self, request):
        serializer = TrainingAdminNotebookAssignmentWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        content_item = serializer.save()
        log_training_audit_event(
            event_type=TrainingAuditEvent.EventType.ADMIN_AI_OPERATIONS_VIEWED,
            category=TrainingAuditEvent.Category.ADMIN,
            request=request,
            actor=request.user,
            content_item=content_item,
            metadata={"action": "notebook_assignment_created", "contentSlug": content_item.slug},
        )
        return Response(TrainingAdminNotebookAssignmentSerializer(content_item).data, status=201)


class TrainingAdminNotebookAssignmentUploadView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        notebook = request.FILES.get("notebook")
        if notebook is None:
            return Response({"detail": "Notebook file is required."}, status=400)
        content_slug = str(request.data.get("content_slug") or request.data.get("slug") or "").strip()
        if not content_slug:
            return Response({"detail": "content_slug is required."}, status=400)
        stored_notebook = store_runtime_notebook_bytes(
            content_slug=content_slug,
            filename=str(getattr(notebook, "name", "") or f"{content_slug}.ipynb"),
            notebook_bytes=notebook.read(),
        )
        log_training_audit_event(
            event_type=TrainingAuditEvent.EventType.ADMIN_AI_OPERATIONS_VIEWED,
            category=TrainingAuditEvent.Category.ADMIN,
            request=request,
            actor=request.user,
            metadata={
                "action": "notebook_assignment_uploaded",
                "contentSlug": content_slug,
                "notebookPath": stored_notebook.notebook_path,
            },
        )
        return Response(
            {
                "contentSlug": content_slug,
                "notebookPath": stored_notebook.notebook_path,
                "storagePath": stored_notebook.storage_path,
                "checksum": stored_notebook.checksum,
                "sizeBytes": stored_notebook.size_bytes,
            },
            status=201,
        )


class TrainingAdminNotebookAssignmentDetailView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    def get(self, request, content_id: int):
        content_item = _admin_notebook_assignment_or_404(content_id)
        return Response(TrainingAdminNotebookAssignmentSerializer(content_item).data)

    def patch(self, request, content_id: int):
        content_item = _admin_notebook_assignment_or_404(content_id)
        serializer = TrainingAdminNotebookAssignmentWriteSerializer(content_item, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        content_item = serializer.save()
        log_training_audit_event(
            event_type=TrainingAuditEvent.EventType.ADMIN_AI_OPERATIONS_VIEWED,
            category=TrainingAuditEvent.Category.ADMIN,
            request=request,
            actor=request.user,
            content_item=content_item,
            metadata={"action": "notebook_assignment_updated", "contentSlug": content_item.slug},
        )
        return Response(TrainingAdminNotebookAssignmentSerializer(content_item).data)

    def delete(self, request, content_id: int):
        content_item = _admin_notebook_assignment_or_404(content_id)
        slug = content_item.slug
        content_item.delete()
        log_training_audit_event(
            event_type=TrainingAuditEvent.EventType.ADMIN_AI_OPERATIONS_VIEWED,
            category=TrainingAuditEvent.Category.ADMIN,
            request=request,
            actor=request.user,
            metadata={"action": "notebook_assignment_deleted", "contentSlug": slug},
        )
        return Response(status=204)


class TrainingAdminAiOverviewView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    def get(self, request):
        course_id = _optional_int_query_param(request, "course_id")
        overview = build_training_ai_governance_overview(course_id=course_id)
        log_training_audit_event(
            event_type=TrainingAuditEvent.EventType.ADMIN_AI_OVERVIEW_VIEWED,
            category=TrainingAuditEvent.Category.ADMIN,
            request=request,
            actor=request.user,
            metadata={"courseId": course_id},
        )
        return Response(TrainingAdminAiOverviewSerializer(overview).data)


class TrainingAdminAiAnalyticsView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]
    throttle_classes = [TrainingAdminAiAnalyticsThrottle]

    def permission_denied(self, request, message=None, code=None):
        log_training_audit_event(
            event_type=TrainingAuditEvent.EventType.ADMIN_AI_ANALYTICS_VIEWED,
            category=TrainingAuditEvent.Category.ADMIN,
            outcome=TrainingAuditEvent.Outcome.DENIED,
            request=request,
            actor=request.user if getattr(request.user, "is_authenticated", False) else None,
            metadata={
                "courseId": request.query_params.get("course_id"),
                "windowDays": request.query_params.get("window_days"),
                "denied": True,
            },
        )
        super().permission_denied(request, message=message, code=code)

    def get(self, request):
        course_id = _optional_int_query_param(request, "course_id")
        window_days = _bounded_positive_int_query_param(
            request,
            "window_days",
            default=7,
            minimum=1,
            maximum=90,
        )
        analytics = build_training_ai_admin_analytics(course_id=course_id, window_days=window_days)
        log_training_audit_event(
            event_type=TrainingAuditEvent.EventType.ADMIN_AI_ANALYTICS_VIEWED,
            category=TrainingAuditEvent.Category.ADMIN,
            request=request,
            actor=request.user,
            metadata={"courseId": course_id, "windowDays": window_days},
        )
        return Response(TrainingAdminAiAnalyticsSerializer(analytics).data)


class TrainingAdminReportsOverviewView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    def get(self, request):
        course_id = _optional_int_query_param(request, "course_id")
        overview = build_training_admin_reports_overview(course_id=course_id)
        return Response(TrainingAdminReportsOverviewSerializer(overview).data)


class TrainingAdminAuditEventListView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    def get(self, request):
        course_id = _optional_int_query_param(request, "course_id")
        outcome = str(request.query_params.get("outcome") or "").strip()
        category = str(request.query_params.get("category") or "").strip()
        query = str(request.query_params.get("q") or "").strip()
        limit = _bounded_positive_int_query_param(request, "limit", default=25, minimum=1, maximum=200)
        queryset = training_admin_audit_events_queryset(
            course_id=course_id,
            outcome=outcome,
            category=category,
            query=query,
        )[:limit]
        serializer = TrainingAdminAuditEventSerializer(queryset, many=True)
        return Response({"results": serializer.data})


class TrainingAdminContentSyncEventListView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    def get(self, request):
        course_id = _optional_int_query_param(request, "course_id")
        status_value = str(request.query_params.get("status") or "").strip()
        query = str(request.query_params.get("q") or "").strip()
        limit = _bounded_positive_int_query_param(request, "limit", default=25, minimum=1, maximum=200)
        queryset = training_admin_content_sync_events_queryset(
            course_id=course_id,
            status_value=status_value,
            query=query,
        )[:limit]
        serializer = TrainingAdminContentSyncEventSerializer(queryset, many=True)
        return Response({"results": serializer.data})


class TrainingAdminGraderJobListView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    def get(self, request):
        course_id = _optional_int_query_param(request, "course_id")
        status_value = str(request.query_params.get("status") or "").strip()
        query = str(request.query_params.get("q") or "").strip()
        limit = _bounded_positive_int_query_param(request, "limit", default=25, minimum=1, maximum=200)
        queryset = training_admin_grader_jobs_queryset(
            course_id=course_id,
            status_value=status_value,
            query=query,
        )[:limit]
        serializer = TrainingAdminGraderJobSerializer(queryset, many=True)
        return Response({"results": serializer.data})


class TrainingAdminAiConversationListView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    def get(self, request):
        course_id = _optional_int_query_param(request, "course_id")
        include_resolved = _bool_query_param(request, "include_resolved", default=False)
        limit = _bounded_positive_int_query_param(request, "limit", default=50, minimum=1, maximum=200)
        queryset = unresolved_training_ai_conversations_queryset(
            course_id=course_id,
            include_resolved=include_resolved,
        )[:limit]
        results = list(queryset)
        log_training_audit_event(
            event_type=TrainingAuditEvent.EventType.ADMIN_AI_QUEUE_VIEWED,
            category=TrainingAuditEvent.Category.ADMIN,
            request=request,
            actor=request.user,
            metadata={
                "courseId": course_id,
                "includeResolved": include_resolved,
                "limit": limit,
                "resultCount": len(results),
            },
        )
        return Response({"results": TrainingAdminAiConversationSerializer(results, many=True).data})


class TrainingAdminAiConversationDetailView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    def patch(self, request, conversation_public_id):
        conversation = _admin_ai_conversation_or_404(conversation_public_id)
        serializer = TrainingAdminAiConversationPatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        previous_status = conversation.governance_status
        previous_assignee_id = conversation.assigned_to_id
        try:
            updated = update_training_ai_conversation_governance(
                conversation=conversation,
                actor=request.user,
                governance_status=serializer.validated_data.get("governance_status"),
                assigned_to_id=serializer.validated_data.get("assigned_to_id"),
                assigned_to_provided="assigned_to_id" in serializer.validated_data,
                resolution_note=serializer.validated_data.get("resolution_note"),
            )
        except TrainingAiGovernanceError as exc:
            return Response({"detail": str(exc)}, status=400)

        serialized_instance = (
            unresolved_training_ai_conversations_queryset(include_resolved=True)
            .filter(pk=updated.pk)
            .first()
        ) or updated
        log_training_audit_event(
            event_type=TrainingAuditEvent.EventType.ADMIN_AI_CONVERSATION_UPDATED,
            category=TrainingAuditEvent.Category.ADMIN,
            request=request,
            actor=request.user,
            target_user=updated.user,
            content_item=updated.content_item,
            metadata={
                "conversationPublicId": str(updated.public_id),
                "previousStatus": previous_status,
                "newStatus": updated.governance_status,
                "previousAssigneeId": previous_assignee_id,
                "newAssigneeId": updated.assigned_to_id,
                "resolutionNoteLength": len(updated.resolution_note or ""),
            },
        )
        return Response(TrainingAdminAiConversationSerializer(serialized_instance).data)


class TrainingAdminAiRebuildIndexView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    def post(self, request):
        serializer = TrainingAdminAiRebuildIndexSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            rebuild_result = rebuild_training_knowledge_index_for_admin(
                course_id=serializer.validated_data.get("course_id"),
                content_slug=serializer.validated_data.get("content_slug", ""),
            )
        except TrainingAiGovernanceError as exc:
            log_training_audit_event(
                event_type=TrainingAuditEvent.EventType.ADMIN_AI_INDEX_REBUILT,
                category=TrainingAuditEvent.Category.ADMIN,
                outcome=TrainingAuditEvent.Outcome.FAILED,
                request=request,
                actor=request.user,
                metadata={
                    "courseId": serializer.validated_data.get("course_id"),
                    "contentSlug": serializer.validated_data.get("content_slug", ""),
                    "reason": str(exc),
                },
            )
            return Response({"detail": str(exc)}, status=400)

        response_payload = {
            "rebuiltContentItems": rebuild_result.rebuilt_content_items,
            "rebuiltChunks": rebuild_result.rebuilt_chunks,
            "filters": rebuild_result.filters,
        }
        log_training_audit_event(
            event_type=TrainingAuditEvent.EventType.ADMIN_AI_INDEX_REBUILT,
            category=TrainingAuditEvent.Category.ADMIN,
            request=request,
            actor=request.user,
            metadata=response_payload,
        )
        return Response(response_payload)


class TrainingGradebookView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        entries = (
            request.user.training_gradebook_entries.select_related(
                "content_item__course",
                "latest_submission__content_item__course",
                "best_submission",
            )
            .prefetch_related(
                "content_item__asset_classes",
                "content_item__topics",
                "latest_submission__artifacts",
            )
            .order_by("content_item__name", "id")
        )
        course_slug = str(request.query_params.get("course") or "").strip()
        if course_slug:
            entries = entries.filter(content_item__course__slug=course_slug)
        entries_list = list(entries)
        log_training_audit_event(
            event_type=TrainingAuditEvent.EventType.GRADEBOOK_VIEWED,
            category=TrainingAuditEvent.Category.GRADING,
            request=request,
            metadata={
                "courseSlug": course_slug,
                "resultCount": len(entries_list),
            },
        )
        serializer = TrainingGradebookEntrySerializer(entries_list, many=True, context={"request": request})
        return Response({"results": serializer.data})


class TrainingInternalDirectusContentSyncView(APIView):
    authentication_classes = []
    permission_classes = [IsTrainingDirectusService]
    throttle_classes = [TrainingDirectusSyncThrottle]

    def permission_denied(self, request, message=None, code=None):
        log_training_audit_event(
            event_type=TrainingAuditEvent.EventType.DIRECTUS_SYNC_FAILED,
            category=TrainingAuditEvent.Category.CONTENT,
            outcome=TrainingAuditEvent.Outcome.DENIED,
            request=request,
            metadata={
                "source": "directus",
                "operation": request.data.get("operation", "upsert") if isinstance(request.data, dict) else "upsert",
                "slug": request.data.get("slug", "") if isinstance(request.data, dict) else "",
                "denied": True,
            },
        )
        super().permission_denied(request, message=message, code=code)

    def post(self, request):
        serializer = TrainingDirectusSyncSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            sync_result = sync_training_content_from_directus(payload=serializer.validated_data)
        except TrainingDirectusSyncError as exc:
            record_failed_training_directus_sync(serializer.validated_data, reason=str(exc))
            log_training_audit_event(
                event_type=TrainingAuditEvent.EventType.DIRECTUS_SYNC_FAILED,
                category=TrainingAuditEvent.Category.CONTENT,
                outcome=TrainingAuditEvent.Outcome.FAILED,
                request=request,
                metadata={
                    "source": "directus",
                    "slug": serializer.validated_data.get("slug"),
                    "externalId": serializer.validated_data.get("externalId", ""),
                    "operation": serializer.validated_data.get("operation", "upsert"),
                    "reason": str(exc),
                },
            )
            return Response({"detail": str(exc)}, status=400)

        content_item = TrainingContentItem.objects.filter(id=sync_result.content_item_id).first() if sync_result.content_item_id else None
        response_payload = {
            "action": sync_result.action,
            "contentId": sync_result.content_item_id,
            "slug": sync_result.slug,
            "status": sync_result.status,
            "indexAction": sync_result.index_action,
            "indexedChunks": sync_result.indexed_chunks,
            "warnings": sync_result.warnings,
        }
        log_training_audit_event(
            event_type=TrainingAuditEvent.EventType.DIRECTUS_SYNC_APPLIED,
            category=TrainingAuditEvent.Category.CONTENT,
            request=request,
            content_item=content_item,
            metadata={
                "source": "directus",
                "action": sync_result.action,
                "slug": sync_result.slug,
                "status": sync_result.status,
                "indexAction": sync_result.index_action,
                "indexedChunks": sync_result.indexed_chunks,
                "warningsCount": len(sync_result.warnings),
            },
        )
        return Response(TrainingDirectusSyncResponseSerializer(response_payload).data)


class TrainingLabSubmissionListCreateView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get(self, request, slug: str):
        item = base_content_queryset(include_references=False).filter(slug=slug).first()
        if item is None or not content_item_is_visible_to_user(item, request.user):
            raise Http404("Content item not found.")

        queryset = (
            TrainingLabSubmission.objects.filter(user=request.user, content_item=item)
            .select_related("content_item__course", "grader_job")
            .prefetch_related("artifacts")
            .order_by("-attempt_number", "-created_at")
        )
        serializer = TrainingLabSubmissionSerializer(queryset, many=True, context={"request": request})
        return Response({"results": serializer.data})

    def post(self, request, slug: str):
        item = base_content_queryset(include_references=False).filter(slug=slug).first()
        if item is None:
            log_training_audit_event(
                event_type=TrainingAuditEvent.EventType.LAB_SUBMISSION_NOT_FOUND,
                category=TrainingAuditEvent.Category.LAB,
                outcome=TrainingAuditEvent.Outcome.FAILED,
                request=request,
                metadata={"slug": slug},
            )
            raise Http404("Content item not found.")
        if not content_item_is_visible_to_user(item, request.user):
            log_training_audit_event(
                event_type=TrainingAuditEvent.EventType.LAB_SUBMISSION_DENIED,
                category=TrainingAuditEvent.Category.LAB,
                outcome=TrainingAuditEvent.Outcome.DENIED,
                request=request,
                actor=request.user,
                target_user=request.user,
                content_item=item,
                metadata={"slug": slug},
            )
            raise Http404("Content item not found.")

        serializer = TrainingLabSubmissionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            launch_token = _latest_consumed_launch_token_for_user(user=request.user, content_item=item)
            submission = create_lab_submission(
                user=request.user,
                content_item=item,
                notebook_upload=serializer.validated_data.get("notebook"),
                response_text=serializer.validated_data.get("answerText", ""),
                client_checksum=serializer.validated_data.get("client_checksum", ""),
                launch_token=launch_token,
            )
            if serializer.validated_data.get("answerText"):
                submission = grade_submission_now(submission=submission, worker_name="training-inline-answer")
        except TrainingGradingError as exc:
            log_training_audit_event(
                event_type=TrainingAuditEvent.EventType.SUBMISSION_REJECTED,
                category=TrainingAuditEvent.Category.GRADING,
                outcome=TrainingAuditEvent.Outcome.FAILED,
                request=request,
                actor=request.user,
                target_user=request.user,
                content_item=item,
                metadata={
                    "slug": slug,
                    "error": str(exc),
                },
            )
            return Response({"detail": str(exc)}, status=400 if training_grader_runtime_enabled() else 503)

        log_training_audit_event(
            event_type=TrainingAuditEvent.EventType.SUBMISSION_CREATED,
            category=TrainingAuditEvent.Category.GRADING,
            request=request,
            actor=request.user,
            target_user=request.user,
            content_item=item,
            submission=submission,
            launch_token=launch_token,
            metadata={
                "slug": slug,
                "attemptNumber": submission.attempt_number,
                "graderBackend": submission.grader_backend,
                "submissionMode": submission.submission_mode,
                "hasLaunchToken": bool(launch_token),
                "notebookArtifactFilename": submission.notebook_artifact_filename,
                "responseLength": len(str(submission.response_text or "").strip()),
            },
        )
        return Response(TrainingLabSubmissionSerializer(submission, context={"request": request}).data, status=201)


class TrainingLabSubmissionArtifactDownloadView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, slug: str, submission_public_id: str, artifact_kind: str):
        item = base_content_queryset(include_references=False).filter(slug=slug).first()
        if item is None or not content_item_is_visible_to_user(item, request.user):
            raise Http404("Content item not found.")

        submission = (
            TrainingLabSubmission.objects.filter(
                public_id=submission_public_id,
                user=request.user,
                content_item=item,
            )
            .prefetch_related("artifacts")
            .first()
        )
        if submission is None:
            raise Http404("Submission not found.")

        artifact = submission.artifacts.filter(artifact_kind=artifact_kind).order_by("id").first()
        if artifact is None:
            raise Http404("Artifact not found.")

        from pathlib import Path
        from django.conf import settings

        media_root = Path(settings.MEDIA_ROOT).resolve()
        resolved_path = (media_root / artifact.storage_path).resolve()
        try:
            resolved_path.relative_to(media_root)
        except ValueError as exc:
            raise Http404("Artifact not found.") from exc
        if not resolved_path.exists():
            raise Http404("Artifact not found.")

        if artifact_kind == TrainingLabSubmissionArtifact.ArtifactKind.FEEDBACK_HTML:
            log_training_audit_event(
                event_type=TrainingAuditEvent.EventType.CONTENT_DETAIL_VIEWED,
                category=TrainingAuditEvent.Category.GRADING,
                request=request,
                actor=request.user,
                target_user=request.user,
                content_item=item,
                submission=submission,
                metadata={"artifactKind": artifact_kind, "contentSlug": slug},
            )
        response = FileResponse(
            resolved_path.open("rb"),
            as_attachment=False,
            filename=resolved_path.name,
            content_type=artifact.media_type or "application/octet-stream",
        )
        if artifact_kind == TrainingLabSubmissionArtifact.ArtifactKind.FEEDBACK_HTML:
            response["Content-Security-Policy"] = (
                "sandbox; default-src 'none'; img-src data:; style-src 'unsafe-inline'; "
                "base-uri 'none'; form-action 'none'"
            )
            response["X-Content-Type-Options"] = "nosniff"
        return response


class TrainingLabHintViewedView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, slug: str, hint_id: int):
        item = _visible_content_or_404(request, slug=slug, include_references=False)
        try:
            lab_profile = item.lab_profile
        except TrainingNotebookLabProfile.DoesNotExist as exc:
            raise Http404("Lab profile not found.") from exc
        hint = lab_profile.hints.filter(id=hint_id, is_active=True).first()
        if hint is None:
            raise Http404("Hint not found.")
        log_training_audit_event(
            event_type=TrainingAuditEvent.EventType.LAB_HINT_VIEWED,
            category=TrainingAuditEvent.Category.LAB,
            request=request,
            actor=request.user,
            target_user=request.user,
            content_item=item,
            metadata={"slug": slug, "hintId": hint.id},
        )
        return Response({"ok": True, "hintId": hint.id})


class TrainingLabLaunchView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, slug: str):
        item = base_content_queryset(include_references=True).filter(slug=slug).first()
        if item is None:
            log_training_audit_event(
                event_type=TrainingAuditEvent.EventType.LAB_LAUNCH_NOT_FOUND,
                category=TrainingAuditEvent.Category.LAB,
                outcome=TrainingAuditEvent.Outcome.FAILED,
                request=request,
                metadata={"slug": slug},
            )
            raise Http404("Content item not found.")
        if not content_item_is_visible_to_user(item, request.user):
            log_training_audit_event(
                event_type=TrainingAuditEvent.EventType.LAB_LAUNCH_REJECTED,
                category=TrainingAuditEvent.Category.LAB,
                outcome=TrainingAuditEvent.Outcome.DENIED,
                request=request,
                actor=request.user,
                target_user=request.user,
                content_item=item,
                metadata={"slug": slug, "reason": "content_not_visible"},
            )
            raise Http404("Content item not found.")
        if item.content_kind != TrainingContentItem.ContentKind.NOTEBOOK:
            log_training_audit_event(
                event_type=TrainingAuditEvent.EventType.LAB_LAUNCH_REJECTED,
                category=TrainingAuditEvent.Category.LAB,
                outcome=TrainingAuditEvent.Outcome.FAILED,
                request=request,
                actor=request.user,
                target_user=request.user,
                content_item=item,
                metadata={"slug": slug, "reason": "content_is_not_notebook"},
            )
            return Response({"detail": "Only notebook content can be launched."}, status=400)

        try:
            lab_profile = item.lab_profile
        except TrainingNotebookLabProfile.DoesNotExist:
            log_training_audit_event(
                event_type=TrainingAuditEvent.EventType.LAB_LAUNCH_REJECTED,
                category=TrainingAuditEvent.Category.LAB,
                outcome=TrainingAuditEvent.Outcome.FAILED,
                request=request,
                actor=request.user,
                target_user=request.user,
                content_item=item,
                metadata={"slug": slug, "reason": "missing_lab_profile"},
            )
            return Response({"detail": "Notebook runtime profile is missing."}, status=400)
        if not lab_profile.is_active:
            log_training_audit_event(
                event_type=TrainingAuditEvent.EventType.LAB_LAUNCH_REJECTED,
                category=TrainingAuditEvent.Category.LAB,
                outcome=TrainingAuditEvent.Outcome.FAILED,
                request=request,
                actor=request.user,
                target_user=request.user,
                content_item=item,
                metadata={"slug": slug, "reason": "inactive_lab_profile"},
            )
            return Response({"detail": "Notebook runtime profile is inactive."}, status=400)
        if not training_lab_runtime_enabled():
            log_training_audit_event(
                event_type=TrainingAuditEvent.EventType.LAB_LAUNCH_REJECTED,
                category=TrainingAuditEvent.Category.LAB,
                outcome=TrainingAuditEvent.Outcome.FAILED,
                request=request,
                actor=request.user,
                target_user=request.user,
                content_item=item,
                metadata={"slug": slug, "reason": "runtime_disabled"},
            )
            return Response({"detail": "Notebook runtime is disabled."}, status=503)

        try:
            launch_token, signed_token = issue_lab_launch_token(user=request.user, content_item=item, request=request)
        except TrainingLabLaunchError as exc:
            log_training_audit_event(
                event_type=TrainingAuditEvent.EventType.LAB_LAUNCH_REJECTED,
                category=TrainingAuditEvent.Category.LAB,
                outcome=TrainingAuditEvent.Outcome.FAILED,
                request=request,
                actor=request.user,
                target_user=request.user,
                content_item=item,
                metadata={"slug": slug, "reason": str(exc)},
            )
            return Response({"detail": str(exc)}, status=400)
        log_training_audit_event(
            event_type=TrainingAuditEvent.EventType.LAB_LAUNCH_ISSUED,
            category=TrainingAuditEvent.Category.LAB,
            request=request,
            actor=request.user,
            target_user=request.user,
            content_item=item,
            launch_token=launch_token,
            metadata={
                "slug": slug,
                "runtimeBackend": lab_profile.runtime_backend,
                "graderBackend": lab_profile.grader_backend,
                "launchUrlPresent": bool(signed_token),
            },
        )
        return Response(build_lab_launch_contract(launch_token=launch_token, signed_token=signed_token), status=201)


class TrainingJupyterLaunchGatewayView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        signed_launch_token = str(request.query_params.get("training_launch_token") or "").strip()
        if not signed_launch_token:
            log_training_audit_event(
                event_type=TrainingAuditEvent.EventType.LAB_GATEWAY_REJECTED,
                category=TrainingAuditEvent.Category.LAB,
                outcome=TrainingAuditEvent.Outcome.FAILED,
                request=request,
                metadata={"reason": "missing_training_launch_token"},
            )
            return Response({"detail": "training_launch_token is required."}, status=400)
        if not training_lab_runtime_enabled():
            log_training_audit_event(
                event_type=TrainingAuditEvent.EventType.LAB_GATEWAY_REJECTED,
                category=TrainingAuditEvent.Category.LAB,
                outcome=TrainingAuditEvent.Outcome.FAILED,
                request=request,
                metadata={"reason": "runtime_disabled"},
            )
            return Response({"detail": "Notebook runtime is disabled."}, status=503)

        try:
            resolved_launch = resolve_lab_launch_token(signed_token=signed_launch_token)
        except TrainingLabLaunchTokenInvalidError as exc:
            log_training_audit_event(
                event_type=TrainingAuditEvent.EventType.LAB_GATEWAY_REJECTED,
                category=TrainingAuditEvent.Category.LAB,
                outcome=TrainingAuditEvent.Outcome.FAILED,
                request=request,
                metadata={"reason": str(exc)},
            )
            return Response({"detail": str(exc)}, status=400)

        try:
            login_token, signed_login_token = issue_jupyter_login_token(launch_token=resolved_launch.token)
        except TrainingJupyterAuthError as exc:
            log_training_audit_event(
                event_type=TrainingAuditEvent.EventType.LAB_GATEWAY_REJECTED,
                category=TrainingAuditEvent.Category.LAB,
                outcome=TrainingAuditEvent.Outcome.FAILED,
                request=request,
                actor=resolved_launch.token.user,
                target_user=resolved_launch.token.user,
                content_item=resolved_launch.token.content_item,
                launch_token=resolved_launch.token,
                metadata={"reason": str(exc)},
            )
            return Response({"detail": str(exc)}, status=400)

        redirect_url = build_jupyterhub_login_redirect_url(
            login_token=login_token,
            signed_token=signed_login_token,
        )
        if not redirect_url:
            log_training_audit_event(
                event_type=TrainingAuditEvent.EventType.LAB_GATEWAY_REJECTED,
                category=TrainingAuditEvent.Category.LAB,
                outcome=TrainingAuditEvent.Outcome.FAILED,
                request=request,
                actor=resolved_launch.token.user,
                target_user=resolved_launch.token.user,
                content_item=resolved_launch.token.content_item,
                launch_token=resolved_launch.token,
                jupyter_login_token=login_token,
                metadata={"reason": "missing_jupyterhub_base_url"},
            )
            return Response({"detail": "JupyterHub base URL is not configured."}, status=503)
        log_training_audit_event(
            event_type=TrainingAuditEvent.EventType.LAB_GATEWAY_REDIRECTED,
            category=TrainingAuditEvent.Category.LAB,
            request=request,
            actor=resolved_launch.token.user,
            target_user=resolved_launch.token.user,
            content_item=resolved_launch.token.content_item,
            launch_token=resolved_launch.token,
            jupyter_login_token=login_token,
            metadata={"redirectUrl": redirect_url},
        )
        return HttpResponseRedirect(redirect_url)


class TrainingInternalLabLaunchResolveView(APIView):
    authentication_classes = []
    permission_classes = [IsTrainingInternalService]

    def post(self, request):
        signed_token = str(request.data.get("launchToken") or "").strip()
        if not signed_token:
            log_training_audit_event(
                event_type=TrainingAuditEvent.EventType.LAB_GATEWAY_REJECTED,
                category=TrainingAuditEvent.Category.LAB,
                outcome=TrainingAuditEvent.Outcome.FAILED,
                request=request,
                metadata={"reason": "missing_launch_token", "service": "internal_resolve"},
            )
            return Response({"detail": "launchToken is required."}, status=400)
        try:
            resolved = resolve_lab_launch_token(signed_token=signed_token)
        except TrainingLabLaunchTokenInvalidError as exc:
            log_training_audit_event(
                event_type=TrainingAuditEvent.EventType.LAB_LAUNCH_RESOLVE_FAILED,
                category=TrainingAuditEvent.Category.LAB,
                outcome=TrainingAuditEvent.Outcome.FAILED,
                request=request,
                metadata={"reason": str(exc), "service": "internal_resolve"},
            )
            return Response({"detail": str(exc)}, status=400)
        log_training_audit_event(
            event_type=TrainingAuditEvent.EventType.LAB_LAUNCH_RESOLVED,
            category=TrainingAuditEvent.Category.LAB,
            request=request,
            actor=resolved.token.user,
            target_user=resolved.token.user,
            content_item=resolved.token.content_item,
            launch_token=resolved.token,
            metadata={"service": "internal_resolve", "tokenId": str(resolved.token.token_id)},
        )
        return Response(build_resolved_lab_contract(resolved_launch=resolved))


class TrainingInternalIssueJupyterLoginView(APIView):
    authentication_classes = []
    permission_classes = [IsTrainingInternalService]

    def post(self, request):
        token_id = str(request.data.get("tokenId") or "").strip()
        if not token_id:
            return Response({"detail": "tokenId is required."}, status=400)

        launch_token = (
            TrainingLabLaunchToken.objects.select_related("content_item__lab_profile", "user")
            .filter(token_id=token_id)
            .first()
        )
        if launch_token is None:
            log_training_audit_event(
                event_type=TrainingAuditEvent.EventType.LAB_LOGIN_ISSUE_NOT_FOUND,
                category=TrainingAuditEvent.Category.LAB,
                outcome=TrainingAuditEvent.Outcome.FAILED,
                request=request,
                metadata={"tokenId": token_id, "service": "internal_issue"},
            )
            return Response({"detail": "Launch token was not found."}, status=404)

        try:
            login_token, signed_token = issue_jupyter_login_token(launch_token=launch_token)
        except TrainingJupyterAuthError as exc:
            log_training_audit_event(
                event_type=TrainingAuditEvent.EventType.LAB_LOGIN_ISSUE_FAILED,
                category=TrainingAuditEvent.Category.LAB,
                outcome=TrainingAuditEvent.Outcome.FAILED,
                request=request,
                actor=launch_token.user,
                target_user=launch_token.user,
                content_item=launch_token.content_item,
                launch_token=launch_token,
                metadata={"tokenId": token_id, "reason": str(exc), "service": "internal_issue"},
            )
            return Response({"detail": str(exc)}, status=400)
        log_training_audit_event(
            event_type=TrainingAuditEvent.EventType.LAB_LOGIN_ISSUED,
            category=TrainingAuditEvent.Category.LAB,
            request=request,
            actor=launch_token.user,
            target_user=launch_token.user,
            content_item=launch_token.content_item,
            launch_token=launch_token,
            jupyter_login_token=login_token,
            metadata={"tokenId": token_id, "service": "internal_issue", "loginTokenId": str(login_token.token_id)},
        )
        return Response(build_jupyter_login_contract(login_token=login_token, signed_token=signed_token), status=201)


class TrainingInternalExchangeJupyterLoginView(APIView):
    authentication_classes = []
    permission_classes = [IsTrainingInternalService]

    def post(self, request):
        signed_token = str(request.data.get("loginToken") or request.data.get("login_token") or "").strip()
        if not signed_token:
            log_training_audit_event(
                event_type=TrainingAuditEvent.EventType.JUPYTER_LOGIN_REJECTED,
                category=TrainingAuditEvent.Category.LAB,
                outcome=TrainingAuditEvent.Outcome.FAILED,
                request=request,
                metadata={"reason": "missing_login_token", "service": "jupyterhub"},
            )
            return Response({"detail": "loginToken is required."}, status=400)

        try:
            resolved_login = resolve_jupyter_login_token(signed_token=signed_token)
        except TrainingJupyterLoginTokenInvalidError as exc:
            log_training_audit_event(
                event_type=TrainingAuditEvent.EventType.JUPYTER_LOGIN_REJECTED,
                category=TrainingAuditEvent.Category.LAB,
                outcome=TrainingAuditEvent.Outcome.FAILED,
                request=request,
                metadata={"reason": str(exc), "service": "jupyterhub"},
            )
            return Response({"detail": str(exc)}, status=400)
        log_training_audit_event(
            event_type=TrainingAuditEvent.EventType.JUPYTER_LOGIN_EXCHANGED,
            category=TrainingAuditEvent.Category.LAB,
            request=request,
            actor=resolved_login.token.user,
            target_user=resolved_login.token.user,
            content_item=resolved_login.token.content_item,
            launch_token=resolved_login.token.launch_token,
            jupyter_login_token=resolved_login.token,
            metadata={"service": "jupyterhub", "jupyterUsername": resolved_login.token.jupyter_username},
        )
        return Response(build_resolved_jupyter_login_contract(resolved_login=resolved_login))


class TrainingInternalNotebookValidateView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, slug: str):
        try:
            user, content_item = _internal_notebook_action_context_or_error(request=request, slug=slug)
        except TrainingNotebookActionError as exc:
            return Response({"detail": str(exc)}, status=401)
        notebook_upload = _require_internal_notebook_upload(request)
        try:
            preview = preview_lab_submission(content_item=content_item, notebook_upload=notebook_upload)
        except TrainingGradingError as exc:
            return Response({"detail": str(exc)}, status=400)
        recommended_hint_ids = list((preview.get("feedbackPayload") or {}).get("recommendedHintIds") or [])
        hint = None
        if not preview.get("passed"):
            hint = _preferred_preview_hint(content_item=content_item, recommended_hint_ids=recommended_hint_ids)
        return Response(
            {
                "validation": preview,
                "hint": _hint_payload(hint),
            },
            status=200,
        )


class TrainingInternalNotebookHintView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, slug: str):
        try:
            user, content_item = _internal_notebook_action_context_or_error(request=request, slug=slug)
        except TrainingNotebookActionError as exc:
            return Response({"detail": str(exc)}, status=401)
        notebook_upload = _require_internal_notebook_upload(request)
        try:
            preview = preview_lab_submission(content_item=content_item, notebook_upload=notebook_upload)
        except TrainingGradingError as exc:
            return Response({"detail": str(exc)}, status=400)
        if preview.get("passed"):
            return Response({"detail": "Validation already passes.", "validation": preview}, status=200)
        recommended_hint_ids = list((preview.get("feedbackPayload") or {}).get("recommendedHintIds") or [])
        hint = _preferred_preview_hint(content_item=content_item, recommended_hint_ids=recommended_hint_ids)
        if hint is None:
            return Response({"detail": "No hint is available yet.", "validation": preview}, status=404)
        log_training_audit_event(
            event_type=TrainingAuditEvent.EventType.LAB_HINT_VIEWED,
            category=TrainingAuditEvent.Category.LAB,
            request=request,
            actor=user,
            target_user=user,
            content_item=content_item,
            metadata={"mode": "notebook_assistant", "hintId": hint.id},
        )
        return Response({"hint": _hint_payload(hint), "validation": preview}, status=200)


class TrainingInternalNotebookAskView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    parser_classes = [JSONParser]

    def post(self, request, slug: str):
        try:
            user, content_item = _internal_notebook_action_context_or_error(request=request, slug=slug)
        except TrainingNotebookActionError as exc:
            return Response({"detail": str(exc)}, status=401)
        serializer = TrainingInternalNotebookAskSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            ai_result = ask_training_ai(
                user=user,
                content_item=content_item,
                question=serializer.validated_data["question"],
                prompt_type=TrainingAiMessage.PromptType.ASK,
            )
        except TrainingAiError as exc:
            return Response({"detail": str(exc)}, status=400)
        return Response(
            {
                "answer": ai_result.response_payload,
                "conversationId": str(ai_result.conversation.public_id),
            },
            status=200,
        )


class TrainingInternalNotebookSubmitView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, slug: str):
        try:
            user, content_item = _internal_notebook_action_context_or_error(request=request, slug=slug)
        except TrainingNotebookActionError as exc:
            return Response({"detail": str(exc)}, status=401)
        notebook_upload = _require_internal_notebook_upload(request)
        client_checksum = str(request.data.get("client_checksum") or request.data.get("clientChecksum") or "").strip()
        try:
            submission = create_lab_submission(
                user=user,
                content_item=content_item,
                notebook_upload=notebook_upload,
                client_checksum=client_checksum,
            )
            submission = grade_submission_now(submission=submission, worker_name="training-notebook-submit")
        except TrainingGradingError as exc:
            return Response({"detail": str(exc)}, status=400)
        serializer = TrainingLabSubmissionSerializer(submission, context={"request": request})
        return Response(serializer.data, status=201)


class TrainingInternalJupyterAiModelsView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request, slug: str):
        content_item = TrainingContentItem.objects.filter(slug=slug, content_kind=TrainingContentItem.ContentKind.NOTEBOOK).first()
        if content_item is None:
            return Response({"error": {"message": "Notebook content was not found.", "type": "not_found"}}, status=404)
        try:
            self._validate_proxy_token(request=request, content_slug=slug)
        except TrainingJupyterAiProxyError as exc:
            return Response({"error": {"message": str(exc), "type": "auth_error"}}, status=401)
        return Response(build_internal_jupyter_ai_models_payload(content_item=content_item), status=200)

    @staticmethod
    def _validate_proxy_token(*, request, content_slug: str) -> None:
        raw_authorization = str(request.headers.get("Authorization") or "").strip()
        if not raw_authorization.startswith("Bearer "):
            raise TrainingJupyterAiProxyError("Bearer token is required.")
        validate_internal_jupyter_ai_proxy_token(
            content_slug=content_slug,
            token=raw_authorization.removeprefix("Bearer ").strip(),
        )


class TrainingInternalJupyterAiChatCompletionsView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request, slug: str):
        content_item = TrainingContentItem.objects.filter(slug=slug, content_kind=TrainingContentItem.ContentKind.NOTEBOOK).first()
        if content_item is None:
            return Response({"error": {"message": "Notebook content was not found.", "type": "not_found"}}, status=404)
        try:
            self._validate_proxy_token(request=request, content_slug=slug)
        except TrainingJupyterAiProxyError as exc:
            return Response({"error": {"message": str(exc), "type": "auth_error"}}, status=401)
        try:
            proxy_request = resolve_internal_jupyter_ai_proxy_request(request.data if isinstance(request.data, dict) else {})
            payload = build_internal_jupyter_ai_chat_completion(
                content_item=content_item,
                question=proxy_request.question,
                requested_model=proxy_request.requested_model,
            )
        except TrainingJupyterAiProxyError as exc:
            return Response({"error": {"message": str(exc), "type": "proxy_error"}}, status=400)
        return Response(payload, status=200)

    @staticmethod
    def _validate_proxy_token(*, request, content_slug: str) -> None:
        raw_authorization = str(request.headers.get("Authorization") or "").strip()
        if not raw_authorization.startswith("Bearer "):
            raise TrainingJupyterAiProxyError("Bearer token is required.")
        validate_internal_jupyter_ai_proxy_token(
            content_slug=content_slug,
            token=raw_authorization.removeprefix("Bearer ").strip(),
        )


class TrainingInternalGraderReportView(APIView):
    authentication_classes = []
    permission_classes = [IsTrainingGraderService]

    def post(self, request):
        serializer = TrainingGraderWebhookResultSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            submission = apply_grader_webhook_result(
                submission_public_id=serializer.validated_data["submissionId"],
                score=serializer.validated_data.get("score"),
                max_score=serializer.validated_data.get("maxScore"),
                passed=serializer.validated_data.get("passed"),
                feedback_markdown=serializer.validated_data.get("feedbackMarkdown", ""),
                feedback_payload=serializer.validated_data.get("feedbackPayload") or {},
                artifacts=serializer.validated_data.get("artifacts") or [],
            )
        except TrainingGradingError as exc:
            log_training_audit_event(
                event_type=TrainingAuditEvent.EventType.GRADING_WEBHOOK_FAILED,
                category=TrainingAuditEvent.Category.GRADING,
                outcome=TrainingAuditEvent.Outcome.FAILED,
                request=request,
                metadata={
                    "submissionId": str(serializer.validated_data.get("submissionId") or ""),
                    "reason": str(exc),
                },
            )
            return Response({"detail": str(exc)}, status=400)
        log_training_audit_event(
            event_type=TrainingAuditEvent.EventType.GRADING_WEBHOOK_APPLIED,
            category=TrainingAuditEvent.Category.GRADING,
            request=request,
            actor=submission.user,
            target_user=submission.user,
            content_item=submission.content_item,
            submission=submission,
            metadata={"submissionId": str(submission.public_id), "status": submission.status},
        )
        return Response(TrainingLabSubmissionSerializer(submission, context={"request": request}).data)


def _optional_int_query_param(request, key: str) -> int | None:
    raw = str(request.query_params.get(key) or "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError as exc:
        raise ValidationError({key: "Must be an integer."}) from exc


def _bounded_positive_int_query_param(
    request,
    key: str,
    *,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    raw = str(request.query_params.get(key) or "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValidationError({key: "Must be an integer."}) from exc
    return max(minimum, min(value, maximum))


def _bool_query_param(request, key: str, *, default: bool) -> bool:
    raw = str(request.query_params.get(key) or "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def _admin_audience_or_404(audience_id: int) -> TrainingAudience:
    audience = TrainingAudience.objects.filter(id=audience_id).first()
    if audience is None:
        raise Http404("Audience not found.")
    return audience


def _admin_role_assignment_or_404(assignment_id: int) -> TrainingCourseRoleAssignment:
    assignment = TrainingCourseRoleAssignment.objects.select_related("course", "user").filter(id=assignment_id).first()
    if assignment is None:
        raise Http404("Role assignment not found.")
    return assignment


def _admin_grant_or_404(grant_id: int) -> TrainingUserAudienceGrant:
    grant = TrainingUserAudienceGrant.objects.select_related("user", "audience").filter(id=grant_id).first()
    if grant is None:
        raise Http404("Audience grant not found.")
    return grant


def _admin_notebook_assignment_or_404(content_id: int) -> TrainingContentItem:
    content_item = (
        TrainingContentItem.objects.select_related("course", "owner", "lab_profile")
        .prefetch_related("asset_classes", "topics", "audience_policies", "lab_profile__hints", "online_course_library_items")
        .filter(id=content_id, content_kind=TrainingContentItem.ContentKind.NOTEBOOK)
        .first()
    )
    if content_item is None:
        raise Http404("Notebook assignment not found.")
    return content_item


def _admin_ai_conversation_or_404(conversation_public_id) -> TrainingAiConversation:
    conversation = (
        TrainingAiConversation.objects.select_related(
            "content_item__course",
            "user",
            "assigned_to",
            "resolved_by",
        )
        .filter(public_id=conversation_public_id)
        .first()
    )
    if conversation is None:
        raise Http404("AI conversation not found.")
    return conversation


def _visible_content_or_404(request, *, slug: str, include_references: bool) -> TrainingContentItem:
    item = base_content_queryset(include_references=include_references).filter(slug=slug).first()
    if item is None or not content_item_is_visible_to_user(item, request.user):
        raise Http404("Content item not found.")
    return item


def _latest_consumed_launch_token_for_user(*, user, content_item: TrainingContentItem) -> TrainingLabLaunchToken | None:
    return (
        TrainingLabLaunchToken.objects.filter(
            user=user,
            content_item=content_item,
            status=TrainingLabLaunchToken.Status.CONSUMED,
        )
        .order_by("-consumed_at", "-created_at")
        .first()
    )
