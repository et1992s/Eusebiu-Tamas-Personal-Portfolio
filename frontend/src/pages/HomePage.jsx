import { Link } from 'react-router-dom';

import CVSection from '../components/portfolio/CVSection';
import ScrollReveal from '../components/portfolio/ScrollReveal';
import ContactForm from '../components/portfolio/ContactForm';

function HomePage() {
  return (
    <main>
      {/* ── Hero ─────────────────────────────────────────── */}
      <section id="home" className="portfolio-home">
        <div className="portfolio-home-content">

          <div className="portfolio-home-main">
            <ScrollReveal as="div" className="portfolio-status-badge">
              <span className="portfolio-status-dot" aria-hidden="true" />
              <span>Available for graduate &amp; junior roles</span>
            </ScrollReveal>

            <ScrollReveal as="p" className="portfolio-eyebrow" delay={40}>
              Eusebiu Tamas
            </ScrollReveal>

            <ScrollReveal as="h1" delay={100}>
              Computer Science graduate building{' '}
              <span className="portfolio-accent-text">AI software</span>,
              ML systems &amp; data-driven applications.
            </ScrollReveal>

            <ScrollReveal as="p" className="portfolio-introduction" delay={180}>
              I design and engineer intelligent applications — from
              LLM-powered developer tools to machine-learning pipelines —
              with a focus on clean architecture and practical results.
            </ScrollReveal>

            <ScrollReveal className="portfolio-home-actions" delay={260}>
              <a href="#projects">
                Explore projects
                <span className="portfolio-action-arrow" aria-hidden="true">→</span>
              </a>
              <a href="#about">About me</a>
            </ScrollReveal>
          </div>

          <ScrollReveal className="portfolio-home-side" delay={300}>
            <div className="portfolio-now-card">
              <span className="portfolio-now-label">Currently building</span>
              <strong className="portfolio-now-title">Zebio</strong>
              <p className="portfolio-now-text">
                A local AI software-engineering platform combining large
                language models, autonomous workflows and persistent memory.
              </p>
              <Link to="/projects/zebio" className="portfolio-now-link">
                View project <span aria-hidden="true">→</span>
              </Link>
            </div>

            <div className="portfolio-stack-row" aria-label="Core stack">
              <span>Python</span>
              <span>React</span>
              <span>FastAPI</span>
              <span>TensorFlow</span>
              <span>Ollama</span>
            </div>
          </ScrollReveal>

        </div>
      </section>

      {/* ── About ────────────────────────────────────────── */}
      <section id="about" className="portfolio-page portfolio-about-page">
        <header className="portfolio-page-header">
          <ScrollReveal as="h1">About</ScrollReveal>
        </header>

        <div className="portfolio-about-layout">
          <ScrollReveal className="portfolio-about-image" delay={80}>
            <div className="portfolio-about-image-frame">
              <img
                src="/graduation.jpg"
                alt="Eusebiu Tamas at his Computer Science graduation"
              />
              <span className="portfolio-about-image-badge">
                BSc Computer Science
              </span>
            </div>
          </ScrollReveal>

          <div className="portfolio-about-content">
            <ScrollReveal as="div" className="portfolio-about-card" delay={160}>
              <p className="portfolio-about-lead">
                I&apos;m a Computer Science graduate with a strong interest in
                artificial intelligence, machine learning, software engineering
                and data-driven systems.
              </p>
            </ScrollReveal>

            <ScrollReveal as="div" className="portfolio-about-card" delay={240}>
              <p>
                My academic and independent work has given me experience building
                projects across Python, machine learning, backend development and
                data analysis. I enjoy understanding how complex systems work
                beneath the surface and turning that understanding into practical,
                well-structured software. I&apos;m currently continuing to develop
                these skills through Zebio, my local AI software-engineering
                platform, while exploring opportunities to apply them
                professionally.
              </p>
            </ScrollReveal>

            <ScrollReveal className="portfolio-about-skills" delay={320}>
              <p className="portfolio-about-skills-label">Core focus</p>
              <div className="portfolio-about-skills-list">
                <span>Machine Learning</span>
                <span>Python</span>
                <span>FastAPI</span>
                <span>React</span>
                <span>LLM Systems</span>
                <span>Data Analysis</span>
              </div>
            </ScrollReveal>
          </div>
        </div>
      </section>

      {/* ── Projects ─────────────────────────────────────── */}
      <section id="projects" className="portfolio-page">
        <header className="portfolio-page-header">
          <ScrollReveal as="h1">Projects</ScrollReveal>
          <ScrollReveal as="p" delay={80}>
            A selection of software, machine-learning and algorithmic systems
            developed across my academic and independent work.
          </ScrollReveal>
        </header>

        <section className="portfolio-project-list" aria-label="Projects">
          <ScrollReveal as={Link} to="/projects/zebio" className="portfolio-project-card" delay={120}>
            <h3>Zebio</h3>
            <p>
              A local AI software-engineering platform combining large language
              models, autonomous engineering workflows, persistent memory and
              developer tooling.
            </p>
            <div className="portfolio-project-card-meta">
              <span>Python</span><span>FastAPI</span>
              <span>React</span><span>Ollama</span>
            </div>
          </ScrollReveal>

          <ScrollReveal as={Link} to="/projects/trading" className="portfolio-project-card" delay={220}>
            <h3>Trading Lab</h3>
            <p>
              A machine-learning system for intraday stock-return prediction and
              trading-strategy research using technical indicators and deep
              learning models.
            </p>
            <div className="portfolio-project-card-meta">
              <span>Python</span><span>TensorFlow</span>
              <span>Machine Learning</span><span>Financial Data</span>
            </div>
          </ScrollReveal>

          <ScrollReveal as={Link} to="/projects/tube" className="portfolio-project-card" delay={320}>
            <h3>London Underground Route Optimisation</h3>
            <p>
              An algorithmic route-planning application using graph algorithms
              to calculate London Underground journeys and analyse network
              changes.
            </p>
            <div className="portfolio-project-card-meta">
              <span>Algorithms</span><span>Graph Theory</span>
              <span>React</span><span>Transport Data</span>
            </div>
          </ScrollReveal>
        </section>
      </section>

      <CVSection />

      {/* ── Contact ──────────────────────────────────────── */}
      <section id="contact" className="portfolio-page portfolio-contact-page">
        <header className="portfolio-page-header">
          <ScrollReveal as="h1">Contact</ScrollReveal>
          <ScrollReveal as="p" delay={80}>
            If you&apos;d like to discuss a project, opportunity or
            collaboration, feel free to get in touch.
          </ScrollReveal>
        </header>

        <ContactForm />
      </section>
    </main>
  );
}

export default HomePage;