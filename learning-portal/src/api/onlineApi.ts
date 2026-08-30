import { isAxiosError } from "axios";

import { apiClient } from "./client";
import type {
  CheckoutPayload,
  GoogleCheckoutPayload,
  GoogleCheckoutResponse,
  CheckoutStartResponse,
  CheckoutStatusResponse,
  CourseDetail,
  CourseSummary,
  Locale,
  MagicLinkRequestPayload,
  MagicLinkRequestResponse,
  PublicCourseFinderResponse,
  PublicStudentAuthResponse,
  PublicPortalResponse,
  PublicPortalSessionsResponse,
  SignupPayload,
  SignupResponse,
  StudentAccessSummary,
  WorkspaceListResponse,
  WorkspaceCourseJoinResponse,
  WorkspaceOfficeDefinition,
} from "../types";

export const fetchCourses = async (locale: Locale): Promise<CourseSummary[]> => {
  const response = await apiClient.get<{ results: CourseSummary[] }>("/public/courses/", {
    params: { lang: locale === "de" ? "de" : "en" }
  });
  return response.data.results;
};

export const fetchCourseBySlug = async (slug: string, locale: Locale): Promise<CourseDetail> => {
  const response = await apiClient.get<CourseDetail>(`/public/courses/${slug}/`, {
    params: { lang: locale === "de" ? "de" : "en" }
  });
  return response.data;
};

export const fetchPublicWorkspaces = async (): Promise<WorkspaceListResponse["results"]> => {
  const response = await apiClient.get<WorkspaceListResponse>("/public/workspaces/");
  return response.data.results;
};

export const fetchPublicWorkspaceBySlug = async (slug: string): Promise<WorkspaceOfficeDefinition> => {
  const response = await apiClient.get<WorkspaceOfficeDefinition>(`/public/workspaces/${slug}/`);
  return response.data;
};

export const askPublicCourseFinder = async (query: string): Promise<PublicCourseFinderResponse> => {
  const response = await apiClient.post<PublicCourseFinderResponse>("/public/course-finder/ask/", { query });
  return response.data;
};

export const createAnnaSpeech = async (payload: {
  language: "de-DE" | "ru-RU" | "uk-UA";
  text: string;
}): Promise<Blob> => {
  const response = await apiClient.post("/public/anna/tts/", payload, {
    responseType: "blob",
    headers: {
      Accept: "audio/mpeg, audio/wav, audio/*, */*",
    },
  });
  return response.data;
};

export type AnnaLiveSession = {
  audio: {
    inputSampleRateHz: number;
    outputSampleRateHz: number;
  };
  clientSecret: string;
  initialMessage: unknown;
  model: string;
  provider: "gemini-live";
  voice: string;
  websocketUrl: string;
};

export const createAnnaLiveSession = async (payload: {
  language: "de-DE" | "ru-RU" | "uk-UA";
  lessonTitle?: string;
  level: string;
  voice?: string;
}): Promise<AnnaLiveSession> => {
  const response = await apiClient.post<AnnaLiveSession>("/public/anna/live/session/", payload);
  return response.data;
};

export const loginPublicStudent = async (
  identifier: string,
  password: string,
): Promise<PublicStudentAuthResponse> => {
  const response = await apiClient.post<PublicStudentAuthResponse>("/public/auth/login/", { identifier, password });
  return response.data;
};

export const loginPublicStudentWithGoogle = async (credential: string): Promise<PublicStudentAuthResponse> => {
  const response = await apiClient.post<PublicStudentAuthResponse>("/public/auth/google/login/", { credential });
  return response.data;
};

export const fetchStudentAccessSummary = async (): Promise<StudentAccessSummary> => {
  try {
    const response = await apiClient.get<{
      hasAccessibleEnrollments: boolean;
      dashboardUrl: string | null;
      summary: {
        totalEnrollments: number;
        accessibleEnrollments: number;
        accessibleCourses: number;
      };
    }>("/student/access/");
    return {
      isAuthenticated: true,
      hasEnrollments: response.data.hasAccessibleEnrollments,
      enrollmentsCount: response.data.summary.accessibleEnrollments,
      dashboardUrl: "/student/dashboard",
    };
  } catch (error) {
    if (isAxiosError(error) && error.response?.status === 404) {
      const response = await apiClient.get<{ enrollments?: unknown[] }>("/student/dashboard/");
      const enrollmentsCount = Array.isArray(response.data.enrollments) ? response.data.enrollments.length : 0;
      return {
        isAuthenticated: true,
        hasEnrollments: enrollmentsCount > 0,
        enrollmentsCount,
        dashboardUrl: "/student/dashboard",
      };
    }
    throw error;
  }
};

export const joinWorkspaceCourse = async (itemId: number): Promise<WorkspaceCourseJoinResponse> => {
  const response = await apiClient.post<WorkspaceCourseJoinResponse>(`/student/workspace-course-items/${itemId}/join/`);
  return response.data;
};

export const createTrialSignup = async (payload: SignupPayload): Promise<SignupResponse> => {
  const response = await apiClient.post<SignupResponse>("/public/trial-signup/", payload);
  return response.data;
};

export const createMockCheckout = async (payload: CheckoutPayload): Promise<SignupResponse> => {
  const response = await apiClient.post<SignupResponse>("/public/checkout/mock/", payload);
  return response.data;
};

export const createCheckoutStart = async (payload: CheckoutPayload): Promise<CheckoutStartResponse> => {
  const response = await apiClient.post<CheckoutStartResponse>("/public/checkout/start/", payload);
  return response.data;
};

export const createGoogleCheckout = async (payload: GoogleCheckoutPayload): Promise<GoogleCheckoutResponse> => {
  const response = await apiClient.post<GoogleCheckoutResponse>("/public/auth/google/checkout/", payload);
  return response.data;
};

export const getCheckoutStatus = async (orderId: number, checkoutToken: string): Promise<CheckoutStatusResponse> => {
  const response = await apiClient.get<CheckoutStatusResponse>(`/public/checkout/status/${orderId}/`, {
    params: {
      token: checkoutToken,
    },
  });
  return response.data;
};

export const createFeedback = async (payload: {
  course_slug?: string;
  full_name: string;
  email: string;
  subject: string;
  message: string;
  preferred_language: Locale;
  source_page?: string;
}): Promise<{ id: number; emailSent: boolean }> => {
  const response = await apiClient.post<{ id: number; emailSent: boolean }>("/public/feedback/", payload);
  return response.data;
};

export const requestMagicLink = async (payload: MagicLinkRequestPayload): Promise<MagicLinkRequestResponse> => {
  const response = await apiClient.post<MagicLinkRequestResponse>("/public/magic-link/request/", payload);
  return response.data;
};

export const fetchPublicPortal = async (token: string): Promise<PublicPortalResponse> => {
  const response = await apiClient.get<PublicPortalResponse>("/public/portal/", {
    params: { token },
  });
  return response.data;
};

export const fetchPublicPortalSessions = async (token: string): Promise<PublicPortalSessionsResponse> => {
  const response = await apiClient.get<PublicPortalSessionsResponse>("/public/portal/sessions/", {
    params: { token },
  });
  return response.data;
};

export const buildPublicPortalCalendarUrl = (token: string): string => {
  const base = (import.meta.env.VITE_ONLINE_API_BASE_URL ?? "http://localhost:1212/api/online").replace(/\/+$/, "");
  return `${base}/public/portal/calendar.ics/?token=${encodeURIComponent(token)}`;
};


