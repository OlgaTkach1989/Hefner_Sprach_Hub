from __future__ import annotations

from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.employees.models import Lehrer
from apps.online.models import (
    OnlineCatalogAttributeDefinition,
    OnlineCatalogAttributeValue,
    OnlineExternalCatalogProvider,
    OnlineInstructorProfile,
    OnlineKnowledgeDocument,
    OnlineKnowledgeSource,
    OnlineLearningProgram,
    OnlineStudentProfile,
    OnlineStudentProgramAssignment,
)
from apps.online.permissions import IsOnlineAdmin
from apps.online.serializers_enterprise import (
    OnlineCatalogAttributeDefinitionSerializer,
    OnlineCatalogAttributeDefinitionUpsertSerializer,
    OnlineCatalogAttributeValueSerializer,
    OnlineCatalogAttributeValueUpsertSerializer,
    OnlineCatalogSearchQuerySerializer,
    OnlineExternalCatalogProviderSerializer,
    OnlineExternalCatalogProviderUpsertSerializer,
    OnlineInstructorProfileSerializer,
    OnlineInstructorProfileUpsertSerializer,
    OnlineKnowledgeDocumentSerializer,
    OnlineKnowledgeDocumentUpsertSerializer,
    OnlineKnowledgeSourceSerializer,
    OnlineKnowledgeSourceUpsertSerializer,
    OnlineLearningProgramSerializer,
    OnlineLearningProgramUpsertSerializer,
    OnlineStudentProfileAdminSerializer,
    OnlineStudentProfileAdminUpsertSerializer,
    OnlineStudentProgramAssignmentSerializer,
    OnlineStudentProgramAssignmentUpsertSerializer,
)
from apps.online.services.catalog_registry import (
    attribute_value_payload,
    build_admin_catalog_search_payload,
    sync_program_courses,
)


class OnlineAdminCatalogSearchView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    def get(self, request):
        serializer = OnlineCatalogSearchQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        return Response(
            build_admin_catalog_search_payload(
                query=payload.get("q", ""),
                confidentiality_level=payload.get("confidentialityLevel", ""),
                provider_type=payload.get("providerType", ""),
                course_type=payload.get("courseType", ""),
                difficulty_level=payload.get("difficultyLevel", ""),
                knowledge_domain=payload.get("knowledgeDomain", ""),
                rating_min=payload.get("ratingMin"),
            ),
            status=status.HTTP_200_OK,
        )


class OnlineAdminCatalogAttributeDefinitionListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    def get(self, request):
        queryset = OnlineCatalogAttributeDefinition.objects.order_by("entity_type", "sort_order", "id")
        entity_type = (request.query_params.get("entity_type") or "").strip()
        if entity_type:
            queryset = queryset.filter(entity_type=entity_type)
        serializer = OnlineCatalogAttributeDefinitionSerializer(queryset, many=True)
        return Response({"results": serializer.data}, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = OnlineCatalogAttributeDefinitionUpsertSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        definition = serializer.save()
        return Response(
            OnlineCatalogAttributeDefinitionSerializer(definition).data,
            status=status.HTTP_201_CREATED,
        )


class OnlineAdminCatalogAttributeDefinitionDetailView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    def get_object(self, definition_id: int) -> OnlineCatalogAttributeDefinition:
        return get_object_or_404(OnlineCatalogAttributeDefinition, id=definition_id)

    def get(self, request, definition_id: int):
        return Response(
            OnlineCatalogAttributeDefinitionSerializer(self.get_object(definition_id)).data,
            status=status.HTTP_200_OK,
        )

    def patch(self, request, definition_id: int):
        definition = self.get_object(definition_id)
        serializer = OnlineCatalogAttributeDefinitionUpsertSerializer(definition, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        definition = serializer.save()
        return Response(
            OnlineCatalogAttributeDefinitionSerializer(definition).data,
            status=status.HTTP_200_OK,
        )

    def delete(self, request, definition_id: int):
        self.get_object(definition_id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class OnlineAdminCatalogAttributeValueListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    def get(self, request):
        queryset = OnlineCatalogAttributeValue.objects.select_related("definition").order_by(
            "definition__entity_type",
            "definition__sort_order",
            "id",
        )
        definition_id = (request.query_params.get("definition_id") or "").strip()
        object_id = (request.query_params.get("object_id") or "").strip()
        entity_type = (request.query_params.get("entity_type") or "").strip()
        if definition_id.isdigit():
            queryset = queryset.filter(definition_id=int(definition_id))
        if object_id.isdigit():
            queryset = queryset.filter(object_id=int(object_id))
        if entity_type:
            queryset = queryset.filter(definition__entity_type=entity_type)
        return Response(
            {"results": [attribute_value_payload(item) for item in queryset[:300]]},
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        serializer = OnlineCatalogAttributeValueUpsertSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        value, _created = OnlineCatalogAttributeValue.objects.update_or_create(
            definition=payload["definition"],
            content_type=payload["content_type"],
            object_id=payload["objectId"],
            defaults={"value_json": payload.get("valueJson", {})},
        )
        return Response(attribute_value_payload(value), status=status.HTTP_201_CREATED)


class OnlineAdminCatalogAttributeValueDetailView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    def get_object(self, value_id: int) -> OnlineCatalogAttributeValue:
        return get_object_or_404(OnlineCatalogAttributeValue.objects.select_related("definition"), id=value_id)

    def patch(self, request, value_id: int):
        value = self.get_object(value_id)
        serializer = OnlineCatalogAttributeValueUpsertSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        value.definition = payload["definition"]
        value.content_type = payload["content_type"]
        value.object_id = payload["objectId"]
        value.value_json = payload.get("valueJson", {})
        value.save()
        return Response(attribute_value_payload(value), status=status.HTTP_200_OK)

    def delete(self, request, value_id: int):
        self.get_object(value_id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class OnlineAdminStudentProfileListView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    def get(self, request):
        query = (request.query_params.get("q") or "").strip()
        queryset = OnlineStudentProfile.objects.select_related("user").order_by("last_name", "first_name", "id")
        if query:
            queryset = queryset.filter(
                Q(first_name__icontains=query)
                | Q(last_name__icontains=query)
                | Q(user__email__icontains=query)
                | Q(employee_id__icontains=query)
                | Q(department__icontains=query)
                | Q(team_name__icontains=query)
                | Q(job_title__icontains=query)
            )
        return Response(
            {"results": OnlineStudentProfileAdminSerializer(queryset[:200], many=True).data},
            status=status.HTTP_200_OK,
        )


class OnlineAdminStudentProfileDetailView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    def get_object(self, profile_id: int) -> OnlineStudentProfile:
        return get_object_or_404(OnlineStudentProfile.objects.select_related("user"), id=profile_id)

    def get(self, request, profile_id: int):
        return Response(
            OnlineStudentProfileAdminSerializer(self.get_object(profile_id)).data,
            status=status.HTTP_200_OK,
        )

    def patch(self, request, profile_id: int):
        profile = self.get_object(profile_id)
        serializer = OnlineStudentProfileAdminUpsertSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        profile = serializer.save()
        return Response(OnlineStudentProfileAdminSerializer(profile).data, status=status.HTTP_200_OK)


class OnlineAdminInstructorProfileListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    def get(self, request):
        query = (request.query_params.get("q") or "").strip()
        queryset = OnlineInstructorProfile.objects.select_related("teacher", "teacher__user").order_by(
            "teacher__Nachname",
            "teacher__Vorname",
            "id",
        )
        if query:
            queryset = queryset.filter(
                Q(teacher__Vorname__icontains=query)
                | Q(teacher__Nachname__icontains=query)
                | Q(teacher__Schule_Email__icontains=query)
                | Q(job_title__icontains=query)
                | Q(department__icontains=query)
                | Q(bio__icontains=query)
            )
        return Response(
            {"results": OnlineInstructorProfileSerializer(queryset[:200], many=True).data},
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        teacher_id = request.data.get("teacherId")
        if not teacher_id:
            return Response({"teacherId": "Teacher is required."}, status=status.HTTP_400_BAD_REQUEST)
        teacher = get_object_or_404(Lehrer.objects.select_related("user"), id=teacher_id)
        serializer = OnlineInstructorProfileUpsertSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile, _created = OnlineInstructorProfile.objects.get_or_create(teacher=teacher)
        for field, value in serializer.validated_data.items():
            setattr(profile, field, value)
        profile.save()
        return Response(OnlineInstructorProfileSerializer(profile).data, status=status.HTTP_201_CREATED)


class OnlineAdminInstructorProfileDetailView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    def get_object(self, profile_id: int) -> OnlineInstructorProfile:
        return get_object_or_404(
            OnlineInstructorProfile.objects.select_related("teacher", "teacher__user"),
            id=profile_id,
        )

    def get(self, request, profile_id: int):
        return Response(OnlineInstructorProfileSerializer(self.get_object(profile_id)).data, status=status.HTTP_200_OK)

    def patch(self, request, profile_id: int):
        profile = self.get_object(profile_id)
        serializer = OnlineInstructorProfileUpsertSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        profile = serializer.save()
        return Response(OnlineInstructorProfileSerializer(profile).data, status=status.HTTP_200_OK)

    def delete(self, request, profile_id: int):
        self.get_object(profile_id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class OnlineAdminExternalCatalogProviderListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    def get(self, request):
        queryset = OnlineExternalCatalogProvider.objects.order_by("display_name", "id")
        return Response(
            {"results": OnlineExternalCatalogProviderSerializer(queryset, many=True).data},
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        serializer = OnlineExternalCatalogProviderUpsertSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        provider = serializer.save()
        return Response(OnlineExternalCatalogProviderSerializer(provider).data, status=status.HTTP_201_CREATED)


class OnlineAdminExternalCatalogProviderDetailView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    def get_object(self, provider_id: int) -> OnlineExternalCatalogProvider:
        return get_object_or_404(OnlineExternalCatalogProvider, id=provider_id)

    def patch(self, request, provider_id: int):
        provider = self.get_object(provider_id)
        serializer = OnlineExternalCatalogProviderUpsertSerializer(provider, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        provider = serializer.save()
        return Response(OnlineExternalCatalogProviderSerializer(provider).data, status=status.HTTP_200_OK)

    def delete(self, request, provider_id: int):
        self.get_object(provider_id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class OnlineAdminLearningProgramListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    def get(self, request):
        queryset = OnlineLearningProgram.objects.prefetch_related("program_courses__course").order_by("title", "id")
        return Response(
            {"results": OnlineLearningProgramSerializer(queryset, many=True).data},
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        serializer = OnlineLearningProgramUpsertSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        program_courses = serializer.validated_data.pop("programCourses", [])
        with transaction.atomic():
            program = serializer.save(created_by=request.user)
            sync_program_courses(program=program, items_data=program_courses)
        program = OnlineLearningProgram.objects.prefetch_related("program_courses__course").get(id=program.id)
        return Response(OnlineLearningProgramSerializer(program).data, status=status.HTTP_201_CREATED)


class OnlineAdminLearningProgramDetailView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    def get_object(self, program_id: int) -> OnlineLearningProgram:
        return get_object_or_404(
            OnlineLearningProgram.objects.prefetch_related("program_courses__course", "student_assignments"),
            id=program_id,
        )

    def get(self, request, program_id: int):
        return Response(OnlineLearningProgramSerializer(self.get_object(program_id)).data, status=status.HTTP_200_OK)

    def patch(self, request, program_id: int):
        program = self.get_object(program_id)
        serializer = OnlineLearningProgramUpsertSerializer(program, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        program_courses = serializer.validated_data.pop("programCourses", None)
        with transaction.atomic():
            program = serializer.save()
            if program_courses is not None:
                sync_program_courses(program=program, items_data=program_courses)
        program = OnlineLearningProgram.objects.prefetch_related("program_courses__course", "student_assignments").get(id=program.id)
        return Response(OnlineLearningProgramSerializer(program).data, status=status.HTTP_200_OK)

    def delete(self, request, program_id: int):
        self.get_object(program_id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class OnlineAdminStudentProgramAssignmentListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    def get(self, request):
        queryset = OnlineStudentProgramAssignment.objects.select_related("profile__user", "program", "assigned_by").order_by("-created_at", "-id")
        program_id = (request.query_params.get("program_id") or "").strip()
        profile_id = (request.query_params.get("profile_id") or "").strip()
        if program_id.isdigit():
            queryset = queryset.filter(program_id=int(program_id))
        if profile_id.isdigit():
            queryset = queryset.filter(profile_id=int(profile_id))
        return Response(
            {"results": OnlineStudentProgramAssignmentSerializer(queryset[:300], many=True).data},
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        serializer = OnlineStudentProgramAssignmentUpsertSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        assignment = serializer.save(assigned_by=request.user)
        return Response(
            OnlineStudentProgramAssignmentSerializer(assignment).data,
            status=status.HTTP_201_CREATED,
        )


class OnlineAdminStudentProgramAssignmentDetailView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    def get_object(self, assignment_id: int) -> OnlineStudentProgramAssignment:
        return get_object_or_404(
            OnlineStudentProgramAssignment.objects.select_related("profile__user", "program", "assigned_by"),
            id=assignment_id,
        )

    def patch(self, request, assignment_id: int):
        assignment = self.get_object(assignment_id)
        serializer = OnlineStudentProgramAssignmentUpsertSerializer(assignment, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        assignment = serializer.save()
        return Response(OnlineStudentProgramAssignmentSerializer(assignment).data, status=status.HTTP_200_OK)

    def delete(self, request, assignment_id: int):
        self.get_object(assignment_id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class OnlineAdminKnowledgeSourceListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    def get(self, request):
        queryset = OnlineKnowledgeSource.objects.select_related("owner", "linked_course").order_by("title", "id")
        query = (request.query_params.get("q") or "").strip()
        if query:
            queryset = queryset.filter(
                Q(title__icontains=query)
                | Q(description__icontains=query)
                | Q(external_url__icontains=query)
                | Q(linked_course__title_en__icontains=query)
            )
        return Response(
            {"results": OnlineKnowledgeSourceSerializer(queryset[:200], many=True).data},
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        serializer = OnlineKnowledgeSourceUpsertSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        source = serializer.save(owner=request.user)
        return Response(OnlineKnowledgeSourceSerializer(source).data, status=status.HTTP_201_CREATED)


class OnlineAdminKnowledgeSourceDetailView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    def get_object(self, source_id: int) -> OnlineKnowledgeSource:
        return get_object_or_404(OnlineKnowledgeSource.objects.select_related("owner", "linked_course"), id=source_id)

    def patch(self, request, source_id: int):
        source = self.get_object(source_id)
        serializer = OnlineKnowledgeSourceUpsertSerializer(source, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        source = serializer.save()
        return Response(OnlineKnowledgeSourceSerializer(source).data, status=status.HTTP_200_OK)

    def delete(self, request, source_id: int):
        self.get_object(source_id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class OnlineAdminKnowledgeDocumentListCreateView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    def get(self, request):
        queryset = OnlineKnowledgeDocument.objects.select_related("source", "source__linked_course").order_by("source_id", "id")
        source_id = (request.query_params.get("source_id") or "").strip()
        query = (request.query_params.get("q") or "").strip()
        if source_id.isdigit():
            queryset = queryset.filter(source_id=int(source_id))
        if query:
            queryset = queryset.filter(
                Q(title__icontains=query)
                | Q(description__icontains=query)
                | Q(body_markdown__icontains=query)
                | Q(transcript_text__icontains=query)
            )
        return Response(
            {"results": OnlineKnowledgeDocumentSerializer(queryset[:300], many=True).data},
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        serializer = OnlineKnowledgeDocumentUpsertSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        document = serializer.save()
        return Response(OnlineKnowledgeDocumentSerializer(document).data, status=status.HTTP_201_CREATED)


class OnlineAdminKnowledgeDocumentDetailView(APIView):
    permission_classes = [IsAuthenticated, IsOnlineAdmin]

    def get_object(self, document_id: int) -> OnlineKnowledgeDocument:
        return get_object_or_404(
            OnlineKnowledgeDocument.objects.select_related("source", "source__linked_course"),
            id=document_id,
        )

    def patch(self, request, document_id: int):
        document = self.get_object(document_id)
        serializer = OnlineKnowledgeDocumentUpsertSerializer(document, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        document = serializer.save()
        return Response(OnlineKnowledgeDocumentSerializer(document).data, status=status.HTTP_200_OK)

    def delete(self, request, document_id: int):
        self.get_object(document_id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
