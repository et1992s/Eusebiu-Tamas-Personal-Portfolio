import { useState, useEffect, useRef } from 'react';
import { Outlet } from 'react-router-dom';
import PortfolioNav from '../components/portfolio/PortfolioNav';
import PortfolioFooter from '../components/portfolio/PortfolioFooter';
import AboutChat from '../components/portfolio/AboutChat';
import ZebioAvatar from '../components/portfolio/ZebioAvatar';
import SmoothScroll from '../components/portfolio/SmoothScroll';
import MouseLight from '../components/portfolio/MouseLight';
import '../styles/portfolio.css';

function PortfolioLayout() {
  const [isChatOpen, setIsChatOpen] = useState(false);
  const chatWindowRef = useRef(null);

  // Close chat when clicking outside
  useEffect(() => {
    if (!isChatOpen) return;

    const handleClickOutside = (event) => {
      // If click is outside the chat window, close it
      if (chatWindowRef.current && !chatWindowRef.current.contains(event.target)) {
        // Exception: If the user clicks the Zebio avatar in the nav bar to close it,
        // don't trigger the close here. Let the nav's onClick handler handle it.
        if (event.target.closest('.portfolio-zebio-menu')) {
          return;
        }
        setIsChatOpen(false);
      }
    };

    // Use 'mousedown' so it feels immediate and doesn't get blocked by focus events
    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isChatOpen]);

  return (
    <div className="portfolio-site">
      {/* Global ambience — once per site */}
      <SmoothScroll />
      <MouseLight />

      {/*
        We use a toggle here so clicking Zebio in the nav
        opens the chat if closed, or closes it if open.
      */}
      <PortfolioNav onOpenChat={() => setIsChatOpen((prev) => !prev)} />

      <Outlet />

      <div
        ref={chatWindowRef}
        className={[
          'portfolio-chat-window',
          isChatOpen ? 'portfolio-chat-window--open' : '',
        ].filter(Boolean).join(' ')}
        /* FIX: Use inert instead of aria-hidden to prevent the browser focus error */
        inert={!isChatOpen}
      >
        <header className="portfolio-chat-window-header">
          <div className="portfolio-chat-window-identity">
            <div className="portfolio-chat-window-avatar">
              <ZebioAvatar active />
            </div>

            <div className="portfolio-chat-window-heading">
              <h2>Eusebiu's AI Assistant</h2>
              <p>
                Ask Zebio about my background, projects, experience or skills.
              </p>
            </div>
          </div>

          <button
            type="button"
            className="portfolio-chat-window-close"
            onClick={() => setIsChatOpen(false)}
            aria-label="Close chat"
            title="Close chat"
            tabIndex={isChatOpen ? 0 : -1}
          >
            ×
          </button>
        </header>

        <AboutChat />
      </div>

      <PortfolioFooter />
    </div>
  );
}

export default PortfolioLayout;