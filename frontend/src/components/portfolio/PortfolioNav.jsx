import { useEffect, useState } from 'react';
import usePortfolioTheme from '../../hooks/usePortfolioTheme';
import ZebioAvatar from './ZebioAvatar';

function PortfolioNav({ onOpenChat }) {
  const { theme, toggleTheme } = usePortfolioTheme();
  const [isPopoverOpen, setIsPopoverOpen] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  useEffect(() => {
    if (!isMobileMenuOpen) {
      return;
    }

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, [isMobileMenuOpen]);

  const isDark = theme === 'dark';

  const closePopover = () => {
    setIsPopoverOpen(false);
  };

  const handleAvatarClick = () => {
    console.log('[Zebio diagnostic] Avatar click handler fired');
    handleOpenChat();
  };

  const handleOpenChat = () => {
    closePopover();
    onOpenChat?.();
  };

  return (
    <header className="portfolio-nav">
      <div className="portfolio-nav-inner">
        <a
          href="#home"
          className="portfolio-nav-brand"
          aria-label="Eusebiu Tamas — Home"
        >
          <img
            src="/portfolio-logo.png"
            alt="Eusebiu Tamas"
            className="portfolio-nav-logo"
          />
        </a>

        <div className="portfolio-nav-controls">
          {isMobileMenuOpen && (
            <button
              type="button"
              className="portfolio-mobile-menu-backdrop"
              aria-label="Close navigation menu"
              onClick={() => setIsMobileMenuOpen(false)}
            />
          )}

          {/* Zebio avatar — positioned before the navigation links */}
          <div
            className={[
              'portfolio-zebio-menu',
              isPopoverOpen ? 'portfolio-zebio-menu--open' : '',
            ].filter(Boolean).join(' ')}
            onMouseEnter={() => setIsPopoverOpen(true)}
            onMouseLeave={closePopover}
            onFocus={() => setIsPopoverOpen(true)}
          >
            <div className="portfolio-zebio-trigger">
              <ZebioAvatar
                active
                onClick={handleAvatarClick}
              />
            </div>

            <div
              className="portfolio-zebio-popover"
              aria-hidden={!isPopoverOpen}
              inert={!isPopoverOpen}
            >
              <p className="portfolio-zebio-popover-title">
                Meet Zebio
              </p>

              <p className="portfolio-zebio-popover-text">
                Curious about my background or projects?
              </p>

              <button
                type="button"
                className="portfolio-zebio-open-chat"
                onClick={handleOpenChat}
              >
                Open Chat
              </button>
            </div>
          </div>

          <nav
            id="portfolio-mobile-navigation"
            className={[
              'portfolio-nav-links',
              isMobileMenuOpen ? 'portfolio-nav-links--mobile-open' : '',
            ].filter(Boolean).join(' ')}
            aria-label="Main navigation"
          >
            <a href="#about" onClick={() => setIsMobileMenuOpen(false)}>
              About
            </a>

            <a href="#projects" onClick={() => setIsMobileMenuOpen(false)}>
              Projects
            </a>

            <a href="#cv" onClick={() => setIsMobileMenuOpen(false)}>
              CV
            </a>

            <a href="#contact" onClick={() => setIsMobileMenuOpen(false)}>
              Contact
            </a>
          </nav>

          <button
            type="button"
            className="portfolio-theme-toggle"
            onClick={toggleTheme}
            aria-label={
              isDark ? 'Switch to light mode' : 'Switch to dark mode'
            }
            title={
              isDark ? 'Switch to light mode' : 'Switch to dark mode'
            }
          >
            <span className="portfolio-theme-toggle-icon" aria-hidden="true">
              {isDark ? (
                <svg
                  viewBox="0 0 24 24"
                  width="18"
                  height="18"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M20.9 13.1A8.5 8.5 0 0 1 10.9 3.1 8.5 8.5 0 1 0 20.9 13.1Z" />
                </svg>
              ) : (
                <svg
                  viewBox="0 0 24 24"
                  width="18"
                  height="18"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <circle cx="12" cy="12" r="4" />
                  <path d="M12 2v2m0 16v2M4.93 4.93l1.42 1.42m11.3 11.3 1.42 1.42M2 12h2m16 0h2M4.93 19.07l1.42-1.42m11.3-11.3 1.42-1.42" />
                </svg>
              )}
            </span>
          </button>

          <button
            type="button"
            className="portfolio-mobile-menu-toggle"
            onClick={() => setIsMobileMenuOpen((open) => !open)}
            aria-label={
              isMobileMenuOpen
                ? 'Close navigation menu'
                : 'Open navigation menu'
            }
            aria-expanded={isMobileMenuOpen}
            aria-controls="portfolio-mobile-navigation"
          >
            <span aria-hidden="true">
              {isMobileMenuOpen ? '×' : '☰'}
            </span>
          </button>
        </div>
      </div>
    </header>
  );
}

export default PortfolioNav;