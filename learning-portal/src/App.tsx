// SPDX-FileCopyrightText: 2026 Serhii TK
// SPDX-License-Identifier: LicenseRef-Proprietary

import { Navigate, Route, Routes } from "react-router-dom";

import { Footer } from "./components/layout/Footer";
import { Header } from "./components/layout/Header";
import { CheckoutPage } from "./pages/CheckoutPage";
import { CourseLessonPage } from "./pages/CourseLessonPage";
import { CoursePage } from "./pages/CoursePage";
import { HomePage } from "./pages/HomePage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { OfficeWorkspacePage } from "./pages/OfficeWorkspacePage";
import { PortalPage } from "./pages/PortalPage";
import { PublicSignInPage } from "./pages/PublicSignInPage";
import { SuccessPage } from "./pages/SuccessPage";
import "./styles/app.css";

const App = () => {
  return (
    <div className="public-app">
      <Header />
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/home" element={<Navigate to="/" replace />} />
        <Route path="/sign-in" element={<PublicSignInPage />} />
        <Route path="/login" element={<Navigate to="/" replace />} />
        <Route path="/spaces/:workspaceSlug" element={<OfficeWorkspacePage />} />
        <Route path="/offices/:officeSlug" element={<OfficeWorkspacePage />} />
        <Route path="/course/:slug" element={<CoursePage />} />
        <Route path="/course/:slug/lesson/:lessonNumber" element={<CourseLessonPage />} />
        <Route path="/buy" element={<CheckoutPage />} />
        <Route path="/checkout" element={<CheckoutPage />} />
        <Route path="/checkout/:slug" element={<CheckoutPage />} />
        <Route path="/checkout/:slug/payment" element={<CheckoutPage />} />
        <Route path="/portal" element={<PortalPage />} />
        <Route path="/success" element={<SuccessPage />} />
        <Route path="/404" element={<NotFoundPage />} />
        <Route path="*" element={<Navigate to="/404" replace />} />
      </Routes>
      <Footer />
    </div>
  );
};

export default App;
