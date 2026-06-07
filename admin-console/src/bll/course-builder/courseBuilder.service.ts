import { baseApi } from "@/bll/base-api";
import type {
  CourseBuilderCourse,
  CourseBuilderImportInput,
  CourseBuilderCourseUpsertInput,
  CourseBuilderDeliveryAssignmentInput,
  CourseBuilderDeliveryAssignmentResponse,
  CourseBuilderLessonGenerationInput,
  CourseBuilderLessonGenerationResponse,
  CourseBuilderVideoLessonGenerationInput,
  CourseBuilderLibraryItem,
  CourseBuilderLibraryItemUpsertInput,
  CourseBuilderLibraryListResponse,
  CourseBuilderNotebookListResponse,
  CourseBuilderSessionSeedInput,
  CourseBuilderSessionSeedResponse,
  CourseBuilderTemplateListResponse,
} from "./courseBuilder.type";

export const courseBuilderService = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    getCourseBuilderTemplates: builder.query<CourseBuilderTemplateListResponse, void>({
      query: () => ({
        url: "/online/admin/course-templates/",
        method: "GET",
      }),
      providesTags: [{ type: "CourseBuilderTemplate", id: "LIST" }],
    }),
    getCourseBuilderLibrary: builder.query<
      CourseBuilderLibraryListResponse,
      { q?: string; sectionType?: string; assetType?: string } | void
    >({
      query: (args) => ({
        url: "/online/admin/course-library/",
        method: "GET",
        params: {
          ...(args?.q ? { q: args.q } : {}),
          ...(args?.sectionType ? { section_type: args.sectionType } : {}),
          ...(args?.assetType ? { asset_type: args.assetType } : {}),
        },
      }),
      providesTags: [{ type: "CourseBuilderLibraryItem", id: "LIST" }],
    }),
    createCourseBuilderLibraryItem: builder.mutation<CourseBuilderLibraryItem, CourseBuilderLibraryItemUpsertInput>({
      query: (body) => {
        if (body.file instanceof File) {
          const formData = new FormData();
          formData.append("sectionType", body.sectionType);
          formData.append("title", body.title);
          formData.append("description", body.description);
          formData.append("libraryGroup", body.libraryGroup);
          formData.append("assetType", body.assetType);
          formData.append("language", body.language);
          formData.append("bodyMarkdown", body.bodyMarkdown);
          formData.append("externalUrl", body.externalUrl);
          formData.append("sortOrder", String(body.sortOrder));
          formData.append("isActive", String(body.isActive));
          if (body.trainingContentId) {
            formData.append("trainingContentId", String(body.trainingContentId));
          }
          (body.audienceIds ?? []).forEach((audienceId, index) => {
            formData.append(`audienceIds[${index}]`, String(audienceId));
          });
          formData.append("file", body.file);
          return {
            url: "/online/admin/course-library/",
            method: "POST",
            body: formData,
          };
        }
        return {
          url: "/online/admin/course-library/",
          method: "POST",
          body: {
            sectionType: body.sectionType,
            title: body.title,
            description: body.description,
            libraryGroup: body.libraryGroup,
            assetType: body.assetType,
            language: body.language,
            bodyMarkdown: body.bodyMarkdown,
            externalUrl: body.externalUrl,
            trainingContentId: body.trainingContentId ?? null,
            audienceIds: body.audienceIds ?? [],
            sortOrder: body.sortOrder,
            isActive: body.isActive,
          },
        };
      },
      invalidatesTags: [{ type: "CourseBuilderLibraryItem", id: "LIST" }],
    }),
    updateCourseBuilderLibraryItem: builder.mutation<
      CourseBuilderLibraryItem,
      { itemId: number; body: Partial<CourseBuilderLibraryItemUpsertInput> }
    >({
      query: ({ itemId, body }) => {
        if (body.file instanceof File) {
          const formData = new FormData();
          Object.entries(body).forEach(([key, value]) => {
            if (key === "file") return;
            if (key === "audienceIds" && Array.isArray(value)) {
              value.forEach((audienceId, index) => {
                formData.append(`audienceIds[${index}]`, String(audienceId));
              });
              return;
            }
            if (value === undefined || value === null) return;
            formData.append(key, typeof value === "boolean" ? String(value) : String(value));
          });
          formData.append("file", body.file);
          return {
            url: `/online/admin/course-library/${itemId}/`,
            method: "PATCH",
            body: formData,
          };
        }
        return {
          url: `/online/admin/course-library/${itemId}/`,
          method: "PATCH",
          body,
        };
      },
      invalidatesTags: [{ type: "CourseBuilderLibraryItem", id: "LIST" }],
    }),
    deleteCourseBuilderLibraryItem: builder.mutation<void, number>({
      query: (itemId) => ({
        url: `/online/admin/course-library/${itemId}/`,
        method: "DELETE",
      }),
      invalidatesTags: [{ type: "CourseBuilderLibraryItem", id: "LIST" }],
    }),
    getCourseBuilderNotebooks: builder.query<CourseBuilderNotebookListResponse, { q?: string; courseId?: number } | void>({
      query: (args) => ({
        url: "/online/admin/course-notebooks/",
        method: "GET",
        params: {
          ...(args?.q ? { q: args.q } : {}),
          ...(args?.courseId ? { course_id: args.courseId } : {}),
        },
      }),
      providesTags: [{ type: "CourseBuilderNotebook", id: "LIST" }],
    }),
    createCourseBuilderCourse: builder.mutation<CourseBuilderCourse, CourseBuilderCourseUpsertInput>({
      query: (body) => ({
        url: "/online/admin/course-builder/courses/",
        method: "POST",
        body,
      }),
      invalidatesTags: [
        { type: "CourseBuilderCourse", id: "LIST" },
        { type: "CourseBuilderTemplate", id: "LIST" },
      ],
    }),
    importCourseBuilderCourse: builder.mutation<CourseBuilderCourse, CourseBuilderImportInput>({
      query: (body) => ({
        url: "/online/admin/course-builder/import/",
        method: "POST",
        body,
      }),
      invalidatesTags: [{ type: "CourseBuilderCourse", id: "LIST" }],
    }),
    generateCourseBuilderLesson: builder.mutation<CourseBuilderLessonGenerationResponse, CourseBuilderLessonGenerationInput>({
      query: (body) => ({
        url: "/online/admin/course-builder/lessons/generate/",
        method: "POST",
        body,
      }),
    }),
    generateCourseBuilderLessonFromVideo: builder.mutation<
      CourseBuilderLessonGenerationResponse,
      CourseBuilderVideoLessonGenerationInput
    >({
      query: (body) => {
        const formData = new FormData();
        formData.append("title", body.title);
        formData.append("description", body.description ?? "");
        formData.append("language", body.language ?? "en");
        formData.append("courseTitle", body.courseTitle ?? "");
        formData.append("moduleTitle", body.moduleTitle ?? "");
        formData.append("videoUrl", body.videoUrl ?? "");
        formData.append("videoDescription", body.videoDescription ?? "");
        formData.append("videoFile", body.videoFile);
        return {
          url: "/online/admin/course-builder/lessons/generate-from-video/",
          method: "POST",
          body: formData,
        };
      },
      invalidatesTags: [{ type: "CourseBuilderLibraryItem", id: "LIST" }],
    }),
    getCourseBuilderCourse: builder.query<CourseBuilderCourse, number>({
      query: (courseId) => ({
        url: `/online/admin/course-builder/courses/${courseId}/`,
        method: "GET",
      }),
      providesTags: (_result, _error, courseId) => [{ type: "CourseBuilderCourse", id: courseId }],
    }),
    updateCourseBuilderCourse: builder.mutation<CourseBuilderCourse, { courseId: number; body: Partial<CourseBuilderCourseUpsertInput> }>({
      query: ({ courseId, body }) => ({
        url: `/online/admin/course-builder/courses/${courseId}/`,
        method: "PATCH",
        body,
      }),
      invalidatesTags: (_result, _error, { courseId }) => [
        { type: "CourseBuilderCourse", id: "LIST" },
        { type: "CourseBuilderCourse", id: courseId },
      ],
    }),
    saveCourseBuilderDeliveryAssignment: builder.mutation<
      CourseBuilderDeliveryAssignmentResponse,
      { courseId: number; body: CourseBuilderDeliveryAssignmentInput }
    >({
      query: ({ courseId, body }) => ({
        url: `/online/admin/course-builder/courses/${courseId}/delivery/`,
        method: "POST",
        body,
      }),
      invalidatesTags: (_result, _error, { courseId }) => [
        { type: "CourseBuilderCourse", id: courseId },
        { type: "OnlineAdminCohortDirectory", id: "LIST" },
        { type: "OnlineAdminCurator", id: "LIST" },
      ],
    }),
    createCourseBuilderSessions: builder.mutation<
      CourseBuilderSessionSeedResponse,
      { courseId: number; body: { cohortId: number; sessions: CourseBuilderSessionSeedInput[] } }
    >({
      query: ({ courseId, body }) => ({
        url: `/online/admin/course-builder/courses/${courseId}/sessions/`,
        method: "POST",
        body,
      }),
      invalidatesTags: (_result, _error, { courseId }) => [
        { type: "CourseBuilderCourse", id: courseId },
        { type: "OnlineAdminCohortDirectory", id: "LIST" },
        { type: "OnlineAdminSessionDirectory", id: "LIST" },
      ],
    }),
  }),
});

export const {
  useGetCourseBuilderTemplatesQuery,
  useGetCourseBuilderLibraryQuery,
  useCreateCourseBuilderLibraryItemMutation,
  useUpdateCourseBuilderLibraryItemMutation,
  useDeleteCourseBuilderLibraryItemMutation,
  useGetCourseBuilderNotebooksQuery,
  useCreateCourseBuilderCourseMutation,
  useImportCourseBuilderCourseMutation,
  useGenerateCourseBuilderLessonMutation,
  useGenerateCourseBuilderLessonFromVideoMutation,
  useGetCourseBuilderCourseQuery,
  useUpdateCourseBuilderCourseMutation,
  useSaveCourseBuilderDeliveryAssignmentMutation,
  useCreateCourseBuilderSessionsMutation,
} = courseBuilderService;
