import { useEffect, useState } from 'react';

const STORAGE_KEY = 'portfolio-theme';

function getInitialTheme() {
  const storedTheme = window.localStorage.getItem(STORAGE_KEY);

  if (storedTheme === 'light' || storedTheme === 'dark') {
    return storedTheme;
  }

  return window.matchMedia('(prefers-color-scheme: dark)').matches
    ? 'dark'
    : 'light';
}

function usePortfolioTheme() {
  const [theme, setTheme] = useState(getInitialTheme);

  useEffect(() => {
    const portfolioSite = document.querySelector('.portfolio-site');

    if (!portfolioSite) {
      return;
    }

    portfolioSite.dataset.theme = theme;
    document.documentElement.style.colorScheme = theme;

    window.localStorage.setItem(STORAGE_KEY, theme);
  }, [theme]);

  function toggleTheme() {
    setTheme((currentTheme) =>
      currentTheme === 'dark' ? 'light' : 'dark',
    );
  }

  return {
    theme,
    toggleTheme,
  };
}

export default usePortfolioTheme;