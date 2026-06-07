import { useMemo, useState } from "react";
import { Outlet, NavLink, useLocation } from "react-router-dom";

import { useAuth } from "@/context/AuthContext";
import styles from "./AdminWorkspaceShell.module.css";

const DashboardIcon = () => (
  <svg viewBox="0 0 24 24" aria-hidden="true">
    <path d="M4 13h7V4H4v9Zm0 7h7v-5H4v5Zm9 0h7V11h-7v9Zm0-16v5h7V4h-7Z" />
  </svg>
);

const CuratorsIcon = () => (
  <svg viewBox="0 0 24 24" aria-hidden="true">
    <path d="M16 11c1.66 0 2.99-1.57 2.99-3.5S17.66 4 16 4s-3 1.57-3 3.5S14.34 11 16 11Zm-8 0c1.66 0 2.99-1.57 2.99-3.5S9.66 4 8 4 5 5.57 5 7.5 6.34 11 8 11Zm0 2c-2.33 0-7 1.17-7 3.5V20h14v-3.5C15 14.17 10.33 13 8 13Zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.95 1.97 3.45V20h6v-3.5c0-2.33-4.67-3.5-7-3.5Z" />
  </svg>
);

const CoursesIcon = () => (
  <svg viewBox="0 0 24 24" aria-hidden="true">
    <path d="M4 5h16a2 2 0 0 1 2 2v10H2V7a2 2 0 0 1 2-2Zm0 14h16v2H4v-2Zm3-8h5V9H7v2Zm0 4h10v-2H7v2Z" />
  </svg>
);

const PublicSiteIcon = () => (
  <svg viewBox="0 0 24 24" aria-hidden="true">
    <path d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Zm6.92 9h-3.02a15.7 15.7 0 0 0-1.12-5.03A8.03 8.03 0 0 1 18.92 11ZM12 4.04c.84 1.17 1.9 3.34 2.36 6.96H9.64C10.1 7.38 11.16 5.21 12 4.04ZM4.08 13h3.02c.16 1.83.56 3.53 1.12 5.03A8.03 8.03 0 0 1 4.08 13Zm3.02-2H4.08a8.03 8.03 0 0 1 4.14-5.03A15.7 15.7 0 0 0 7.1 11Zm1.99 0c.44-3.12 1.33-5.09 1.91-6.17.58 1.08 1.47 3.05 1.91 6.17H9.09Zm0 2h3.82c-.44 3.12-1.33 5.09-1.91 6.17-.58-1.08-1.47-3.05-1.91-6.17Zm5.69 5.03A15.7 15.7 0 0 0 15.9 13h3.02a8.03 8.03 0 0 1-4.14 5.03Z" />
  </svg>
);

const GovernanceIcon = () => (
  <svg viewBox="0 0 24 24" aria-hidden="true">
    <path d="M12 2 4 5v6c0 5.2 3.4 10 8 11 4.6-1 8-5.8 8-11V5l-8-3Zm-1 6h2v6h-2V8Zm0 8h2v2h-2v-2Z" />
  </svg>
);

const KnowledgeIcon = () => (
  <svg viewBox="0 0 24 24" aria-hidden="true">
    <path d="M12 3 1 9l11 6 9-4.91V17h2V9L12 3Zm-7.67 9L12 16.18 19.67 12 12 7.82 4.33 12ZM6 16.97v2.11L12 22l6-2.92v-2.11L12 20l-6-3.03Z" />
  </svg>
);

const ReportsIcon = () => (
  <svg viewBox="0 0 24 24" aria-hidden="true">
    <path d="M5 3h10l4 4v14H5V3Zm9 1.5V8h3.5L14 4.5ZM8 12h8v-1.5H8V12Zm0 3h8v-1.5H8V15Zm0 3h5v-1.5H8V18Z" />
  </svg>
);

const OperationsIcon = () => (
  <svg viewBox="0 0 24 24" aria-hidden="true">
    <path d="M19.14 12.94a7.48 7.48 0 0 0 .05-.94 7.48 7.48 0 0 0-.05-.94l2.03-1.58a.5.5 0 0 0 .12-.65l-1.92-3.32a.5.5 0 0 0-.61-.22l-2.39.96a7.14 7.14 0 0 0-1.63-.94l-.36-2.54a.49.49 0 0 0-.49-.42h-3.84a.49.49 0 0 0-.49.42l-.36 2.54c-.58.23-1.12.54-1.63.94l-2.39-.96a.5.5 0 0 0-.61.22L2.68 8.83a.5.5 0 0 0 .12.65l2.03 1.58c-.03.31-.05.63-.05.94 0 .31.02.63.05.94l-2.03 1.58a.5.5 0 0 0-.12.65l1.92 3.32c.13.22.39.31.61.22l2.39-.96c.51.4 1.05.71 1.63.94l.36 2.54c.04.24.25.42.49.42h3.84c.24 0 .45-.18.49-.42l.36-2.54c.58-.23 1.12-.54 1.63-.94l2.39.96c.22.09.48 0 .61-.22l1.92-3.32a.5.5 0 0 0-.12-.65l-2.03-1.58ZM12 15.5A3.5 3.5 0 1 1 12 8a3.5 3.5 0 0 1 0 7.5Z" />
  </svg>
);

const LogoutIcon = () => (
  <svg viewBox="0 0 24 24" aria-hidden="true">
    <path d="M10 4H5a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h5v-2H5V6h5V4Zm7.59 7-2.3-2.29L16.7 7.3 21.41 12l-4.7 4.7-1.42-1.41L17.59 13H9v-2h8.59Z" />
  </svg>
);

const SidebarToggleIcon = ({ collapsed }: { collapsed: boolean }) => (
  <svg viewBox="0 0 24 24" aria-hidden="true">
    {collapsed ? (
      <path d="M9.29 7.29 13.59 11.59 9.29 15.89 10.7 17.3 16.41 11.59 10.7 5.88 9.29 7.29Z" />
    ) : (
      <path d="M14.71 7.29 10.41 11.59 14.71 15.89 13.3 17.3 7.59 11.59 13.3 5.88 14.71 7.29Z" />
    )}
  </svg>
);

const SIDEBAR_STATE_KEY = "learning-hub.admin.sidebar-collapsed";

export const AdminWorkspaceShell = () => {
  const { profile, logout } = useAuth();
  const location = useLocation();
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(() => {
    if (typeof window === "undefined") return false;
    return window.localStorage.getItem(SIDEBAR_STATE_KEY) === "1";
  });

  const sidebarTitle = profile?.fullName || "Administrator";
  const sidebarEmail = profile?.email || "";
  const avatarLetter = (profile?.firstName?.[0] || sidebarTitle[0] || "A").toUpperCase();

  const navItems = [
    { href: "/online", label: "Dashboard", icon: <DashboardIcon /> },
    { href: "/curators", label: "Users & Instructors", icon: <CuratorsIcon /> },
    { href: "/courses", label: "Courses", icon: <CoursesIcon /> },
    { href: "/site", label: "Homepage", icon: <PublicSiteIcon /> },
    { href: "/governance", label: "Governance", icon: <GovernanceIcon /> },
    { href: "/knowledge", label: "Knowledge & AI", icon: <KnowledgeIcon /> },
    { href: "/reports", label: "Reports & Logs", icon: <ReportsIcon /> },
    { href: "/operations", label: "Operations", icon: <OperationsIcon /> },
  ];

  const currentSection = useMemo(() => {
    const activeItem = [...navItems]
      .sort((left, right) => right.href.length - left.href.length)
      .find((item) => location.pathname === item.href || location.pathname.startsWith(`${item.href}/`));

    if (activeItem?.href === "/curators") {
      return {
        title: "Users & Instructors",
        description: "Grant instructor access to registered users, maintain instructor profiles, and assign cohorts to delivery owners.",
      };
    }

    if (activeItem?.href === "/courses") {
      return {
        title: "Courses",
        description: "Operate course catalog, cohorts, delivery sessions, and attendance from one course-first workspace.",
      };
    }

    if (activeItem?.href === "/site") {
      return {
        title: "Homepage",
        description: "Manage homepage sections, shared resource hubs, and content behind academy pages.",
      };
    }

    if (activeItem?.href === "/governance") {
      return {
        title: "Governance",
        description: "Control ownership, access policy, metadata coverage, and release readiness before learners see the course.",
      };
    }

    if (activeItem?.href === "/knowledge") {
      return {
        title: "Knowledge & AI",
        description: "Work unresolved AI conversations, index coverage, and knowledge refresh from one course-scoped queue.",
      };
    }

    if (activeItem?.href === "/reports") {
      return {
        title: "Reports & Logs",
        description: "Review audit exceptions, sync failures, grader incidents, and the operational evidence behind admin decisions.",
      };
    }

    if (activeItem?.href === "/operations") {
      return {
        title: "Operations",
        description: "Track delivery health, sync signals, runtime pressure, and academy-wide operational attention items.",
      };
    }

    return {
      title: "Dashboard",
      description: "Executive view of course delivery, governance readiness, and academy-wide operational signals.",
    };
  }, [location.pathname]);

  const onToggleSidebar = () => {
    setIsSidebarCollapsed((current) => {
      const nextValue = !current;
      if (typeof window !== "undefined") {
        window.localStorage.setItem(SIDEBAR_STATE_KEY, nextValue ? "1" : "0");
      }
      return nextValue;
    });
  };

  return (
    <main className={styles.shell}>
      <div className={styles.layout}>
        <aside className={`${styles.sidebar} ${isSidebarCollapsed ? styles.sidebarCollapsed : ""}`}>
          <div className={styles.brandBlock}>
            <div className={styles.brandCopy}>
              <p className={styles.brandEyebrow}>Internal academy</p>
              <strong className={styles.brandTitle}>Admin Console</strong>
              <p className={styles.brandText}>Operate courses, access, AI, and delivery health.</p>
            </div>
            <button
              type="button"
              className={styles.toggleButton}
              onClick={onToggleSidebar}
              aria-label={isSidebarCollapsed ? "Expand navigation" : "Collapse navigation"}
              title={isSidebarCollapsed ? "Expand navigation" : "Collapse navigation"}
            >
              <SidebarToggleIcon collapsed={isSidebarCollapsed} />
            </button>
          </div>

          <div className={styles.profileCard} title={isSidebarCollapsed ? sidebarTitle : undefined}>
            <div className={styles.avatar}>
              <span>{avatarLetter}</span>
            </div>
            <div className={styles.profileCopy}>
              <p>{sidebarTitle}</p>
              <span>{sidebarEmail}</span>
            </div>
          </div>

          <nav className={styles.nav} aria-label="Admin workspace navigation">
            {navItems.map((item) => (
              <NavLink
                key={item.href}
                to={item.href}
                end={item.href === "/online"}
                title={isSidebarCollapsed ? item.label : undefined}
                className={({ isActive }) => `${styles.navLink} ${isActive ? styles.navLinkActive : ""}`}
              >
                <span className={styles.navIcon}>{item.icon}</span>
                <span className={styles.navLabel}>{item.label}</span>
              </NavLink>
            ))}

            <button
              type="button"
              className={styles.logoutButton}
              onClick={logout}
              title={isSidebarCollapsed ? "Sign out" : undefined}
            >
              <span className={styles.navIcon}>
                <LogoutIcon />
              </span>
              <span className={styles.logoutLabel}>Sign out</span>
            </button>
          </nav>
        </aside>

        <section className={styles.content}>
          <header className={styles.topbar}>
            <div className={styles.topbarCopy}>
              <span className={styles.kicker}>Internal academy</span>
              <h1>{currentSection.title}</h1>
              <p>{currentSection.description}</p>
            </div>
            <div className={styles.topbarActions}>
              <span className={styles.pill}>English only</span>
              <span className={styles.pill}>Admin access</span>
            </div>
          </header>

          <section className={styles.main}>
            <Outlet />
          </section>
        </section>
      </div>
    </main>
  );
};
