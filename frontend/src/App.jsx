import { useEffect } from "react";

const navItems = ["Home", "Features", "Clubs", "Parents", "About"];

const homepageImages = {
  hero: "/homepage/hero-volleyball.png",
  stripTop: "/homepage/strip-top.png",
  stripMiddle: "/homepage/strip-middle.png",
  stripBottom: "/homepage/strip-bottom.png",
};

const featureFeed = [
  {
    category: "Club Operations",
    title: "Create clubs, build teams, and keep every role organized.",
    description:
      "Directors and coaches can manage clubs, spin up teams, and update structures without losing track of who belongs where.",
  },
  {
    category: "Roster Control",
    title: "Add players and coaches with role-aware team management.",
    description:
      "Membership updates, captain assignment, and player-specific details all live in one place so staff can move quickly.",
  },
  {
    category: "Parent Access",
    title: "Support parent-linked accounts and child access settings.",
    description:
      "Parents can stay connected to younger athletes while age-aware policies protect the right level of self-service access.",
  },
];

const highlightCards = [
  {
    eyebrow: "01",
    title: "Registration & Login",
    text: "Simple account entry points for players, parents, coaches, and directors.",
    image: homepageImages.stripTop,
    alt: "Close-up volleyball scene with a red and yellow ball",
  },
  {
    eyebrow: "02",
    title: "Team Memberships",
    text: "Bring rosters together, manage staff, and keep team roles clear.",
    image: homepageImages.stripMiddle,
    alt: "Close-up volleyball scene with a blue and yellow ball",
  },
  {
    eyebrow: "03",
    title: "Protected Player Access",
    text: "Respect parent-managed rules without blocking the full club workflow.",
    image: homepageImages.stripBottom,
    alt: "Close-up volleyball scene with a white volleyball",
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

const workspaceTiles = ["Clubs", "Teams", "Players", "Parents"];

const workspaceList = [
  "Role-based permissions",
  "Captain assignment",
  "Coach-managed rosters",
];

const workspaceFeatureCards = [
  {
    label: "01",
    title: "Smooth onboarding for every role",
    text: "Directors, coaches, players, and parents each get a clear place to start without extra admin overhead.",
  },
  {
    label: "02",
    title: "Shared visibility across the club",
    text: "Team activity, roster changes, and family connections stay organized in one connected system.",
  },
  {
    label: "03",
    title: "Guardrails that still feel fast",
    text: "Parent-managed access rules protect younger athletes while keeping the full workflow easy to use.",
  },
];

const workspaceFeatureTags = [
  "Club setup",
  "Roster flow",
  "Parent links",
  "Player protection",
];

const footerLinks = ["Features", "Clubs", "Teams", "Parents", "Contact"];

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

  return (
    <div className="homepage-shell">
      <section className="hero-section">
        <div
          className="hero-backdrop"
          style={{ "--hero-image": `url(${homepageImages.hero})` }}
        />
        <header className="site-nav">
          <div className="nav-left">
            {navItems.map((item) => (
              <button key={item} className="nav-button" type="button">
                {item}
              </button>
            ))}
          </div>

          <div className="nav-right">
            <span className="brand-mark">NetUp</span>
            <button className="action-button action-button--ghost" type="button">
              Register
            </button>
            <button className="action-button" type="button">
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

      <section className="content-section feature-feed-section">
        <div className="section-heading reveal-on-scroll" data-reveal="left">
          <h2>FEATURES</h2>
          <div className="heading-line" />
        </div>

        <div className="feature-feed">
          {featureFeed.map((item, index) => (
            <article
              key={item.title}
              className="feature-post reveal-on-scroll"
              data-reveal={index % 2 === 0 ? "left" : "right"}
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

      <section className="content-section highlights-section">
        <div
          className="section-heading section-heading--split reveal-on-scroll"
          data-reveal="left"
        >
          <h2>
            <span>PLATFORM</span>
            <span className="accent-word">HIGHLIGHTS</span>
          </h2>
          <div className="heading-line" />
        </div>

        <div className="highlight-grid">
          {highlightCards.map((card, index) => (
            <article
              key={card.title}
              className="highlight-card reveal-on-scroll"
              data-reveal={index % 2 === 0 ? "up" : "right"}
              style={{ "--reveal-delay": `${index * 120}ms` }}
            >
              <div className="highlight-visual">
                <img
                  className="highlight-visual__image"
                  src={card.image}
                  alt={card.alt}
                />
                <span className="highlight-badge">{card.eyebrow}</span>
              </div>
              <div className="highlight-body">
                <h3>{card.title}</h3>
                <p>{card.text}</p>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="workspace-section">
        <div
          className="section-heading section-heading--workspace reveal-on-scroll"
          data-reveal="left"
        >
          <h2>
            <span>YOUR CLUB</span>
            <span className="accent-word accent-word--blue">CONNECTED</span>
          </h2>
          <div className="heading-line heading-line--blue" />
        </div>

        <div className="workspace-panel reveal-on-scroll" data-reveal="up">
          <aside className="workspace-sidebar reveal-on-scroll" data-reveal="left">
            <div className="workspace-tile-grid">
              {workspaceTiles.map((tile) => (
                <button key={tile} className="workspace-tile" type="button">
                  {tile}
                </button>
              ))}
            </div>

            <div className="workspace-list">
              <div className="workspace-list__header">
                <span>Core tools</span>
                <span>+</span>
              </div>
              {workspaceList.map((item) => (
                <p key={item}>{item}</p>
              ))}
            </div>
          </aside>

          <div
            className="workspace-main reveal-on-scroll"
            data-reveal="right"
            style={{ "--reveal-delay": "120ms" }}
          >
            <div className="workspace-main__header">
              <h3>Everything you need to launch and manage your club</h3>
              <button type="button">Explore Platform</button>
            </div>

            <div className="workspace-feature-stage">
              <div className="workspace-feature-tags" aria-label="Platform features">
                {workspaceFeatureTags.map((tag, index) => (
                  <span
                    key={tag}
                    className="workspace-feature-tag reveal-on-scroll"
                    data-reveal="up"
                    style={{ "--reveal-delay": `${index * 70}ms` }}
                  >
                    {tag}
                  </span>
                ))}
              </div>

              <div className="workspace-feature-grid">
                {workspaceFeatureCards.map((item, index) => (
                  <article
                    key={item.title}
                    className="workspace-feature-card reveal-on-scroll"
                    data-reveal={index === 1 ? "up" : index % 2 === 0 ? "left" : "right"}
                    style={{ "--reveal-delay": `${index * 130}ms` }}
                  >
                    <span className="workspace-feature-card__label">{item.label}</span>
                    <h4>{item.title}</h4>
                    <p>{item.text}</p>
                  </article>
                ))}
              </div>
            </div>
          </div>
        </div>

        <div
          className="workspace-closing-banner reveal-on-scroll"
          data-reveal="up"
          style={{ "--closing-banner-image": `url(${homepageImages.hero})` }}
        >
          <p>Built for the full volleyball community</p>
          <h3>One place for clubs, teams, players, and parents to move together.</h3>
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
              <a key={item} href="/" onClick={(event) => event.preventDefault()}>
                {item}
              </a>
            ))}
          </nav>
        </div>

        <div
          className="page-footer__bottom reveal-on-scroll"
          data-reveal="up"
          style={{ "--reveal-delay": "120ms" }}
        >
          <span>2026 NetUp</span>
          <span>Built for modern volleyball clubs</span>
        </div>
      </footer>
    </div>
  );
}

export default App;
