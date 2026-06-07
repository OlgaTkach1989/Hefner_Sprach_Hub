import { useMemo, useState, type FormEvent } from "react";

import { useOnboardOnlineAdminCuratorMutation } from "@/bll/online/online.service";
import type { OnlineAdminCuratorSummary } from "@/bll/online/online.type";
import shared from "./AdminPagesShared.module.css";
import styles from "./AdminCuratorsPage.module.css";

type OnboardingFormState = {
  email: string;
  temporaryPassword: string;
  firstName: string;
  lastName: string;
  schoolEmail: string;
  privateEmail: string;
  phone: string;
  shortName: string;
};

const EMPTY_FORM: OnboardingFormState = {
  email: "",
  temporaryPassword: "",
  firstName: "",
  lastName: "",
  schoolEmail: "",
  privateEmail: "",
  phone: "",
  shortName: "",
};

const shortNameFrom = (firstName: string, lastName: string) =>
  `${firstName.trim().slice(0, 1)}${lastName.trim().slice(0, 1)}`.toUpperCase();

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

type Props = {
  registeredUsersCount: number;
  onCreated: (curator: OnlineAdminCuratorSummary) => void;
};

export const AdminCuratorOnboardingPanel = ({ registeredUsersCount, onCreated }: Props) => {
  const [form, setForm] = useState<OnboardingFormState>(EMPTY_FORM);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [onboardCurator, onboardState] = useOnboardOnlineAdminCuratorMutation();

  const generatedShortName = useMemo(
    () => shortNameFrom(form.firstName, form.lastName),
    [form.firstName, form.lastName],
  );

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const payload = {
      email: form.email.trim().toLowerCase(),
      temporaryPassword: form.temporaryPassword,
      firstName: form.firstName.trim(),
      lastName: form.lastName.trim(),
      schoolEmail: form.schoolEmail.trim(),
      privateEmail: form.privateEmail.trim(),
      phone: form.phone.trim(),
      shortName: form.shortName.trim().replace(/\s+/g, "").toUpperCase(),
    };

    if (!payload.email || !payload.temporaryPassword || !payload.firstName || !payload.lastName || !payload.schoolEmail || !payload.shortName) {
      setErrorMessage("Email, temporary password, names, school email, and short name are required.");
      setSuccessMessage(null);
      return;
    }

    try {
      const created = await onboardCurator(payload).unwrap();
      setSuccessMessage(`Instructor account created for ${created.fullName}. Temporary login email: ${created.email}`);
      setErrorMessage(null);
      setForm(EMPTY_FORM);
      onCreated(created);
    } catch (error) {
      setErrorMessage(errorMessageFrom(error, "Failed to create instructor account."));
      setSuccessMessage(null);
    }
  };

  return (
    <section className={shared.panel}>
      <header className={shared.panelHeader}>
        <div>
          <h2>Onboard a new instructor</h2>
          <p>Create a new registered user and instructor profile in one controlled action. The new account becomes visible in the registry immediately.</p>
        </div>
        <span className={shared.sectionHint}>{registeredUsersCount} users already registered</span>
      </header>

      <div className={styles.selectionSummary}>
        <article className={styles.summaryCard}>
          <span className={shared.fieldLabel}>What this creates</span>
          <strong>User account + instructor profile</strong>
          <span>The user can sign in to instructor workspace as soon as you share the temporary password.</span>
        </article>
        <article className={styles.summaryCard}>
          <span className={shared.fieldLabel}>Recommended policy</span>
          <strong>Share credentials once, then rotate</strong>
          <span>Use a strong temporary password and ask the instructor to change it after first login.</span>
        </article>
      </div>

      <form className={styles.form} onSubmit={onSubmit}>
        <div className={styles.formGrid}>
          <label className={styles.field}>
            <span className={shared.fieldLabel}>Login email</span>
            <input
              type="email"
              className={shared.inlineInput}
              value={form.email}
              onChange={(event) => {
                const nextValue = event.currentTarget.value;
                setForm((current) => ({
                  ...current,
                  email: nextValue,
                  schoolEmail: current.schoolEmail || nextValue,
                }));
              }}
              placeholder="instructor@your-organization.example"
            />
          </label>

          <label className={styles.field}>
            <span className={shared.fieldLabel}>Temporary password</span>
            <input
              type="text"
              className={shared.inlineInput}
              value={form.temporaryPassword}
              onChange={(event) => setForm((current) => ({ ...current, temporaryPassword: event.currentTarget.value }))}
              placeholder="At least 10 chars with letters and numbers"
            />
          </label>

          <label className={styles.field}>
            <span className={shared.fieldLabel}>First name</span>
            <input
              type="text"
              className={shared.inlineInput}
              value={form.firstName}
              onChange={(event) => setForm((current) => ({ ...current, firstName: event.currentTarget.value }))}
            />
          </label>

          <label className={styles.field}>
            <span className={shared.fieldLabel}>Last name</span>
            <input
              type="text"
              className={shared.inlineInput}
              value={form.lastName}
              onChange={(event) => setForm((current) => ({ ...current, lastName: event.currentTarget.value }))}
            />
          </label>

          <label className={styles.field}>
            <span className={shared.fieldLabel}>School email</span>
            <input
              type="email"
              className={shared.inlineInput}
              value={form.schoolEmail}
              onChange={(event) => setForm((current) => ({ ...current, schoolEmail: event.currentTarget.value }))}
            />
          </label>

          <label className={styles.field}>
            <span className={shared.fieldLabel}>Private email</span>
            <input
              type="email"
              className={shared.inlineInput}
              value={form.privateEmail}
              onChange={(event) => setForm((current) => ({ ...current, privateEmail: event.currentTarget.value }))}
              placeholder="Optional"
            />
          </label>

          <label className={styles.field}>
            <span className={shared.fieldLabel}>Phone</span>
            <input
              type="text"
              className={shared.inlineInput}
              value={form.phone}
              onChange={(event) => setForm((current) => ({ ...current, phone: event.currentTarget.value }))}
              placeholder="Optional"
            />
          </label>

          <label className={styles.field}>
            <span className={shared.fieldLabel}>Short name</span>
            <input
              type="text"
              className={shared.inlineInput}
              value={form.shortName}
              onChange={(event) => setForm((current) => ({ ...current, shortName: event.currentTarget.value }))}
              placeholder={generatedShortName || "AB"}
            />
          </label>
        </div>

        {successMessage ? <p className={styles.successText}>{successMessage}</p> : null}
        {errorMessage ? <p className={shared.errorText}>{errorMessage}</p> : null}

        <div className={styles.actionRow}>
          <button type="submit" className={styles.primaryButton} disabled={onboardState.isLoading}>
            {onboardState.isLoading ? "Creating..." : "Create instructor account"}
          </button>
        </div>

        <p className={styles.helperText}>
          Login uses the email above. If you leave short name blank, use the initials shown in the placeholder.
        </p>
      </form>
    </section>
  );
};
