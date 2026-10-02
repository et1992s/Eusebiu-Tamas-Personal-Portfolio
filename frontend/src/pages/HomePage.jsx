import { Link } from 'react-router-dom';

import AboutChat from '../components/portfolio/AboutChat';
import CVSection from '../components/portfolio/CVSection';
import ScrollReveal from '../components/portfolio/ScrollReveal';
import ContactForm from '../components/portfolio/ContactForm';

function HomePage() {
  return (
    <main>
      {/* Hero */}
      <section
        id="home"
        className="portfolio-home"
      >
        <div className="portfolio-home-content">
          <ScrollReveal as="p" className="portfolio-eyebrow">
            Eusebiu Tamas
          </ScrollReveal>

          <ScrollReveal as="h1" delay={80}>
            Computer Science graduate building
            <br />
            AI software, ML systems and data-driven applications.
          </ScrollReveal>

          <ScrollReveal
            as="p"
            className="portfolio-introduction"
            delay={160}
          >
            I build practical software across artificial intelligence,
            machine learning, data engineering and full-stack development.
          </ScrollReveal>

          <ScrollReveal
            className="portfolio-home-actions"
            delay={240}
          >
            <a href="#projects">
              Explore projects
            </a>

            <a href="#about">
              About me
            </a>
          </ScrollReveal>
        </div>
      </section>

      {/* About */}
      <section
        id="about"
        className="portfolio-page portfolio-about-page"
      >
        <header className="portfolio-page-header">
          <ScrollReveal as="h2">
            About
          </ScrollReveal>
        </header>

        <div className="portfolio-about-intro">
          <ScrollReveal
            className="portfolio-about-image"
            delay={80}
          >
            <img
              src="/graduation.jpg"
              alt="Eusebiu Tamas at his Computer Science graduation"
            />
          </ScrollReveal>

          <div className="portfolio-about-intro-text">
            <ScrollReveal as="p" delay={160}>
              I am a Computer Science graduate with a strong interest 
              in artificial intelligence, machine learning, software engineering 
              and data-driven systems. During my degree, 
              I developed a particular interest in applying these areas 
              to practical problems, from machine learning and algorithmic systems 
              to software architecture and intelligent applications.
            </ScrollReveal>  

            <ScrollReveal as="p" delay={240}>
              My academic and independent work has given me experience 
              building projects across Python, machine learning, backend development 
              and data analysis. I enjoy understanding how complex systems work beneath 
              the surface and turning that understanding into practical, well-structured 
              software. I am currently continuing to develop these skills through Zebio, 
              my local AI software engineering platform, while exploring opportunities 
              to apply them professionally.
            </ScrollReveal>

            <ScrollReveal as="p" delay={240}>
              Ask Zebio about my background, projects, experience or skills.
            </ScrollReveal>
          </div>
        </div>

        <ScrollReveal delay={320}>
          <AboutChat />
        </ScrollReveal>
      </section>

      {/* Projects */}
      <section
        id="projects"
        className="portfolio-page"
      >
        <header className="portfolio-page-header">
          <ScrollReveal as="h2">
            Projects
          </ScrollReveal>

          <ScrollReveal as="p" delay={80}>
            A selection of software, machine learning and algorithmic
            systems developed across my academic and independent work.
          </ScrollReveal>
        </header>

        <section
          className="portfolio-project-list"
          aria-label="Projects"
        >
          <ScrollReveal
            as={Link}
            to="/projects/zebio"
            className="portfolio-project-card"
            delay={120}
          >
            <h3>Zebio</h3>

            <p>
              A local AI software engineering platform combining large
              language models, autonomous engineering workflows,
              persistent memory and developer tooling.
            </p>

            <div className="portfolio-project-card-meta">
              <span>Python</span>
              <span>FastAPI</span>
              <span>React</span>
              <span>Ollama</span>
            </div>
          </ScrollReveal>

          <ScrollReveal
            as={Link}
            to="/projects/trading"
            className="portfolio-project-card"
            delay={220}
          >
            <h3>Intraday Trading ML System</h3>

            <p>
              A machine-learning system for intraday stock-return
              prediction and trading strategy research using technical
              indicators and deep learning models.
            </p>

            <div className="portfolio-project-card-meta">
              <span>Python</span>
              <span>TensorFlow</span>
              <span>Machine Learning</span>
              <span>Financial Data</span>
            </div>
          </ScrollReveal>

          <ScrollReveal
            as={Link}
            to="/projects/tube"
            className="portfolio-project-card"
            delay={320}
          >
            <h3>London Underground Route Optimisation</h3>

            <p>
              An algorithmic route-planning application using graph
              algorithms to calculate London Underground journeys and
              analyse network changes.
            </p>

            <div className="portfolio-project-card-meta">
              <span>Algorithms</span>
              <span>Graph Theory</span>
              <span>React</span>
              <span>Transport Data</span>
            </div>
          </ScrollReveal>
        </section>
      </section>

      {/* CV */}
      <CVSection />

      {/* Contact */}
      <section
        id="contact"
        className="portfolio-page portfolio-contact-page"
      >
        <header className="portfolio-page-header">
          <ScrollReveal as="h2">
            Contact
          </ScrollReveal>

          <ScrollReveal as="p" delay={80}>
            If you would like to discuss a project, opportunity or
            collaboration, feel free to get in touch.
          </ScrollReveal>
      </header>

      <ContactForm />
    </section>
    </main>
  );
}

export default HomePage;
