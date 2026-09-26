import React, { useEffect, useState } from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import '../App.css';

function AppShell({ children }) {
  const [backendOnline, setBackendOnline] = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const modelName = 'qwen2.5-coder:14b';

  useEffect(() => {
    const checkBackend = async () => {
      try {
        const response = await fetch('/health', {
          cache: 'no-store',
        });

        setBackendOnline(response.ok);
      } catch {
        setBackendOnline(false);
      }
    };

    checkBackend();

    const interval = window.setInterval(
      checkBackend,
      15000
    );

    return () => {
      window.clearInterval(interval);
    };
  }, []);

  const connectionLabel =
    backendOnline === null
      ? 'Checking backend'
      : backendOnline
        ? 'Backend online'
        : 'Backend offline';

  const closeSidebar = () => {
    setSidebarOpen(false);
  };

  return (
    <div className="zebio-app">

      {/* Ambient background effects */}
      <div className="ambient ambient-one" />
      <div className="ambient ambient-two" />

      {/* =====================================================
          TOP BAR
      ====================================================== */}

      <header className="topbar">

        <div className="brand-area">

          {/* Mobile menu button */}
          <button
            type="button"
            className="mobile-menu-button"
            aria-label={
              sidebarOpen
                ? 'Close navigation menu'
                : 'Open navigation menu'
            }
            aria-expanded={sidebarOpen}
            onClick={() =>
              setSidebarOpen((open) => !open)
            }
          >
            <span />
            <span />
            <span />
          </button>

          {/* ZEBIO brand / desktop-tablet menu trigger */}
          <button
            type="button"
            className="brand brand-menu-trigger"
            aria-label={
              sidebarOpen
                ? 'Close navigation menu'
                : 'Open navigation menu'
            }
            aria-expanded={sidebarOpen}
            onClick={() =>
              setSidebarOpen((open) => !open)
            }
          >

            <div
              className="brand-mark"
              aria-hidden="true"
            >
              <span />
              <span />
              <span />
            </div>

            <div>
              <div className="brand-name">
                ZEBIO
              </div>

              <div className="brand-subtitle">
                LOCAL AI ENGINEERING STUDIO
              </div>
            </div>

          </button>

        </div>

        <div className="topbar-status">

          <div
            className={`status-pill ${
              backendOnline === true
                ? 'online'
                : backendOnline === false
                  ? 'offline'
                  : ''
            }`}
          >
            <span className="status-dot" />

            {connectionLabel}
          </div>

          <div className="model-pill">

            <span className="model-pulse" />

            {modelName}

          </div>

        </div>

      </header>

      {/* =====================================================
          SIDEBAR
      ====================================================== */}

      <div
        className={`sidebar-backdrop ${
          sidebarOpen ? 'open' : ''
        }`}
        aria-hidden={!sidebarOpen}
        onClick={closeSidebar}
      />

      <aside
        className={`sidebar ${
          sidebarOpen ? 'open' : ''
        }`}
        aria-hidden={!sidebarOpen}
      >

        <div className="sidebar-header">

          <div>
            <div className="sidebar-title">
              ZEBIO
            </div>

            <div className="sidebar-subtitle">
              LOCAL AI ENGINEERING STUDIO
            </div>
          </div>

          <button
            type="button"
            className="sidebar-close"
            aria-label="Close navigation menu"
            onClick={closeSidebar}
          >
            ×
          </button>

        </div>

        <nav
          className="sidebar-nav"
          aria-label="Primary navigation"
        >

          <NavLink
            to="/"
            end
            onClick={closeSidebar}
            className={({ isActive }) =>
              `sidebar-nav-link ${
                isActive ? 'active' : ''
              }`
            }
          >
            <span className="sidebar-nav-index">
              01
            </span>

            <span>
              AI ENGINEER
            </span>
          </NavLink>

          <NavLink
            to="/projects/trading"
            onClick={closeSidebar}
            className={({ isActive }) =>
              `sidebar-nav-link ${
                isActive ? 'active' : ''
              }`
            }
          >
            <span className="sidebar-nav-index">
              02
            </span>

            <span>
              TRADING LAB
            </span>
          </NavLink>

          <NavLink
            to="/projects/tube"
            onClick={closeSidebar}
            className={({ isActive }) =>
              `sidebar-nav-link ${
                isActive ? 'active' : ''
              }`
            }
          >
            <span className="sidebar-nav-index">
              03
            </span>

            <span>
              TUBE GRAPH
            </span>
          </NavLink>

        </nav>

        <div className="sidebar-footer">
          <span className="sidebar-footer-dot" />
          PRIVATE LOCAL WORKSPACE
        </div>

      </aside>

      <main className="page-content">
        <Outlet />
      </main>

      {/* =====================================================
          FOOTER
      ====================================================== */}

      <footer className="footer">

        <span>
          ZEBIO STUDIO ENGINE · LOCAL FIRST
        </span>

        <span>
          AI ENGINEERING · MARKET INTELLIGENCE · PRIVATE WORKSPACE
        </span>

      </footer>

    </div>
  );
}

export default AppShell;