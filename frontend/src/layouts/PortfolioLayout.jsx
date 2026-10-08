import { Outlet } from 'react-router-dom';
import PortfolioNav from '../components/portfolio/PortfolioNav';
import PortfolioFooter from '../components/portfolio/PortfolioFooter';
import '../styles/portfolio.css';

function PortfolioLayout() {
  return (
    <div className="portfolio-site">
      <PortfolioNav />

      <Outlet />

      <PortfolioFooter />
    </div>
  );
}

export default PortfolioLayout;
