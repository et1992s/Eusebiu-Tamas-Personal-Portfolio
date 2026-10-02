import { Outlet } from 'react-router-dom';
import PortfolioNav from '../components/portfolio/PortfolioNav';
import '../styles/portfolio.css';

function PortfolioLayout() {
  return (
    <div className="portfolio-site">
      <PortfolioNav />

      <Outlet />
    </div>
  );
}

export default PortfolioLayout;
