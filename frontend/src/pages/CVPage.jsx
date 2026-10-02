function CVPage() {
  return (
    <main className="portfolio-page portfolio-cv-page">
      <header className="portfolio-cv-header">
        <div>
          <p className="portfolio-eyebrow">Curriculum Vitae</p>

          <h1>Eusebiu Tamas</h1>

          <p className="portfolio-cv-role">
            Computer Science Graduate · AI / Machine Learning · Software
            Engineering
          </p>
        </div>

        <div className="portfolio-cv-actions">
          <a
            href="/Eusebiu_Tamas_Computer_Science_Graduate_CV.pdf"
            download="Eusebiu_Tamas_Computer_Science_Graduate_CV.pdf"
          >
            Download CV
          </a>
        </div>
      </header>

      <div className="portfolio-cv-contact">
        <span>Warrington, UK</span>
        <span>+44 7498 058272</span>
        <span>eusebiutamas@outlook.com</span>
        <a
          href="https://www.linkedin.com/in/eusebiu-tamas/"
          target="_blank"
          rel="noreferrer"
        >
          LinkedIn
        </a>
        <a
          href="https://github.com/et1992s"
          target="_blank"
          rel="noreferrer"
        >
          GitHub
        </a>
      </div>

      <section className="portfolio-cv-section">
        <h2>Profile</h2>

        <p>
          Computer Science graduate with a First-Class Honours degree and
          practical experience across machine learning, software development,
          data analysis and customer-facing operations. Interested in building
          reliable AI and data-driven systems with a strong focus on practical
          engineering, analytical problem solving and continuous learning.
        </p>
      </section>

      <section className="portfolio-cv-section">
        <h2>Education</h2>

        <article className="portfolio-cv-entry">
          <div className="portfolio-cv-entry-heading">
            <div>
              <h3>University of Greenwich</h3>
              <p>BSc (Hons) Computer Science · First-Class Honours</p>
            </div>

            <span>Sept 2021 – Jul 2025</span>
          </div>

          <p>London, UK · Overall result: 80/100</p>
        </article>

        <article className="portfolio-cv-entry">
          <div className="portfolio-cv-entry-heading">
            <div>
              <h3>Technological Lyceum Henri Coanda</h3>
              <p>Baccalaureate Diploma in Mathematics and Computer Science</p>
            </div>

            <span>Sept 2007 – Jul 2011</span>
          </div>

          <p>Ramnicu Valcea, Romania · Overall result: 6.05/10</p>
        </article>
      </section>

      <section className="portfolio-cv-section">
        <h2>Selected Projects</h2>

        <article className="portfolio-cv-project">
          <div className="portfolio-cv-entry-heading">
            <div>
              <h3>Recommending Intraday Stock Trading Strategies</h3>
              <p>Final Year Project · Python · TensorFlow · DEAP</p>
            </div>

            <span>Oct 2024 – May 2025</span>
          </div>

          <ul>
            <li>
              Engineered a trading system using a hybrid CNN-BiLSTM model
              evaluated against traditional CNN and LSTM architectures.
            </li>
            <li>
              Achieved a predictive R-squared score of 99.52% on 2016
              NASDAQ-100 test data through the simple LSTM model.
            </li>
            <li>
              Demonstrated a Sharpe Ratio of 0.10 and generated $1,355 profit
              on a $100,000 simulated portfolio.
            </li>
            <li>
              Managed the complete project independently, including the legal,
              social, ethical and professional considerations of AI in
              financial applications.
            </li>
          </ul>

          <p className="portfolio-cv-result">
            Overall result: 86/100
          </p>
        </article>

        <article className="portfolio-cv-project">
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
            <li>
              Developed regression models to estimate median house values using
              geographical and demographic features.
            </li>
            <li>
              Implemented binary classification pipelines using multiple
              machine learning models to predict passenger survival.
            </li>
            <li>
              Achieved an R-squared score of 63% with the Random Forest
              Regressor and an F1 score of 86.21% with the Support Vector
              Classifier.
            </li>
          </ul>

          <p className="portfolio-cv-result">
            Overall result: 78/100
          </p>
        </article>

        <article className="portfolio-cv-project">
          <div className="portfolio-cv-entry-heading">
            <div>
              <h3>Lloyds Banking Group Data Science</h3>
              <p>Job Simulation on Forage · Python · scikit-learn · XGBoost</p>
            </div>

            <span>Jun 2025 – Jul 2025</span>
          </div>

          <ul>
            <li>
              Developed and implemented predictive models for customer churn
              using several machine learning algorithms.
            </li>
            <li>
              Achieved an ROC-AUC score of 52% and an accuracy score of 78%
              using the Random Forest Classifier.
            </li>
          </ul>
        </article>
      </section>

      <section className="portfolio-cv-section">
        <h2>Professional Experience</h2>

        <article className="portfolio-cv-entry">
          <div className="portfolio-cv-entry-heading">
            <div>
              <h3>TfL Private Hire Driver · Uber Self-Employed</h3>
              <p>London, UK</p>
            </div>

            <span>Apr 2023 – Present</span>
          </div>

          <ul>
            <li>
              Maintained a 4.98/5.00 rating across more than 5,000 passenger
              trips while consistently delivering high customer satisfaction.
            </li>
            <li>
              Used Uber's driver dashboard to analyse trip patterns, reduce
              average idle time and improve weekly earnings.
            </li>
          </ul>
        </article>

        <article className="portfolio-cv-entry">
          <div className="portfolio-cv-entry-heading">
            <div>
              <h3>Front Desk Receptionist · Park Grand London Lancaster Gate</h3>
              <p>London, UK</p>
            </div>

            <span>Jun 2021 – Apr 2023</span>
          </div>

          <ul>
            <li>
              Achieved a 95% guest-satisfaction rating while handling more than
              40 daily check-ins and reservations.
            </li>
            <li>
              Managed more than 6,000 reservations in Opera PMS while
              maintaining 99% data accuracy and producing daily occupancy
              reports.
            </li>
          </ul>
        </article>

        <article className="portfolio-cv-entry">
          <div className="portfolio-cv-entry-heading">
            <div>
              <h3>Warehouse Operative · Ralawise LTD</h3>
              <p>Deeside, UK</p>
            </div>

            <span>Apr 2016 – May 2021</span>
          </div>

          <ul>
            <li>
              Picked more than 400 products per day in a fast-paced warehouse
              environment.
            </li>
            <li>
              Reduced order-picking errors by 20% after introducing quality
              checklists.
            </li>
            <li>
              Adapted to VNA forklift technology, learning system controls and
              data-logging procedures within one week.
            </li>
          </ul>
        </article>

        <article className="portfolio-cv-entry">
          <div className="portfolio-cv-entry-heading">
            <div>
              <h3>Data Entry Clerk / Admin Officer · Intexim SRL</h3>
              <p>Ramnicu Valcea, Romania</p>
            </div>

            <span>Jul 2011 – Apr 2016</span>
          </div>

          <ul>
            <li>
              Maintained 99.8% accuracy across more than 10,000 monthly
              records while meeting demanding deadlines.
            </li>
            <li>
              Maintained high data integrity while adapting to changing
              operational requirements.
            </li>
          </ul>
        </article>
      </section>

      <section className="portfolio-cv-section">
        <h2>Technical Skills</h2>

        <div className="portfolio-cv-skills">
          <div>
            <h3>Programming</h3>
            <p>Python · SQL · C++ · Java · R · PostgreSQL</p>
          </div>

          <div>
            <h3>Machine Learning</h3>
            <p>TensorFlow · PyTorch · Keras · scikit-learn · XGBoost</p>
          </div>

          <div>
            <h3>Data & Scientific Computing</h3>
            <p>NumPy · Pandas · Matplotlib · Seaborn · Jupyter</p>
          </div>

          <div>
            <h3>Development & Systems</h3>
            <p>Linux/Unix · Git · GitHub · Microsoft Office 365</p>
          </div>

          <div>
            <h3>Cloud & Infrastructure</h3>
            <p>Microsoft Azure · Google Cloud · VMware</p>
          </div>

          <div>
            <h3>Big Data</h3>
            <p>Hadoop · HDFS · MapReduce</p>
          </div>
        </div>
      </section>

      <section className="portfolio-cv-section portfolio-cv-final-section">
        <div className="portfolio-cv-columns">
          <div>
            <h2>Certifications</h2>

            <ul>
              <li>Python for Data Science, AI and Development — IBM</li>
              <li>Tools for Data Science — IBM</li>
            </ul>
          </div>

          <div>
            <h2>Interests</h2>

            <p>
              Mentoring and knowledge sharing · Entrepreneurship · Personal
              growth · Career development · Cross-cultural experiences
            </p>
          </div>
        </div>
      </section>
    </main>
  );
}

export default CVPage;