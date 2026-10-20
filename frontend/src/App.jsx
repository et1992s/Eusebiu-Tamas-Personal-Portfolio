import { useEffect } from 'react';
import { Routes, Route, Navigate, useLocation } from 'react-router-dom';

import PortfolioLayout from './layouts/PortfolioLayout';
import HomePage from './pages/HomePage';
import { getLenisInstance } from './components/portfolio/SmoothScroll';

import AppShell from './layouts/AppShell';
import AIChat from './components/AI/AIChat';
import ZebioPage from './pages/ZebioPage';
import TradingProjectPage from './pages/TradingProjectPage';
import TubeProjectPage from './pages/TubeProjectPage';

function ScrollToTop() {
  const { pathname } = useLocation();

  useEffect(() => {
    const lenis = getLenisInstance();

    if (lenis) {
      // Route change while Lenis is live — reset it, don't fight it
      lenis.scrollTo(0, { immediate: true });
    } else {
      // Zebio app / no Lenis — plain scroll reset
      window.scrollTo({ top: 0, left: 0, behavior: 'instant' });
    }
  }, [pathname]);

  return null;
}

function App() {
  return (
    <>
      <ScrollToTop />

      <Routes>
        <Route element={<PortfolioLayout />}>
          <Route path="/" element={<HomePage />} />
        </Route>

        <Route element={<AppShell />}>
          <Route path="/projects/zebio"          element={<AIChat />} />
          <Route path="/projects/trading"        element={<TradingProjectPage />} />
          <Route path="/projects/tube"           element={<TubeProjectPage />} />
          <Route path="/projects/zebio/engineer" element={<ZebioPage />} />
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  );
}

export default App;