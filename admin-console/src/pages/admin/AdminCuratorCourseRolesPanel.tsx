import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";

import {
  useCreateTrainingAdminCourseRoleAssignmentMutation,
  useDeleteTrainingAdminCourseRoleAssignmentMutation,
  useGetTrainingAdminCourseRoleAssignmentsQuery,
  useUpdateTrainingAdminCourseRoleAssignmentMutation,
} from "@/bll/training/training.service";
import type { TrainingAdminCourseRoleAssignment, TrainingCourseRole } from "@/bll/training/training.type";
import type { OnlineAdminUserSummary, OnlineCourseCard } from "@/bll/online/online.type";
import shared from "./AdminPagesShared.module.css";
import styles from "./AdminCuratorCourseRolesPanel.module.css";
import { courseDisplayTitle, formatDateTime } from "./adminPageUtils";

type ManagedCourseRole = TrainingCourseRole;

type CreateFormState = {
  courseId: string;
  role: ManagedCourseRole;
  isPrimary: boolean;
  responseSlaHours: string;
};

type EditFormState = {
  role: ManagedCourseRole;
  isPrimary: boolean;
  responseSlaHours: string;
};

type AdminCuratorCourseRolesPanelProps = {
  selectedUser: OnlineAdminUserSummary | null;
  courses: OnlineCourseCard[];
  courseScopeId: number | "";
  onCourseScopeChange: (value: number | "") => void;
};

const EMPTY_CREATE_FORM = (courseScopeId: number | "", courses: OnlineCourseCard[]): CreateFormState => ({
  courseId: courseScopeId ? String(courseScopeId) : courses[0] ? String(courses[0].id) : "",
  role: "owner",
  isPrimary: true,
  responseSlaHours: "24",
});

const resolveApiErrorMessage = (error: unknown, fallback: string) => {
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

const roleLabel: Record<ManagedCourseRole, string> = {
  owner: "Course owner",
  reviewer: "Reviewer",
  instructor: "Instructor",
};

const rolePillClassName = (role: ManagedCourseRole) => {
  if (role === "owner") return `${shared.goodPill} ${styles.rolePill}`;
  if (role === "reviewer") return `${shared.neutralPill} ${styles.rolePill}`;
  return `${shared.linkPill} ${styles.rolePill}`;
};

type EligibilityPolicy = {
  allowedRoles: ManagedCourseRole[];
  toneClassName: string;
  headline: string;
  detail: string;
};

const buildEligibilityPolicy = (selectedUser: OnlineAdminUserSummary | null): EligibilityPolicy => {
  if (!selectedUser) {
    return {
      allowedRoles: [],
      toneClassName: shared.neutralPill,
      headline: "Select a user",
      detail: "Choose a registered account first to see which course roles can be assigned.",
    };
  }

  if (!selectedUser.isActive) {
    return {
      allowedRoles: [],
      toneClassName: shared.warnPill,
      headline: "Inactive account",
      detail: "Reactivate this account before assigning any course role.",
    };
  }

  if (selectedUser.isCurator) {
    return {
      allowedRoles: ["owner", "reviewer", "instructor"],
      toneClassName: shared.goodPill,
      headline: "Instructor delivery access",
      detail: "Active instructors can hold owner, reviewer, and instructor assignments.",
    };
  }

  if (selectedUser.isAdmin || selectedUser.isSuperuser) {
    return {
      allowedRoles: ["owner", "reviewer"],
      toneClassName: shared.neutralPill,
      headline: "Admin governance access",
      detail: "Active admin accounts can own or review a course, but instructor assignments require instructor access.",
    };
  }

  return {
    allowedRoles: [],
    toneClassName: shared.warnPill,
    headline: "No course-role eligibility",
    detail: "This account needs instructor access before it can be used for delivery or course accountability.",
  };
};

export const AdminCuratorCourseRolesPanel = ({
  selectedUser,
  courses,
  courseScopeId,
  onCourseScopeChange,
}: AdminCuratorCourseRolesPanelProps) => {
  const [createForm, setCreateForm] = useState<CreateFormState>(() => EMPTY_CREATE_FORM(courseScopeId, courses));
  const [editingAssignmentId, setEditingAssignmentId] = useState<number | null>(null);
  const [editForm, setEditForm] = useState<EditFormState | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const {
    data,
    isLoading,
    isError,
  } = useGetTrainingAdminCourseRoleAssignmentsQuery(
    selectedUser ? { userId: selectedUser.id } : undefined,
    { skip: !selectedUser }
  );
  const [createAssignment, createState] = useCreateTrainingAdminCourseRoleAssignmentMutation();
  const [updateAssignment, updateState] = useUpdateTrainingAdminCourseRoleAssignmentMutation();
  const [deleteAssignment, deleteState] = useDeleteTrainingAdminCourseRoleAssignmentMutation();

  const eligibility = useMemo(() => buildEligibilityPolicy(selectedUser), [selectedUser]);
  const allowedRoles = eligibility.allowedRoles;
  const canAssignRole = (role: ManagedCourseRole) => allowedRoles.includes(role);

  const assignments = useMemo(
    () =>
      [...(data?.results ?? [])].sort((left, right) => {
          if (left.course.slug !== right.course.slug) return left.course.slug.localeCompare(right.course.slug);
          if (left.role !== right.role) return left.role.localeCompare(right.role);
          if (left.is_primary !== right.is_primary) return left.is_primary ? -1 : 1;
          return left.created_at.localeCompare(right.created_at);
        }),
    [data]
  );

  const visibleAssignments = useMemo(
    () => assignments.filter((assignment) => (!courseScopeId ? true : assignment.course.id === courseScopeId)),
    [assignments, courseScopeId]
  );

  const ownerAssignments = useMemo(
    () => assignments.filter((assignment) => assignment.role === "owner").length,
    [assignments]
  );
  const reviewerAssignments = useMemo(
    () => assignments.filter((assignment) => assignment.role === "reviewer").length,
    [assignments]
  );
  const instructorAssignments = useMemo(
    () => assignments.filter((assignment) => assignment.role === "instructor").length,
    [assignments]
  );
  const primaryAssignments = useMemo(() => assignments.filter((assignment) => assignment.is_primary).length, [assignments]);

  const editingAssignment = useMemo(
    () => assignments.find((assignment) => assignment.id === editingAssignmentId) ?? null,
    [assignments, editingAssignmentId]
  );

  useEffect(() => {
    if (!editingAssignment) {
      setEditForm(null);
      return;
    }
    setEditForm({
      role: editingAssignment.role,
      isPrimary: editingAssignment.is_primary,
      responseSlaHours: String(editingAssignment.response_sla_hours),
    });
  }, [editingAssignment]);

  useEffect(() => {
    setCreateForm(EMPTY_CREATE_FORM(courseScopeId, courses));
    setEditingAssignmentId(null);
    setEditForm(null);
    setActionError(null);
    setActionMessage(null);
  }, [courseScopeId, courses, selectedUser?.id]);

  const busy = createState.isLoading || updateState.isLoading || deleteState.isLoading;
  const governanceScopeQuery = courseScopeId ? `?courseId=${courseScopeId}` : "";

  const resetCreateForm = () => {
    setCreateForm(EMPTY_CREATE_FORM(courseScopeId, courses));
    setActionError(null);
  };

  const resetEditForm = () => {
    setEditingAssignmentId(null);
    setEditForm(null);
    setActionError(null);
  };

  const onCreateSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedUser) {
      setActionError("Select a registered user before assigning governance roles.");
      setActionMessage(null);
      return;
    }
    if (!selectedUser.isActive) {
      setActionError("Reactivate this account before assigning governance ownership.");
      setActionMessage(null);
      return;
    }
    if (!canAssignRole(createForm.role)) {
      setActionError(`This account cannot receive the ${roleLabel[createForm.role]} role under the current access policy.`);
      setActionMessage(null);
      return;
    }

    const courseId = Number(createForm.courseId);
    const responseSlaHours = Number(createForm.responseSlaHours);
    if (!Number.isInteger(courseId) || courseId <= 0) {
      setActionError("Choose a valid course before creating an assignment.");
      setActionMessage(null);
      return;
    }
    if (!Number.isInteger(responseSlaHours) || responseSlaHours < 1 || responseSlaHours > 168) {
      setActionError("Response SLA must stay between 1 and 168 hours.");
      setActionMessage(null);
      return;
    }

    setActionError(null);
    setActionMessage(null);
    try {
      await createAssignment({
        user_id: selectedUser.id,
        course_id: courseId,
        role: createForm.role,
        is_primary: createForm.isPrimary,
        response_sla_hours: responseSlaHours,
      }).unwrap();
      resetCreateForm();
      setActionMessage(`${roleLabel[createForm.role]} assigned to ${selectedUser.fullName}.`);
    } catch (error) {
      setActionError(resolveApiErrorMessage(error, "Failed to assign course governance role."));
    }
  };

  const onEditSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!editingAssignmentId || !editForm) return;

    const responseSlaHours = Number(editForm.responseSlaHours);
    if (!canAssignRole(editForm.role)) {
      setActionError(`This account cannot hold the ${roleLabel[editForm.role]} role under the current access policy.`);
      setActionMessage(null);
      return;
    }
    if (!Number.isInteger(responseSlaHours) || responseSlaHours < 1 || responseSlaHours > 168) {
      setActionError("Response SLA must stay between 1 and 168 hours.");
      setActionMessage(null);
      return;
    }

    setActionError(null);
    setActionMessage(null);
    try {
      await updateAssignment({
        assignmentId: editingAssignmentId,
        body: {
          role: editForm.role,
          is_primary: editForm.isPrimary,
          response_sla_hours: responseSlaHours,
        },
      }).unwrap();
      setActionMessage("Governance role assignment updated.");
      resetEditForm();
    } catch (error) {
      setActionError(resolveApiErrorMessage(error, "Failed to update governance role assignment."));
    }
  };

  const onDelete = async (assignment: TrainingAdminCourseRoleAssignment) => {
    if (!window.confirm(`Delete the ${roleLabel[assignment.role]} assignment for ${assignment.course.title_de}?`)) {
      return;
    }

    setActionError(null);
    setActionMessage(null);
    try {
      await deleteAssignment(assignment.id).unwrap();
      if (editingAssignmentId === assignment.id) {
        resetEditForm();
      }
      setActionMessage(`${roleLabel[assignment.role]} removed from ${assignment.course.title_de}.`);
    } catch (error) {
      setActionError(resolveApiErrorMessage(error, "Failed to delete governance role assignment."));
    }
  };

  return (
    <section className={shared.panel}>
      <header className={shared.panelHeader}>
        <div>
          <h2>Course roles and accountability</h2>
          <p>
            Assign governance ownership for the selected user. Cohort delivery stays under instructor staffing above,
            while course-level accountability for content, review, and instruction lives here.
          </p>
        </div>
        <div className={styles.headerActions}>
          <Link to={`/courses${governanceScopeQuery}`} className={shared.linkPill}>
            Open courses
          </Link>
          <Link to={`/governance${governanceScopeQuery}`} className={shared.linkPill}>
            Open governance
          </Link>
          <Link to={`/knowledge${governanceScopeQuery}`} className={shared.linkPill}>
            Open knowledge
          </Link>
        </div>
      </header>

      {!selectedUser ? <p className={shared.emptyText}>Select a registered user to manage course governance roles.</p> : null}
      {selectedUser ? (
        <>
          <div className={shared.grid3}>
            <article className={shared.card}>
              <span className={shared.fieldLabel}>Selected user</span>
              <h3>{selectedUser.fullName}</h3>
              <p>{selectedUser.email}</p>
            </article>
            <article className={shared.card}>
              <span className={shared.fieldLabel}>Role coverage</span>
              <h3>
                {ownerAssignments} / {reviewerAssignments} / {instructorAssignments}
              </h3>
              <p>Owner, reviewer, and instructor assignments currently held by this user.</p>
            </article>
            <article className={shared.card}>
              <span className={shared.fieldLabel}>Primary assignments</span>
              <h3>{primaryAssignments}</h3>
              <p>Primary ownership records used by escalation and governance workflows.</p>
            </article>
          </div>

          <section className={styles.policyPanel}>
            <div className={styles.policyHeader}>
              <div>
                <span className={shared.fieldLabel}>Eligibility policy</span>
                <strong>{eligibility.headline}</strong>
              </div>
              <span className={eligibility.toneClassName}>
                {allowedRoles.length > 0 ? `${allowedRoles.length} role types allowed` : "No eligible roles"}
              </span>
            </div>
            <p className={styles.policyText}>{eligibility.detail}</p>
            <div className={styles.policyRoles}>
              {(["owner", "reviewer", "instructor"] as ManagedCourseRole[]).map((role) => (
                <span
                  key={role}
                  className={canAssignRole(role) ? rolePillClassName(role) : `${shared.warnPill} ${styles.rolePill}`}
                >
                  {roleLabel[role]}
                </span>
              ))}
            </div>
          </section>

          <div className={styles.controlGrid}>
            <label className={shared.selectWrap}>
              <span className={shared.fieldLabel}>Delivery course scope</span>
              <select
                className={shared.select}
                value={courseScopeId}
                onChange={(event) => onCourseScopeChange(event.currentTarget.value ? Number(event.currentTarget.value) : "")}
                disabled={courses.length === 0}
              >
                <option value="">All courses</option>
                {courses.map((course) => (
                  <option key={course.id} value={course.id}>
                    {courseDisplayTitle(course)}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <form className={styles.form} onSubmit={onCreateSubmit}>
            <div className={styles.formGrid}>
              <label className={styles.field}>
                <span className={shared.fieldLabel}>Course</span>
                <select
                  className={shared.select}
                  value={createForm.courseId}
                  onChange={(event) => setCreateForm((current) => ({ ...current, courseId: event.currentTarget.value }))}
                  disabled={courses.length === 0}
                >
                  <option value="">Choose course</option>
                  {courses.map((course) => (
                    <option key={course.id} value={course.id}>
                      {courseDisplayTitle(course)}
                    </option>
                  ))}
                </select>
              </label>
              <label className={styles.field}>
                <span className={shared.fieldLabel}>Governance role</span>
                <select
                  className={shared.select}
                  value={createForm.role}
                  onChange={(event) =>
                    setCreateForm((current) => ({ ...current, role: event.currentTarget.value as ManagedCourseRole }))
                  }
                >
                  <option value="owner" disabled={!canAssignRole("owner")}>
                    Course owner
                  </option>
                  <option value="reviewer" disabled={!canAssignRole("reviewer")}>
                    Reviewer
                  </option>
                  <option value="instructor" disabled={!canAssignRole("instructor")}>
                    Instructor
                  </option>
                </select>
              </label>
              <label className={styles.field}>
                <span className={shared.fieldLabel}>Response SLA hours</span>
                <input
                  type="number"
                  min={1}
                  max={168}
                  className={shared.inlineInput}
                  value={createForm.responseSlaHours}
                  onChange={(event) =>
                    setCreateForm((current) => ({ ...current, responseSlaHours: event.currentTarget.value }))
                  }
                />
              </label>
              <label className={styles.checkboxField}>
                <span className={shared.fieldLabel}>Primary assignment</span>
                <span className={styles.checkboxWrap}>
                  <input
                    type="checkbox"
                    checked={createForm.isPrimary}
                    onChange={(event) =>
                      setCreateForm((current) => ({ ...current, isPrimary: event.currentTarget.checked }))
                    }
                  />
                  <span>Use as the main escalation target</span>
                </span>
              </label>
            </div>

            <div className={styles.formActions}>
              <button
                type="submit"
                className={styles.primaryButton}
                disabled={busy || courses.length === 0 || !selectedUser || !canAssignRole(createForm.role)}
              >
                {createState.isLoading ? "Assigning..." : "Assign course role"}
              </button>
              <button type="button" className={styles.secondaryButton} disabled={busy} onClick={resetCreateForm}>
                Reset
              </button>
            </div>
            <p className={styles.helperText}>The API enforces the same access policy shown above, so invalid role combinations are rejected server-side.</p>
          </form>

          {actionMessage ? <p className={styles.successText}>{actionMessage}</p> : null}
          {actionError ? <p className={shared.errorText}>{actionError}</p> : null}

          {editingAssignment && editForm ? (
            <form className={styles.editPanel} onSubmit={onEditSubmit}>
              <div className={shared.panelHeader}>
                <div>
                  <h3>Edit governance assignment</h3>
                  <p>{editingAssignment.course.title_de}</p>
                </div>
                <span className={rolePillClassName(editingAssignment.role)}>{roleLabel[editingAssignment.role]}</span>
              </div>
              <div className={styles.formGrid}>
                <label className={styles.field}>
                  <span className={shared.fieldLabel}>Role</span>
                <select
                  className={shared.select}
                  value={editForm.role}
                  onChange={(event) =>
                      setEditForm((current) =>
                        current ? { ...current, role: event.currentTarget.value as ManagedCourseRole } : current
                      )
                    }
                  >
                    <option value="owner" disabled={!canAssignRole("owner")}>
                      Course owner
                    </option>
                    <option value="reviewer" disabled={!canAssignRole("reviewer")}>
                      Reviewer
                    </option>
                    <option value="instructor" disabled={!canAssignRole("instructor")}>
                      Instructor
                    </option>
                  </select>
                </label>
                <label className={styles.field}>
                  <span className={shared.fieldLabel}>Response SLA hours</span>
                  <input
                    type="number"
                    min={1}
                    max={168}
                    className={shared.inlineInput}
                    value={editForm.responseSlaHours}
                    onChange={(event) =>
                      setEditForm((current) =>
                        current ? { ...current, responseSlaHours: event.currentTarget.value } : current
                      )
                    }
                  />
                </label>
                <label className={styles.checkboxField}>
                  <span className={shared.fieldLabel}>Primary assignment</span>
                  <span className={styles.checkboxWrap}>
                    <input
                      type="checkbox"
                      checked={editForm.isPrimary}
                      onChange={(event) =>
                        setEditForm((current) => (current ? { ...current, isPrimary: event.currentTarget.checked } : current))
                      }
                    />
                    <span>Keep this user as primary for the selected role</span>
                  </span>
                </label>
              </div>
              <div className={styles.formActions}>
                <button type="submit" className={styles.primaryButton} disabled={busy}>
                  {updateState.isLoading ? "Saving..." : "Save assignment"}
                </button>
                <button type="button" className={styles.secondaryButton} disabled={busy} onClick={resetEditForm}>
                  Cancel
                </button>
              </div>
            </form>
          ) : null}

          {isLoading ? <p className={shared.emptyText}>Loading role assignments...</p> : null}
          {isError ? <p className={shared.errorText}>Failed to load course governance assignments.</p> : null}

          <div className={shared.tableWrap}>
            <table className={shared.table}>
              <thead>
                <tr>
                  <th>Course</th>
                  <th>Role</th>
                  <th>SLA</th>
                  <th>Assigned</th>
                  <th>Governance</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {visibleAssignments.length === 0 ? (
                  <tr>
                    <td colSpan={6}>
                        <p className={shared.emptyText}>
                        No course-role assignments match the current course scope for this user.
                      </p>
                    </td>
                  </tr>
                ) : null}
                {visibleAssignments.map((assignment) => {
                  const courseQuery = `?courseId=${assignment.course.id}`;
                  return (
                    <tr key={assignment.id}>
                      <td>
                        <div className={shared.tableCellStack}>
                          <strong>{assignment.course.title_de}</strong>
                          <span>{assignment.course.slug}</span>
                        </div>
                      </td>
                      <td>
                        <div className={styles.roleCell}>
                          <span className={rolePillClassName(assignment.role)}>{roleLabel[assignment.role]}</span>
                          {assignment.is_primary ? <span className={shared.linkPill}>Primary</span> : null}
                        </div>
                      </td>
                      <td>{assignment.response_sla_hours}h</td>
                      <td>{formatDateTime(assignment.created_at)}</td>
                      <td>
                        <div className={styles.inlineLinks}>
                          <Link to={`/governance${courseQuery}`} className={shared.linkPill}>
                            Governance
                          </Link>
                          <Link to={`/knowledge${courseQuery}`} className={shared.linkPill}>
                            Knowledge
                          </Link>
                        </div>
                      </td>
                      <td>
                        <div className={styles.inlineLinks}>
                          <button
                            type="button"
                            className={styles.secondaryButton}
                            disabled={busy}
                            onClick={() => setEditingAssignmentId(assignment.id)}
                          >
                            Edit
                          </button>
                          <button
                            type="button"
                            className={styles.dangerButton}
                            disabled={busy}
                            onClick={() => onDelete(assignment)}
                          >
                            Delete
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      ) : null}
    </section>
  );
};
