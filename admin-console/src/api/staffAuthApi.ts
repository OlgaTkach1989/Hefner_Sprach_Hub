import { apiClient } from "./client";
import type { StaffLoginResponse, StaffProfile } from "../types/auth";

export const loginAdmin = async (identifier: string, password: string): Promise<StaffLoginResponse> => {
  const response = await apiClient.post<StaffLoginResponse>("/online/staff/auth/login/", {
    identifier,
    password,
    role: "admin"
  });
  return response.data;
};

export const fetchAdminMe = async (): Promise<StaffProfile> => {
  const response = await apiClient.get<StaffProfile>("/online/staff/auth/me/");
  return response.data;
};

export const logoutAdminSession = async (): Promise<void> => {
  await apiClient.post("/online/staff/auth/logout/", {});
};
