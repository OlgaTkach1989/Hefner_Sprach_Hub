import { FormEvent, useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { onlineStudentLogin } from "../api/onlineStudentApi";
import { useAuth } from "../context/AuthContext";
import "./LoginPage.css";

export const LoginPage = () => {
  const { t } = useTranslation();
  const { applyLogin } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const configuredBasePath = (import.meta.env.VITE_ONLINE_STUDENT_BASE_PATH ?? "/").trim();
  const normalizedBasePath = configuredBasePath === "/" ? "" : configuredBasePath.replace(/\/+$/, "");
  const apiBaseUrl = String(import.meta.env.VITE_ONLINE_API_BASE_URL ?? "http://localhost:1212/api/online").replace(
    /\/+$/,
    "",
  );
  const withBasePath = (path: string) => (normalizedBasePath ? `${normalizedBasePath}${path}` : path);
  const searchParams = new URLSearchParams(location.search);
  const nextPath = (() => {
    const raw = searchParams.get("next") || "/dashboard";
    return raw.startsWith("/") ? raw : "/dashboard";
  })();
  const microsoftLoginUrl = `${apiBaseUrl}/public/auth/microsoft/start/?${new URLSearchParams({
    next: withBasePath(nextPath),
    login: withBasePath("/login"),
    role: "student",
  }).toString()}`;

  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorText, setErrorText] = useState("");

  useEffect(() => {
    const nextError = searchParams.get("error") || "";
    setErrorText(nextError);
  }, [location.search]);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setIsSubmitting(true);
    setErrorText("");
    try {
      const response = await onlineStudentLogin(identifier, password);
      applyLogin(response.profile);
      navigate(nextPath, { replace: true });
    } catch {
      setErrorText(t("loginFailed"));
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <main className="login-page">
      <section className="login-page__box">
        <p className="login-page__eyebrow">{t("brand")}</p>
        <h1>{t("loginTitle")}</h1>
        <p className="login-page__intro">{t("loginIntro")}</p>
        <form className="login-page__form" onSubmit={submit}>
          <input
            value={identifier}
            onChange={(event) => setIdentifier(event.target.value)}
            required
            placeholder={t("emailOrUser")}
          />
          <input
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            required
            type="password"
            placeholder={t("password")}
          />
          <button type="submit" disabled={isSubmitting}>
            {t("loginButton")}
          </button>
          <div className="login-page__divider">
            <span>{t("orLabel")}</span>
          </div>
          <button
            type="button"
            className="login-page__google-btn"
            disabled={isSubmitting}
            onClick={() => window.location.assign(microsoftLoginUrl)}
          >
            <span className="login-page__google-icon">M</span>
            <span>{t("loginWithMicrosoft")}</span>
          </button>
          {errorText ? <p className="login-page__error">{errorText}</p> : null}
        </form>
      </section>
    </main>
  );
};
