import { apiClient } from "./client";
import type { StaffLoginResponse, StaffProfile } from "../types/auth";

export const loginTeacher = async (identifier: string, password: string): Promise<StaffLoginResponse> => {
  const response = await apiClient.post<StaffLoginResponse>("/staff/auth/login/", {
    identifier,
    password,
    role: "teacher"
  });
  return response.data;
};

export const fetchTeacherMe = async (): Promise<StaffProfile> => {
  const response = await apiClient.get<StaffProfile>("/staff/auth/me/");
  return response.data;
};

export const logoutTeacherSession = async (): Promise<void> => {
  await apiClient.post("/staff/auth/logout/", {});
};
