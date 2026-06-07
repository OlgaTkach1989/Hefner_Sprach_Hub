import { useEffect, useMemo, useState, type FormEvent } from "react";

import {
  useCreateTrainingAdminCourseRoleAssignmentMutation,
  useDeleteTrainingAdminCourseRoleAssignmentMutation,
  useGetTrainingAdminCourseRoleAssignmentsQuery,
  useUpdateTrainingAdminCourseRoleAssignmentMutation,
} from "@/bll/training/training.service";
import type { TrainingCourseRole } from "@/bll/training/training.type";
import { formatDateTime, resolveApiErrorMessage } from "./training.utils";
import cl from "../OnlinePage.module.scss";

type CreateFormState = {
  userId: string;
  role: TrainingCourseRole;
  isPrimary: boolean;
  responseSlaHours: string;
};

type EditFormState = {
  role: TrainingCourseRole;
  isPrimary: boolean;
  responseSlaHours: string;
};

const emptyCreateForm = (): CreateFormState => ({
  userId: "",
  role: "owner",
  isPrimary: true,
  responseSlaHours: "24",
});

const TrainingCourseRoleCrudSection = ({ courseId, courseTitle }: { courseId: number; courseTitle: string }) => {
  const { data, isLoading, isError } = useGetTrainingAdminCourseRoleAssignmentsQuery({ courseId }, { skip: !courseId });
  const assignments = useMemo(() => data?.results ?? [], [data]);
  const [createForm, setCreateForm] = useState<CreateFormState>(emptyCreateForm());
  const [editingAssignmentId, setEditingAssignmentId] = useState<number | null>(null);
  const [editForm, setEditForm] = useState<EditFormState | null>(null);
  const [actionError, setActionError] = useState("");

  const [createAssignment, { isLoading: isCreating }] = useCreateTrainingAdminCourseRoleAssignmentMutation();
  const [updateAssignment, { isLoading: isUpdating }] = useUpdateTrainingAdminCourseRoleAssignmentMutation();
  const [deleteAssignment, { isLoading: isDeleting }] = useDeleteTrainingAdminCourseRoleAssignmentMutation();

  const sortedAssignments = useMemo(
    () =>
      [...assignments].sort((left, right) => {
        if (left.role !== right.role) return left.role.localeCompare(right.role);
        if (left.is_primary !== right.is_primary) return left.is_primary ? -1 : 1;
        return left.user.email.localeCompare(right.user.email);
      }),
    [assignments]
  );

  const editingAssignment = useMemo(
    () => sortedAssignments.find((assignment) => assignment.id === editingAssignmentId) ?? null,
    [editingAssignmentId, sortedAssignments]
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

  const resetCreateForm = () => {
    setCreateForm(emptyCreateForm());
    setActionError("");
  };

  const resetEditForm = () => {
    setEditingAssignmentId(null);
    setEditForm(null);
    setActionError("");
  };

  const onCreateSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setActionError("");

    const userId = Number(createForm.userId);
    const slaHours = Number(createForm.responseSlaHours);
    if (!Number.isInteger(userId) || userId <= 0) {
      setActionError("User ID must be a positive integer.");
      return;
    }
    if (!Number.isInteger(slaHours) || slaHours < 1 || slaHours > 168) {
      setActionError("SLA hours must be between 1 and 168.");
      return;
    }

    try {
      await createAssignment({
        user_id: userId,
        course_id: courseId,
        role: createForm.role,
        is_primary: createForm.isPrimary,
        response_sla_hours: slaHours,
      }).unwrap();
      resetCreateForm();
    } catch (error) {
      setActionError(resolveApiErrorMessage(error, "Failed to create course role assignment."));
    }
  };

  const onEditSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!editingAssignmentId || !editForm) return;

    setActionError("");
    const slaHours = Number(editForm.responseSlaHours);
    if (!Number.isInteger(slaHours) || slaHours < 1 || slaHours > 168) {
      setActionError("SLA hours must be between 1 and 168.");
      return;
    }

    try {
      await updateAssignment({
        assignmentId: editingAssignmentId,
        body: {
          role: editForm.role,
          is_primary: editForm.isPrimary,
          response_sla_hours: slaHours,
        },
      }).unwrap();
      resetEditForm();
    } catch (error) {
      setActionError(resolveApiErrorMessage(error, "Failed to update course role assignment."));
    }
  };

  const onDelete = async (assignmentId: number) => {
    if (!window.confirm("Delete this course role assignment?")) {
      return;
    }
    setActionError("");
    try {
      await deleteAssignment(assignmentId).unwrap();
      if (editingAssignmentId === assignmentId) {
        resetEditForm();
      }
    } catch (error) {
      setActionError(resolveApiErrorMessage(error, "Failed to delete course role assignment."));
    }
  };

  const busy = isCreating || isUpdating || isDeleting;

  return (
    <section className={cl.block}>
      <div className={cl.blockHead}>
        <div>
          <h3>Course Roles</h3>
          <p className={cl.governanceMuted}>Assign owners, reviewers and instructors for the active course.</p>
        </div>
        <span className={cl.sectionHint}>{courseTitle}</span>
      </div>

      {isLoading ? <p>Loading course roles...</p> : null}
      {isError ? <p className={cl.errorText}>Failed to load course role assignments.</p> : null}

      <form className={cl.crudForm} onSubmit={onCreateSubmit}>
        <div className={cl.crudGrid}>
          <label className={cl.field}>
            <span className={cl.fieldLabel}>User ID</span>
            <input
              className={cl.fieldInput}
              value={createForm.userId}
              onChange={(event) => setCreateForm((current) => ({ ...current, userId: event.currentTarget.value }))}
              required
              inputMode="numeric"
            />
          </label>
          <label className={cl.field}>
            <span className={cl.fieldLabel}>Role</span>
            <select
              className={cl.fieldInput}
              value={createForm.role}
              onChange={(event) =>
                setCreateForm((current) => ({
                  ...current,
                  role: event.currentTarget.value as TrainingCourseRole,
                }))
              }
            >
              <option value="owner">Course owner</option>
              <option value="reviewer">Reviewer</option>
              <option value="instructor">Instructor</option>
            </select>
          </label>
        </div>
        <div className={cl.crudToggleRow}>
          <label className={cl.fieldCheckbox}>
            <input
              type="checkbox"
              checked={createForm.isPrimary}
              onChange={(event) => setCreateForm((current) => ({ ...current, isPrimary: event.currentTarget.checked }))}
            />
            Primary assignment
          </label>
          <label className={cl.field}>
            <span className={cl.fieldLabel}>Response SLA hours</span>
            <input
              className={cl.fieldInput}
              value={createForm.responseSlaHours}
              onChange={(event) =>
                setCreateForm((current) => ({ ...current, responseSlaHours: event.currentTarget.value }))
              }
              required
              inputMode="numeric"
            />
          </label>
        </div>
        <p className={cl.governanceMuted}>
          New assignments are created for course ID <strong>{courseId}</strong>.
        </p>
        {actionError ? <p className={cl.errorText}>{actionError}</p> : null}
        <div className={cl.formActions}>
          <button type="submit" className={cl.primaryButton} disabled={busy}>
            Create assignment
          </button>
          <button type="button" className={cl.secondaryButton} onClick={resetCreateForm} disabled={busy}>
            Reset
          </button>
        </div>
      </form>

      {editingAssignment && editForm ? (
        <form className={cl.editPanel} onSubmit={onEditSubmit}>
          <div className={cl.blockHead}>
            <h4>Edit assignment</h4>
            <span className={cl.sectionHint}>
              {editingAssignment.user.email} - {editingAssignment.course.slug}
            </span>
          </div>
          <div className={cl.crudGrid}>
            <label className={cl.field}>
              <span className={cl.fieldLabel}>Role</span>
              <select
                className={cl.fieldInput}
                value={editForm.role}
                onChange={(event) =>
                  setEditForm((current) =>
                    current ? { ...current, role: event.currentTarget.value as TrainingCourseRole } : current
                  )
                }
              >
                <option value="owner">Course owner</option>
                <option value="reviewer">Reviewer</option>
                <option value="instructor">Instructor</option>
              </select>
            </label>
            <label className={cl.field}>
              <span className={cl.fieldLabel}>Response SLA hours</span>
              <input
                className={cl.fieldInput}
                value={editForm.responseSlaHours}
                onChange={(event) =>
                  setEditForm((current) => (current ? { ...current, responseSlaHours: event.currentTarget.value } : current))
                }
                required
                inputMode="numeric"
              />
            </label>
          </div>
          <label className={cl.fieldCheckbox}>
            <input
              type="checkbox"
              checked={editForm.isPrimary}
              onChange={(event) =>
                setEditForm((current) => (current ? { ...current, isPrimary: event.currentTarget.checked } : current))
              }
            />
            Primary assignment
          </label>
          {actionError ? <p className={cl.errorText}>{actionError}</p> : null}
          <div className={cl.formActions}>
            <button type="submit" className={cl.primaryButton} disabled={busy}>
              Save changes
            </button>
            <button type="button" className={cl.secondaryButton} onClick={resetEditForm} disabled={busy}>
              Cancel edit
            </button>
          </div>
        </form>
      ) : null}

      <div className={cl.tableWrap}>
        <table className={cl.dataTable}>
          <thead>
            <tr>
              <th>User</th>
              <th>Role</th>
              <th>SLA</th>
              <th>Assigned</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {sortedAssignments.length === 0 ? (
              <tr>
                <td colSpan={5}>No governance roles assigned yet.</td>
              </tr>
            ) : null}
            {sortedAssignments.map((assignment) => (
              <tr key={assignment.id}>
                <td>
                  <div className={cl.governanceCell}>
                    <strong>{assignment.user.email}</strong>
                    {assignment.user.username ? <span className={cl.governanceMuted}>{assignment.user.username}</span> : null}
                  </div>
                </td>
                <td>
                  <span className={cl.governanceRolePill}>{assignment.role}</span>
                  {assignment.is_primary ? <span className={cl.governancePrimaryPill}>Primary</span> : null}
                </td>
                <td>{assignment.response_sla_hours}h</td>
                <td>{formatDateTime(assignment.created_at)}</td>
                <td>
                  <div className={cl.actionRow}>
                    <button type="button" className={cl.tableAction} onClick={() => setEditingAssignmentId(assignment.id)}>
                      Edit
                    </button>
                    <button type="button" className={cl.tableDangerAction} onClick={() => onDelete(assignment.id)}>
                      Delete
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
};

export default TrainingCourseRoleCrudSection;
