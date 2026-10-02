import { useEffect } from 'react';
import { Routes, Route, Navigate, useLocation } from 'react-router-dom';

import PortfolioLayout from './layouts/PortfolioLayout';
import HomePage from './pages/HomePage';

import AppShell from './layouts/AppShell';
import AIChat from './components/AI/AIChat';
import ZebioPage from './pages/ZebioPage';
import TradingProjectPage from './pages/TradingProjectPage';
import TubeProjectPage from './pages/TubeProjectPage';

function ScrollToTop() {
  const { pathname } = useLocation();

  useEffect(() => {
    window.scrollTo({
      top: 0,
      left: 0,
      behavior: 'instant',
    });
  }, [pathname]);

  return null;
}

function App() {
  return (
    <>
      <ScrollToTop />

      <Routes>
        {/* Single-page portfolio */}
        <Route element={<PortfolioLayout />}>
          <Route path="/" element={<HomePage />} />
        </Route>

        {/* Public project applications */}
        <Route element={<AppShell />}>
          <Route
            path="/projects/zebio"
            element={<AIChat />}
          />

          <Route
            path="/projects/trading"
            element={<TradingProjectPage />}
          />

          <Route
            path="/projects/tube"
            element={<TubeProjectPage />}
          />

          {/* Private/local Zebio engineering workspace */}
          <Route
            path="/projects/zebio/engineer"
            element={<ZebioPage />}
          />
        </Route>

        {/* Fallback */}
        <Route
          path="*"
          element={<Navigate to="/" replace />}
        />
      </Routes>
    </>
  );
}

export default App;