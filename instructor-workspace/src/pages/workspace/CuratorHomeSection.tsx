import { useEffect, useState, type FormEvent } from "react";

import {
  useGetTeacherWorkspaceQuery,
  useUpdateTeacherWorkspaceProfileMutation,
} from "@/bll/workspace/workspace.service";
import { formatDateTime, formatPercent, resolveApiErrorMessage } from "./workspaceShared";

type ProfileFormState = {
  firstName: string;
  lastName: string;
  privateEmail: string;
  phone: string;
};

const buildInitialFormState = (): ProfileFormState => ({
  firstName: "",
  lastName: "",
  privateEmail: "",
  phone: "",
});

export const CuratorHomeSection = () => {
  const { data, isLoading, isError } = useGetTeacherWorkspaceQuery();
  const [updateProfile, updateState] = useUpdateTeacherWorkspaceProfileMutation();
  const [formState, setFormState] = useState<ProfileFormState>(buildInitialFormState);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (!data?.profile) return;
    setFormState({
      firstName: data.profile.firstName,
      lastName: data.profile.lastName,
      privateEmail: data.profile.privateEmail || "",
      phone: data.profile.phone || "",
    });
  }, [data?.profile]);

  if (isLoading) {
    return <p className="curator-workspace__empty-copy">Loading instructor profile...</p>;
  }

  if (isError || !data) {
    return <p className="curator-workspace__error-copy">Failed to load instructor profile.</p>;
  }

  const nextSession = data.upcomingSessions[0] ?? null;
  const highlightedCohorts = data.cohorts.slice(0, 4);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setMessage("");
    setError("");

    try {
      await updateProfile({
        firstName: formState.firstName.trim(),
        lastName: formState.lastName.trim(),
        privateEmail: formState.privateEmail.trim(),
        phone: formState.phone.trim(),
      }).unwrap();
      setMessage("Profile updated.");
    } catch (updateError) {
      setError(resolveApiErrorMessage(updateError, "Failed to update profile."));
    }
  };

  return (
    <div className="curator-workspace__section-stack">
      <section className="curator-workspace__card">
        <div className="curator-workspace__panel-heading">
          <div>
            <span className="curator-workspace__eyebrow">Personal data</span>
            <h3>Instructor profile</h3>
          </div>
          <p>Maintain the core delivery contact details used by learners, coordinators, and live-course operations.</p>
        </div>

        <form className="curator-workspace__form curator-workspace__form--grid" onSubmit={handleSubmit}>
          <label>
            <span>First name</span>
            <input
              type="text"
              value={formState.firstName}
              onChange={(event) => setFormState((current) => ({ ...current, firstName: event.currentTarget.value }))}
            />
          </label>

          <label>
            <span>Last name</span>
            <input
              type="text"
              value={formState.lastName}
              onChange={(event) => setFormState((current) => ({ ...current, lastName: event.currentTarget.value }))}
            />
          </label>

          <label className="curator-workspace__readonly-field">
            <span>School email</span>
            <input type="email" value={data.profile.schoolEmail} readOnly />
            <small>Provided by the academy account.</small>
          </label>

          <label className="curator-workspace__readonly-field">
            <span>Short name</span>
            <input type="text" value={data.profile.shortName} readOnly />
            <small>Used as the internal instructor identifier.</small>
          </label>

          <label>
            <span>Private email</span>
            <input
              type="email"
              value={formState.privateEmail}
              onChange={(event) =>
                setFormState((current) => ({ ...current, privateEmail: event.currentTarget.value }))
              }
            />
          </label>

          <label>
            <span>Phone</span>
            <input
              type="text"
              value={formState.phone}
              onChange={(event) => setFormState((current) => ({ ...current, phone: event.currentTarget.value }))}
            />
          </label>

          {error ? <p className="curator-workspace__notice curator-workspace__notice--error">{error}</p> : null}
          {message ? <p className="curator-workspace__notice curator-workspace__notice--success">{message}</p> : null}

          <button type="submit" className="curator-workspace__primary-action" disabled={updateState.isLoading}>
            {updateState.isLoading ? "Saving..." : "Save profile"}
          </button>
        </form>
      </section>

      <div className="curator-workspace__grid curator-workspace__grid--balanced">
        <section className="curator-workspace__card">
          <div className="curator-workspace__panel-heading">
            <div>
              <span className="curator-workspace__eyebrow">Current footprint</span>
              <h3>Operational KPIs</h3>
            </div>
            <p>Quick visibility into your current course responsibility and delivery coverage.</p>
          </div>
          <div className="curator-workspace__metric-grid">
            <article>
              <span>Courses</span>
              <strong>{data.summary.courses}</strong>
              <small>assigned to you</small>
            </article>
            <article>
              <span>Cohorts</span>
              <strong>{data.summary.cohorts}</strong>
              <small>active groups</small>
            </article>
            <article>
              <span>Sessions</span>
              <strong>{data.summary.sessions}</strong>
              <small>tracked sessions</small>
            </article>
            <article>
              <span>Attendance</span>
              <strong>{formatPercent(data.summary.attendancePercent)}</strong>
              <small>average attendance</small>
            </article>
          </div>
        </section>

        <section className="curator-workspace__card">
          <div className="curator-workspace__panel-heading">
            <div>
              <span className="curator-workspace__eyebrow">Priority</span>
              <h3>Next session</h3>
            </div>
            <p>Use this slot as your immediate checkpoint for live delivery readiness.</p>
          </div>
          {nextSession ? (
            <div className="curator-workspace__highlight">
              <strong>{nextSession.title}</strong>
              <p>
                {nextSession.groupCode} · {nextSession.groupName}
              </p>
              <span>{formatDateTime(nextSession.startsAt)}</span>
            </div>
          ) : (
            <p className="curator-workspace__empty-copy">No upcoming sessions are currently scheduled.</p>
          )}
        </section>
      </div>

      <section className="curator-workspace__card">
        <div className="curator-workspace__panel-heading">
          <div>
            <span className="curator-workspace__eyebrow">Assigned cohorts</span>
            <h3>Teaching scope</h3>
          </div>
          <p>Overview of the groups currently linked to your instructor account.</p>
        </div>
        <div className="curator-workspace__process-grid">
          {highlightedCohorts.length === 0 ? (
            <p className="curator-workspace__empty-copy">No cohorts are assigned to this instructor yet.</p>
          ) : null}
          {highlightedCohorts.map((cohort) => (
            <article key={cohort.id}>
              <strong>
                {cohort.groupCode} · {cohort.groupName}
              </strong>
              <p>{cohort.courseTitleEn || cohort.courseTitleDe}</p>
              <span>
                {cohort.studentsCount} learners · {formatPercent(cohort.attendancePercent)} attendance
              </span>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
};
