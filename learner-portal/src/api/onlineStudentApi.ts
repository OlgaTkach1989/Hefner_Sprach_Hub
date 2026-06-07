import { apiClient } from "./client";
import type {
  DashboardResponse,
  Gender,
  LearningWorkspacePayload,
  LoginResponse,
  StudentLessonAiAskResponse,
  StudentLessonDetailResponse,
  StudentLessonGraderResponse,
  StudentProfile,
  SupportMessage,
} from "../types";

export const onlineStudentLogin = async (identifier: string, password: string): Promise<LoginResponse> => {
  const response = await apiClient.post<LoginResponse>("/public/auth/login/", { identifier, password });
  return response.data;
};

export const onlineStudentGoogleLogin = async (credential: string): Promise<LoginResponse> => {
  const response = await apiClient.post<LoginResponse>("/public/auth/google/login/", { credential });
  return response.data;
};

export const fetchStudentMe = async (): Promise<StudentProfile> => {
  const response = await apiClient.get<StudentProfile>("/student/me/");
  return response.data;
};

export const logoutStudentSession = async (): Promise<void> => {
  await apiClient.post("/public/auth/logout/", {});
};

export const fetchStudentDashboard = async (): Promise<DashboardResponse> => {
  const response = await apiClient.get<DashboardResponse>("/student/dashboard/");
  return response.data;
};

export const fetchStudentLesson = async (lessonId: number): Promise<StudentLessonDetailResponse> => {
  const response = await apiClient.get<StudentLessonDetailResponse>(`/student/lessons/${lessonId}/`);
  return response.data;
};

export const saveStudentLessonProgress = async (
  lessonId: number,
  payload: {
    activeStepId?: string;
    completedStepIds?: string[];
  },
): Promise<{
  progress: NonNullable<StudentLessonDetailResponse["lesson"]["progress"]>;
  completion: StudentLessonDetailResponse["completion"];
}> => {
  const response = await apiClient.post(`/student/lessons/${lessonId}/progress/`, payload);
  return response.data;
};

export const submitStudentCourseAttestation = async (
  enrollmentId: number,
  payload: {
    fullName: string;
    agreed: boolean;
  },
): Promise<{
  attestation: NonNullable<StudentLessonDetailResponse["completion"]["attestation"]>;
  evidence: StudentLessonDetailResponse["completion"]["evidence"];
  completion: StudentLessonDetailResponse["completion"];
}> => {
  const response = await apiClient.post(`/student/enrollments/${enrollmentId}/attestation/`, payload);
  return response.data;
};

export const askStudentLessonAi = async (
  lessonId: number,
  payload: {
    question: string;
    stepId?: string;
    promptType?: string;
    code?: string;
  },
): Promise<StudentLessonAiAskResponse> => {
  const response = await apiClient.post<StudentLessonAiAskResponse>(
    `/student/lessons/${lessonId}/ai/ask/`,
    payload,
    {
      // Lesson AI answers can take longer than the default API timeout, especially on
      // richer prompts like key takeaways and practice guidance.
      timeout: 45000,
    },
  );
  return response.data;
};

export const checkStudentLessonCode = async (
  lessonId: number,
  payload: {
    stepId: string;
    code: string;
  },
): Promise<StudentLessonGraderResponse> => {
  const response = await apiClient.post<StudentLessonGraderResponse>(`/student/lessons/${lessonId}/grader/check/`, payload);
  return response.data;
};

export const fetchLearningWorkspace = async (programSlug: string): Promise<LearningWorkspacePayload> => {
  const response = await apiClient.get<LearningWorkspacePayload>(`/student/workspaces/${programSlug}/`);
  return response.data;
};

export const fetchSupportMessages = async (): Promise<SupportMessage[]> => {
  const response = await apiClient.get<{ results: SupportMessage[] }>("/student/support-messages/");
  return response.data.results;
};

export const createSupportMessage = async (message: string, enrollmentId?: number): Promise<SupportMessage> => {
  const response = await apiClient.post<SupportMessage>("/student/support-messages/", {
    message,
    enrollment_id: enrollmentId
  });
  return response.data;
};

export const markStudentSessionJoin = async (sessionId: number): Promise<{
  sessionId: number;
  attendanceStatus: string;
  joinedAt?: string | null;
  joinUrl?: string | null;
}> => {
  const response = await apiClient.post(`/student/sessions/${sessionId}/join/`);
  return response.data;
};

type UpdateProfilePayload = {
  phone?: string;
  gender?: Gender;
  avatar?: File;
  removeAvatar?: boolean;
};

export const updateStudentProfile = async (payload: UpdateProfilePayload): Promise<StudentProfile> => {
  const formData = new FormData();

  if (payload.phone !== undefined) {
    formData.append("phone", payload.phone);
  }
  if (payload.gender !== undefined) {
    formData.append("gender", payload.gender);
  }
  if (payload.avatar) {
    formData.append("avatar", payload.avatar);
  }
  if (payload.removeAvatar) {
    formData.append("remove_avatar", "true");
  }

  const response = await apiClient.patch<StudentProfile>("/student/profile/", formData, {
    headers: {
      "Content-Type": "multipart/form-data"
    }
  });
  return response.data;
};
