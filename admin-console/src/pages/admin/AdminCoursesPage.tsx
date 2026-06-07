import { useDeferredValue, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import {
  useCreateOnlineAdminExternalProviderMutation,
  useCreateOnlineAdminLearningProgramMutation,
  useDeleteOnlineAdminExternalProviderMutation,
  useDeleteOnlineAdminLearningProgramMutation,
  useGetOnlineAdminExternalProvidersQuery,
  useGetOnlineAdminLearningProgramsQuery,
  useGetOnlineAdminSessionsQuery,
  useGetOnlineCohortDetailQuery,
  useGetOnlineCourseDetailQuery,
  useGetOnlineCoursesQuery,
  useRunOnlineAdminSessionBulkActionMutation,
  useSearchOnlineAdminCatalogQuery,
  useUpdateOnlineAdminExternalProviderMutation,
  useUpdateOnlineAdminLearningProgramMutation,
} from "@/bll/online/online.service";
import type {
  OnlineAdminExternalCatalogProviderWriteInput,
  OnlineAdminLearningProgramWriteInput,
  OnlineAdminSessionBulkAction,
  OnlineAdminSessionRow,
  OnlineCourseAudience,
  OnlineCourseCard,
  OnlineSessionStatus,
} from "@/bll/online/online.type";
import type { CourseBuilderCourse } from "@/bll/course-builder/courseBuilder.type";
import { pocHighlights, pocProgramCourses, pocRuntimePreset } from "../../data/pocProgram";
import AdminCourseBuilderModal from "./course-builder/AdminCourseBuilderModal";
import shared from "./AdminPagesShared.module.css";
import styles from "./AdminCoursesPage.module.css";
import {
  courseDisplayDescription,
  courseDisplayTitle,
  formatDateTime,
  formatLifecycleLabel,
  formatPercent,
  formatRelativeHealth,
  lifecycleBadgeTone,
  sumValues,
} from "./adminPageUtils";

type CohortStatusFilter = "all" | "draft" | "open" | "running" | "finished";
type SessionStatusFilter = "all" | OnlineSessionStatus;
type SessionAttendanceSyncFilter = "all" | "synced" | "pending";
type SessionPresenceFilter = "all" | "present" | "missing";
type SessionAction = OnlineAdminSessionBulkAction;

const parsePositiveInteger = (value: string | null): number | null => {
  if (!value) return null;
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
};

const errorMessageFrom = (error: unknown, fallback: string) => {
  if (!error || typeof error !== "object" || !("data" in error)) return fallback;
  const payload = (error as { data?: unknown }).data;
  if (!payload || typeof payload !== "object") return fallback;
  const objectPayload = payload as Record<string, unknown>;
  if (typeof objectPayload.detail === "string") return objectPayload.detail;
  if (typeof objectPayload.status === "string") return objectPayload.status;
  for (const value of Object.values(objectPayload)) {
    if (typeof value === "string") return value;
    if (Array.isArray(value) && typeof value[0] === "string") return value[0];
  }
  return fallback;
};

const sessionActionLabel: Record<SessionAction, string> = {
  open: "Open",
  end: "End",
  sync: "Sync",
};

const sessionActionProgressLabel: Record<SessionAction, string> = {
  open: "Opening",
  end: "Ending",
  sync: "Syncing",
};

const isActionableSession = (action: SessionAction, session: OnlineAdminSessionRow) => {
  if (action === "open") return session.status === "scheduled";
  if (action === "end") return session.status === "live";
  return true;
};

const sessionStatusLabel = (status: OnlineSessionStatus) => {
  switch (status) {
    case "scheduled":
      return "Scheduled";
    case "live":
      return "Live";
    case "ended":
      return "Ended";
    case "canceled":
      return "Canceled";
    default:
      return status;
  }
};

const cohortStatusLabel = (status: string) => {
  if (!status) return "Unknown";
  return status.charAt(0).toUpperCase() + status.slice(1);
};

const cohortStatusBadgeClass = (status: string, sharedStyles: typeof shared) => {
  if (status === "running") return sharedStyles.goodPill;
  if (status === "finished") return sharedStyles.neutralPill;
  if (status === "draft") return sharedStyles.warnPill;
  return sharedStyles.linkPill;
};

const sessionStatusBadgeClass = (status: OnlineSessionStatus, sharedStyles: typeof shared) => {
  if (status === "live") return sharedStyles.goodPill;
  if (status === "canceled") return sharedStyles.warnPill;
  return sharedStyles.neutralPill;
};

const slugify = (value: string) =>
  value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");

const lifecycleBadgeClass = (status: OnlineCourseCard["lifecycleStatus"], sharedStyles: typeof shared) => {
  const tone = lifecycleBadgeTone(status);
  if (tone === "good") return sharedStyles.goodPill;
  if (tone === "link") return sharedStyles.linkPill;
  if (tone === "neutral") return sharedStyles.neutralPill;
  return sharedStyles.warnPill;
};

const formatCoursePrice = (course: Pick<OnlineCourseCard, "priceAmount" | "currency"> | null) => {
  if (!course) return "-";
  const numericValue = Number(course.priceAmount);
  if (Number.isNaN(numericValue)) {
    return `${course.priceAmount} ${course.currency}`.trim();
  }
  return `${numericValue.toFixed(2)} ${course.currency}`.trim();
};

const courseAudiencePillClass = (slug: string) => {
  if (slug === "external-users") return styles.rolePillGuest;
  if (slug === "interns-new-grads") return styles.rolePillStudent;
  if (slug === "lateral-transfers") return styles.rolePillInstructor;
  return styles.rolePillAdmin;
};

const renderCourseAudiencePills = (audiences?: OnlineCourseAudience[]) => {
  if (!audiences?.length) return null;
  return (
    <div className={styles.rolePillRow}>
      {audiences.map((audience) => (
        <span
          key={audience.id}
          className={`${styles.rolePill} ${courseAudiencePillClass(audience.slug)}`}
        >
          {audience.shortLabel || audience.name}
        </span>
      ))}
    </div>
  );
};

const AdminCoursesPage = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [isCourseBuilderOpen, setIsCourseBuilderOpen] = useState(false);
  const [courseBuilderMode, setCourseBuilderMode] = useState<"create" | "edit">("edit");
  const [courseBuilderCourseId, setCourseBuilderCourseId] = useState<number | null>(null);
  const [courseBuilderInitialStep, setCourseBuilderInitialStep] = useState<"template" | "basics">("basics");
  const [courseQuery, setCourseQuery] = useState(() => searchParams.get("q") ?? "");
  const [cohortQuery, setCohortQuery] = useState("");
  const [sessionQuery, setSessionQuery] = useState("");
  const [cohortStatusFilter, setCohortStatusFilter] = useState<CohortStatusFilter>("all");
  const [sessionStatusFilter, setSessionStatusFilter] = useState<SessionStatusFilter>("all");
  const [sessionAttendanceSyncFilter, setSessionAttendanceSyncFilter] =
    useState<SessionAttendanceSyncFilter>("all");
  const [sessionJoinLinkFilter, setSessionJoinLinkFilter] = useState<SessionPresenceFilter>("all");
  const [sessionRecordingFilter, setSessionRecordingFilter] = useState<SessionPresenceFilter>("all");
  const [selectedCourseId, setSelectedCourseId] = useState<number | null>(() =>
    parsePositiveInteger(searchParams.get("courseId"))
  );
  const [selectedCohortId, setSelectedCohortId] = useState<number | null>(() =>
    parsePositiveInteger(searchParams.get("cohortId"))
  );
  const [selectedSessionIds, setSelectedSessionIds] = useState<number[]>([]);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [pendingAction, setPendingAction] = useState<SessionAction | null>(null);
  const [catalogSearchQuery, setCatalogSearchQuery] = useState("");
  const [catalogProviderFilter, setCatalogProviderFilter] = useState<OnlineCourseCard["providerType"] | "">("");
  const [catalogDomainFilter, setCatalogDomainFilter] = useState("");
  const [selectedProviderId, setSelectedProviderId] = useState<number | null>(null);
  const [providerForm, setProviderForm] = useState<OnlineAdminExternalCatalogProviderWriteInput>({
    slug: "",
    displayName: "",
    providerType: "custom",
    importMode: "manual",
    baseUrl: "",
    apiBaseUrl: "",
    verificationMessage: "",
    isEnabled: false,
    syncStatus: "draft",
  });
  const [providerMessage, setProviderMessage] = useState<string | null>(null);
  const [providerError, setProviderError] = useState<string | null>(null);
  const [selectedProgramId, setSelectedProgramId] = useState<number | null>(null);
  const [programForm, setProgramForm] = useState<{
    slug: string;
    title: string;
    description: string;
    targetAudience: string;
    assignmentMode: OnlineAdminLearningProgramWriteInput["assignmentMode"];
    recommendationPrompt: string;
    isActive: boolean;
    courseIds: number[];
  }>({
    slug: "",
    title: "",
    description: "",
    targetAudience: "",
    assignmentMode: "hybrid",
    recommendationPrompt: "",
    isActive: true,
    courseIds: [],
  });
  const [programMessage, setProgramMessage] = useState<string | null>(null);
  const [programError, setProgramError] = useState<string | null>(null);

  const deferredCourseQuery = useDeferredValue(courseQuery.trim());
  const deferredCohortQuery = useDeferredValue(cohortQuery.trim().toLowerCase());
  const deferredSessionQuery = useDeferredValue(sessionQuery.trim().toLowerCase());
  const deferredCatalogSearchQuery = useDeferredValue(catalogSearchQuery.trim());

  const {
    data: courseListData,
    isLoading: isCourseListLoading,
    isError: isCourseListError,
    refetch: refetchCourseList,
  } = useGetOnlineCoursesQuery(deferredCourseQuery || undefined);
  const {
    data: catalogSearchData,
    isLoading: isCatalogSearchLoading,
  } = useSearchOnlineAdminCatalogQuery(
    deferredCatalogSearchQuery || catalogProviderFilter || catalogDomainFilter
      ? {
          q: deferredCatalogSearchQuery || undefined,
          providerType: catalogProviderFilter || undefined,
          knowledgeDomain: catalogDomainFilter || undefined,
        }
      : undefined,
  );
  const courseCards = useMemo(() => courseListData?.results ?? [], [courseListData]);
  const { data: externalProvidersData } = useGetOnlineAdminExternalProvidersQuery();
  const { data: learningProgramsData } = useGetOnlineAdminLearningProgramsQuery();
  const [createExternalProvider, createExternalProviderState] = useCreateOnlineAdminExternalProviderMutation();
  const [updateExternalProvider, updateExternalProviderState] = useUpdateOnlineAdminExternalProviderMutation();
  const [deleteExternalProvider, deleteExternalProviderState] = useDeleteOnlineAdminExternalProviderMutation();
  const [createLearningProgram, createLearningProgramState] = useCreateOnlineAdminLearningProgramMutation();
  const [updateLearningProgram, updateLearningProgramState] = useUpdateOnlineAdminLearningProgramMutation();
  const [deleteLearningProgram, deleteLearningProgramState] = useDeleteOnlineAdminLearningProgramMutation();
  const externalProviders = useMemo(() => externalProvidersData?.results ?? [], [externalProvidersData]);
  const learningPrograms = useMemo(() => learningProgramsData?.results ?? [], [learningProgramsData]);

  useEffect(() => {
    if (isCourseListLoading) return;
    if (courseCards.length === 0) {
      if (selectedCourseId !== null) {
        setSelectedCourseId(null);
      }
      return;
    }
    if (!selectedCourseId || !courseCards.some((course) => course.id === selectedCourseId)) {
      setSelectedCourseId(courseCards[0].id);
    }
  }, [courseCards, isCourseListLoading, selectedCourseId]);

  const selectedCourseCard = useMemo(
    () => courseCards.find((course) => course.id === selectedCourseId) ?? null,
    [courseCards, selectedCourseId],
  );

  const {
    data: selectedCourseDetail,
    isLoading: isCourseDetailLoading,
    isError: isCourseDetailError,
    refetch: refetchCourseDetail,
  } = useGetOnlineCourseDetailQuery(selectedCourseId as number, { skip: !selectedCourseId });

  const cohorts = useMemo(() => selectedCourseDetail?.cohorts ?? [], [selectedCourseDetail]);

  useEffect(() => {
    if (cohorts.length === 0) {
      if (selectedCohortId !== null) {
        setSelectedCohortId(null);
      }
      return;
    }
    if (!selectedCohortId || !cohorts.some((cohort) => cohort.id === selectedCohortId)) {
      setSelectedCohortId(cohorts[0].id);
    }
  }, [cohorts, selectedCohortId]);

  const {
    data: selectedCohortDetail,
    isLoading: isCohortDetailLoading,
    isError: isCohortDetailError,
    refetch: refetchCohortDetail,
  } = useGetOnlineCohortDetailQuery(selectedCohortId as number, { skip: !selectedCohortId });

  const sessionQueryArgs = useMemo(() => {
    if (!selectedCourseId || !selectedCohortId) return undefined;
    return {
      courseId: selectedCourseId,
      cohortId: selectedCohortId,
      q: deferredSessionQuery || undefined,
      status: sessionStatusFilter !== "all" ? sessionStatusFilter : undefined,
      attendanceSynced:
        sessionAttendanceSyncFilter === "all" ? undefined : sessionAttendanceSyncFilter === "synced",
      hasJoinUrl: sessionJoinLinkFilter === "all" ? undefined : sessionJoinLinkFilter === "present",
      hasRecording: sessionRecordingFilter === "all" ? undefined : sessionRecordingFilter === "present",
    };
  }, [
    deferredSessionQuery,
    selectedCohortId,
    selectedCourseId,
    sessionAttendanceSyncFilter,
    sessionJoinLinkFilter,
    sessionRecordingFilter,
    sessionStatusFilter,
  ]);
  const {
    data: sessionListData,
    isLoading: isSessionsLoading,
    isError: isSessionsError,
    refetch: refetchSessionList,
  } = useGetOnlineAdminSessionsQuery(sessionQueryArgs, { skip: !sessionQueryArgs });

  const [runBulkSessionAction] = useRunOnlineAdminSessionBulkActionMutation();

  const openCreateCourseBuilder = () => {
    setCourseBuilderMode("create");
    setCourseBuilderCourseId(null);
    setCourseBuilderInitialStep("basics");
    setIsCourseBuilderOpen(true);
  };

  const openTemplateCourseBuilder = () => {
    setCourseBuilderMode("create");
    setCourseBuilderCourseId(null);
    setCourseBuilderInitialStep("template");
    setIsCourseBuilderOpen(true);
  };

  const openEditCourseBuilder = () => {
    if (!selectedCourseId) return;
    setCourseBuilderMode("edit");
    setCourseBuilderCourseId(selectedCourseId);
    setCourseBuilderInitialStep("basics");
    setIsCourseBuilderOpen(true);
  };

  const handleCourseBuilderSaved = (savedCourse: CourseBuilderCourse) => {
    if (savedCourse.id) {
      setSelectedCourseId(savedCourse.id);
    }
    void refetchCourseList();
    void refetchCourseDetail();
  };

  useEffect(() => {
    const nextParams = new URLSearchParams(searchParams);
    const trimmedQuery = courseQuery.trim();
    if (trimmedQuery) {
      nextParams.set("q", trimmedQuery);
    } else {
      nextParams.delete("q");
    }
    if (selectedCourseId) {
      nextParams.set("courseId", String(selectedCourseId));
    } else {
      nextParams.delete("courseId");
    }
    if (selectedCohortId) {
      nextParams.set("cohortId", String(selectedCohortId));
    } else {
      nextParams.delete("cohortId");
    }
    if (nextParams.toString() !== searchParams.toString()) {
      setSearchParams(nextParams, { replace: true });
    }
  }, [courseQuery, searchParams, selectedCourseId, selectedCohortId, setSearchParams]);

  const filteredCohorts = useMemo(() => {
    return cohorts.filter((cohort) => {
      if (cohortStatusFilter !== "all" && cohort.status !== cohortStatusFilter) {
        return false;
      }
      if (!deferredCohortQuery) return true;
      return [
        cohort.groupCode,
        cohort.groupName,
        cohort.teacherName,
        cohort.courseTitleDe,
        cohort.courseTitleEn,
      ]
        .join(" ")
        .toLowerCase()
        .includes(deferredCohortQuery);
    });
  }, [cohortStatusFilter, cohorts, deferredCohortQuery]);

  const filteredSessions = useMemo(() => sessionListData?.results ?? [], [sessionListData]);

  useEffect(() => {
    const availableIds = new Set(filteredSessions.map((session) => session.id));
    setSelectedSessionIds((current) => current.filter((sessionId) => availableIds.has(sessionId)));
  }, [filteredSessions]);

  const selectedSessions = useMemo(() => {
    const sessionMap = new Map(filteredSessions.map((session) => [session.id, session]));
    return selectedSessionIds
      .map((sessionId) => sessionMap.get(sessionId))
      .filter((session): session is OnlineAdminSessionRow => Boolean(session));
  }, [filteredSessions, selectedSessionIds]);

  const academySummary = useMemo(() => {
    if (courseCards.length === 0) {
      return {
        students: 0,
        sessions: 0,
        publicCohorts: 0,
        attendance: null as number | null,
      };
    }
    return {
      students: sumValues(courseCards.map((course) => course.studentsCount)),
      sessions: sumValues(courseCards.map((course) => course.sessionsSummary.total)),
      publicCohorts: sumValues(courseCards.map((course) => course.publicCohortsCount)),
      attendance: sumValues(courseCards.map((course) => course.attendancePercent)) / courseCards.length,
    };
  }, [courseCards]);
  const pocCourseCount = pocProgramCourses.length;
  const pocModuleCount = sumValues(pocProgramCourses.map((course) => course.modules.length));
  const pocStepCount = pocProgramCourses.reduce(
    (courseTotal, course) =>
      courseTotal + course.modules.reduce((moduleTotal, module) => moduleTotal + module.steps.length, 0),
    0,
  );

  const selectedCourseMetrics = useMemo(() => {
    if (!selectedCourseCard) {
      return {
        teachers: "Not assigned",
        description: "Select a course to inspect cohorts, session health, and learner coverage.",
        cohortsTotal: 0,
        cohortsPublic: 0,
        cohortsRunning: 0,
        cohortsOpen: 0,
        cohortsFinished: 0,
        deliveryTotal: 0,
        deliveryLive: 0,
        deliveryCompleted: 0,
        deliveryCanceled: 0,
      };
    }

    return {
      teachers:
        selectedCourseDetail?.teachers?.length
          ? selectedCourseDetail.teachers.join(", ")
          : selectedCourseCard.teachers.length
            ? selectedCourseCard.teachers.join(", ")
            : "Not assigned",
      description: courseDisplayDescription(selectedCourseDetail),
      cohortsTotal: selectedCourseDetail?.cohortsSummary.total ?? selectedCourseCard.cohortsCount,
      cohortsPublic: selectedCourseDetail?.cohortsSummary.public ?? selectedCourseCard.publicCohortsCount,
      cohortsRunning: selectedCourseDetail?.cohortsSummary.running ?? 0,
      cohortsOpen: selectedCourseDetail?.cohortsSummary.open ?? 0,
      cohortsFinished: selectedCourseDetail?.cohortsSummary.finished ?? 0,
      deliveryTotal: selectedCourseDetail?.sessionsSummary.total ?? selectedCourseCard.sessionsSummary.total,
      deliveryLive: selectedCourseDetail?.sessionsSummary.live ?? selectedCourseCard.sessionsSummary.live,
      deliveryCompleted: selectedCourseDetail?.sessionsSummary.completed ?? selectedCourseCard.sessionsSummary.completed,
      deliveryCanceled: selectedCourseDetail?.sessionsSummary.canceled ?? selectedCourseCard.sessionsSummary.canceled,
    };
  }, [selectedCourseCard, selectedCourseDetail]);

  const selectedProvider = useMemo(
    () => externalProviders.find((provider) => provider.id === selectedProviderId) ?? null,
    [externalProviders, selectedProviderId],
  );
  const selectedProgram = useMemo(
    () => learningPrograms.find((program) => program.id === selectedProgramId) ?? null,
    [learningPrograms, selectedProgramId],
  );

  useEffect(() => {
    if (selectedProviderId !== null && !externalProviders.some((provider) => provider.id === selectedProviderId)) {
      setSelectedProviderId(null);
    }
    if (selectedProvider) {
      setProviderForm({
        slug: selectedProvider.slug,
        displayName: selectedProvider.displayName,
        providerType: selectedProvider.providerType,
        importMode: selectedProvider.importMode,
        baseUrl: selectedProvider.baseUrl,
        apiBaseUrl: selectedProvider.apiBaseUrl,
        verificationMessage: selectedProvider.verificationMessage,
        isEnabled: selectedProvider.isEnabled,
        syncStatus: selectedProvider.syncStatus,
      });
    }
    if (!selectedProvider && selectedProviderId === null) {
      setProviderForm({
        slug: "",
        displayName: "",
        providerType: "custom",
        importMode: "manual",
        baseUrl: "",
        apiBaseUrl: "",
        verificationMessage: "",
        isEnabled: false,
        syncStatus: "draft",
      });
    }
  }, [externalProviders, selectedProvider, selectedProviderId]);

  useEffect(() => {
    if (selectedProgramId !== null && !learningPrograms.some((program) => program.id === selectedProgramId)) {
      setSelectedProgramId(null);
    }
    if (selectedProgram) {
      setProgramForm({
        slug: selectedProgram.slug,
        title: selectedProgram.title,
        description: selectedProgram.description,
        targetAudience: selectedProgram.targetAudience,
        assignmentMode: selectedProgram.assignmentMode,
        recommendationPrompt: selectedProgram.recommendationPrompt,
        isActive: selectedProgram.isActive,
        courseIds: selectedProgram.programCourses.map((item) => item.courseId),
      });
    }
    if (!selectedProgram && selectedProgramId === null) {
      setProgramForm({
        slug: "",
        title: "",
        description: "",
        targetAudience: "",
        assignmentMode: "hybrid",
        recommendationPrompt: "",
        isActive: true,
        courseIds: selectedCourseId ? [selectedCourseId] : [],
      });
    }
  }, [learningPrograms, selectedCourseId, selectedProgram, selectedProgramId]);

  const courseTimeline = useMemo(() => (selectedCourseDetail?.sessions ?? []).slice(0, 8), [selectedCourseDetail]);

  const selectedCohortCard = useMemo(
    () => cohorts.find((cohort) => cohort.id === selectedCohortId) ?? null,
    [cohorts, selectedCohortId],
  );

  const selectedCohortSummary = useMemo(() => {
    if (!selectedCohortDetail) {
      return {
        students: 0,
        sessions: 0,
        completed: 0,
        scheduled: 0,
        live: 0,
        canceled: 0,
        riskStudents: 0,
      };
    }

    let scheduled = 0;
    let live = 0;
    let canceled = 0;
    selectedCohortDetail.sessions.forEach((session) => {
      if (session.status === "scheduled") scheduled += 1;
      if (session.status === "live") live += 1;
      if (session.status === "canceled") canceled += 1;
    });

    return {
      students: selectedCohortDetail.studentsCount,
      sessions: selectedCohortDetail.sessions.length,
      completed: selectedCohortDetail.sessionsSummary?.completed ?? 0,
      scheduled,
      live,
      canceled,
      riskStudents: selectedCohortDetail.students.filter((student) => student.attendancePercent < 60).length,
    };
  }, [selectedCohortDetail]);

  const riskLearners = useMemo(() => {
    if (!selectedCohortDetail) return [];
    return [...selectedCohortDetail.students]
      .sort((left, right) => left.attendancePercent - right.attendancePercent)
      .slice(0, 6);
  }, [selectedCohortDetail]);

  const sessionSelectionSummary = useMemo(() => {
    return {
      total: selectedSessions.length,
      openable: selectedSessions.filter((session) => isActionableSession("open", session)).length,
      endable: selectedSessions.filter((session) => isActionableSession("end", session)).length,
      syncable: selectedSessions.filter((session) => isActionableSession("sync", session)).length,
    };
  }, [selectedSessions]);

  const sessionOperationalSummary = useMemo(() => {
    return filteredSessions.reduce(
      (summary, session) => {
        if (session.attendanceSyncedAt) {
          summary.synced += 1;
        } else {
          summary.pendingSync += 1;
        }
        if (session.joinUrl) {
          summary.joinLinkReady += 1;
        } else {
          summary.joinLinkMissing += 1;
        }
        if (session.recordingUrl) {
          summary.recordingsReady += 1;
        } else {
          summary.recordingsMissing += 1;
        }
        return summary;
      },
      {
        synced: 0,
        pendingSync: 0,
        joinLinkReady: 0,
        joinLinkMissing: 0,
        recordingsReady: 0,
        recordingsMissing: 0,
      },
    );
  }, [filteredSessions]);

  const scopedQuery = selectedCourseId ? `?courseId=${selectedCourseId}` : "";

  const selectAllVisibleSessions = () => {
    setSelectedSessionIds(filteredSessions.map((session) => session.id));
    setActionMessage(null);
    setActionError(null);
  };

  const clearSelectedSessions = () => {
    setSelectedSessionIds([]);
    setActionMessage(null);
    setActionError(null);
  };

  const toggleSessionSelection = (sessionId: number) => {
    setSelectedSessionIds((current) =>
      current.includes(sessionId) ? current.filter((id) => id !== sessionId) : [...current, sessionId]
    );
    setActionMessage(null);
    setActionError(null);
  };

  const executeSessionAction = async (action: SessionAction, explicitIds?: number[]) => {
    if (!selectedCohortDetail) {
      setActionMessage(null);
      setActionError("Select a cohort before running session actions.");
      return;
    }

    const targetIds = explicitIds?.length ? explicitIds : selectedSessionIds;
    if (targetIds.length === 0) {
      setActionMessage(null);
      setActionError("Select at least one session first.");
      return;
    }

    const sessionMap = new Map(filteredSessions.map((session) => [session.id, session]));
    const actionableIds = targetIds.filter((sessionId) => {
      const session = sessionMap.get(sessionId);
      return session ? isActionableSession(action, session) : false;
    });
    const skippedCount = targetIds.length - actionableIds.length;

    if (actionableIds.length === 0) {
      const requirement =
        action === "open"
          ? "Only scheduled sessions can be opened."
          : action === "end"
            ? "Only live sessions can be ended."
            : "Select at least one valid session to sync.";
      setActionMessage(null);
      setActionError(requirement);
      return;
    }

    setPendingAction(action);
    setActionMessage(null);
    setActionError(null);
    let response:
      | {
          succeededCount: number;
          failedCount: number;
          results: Array<{ error: string | null; ok: boolean }>;
        }
      | undefined;
    try {
      response = await runBulkSessionAction({ action, sessionIds: actionableIds }).unwrap();
    } catch (error) {
      setPendingAction(null);
      setActionMessage(null);
      setActionError(errorMessageFrom(error, `Failed to ${action} the selected sessions.`));
      return;
    }

    const refreshPromises: Array<Promise<unknown>> = [refetchCourseList()];
    if (selectedCourseId) {
      refreshPromises.push(refetchCourseDetail());
    }
    if (selectedCohortId) {
      refreshPromises.push(refetchCohortDetail());
    }
    if (sessionQueryArgs) {
      refreshPromises.push(refetchSessionList());
    }
    await Promise.all(refreshPromises);

    if (!explicitIds) {
      setSelectedSessionIds([]);
    }

    if (response.succeededCount > 0 || skippedCount > 0) {
      const skippedText = skippedCount > 0 ? ` ${skippedCount} skipped by status.` : "";
      setActionMessage(
        `${sessionActionLabel[action]} completed for ${response.succeededCount} session(s).${skippedText}`
      );
    } else {
      setActionMessage(null);
    }

    const failures = response.results.filter((result) => !result.ok && result.error).map((result) => result.error as string);
    if (failures.length > 0) {
      const moreText = failures.length > 1 ? ` ${failures.length - 1} more issue(s) recorded.` : "";
      setActionError(`${failures[0]}${moreText}`);
    } else {
      setActionError(null);
    }

    setPendingAction(null);
  };

  const onSaveExternalProvider = async () => {
    const body = {
      slug: providerForm.slug || slugify(providerForm.displayName),
      displayName: providerForm.displayName.trim(),
      providerType: providerForm.providerType,
      importMode: providerForm.importMode,
      baseUrl: (providerForm.baseUrl ?? "").trim(),
      apiBaseUrl: (providerForm.apiBaseUrl ?? "").trim(),
      verificationMessage: (providerForm.verificationMessage ?? "").trim(),
      isEnabled: providerForm.isEnabled,
      syncStatus: providerForm.syncStatus,
      metadataSchema: {},
    };
    if (!body.displayName) {
      setProviderMessage(null);
      setProviderError("Provider name is required.");
      return;
    }
    setProviderMessage(null);
    setProviderError(null);
    try {
      if (selectedProvider) {
        await updateExternalProvider({ providerId: selectedProvider.id, body }).unwrap();
        setProviderMessage("External provider updated.");
      } else {
        const created = await createExternalProvider(body).unwrap();
        setSelectedProviderId(created.id);
        setProviderMessage("External provider created.");
      }
    } catch (error) {
      setProviderError(errorMessageFrom(error, "Failed to save the external provider."));
    }
  };

  const onDeleteExternalProvider = async () => {
    if (!selectedProvider) return;
    setProviderMessage(null);
    setProviderError(null);
    try {
      await deleteExternalProvider(selectedProvider.id).unwrap();
      setSelectedProviderId(null);
      setProviderMessage("External provider removed.");
    } catch (error) {
      setProviderError(errorMessageFrom(error, "Failed to remove the external provider."));
    }
  };

  const onSaveLearningProgram = async () => {
    const courseIds = Array.from(new Set(programForm.courseIds)).filter(Boolean);
    const programCourses: NonNullable<OnlineAdminLearningProgramWriteInput["programCourses"]> = courseIds.map((courseId, index) => ({
      courseId,
      sortOrder: index + 1,
      isRequired: true,
      unlockRule: index === 0 ? "immediate" : "after_previous",
      minCompletionPercent: 100,
    }));
    const body = {
      slug: programForm.slug || slugify(programForm.title),
      title: programForm.title.trim(),
      description: programForm.description.trim(),
      targetAudience: programForm.targetAudience.trim(),
      assignmentMode: programForm.assignmentMode,
      recommendationPrompt: programForm.recommendationPrompt.trim(),
      isActive: programForm.isActive,
      programCourses,
    };
    if (!body.title) {
      setProgramMessage(null);
      setProgramError("Program title is required.");
      return;
    }
    setProgramMessage(null);
    setProgramError(null);
    try {
      if (selectedProgram) {
        await updateLearningProgram({ programId: selectedProgram.id, body }).unwrap();
        setProgramMessage("Learning program updated.");
      } else {
        const created = await createLearningProgram(body).unwrap();
        setSelectedProgramId(created.id);
        setProgramMessage("Learning program created.");
      }
    } catch (error) {
      setProgramError(errorMessageFrom(error, "Failed to save the learning program."));
    }
  };

  const onDeleteLearningProgram = async () => {
    if (!selectedProgram) return;
    setProgramMessage(null);
    setProgramError(null);
    try {
      await deleteLearningProgram(selectedProgram.id).unwrap();
      setSelectedProgramId(null);
      setProgramMessage("Learning program removed.");
    } catch (error) {
      setProgramError(errorMessageFrom(error, "Failed to remove the learning program."));
    }
  };

  return (
    <div className={shared.page}>
      <section className={shared.hero}>
        <div className={shared.heroCopy}>
          <span className={shared.eyebrow}>Course delivery control</span>
          <h1>Courses, cohorts, and live session operations</h1>
          <p>
            Operate the catalog from a course-first workspace. Search the academy portfolio, inspect cohort delivery,
            and run live-session lifecycle actions without leaving the admin control plane.
          </p>
        </div>
        <div className={shared.toolbar}>
          <div className={shared.scopeControls}>
            <label className={shared.selectWrap}>
              <span className={shared.fieldLabel}>Search course, cohort, or teacher</span>
              <input
                className={shared.inlineInput}
                value={courseQuery}
                onChange={(event) => setCourseQuery(event.currentTarget.value)}
                placeholder="Search by title, slug, group code, or teacher"
              />
            </label>
          </div>
          <div className={shared.heroMeta}>
            <span>{courseCards.length} courses</span>
            <span>{academySummary.publicCohorts} public cohorts</span>
            <span>{academySummary.students} learners</span>
            <span>{formatPercent(academySummary.attendance)} average attendance</span>
          </div>

          <div className={styles.builderToolbar}>
            <div className={styles.builderToolbarCopy}>
              <strong>Course builder</strong>
              <p>Create modular courses from templates and manage lesson structure in a single-page studio.</p>
            </div>
            <div className={styles.builderButtonGroup}>
              <button type="button" className={styles.builderPrimaryButton} onClick={openCreateCourseBuilder}>
                Create course
              </button>
              <button type="button" className={styles.builderSecondaryButton} onClick={openTemplateCourseBuilder}>
                Create from template
              </button>
              <button
                type="button"
                className={styles.builderGhostButton}
                onClick={openEditCourseBuilder}
                disabled={!selectedCourseId}
              >
                Edit structure
              </button>
            </div>
          </div>
        </div>
      </section>

      {isCourseBuilderOpen ? (
        <div className={styles.builderInlineWrap}>
          <AdminCourseBuilderModal
            isOpen={isCourseBuilderOpen}
            inline
            mode={courseBuilderMode}
            courseId={courseBuilderCourseId}
            initialStep={courseBuilderInitialStep}
            onClose={() => setIsCourseBuilderOpen(false)}
            onSaved={handleCourseBuilderSaved}
          />
        </div>
      ) : null}

      {isCourseListLoading ? <p className={shared.emptyText}>Loading course catalog...</p> : null}
      {isCourseListError ? <p className={shared.errorText}>Failed to load the course catalog.</p> : null}

      <section className={styles.commandPanel}>
        <div className={styles.commandCopy}>
          <strong>POC structure preview</strong>
          <p>
            The seeded catalog now mirrors the programming demo rollout: two Python courses, guided lesson documents,
            interactive practice, and a final project / exam path that stays aligned across public, student, instructor,
            and admin surfaces.
          </p>
        </div>
        <div className={styles.commandStats}>
          <article className={styles.commandStat}>
            <span>Courses</span>
            <strong>{pocCourseCount}</strong>
          </article>
          <article className={styles.commandStat}>
            <span>Modules</span>
            <strong>{pocModuleCount}</strong>
          </article>
          <article className={styles.commandStat}>
            <span>Step nodes</span>
            <strong>{pocStepCount}</strong>
          </article>
          <article className={styles.commandStat}>
            <span>Runtime</span>
            <strong>{pocRuntimePreset.title}</strong>
          </article>
        </div>
        <div className={shared.heroMeta}>
          {pocHighlights.map((item) => (
            <span key={item}>{item}</span>
          ))}
        </div>
      </section>

      <section className={shared.kpiGrid}>
        <article className={shared.kpiCard}>
          <span className={shared.kpiLabel}>Selected course</span>
          <strong className={shared.kpiValue}>{selectedCourseCard ? courseDisplayTitle(selectedCourseCard, "-") : "-"}</strong>
          <span className={shared.kpiMeta}>
            {selectedCourseCard ? selectedCourseCard.slug : "Pick a course from the directory to focus delivery."}
          </span>
        </article>
        <article className={shared.kpiCard}>
          <span className={shared.kpiLabel}>Delivery sessions</span>
          <strong className={shared.kpiValue}>{selectedCourseMetrics.deliveryTotal}</strong>
          <span className={shared.kpiMeta}>
            {selectedCourseMetrics.deliveryLive} live · {selectedCourseMetrics.deliveryCompleted} completed ·{" "}
            {selectedCourseMetrics.deliveryCanceled} canceled
          </span>
        </article>
        <article className={shared.kpiCard}>
          <span className={shared.kpiLabel}>Cohort coverage</span>
          <strong className={shared.kpiValue}>{selectedCourseMetrics.cohortsTotal}</strong>
          <span className={shared.kpiMeta}>
            {selectedCourseMetrics.cohortsRunning} running · {selectedCourseMetrics.cohortsOpen} open ·{" "}
            {selectedCourseMetrics.cohortsFinished} finished
          </span>
        </article>
        <article className={shared.kpiCard}>
          <span className={shared.kpiLabel}>Learner health</span>
          <strong className={shared.kpiValue}>
            {formatRelativeHealth(selectedCourseCard?.attendancePercent ?? selectedCourseDetail?.attendancePercent)}
          </strong>
          <span className={shared.kpiMeta}>
            {formatPercent(selectedCourseCard?.attendancePercent ?? selectedCourseDetail?.attendancePercent)} attendance
            across the selected course scope
          </span>
        </article>
      </section>

      <div className={shared.grid2}>
        <section className={shared.panel}>
          <header className={shared.panelHeader}>
            <div>
              <h2>Course directory</h2>
              <p>Choose the course that should drive the cohort board and session operations below.</p>
            </div>
            <span className={shared.linkPill}>{courseCards.length} result(s)</span>
          </header>
          <div className={styles.directoryList}>
            {courseCards.length === 0 ? (
              <p className={shared.emptyText}>No courses match the current search query.</p>
            ) : null}
            {courseCards.map((course) => {
              const isActive = course.id === selectedCourseId;
              return (
                <button
                  key={course.id}
                  type="button"
                  className={`${styles.directoryItem} ${isActive ? styles.directoryItemActive : ""}`}
                  onClick={() => {
                    setSelectedCourseId(course.id);
                    setActionMessage(null);
                    setActionError(null);
                  }}
                >
                  <div className={styles.directoryHeader}>
                    <div className={shared.tableCellStack}>
                      <strong>{courseDisplayTitle(course)}</strong>
                      <span>{course.slug}</span>
                    </div>
                    <div className={styles.inlinePills}>
                      <span className={lifecycleBadgeClass(course.lifecycleStatus, shared)}>
                        {formatLifecycleLabel(course.lifecycleStatus)}
                      </span>
                      <span className={course.governance.readiness.requiredChecksPassed ? shared.neutralPill : shared.warnPill}>
                        {course.governance.readiness.requiredChecksPassed
                          ? "Release ready"
                          : `${course.governance.readiness.requiredFailedCount} gate${course.governance.readiness.requiredFailedCount === 1 ? "" : "s"} blocked`}
                      </span>
                      {course.governance.latestVersion ? (
                        <span className={shared.linkPill}>v{course.governance.latestVersion.versionNumber}</span>
                      ) : null}
                      <span className={course.trialAvailable ? shared.neutralPill : shared.linkPill}>
                        {course.trialAvailable ? "Trial on" : "Trial off"}
                      </span>
                    </div>
                  </div>
                  {renderCourseAudiencePills(course.audiences)}
                  <div className={styles.directoryMetrics}>
                    <span>{course.cohortsCount} cohorts</span>
                    <span>{course.studentsCount} learners</span>
                    <span>{formatPercent(course.attendancePercent)} attendance</span>
                    <span>{course.governance.versionsCount} version(s)</span>
                    <span>{formatDateTime(course.nearestSessionAt)}</span>
                  </div>
                </button>
              );
            })}
          </div>
        </section>

        <section className={shared.panel}>
          <header className={shared.panelHeader}>
            <div>
              <h2>Course command center</h2>
              <p>Selected course scope, delivery readiness, and direct handoff into governance and AI operations.</p>
            </div>
            <div className={styles.inlinePills}>
              <span className={shared.linkPill}>{selectedCourseMetrics.teachers}</span>
              <span className={shared.linkPill}>
                {selectedCourseMetrics.cohortsPublic} public cohort{selectedCourseMetrics.cohortsPublic === 1 ? "" : "s"}
              </span>
            </div>
          </header>

          {isCourseDetailLoading ? <p className={shared.emptyText}>Loading selected course details...</p> : null}
          {isCourseDetailError ? <p className={shared.errorText}>Failed to load selected course detail.</p> : null}

          <div className={styles.commandPanel}>
            <div className={styles.commandCopy}>
              <strong>{selectedCourseCard ? courseDisplayTitle(selectedCourseCard) : "No course selected"}</strong>
              {selectedCourseCard ? renderCourseAudiencePills(selectedCourseCard.audiences) : null}
              <p>{selectedCourseMetrics.description}</p>
            </div>
            <div className={styles.commandStats}>
              <div className={styles.commandStat}>
                <span>Price</span>
                <strong>{formatCoursePrice(selectedCourseCard)}</strong>
              </div>
              <div className={styles.commandStat}>
                <span>Nearest session</span>
                <strong>{formatDateTime(selectedCourseCard?.nearestSessionAt ?? selectedCourseDetail?.nearestSessionAt)}</strong>
              </div>
              <div className={styles.commandStat}>
                <span>Lessons</span>
                <strong>{selectedCourseCard?.lessonsCount ?? 0}</strong>
              </div>
              <div className={styles.commandStat}>
                <span>Attendance</span>
                <strong>{formatPercent(selectedCourseCard?.attendancePercent ?? selectedCourseDetail?.attendancePercent)}</strong>
              </div>
              <div className={styles.commandStat}>
                <span>Release</span>
                <strong>
                  {selectedCourseCard?.governance.readiness.requiredChecksPassed ? "Ready" : "Blocked"}
                </strong>
              </div>
            </div>
          </div>

          {selectedCourseCard ? (
            <div className={styles.summaryGrid}>
              <article className={styles.summaryCard}>
                <span>Release checks</span>
                <strong>
                  {selectedCourseCard.governance.readiness.requiredChecksPassed
                    ? "All required checks passed"
                    : `${selectedCourseCard.governance.readiness.requiredFailedCount} required check(s) open`}
                </strong>
                <small>{selectedCourseCard.governance.readiness.statusLabel}</small>
              </article>
              <article className={styles.summaryCard}>
                <span>Latest snapshot</span>
                <strong>
                  {selectedCourseCard.governance.latestVersion
                    ? `v${selectedCourseCard.governance.latestVersion.versionNumber}`
                    : "No version yet"}
                </strong>
                <small>
                  {selectedCourseCard.governance.latestVersion?.changeSummary || "Create or save the course to start version history."}
                </small>
              </article>
              <article className={styles.summaryCard}>
                <span>Approval history</span>
                <strong>{selectedCourseCard.governance.approvalsCount}</strong>
                <small>
                  {selectedCourseCard.governance.latestApproval
                    ? `${selectedCourseCard.governance.latestApproval.actionLabel} by ${selectedCourseCard.governance.latestApproval.actorEmail || "system"}`
                    : "No approval events yet"}
                </small>
              </article>
            </div>
          ) : null}

          <div className={shared.linkGrid}>
            <Link to={`/curators${scopedQuery}`} className={shared.quickLink}>
              <strong>Instructors</strong>
              <span>Assign delivery owners and balance cohort ownership for this course.</span>
            </Link>
            <Link to={`/governance${scopedQuery}`} className={shared.quickLink}>
              <strong>Governance</strong>
              <span>Review content completeness, entitlements, and practice readiness.</span>
            </Link>
            <Link to={`/knowledge${scopedQuery}`} className={shared.quickLink}>
              <strong>Knowledge &amp; AI</strong>
              <span>Inspect AI escalations, index freshness, and unresolved support pressure.</span>
            </Link>
            <Link to={`/reports${scopedQuery}`} className={shared.quickLink}>
              <strong>Reports &amp; logs</strong>
              <span>Open audit evidence, sync failures, and grader incidents for this course scope.</span>
            </Link>
          </div>
        </section>
      </div>

      <div className={shared.grid2}>
        <section className={shared.panel}>
          <header className={shared.panelHeader}>
            <div>
              <h2>Catalog search</h2>
              <p>Search across courses, students, instructors, programs, and knowledge documents from a single admin query.</p>
            </div>
            <span className={shared.linkPill}>
              {(catalogSearchData?.courses.length ?? 0) +
                (catalogSearchData?.students.length ?? 0) +
                (catalogSearchData?.instructors.length ?? 0) +
                (catalogSearchData?.programs.length ?? 0) +
                (catalogSearchData?.knowledgeDocuments.length ?? 0)} hit(s)
            </span>
          </header>
          <div className={styles.filterRow}>
            <label className={shared.selectWrap}>
              <span className={shared.fieldLabel}>Search query</span>
              <input className={shared.inlineInput} value={catalogSearchQuery} onChange={(event) => setCatalogSearchQuery(event.currentTarget.value)} placeholder="Course, student, author, program, transcript..." />
            </label>
            <label className={shared.selectWrap}>
              <span className={shared.fieldLabel}>Provider</span>
              <select className={shared.select} value={catalogProviderFilter} onChange={(event) => setCatalogProviderFilter(event.currentTarget.value as typeof catalogProviderFilter)}>
                <option value="">All providers</option>
                <option value="internal">Internal</option>
                <option value="linkedin_learning">LinkedIn Learning</option>
                <option value="coursera">Coursera</option>
                <option value="udemy_business">Udemy Business</option>
                <option value="external_custom">External custom</option>
              </select>
            </label>
            <label className={shared.selectWrap}>
              <span className={shared.fieldLabel}>Knowledge domain</span>
              <input className={shared.inlineInput} value={catalogDomainFilter} onChange={(event) => setCatalogDomainFilter(event.currentTarget.value)} placeholder="Python, risk, data..." />
            </label>
          </div>
          {isCatalogSearchLoading ? <p className={shared.emptyText}>Searching the admin catalog...</p> : null}
          <div className={styles.summaryGrid}>
            <article className={styles.summaryCard}>
              <span>Courses</span>
              <strong>{catalogSearchData?.courses.length ?? 0}</strong>
              <small>{catalogSearchData?.courses.slice(0, 3).map((item) => item.title).join(" · ") || "Search to inspect catalog courses."}</small>
            </article>
            <article className={styles.summaryCard}>
              <span>Students</span>
              <strong>{catalogSearchData?.students.length ?? 0}</strong>
              <small>{catalogSearchData?.students.slice(0, 2).map((item) => item.fullName).join(" · ") || "Student registry participates in the same search layer."}</small>
            </article>
            <article className={styles.summaryCard}>
              <span>Authors</span>
              <strong>{catalogSearchData?.instructors.length ?? 0}</strong>
              <small>{catalogSearchData?.instructors.slice(0, 2).map((item) => item.fullName).join(" · ") || "Instructor expertise is indexed for discovery."}</small>
            </article>
            <article className={styles.summaryCard}>
              <span>Programs / Knowledge</span>
              <strong>{(catalogSearchData?.programs.length ?? 0) + (catalogSearchData?.knowledgeDocuments.length ?? 0)}</strong>
              <small>Programs and KB documents are searchable alongside courses.</small>
            </article>
          </div>
        </section>

        <section className={shared.panel}>
          <header className={shared.panelHeader}>
            <div>
              <h2>External provider registry</h2>
              <p>Register LinkedIn, Coursera, Udemy Business, or custom external catalogs so third-party courses can enter the same metadata model and search index.</p>
            </div>
            <span className={shared.sectionHint}>{externalProviders.length} provider(s)</span>
          </header>
          <div className={styles.directoryList}>
            {externalProviders.map((provider) => (
              <button key={provider.id} type="button" className={`${styles.directoryItem} ${provider.id === selectedProviderId ? styles.directoryItemActive : ""}`} onClick={() => setSelectedProviderId(provider.id)}>
                <div className={styles.directoryHeader}>
                  <div className={shared.tableCellStack}>
                    <strong>{provider.displayName}</strong>
                    <span>{provider.providerType} · {provider.importMode}</span>
                  </div>
                  <span className={provider.isEnabled ? shared.goodPill : shared.warnPill}>{provider.syncStatus}</span>
                </div>
                <div className={styles.directoryMetrics}>
                  <span>{provider.baseUrl || "No base URL"}</span>
                  <span>{provider.lastSyncAt ? formatDateTime(provider.lastSyncAt) : "Never synced"}</span>
                </div>
              </button>
            ))}
          </div>
          <div className={styles.filterRow}>
            <label className={shared.selectWrap}>
              <span className={shared.fieldLabel}>Provider name</span>
              <input className={shared.inlineInput} value={providerForm.displayName} onChange={(event) => setProviderForm((current) => ({ ...current, displayName: event.currentTarget.value, slug: current.slug || slugify(event.currentTarget.value) }))} />
            </label>
            <label className={shared.selectWrap}>
              <span className={shared.fieldLabel}>Provider type</span>
              <select className={shared.select} value={providerForm.providerType} onChange={(event) => setProviderForm((current) => ({ ...current, providerType: event.currentTarget.value as typeof providerForm.providerType }))}>
                <option value="custom">Custom</option>
                <option value="linkedin_learning">LinkedIn Learning</option>
                <option value="coursera">Coursera</option>
                <option value="udemy_business">Udemy Business</option>
              </select>
            </label>
            <label className={shared.selectWrap}>
              <span className={shared.fieldLabel}>Import mode</span>
              <select className={shared.select} value={providerForm.importMode} onChange={(event) => setProviderForm((current) => ({ ...current, importMode: event.currentTarget.value as typeof providerForm.importMode }))}>
                <option value="manual">Manual</option>
                <option value="file">File</option>
                <option value="api">API</option>
              </select>
            </label>
          </div>
          <div className={styles.filterRow}>
            <label className={shared.selectWrap}>
              <span className={shared.fieldLabel}>Base URL</span>
              <input className={shared.inlineInput} value={providerForm.baseUrl} onChange={(event) => setProviderForm((current) => ({ ...current, baseUrl: event.currentTarget.value }))} />
            </label>
            <label className={shared.selectWrap}>
              <span className={shared.fieldLabel}>API base URL</span>
              <input className={shared.inlineInput} value={providerForm.apiBaseUrl} onChange={(event) => setProviderForm((current) => ({ ...current, apiBaseUrl: event.currentTarget.value }))} />
            </label>
            <label className={shared.selectWrap}>
              <span className={shared.fieldLabel}>Verification note</span>
              <input className={shared.inlineInput} value={providerForm.verificationMessage} onChange={(event) => setProviderForm((current) => ({ ...current, verificationMessage: event.currentTarget.value }))} />
            </label>
          </div>
          <div className={styles.filterRow}>
            <label className={styles.summaryCard}>
              <span>Provider slug</span>
              <strong>{providerForm.slug || slugify(providerForm.displayName) || "generated-from-name"}</strong>
              <small>Used as the stable registry key for connector and sync wiring.</small>
            </label>
            <label className={styles.summaryCard}>
              <span>Status</span>
              <strong>{providerForm.syncStatus}</strong>
              <small>Keep providers in draft until the connector and metadata mapping are validated.</small>
            </label>
            <label className={styles.summaryCard}>
              <span>Enabled</span>
              <strong>{providerForm.isEnabled ? "Yes" : "No"}</strong>
              <small>
                <input type="checkbox" checked={providerForm.isEnabled} onChange={(event) => setProviderForm((current) => ({ ...current, isEnabled: event.currentTarget.checked, syncStatus: event.currentTarget.checked ? current.syncStatus : "draft" }))} /> Enable in catalog
              </small>
            </label>
          </div>
          {providerMessage ? <p className={styles.successText}>{providerMessage}</p> : null}
          {providerError ? <p className={shared.errorText}>{providerError}</p> : null}
          <div className={styles.actionButtons}>
            <button type="button" className={styles.primaryButton} disabled={createExternalProviderState.isLoading || updateExternalProviderState.isLoading} onClick={onSaveExternalProvider}>
              {createExternalProviderState.isLoading || updateExternalProviderState.isLoading ? "Saving..." : selectedProvider ? "Save provider" : "Create provider"}
            </button>
            {selectedProvider ? (
              <button type="button" className={styles.secondaryButton} disabled={deleteExternalProviderState.isLoading} onClick={onDeleteExternalProvider}>
                {deleteExternalProviderState.isLoading ? "Removing..." : "Remove provider"}
              </button>
            ) : null}
          </div>
        </section>
      </div>

      <section className={shared.panel}>
        <header className={shared.panelHeader}>
          <div>
            <h2>Learning programs</h2>
            <p>Create reusable standard sets of courses for onboarding, roles, departments, or AI-assisted recommendations, then assign them to individual learners from the user registry.</p>
          </div>
          <span className={shared.sectionHint}>{learningPrograms.length} program(s)</span>
        </header>
        <div className={shared.grid2}>
          <div className={styles.directoryList}>
            {learningPrograms.map((program) => (
              <button key={program.id} type="button" className={`${styles.directoryItem} ${program.id === selectedProgramId ? styles.directoryItemActive : ""}`} onClick={() => setSelectedProgramId(program.id)}>
                <div className={styles.directoryHeader}>
                  <div className={shared.tableCellStack}>
                    <strong>{program.title}</strong>
                    <span>{program.assignmentMode} · {program.targetAudience || "No audience configured"}</span>
                  </div>
                  <span className={program.isActive ? shared.goodPill : shared.warnPill}>
                    {program.isActive ? "Active" : "Paused"}
                  </span>
                </div>
                <div className={styles.directoryMetrics}>
                  <span>{program.programCourses.length} course(s)</span>
                  <span>{program.assignmentsCount} assignment(s)</span>
                  <span>{program.slug}</span>
                </div>
              </button>
            ))}
          </div>
          <div className={styles.commandPanel}>
            <div className={styles.filterRow}>
              <label className={shared.selectWrap}>
                <span className={shared.fieldLabel}>Program title</span>
                <input className={shared.inlineInput} value={programForm.title} onChange={(event) => setProgramForm((current) => ({ ...current, title: event.currentTarget.value, slug: current.slug || slugify(event.currentTarget.value) }))} />
              </label>
              <label className={shared.selectWrap}>
                <span className={shared.fieldLabel}>Slug</span>
                <input className={shared.inlineInput} value={programForm.slug} onChange={(event) => setProgramForm((current) => ({ ...current, slug: event.currentTarget.value }))} />
              </label>
              <label className={shared.selectWrap}>
                <span className={shared.fieldLabel}>Assignment mode</span>
                <select className={shared.select} value={programForm.assignmentMode} onChange={(event) => setProgramForm((current) => ({ ...current, assignmentMode: event.currentTarget.value as typeof programForm.assignmentMode }))}>
                  <option value="manual">Manual</option>
                  <option value="role_based">Role-based</option>
                  <option value="ai_recommended">AI recommended</option>
                  <option value="hybrid">Hybrid</option>
                </select>
              </label>
            </div>
            <div className={styles.filterRow}>
              <label className={shared.selectWrap}>
                <span className={shared.fieldLabel}>Target audience</span>
                <input className={shared.inlineInput} value={programForm.targetAudience} onChange={(event) => setProgramForm((current) => ({ ...current, targetAudience: event.currentTarget.value }))} placeholder="Students, analysts, managers..." />
              </label>
              <label className={shared.selectWrap}>
                <span className={shared.fieldLabel}>Recommended by AI when</span>
                <input className={shared.inlineInput} value={programForm.recommendationPrompt} onChange={(event) => setProgramForm((current) => ({ ...current, recommendationPrompt: event.currentTarget.value }))} placeholder="New data analyst onboarding, Python skill gap..." />
              </label>
            </div>
            <label className={shared.selectWrap}>
              <span className={shared.fieldLabel}>Description</span>
              <textarea className={shared.textarea} rows={4} value={programForm.description} onChange={(event) => setProgramForm((current) => ({ ...current, description: event.currentTarget.value }))} />
            </label>
            <label className={shared.selectWrap}>
              <span className={shared.fieldLabel}>Program course set</span>
              <select
                className={shared.select}
                multiple
                size={Math.min(8, Math.max(4, courseCards.length || 4))}
                value={programForm.courseIds.map(String)}
                onChange={(event) =>
                  setProgramForm((current) => ({
                    ...current,
                    courseIds: Array.from(event.currentTarget.selectedOptions).map((option) => Number(option.value)),
                  }))
                }
              >
                {courseCards.map((course) => (
                  <option key={course.id} value={course.id}>
                    {courseDisplayTitle(course)}
                  </option>
                ))}
              </select>
            </label>
            <label className={styles.checkboxRow}>
              <input type="checkbox" checked={programForm.isActive} onChange={(event) => setProgramForm((current) => ({ ...current, isActive: event.currentTarget.checked }))} />
              <span>Program active</span>
            </label>
            {programMessage ? <p className={styles.successText}>{programMessage}</p> : null}
            {programError ? <p className={shared.errorText}>{programError}</p> : null}
            <div className={styles.actionButtons}>
              <button type="button" className={styles.primaryButton} disabled={createLearningProgramState.isLoading || updateLearningProgramState.isLoading} onClick={onSaveLearningProgram}>
                {createLearningProgramState.isLoading || updateLearningProgramState.isLoading ? "Saving..." : selectedProgram ? "Save program" : "Create program"}
              </button>
              {selectedProgram ? (
                <button type="button" className={styles.secondaryButton} disabled={deleteLearningProgramState.isLoading} onClick={onDeleteLearningProgram}>
                  {deleteLearningProgramState.isLoading ? "Removing..." : "Remove program"}
                </button>
              ) : null}
            </div>
          </div>
        </div>
      </section>

      <div className={shared.grid2}>
        <section className={shared.panel}>
          <header className={shared.panelHeader}>
            <div>
              <h2>Cohort delivery board</h2>
              <p>Filter active cohorts for the selected course and move into the detailed session board below.</p>
            </div>
            <span className={shared.linkPill}>{filteredCohorts.length} cohort(s) visible</span>
          </header>

          <div className={styles.filterRow}>
            <label className={shared.selectWrap}>
              <span className={shared.fieldLabel}>Cohort search</span>
              <input
                className={shared.inlineInput}
                value={cohortQuery}
                onChange={(event) => setCohortQuery(event.currentTarget.value)}
                placeholder="Search group code, name, or teacher"
              />
            </label>
            <label className={shared.selectWrap}>
              <span className={shared.fieldLabel}>Status</span>
              <select
                className={shared.select}
                value={cohortStatusFilter}
                onChange={(event) => setCohortStatusFilter(event.currentTarget.value as CohortStatusFilter)}
              >
                <option value="all">All statuses</option>
                <option value="draft">Draft</option>
                <option value="open">Open</option>
                <option value="running">Running</option>
                <option value="finished">Finished</option>
              </select>
            </label>
          </div>

          <div className={styles.directoryList}>
            {filteredCohorts.length === 0 ? (
              <p className={shared.emptyText}>No cohorts match the current filters for this course.</p>
            ) : null}
            {filteredCohorts.map((cohort) => {
              const isActive = cohort.id === selectedCohortId;
              return (
                <button
                  key={cohort.id}
                  type="button"
                  className={`${styles.directoryItem} ${isActive ? styles.directoryItemActive : ""}`}
                  onClick={() => {
                    setSelectedCohortId(cohort.id);
                    setSelectedSessionIds([]);
                    setActionMessage(null);
                    setActionError(null);
                  }}
                >
                  <div className={styles.directoryHeader}>
                    <div className={shared.tableCellStack}>
                      <strong>
                        {cohort.groupCode} · {cohort.groupName}
                      </strong>
                      <span>{cohort.teacherName}</span>
                    </div>
                    <div className={styles.inlinePills}>
                      <span className={cohortStatusBadgeClass(cohort.status, shared)}>
                        {cohortStatusLabel(cohort.status)}
                      </span>
                      <span className={cohort.isPublic ? shared.neutralPill : shared.linkPill}>
                        {cohort.isPublic ? "Public" : "Internal"}
                      </span>
                    </div>
                  </div>
                  <div className={styles.directoryMetrics}>
                    <span>{cohort.studentsCount} learners</span>
                    <span>{cohort.sessionsCount} sessions</span>
                    <span>{formatPercent(cohort.attendancePercent)} attendance</span>
                    <span>{formatDateTime(cohort.nearestSessionAt)}</span>
                  </div>
                </button>
              );
            })}
          </div>
        </section>

        <section className={shared.panel}>
          <header className={shared.panelHeader}>
            <div>
              <h2>Selected cohort overview</h2>
              <p>Operational pulse for the current cohort, including learner risk and upcoming delivery pressure.</p>
            </div>
            {selectedCohortCard ? (
              <span className={shared.linkPill}>{selectedCohortCard.groupCode}</span>
            ) : null}
          </header>

          {isCohortDetailLoading ? <p className={shared.emptyText}>Loading selected cohort details...</p> : null}
          {isCohortDetailError ? <p className={shared.errorText}>Failed to load selected cohort detail.</p> : null}

          <div className={styles.summaryGrid}>
            <article className={styles.summaryCard}>
              <span>Teacher</span>
              <strong>{selectedCohortDetail?.teacherName ?? selectedCohortCard?.teacherName ?? "Not assigned"}</strong>
              <small>Group lead currently assigned to this cohort</small>
            </article>
            <article className={styles.summaryCard}>
              <span>Students</span>
              <strong>{selectedCohortSummary.students}</strong>
              <small>{selectedCohortSummary.riskStudents} learners below 60% attendance</small>
            </article>
            <article className={styles.summaryCard}>
              <span>Sessions</span>
              <strong>{selectedCohortSummary.sessions}</strong>
              <small>{selectedCohortSummary.completed} completed so far</small>
            </article>
            <article className={styles.summaryCard}>
              <span>Nearest live point</span>
              <strong>{formatDateTime(selectedCohortDetail?.nearestSessionAt ?? selectedCohortCard?.nearestSessionAt)}</strong>
              <small>{formatPercent(selectedCohortDetail?.attendancePercent ?? selectedCohortCard?.attendancePercent)} attendance</small>
            </article>
          </div>

          <div className={styles.inlinePills}>
            <span className={shared.neutralPill}>{selectedCohortSummary.scheduled} scheduled</span>
            <span className={shared.goodPill}>{selectedCohortSummary.live} live</span>
            <span className={shared.warnPill}>{selectedCohortSummary.canceled} canceled</span>
          </div>

          <div className={shared.list}>
            {riskLearners.length === 0 ? (
              <p className={shared.emptyText}>No learner risk indicators are available for the selected cohort yet.</p>
            ) : null}
            {riskLearners.map((student) => (
              <article key={student.enrollmentId} className={shared.listItem}>
                <strong>{student.fullName}</strong>
                <span>{student.email}</span>
                <span>
                  {student.status} · {formatPercent(student.attendancePercent)} attendance
                </span>
              </article>
            ))}
          </div>
        </section>
      </div>

      <section className={shared.panel}>
        <header className={shared.panelHeader}>
          <div>
            <h2>Session operations board</h2>
            <p>Run session lifecycle actions in bulk, inspect join links, and keep attendance sync current.</p>
          </div>
          <div className={styles.inlinePills}>
            <span className={shared.neutralPill}>{sessionSelectionSummary.total} selected</span>
            <span className={shared.linkPill}>{sessionSelectionSummary.openable} openable</span>
            <span className={shared.linkPill}>{sessionSelectionSummary.endable} endable</span>
            <span className={shared.linkPill}>{sessionSelectionSummary.syncable} syncable</span>
          </div>
        </header>

        <div className={styles.filterRow}>
          <label className={shared.selectWrap}>
            <span className={shared.fieldLabel}>Session search</span>
            <input
              className={shared.inlineInput}
              value={sessionQuery}
              onChange={(event) => setSessionQuery(event.currentTarget.value)}
              placeholder="Search title or schedule"
            />
          </label>
          <label className={shared.selectWrap}>
            <span className={shared.fieldLabel}>Session status</span>
            <select
              className={shared.select}
              value={sessionStatusFilter}
              onChange={(event) => setSessionStatusFilter(event.currentTarget.value as SessionStatusFilter)}
            >
              <option value="all">All statuses</option>
              <option value="scheduled">Scheduled</option>
              <option value="live">Live</option>
              <option value="ended">Ended</option>
              <option value="canceled">Canceled</option>
            </select>
          </label>
          <label className={shared.selectWrap}>
            <span className={shared.fieldLabel}>Attendance sync</span>
            <select
              className={shared.select}
              value={sessionAttendanceSyncFilter}
              onChange={(event) =>
                setSessionAttendanceSyncFilter(event.currentTarget.value as SessionAttendanceSyncFilter)
              }
            >
              <option value="all">All sync states</option>
              <option value="synced">Synced</option>
              <option value="pending">Pending sync</option>
            </select>
          </label>
          <label className={shared.selectWrap}>
            <span className={shared.fieldLabel}>Join link</span>
            <select
              className={shared.select}
              value={sessionJoinLinkFilter}
              onChange={(event) => setSessionJoinLinkFilter(event.currentTarget.value as SessionPresenceFilter)}
            >
              <option value="all">All join states</option>
              <option value="present">Link ready</option>
              <option value="missing">Missing link</option>
            </select>
          </label>
          <label className={shared.selectWrap}>
            <span className={shared.fieldLabel}>Recording</span>
            <select
              className={shared.select}
              value={sessionRecordingFilter}
              onChange={(event) => setSessionRecordingFilter(event.currentTarget.value as SessionPresenceFilter)}
            >
              <option value="all">All recording states</option>
              <option value="present">Recording ready</option>
              <option value="missing">Missing recording</option>
            </select>
          </label>
        </div>

        <div className={styles.sessionInsightGrid}>
          <article className={styles.sessionInsightCard}>
            <span>Attendance sync</span>
            <strong>{sessionOperationalSummary.synced}</strong>
            <small>{sessionOperationalSummary.pendingSync} session(s) still pending sync</small>
          </article>
          <article className={styles.sessionInsightCard}>
            <span>Join links</span>
            <strong>{sessionOperationalSummary.joinLinkReady}</strong>
            <small>{sessionOperationalSummary.joinLinkMissing} session(s) missing live access</small>
          </article>
          <article className={styles.sessionInsightCard}>
            <span>Recordings</span>
            <strong>{sessionOperationalSummary.recordingsReady}</strong>
            <small>{sessionOperationalSummary.recordingsMissing} session(s) without replay</small>
          </article>
        </div>

        {isSessionsLoading ? <p className={shared.emptyText}>Loading cohort sessions...</p> : null}
        {isSessionsError ? <p className={shared.errorText}>Failed to load session operations for the selected cohort.</p> : null}

        <div className={styles.selectionBar}>
          <div className={styles.selectionButtons}>
            <button type="button" className={styles.ghostButton} onClick={selectAllVisibleSessions}>
              Select visible
            </button>
            <button type="button" className={styles.ghostButton} onClick={clearSelectedSessions}>
              Clear selection
            </button>
          </div>
          <div className={styles.actionButtons}>
            <button
              type="button"
              className={styles.primaryButton}
              disabled={pendingAction !== null || sessionSelectionSummary.openable === 0}
              onClick={() => executeSessionAction("open")}
            >
              {pendingAction === "open" ? `${sessionActionProgressLabel.open}...` : "Open selected"}
            </button>
            <button
              type="button"
              className={styles.primaryButton}
              disabled={pendingAction !== null || sessionSelectionSummary.endable === 0}
              onClick={() => executeSessionAction("end")}
            >
              {pendingAction === "end" ? `${sessionActionProgressLabel.end}...` : "End selected"}
            </button>
            <button
              type="button"
              className={styles.secondaryButton}
              disabled={pendingAction !== null || sessionSelectionSummary.syncable === 0}
              onClick={() => executeSessionAction("sync")}
            >
              {pendingAction === "sync" ? `${sessionActionProgressLabel.sync}...` : "Sync attendance"}
            </button>
          </div>
        </div>

        {actionMessage ? <p className={styles.successText}>{actionMessage}</p> : null}
        {actionError ? <p className={shared.errorText}>{actionError}</p> : null}

        <div className={shared.tableWrap}>
          <table className={shared.table}>
            <thead>
              <tr>
                <th>Select</th>
                <th>Session</th>
                <th>Schedule</th>
                <th>Status</th>
                <th>Attendance</th>
                <th>Join</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredSessions.length === 0 ? (
                <tr>
                  <td colSpan={7}>
                    <p className={shared.emptyText}>No sessions match the current filters for this cohort.</p>
                  </td>
                </tr>
              ) : null}
              {filteredSessions.map((session) => {
                const selected = selectedSessionIds.includes(session.id);
                const attendanceKnown =
                  session.attendanceSummary.present +
                  session.attendanceSummary.absent +
                  session.attendanceSummary.excused +
                  session.attendanceSummary.unknown;
                return (
                  <tr key={session.id} className={selected ? styles.tableRowActive : ""}>
                    <td>
                      <label className={styles.checkboxWrap}>
                        <input
                          type="checkbox"
                          checked={selected}
                          onChange={() => toggleSessionSelection(session.id)}
                        />
                        <span>{session.id}</span>
                      </label>
                    </td>
                    <td>
                      <div className={shared.tableCellStack}>
                        <strong>{session.title}</strong>
                        <span>
                          {selectedCohortCard
                            ? `${selectedCohortCard.groupCode} · ${selectedCohortCard.groupName}`
                            : "Selected cohort"}
                        </span>
                      </div>
                    </td>
                    <td>
                      <div className={shared.tableCellStack}>
                        <strong>{formatDateTime(session.startsAt)}</strong>
                        <span>{formatDateTime(session.endsAt)}</span>
                      </div>
                    </td>
                    <td>
                      <span className={sessionStatusBadgeClass(session.status, shared)}>
                        {sessionStatusLabel(session.status)}
                      </span>
                    </td>
                    <td>
                      <div className={shared.tableCellStack}>
                        <strong>{attendanceKnown} rows tracked</strong>
                        <span>
                          {session.attendanceSummary.present} present · {session.attendanceSummary.absent} absent ·{" "}
                          {session.attendanceSummary.unknown} unknown
                        </span>
                      </div>
                    </td>
                    <td>
                      {session.joinUrl ? (
                        <a className={shared.linkPill} href={session.joinUrl} target="_blank" rel="noreferrer">
                          Open link
                        </a>
                      ) : (
                        <span className={shared.linkPill}>Not generated</span>
                      )}
                    </td>
                    <td>
                      <div className={styles.rowActions}>
                        <button
                          type="button"
                          className={styles.ghostButton}
                          disabled={pendingAction !== null || !isActionableSession("open", session)}
                          onClick={() => executeSessionAction("open", [session.id])}
                        >
                          Open
                        </button>
                        <button
                          type="button"
                          className={styles.ghostButton}
                          disabled={pendingAction !== null || !isActionableSession("end", session)}
                          onClick={() => executeSessionAction("end", [session.id])}
                        >
                          End
                        </button>
                        <button
                          type="button"
                          className={styles.ghostButton}
                          disabled={pendingAction !== null}
                          onClick={() => executeSessionAction("sync", [session.id])}
                        >
                          Sync
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      <div className={shared.grid2}>
        <section className={shared.panel}>
          <header className={shared.panelHeader}>
            <div>
              <h2>Learner roster</h2>
              <p>Fast read on enrollment health for the currently selected cohort.</p>
            </div>
            <span className={shared.linkPill}>{selectedCohortDetail?.students.length ?? 0} learners</span>
          </header>
          <div className={shared.tableWrap}>
            <table className={shared.table}>
              <thead>
                <tr>
                  <th>Learner</th>
                  <th>Email</th>
                  <th>Status</th>
                  <th>Attendance</th>
                </tr>
              </thead>
              <tbody>
                {(selectedCohortDetail?.students ?? []).length === 0 ? (
                  <tr>
                    <td colSpan={4}>
                      <p className={shared.emptyText}>No learners are assigned to this cohort yet.</p>
                    </td>
                  </tr>
                ) : null}
                {(selectedCohortDetail?.students ?? []).map((student) => (
                  <tr key={student.enrollmentId}>
                    <td>
                      <div className={shared.tableCellStack}>
                        <strong>{student.fullName}</strong>
                        <span>{formatRelativeHealth(student.attendancePercent)}</span>
                      </div>
                    </td>
                    <td>{student.email}</td>
                    <td>{student.status}</td>
                    <td>{formatPercent(student.attendancePercent)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className={shared.panel}>
          <header className={shared.panelHeader}>
            <div>
              <h2>Course delivery timeline</h2>
              <p>Upcoming course sessions help admins anticipate pressure before switching to individual cohort actions.</p>
            </div>
            <span className={shared.linkPill}>{courseTimeline.length} upcoming checkpoints</span>
          </header>
          <div className={shared.list}>
            {courseTimeline.length === 0 ? (
              <p className={shared.emptyText}>No course-level sessions are available for the selected scope.</p>
            ) : null}
            {courseTimeline.map((session) => (
              <article key={session.id} className={shared.listItem}>
                <strong>{session.title}</strong>
                <span>
                  {session.groupCode} · {session.groupName}
                </span>
                <span>
                  {formatDateTime(session.startsAt)} ·{" "}
                  <span className={sessionStatusBadgeClass(session.status, shared)}>
                    {sessionStatusLabel(session.status)}
                  </span>
                </span>
              </article>
            ))}
          </div>
        </section>
      </div>

      <section className={shared.panel}>
        <header className={shared.panelHeader}>
          <div>
            <h2>Seeded program families</h2>
            <p>The same seeded programming catalog should be visible here and in the public course page so admins can trace the lesson-document structure end-to-end.</p>
          </div>
        </header>
        <div className={shared.grid3}>
          {pocProgramCourses.map((blueprint) => (
            <article key={blueprint.slug} className={shared.card}>
              <div className={shared.tableCellStack}>
                <strong>{blueprint.title}</strong>
                <span>{blueprint.summary}</span>
                <span>{blueprint.audience}</span>
              </div>
              <div className={shared.heroMeta}>
                <span>{blueprint.focus}</span>
                <span>{blueprint.modules.length} modules</span>
              </div>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
};

export default AdminCoursesPage;
