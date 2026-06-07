// SPDX-FileCopyrightText: 2026 Serhii TK
// SPDX-License-Identifier: LicenseRef-Proprietary

import { Provider } from "react-redux";
import { Navigate, Outlet, Route, Routes } from "react-router-dom";

import { store } from "./app/store";
import { useAuth } from "./context/AuthContext";
import { LoginPage } from "./pages/LoginPage";
import { CuratorWorkspacePage } from "./pages/workspace/CuratorWorkspacePage";
import "./styles/app.css";

const TeacherGuard = () => {
  const { isAuthenticated, isReady, logout, profile } = useAuth();

  if (!isReady) {
    return (
      <main className="teacher-guard-state">
        <section className="teacher-guard-card">
          <h2>Loading teacher workspace</h2>
          <p>Checking your standalone Learning Hub session.</p>
        </section>
      </main>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (!profile?.isTeacher) {
    return (
      <main className="teacher-guard-state">
        <section className="teacher-guard-card">
          <h2>Teacher access required</h2>
          <p>This cabinet is only available for users linked to a teacher profile.</p>
          <button type="button" className="teacher-toolbar-logout" onClick={logout}>
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
    <div className="teacher-app">
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<TeacherGuard />}>
          <Route path="/home" element={<CuratorWorkspacePage section="home" />} />
          <Route path="/documents" element={<CuratorWorkspacePage section="documents" />} />
          <Route path="/courses" element={<CuratorWorkspacePage section="documents" />} />
          <Route path="/portfolio" element={<CuratorWorkspacePage section="portfolio" />} />
          <Route path="/delivery" element={<CuratorWorkspacePage section="portfolio" />} />
          <Route path="/online" element={<CuratorWorkspacePage section="online" />} />
          <Route path="/calendar" element={<CuratorWorkspacePage section="calendar" />} />
          <Route path="/information" element={<CuratorWorkspacePage section="information" />} />
          <Route path="/feedback" element={<CuratorWorkspacePage section="feedback" />} />
        </Route>
        <Route path="/" element={<Navigate to={isAuthenticated ? "/home" : "/login"} replace />} />
        <Route path="*" element={<Navigate to={isAuthenticated ? "/home" : "/login"} replace />} />
      </Routes>
    </div>
  );
};

export default App;
