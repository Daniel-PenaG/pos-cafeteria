import { useState, useEffect } from "react";
import Sidebar from "./components/Sidebar";
import Navbar from "./components/Navbar";
import { Outlet, useLocation } from "react-router-dom";

export default function MainLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const location = useLocation();

  useEffect(() => {
    setSidebarOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    document.body.style.overflow = sidebarOpen ? "hidden" : "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [sidebarOpen]);

  return (
    <div className={`app-shell${sidebarOpen ? " app-shell--sidebar-open" : ""}`}>
      <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      {sidebarOpen && (
        <button
          type="button"
          className="sidebar-backdrop"
          aria-label="Cerrar menú"
          onClick={() => setSidebarOpen(false)}
        />
      )}
      <div className="app-main">
        <Navbar onMenuClick={() => setSidebarOpen((v) => !v)} />
        <main className="app-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
