// SPDX-FileCopyrightText: 2026 Serhii TK
// SPDX-License-Identifier: LicenseRef-Proprietary

import { Provider } from "react-redux";
import { Navigate, Outlet, Route, Routes } from "react-router-dom";

import { store } from "./app/store";
import { useAuth } from "./context/AuthContext";
import AdminCoursesPage from "./pages/admin/AdminCoursesPage";
import AdminCuratorsPage from "./pages/admin/AdminCuratorsPage";
import AdminDashboardPage from "./pages/admin/AdminDashboardPage";
import AdminGovernancePage from "./pages/admin/AdminGovernancePage";
import AdminKnowledgePage from "./pages/admin/AdminKnowledgePage";
import AdminOperationsPage from "./pages/admin/AdminOperationsPage";
import AdminPublicSitePage from "./pages/admin/AdminPublicSitePage";
import AdminReportsPage from "./pages/admin/AdminReportsPage";
import { AdminWorkspaceShell } from "./pages/admin/AdminWorkspaceShell";
import { LoginPage } from "./pages/LoginPage";
import styles from "./App.module.css";

const AdminGuard = () => {
  const { isAuthenticated, isReady, logout, profile } = useAuth();

  if (!isReady) {
    return (
      <main className={styles.guardState}>
        <section className={styles.guardCard}>
          <h2>Loading admin workspace</h2>
          <p>Checking your standalone Learning Hub session.</p>
        </section>
      </main>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (!profile?.isAdmin) {
    return (
      <main className={styles.guardState}>
        <section className={styles.guardCard}>
          <h2>Admin access required</h2>
          <p>This cabinet is only available for admin users of the Learning Hub backend.</p>
          <button type="button" className={styles.logoutButton} onClick={logout}>
            Sign out
          </button>
        </section>
      </main>
    );
  }

  return (
    <Provider store={store}>
      <Outlet />
    </Provider>
  );
};

const App = () => {
  const { isAuthenticated } = useAuth();

  return (
    <div className={styles.app}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={<Navigate to={isAuthenticated ? "/online" : "/login"} replace />} />
        <Route element={<AdminGuard />}>
          <Route element={<AdminWorkspaceShell />}>
            <Route path="/online" element={<AdminDashboardPage />} />
            <Route path="/curators" element={<AdminCuratorsPage />} />
            <Route path="/courses" element={<AdminCoursesPage />} />
            <Route path="/notebooks" element={<Navigate to="/courses" replace />} />
            <Route path="/site" element={<AdminPublicSitePage />} />
            <Route path="/governance" element={<AdminGovernancePage />} />
            <Route path="/knowledge" element={<AdminKnowledgePage />} />
            <Route path="/reports" element={<AdminReportsPage />} />
            <Route path="/operations" element={<AdminOperationsPage />} />
          </Route>
        </Route>
        <Route path="*" element={<Navigate to={isAuthenticated ? "/online" : "/login"} replace />} />
      </Routes>
    </div>
  );
};

export default App;
