import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import App from "./App";
import { AuthProvider } from "./context/AuthContext";
import "./styles/index.css";

const configuredBasePath = (import.meta.env.VITE_ONLINE_TEACHER_BASE_PATH ?? "/").trim();
const routerBasename = configuredBasePath === "/" ? "/" : configuredBasePath.replace(/\/+$/, "");

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter basename={routerBasename}>
      <AuthProvider>
        <App />
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>
);
