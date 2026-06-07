import { baseApi } from "@/bll/base-api";
import type {
  TeacherFeedbackRequest,
  TeacherFeedbackResponse,
  TeacherWorkspaceProfile,
  TeacherWorkspaceResponse,
  UpdateTeacherWorkspaceProfileRequest,
} from "@/bll/workspace/workspace.type";

export const workspaceService = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    getTeacherWorkspace: builder.query<TeacherWorkspaceResponse, void>({
      query: () => ({
        url: "/online/teacher/workspace/",
        method: "GET",
      }),
    }),
    getTeacherWorkspaceProfile: builder.query<TeacherWorkspaceProfile, void>({
      query: () => ({
        url: "/online/teacher/profile/",
        method: "GET",
      }),
    }),
    updateTeacherWorkspaceProfile: builder.mutation<TeacherWorkspaceProfile, UpdateTeacherWorkspaceProfileRequest>({
      query: (body) => ({
        url: "/online/teacher/profile/",
        method: "PATCH",
        body,
      }),
    }),
    submitTeacherFeedback: builder.mutation<TeacherFeedbackResponse, TeacherFeedbackRequest>({
      query: (body) => ({
        url: "/online/teacher/feedback/",
        method: "POST",
        body,
      }),
    }),
  }),
});

export const {
  useGetTeacherWorkspaceProfileQuery,
  useGetTeacherWorkspaceQuery,
  useSubmitTeacherFeedbackMutation,
  useUpdateTeacherWorkspaceProfileMutation,
} = workspaceService;
