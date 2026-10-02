import { Link } from 'react-router-dom';

function ProjectsPage() {
  return (
    <main className="portfolio-page">
      <header className="portfolio-page-header">
        <h1>Projects</h1>

        <p>
          A selection of software, machine learning and algorithmic systems
          developed across my academic and independent work.
        </p>
      </header>

      <section className="portfolio-project-list" aria-label="Projects">
        <Link
          to="/projects/zebio"
          className="portfolio-project-card"
        >
          <h2>Zebio</h2>

          <p>
            A local AI software engineering platform combining large language
            models, autonomous engineering workflows, persistent memory and
            developer tooling.
          </p>

          <div className="portfolio-project-card-meta">
            <span>Python</span>
            <span>FastAPI</span>
            <span>React</span>
            <span>Ollama</span>
          </div>
        </Link>

        <Link
          to="/projects/trading"
          className="portfolio-project-card"
        >
          <h2>Intraday Trading ML System</h2>

          <p>
            A machine-learning system for intraday stock-return prediction and
            trading strategy research using technical indicators and deep
            learning models.
          </p>

          <div className="portfolio-project-card-meta">
            <span>Python</span>
            <span>TensorFlow</span>
            <span>Machine Learning</span>
            <span>Financial Data</span>
          </div>
        </Link>

        <Link
          to="/projects/tube"
          className="portfolio-project-card"
        >
          <h2>London Underground Route Optimisation</h2>

          <p>
            An algorithmic route-planning application using graph algorithms
            to calculate London Underground journeys and analyse network
            changes.
          </p>

          <div className="portfolio-project-card-meta">
            <span>Algorithms</span>
            <span>Graph Theory</span>
            <span>React</span>
            <span>Transport Data</span>
          </div>
        </Link>
      </section>
    </main>
  );
}

export default ProjectsPage;
