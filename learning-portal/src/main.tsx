import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { HelmetProvider } from "react-helmet-async";

import App from "./App";
import { UiPreferencesProvider } from "./context/UiPreferencesContext";
import "./i18n";
import "./styles/index.css";

const configuredBasePath = (import.meta.env.VITE_PUBLIC_BASE_PATH ?? "/").trim();
const routerBasename = configuredBasePath === "/" ? "/" : configuredBasePath.replace(/\/+$/, "");

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <HelmetProvider>
      <BrowserRouter basename={routerBasename}>
        <UiPreferencesProvider>
          <App />
        </UiPreferencesProvider>
      </BrowserRouter>
    </HelmetProvider>
  </React.StrictMode>
);
