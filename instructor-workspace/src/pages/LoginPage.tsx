import { useEffect, useMemo, useState, type FormEvent } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "../context/AuthContext";
import "./LoginPage.css";

const resolveApiErrorMessage = (error: unknown, fallback: string) => {
  const data = (error as { response?: { data?: { detail?: string; identifier?: string[]; password?: string[]; role?: string[] } } })
    ?.response?.data;
  if (data?.detail) return data.detail;
  if (data?.identifier?.[0]) return data.identifier[0];
  if (data?.password?.[0]) return data.password[0];
  if (data?.role?.[0]) return data.role[0];
  return fallback;
};

export const LoginPage = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { isAuthenticated, isReady, login } = useAuth();
  const configuredBasePath = (import.meta.env.VITE_ONLINE_TEACHER_BASE_PATH ?? "/").trim();
  const normalizedBasePath = configuredBasePath === "/" ? "" : configuredBasePath.replace(/\/+$/, "");
  const apiBaseUrl = String(import.meta.env.VITE_ONLINE_API_BASE_URL ?? "http://localhost:1212/api/online").replace(/\/+$/, "");
  const absolutePath = (path: string) => (normalizedBasePath ? `${normalizedBasePath}${path}` : path);
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState("");
  const searchParams = useMemo(() => new URLSearchParams(location.search), [location.search]);
  const microsoftLoginUrl = `${apiBaseUrl}/staff/auth/microsoft/start/?${new URLSearchParams({
    next: absolutePath("/home"),
    login: absolutePath("/login"),
    role: "teacher",
  }).toString()}`;

  useEffect(() => {
    if (isReady && isAuthenticated) {
      navigate("/home", { replace: true });
    }
  }, [isAuthenticated, isReady, navigate]);

  useEffect(() => {
    const externalError = searchParams.get("error") || "";
    setError(externalError);
  }, [searchParams]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError("");
    setIsSubmitting(true);
    const formData = new FormData(event.currentTarget);
    const submittedIdentifier = String(formData.get("teacher_identifier") ?? identifier).trim();
    const submittedPassword = String(formData.get("teacher_password") ?? password);
    try {
      setIdentifier(submittedIdentifier);
      setPassword(submittedPassword);
      await login(submittedIdentifier, submittedPassword);
      navigate("/home", { replace: true });
    } catch (authError) {
      setError(resolveApiErrorMessage(authError, "Teacher login failed."));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="teacher-login-page">
      <section className="teacher-login-card">
        <div className="teacher-login-copy">
          <span className="teacher-login-kicker">Online lessons</span>
          <h1>Teacher workspace</h1>
          <p>Open cohorts, live sessions, and attendance tools from the extracted standalone project.</p>
        </div>

        <form className="teacher-login-form" onSubmit={handleSubmit} autoComplete="off">
          <button
            type="button"
            className="teacher-login-sso"
            disabled={isSubmitting}
            onClick={() => window.location.assign(microsoftLoginUrl)}
          >
            <span className="teacher-login-sso__icon">M</span>
            <span>Sign in with Microsoft</span>
          </button>

          <div className="teacher-login-divider">
            <span>Or</span>
          </div>

          <label className="teacher-login-field">
            <span>Email or username</span>
            <input
              name="teacher_identifier"
              type="text"
              value={identifier}
              onChange={(event) => setIdentifier(event.currentTarget.value)}
              placeholder="teacher@example.com"
              autoComplete="section-teacher username"
              required
            />
          </label>

          <label className="teacher-login-field">
            <span>Password</span>
            <input
              name="teacher_password"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.currentTarget.value)}
              placeholder="Enter password"
              autoComplete="section-teacher current-password"
              required
            />
          </label>

          {error ? <p className="teacher-login-error">{error}</p> : null}

          <button type="submit" className="teacher-login-submit" disabled={isSubmitting}>
            {isSubmitting ? "Signing in..." : "Open teacher cabinet"}
          </button>
        </form>
      </section>
    </main>
  );
};
