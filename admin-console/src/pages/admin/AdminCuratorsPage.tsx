import { useCallback, useDeferredValue, useEffect, useMemo, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";

import {
  useAssignOnlineAdminCohortCuratorMutation,
  useCreateOnlineAdminInstructorProfileMutation,
  useCreateOnlineAdminCuratorMutation,
  useCreateOnlineAdminScopeAssignmentMutation,
  useDeleteOnlineAdminScopeAssignmentMutation,
  useDeleteOnlineAdminInstructorProfileMutation,
  useDeleteOnlineAdminCuratorMutation,
  useGetOnlineAdminCuratorsQuery,
  useGetOnlineAdminScopeAssignmentsQuery,
  useGetOnlineAdminUsersQuery,
  useGetOnlineCohortsQuery,
  useGetOnlineCoursesQuery,
  useResetOnlineAdminUserTemporaryPasswordMutation,
  useUpdateOnlineAdminInstructorProfileMutation,
  useUpdateOnlineAdminStudentProfileMutation,
  useUpdateOnlineAdminScopeAssignmentMutation,
  useUpdateOnlineAdminUserStatusMutation,
  useUpdateOnlineAdminCuratorMutation,
} from "@/bll/online/online.service";
import type {
  OnlineAdminCuratorSummary,
  OnlineAdminScopeAssignment,
  OnlineAdminUserSummary,
  OnlineCohortCard,
} from "@/bll/online/online.type";
import shared from "./AdminPagesShared.module.css";
import { AdminCuratorCourseRolesPanel } from "./AdminCuratorCourseRolesPanel";
import { AdminCuratorDemoRolePanel } from "./AdminCuratorDemoRolePanel";
import { AdminCuratorOnboardingPanel } from "./AdminCuratorOnboardingPanel";
import styles from "./AdminCuratorsPage.module.css";
import { courseDisplayTitle, formatDateTime, formatPercent, sumValues } from "./adminPageUtils";

type UserRoleFilter = "" | "curator" | "admin" | "student";
type FormState = { firstName: string; lastName: string; schoolEmail: string; privateEmail: string; phone: string; shortName: string };
type ScopeRole = "manager" | "delivery_manager" | "compliance_manager" | "review_manager";
type ScopeType = "academy" | "course" | "cohort";
type ScopeFormState = {
  role: ScopeRole;
  scopeType: ScopeType;
  courseId: number | "";
  cohortId: number | "";
  note: string;
  isPrimary: boolean;
};

const EMPTY_FORM: FormState = { firstName: "", lastName: "", schoolEmail: "", privateEmail: "", phone: "", shortName: "" };
const EMPTY_SCOPE_FORM: ScopeFormState = {
  role: "manager",
  scopeType: "academy",
  courseId: "",
  cohortId: "",
  note: "",
  isPrimary: false,
};

type StudentProfileFormState = {
  employeeId: string;
  department: string;
  teamName: string;
  officeLocation: string;
  jobTitle: string;
  managerName: string;
  phone: string;
  employmentStatus: "active" | "on_leave" | "contractor" | "inactive";
  hiredAt: string;
};

type InstructorProfileFormState = {
  department: string;
  jobTitle: string;
  bio: string;
  expertiseAreas: string;
  spokenLanguages: string;
  canAuthor: boolean;
  canReview: boolean;
  canPublish: boolean;
  canGenerateWithAi: boolean;
  canManageAssessments: boolean;
};

const EMPTY_STUDENT_PROFILE_FORM: StudentProfileFormState = {
  employeeId: "",
  department: "",
  teamName: "",
  officeLocation: "",
  jobTitle: "",
  managerName: "",
  phone: "",
  employmentStatus: "active",
  hiredAt: "",
};

const EMPTY_INSTRUCTOR_PROFILE_FORM: InstructorProfileFormState = {
  department: "",
  jobTitle: "",
  bio: "",
  expertiseAreas: "",
  spokenLanguages: "",
  canAuthor: true,
  canReview: false,
  canPublish: false,
  canGenerateWithAi: true,
  canManageAssessments: true,
};

const shortNameFrom = (firstName: string, lastName: string) =>
  `${firstName.trim().slice(0, 1)}${lastName.trim().slice(0, 1)}`.toUpperCase();

const normalizeForm = (state: FormState): FormState => ({
  firstName: state.firstName.trim(),
  lastName: state.lastName.trim(),
  schoolEmail: state.schoolEmail.trim(),
  privateEmail: state.privateEmail.trim(),
  phone: state.phone.trim(),
  shortName: state.shortName.trim().replace(/\s+/g, "").toUpperCase(),
});

const errorMessageFrom = (error: unknown, fallback: string) => {
  if (!error || typeof error !== "object" || !("data" in error)) return fallback;
  const payload = (error as { data?: unknown }).data;
  if (!payload || typeof payload !== "object") return fallback;
  const objectPayload = payload as Record<string, unknown>;
  if (typeof objectPayload.detail === "string") return objectPayload.detail;
  for (const value of Object.values(objectPayload)) {
    if (typeof value === "string") return value;
    if (Array.isArray(value) && typeof value[0] === "string") return value[0];
  }
  return fallback;
};

const parseCourseScopeId = (value: string | null): number | "" => {
  if (!value) return "";
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : "";
};

const toCommaSeparated = (value: string[]) => value.join(", ");

const parseCommaSeparated = (value: string) =>
  value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);

const badgeClassFor = (user: OnlineAdminUserSummary, sharedStyles: typeof shared) => {
  if (!user.isActive) return sharedStyles.warnPill;
  if (user.isCurator) return sharedStyles.goodPill;
  return sharedStyles.neutralPill;
};

const AdminCuratorsPage = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [userSearch, setUserSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState<UserRoleFilter>("");
  const [curatorSearch, setCuratorSearch] = useState("");
  const [cohortSearch, setCohortSearch] = useState("");
  const [selectedUserId, setSelectedUserId] = useState<number | null>(null);
  const [selectedCuratorId, setSelectedCuratorId] = useState<number | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [formMessage, setFormMessage] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [assignmentMessage, setAssignmentMessage] = useState<string | null>(null);
  const [assignmentError, setAssignmentError] = useState<string | null>(null);
  const [accessMessage, setAccessMessage] = useState<string | null>(null);
  const [accessError, setAccessError] = useState<string | null>(null);
  const [scopeForm, setScopeForm] = useState<ScopeFormState>(EMPTY_SCOPE_FORM);
  const [scopeMessage, setScopeMessage] = useState<string | null>(null);
  const [scopeError, setScopeError] = useState<string | null>(null);
  const [studentProfileForm, setStudentProfileForm] = useState<StudentProfileFormState>(EMPTY_STUDENT_PROFILE_FORM);
  const [studentProfileMessage, setStudentProfileMessage] = useState<string | null>(null);
  const [studentProfileError, setStudentProfileError] = useState<string | null>(null);
  const [instructorProfileForm, setInstructorProfileForm] = useState<InstructorProfileFormState>(EMPTY_INSTRUCTOR_PROFILE_FORM);
  const [instructorProfileMessage, setInstructorProfileMessage] = useState<string | null>(null);
  const [instructorProfileError, setInstructorProfileError] = useState<string | null>(null);
  const [temporaryPassword, setTemporaryPassword] = useState("");
  const [busyCohortId, setBusyCohortId] = useState<number | null>(null);

  const deferredUserSearch = useDeferredValue(userSearch.trim().toLowerCase());
  const deferredCuratorSearch = useDeferredValue(curatorSearch.trim().toLowerCase());
  const deferredCohortSearch = useDeferredValue(cohortSearch.trim().toLowerCase());
  const requestedCourseId = useMemo(() => parseCourseScopeId(searchParams.get("courseId")), [searchParams]);

  const { data: usersData, isLoading: isUsersLoading, isError: isUsersError } = useGetOnlineAdminUsersQuery();
  const { data: curatorsData, isLoading: isCuratorsLoading, isError: isCuratorsError } = useGetOnlineAdminCuratorsQuery();
  const { data: cohortsData, isLoading: isCohortsLoading, isError: isCohortsError } = useGetOnlineCohortsQuery();
  const { data: coursesData } = useGetOnlineCoursesQuery();

  const [createCurator, createState] = useCreateOnlineAdminCuratorMutation();
  const [createInstructorProfile, createInstructorProfileState] = useCreateOnlineAdminInstructorProfileMutation();
  const [createScopeAssignment, createScopeAssignmentState] = useCreateOnlineAdminScopeAssignmentMutation();
  const [updateScopeAssignment, updateScopeAssignmentState] = useUpdateOnlineAdminScopeAssignmentMutation();
  const [deleteScopeAssignment, deleteScopeAssignmentState] = useDeleteOnlineAdminScopeAssignmentMutation();
  const [updateCurator, updateState] = useUpdateOnlineAdminCuratorMutation();
  const [updateStudentProfile, updateStudentProfileState] = useUpdateOnlineAdminStudentProfileMutation();
  const [updateInstructorProfile, updateInstructorProfileState] = useUpdateOnlineAdminInstructorProfileMutation();
  const [deleteInstructorProfile, deleteInstructorProfileState] = useDeleteOnlineAdminInstructorProfileMutation();
  const [deleteCurator, deleteState] = useDeleteOnlineAdminCuratorMutation();
  const [assignCurator, assignState] = useAssignOnlineAdminCohortCuratorMutation();
  const [updateUserStatus, userStatusState] = useUpdateOnlineAdminUserStatusMutation();
  const [resetTemporaryPassword, passwordResetState] = useResetOnlineAdminUserTemporaryPasswordMutation();

  const users = usersData?.results ?? [];
  const curators = curatorsData?.results ?? [];
  const cohorts = cohortsData?.results ?? [];
  const courses = coursesData?.results ?? [];
  const courseId = useMemo(() => {
    if (!requestedCourseId) return "";
    return courses.some((course) => course.id === requestedCourseId) ? requestedCourseId : "";
  }, [courses, requestedCourseId]);
  const { data: scopeAssignmentsData, isLoading: isScopeAssignmentsLoading, isError: isScopeAssignmentsError } =
    useGetOnlineAdminScopeAssignmentsQuery(
      selectedUserId
        ? {
            userId: selectedUserId,
            courseId: courseId || undefined,
          }
        : undefined,
      { skip: !selectedUserId }
    );

  const curatorMap = useMemo(() => new Map(curators.map((item) => [item.id, item])), [curators]);

  const filteredUsers = useMemo(() => users.filter((user) => {
    if (roleFilter === "curator" && !user.isCurator) return false;
    if (roleFilter === "admin" && !user.isAdmin) return false;
    if (roleFilter === "student" && !user.isStudent) return false;
    if (!deferredUserSearch) return true;
    return [user.fullName, user.email, user.username ?? "", user.curatorProfile?.schoolEmail ?? "", user.curatorProfile?.shortName ?? ""]
      .join(" ")
      .toLowerCase()
      .includes(deferredUserSearch);
  }), [deferredUserSearch, roleFilter, users]);

  const filteredCurators = useMemo(() => curators.filter((curator) => {
    if (!deferredCuratorSearch) return true;
    return [curator.fullName, curator.schoolEmail, curator.email, curator.shortName].join(" ").toLowerCase().includes(deferredCuratorSearch);
  }), [curators, deferredCuratorSearch]);

  const filteredCohorts = useMemo(() => cohorts.filter((cohort) => {
    if (courseId && cohort.courseId !== courseId) return false;
    if (!deferredCohortSearch) return true;
    return [cohort.groupCode, cohort.groupName, cohort.courseTitleDe, cohort.courseTitleEn, cohort.teacherName].join(" ").toLowerCase().includes(deferredCohortSearch);
  }), [cohorts, courseId, deferredCohortSearch]);
  const scopeAssignments = useMemo(() => scopeAssignmentsData?.results ?? [], [scopeAssignmentsData]);
  const scopeCourseId = scopeForm.courseId || courseId || "";
  const scopeCohorts = useMemo(
    () => cohorts.filter((cohort) => (scopeCourseId ? cohort.courseId === scopeCourseId : true)),
    [cohorts, scopeCourseId]
  );

  const setCourseId = useCallback((value: number | "") => {
    const nextParams = new URLSearchParams(searchParams);
    if (value) {
      nextParams.set("courseId", String(value));
    } else {
      nextParams.delete("courseId");
    }
    setSearchParams(nextParams, { replace: true });
  }, [searchParams, setSearchParams]);

  useEffect(() => {
    if (selectedUserId === null && users.length > 0) {
      setSelectedUserId(filteredUsers[0]?.id ?? users[0].id);
      return;
    }
    if (selectedUserId !== null && !users.some((user) => user.id === selectedUserId)) {
      setSelectedUserId(filteredUsers[0]?.id ?? users[0]?.id ?? null);
    }
  }, [filteredUsers, selectedUserId, users]);

  useEffect(() => {
    if (selectedCuratorId !== null && !curators.some((curator) => curator.id === selectedCuratorId)) {
      setSelectedCuratorId(null);
    }
  }, [curators, selectedCuratorId]);

  useEffect(() => {
    setScopeForm((current) => {
      if (current.scopeType !== "course" && current.scopeType !== "cohort") return current;
      if (current.courseId || !courseId) return current;
      return { ...current, courseId };
    });
  }, [courseId]);

  const selectedUser = users.find((user) => user.id === selectedUserId) ?? null;
  const selectedCurator = selectedCuratorId !== null
    ? curatorMap.get(selectedCuratorId) ?? null
    : selectedUser?.curatorId
      ? curatorMap.get(selectedUser.curatorId) ?? null
      : null;

  useEffect(() => {
    if (selectedCurator) {
      setForm({
        firstName: selectedCurator.firstName,
        lastName: selectedCurator.lastName,
        schoolEmail: selectedCurator.schoolEmail,
        privateEmail: selectedCurator.privateEmail,
        phone: selectedCurator.phone,
        shortName: selectedCurator.shortName,
      });
      return;
    }
    if (selectedUser) {
      setForm({
        firstName: selectedUser.firstName,
        lastName: selectedUser.lastName,
        schoolEmail: selectedUser.email,
        privateEmail: "",
        phone: "",
        shortName: shortNameFrom(selectedUser.firstName, selectedUser.lastName),
      });
      return;
    }
    setForm(EMPTY_FORM);
  }, [selectedCurator, selectedUser]);

  useEffect(() => {
    if (selectedUser?.studentProfile) {
      setStudentProfileForm({
        employeeId: selectedUser.studentProfile.employeeId,
        department: selectedUser.studentProfile.department,
        teamName: selectedUser.studentProfile.teamName,
        officeLocation: selectedUser.studentProfile.officeLocation,
        jobTitle: selectedUser.studentProfile.jobTitle,
        managerName: selectedUser.studentProfile.managerName,
        phone: selectedUser.studentProfile.phone,
        employmentStatus: selectedUser.studentProfile.employmentStatus,
        hiredAt: selectedUser.studentProfile.hiredAt ? String(selectedUser.studentProfile.hiredAt).slice(0, 10) : "",
      });
      return;
    }
    setStudentProfileForm(EMPTY_STUDENT_PROFILE_FORM);
  }, [selectedUser]);

  useEffect(() => {
    if (selectedCurator?.instructorProfile) {
      setInstructorProfileForm({
        department: selectedCurator.instructorProfile.department,
        jobTitle: selectedCurator.instructorProfile.jobTitle,
        bio: selectedCurator.instructorProfile.bio,
        expertiseAreas: toCommaSeparated(selectedCurator.instructorProfile.expertiseAreas),
        spokenLanguages: toCommaSeparated(selectedCurator.instructorProfile.spokenLanguages),
        canAuthor: selectedCurator.instructorProfile.canAuthor,
        canReview: selectedCurator.instructorProfile.canReview,
        canPublish: selectedCurator.instructorProfile.canPublish,
        canGenerateWithAi: selectedCurator.instructorProfile.canGenerateWithAi,
        canManageAssessments: selectedCurator.instructorProfile.canManageAssessments,
      });
      return;
    }
    setInstructorProfileForm(EMPTY_INSTRUCTOR_PROFILE_FORM);
  }, [selectedCurator]);

  const assignedCohortsTotal = useMemo(() => sumValues(curators.map((curator) => curator.assignedCohortsCount)), [curators]);
  const assignedCoursesTotal = useMemo(() => sumValues(curators.map((curator) => curator.assignedCoursesCount)), [curators]);
  const unassignedCohorts = useMemo(() => cohorts.filter((cohort) => !cohort.teacherId).length, [cohorts]);
  const coverage = cohorts.length > 0 ? (assignedCohortsTotal / cohorts.length) * 100 : 0;

  const selectUser = (user: OnlineAdminUserSummary) => {
    setSelectedUserId(user.id);
    setSelectedCuratorId(user.curatorId ?? null);
    setFormMessage(null);
    setFormError(null);
    setAssignmentMessage(null);
    setAssignmentError(null);
    setAccessMessage(null);
    setAccessError(null);
    setScopeMessage(null);
    setScopeError(null);
    setTemporaryPassword("");
  };

  const selectCurator = (curator: OnlineAdminCuratorSummary) => {
    setSelectedCuratorId(curator.id);
    setSelectedUserId(curator.userId);
    setFormMessage(null);
    setFormError(null);
    setAssignmentMessage(null);
    setAssignmentError(null);
    setAccessMessage(null);
    setAccessError(null);
    setScopeMessage(null);
    setScopeError(null);
    setTemporaryPassword("");
  };

  const onSaveStudentProfile = async () => {
    if (!selectedUser?.studentProfile?.id) {
      setStudentProfileMessage(null);
      setStudentProfileError("Student profile is not provisioned for the selected user.");
      return;
    }
    setStudentProfileMessage(null);
    setStudentProfileError(null);
    try {
      await updateStudentProfile({
        profileId: selectedUser.studentProfile.id,
        body: {
          employeeId: studentProfileForm.employeeId.trim(),
          department: studentProfileForm.department.trim(),
          teamName: studentProfileForm.teamName.trim(),
          officeLocation: studentProfileForm.officeLocation.trim(),
          jobTitle: studentProfileForm.jobTitle.trim(),
          managerName: studentProfileForm.managerName.trim(),
          phone: studentProfileForm.phone.trim(),
          employmentStatus: studentProfileForm.employmentStatus,
          hiredAt: studentProfileForm.hiredAt || null,
        },
      }).unwrap();
      setStudentProfileMessage("Student profile updated.");
    } catch (error) {
      setStudentProfileError(errorMessageFrom(error, "Failed to update the student profile."));
    }
  };

  const onSaveInstructorProfile = async () => {
    if (!selectedCurator) {
      setInstructorProfileMessage(null);
      setInstructorProfileError("Select an instructor first.");
      return;
    }
    const payload = {
      department: instructorProfileForm.department.trim(),
      jobTitle: instructorProfileForm.jobTitle.trim(),
      bio: instructorProfileForm.bio.trim(),
      expertiseAreas: parseCommaSeparated(instructorProfileForm.expertiseAreas),
      spokenLanguages: parseCommaSeparated(instructorProfileForm.spokenLanguages),
      canAuthor: instructorProfileForm.canAuthor,
      canReview: instructorProfileForm.canReview,
      canPublish: instructorProfileForm.canPublish,
      canGenerateWithAi: instructorProfileForm.canGenerateWithAi,
      canManageAssessments: instructorProfileForm.canManageAssessments,
    };
    setInstructorProfileMessage(null);
    setInstructorProfileError(null);
    try {
      if (selectedCurator.instructorProfile?.id) {
        await updateInstructorProfile({
          profileId: selectedCurator.instructorProfile.id,
          body: payload,
        }).unwrap();
      } else {
        await createInstructorProfile({
          teacherId: selectedCurator.id,
          ...payload,
        }).unwrap();
      }
      setInstructorProfileMessage("Instructor profile updated.");
    } catch (error) {
      setInstructorProfileError(errorMessageFrom(error, "Failed to save the instructor profile."));
    }
  };

  const onDeleteInstructorProfile = async () => {
    if (!selectedCurator?.instructorProfile?.id) return;
    setInstructorProfileMessage(null);
    setInstructorProfileError(null);
    try {
      await deleteInstructorProfile(selectedCurator.instructorProfile.id).unwrap();
      setInstructorProfileMessage("Instructor capability profile removed.");
    } catch (error) {
      setInstructorProfileError(errorMessageFrom(error, "Failed to remove the instructor profile."));
    }
  };

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedUser) {
      setFormError("Select a registered user first.");
      return;
    }

    const payload = normalizeForm(form);
    if (!payload.firstName || !payload.lastName || !payload.schoolEmail || !payload.shortName) {
      setFormError("First name, last name, school email, and short name are required.");
      return;
    }

    setFormMessage(null);
    setFormError(null);

    try {
      if (selectedCurator) {
        const result = await updateCurator({ curatorId: selectedCurator.id, body: payload }).unwrap();
        setSelectedCuratorId(result.id);
        setSelectedUserId(result.userId);
        setFormMessage("Instructor profile updated.");
      } else {
        const result = await createCurator({ userId: selectedUser.id, ...payload }).unwrap();
        setSelectedCuratorId(result.id);
        setSelectedUserId(result.userId);
        setFormMessage("Instructor access granted.");
      }
    } catch (error) {
      setFormError(errorMessageFrom(error, "Failed to save instructor profile."));
    }
  };

  const onRemoveCurator = async () => {
    if (!selectedCurator) return;
    setFormMessage(null);
    setFormError(null);
    try {
      await deleteCurator(selectedCurator.id).unwrap();
      setSelectedCuratorId(null);
      setFormMessage("Instructor access removed.");
    } catch (error) {
      setFormError(errorMessageFrom(error, "Failed to remove instructor access."));
    }
  };

  const onToggleAssignment = async (cohort: OnlineCohortCard) => {
    if (!selectedCurator) {
      setAssignmentError("Select or create an instructor profile first.");
      return;
    }

    setBusyCohortId(cohort.id);
    setAssignmentMessage(null);
    setAssignmentError(null);
    const isUnassign = cohort.teacherId === selectedCurator.id;

    try {
      await assignCurator({ cohortId: cohort.id, body: { curatorId: isUnassign ? null : selectedCurator.id } }).unwrap();
      setAssignmentMessage(isUnassign ? `Removed ${cohort.groupCode} from ${selectedCurator.fullName}.` : `Assigned ${cohort.groupCode} to ${selectedCurator.fullName}.`);
    } catch (error) {
      setAssignmentError(errorMessageFrom(error, "Failed to update cohort assignment."));
    } finally {
      setBusyCohortId(null);
    }
  };

  const lifecycleRestricted = !!selectedUser && (selectedUser.isAdmin || selectedUser.isSuperuser);

  const onToggleUserStatus = async () => {
    if (!selectedUser) return;
    setAccessMessage(null);
    setAccessError(null);

    try {
      const updatedUser = await updateUserStatus({
        userId: selectedUser.id,
        body: { isActive: !selectedUser.isActive },
      }).unwrap();
      setAccessMessage(updatedUser.isActive ? "Account reactivated." : "Account deactivated.");
    } catch (error) {
      setAccessError(errorMessageFrom(error, "Failed to update account status."));
    }
  };

  const onResetTemporaryPassword = async () => {
    if (!selectedUser) return;
    if (!temporaryPassword.trim()) {
      setAccessError("Enter a temporary password before resetting access.");
      setAccessMessage(null);
      return;
    }

    setAccessMessage(null);
    setAccessError(null);

    try {
      await resetTemporaryPassword({
        userId: selectedUser.id,
        body: { temporaryPassword: temporaryPassword.trim() },
      }).unwrap();
      setAccessMessage("Temporary password updated.");
      setTemporaryPassword("");
    } catch (error) {
      setAccessError(errorMessageFrom(error, "Failed to reset temporary password."));
    }
  };

  const onCreateScopeAssignment = async () => {
    if (!selectedUser) {
      setScopeError("Select a registered user before assigning scoped accountability.");
      setScopeMessage(null);
      return;
    }

    const payload = {
      userId: selectedUser.id,
      role: scopeForm.role,
      scopeType: scopeForm.scopeType,
      note: scopeForm.note.trim(),
      isPrimary: scopeForm.isPrimary,
      isActive: true,
      courseId: scopeForm.scopeType === "course" || scopeForm.scopeType === "cohort" ? (scopeCourseId || undefined) : undefined,
      cohortId: scopeForm.scopeType === "cohort" ? (scopeForm.cohortId || undefined) : undefined,
    };
    if ((scopeForm.scopeType === "course" || scopeForm.scopeType === "cohort") && !payload.courseId) {
      setScopeError("Select a course scope before creating this assignment.");
      setScopeMessage(null);
      return;
    }
    if (scopeForm.scopeType === "cohort" && !payload.cohortId) {
      setScopeError("Select a cohort scope before creating this assignment.");
      setScopeMessage(null);
      return;
    }

    setScopeMessage(null);
    setScopeError(null);
    try {
      await createScopeAssignment(payload).unwrap();
      setScopeMessage("Scoped accountability assignment created.");
      setScopeForm((current) => ({
        ...current,
        note: "",
        cohortId: current.scopeType === "cohort" ? current.cohortId : "",
      }));
    } catch (error) {
      setScopeError(errorMessageFrom(error, "Failed to create scoped assignment."));
    }
  };

  const onToggleScopeAssignment = async (assignment: OnlineAdminScopeAssignment) => {
    setScopeMessage(null);
    setScopeError(null);
    try {
      await updateScopeAssignment({
        assignmentId: assignment.id,
        body: { isActive: !assignment.isActive },
      }).unwrap();
      setScopeMessage(assignment.isActive ? "Scoped assignment disabled." : "Scoped assignment reactivated.");
    } catch (error) {
      setScopeError(errorMessageFrom(error, "Failed to update scoped assignment."));
    }
  };

  const onDeleteScopeAssignment = async (assignmentId: number) => {
    setScopeMessage(null);
    setScopeError(null);
    try {
      await deleteScopeAssignment(assignmentId).unwrap();
      setScopeMessage("Scoped assignment removed.");
    } catch (error) {
      setScopeError(errorMessageFrom(error, "Failed to remove scoped assignment."));
    }
  };

  return (
    <div className={shared.page}>
      <section className={shared.hero}>
        <div className={shared.heroCopy}>
          <span className={shared.eyebrow}>User operations</span>
          <h1>Manage instructor access and delivery ownership</h1>
          <p>Grant instructor access to registered users, maintain delivery contact data, attach cohorts to delivery owners, and assign course-level governance roles.</p>
        </div>
        <div className={shared.heroMeta}>
          <span>{users.length} registered users</span>
          <span>{curators.length} instructor profiles</span>
          <span>{assignedCohortsTotal} cohort assignments</span>
          <span>{unassignedCohorts} unassigned cohorts</span>
        </div>
      </section>

      <section className={shared.kpiGrid}>
        <article className={shared.kpiCard}><span className={shared.kpiLabel}>Registered users</span><strong className={shared.kpiValue}>{users.length}</strong><span className={shared.kpiMeta}>Accounts available for role assignment.</span></article>
        <article className={shared.kpiCard}><span className={shared.kpiLabel}>Instructor coverage</span><strong className={shared.kpiValue}>{formatPercent(coverage)}</strong><span className={shared.kpiMeta}>Share of cohorts already staffed with an instructor.</span></article>
        <article className={shared.kpiCard}><span className={shared.kpiLabel}>Assigned courses</span><strong className={shared.kpiValue}>{assignedCoursesTotal}</strong><span className={shared.kpiMeta}>Unique course lines under instructor ownership.</span></article>
        <article className={shared.kpiCard}><span className={shared.kpiLabel}>Attention items</span><strong className={shared.kpiValue}>{unassignedCohorts}</strong><span className={shared.kpiMeta}>Cohorts still waiting for a named instructor.</span></article>
      </section>

      {(isUsersError || isCuratorsError || isCohortsError || isScopeAssignmentsError) ? (
        <p className={shared.errorText}>Failed to load one or more instructor datasets.</p>
      ) : null}

      <AdminCuratorOnboardingPanel
        registeredUsersCount={users.length}
        onCreated={(curator) => {
          setSelectedCuratorId(curator.id);
          setSelectedUserId(curator.userId);
          setFormMessage("Instructor account created and selected for assignment.");
          setFormError(null);
          setAssignmentMessage(null);
          setAssignmentError(null);
          setAccessMessage(null);
          setAccessError(null);
          setScopeMessage(null);
          setScopeError(null);
          setTemporaryPassword("");
        }}
      />

      <AdminCuratorDemoRolePanel selectedUser={selectedUser} />

      <section className={shared.panel}>
        <header className={shared.panelHeader}>
          <div>
            <h2>Scoped accountability</h2>
            <p>
              Assign manager, delivery, review, or compliance responsibilities at academy, course, or cohort scope.
              This gives the platform a reusable enterprise access layer without hard-coding bank-only roles.
            </p>
          </div>
          <span className={shared.sectionHint}>
            {selectedUser ? selectedUser.fullName : "Select a user first"}
          </span>
        </header>

        <div className={styles.formGrid}>
          <label className={styles.field}>
            <span className={shared.fieldLabel}>Role</span>
            <select
              className={shared.select}
              value={scopeForm.role}
              onChange={(event) =>
                setScopeForm((current) => ({ ...current, role: event.currentTarget.value as ScopeRole }))
              }
            >
              <option value="manager">Manager</option>
              <option value="delivery_manager">Delivery manager</option>
              <option value="compliance_manager">Compliance manager</option>
              <option value="review_manager">Review manager</option>
            </select>
          </label>
          <label className={styles.field}>
            <span className={shared.fieldLabel}>Scope type</span>
            <select
              className={shared.select}
              value={scopeForm.scopeType}
              onChange={(event) =>
                setScopeForm((current) => ({
                  ...current,
                  scopeType: event.currentTarget.value as ScopeType,
                  cohortId: "",
                  courseId:
                    event.currentTarget.value === "academy" ? "" : current.courseId || courseId || "",
                }))
              }
            >
              <option value="academy">Academy-wide</option>
              <option value="course">Course</option>
              <option value="cohort">Cohort</option>
            </select>
          </label>
          {scopeForm.scopeType !== "academy" ? (
            <label className={styles.field}>
              <span className={shared.fieldLabel}>Course scope</span>
              <select
                className={shared.select}
                value={scopeCourseId}
                onChange={(event) =>
                  setScopeForm((current) => ({
                    ...current,
                    courseId: event.currentTarget.value ? Number(event.currentTarget.value) : "",
                    cohortId: "",
                  }))
                }
              >
                <option value="">Select course</option>
                {courses.map((course) => (
                  <option key={course.id} value={course.id}>
                    {courseDisplayTitle(course)}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
          {scopeForm.scopeType === "cohort" ? (
            <label className={styles.field}>
              <span className={shared.fieldLabel}>Cohort scope</span>
              <select
                className={shared.select}
                value={scopeForm.cohortId}
                onChange={(event) =>
                  setScopeForm((current) => ({
                    ...current,
                    cohortId: event.currentTarget.value ? Number(event.currentTarget.value) : "",
                  }))
                }
              >
                <option value="">Select cohort</option>
                {scopeCohorts.map((cohort) => (
                  <option key={cohort.id} value={cohort.id}>
                    {cohort.groupCode} · {cohort.groupName}
                  </option>
                ))}
              </select>
            </label>
          ) : null}
          <label className={styles.field}>
            <span className={shared.fieldLabel}>Delivery note</span>
            <input
              className={shared.inlineInput}
              value={scopeForm.note}
              onChange={(event) => setScopeForm((current) => ({ ...current, note: event.currentTarget.value }))}
              placeholder="Primary point of contact, escalation note, or reviewer context"
            />
          </label>
        </div>

        <div className={styles.inlineActionGroup}>
          <label className={styles.checkboxRow}>
            <input
              type="checkbox"
              checked={scopeForm.isPrimary}
              onChange={(event) =>
                setScopeForm((current) => ({ ...current, isPrimary: event.currentTarget.checked }))
              }
            />
            <span>Mark as primary assignment</span>
          </label>
          <button
            type="button"
            className={styles.primaryButton}
            onClick={onCreateScopeAssignment}
            disabled={!selectedUser || createScopeAssignmentState.isLoading}
          >
            {createScopeAssignmentState.isLoading ? "Saving..." : "Add scoped assignment"}
          </button>
        </div>

        {scopeMessage ? <p className={styles.successText}>{scopeMessage}</p> : null}
        {scopeError ? <p className={shared.errorText}>{scopeError}</p> : null}
        {isScopeAssignmentsLoading ? <p className={shared.emptyText}>Loading scoped assignments...</p> : null}

        <div className={shared.list}>
          {scopeAssignments.length === 0 && !isScopeAssignmentsLoading ? (
            <p className={shared.emptyText}>No scoped assignments for the selected user and course scope.</p>
          ) : null}
          {scopeAssignments.map((assignment) => (
            <article key={assignment.id} className={shared.listItem}>
              <strong>
                {assignment.roleLabel} · {assignment.scopeLabel}
              </strong>
              <span>
                {assignment.user.fullName} · {assignment.isPrimary ? "Primary" : "Secondary"} ·{" "}
                {assignment.isActive ? "Active" : "Inactive"}
              </span>
              <span>{assignment.note || "No assignment note provided."}</span>
              <span>
                Added {formatDateTime(assignment.createdAt)}
                {assignment.createdByEmail ? ` · by ${assignment.createdByEmail}` : ""}
              </span>
              <div className={styles.inlineActionGroup}>
                <button
                  type="button"
                  className={styles.secondaryButton}
                  onClick={() => onToggleScopeAssignment(assignment)}
                  disabled={updateScopeAssignmentState.isLoading}
                >
                  {assignment.isActive ? "Disable" : "Enable"}
                </button>
                <button
                  type="button"
                  className={styles.dangerButton}
                  onClick={() => onDeleteScopeAssignment(assignment.id)}
                  disabled={deleteScopeAssignmentState.isLoading}
                >
                  Remove
                </button>
              </div>
            </article>
          ))}
        </div>
      </section>

      <div className={shared.grid2}>
        <section className={shared.panel}>
          <header className={shared.panelHeader}>
            <div><h2>Registered users</h2><p>Pick a user to review current roles or turn that account into an instructor profile.</p></div>
            <span className={shared.sectionHint}>{filteredUsers.length} visible</span>
          </header>
          <div className={styles.controlGrid}>
            <label className={shared.selectWrap}>
              <span className={shared.fieldLabel}>Find user</span>
              <input type="search" className={shared.inlineInput} value={userSearch} onChange={(event) => setUserSearch(event.currentTarget.value)} placeholder="Search by name or email" />
            </label>
            <label className={shared.selectWrap}>
              <span className={shared.fieldLabel}>Role scope</span>
              <select className={shared.select} value={roleFilter} onChange={(event) => setRoleFilter(event.currentTarget.value as UserRoleFilter)}>
                <option value="">All registered users</option>
                <option value="curator">Existing instructors</option>
                <option value="admin">Administrators</option>
                <option value="student">Students</option>
              </select>
            </label>
          </div>
          {isUsersLoading ? <p className={shared.emptyText}>Loading registered users...</p> : null}
          <div className={styles.directoryList}>
            {filteredUsers.length === 0 ? <p className={shared.emptyText}>No users match the current filter.</p> : null}
            {filteredUsers.map((user) => (
              <button key={user.id} type="button" onClick={() => selectUser(user)} className={`${styles.directoryItem} ${user.id === selectedUserId ? styles.directoryItemActive : ""}`}>
                <div className={styles.directoryHeader}>
                  <div className={styles.directoryCopy}><strong>{user.fullName}</strong><span>{user.email}</span></div>
                  <span className={styles.directoryValue}>{user.assignedCohortsCount}</span>
                </div>
                <div className={styles.badgeRow}>
                  <span className={badgeClassFor(user, shared)}>{user.isCurator ? "Instructor" : user.isAdmin ? "Admin" : user.isStudent ? "Student" : "Registered"}</span>
                  {!user.isActive ? <span className={shared.warnPill}>Inactive</span> : null}
                  {!user.isCurator ? <span className={shared.linkPill}>Eligible for instructor access</span> : null}
                </div>
                <div className={styles.directoryMeta}><span>{user.username || "Username not set"}</span><span>{user.assignedCoursesCount} courses</span></div>
              </button>
            ))}
          </div>
        </section>

        <section className={shared.panel}>
          <header className={shared.panelHeader}>
            <div><h2>Instructor directory</h2><p>Inspect the active instructor registry, workload, and ownership footprint.</p></div>
            <Link to="/courses" className={shared.linkPill}>Open course control</Link>
          </header>
          <label className={shared.selectWrap}>
            <span className={shared.fieldLabel}>Find instructor</span>
            <input type="search" className={shared.inlineInput} value={curatorSearch} onChange={(event) => setCuratorSearch(event.currentTarget.value)} placeholder="Search by instructor name or email" />
          </label>
          {isCuratorsLoading ? <p className={shared.emptyText}>Loading instructor registry...</p> : null}
          <div className={styles.directoryList}>
            {filteredCurators.length === 0 ? <p className={shared.emptyText}>No instructor profiles match the current search.</p> : null}
            {filteredCurators.map((curator) => (
              <button key={curator.id} type="button" onClick={() => selectCurator(curator)} className={`${styles.directoryItem} ${curator.id === selectedCurator?.id ? styles.directoryItemActive : ""}`}>
                <div className={styles.directoryHeader}>
                  <div className={styles.directoryCopy}><strong>{curator.fullName}</strong><span>{curator.schoolEmail}</span></div>
                  <span className={styles.directoryValue}>{curator.assignedCohortsCount}</span>
                </div>
                <div className={styles.badgeRow}>
                  <span className={shared.goodPill}>Instructor</span>
                  {curator.isAdmin ? <span className={shared.neutralPill}>Admin</span> : null}
                </div>
                <div className={styles.directoryMeta}><span>{curator.shortName}</span><span>{curator.assignedCoursesCount} courses</span><span>{curator.email}</span></div>
              </button>
            ))}
          </div>
        </section>
      </div>

      <div className={shared.grid2}>
        <section className={shared.panel}>
          <header className={shared.panelHeader}>
            <div><h2>{selectedCurator ? "Instructor profile" : "Grant instructor access"}</h2><p>{selectedCurator ? "Update instructor contact details and naming conventions." : "Create an instructor profile from the selected registered user."}</p></div>
            <span className={shared.sectionHint}>{selectedUser?.email ?? "No user selected"}</span>
          </header>
          {selectedUser ? (
            <form className={styles.form} onSubmit={onSubmit}>
              <div className={styles.selectionSummary}>
                <article className={styles.summaryCard}><span className={shared.fieldLabel}>Selected account</span><strong>{selectedUser.fullName}</strong><span>{selectedUser.email}</span></article>
                <article className={styles.summaryCard}><span className={shared.fieldLabel}>Access state</span><strong>{selectedCurator ? "Instructor access enabled" : "Instructor access not granted"}</strong><span>{selectedCurator ? `${selectedCurator.assignedCohortsCount} cohorts assigned` : "Save profile to unlock instructor workspace access"}</span></article>
              </div>
              <div className={styles.formGrid}>
                <label className={styles.field}><span className={shared.fieldLabel}>First name</span><input type="text" className={shared.inlineInput} value={form.firstName} onChange={(event) => setForm((current) => ({ ...current, firstName: event.currentTarget.value }))} /></label>
                <label className={styles.field}><span className={shared.fieldLabel}>Last name</span><input type="text" className={shared.inlineInput} value={form.lastName} onChange={(event) => setForm((current) => ({ ...current, lastName: event.currentTarget.value }))} /></label>
                <label className={styles.field}><span className={shared.fieldLabel}>School email</span><input type="email" className={shared.inlineInput} value={form.schoolEmail} onChange={(event) => setForm((current) => ({ ...current, schoolEmail: event.currentTarget.value }))} /></label>
                <label className={styles.field}><span className={shared.fieldLabel}>Private email</span><input type="email" className={shared.inlineInput} value={form.privateEmail} onChange={(event) => setForm((current) => ({ ...current, privateEmail: event.currentTarget.value }))} placeholder="Optional" /></label>
                <label className={styles.field}><span className={shared.fieldLabel}>Phone</span><input type="text" className={shared.inlineInput} value={form.phone} onChange={(event) => setForm((current) => ({ ...current, phone: event.currentTarget.value }))} placeholder="Optional" /></label>
                <label className={styles.field}><span className={shared.fieldLabel}>Short name</span><input type="text" className={shared.inlineInput} value={form.shortName} onChange={(event) => setForm((current) => ({ ...current, shortName: event.currentTarget.value }))} /></label>
              </div>
              <div className={styles.lifecycleGrid}>
                <article className={styles.lifecycleCard}>
                  <div className={styles.lifecycleHeader}>
                    <span className={shared.fieldLabel}>Account access</span>
                    <span className={selectedUser.isActive ? shared.goodPill : shared.warnPill}>
                      {selectedUser.isActive ? "Active" : "Inactive"}
                    </span>
                  </div>
                  <strong>{selectedUser.email}</strong>
                  <span className={styles.lifecycleText}>
                    {lifecycleRestricted
                      ? "Admin accounts are protected in this panel. Use dedicated operator tooling for admin lifecycle changes."
                      : selectedUser.isCurator
                        ? "This account can sign in to instructor workspace and access assigned cohorts."
                        : "This registered account can be activated or paused before instructor access is granted."}
                  </span>
                  <div className={styles.inlineActionGroup}>
                    <button
                      type="button"
                      className={styles.secondaryButton}
                      disabled={lifecycleRestricted || userStatusState.isLoading}
                      onClick={onToggleUserStatus}
                    >
                      {userStatusState.isLoading
                        ? "Saving..."
                        : selectedUser.isActive
                          ? "Deactivate account"
                          : "Reactivate account"}
                    </button>
                  </div>
                </article>

                <article className={styles.lifecycleCard}>
                  <div className={styles.lifecycleHeader}>
                    <span className={shared.fieldLabel}>Temporary password</span>
                    <span className={shared.neutralPill}>Reset</span>
                  </div>
                  <label className={styles.field}>
                    <span className={styles.lifecycleText}>
                      Set a new temporary password for the selected user. The next login must use this value.
                    </span>
                    <input
                      type="text"
                      className={shared.inlineInput}
                      value={temporaryPassword}
                      onChange={(event) => setTemporaryPassword(event.currentTarget.value)}
                      placeholder="At least 10 chars with letters and numbers"
                      disabled={lifecycleRestricted}
                    />
                  </label>
                  <div className={styles.inlineActionGroup}>
                    <button
                      type="button"
                      className={styles.secondaryButton}
                      disabled={lifecycleRestricted || passwordResetState.isLoading}
                      onClick={onResetTemporaryPassword}
                    >
                      {passwordResetState.isLoading ? "Updating..." : "Reset temporary password"}
                    </button>
                  </div>
                </article>
              </div>
              {formMessage ? <p className={styles.successText}>{formMessage}</p> : null}
              {formError ? <p className={shared.errorText}>{formError}</p> : null}
              {accessMessage ? <p className={styles.successText}>{accessMessage}</p> : null}
              {accessError ? <p className={shared.errorText}>{accessError}</p> : null}
              <div className={styles.actionRow}>
                <button type="submit" className={styles.primaryButton} disabled={createState.isLoading || updateState.isLoading}>{createState.isLoading || updateState.isLoading ? "Saving..." : selectedCurator ? "Update instructor profile" : "Grant instructor access"}</button>
                {selectedCurator ? <button type="button" className={styles.dangerButton} disabled={deleteState.isLoading || selectedCurator.assignedCohortsCount > 0} onClick={onRemoveCurator}>{deleteState.isLoading ? "Removing..." : "Remove instructor access"}</button> : null}
              </div>
              {selectedCurator && selectedCurator.assignedCohortsCount > 0 ? <p className={styles.helperText}>Unassign the instructor from all cohorts before removing access.</p> : null}
            </form>
          ) : <p className={shared.emptyText}>Select a user to open instructor profile controls.</p>}
        </section>

        <section className={shared.panel}>
          <header className={shared.panelHeader}>
            <div><h2>Cohort assignments</h2><p>Attach cohorts to the selected instructor. Assigned cohorts become visible inside instructor workspace.</p></div>
            {selectedCurator ? <span className={shared.sectionHint}>{selectedCurator.fullName}</span> : null}
          </header>
          <div className={styles.controlGrid}>
            <label className={shared.selectWrap}>
              <span className={shared.fieldLabel}>Delivery course scope</span>
              <select className={shared.select} value={courseId} onChange={(event) => setCourseId(event.currentTarget.value ? Number(event.currentTarget.value) : "")}>
                <option value="">All courses</option>
                {courses.map((course) => <option key={course.id} value={course.id}>{courseDisplayTitle(course)}</option>)}
              </select>
            </label>
            <label className={shared.selectWrap}>
              <span className={shared.fieldLabel}>Find cohort</span>
              <input type="search" className={shared.inlineInput} value={cohortSearch} onChange={(event) => setCohortSearch(event.currentTarget.value)} placeholder="Search by cohort or course" />
            </label>
          </div>
          <p className={styles.helperText}>The same course scope is reused below for owner and reviewer governance roles.</p>
          {selectedCurator ? (
            <div className={styles.selectionSummary}>
              <article className={styles.summaryCard}><span className={shared.fieldLabel}>Assigned cohorts</span><strong>{selectedCurator.assignedCohortsCount}</strong><span>{selectedCurator.assignedCoursesCount} courses covered</span></article>
              <article className={styles.summaryCard}><span className={shared.fieldLabel}>Current groups</span><strong>{selectedCurator.assignedCohorts.length > 0 ? selectedCurator.assignedCohorts.slice(0, 3).map((cohort) => cohort.groupCode).join(", ") : "No groups assigned"}</strong><span>{selectedCurator.assignedCohorts.length > 3 ? `${selectedCurator.assignedCohorts.length - 3} more groups on this profile` : "Assignments update teacher workspace visibility"}</span></article>
            </div>
          ) : <p className={shared.emptyText}>Select or create an instructor profile before assigning cohorts.</p>}
          {assignmentMessage ? <p className={styles.successText}>{assignmentMessage}</p> : null}
          {assignmentError ? <p className={shared.errorText}>{assignmentError}</p> : null}
          {isCohortsLoading ? <p className={shared.emptyText}>Loading cohorts...</p> : null}
          <div className={shared.tableWrap}>
            <table className={shared.table}>
              <thead><tr><th>Cohort</th><th>Current instructor</th><th>Students</th><th>Attendance</th><th>Next session</th><th>Action</th></tr></thead>
              <tbody>
                {filteredCohorts.length === 0 ? <tr><td colSpan={6}><p className={shared.emptyText}>No cohorts match the current filter.</p></td></tr> : null}
                {filteredCohorts.map((cohort) => {
                  const currentCurator = cohort.teacherId ? curatorMap.get(cohort.teacherId) ?? null : null;
                  const isAssigned = selectedCurator?.id === cohort.teacherId;
                  const actionLabel = isAssigned ? "Unassign" : cohort.teacherId ? "Reassign" : "Assign";
                  return (
                    <tr key={cohort.id}>
                      <td><div className={shared.tableCellStack}><strong>{cohort.groupCode} · {cohort.groupName}</strong><span>{cohort.courseTitleDe}</span></div></td>
                      <td><div className={shared.tableCellStack}><strong>{currentCurator?.fullName ?? "Not assigned"}</strong><span>{currentCurator?.schoolEmail ?? "Open staffing slot"}</span></div></td>
                      <td>{cohort.studentsCount}</td>
                      <td>{formatPercent(cohort.attendancePercent)}</td>
                      <td>{formatDateTime(cohort.nearestSessionAt)}</td>
                      <td><button type="button" className={styles.secondaryButton} disabled={!selectedCurator || assignState.isLoading || busyCohortId === cohort.id} onClick={() => onToggleAssignment(cohort)}>{busyCohortId === cohort.id ? "Saving..." : actionLabel}</button></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      </div>

      <div className={shared.grid2}>
        <section className={shared.panel}>
          <header className={shared.panelHeader}>
            <div>
              <h2>Student registry profile</h2>
              <p>Maintain standard student metadata used for search, programs, recommendations, and manager reporting.</p>
            </div>
            <span className={shared.sectionHint}>
              {selectedUser?.isStudent ? "Student account selected" : "Select a student"}
            </span>
          </header>

          {selectedUser?.isStudent && selectedUser.studentProfile ? (
            <>
              <div className={styles.formGrid}>
                <label className={styles.field}>
                  <span className={shared.fieldLabel}>Employee ID</span>
                  <input className={shared.inlineInput} value={studentProfileForm.employeeId} onChange={(event) => setStudentProfileForm((current) => ({ ...current, employeeId: event.currentTarget.value }))} />
                </label>
                <label className={styles.field}>
                  <span className={shared.fieldLabel}>Department</span>
                  <input className={shared.inlineInput} value={studentProfileForm.department} onChange={(event) => setStudentProfileForm((current) => ({ ...current, department: event.currentTarget.value }))} />
                </label>
                <label className={styles.field}>
                  <span className={shared.fieldLabel}>Team</span>
                  <input className={shared.inlineInput} value={studentProfileForm.teamName} onChange={(event) => setStudentProfileForm((current) => ({ ...current, teamName: event.currentTarget.value }))} />
                </label>
                <label className={styles.field}>
                  <span className={shared.fieldLabel}>Office</span>
                  <input className={shared.inlineInput} value={studentProfileForm.officeLocation} onChange={(event) => setStudentProfileForm((current) => ({ ...current, officeLocation: event.currentTarget.value }))} />
                </label>
                <label className={styles.field}>
                  <span className={shared.fieldLabel}>Job title</span>
                  <input className={shared.inlineInput} value={studentProfileForm.jobTitle} onChange={(event) => setStudentProfileForm((current) => ({ ...current, jobTitle: event.currentTarget.value }))} />
                </label>
                <label className={styles.field}>
                  <span className={shared.fieldLabel}>Manager</span>
                  <input className={shared.inlineInput} value={studentProfileForm.managerName} onChange={(event) => setStudentProfileForm((current) => ({ ...current, managerName: event.currentTarget.value }))} />
                </label>
                <label className={styles.field}>
                  <span className={shared.fieldLabel}>Phone</span>
                  <input className={shared.inlineInput} value={studentProfileForm.phone} onChange={(event) => setStudentProfileForm((current) => ({ ...current, phone: event.currentTarget.value }))} />
                </label>
                <label className={styles.field}>
                  <span className={shared.fieldLabel}>Employment status</span>
                  <select className={shared.select} value={studentProfileForm.employmentStatus} onChange={(event) => setStudentProfileForm((current) => ({ ...current, employmentStatus: event.currentTarget.value as StudentProfileFormState["employmentStatus"] }))}>
                    <option value="active">Active</option>
                    <option value="on_leave">On leave</option>
                    <option value="contractor">Contractor</option>
                    <option value="inactive">Inactive</option>
                  </select>
                </label>
                <label className={styles.field}>
                  <span className={shared.fieldLabel}>Hire date</span>
                  <input className={shared.inlineInput} type="date" value={studentProfileForm.hiredAt} onChange={(event) => setStudentProfileForm((current) => ({ ...current, hiredAt: event.currentTarget.value }))} />
                </label>
              </div>
              {studentProfileMessage ? <p className={styles.successText}>{studentProfileMessage}</p> : null}
              {studentProfileError ? <p className={shared.errorText}>{studentProfileError}</p> : null}
              <div className={styles.inlineActionGroup}>
                <button type="button" className={styles.primaryButton} disabled={updateStudentProfileState.isLoading} onClick={onSaveStudentProfile}>
                  {updateStudentProfileState.isLoading ? "Saving..." : "Save student profile"}
                </button>
                <span className={shared.sectionHint}>
                  Used for search, learning programs, and manager/compliance reporting.
                </span>
              </div>
            </>
          ) : (
            <p className={shared.emptyText}>Select a student account to maintain employment and organizational metadata.</p>
          )}
        </section>

        <section className={shared.panel}>
          <header className={shared.panelHeader}>
            <div>
              <h2>Author / instructor profile</h2>
              <p>Control authoring permissions, AI assistance, assessment authority, and searchable expertise for the selected instructor.</p>
            </div>
            <span className={shared.sectionHint}>
              {selectedCurator ? selectedCurator.fullName : "Select an instructor"}
            </span>
          </header>

          {selectedCurator ? (
            <>
              <div className={styles.formGrid}>
                <label className={styles.field}>
                  <span className={shared.fieldLabel}>Department</span>
                  <input className={shared.inlineInput} value={instructorProfileForm.department} onChange={(event) => setInstructorProfileForm((current) => ({ ...current, department: event.currentTarget.value }))} />
                </label>
                <label className={styles.field}>
                  <span className={shared.fieldLabel}>Job title</span>
                  <input className={shared.inlineInput} value={instructorProfileForm.jobTitle} onChange={(event) => setInstructorProfileForm((current) => ({ ...current, jobTitle: event.currentTarget.value }))} />
                </label>
                <label className={styles.field}>
                  <span className={shared.fieldLabel}>Expertise areas</span>
                  <input className={shared.inlineInput} value={instructorProfileForm.expertiseAreas} onChange={(event) => setInstructorProfileForm((current) => ({ ...current, expertiseAreas: event.currentTarget.value }))} placeholder="Python, risk, compliance, data..." />
                </label>
                <label className={styles.field}>
                  <span className={shared.fieldLabel}>Languages</span>
                  <input className={shared.inlineInput} value={instructorProfileForm.spokenLanguages} onChange={(event) => setInstructorProfileForm((current) => ({ ...current, spokenLanguages: event.currentTarget.value }))} placeholder="English, German" />
                </label>
                <label className={styles.field} style={{ gridColumn: "1 / -1" }}>
                  <span className={shared.fieldLabel}>Bio</span>
                  <textarea className={shared.textarea ?? shared.inlineInput} value={instructorProfileForm.bio} onChange={(event) => setInstructorProfileForm((current) => ({ ...current, bio: event.currentTarget.value }))} rows={4} />
                </label>
              </div>
              <div className={styles.badgeRow}>
                <label className={styles.checkboxRow}><input type="checkbox" checked={instructorProfileForm.canAuthor} onChange={(event) => setInstructorProfileForm((current) => ({ ...current, canAuthor: event.currentTarget.checked }))} /><span>Can author courses</span></label>
                <label className={styles.checkboxRow}><input type="checkbox" checked={instructorProfileForm.canReview} onChange={(event) => setInstructorProfileForm((current) => ({ ...current, canReview: event.currentTarget.checked }))} /><span>Can review content</span></label>
                <label className={styles.checkboxRow}><input type="checkbox" checked={instructorProfileForm.canPublish} onChange={(event) => setInstructorProfileForm((current) => ({ ...current, canPublish: event.currentTarget.checked }))} /><span>Can publish</span></label>
                <label className={styles.checkboxRow}><input type="checkbox" checked={instructorProfileForm.canGenerateWithAi} onChange={(event) => setInstructorProfileForm((current) => ({ ...current, canGenerateWithAi: event.currentTarget.checked }))} /><span>Can use AI generation</span></label>
                <label className={styles.checkboxRow}><input type="checkbox" checked={instructorProfileForm.canManageAssessments} onChange={(event) => setInstructorProfileForm((current) => ({ ...current, canManageAssessments: event.currentTarget.checked }))} /><span>Can manage tests and exams</span></label>
              </div>
              {instructorProfileMessage ? <p className={styles.successText}>{instructorProfileMessage}</p> : null}
              {instructorProfileError ? <p className={shared.errorText}>{instructorProfileError}</p> : null}
              <div className={styles.inlineActionGroup}>
                <button type="button" className={styles.primaryButton} disabled={createInstructorProfileState.isLoading || updateInstructorProfileState.isLoading} onClick={onSaveInstructorProfile}>
                  {createInstructorProfileState.isLoading || updateInstructorProfileState.isLoading ? "Saving..." : selectedCurator.instructorProfile ? "Save instructor profile" : "Create instructor profile"}
                </button>
                {selectedCurator.instructorProfile ? (
                  <button type="button" className={styles.dangerButton} disabled={deleteInstructorProfileState.isLoading} onClick={onDeleteInstructorProfile}>
                    {deleteInstructorProfileState.isLoading ? "Removing..." : "Remove instructor profile"}
                  </button>
                ) : null}
              </div>
            </>
          ) : (
            <p className={shared.emptyText}>Select an instructor to configure authoring and instructor capabilities.</p>
          )}
        </section>
      </div>

      <AdminCuratorCourseRolesPanel
        selectedUser={selectedUser}
        courses={courses}
        courseScopeId={courseId}
        onCourseScopeChange={setCourseId}
      />
    </div>
  );
};

export default AdminCuratorsPage;
