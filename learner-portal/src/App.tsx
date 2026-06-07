// SPDX-FileCopyrightText: 2026 Serhii TK
// SPDX-License-Identifier: LicenseRef-Proprietary

import { Navigate, Route, Routes, useLocation } from "react-router-dom";

import { Footer } from "./components/layout/Footer";
import { useAuth } from "./context/AuthContext";
import { DashboardPage } from "./pages/DashboardPage";
import { LessonWorkspacePage } from "./pages/LessonWorkspacePage";
import { LoginPage } from "./pages/LoginPage";
import "./styles/app.css";

const App = () => {
  const { isAuthenticated, isReady } = useAuth();
  const location = useLocation();
  const hideFooter = location.pathname.startsWith("/lessons/");

  if (!isReady) {
    return (
      <div className="student-app">
        <main className="login-page">
          <section className="login-page__box">
            <p className="login-page__eyebrow">Internal Academy</p>
            <h1>Loading workspace</h1>
            <p className="login-page__intro">Checking your secure browser session.</p>
          </section>
        </main>
        {hideFooter ? null : <Footer />}
      </div>
    );
  }

  return (
    <div className="student-app">
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/learn/:programSlug" element={<Navigate to={isAuthenticated ? "/dashboard" : "/login"} replace />} />
        <Route path="/learn" element={<Navigate to={isAuthenticated ? "/dashboard" : "/login"} replace />} />
        <Route path="/workspace/:programSlug" element={<Navigate to={isAuthenticated ? "/dashboard" : "/login"} replace />} />
        <Route path="/workspace" element={<Navigate to={isAuthenticated ? "/dashboard" : "/login"} replace />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/lessons/:lessonId" element={<LessonWorkspacePage />} />
        <Route path="/" element={<Navigate to={isAuthenticated ? "/dashboard" : "/login"} replace />} />
        <Route path="*" element={<Navigate to={isAuthenticated ? "/dashboard" : "/login"} replace />} />
      </Routes>
      {hideFooter ? null : <Footer />}
    </div>
  );
};

export default App;
