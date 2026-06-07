import { useCallback, useEffect, useMemo } from "react";
import { useSearchParams } from "react-router-dom";

import { useGetOnlineCoursesQuery } from "@/bll/online/online.service";

const parseCourseId = (value: string | null): number | null => {
  if (!value) return null;
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
};

export const useAdminCourseScope = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const {
    data: courseListData,
    isLoading: isCoursesLoading,
    isError: isCoursesError,
  } = useGetOnlineCoursesQuery();

  const courses = useMemo(() => courseListData?.results ?? [], [courseListData]);
  const requestedCourseId = useMemo(() => parseCourseId(searchParams.get("courseId")), [searchParams]);
  const selectedCourseId = useMemo(() => {
    if (courses.length === 0) {
      return requestedCourseId;
    }
    if (requestedCourseId && courses.some((item) => item.id === requestedCourseId)) {
      return requestedCourseId;
    }
    return courses[0].id;
  }, [courses, requestedCourseId]);

  useEffect(() => {
    if (isCoursesLoading) {
      return;
    }

    const currentQueryValue = parseCourseId(searchParams.get("courseId"));
    if (currentQueryValue === selectedCourseId) {
      return;
    }
    const nextParams = new URLSearchParams(searchParams);
    if (selectedCourseId) {
      nextParams.set("courseId", String(selectedCourseId));
    } else {
      nextParams.delete("courseId");
    }
    setSearchParams(nextParams, { replace: true });
  }, [isCoursesLoading, searchParams, selectedCourseId, setSearchParams]);

  const selectedCourse = useMemo(
    () => courses.find((item) => item.id === selectedCourseId) ?? null,
    [courses, selectedCourseId],
  );

  const setSelectedCourseId = useCallback(
    (value: number | null) => {
      const nextParams = new URLSearchParams(searchParams);
      if (value) {
        nextParams.set("courseId", String(value));
      } else {
        nextParams.delete("courseId");
      }
      setSearchParams(nextParams, { replace: true });
    },
    [searchParams, setSearchParams],
  );

  return {
    courses,
    selectedCourseId,
    selectedCourse,
    isCoursesLoading,
    isCoursesError,
    setSelectedCourseId,
  };
};
