import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import "./NotFoundPage.css";

export const NotFoundPage = () => {
  const { t } = useTranslation();
  return (
    <main className="not-found-page">
      <h1>404</h1>
      <p>{t("noCourse")}</p>
      <Link to="/">{t("backHome")}</Link>
    </main>
  );
};
