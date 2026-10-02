import usePortfolioTheme from '../../hooks/usePortfolioTheme';

function PortfolioNav() {
  const { theme, toggleTheme } = usePortfolioTheme();

  const isDark = theme === 'dark';

  return (
    <header className="portfolio-nav">
      <div className="portfolio-nav-inner">
        <a
          href="#home"
          className="portfolio-nav-brand"
        >
          ET
        </a>

        <nav
          className="portfolio-nav-links"
          aria-label="Main navigation"
        >
          <a href="#about">About</a>
          <a href="#projects">Projects</a>
          <a href="#cv">CV</a>
          <a href="#contact">Contact</a>

          <button
            type="button"
            className="portfolio-theme-toggle"
            onClick={toggleTheme}
            aria-label={
              isDark
                ? 'Switch to light mode'
                : 'Switch to dark mode'
            }
            title={
              isDark
                ? 'Switch to light mode'
                : 'Switch to dark mode'
            }
          >
            <span
              className="portfolio-theme-toggle-icon"
              aria-hidden="true"
            >
              {isDark ? '☾' : '☀'}
            </span>
          </button>
        </nav>
      </div>
    </header>
  );
}

export default PortfolioNav;