import AboutChat from '../components/portfolio/AboutChat';

function AboutPage() {
  return (
    <main className="portfolio-page portfolio-about-page">
      <header className="portfolio-page-header">
        <h1>About</h1>

        <p>
          Ask Zebio about my background, projects, experience or skills.
        </p>
      </header>

      <AboutChat />
    </main>
  );
}

export default AboutPage;