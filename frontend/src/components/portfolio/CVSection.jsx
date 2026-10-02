import ScrollReveal from './ScrollReveal';

function CVSection() {
  return (
    <section
      id="cv"
      className="portfolio-page portfolio-cv-page"
    >
      <header className="portfolio-cv-header">
        <div>
          <ScrollReveal as="p" className="portfolio-eyebrow">
            Curriculum Vitae
          </ScrollReveal>

          <ScrollReveal as="h2" delay={80}>
            Eusebiu Tamas
          </ScrollReveal>

          <ScrollReveal
            as="p"
            className="portfolio-cv-role"
            delay={160}
          >
            Computer Science Graduate · AI / Machine Learning · Software
            Engineering
          </ScrollReveal>
        </div>

        <ScrollReveal
          className="portfolio-cv-actions"
          delay={240}
        >
          <a
            href="/Eusebiu_Tamas_Computer_Science_Graduate_CV.pdf"
            download="Eusebiu_Tamas_Computer_Science_Graduate_CV.pdf"
          >
            Download CV
          </a>
        </ScrollReveal>
      </header>

      <div className="portfolio-cv-contact">
        <ScrollReveal as="span">
          Warrington, UK
        </ScrollReveal>

        <ScrollReveal as="span" delay={60}>
          +44 7498 058272
        </ScrollReveal>

        <ScrollReveal as="span" delay={120}>
          eusebiutamas@outlook.com
        </ScrollReveal>

        <ScrollReveal as="span" delay={180}>
          <a
            href="https://www.linkedin.com/in/eusebiu-tamas/"
            target="_blank"
            rel="noreferrer"
          >
            LinkedIn
          </a>
        </ScrollReveal>

        <ScrollReveal as="span" delay={240}>
          <a
            href="https://github.com/et1992s"
            target="_blank"
            rel="noreferrer"
          >
            GitHub
          </a>
        </ScrollReveal>
      </div>

      <section className="portfolio-cv-section">
        <ScrollReveal as="h2">
          Profile
        </ScrollReveal>

        <ScrollReveal as="p" delay={80}>
          Computer Science graduate with a First-Class Honours degree and
          practical experience across machine learning, software development,
          data analysis and customer-facing operations. Interested in building
          reliable AI and data-driven systems with a strong focus on practical
          engineering, analytical problem solving and continuous learning.
        </ScrollReveal>
      </section>

      <section className="portfolio-cv-section">
        <ScrollReveal as="h2">
          Education
        </ScrollReveal>

        <ScrollReveal
          as="article"
          className="portfolio-cv-entry"
          delay={100}
        >
          <div className="portfolio-cv-entry-heading">
            <div>
              <h3>University of Greenwich</h3>
              <p>BSc (Hons) Computer Science · First-Class Honours</p>
            </div>

            <span>Sept 2021 – Jul 2025</span>
          </div>

          <p>London, UK · Overall result: 80/100</p>
        </ScrollReveal>

        <ScrollReveal
          as="article"
          className="portfolio-cv-entry"
          delay={180}
        >
          <div className="portfolio-cv-entry-heading">
            <div>
              <h3>Technological Lyceum Henri Coanda</h3>
              <p>
                Baccalaureate Diploma in Mathematics and Computer Science
              </p>
            </div>

            <span>Sept 2007 – Jul 2011</span>
          </div>

          <p>Ramnicu Valcea, Romania · Overall result: 6.05/10</p>
        </ScrollReveal>
      </section>

      <section className="portfolio-cv-section">
        <ScrollReveal as="h2">
          Selected Projects
        </ScrollReveal>

        <ScrollReveal
          as="article"
          className="portfolio-cv-project"
          delay={100}
        >
          <div className="portfolio-cv-entry-heading">
            <div>
              <h3>Recommending Intraday Stock Trading Strategies</h3>
              <p>Final Year Project · Python · TensorFlow · DEAP</p>
            </div>

            <span>Oct 2024 – May 2025</span>
          </div>

          <ul>
            <ScrollReveal as="li" delay={160}>
              Engineered a trading system using a hybrid CNN-BiLSTM model
              evaluated against traditional CNN and LSTM architectures.
            </ScrollReveal>

            <ScrollReveal as="li" delay={220}>
              Achieved a predictive R-squared score of 99.52% on 2016
              NASDAQ-100 test data through the simple LSTM model.
            </ScrollReveal>

            <ScrollReveal as="li" delay={280}>
              Demonstrated a Sharpe Ratio of 0.10 and generated $1,355 profit
              on a $100,000 simulated portfolio.
            </ScrollReveal>

            <ScrollReveal as="li" delay={340}>
              Managed the complete project independently, including the legal,
              social, ethical and professional considerations of AI in
              financial applications.
            </ScrollReveal>
          </ul>

          <ScrollReveal
            as="p"
            className="portfolio-cv-result"
            delay={400}
          >
            Overall result: 86/100
          </ScrollReveal>
        </ScrollReveal>

        <ScrollReveal
          as="article"
          className="portfolio-cv-project"
          delay={180}
        >
          <div className="portfolio-cv-entry-heading">
            <div>
              <h3>California House Price & Titanic Survival Predictions</h3>

              <p>
                Machine Learning Project · Python · TensorFlow · scikit-learn ·
                XGBoost
              </p>
            </div>

            <span>Jan 2025 – Mar 2025</span>
          </div>

          <ul>
            <ScrollReveal as="li" delay={240}>
              Developed regression models to estimate median house values using
              geographical and demographic features.
            </ScrollReveal>

            <ScrollReveal as="li" delay={300}>
              Implemented binary classification pipelines using multiple
              machine learning models to predict passenger survival.
            </ScrollReveal>

            <ScrollReveal as="li" delay={360}>
              Achieved an R-squared score of 63% with the Random Forest
              Regressor and an F1 score of 86.21% with the Support Vector
              Classifier.
            </ScrollReveal>
          </ul>

          <ScrollReveal
            as="p"
            className="portfolio-cv-result"
            delay={420}
          >
            Overall result: 78/100
          </ScrollReveal>
        </ScrollReveal>

        <ScrollReveal
          as="article"
          className="portfolio-cv-project"
          delay={260}
        >
          <div className="portfolio-cv-entry-heading">
            <div>
              <h3>Lloyds Banking Group Data Science</h3>

              <p>
                Job Simulation on Forage · Python · scikit-learn · XGBoost
              </p>
            </div>

            <span>Jun 2025 – Jul 2025</span>
          </div>

          <ul>
            <ScrollReveal as="li" delay={320}>
              Developed and implemented predictive models for customer churn
              using several machine learning algorithms.
            </ScrollReveal>

            <ScrollReveal as="li" delay={380}>
              Achieved an ROC-AUC score of 52% and an accuracy score of 78%
              using the Random Forest Classifier.
            </ScrollReveal>
          </ul>
        </ScrollReveal>
      </section>

      <section className="portfolio-cv-section">
        <ScrollReveal as="h2">
          Professional Experience
        </ScrollReveal>

        <ScrollReveal
          as="article"
          className="portfolio-cv-entry"
          delay={100}
        >
          <div className="portfolio-cv-entry-heading">
            <div>
              <h3>TfL Private Hire Driver · Uber Self-Employed</h3>
              <p>London, UK</p>
            </div>

            <span>Apr 2023 – Present</span>
          </div>

          <ul>
            <ScrollReveal as="li" delay={160}>
              Maintained a 4.98/5.00 rating across more than 5,000 passenger
              trips while consistently delivering high customer satisfaction.
            </ScrollReveal>

            <ScrollReveal as="li" delay={220}>
              Used Uber's driver dashboard to analyse trip patterns, reduce
              average idle time and improve weekly earnings.
            </ScrollReveal>
          </ul>
        </ScrollReveal>

        <ScrollReveal
          as="article"
          className="portfolio-cv-entry"
          delay={180}
        >
          <div className="portfolio-cv-entry-heading">
            <div>
              <h3>
                Front Desk Receptionist · Park Grand London Lancaster Gate
              </h3>
              <p>London, UK</p>
            </div>

            <span>Jun 2021 – Apr 2023</span>
          </div>

          <ul>
            <ScrollReveal as="li" delay={240}>
              Achieved a 95% guest-satisfaction rating while handling more than
              40 daily check-ins and reservations.
            </ScrollReveal>

            <ScrollReveal as="li" delay={300}>
              Managed more than 6,000 reservations in Opera PMS while
              maintaining 99% data accuracy and producing daily occupancy
              reports.
            </ScrollReveal>
          </ul>
        </ScrollReveal>

        <ScrollReveal
          as="article"
          className="portfolio-cv-entry"
          delay={260}
        >
          <div className="portfolio-cv-entry-heading">
            <div>
              <h3>Warehouse Operative · Ralawise LTD</h3>
              <p>Deeside, UK</p>
            </div>

            <span>Apr 2016 – May 2021</span>
          </div>

          <ul>
            <ScrollReveal as="li" delay={320}>
              Picked more than 400 products per day in a fast-paced warehouse
              environment.
            </ScrollReveal>

            <ScrollReveal as="li" delay={380}>
              Reduced order-picking errors by 20% after introducing quality
              checklists.
            </ScrollReveal>

            <ScrollReveal as="li" delay={440}>
              Adapted to VNA forklift technology, learning system controls and
              data-logging procedures within one week.
            </ScrollReveal>
          </ul>
        </ScrollReveal>

        <ScrollReveal
          as="article"
          className="portfolio-cv-entry"
          delay={340}
        >
          <div className="portfolio-cv-entry-heading">
            <div>
              <h3>Data Entry Clerk / Admin Officer · Intexim SRL</h3>
              <p>Ramnicu Valcea, Romania</p>
            </div>

            <span>Jul 2011 – Apr 2016</span>
          </div>

          <ul>
            <ScrollReveal as="li" delay={400}>
              Maintained 99.8% accuracy across more than 10,000 monthly
              records while meeting demanding deadlines.
            </ScrollReveal>

            <ScrollReveal as="li" delay={460}>
              Maintained high data integrity while adapting to changing
              operational requirements.
            </ScrollReveal>
          </ul>
        </ScrollReveal>
      </section>

      <section className="portfolio-cv-section">
        <ScrollReveal as="h2">
          Technical Skills
        </ScrollReveal>

        <div className="portfolio-cv-skills">
          <ScrollReveal as="div" delay={100}>
            <h3>Programming</h3>
            <p>Python · SQL · C++ · Java · R · PostgreSQL</p>
          </ScrollReveal>

          <ScrollReveal as="div" delay={160}>
            <h3>Machine Learning</h3>
            <p>TensorFlow · PyTorch · Keras · scikit-learn · XGBoost</p>
          </ScrollReveal>

          <ScrollReveal as="div" delay={220}>
            <h3>Data & Scientific Computing</h3>
            <p>NumPy · Pandas · Matplotlib · Seaborn · Jupyter</p>
          </ScrollReveal>

          <ScrollReveal as="div" delay={280}>
            <h3>Development & Systems</h3>
            <p>Linux/Unix · Git · GitHub · Microsoft Office 365</p>
          </ScrollReveal>

          <ScrollReveal as="div" delay={340}>
            <h3>Cloud & Infrastructure</h3>
            <p>Microsoft Azure · Google Cloud · VMware</p>
          </ScrollReveal>

          <ScrollReveal as="div" delay={400}>
            <h3>Big Data</h3>
            <p>Hadoop · HDFS · MapReduce</p>
          </ScrollReveal>
        </div>
      </section>

      <section className="portfolio-cv-section portfolio-cv-final-section">
        <div className="portfolio-cv-columns">
          <div>
            <ScrollReveal as="h2">
              Certifications
            </ScrollReveal>

            <ul>
              <ScrollReveal as="li" delay={100}>
                Python for Data Science, AI and Development — IBM
              </ScrollReveal>

              <ScrollReveal as="li" delay={160}>
                Tools for Data Science — IBM
              </ScrollReveal>
            </ul>
          </div>

          <div>
            <ScrollReveal as="h2">
              Interests
            </ScrollReveal>

            <ScrollReveal as="p" delay={100}>
              Mentoring and knowledge sharing · Entrepreneurship · Personal
              growth · Career development · Cross-cultural experiences
            </ScrollReveal>
          </div>
        </div>
      </section>
    </section>
  );
}

export default CVSection;