import { useState } from 'react';
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

  return (
    <div className="portfolio-site">
      {/* Global ambience — once per site */}
      <SmoothScroll />
      <MouseLight />

      <PortfolioNav onOpenChat={() => setIsChatOpen(true)} />

      <Outlet />

      <div
        className={[
          'portfolio-chat-window',
          isChatOpen ? 'portfolio-chat-window--open' : '',
        ].filter(Boolean).join(' ')}
        aria-hidden={!isChatOpen}
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