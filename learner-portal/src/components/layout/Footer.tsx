import "./Footer.css";
import { useTranslation } from "react-i18next";

export const Footer = () => {
  const { t } = useTranslation();
  const publicUrl = String(import.meta.env.VITE_ONLINE_PUBLIC_URL ?? "/").trim() || "/";
  const privacyUrl = String(import.meta.env.VITE_PRIVACY_URL ?? "").trim() || publicUrl;
  const impressumUrl = String(import.meta.env.VITE_IMPRESSUM_URL ?? "").trim() || publicUrl;
  const currentYear = new Date().getFullYear();

  return (
    <footer className="student-footer">
      <div className="student-footer__left">
        <span>Internal Academy © {currentYear}</span>
      </div>
      <div className="student-footer__right">
        <a href={privacyUrl} target="_blank" rel="noreferrer">
          {t("footerPrivacy")}
        </a>
        <a href={impressumUrl} target="_blank" rel="noreferrer">
          {t("footerImpressum")}
        </a>
      </div>
    </footer>
  );
};
