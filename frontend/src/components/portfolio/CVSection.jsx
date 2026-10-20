import ScrollReveal from './ScrollReveal';
import {
  siPython,
  siPostgresql,
  siCplusplus,
  siR,
  siTensorflow,
  siPytorch,
  siKeras,
  siScikitlearn,
  siNumpy,
  siPandas,
  siJupyter,
  siLinux,
  siGit,
  siGithub,
  siGooglecloud,
  siVmware,
  siApachehadoop,
} from 'simple-icons';

import javaIcon from 'devicon/icons/java/java-original.svg';
import azureIcon from 'devicon/icons/azure/azure-original.svg';
import matplotlibIcon from 'devicon/icons/matplotlib/matplotlib-original.svg';

import microsoft365Icon from '../../assets/microsoft365.svg';
import seabornIcon from '../../assets/seaborn.svg';
import sqlIcon from '../../assets/sql.svg';
import xgboostIcon from '../../assets/xgboost.svg';


const skillGroups = [
  {
    title: 'Programming',
    skills: ['Python', 'SQL', 'C++', 'Java', 'R', 'PostgreSQL'],
  },
  {
    title: 'Machine Learning',
    skills: ['TensorFlow', 'PyTorch', 'Keras', 'scikit-learn', 'XGBoost'],
  },
  {
    title: 'Data & Scientific Computing',
    skills: ['NumPy', 'Pandas', 'Matplotlib', 'Seaborn', 'Jupyter'],
  },
  {
    title: 'Development & Systems',
    skills: ['Linux/Unix', 'Git', 'GitHub', 'Microsoft Office 365'],
  },
  {
    title: 'Cloud & Infrastructure',
    skills: ['Microsoft Azure', 'Google Cloud', 'VMware'],
  },
  {
    title: 'Big Data',
    skills: ['Hadoop', 'HDFS', 'MapReduce'],
  },
];

const skillIcons = {
  Python: siPython,
  SQL: null,
  'C++': siCplusplus,
  Java: null,
  R: siR,
  PostgreSQL: siPostgresql,
  TensorFlow: siTensorflow,
  PyTorch: siPytorch,
  Keras: siKeras,
  'scikit-learn': siScikitlearn,
  XGBoost: null,
  NumPy: siNumpy,
  Pandas: siPandas,
  Matplotlib: null,
  Seaborn: null,
  Jupyter: siJupyter,
  'Linux/Unix': siLinux,
  Git: siGit,
  GitHub: siGithub,
  'Microsoft Office 365': null,
  'Microsoft Azure': null,
  'Google Cloud': siGooglecloud,
  VMware: siVmware,
  Hadoop: siApachehadoop,
  HDFS: null,
  MapReduce: null,
};

const deviconSkillIcons = {
  Java: javaIcon,
  'Microsoft Azure': azureIcon,
  Matplotlib: matplotlibIcon,
  'Microsoft Office 365': microsoft365Icon,
  Seaborn: seabornIcon,
  SQL: sqlIcon,
  XGBoost: xgboostIcon,
};

const genericSkillPaths = {
  SQL: (
    <>
      <ellipse cx="12" cy="5" rx="7.5" ry="3" />
      <path d="M4.5 5v6c0 1.7 3.4 3 7.5 3s7.5-1.3 7.5-3V5" />
      <path d="M4.5 11v6c0 1.7 3.4 3 7.5 3s7.5-1.3 7.5-3v-6" />
    </>
  ),
  Java: (
    <>
      <path d="m8 5-5 7 5 7" />
      <path d="m16 5 5 7-5 7" />
      <path d="m14 4-4 16" />
    </>
  ),
  XGBoost: (
    <>
      <path d="M12 4v4M6 12v4M18 12v4M12 8H6v4M12 8h6v4" />
      <circle cx="12" cy="4" r="2" />
      <circle cx="6" cy="18" r="2" />
      <circle cx="18" cy="18" r="2" />
    </>
  ),
  Matplotlib: (
    <>
      <path d="M4 4v16h16" />
      <path d="m7 15 4-5 3 2 5-6" />
    </>
  ),
  Seaborn: (
    <>
      <path d="M4 19V5M4 19h16" />
      <path d="m6 15 4-5 3 3 5-7" />
      <circle cx="18" cy="6" r="1" />
    </>
  ),
  'Microsoft Office 365': (
    <>
      <rect x="3.5" y="3.5" width="7" height="7" rx="1" />
      <rect x="13.5" y="3.5" width="7" height="7" rx="1" />
      <rect x="3.5" y="13.5" width="7" height="7" rx="1" />
      <rect x="13.5" y="13.5" width="7" height="7" rx="1" />
    </>
  ),
  'Microsoft Azure': (
    <>
      <path d="m9 5-6 12h6l6-12h-6Z" />
      <path d="M12 17h9l-6-12" />
    </>
  ),
  HDFS: (
    <>
      <ellipse cx="12" cy="5" rx="7.5" ry="3" />
      <path d="M4.5 5v14c0 1.7 3.4 3 7.5 3s7.5-1.3 7.5-3V5" />
      <path d="M4.5 12c0 1.7 3.4 3 7.5 3s7.5-1.3 7.5-3" />
    </>
  ),
  MapReduce: (
    <>
      <rect x="2.5" y="3.5" width="6" height="5" rx="1" />
      <rect x="15.5" y="3.5" width="6" height="5" rx="1" />
      <rect x="9" y="15.5" width="6" height="5" rx="1" />
      <path d="M5.5 8.5v3h13v-3M12 11.5v4" />
    </>
  ),
};

function SkillIcon({ skill }) {
  const icon = skillIcons[skill];
  const deviconIcon = deviconSkillIcons[skill];

  if (!icon && deviconIcon) {
    return (
      <img
        className="portfolio-profile-skill-icon"
        src={deviconIcon}
        alt={`${skill} logo`}
      />
    );
  }

  if (!icon) {
    return (
      <svg
        className="portfolio-profile-skill-icon portfolio-profile-skill-icon--generic"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.7"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
        focusable="false"
      >
        {genericSkillPaths[skill] ?? (
          <>
            <path d="m8 8-4 4 4 4" />
            <path d="m16 8 4 4-4 4" />
            <path d="m14 5-4 14" />
          </>
        )}
      </svg>
    );
  }

  return (
    <svg
      className="portfolio-profile-skill-icon"
      viewBox="0 0 24 24"
      fill={`#${icon.hex}`}
      role="img"
      aria-label={`${skill} logo`}
      focusable="false"
    >
      <path d={icon.path} />
    </svg>
  );
}

const education = [
  {
    institution: 'University of Greenwich',
    qualification: 'BSc (Hons) Computer Science',
    result: 'Grade: First-Class Honours',
    period: '2021–2025',
    location: 'London, UK',
  },
  {
    institution: 'Technological Lyceum Henri Coanda',
    qualification: 'Baccalaureate Diploma in Mathematics and Computer Science',
    period: '2007–2011',
    location: 'Ramnicu Valcea, Romania',
  },
];

const certifications = [
  'Python for Data Science, AI and Development — IBM',
  'Tools for Data Science — IBM',
];

const featuredExperience = [
  {
    role: 'TfL Private Hire Driver',
    employer: 'Uber · Self-employed',
    period: 'Apr 2023–Present',
    location: 'London, UK',
    achievements: [
      'Maintained a 4.98/5 rating across more than 5,000 trips.',
      'Used Uber dashboard data to analyse trip patterns, reduce average idle time and improve weekly earnings.',
    ],
  },
  {
    role: 'Front Desk Receptionist',
    employer: 'Park Grand London Lancaster Gate',
    period: 'Jun 2021–Apr 2023',
    location: 'London, UK',
    achievements: [
      'Achieved 95% guest satisfaction while handling more than 40 daily check-ins and reservations.',
      'Managed more than 6,000 reservations in Opera PMS, maintaining 99% data accuracy and producing daily occupancy reports.',
    ],
  },
];

const earlierExperience = [
  {
    role: 'Warehouse Operative',
    employer: 'Ralawise LTD',
    period: 'Apr 2016–May 2021',
    location: 'Deeside, UK',
    achievements: [
      'Picked more than 400 products per day and reduced order-picking errors by 20% using quality checklists.',
      'Adapted to VNA forklift technology within one week.',
    ],
  },
  {
    role: 'Data Entry Clerk / Admin Officer',
    employer: 'Intexim SRL',
    period: 'Jul 2011–Apr 2016',
    location: 'Ramnicu Valcea, Romania',
    achievements: [
      'Maintained 99.8% accuracy across more than 10,000 monthly records.',
      'Supported data integrity and changing operational requirements.',
    ],
  },
];

function ExperienceEntry({ entry, featured = false, delay = 0 }) {
  return (
    <ScrollReveal
      as="article"
      delay={delay}
      className={[
        'portfolio-profile-experience-entry',
        featured ? 'portfolio-profile-experience-entry--featured' : '',
      ]
        .filter(Boolean)
        .join(' ')}
    >
      <div className="portfolio-profile-entry-heading">
        <div className="portfolio-profile-entry-main">
          <h3>{entry.role}</h3>
          <p className="portfolio-profile-entry-employer">
            {entry.employer}
          </p>
          <p className="portfolio-profile-entry-location">
            {entry.location}
          </p>
        </div>

        <span className="portfolio-profile-entry-period">
          {entry.period}
        </span>
      </div>

      <ul className="portfolio-profile-achievements">
        {entry.achievements.map((achievement) => (
          <li key={achievement}>{achievement}</li>
        ))}
      </ul>
    </ScrollReveal>
  );
}

function CVSection() {
  return (
    <div className="portfolio-profile-sections">
      {/* Skills */}
      <ScrollReveal
        as="section"
        id="skills"
        className="portfolio-page portfolio-profile-section portfolio-profile-skills"
      >
        <div className="portfolio-profile-section-heading">
          <p className="portfolio-profile-eyebrow">Technical capabilities</p>
          <h2>Skills</h2>
          <p className="portfolio-profile-section-intro">
            Technologies and tools used across programming, machine learning,
            data analysis and software development.
          </p>
        </div>

        <div className="portfolio-profile-skill-groups">
          {skillGroups.map((group, index) => (
            <ScrollReveal
              as="article"
              className="portfolio-profile-skill-group"
              key={group.title}
              delay={120 + index * 100}
            >
              <span className="portfolio-profile-index">
                {String(index + 1).padStart(2, '0')}
              </span>

              <div className="portfolio-profile-skill-content">
                <h3>{group.title}</h3>
                <ul className="portfolio-profile-skill-list">
                  {group.skills.map((skill) => (
                    <li key={skill}>
                      <SkillIcon skill={skill} />
                      <span>{skill}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </ScrollReveal>
          ))}
        </div>
      </ScrollReveal>

      {/* Education and certifications */}
      <ScrollReveal
        as="section"
        id="education"
        className="portfolio-page portfolio-profile-section portfolio-profile-education"
      >
        <div className="portfolio-profile-section-heading">
          <p className="portfolio-profile-eyebrow">Academic background</p>
          <h2>Education &amp; Certifications</h2>
          <p className="portfolio-profile-section-intro">
            Formal education in computer science, mathematics and computing,
            complemented by IBM professional certificates.
          </p>
        </div>

        <div className="portfolio-profile-education-list">
          {education.map((entry, index) => (
            <ScrollReveal
              as="article"
              className="portfolio-profile-education-entry"
              key={entry.institution}
              delay={120 + index * 100}
            >
              <span className="portfolio-profile-index">
                {String(index + 1).padStart(2, '0')}
              </span>

              <div className="portfolio-profile-education-content">
                <div className="portfolio-profile-entry-heading">
                  <div className="portfolio-profile-entry-main">
                    <h3>{entry.institution}</h3>
                    <p>{entry.qualification}</p>
                  </div>

                  <span className="portfolio-profile-entry-period">
                    {entry.period}
                  </span>
                </div>

                {entry.result && (
                  <p className="portfolio-profile-education-result">
                    {entry.result}
                  </p>
                )}

                <p className="portfolio-profile-entry-location">
                  {entry.location}
                </p>
              </div>
            </ScrollReveal>
          ))}
        </div>

        <div className="portfolio-profile-certifications">
          <ScrollReveal
            className="portfolio-profile-subheading"
            delay={120}
          >
            <span className="portfolio-profile-eyebrow">
              Professional development
            </span>
            <h3>Certifications</h3>
          </ScrollReveal>

          <ul className="portfolio-profile-certification-list">
            {certifications.map((certification, index) => (
              <ScrollReveal
                as="li"
                key={certification}
                delay={220 + index * 100}
              >
                <span
                  className="portfolio-profile-certification-mark"
                  aria-hidden="true"
                >
                  ↗
                </span>
                <span>{certification}</span>
              </ScrollReveal>
            ))}
          </ul>
        </div>
      </ScrollReveal>

      {/* Professional experience */}
      <ScrollReveal
        as="section"
        id="experience"
        className="portfolio-page portfolio-profile-section portfolio-profile-experience"
      >
        <div className="portfolio-profile-section-heading">
          <p className="portfolio-profile-eyebrow">Professional background</p>
          <h2>Experience</h2>
          <p className="portfolio-profile-section-intro">
            Experience spanning data accuracy, operational reporting,
            customer-facing responsibilities and data-informed decisions.
          </p>
        </div>

        <div className="portfolio-profile-featured-experience">
          {featuredExperience.map((entry, index) => (
            <ExperienceEntry
              key={`${entry.employer}-${entry.role}`}
              entry={entry}
              featured
              delay={120 + index * 100}
            />
          ))}
        </div>

        <div className="portfolio-profile-earlier-experience">
          <h3 className="portfolio-profile-subheading-title">
            Earlier experience
          </h3>

          {earlierExperience.map((entry, index) => (
            <ExperienceEntry
              key={`${entry.employer}-${entry.role}`}
              entry={entry}
              delay={120 + index * 100}
            />
          ))}
        </div>
      </ScrollReveal>
    </div>
  );
}

export default CVSection;