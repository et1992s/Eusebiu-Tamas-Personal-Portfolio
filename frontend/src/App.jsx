import { Routes, Route, Navigate } from 'react-router-dom';
import AppShell from './layouts/AppShell';
import HomePage from './pages/HomePage';
import TradingProjectPage from './pages/TradingProjectPage';
import TubeProjectPage from './pages/TubeProjectPage';

function App() {
  return (
    <Routes>

      <Route element={<AppShell />}>

        <Route
          path="/"
          element={<HomePage />}
        />

        <Route
          path="/projects/trading"
          element={<TradingProjectPage />}
        />

        <Route
          path="/projects/tube"
          element={<TubeProjectPage />}
        />

      </Route>

      <Route
        path="*"
        element={<Navigate to="/" replace />}
      />

    </Routes>
  );
}

export default App;