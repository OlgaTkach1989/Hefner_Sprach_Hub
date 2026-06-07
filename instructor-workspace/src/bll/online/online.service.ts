import { baseApi } from "@/bll/base-api";
import type {
  TeacherAttendanceSyncResponse,
  TeacherOnlineCohortCalendar,
  TeacherOnlineCohortListResponse,
  TeacherSessionActionResponse,
} from "@/bll/online/online.type";

export const onlineService = baseApi.injectEndpoints({
  endpoints: (builder) => ({
    getTeacherOnlineCohorts: builder.query<TeacherOnlineCohortListResponse, string | void>({
      query: (queryText) => ({
        url: "/online/teacher/cohorts/",
        method: "GET",
        params: queryText ? { q: queryText } : undefined
      })
    }),
    getTeacherOnlineCohortCalendar: builder.query<TeacherOnlineCohortCalendar, { cohortId: number; student?: string }>({
      query: ({ cohortId, student }) => ({
        url: `/online/teacher/cohorts/${cohortId}/calendar/`,
        method: "GET",
        params: student ? { student } : undefined
      })
    }),
    openTeacherSession: builder.mutation<TeacherSessionActionResponse, number>({
      query: (sessionId) => ({
        url: `/online/teacher/sessions/${sessionId}/open/`,
        method: "POST",
      }),
    }),
    endTeacherSession: builder.mutation<TeacherSessionActionResponse, number>({
      query: (sessionId) => ({
        url: `/online/teacher/sessions/${sessionId}/end/`,
        method: "POST",
      }),
    }),
    syncTeacherSessionAttendance: builder.mutation<TeacherAttendanceSyncResponse, number>({
      query: (sessionId) => ({
        url: `/online/teacher/sessions/${sessionId}/attendance/sync/`,
        method: "POST",
      }),
    })
  })
});

export const {
  useGetTeacherOnlineCohortsQuery,
  useGetTeacherOnlineCohortCalendarQuery,
  useEndTeacherSessionMutation,
  useOpenTeacherSessionMutation,
  useSyncTeacherSessionAttendanceMutation,
} = onlineService;
