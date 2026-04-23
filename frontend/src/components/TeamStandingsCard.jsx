import { useEffect, useState } from "react";
import { downloadTeamStandingsPdf, fetchTeamStandings } from "../api";

function statToneClass(value) {
  if (value > 0) return "is-positive";
  if (value < 0) return "is-negative";
  return "is-neutral";
}

export default function TeamStandingsCard({
  activeTeamId = "",
  title = "Team Standings",
  eyebrow = "Rankings",
  emptySelectionMessage = "Select a team in the focus dropdown to load standings.",
  canExport = false,
}) {
  const [payload, setPayload] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [downloadBusy, setDownloadBusy] = useState(false);
  const [downloadFeedback, setDownloadFeedback] = useState("");

  useEffect(() => {
    if (!activeTeamId || activeTeamId === "__all__") {
      setPayload(null);
      setLoading(false);
      setError("");
      setDownloadFeedback("");
      return;
    }

    let cancelled = false;
    const loadStandings = () => {
      setLoading(true);
      setError("");
      setDownloadFeedback("");
      void fetchTeamStandings(activeTeamId)
        .then((data) => {
          if (!cancelled) {
            setPayload(data);
          }
        })
        .catch((err) => {
          if (!cancelled) {
            setPayload(null);
            setError(err.message || "Could not load standings.");
          }
        })
        .finally(() => {
          if (!cancelled) {
            setLoading(false);
          }
        });
    };

    loadStandings();
    const onStandingsChanged = () => loadStandings();
    window.addEventListener("netup-standings-changed", onStandingsChanged);

    return () => {
      cancelled = true;
      window.removeEventListener("netup-standings-changed", onStandingsChanged);
    };
  }, [activeTeamId]);

  const standings = payload?.standings || null;

  const handleDownloadPdf = async () => {
    if (!activeTeamId || !standings || downloadBusy) {
      return;
    }
    setDownloadBusy(true);
    setDownloadFeedback("");
    try {
      const blob = await downloadTeamStandingsPdf(activeTeamId);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      const safeTeamName =
        String(standings.team_name || "team")
          .toLowerCase()
          .replace(/[^a-z0-9]+/g, "_")
          .replace(/^_+|_+$/g, "") || "team";
      anchor.href = url;
      anchor.download = `team_standings_${safeTeamName}.pdf`;
      anchor.rel = "noopener";
      anchor.style.display = "none";
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 500);
      setDownloadFeedback("Standings PDF downloaded.");
    } catch (err) {
      setDownloadFeedback(err.message || "Could not download standings PDF.");
    } finally {
      setDownloadBusy(false);
    }
  };

  return (
    <section className="vc-panel vc-panel--dashboard vc-panel--director-white vc-team-standings-card">
      <div className="vc-dashboard-panel-head">
        <div>
          <p className="vc-dashboard-panel-head__eyebrow">{eyebrow}</p>
          <h2 className="vc-panel-title">{title}</h2>
        </div>
        <div className="vc-team-standings-card__head-actions">
          {standings?.team_name ? <span className="vc-dashboard-inline-note">{standings.team_name}</span> : null}
          {canExport && standings ? (
            <button
              type="button"
              className="vc-team-standings-card__export-btn"
              onClick={handleDownloadPdf}
              disabled={downloadBusy}
            >
              {downloadBusy ? "Preparing PDF…" : "Export PDF"}
            </button>
          ) : null}
        </div>
      </div>

      {!activeTeamId || activeTeamId === "__all__" ? (
        <p className="vc-modal__muted" style={{ margin: 0 }}>{emptySelectionMessage}</p>
      ) : loading ? (
        <p className="vc-modal__muted" style={{ margin: 0 }}>Loading standings…</p>
      ) : error ? (
        <p className="vc-modal__error" style={{ margin: 0 }}>{error}</p>
      ) : standings ? (
        <>
          <div className="vc-team-standings-card__record">
            <div>
              <div className="vc-team-standings-card__record-label">Record</div>
              <div className="vc-team-standings-card__record-value">{standings.record_label}</div>
              <div className="vc-team-standings-card__record-note">Wins - Losses</div>
            </div>
            <div className="vc-team-standings-card__matches">
              {standings.matches_played} match{standings.matches_played === 1 ? "" : "es"} counted
            </div>
          </div>

          <div className="vc-team-standings-card__grid" role="list" aria-label="Standing metrics">
            <div className="vc-team-standings-card__stat" role="listitem">
              <span className="vc-team-standings-card__label">Points For</span>
              <strong>{standings.points_for}</strong>
            </div>
            <div className="vc-team-standings-card__stat" role="listitem">
              <span className="vc-team-standings-card__label">Points Against</span>
              <strong>{standings.points_against}</strong>
            </div>
            <div className={`vc-team-standings-card__stat ${statToneClass(standings.point_differential)}`} role="listitem">
              <span className="vc-team-standings-card__label">Point Differential</span>
              <strong>{standings.point_differential}</strong>
            </div>
          </div>

          <p className="vc-team-standings-card__note">{standings.note || "Completed matches only."}</p>
          {downloadFeedback ? (
            <p
              className={
                downloadFeedback.toLowerCase().includes("downloaded")
                  ? "vc-team-standings-card__feedback is-success"
                  : "vc-team-standings-card__feedback is-error"
              }
            >
              {downloadFeedback}
            </p>
          ) : null}
        </>
      ) : (
        <p className="vc-modal__muted" style={{ margin: 0 }}>No standings available yet.</p>
      )}
    </section>
  );
}
