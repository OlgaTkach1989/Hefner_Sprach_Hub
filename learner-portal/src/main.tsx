import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import App from "./App";
import { AuthProvider } from "./context/AuthContext";
import { UiPreferencesProvider } from "./context/UiPreferencesContext";
import "./i18n";
import "./styles/index.css";

const configuredBasePath = (import.meta.env.VITE_ONLINE_STUDENT_BASE_PATH ?? "/").trim();
const routerBasename = configuredBasePath === "/" ? "/" : configuredBasePath.replace(/\/+$/, "");

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter basename={routerBasename}>
      <UiPreferencesProvider>
        <AuthProvider>
          <App />
        </AuthProvider>
      </UiPreferencesProvider>
    </BrowserRouter>
  </React.StrictMode>
);
