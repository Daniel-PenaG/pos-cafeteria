import { useCallback, useEffect, useRef, useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import Sidebar, { SIDEBAR_ID } from "./components/Sidebar";
import Navbar from "./components/Navbar";

function isMobileViewport() {
  return window.matchMedia("(max-width: 767px)").matches;
}

function getSidebarFocusables(sidebar) {
  if (!sidebar) return [];
  return Array.from(
    sidebar.querySelectorAll(
      'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
    )
  ).filter((el) => el.offsetParent !== null || sidebar.contains(el));
}

export default function MainLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const location = useLocation();
  const menuBtnRef = useRef(null);
  const restoreFocusRef = useRef(false);

  const closeSidebar = useCallback(() => {
    restoreFocusRef.current = isMobileViewport();
    setSidebarOpen(false);
  }, []);

  useEffect(() => {
    closeSidebar();
  }, [location.pathname, closeSidebar]);

  useEffect(() => {
    const mq = window.matchMedia("(min-width: 768px)");
    const onChange = () => {
      if (mq.matches) closeSidebar();
    };
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, [closeSidebar]);

  useEffect(() => {
    const onPopState = () => closeSidebar();
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, [closeSidebar]);

  useEffect(() => {
    if (!sidebarOpen) {
      document.body.style.overflow = "";
      if (restoreFocusRef.current && menuBtnRef.current) {
        menuBtnRef.current.focus();
        restoreFocusRef.current = false;
      }
      return undefined;
    }

    document.body.style.overflow = "hidden";

    const sidebar = document.getElementById(SIDEBAR_ID);
    const onKey = (event) => {
      if (event.key === "Escape") {
        closeSidebar();
        return;
      }
      if (event.key !== "Tab" || !isMobileViewport() || !sidebar) return;

      const focusables = getSidebarFocusables(sidebar);
      if (focusables.length === 0) return;

      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      const active = document.activeElement;

      if (event.shiftKey) {
        if (active === first || !sidebar.contains(active)) {
          event.preventDefault();
          last.focus();
        }
      } else if (active === last || !sidebar.contains(active)) {
        event.preventDefault();
        first.focus();
      }
    };

    window.addEventListener("keydown", onKey);

    if (isMobileViewport() && sidebar) {
      const closeBtn = sidebar.querySelector(".sidebar__close");
      const focusables = getSidebarFocusables(sidebar);
      (closeBtn || focusables[0])?.focus();
    }

    return () => {
      document.body.style.overflow = "";
      window.removeEventListener("keydown", onKey);
    };
  }, [sidebarOpen, closeSidebar]);

  return (
    <div className={`app-shell${sidebarOpen ? " app-shell--sidebar-open" : ""}`}>
      {sidebarOpen && (
        <button
          type="button"
          className="sidebar-overlay"
          aria-label="Cerrar menú"
          onClick={closeSidebar}
        />
      )}
      <Sidebar open={sidebarOpen} onClose={closeSidebar} />
      <div className="app-main">
        <Navbar
          ref={menuBtnRef}
          onMenuOpen={() => setSidebarOpen(true)}
          menuExpanded={sidebarOpen}
        />
        <main className="app-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
