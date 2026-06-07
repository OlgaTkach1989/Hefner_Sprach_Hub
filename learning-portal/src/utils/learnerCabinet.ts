import { isAxiosError } from "axios"

import { clearTokens } from "../api/authStorage"
import { fetchStudentAccessSummary } from "../api/onlineApi"

export type LearnerCabinetResolution =
  | { kind: "sign_in"; url: string }
  | { kind: "dashboard"; url: string }
  | { kind: "blocked"; message: string }

const DEFAULT_SIGN_IN_URL = "/"
const DEFAULT_DASHBOARD_URL = "/student/dashboard"
const DEFAULT_BLOCKED_MESSAGE =
  "To open your learner dashboard, you need to order at least one course."

export const resolveLearnerCabinetAccess = async (): Promise<LearnerCabinetResolution> => {
  try {
    const summary = await fetchStudentAccessSummary()
    if (summary.hasEnrollments) {
      return {
        kind: "dashboard",
        url: summary.dashboardUrl || DEFAULT_DASHBOARD_URL,
      }
    }

    return {
      kind: "blocked",
      message: DEFAULT_BLOCKED_MESSAGE,
    }
  } catch (error) {
    if (isAxiosError(error) && [401, 403].includes(error.response?.status ?? 0)) {
      clearTokens()
      return { kind: "sign_in", url: DEFAULT_SIGN_IN_URL }
    }
    throw error
  }
}
