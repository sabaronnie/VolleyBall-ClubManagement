import { useEffect } from "react";

const navItems = [
  { label: "Home", sectionId: "home" },
  { label: "Features", sectionId: "features" },
  { label: "Clubs", sectionId: "roles" },
  { label: "Parents", sectionId: "faq" },
  { label: "About", sectionId: "about" },
];

const homepageImages = {
  hero: "/homepage/hero-volleyball.png",
  stripTop: "/homepage/strip-top.png",
  stripMiddle: "/homepage/strip-middle.png",
  stripBottom: "/homepage/strip-bottom.png",
};

const featureFeed = [
  {
    category: "Club Operations",
    title: "Create clubs and structure teams in minutes.",
    description:
      "Directors and coaches can launch club spaces, build squads, and keep responsibilities clear from day one.",
  },
  {
    category: "Roster Control",
    title: "Manage rosters with role-aware updates.",
    description:
      "Player assignments, coach roles, and captain changes stay organized in one shared workflow.",
  },
  {
    category: "Scheduling",
    title: "Keep practices, matches, and planning aligned.",
    description:
      "Teams can track activity and stay in sync around the rhythm of the season without scattered tools.",
  },
  {
    category: "Parent Access",
    title: "Give families connected, protected access.",
    description:
      "Parents can stay close to younger athletes while age-aware permissions protect the right self-service boundaries.",
  },
];

const platformStats = [
  {
    value: "4",
    label: "core user roles supported",
  },
  {
    value: "1",
    label: "shared workspace for the whole club",
  },
  {
    value: "24/7",
    label: "access to schedules, rosters, and updates",
  },
];

const trustBrands = [
  { name: "Mikasa", mark: "M" },
  { name: "Molten", mark: "MO" },
  { name: "Wilson", mark: "W" },
  { name: "Mizuno", mark: "MI" },
  { name: "ASICS", mark: "A" },
  { name: "adidas", mark: "ad" },
];

const valueHighlights = [
  {
    title: "Less admin overhead",
    description:
      "Cut down on scattered messages and manual follow-ups by keeping the core club workflow in one place.",
  },
  {
    title: "Clearer team ownership",
    description:
      "Directors and coaches can see who belongs where, who is responsible for what, and what still needs attention.",
  },
  {
    title: "A better family experience",
    description:
      "Parents get visibility without clubs sacrificing structure, boundaries, or role-based access control.",
  },
];

const journeySteps = [
  {
    number: "01",
    title: "Launch your club space",
    description:
      "Set up your organization, create teams, and invite the right people without messy handoffs.",
  },
  {
    number: "02",
    title: "Keep everyone aligned",
    description:
      "Manage rosters, staff responsibilities, and day-to-day updates from one connected system.",
  },
  {
    number: "03",
    title: "Support families with confidence",
    description:
      "Give parents visibility and athletes the right level of access with age-aware controls built in.",
  },
];

const roleSpotlights = [
  {
    role: "Directors",
    title: "See the full club picture.",
    description:
      "Track teams, coaches, and memberships from a single operational view that helps the season stay organized.",
  },
  {
    role: "Coaches",
    title: "Work with cleaner rosters.",
    description:
      "Spend less time untangling lists and more time coaching with up-to-date team information.",
  },
  {
    role: "Players",
    title: "Stay connected to your team.",
    description:
      "Give athletes a clearer view of their role, their team space, and the structure around them.",
  },
  {
    role: "Parents",
    title: "Stay informed with confidence.",
    description:
      "Follow younger athletes through parent-linked access that keeps communication and visibility simple.",
  },
];

const faqs = [
  {
    question: "Who is NetUp for?",
    answer:
      "NetUp is designed for volleyball clubs that need one platform for directors, coaches, players, and parents to work together.",
  },
  {
    question: "Can parents and players use the same system?",
    answer:
      "Yes. Parent-linked access is part of the workflow, so families can stay informed while clubs keep the right boundaries in place.",
  },
  {
    question: "What makes it different from scattered tools?",
    answer:
      "Instead of splitting club operations across messages, spreadsheets, and separate apps, NetUp keeps the core workflow in one place.",
  },
];

const showcaseStrips = [
  {
    src: homepageImages.stripTop,
    alt: "Red and yellow volleyball above a blue court backdrop",
    className: "showcase-strip showcase-strip--top",
  },
  {
    src: homepageImages.stripMiddle,
    alt: "Blue and yellow volleyball over stadium seating",
    className: "showcase-strip showcase-strip--middle",
  },
  {
    src: homepageImages.stripBottom,
    alt: "White volleyball against a warm blurred background",
    className: "showcase-strip showcase-strip--bottom",
  },
];

const footerLinks = [
  { label: "Features", sectionId: "features" },
  { label: "Clubs", sectionId: "roles" },
  { label: "Teams", sectionId: "journey" },
  { label: "Parents", sectionId: "faq" },
  { label: "Contact", sectionId: "cta" },
];

function App() {
  useEffect(() => {
    const revealElements = document.querySelectorAll(".reveal-on-scroll");

    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      revealElements.forEach((element) => {
        element.classList.add("is-visible");
      });
      return undefined;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) {
            return;
          }

          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        });
      },
      {
        threshold: 0.18,
        rootMargin: "0px 0px -10% 0px",
      },
    );

    revealElements.forEach((element) => {
      observer.observe(element);
    });

    return () => {
      observer.disconnect();
    };
  }, []);

  const scrollToSection = (sectionId) => {
    const section = document.getElementById(sectionId);

    if (!section) {
      return;
    }

    section.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <div className="homepage-shell">
      <section id="home" className="hero-section">
        <div
          className="hero-backdrop"
          style={{ "--hero-image": `url(${homepageImages.hero})` }}
        />
        <header className="site-nav">
          <div className="nav-left">
            {navItems.map((item) => (
              <button
                key={item.label}
                className="nav-button"
                type="button"
                onClick={() => scrollToSection(item.sectionId)}
              >
                {item.label}
              </button>
            ))}
          </div>

          <div className="nav-right">
            <span className="brand-mark">NetUp</span>
            <button
              className="action-button action-button--ghost"
              type="button"
              onClick={() => scrollToSection("cta")}
            >
              Register
            </button>
            <button
              className="action-button"
              type="button"
              onClick={() => scrollToSection("journey")}
            >
              Login
            </button>
          </div>
        </header>

        <div className="hero-content">
          <div className="hero-copy reveal-on-scroll" data-reveal="left">
            <p className="eyebrow">Sports Team Management Platform</p>
            <h1>All Your Volleyball Club Operations In One Place</h1>
            <p className="hero-description">
              Bring directors, coaches, players, and parents onto one shared
              platform with role-aware access and a homepage inspired by your
              reference design.
            </p>
          </div>

          <div className="hero-pills reveal-on-scroll" data-reveal="right" aria-hidden="true">
            <div className="hero-pill" style={{ "--reveal-delay": "80ms" }}>
              <span>Club creation</span>
              <strong>Faster setup</strong>
            </div>
            <div className="hero-pill" style={{ "--reveal-delay": "160ms" }}>
              <span>Team workflows</span>
              <strong>Cleaner rosters</strong>
            </div>
            <div className="hero-pill" style={{ "--reveal-delay": "240ms" }}>
              <span>Parent controls</span>
              <strong>Safer access</strong>
            </div>
          </div>
        </div>
      </section>

      <section id="about" className="content-section story-section">
        <div className="section-heading reveal-on-scroll" data-reveal="left">
          <h2>WHO WE ARE</h2>
          <div className="heading-line" />
        </div>

        <div className="story-grid">
          <div className="story-copy reveal-on-scroll" data-reveal="left">
            <p className="story-intro">
              NetUp is a volleyball operations platform built to help clubs feel
              more connected, more organized, and easier to run.
            </p>
            <p>
              We focus on the everyday work that keeps a club healthy: creating
              teams, managing roles, supporting families, and giving everyone a
              clearer place inside the same system.
            </p>

            <div className="story-stats">
              {platformStats.map((stat, index) => (
                <div
                  key={stat.label}
                  className="story-stat reveal-on-scroll"
                  data-reveal="up"
                  style={{ "--reveal-delay": `${index * 100}ms` }}
                >
                  <strong>{stat.value}</strong>
                  <span>{stat.label}</span>
                </div>
              ))}
            </div>
          </div>

          <div id="features" className="story-cards">
            {featureFeed.map((item, index) => (
              <article
                key={item.title}
                className="feature-post reveal-on-scroll"
                data-reveal={index % 2 === 0 ? "up" : "right"}
                style={{ "--reveal-delay": `${index * 110}ms` }}
              >
                <div className="feature-post__meta">
                  <span>{item.category}</span>
                  <span>{`0${index + 1}`}</span>
                </div>
                <h3>{item.title}</h3>
                <p>{item.description}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="showcase-band">
        {showcaseStrips.map((strip, index) => (
          <figure
            key={strip.src}
            className="showcase-frame reveal-on-scroll"
            data-reveal={index === 1 ? "up" : index % 2 === 0 ? "left" : "right"}
            style={{ "--reveal-delay": `${index * 110}ms` }}
          >
            <img className={strip.className} src={strip.src} alt={strip.alt} />
          </figure>
        ))}
      </section>

      <section className="content-section value-section">
        <div className="section-heading reveal-on-scroll" data-reveal="left">
          <h2>WHY NETUP</h2>
          <div className="heading-line" />
        </div>

        <div className="value-grid">
          {valueHighlights.map((item, index) => (
            <article
              key={item.title}
              className="value-card reveal-on-scroll"
              data-reveal={index % 2 === 0 ? "up" : "right"}
              style={{ "--reveal-delay": `${index * 100}ms` }}
            >
              <h3>{item.title}</h3>
              <p>{item.description}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="content-section trust-section">
        <div className="trust-strip reveal-on-scroll" data-reveal="left">
          <span className="trust-strip__title">Trusted By</span>
          <div className="brand-logos" aria-label="Volleyball brands">
            {trustBrands.map((brand, index) => (
              <span
                key={brand.name}
                className="brand-logo reveal-on-scroll"
                data-reveal="up"
                style={{ "--reveal-delay": `${index * 70}ms` }}
              >
                <span className="brand-logo__mark" aria-hidden="true">
                  {brand.mark}
                </span>
                <span className="brand-logo__name">{brand.name}</span>
              </span>
            ))}
          </div>
        </div>
      </section>

      <section id="journey" className="content-section journey-section">
        <div className="section-heading reveal-on-scroll" data-reveal="left">
          <h2>HOW IT WORKS</h2>
          <div className="heading-line" />
        </div>

        <div className="journey-grid">
          {journeySteps.map((step, index) => (
            <article
              key={step.title}
              className="journey-card reveal-on-scroll"
              data-reveal={index % 2 === 0 ? "up" : "right"}
              style={{ "--reveal-delay": `${index * 120}ms` }}
            >
              <span className="journey-card__number">{step.number}</span>
              <h3>{step.title}</h3>
              <p>{step.description}</p>
            </article>
          ))}
        </div>
      </section>

      <section id="roles" className="content-section role-section">
        <div className="section-heading reveal-on-scroll" data-reveal="left">
          <h2>FOR EVERY ROLE</h2>
          <div className="heading-line" />
        </div>

        <div className="role-grid">
          {roleSpotlights.map((item, index) => (
            <article
              key={item.role}
              className="role-card reveal-on-scroll"
              data-reveal={index % 2 === 0 ? "left" : "right"}
              style={{ "--reveal-delay": `${index * 90}ms` }}
            >
              <span className="role-card__label">{item.role}</span>
              <h3>{item.title}</h3>
              <p>{item.description}</p>
            </article>
          ))}
        </div>

        <div
          id="cta"
          className="workspace-closing-banner reveal-on-scroll"
          data-reveal="up"
          style={{ "--closing-banner-image": `url(${homepageImages.hero})` }}
        >
          <p>Built for the full volleyball community</p>
          <h3>One place for clubs, teams, players, and parents to move together.</h3>
          <div className="closing-banner-actions">
            <button
              className="closing-button"
              type="button"
              onClick={() => scrollToSection("faq")}
            >
              Request a demo
            </button>
            <button
              className="closing-button closing-button--ghost"
              type="button"
              onClick={() => scrollToSection("features")}
            >
              Explore features
            </button>
          </div>
        </div>
      </section>

      <section id="faq" className="content-section faq-section">
        <div className="section-heading reveal-on-scroll" data-reveal="left">
          <h2>FAQ</h2>
          <div className="heading-line" />
        </div>

        <div className="faq-grid">
          {faqs.map((item, index) => (
            <article
              key={item.question}
              className="faq-card reveal-on-scroll"
              data-reveal={index % 2 === 0 ? "left" : "right"}
              style={{ "--reveal-delay": `${index * 100}ms` }}
            >
              <h3>{item.question}</h3>
              <p>{item.answer}</p>
            </article>
          ))}
        </div>
      </section>

      <footer className="page-footer">
        <div className="page-footer__content reveal-on-scroll" data-reveal="up">
          <div>
            <span className="page-footer__brand">NetUp</span>
            <p className="page-footer__tagline">
              Club operations, team coordination, and family access in one shared
              platform.
            </p>
          </div>

          <nav className="page-footer__nav" aria-label="Footer">
            {footerLinks.map((item) => (
              <button
                key={item.label}
                type="button"
                className="footer-link"
                onClick={() => scrollToSection(item.sectionId)}
              >
                {item.label}
              </button>
            ))}
          </nav>
        </div>

        <div
          className="page-footer__bottom reveal-on-scroll"
          data-reveal="up"
          style={{ "--reveal-delay": "120ms" }}
        >
          <span>Copyright 2026 NetUp. All rights reserved.</span>
          <span>Built for modern volleyball clubs</span>
        </div>
      </footer>
    </div>
  );
}

export default App;
