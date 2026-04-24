import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchInvitationByCode, respondToInvitation } from "../api";

function navigate(path) {
  window.history.pushState({}, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

const AUTH_TOKEN_KEY = "netup.auth.token";
const AUTH_USER_KEY = "netup.auth.user";

export default function TeamInvitationPage({ invitationCode, isAuthenticated }) {
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [payload, setPayload] = useState(null);

  const loadInvitation = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await fetchInvitationByCode(invitationCode);
      setPayload(data);
    } catch (e) {
      setError(e.message || "Could not load invitation.");
      setPayload(null);
    } finally {
      setLoading(false);
    }
  }, [invitationCode]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (cancelled) return;
      await loadInvitation();
    })();
    return () => {
      cancelled = true;
    };
  }, [loadInvitation]);

  const invitation = payload?.invitation || null;
  const canRespond = invitation?.status === "pending" && payload?.viewer_email_matches_invite;
  const canRespondToParentLink =
    invitation?.status === "pending_parent_response" && payload?.viewer_email_matches_invite;
  const showAuthPrompt = !isAuthenticated;
  const isParentLinkInvite = invitation?.kind === "parent_link";

  const clubAndTeam = useMemo(() => {
    if (!invitation?.team) return "";
    const teamName = invitation.team.name || "Team";
    const clubName = invitation.team.club_name || "Club";
    return `${teamName} (${clubName})`;
  }, [invitation]);

  const onRespond = async (action) => {
    setSubmitting(true);
    setError("");
    setSuccess("");
    try {
      const res = await respondToInvitation(invitationCode, action);
      setSuccess(res?.message || (action === "accept" ? "Invitation accepted." : "Invitation declined."));
      const refreshed = await fetchInvitationByCode(invitationCode);
      setPayload(refreshed);
      window.dispatchEvent(new Event("netup-teams-changed"));
    } catch (e) {
      setError(e.message || "Could not process invitation.");
    } finally {
      setSubmitting(false);
    }
  };

  const onSignOutAndSwitch = () => {
    localStorage.removeItem(AUTH_TOKEN_KEY);
    localStorage.removeItem(AUTH_USER_KEY);
    window.dispatchEvent(new Event("auth-state-changed"));
    navigate(`/login?invitation=${encodeURIComponent(invitationCode)}`);
  };

  return (
    <div className="vc-director-page">
      <div className="vc-director-card" style={{ maxWidth: "760px", margin: "2rem auto" }}>
        <h1 className="vc-panel-title">{isParentLinkInvite ? "Parent access invitation" : "Team invitation"}</h1>
        {loading ? <p className="vc-modal__muted">Loading invitation…</p> : null}
        {error ? <div className="vc-director-error">{error}</div> : null}
        {success ? <div className="vc-director-success">{success}</div> : null}

        {!loading && invitation ? (
          <>
            <p className="vc-modal__muted" style={{ marginTop: "0.4rem" }}>
              Invitation for <strong>{invitation.invited_email}</strong>
            </p>
            <p className="vc-modal__muted" style={{ marginTop: "0.2rem" }}>
              {isParentLinkInvite ? (
                <>
                  Player:{" "}
                  <strong>
                    {[invitation.player?.first_name, invitation.player?.last_name].filter(Boolean).join(" ").trim() ||
                      invitation.player?.email}
                  </strong>
                </>
              ) : (
                <>
                  Team: <strong>{clubAndTeam}</strong>
                </>
              )}
            </p>
            {!isParentLinkInvite ? (
              <p className="vc-modal__muted" style={{ marginTop: "0.2rem" }}>
                Role: <strong>{invitation.role}</strong>
              </p>
            ) : null}
            <p className="vc-modal__muted" style={{ marginTop: "0.2rem" }}>
              Status: <strong>{invitation.status}</strong>
            </p>
          </>
        ) : null}

        {showAuthPrompt ? (
          <div style={{ display: "flex", gap: "0.6rem", marginTop: "1rem", flexWrap: "wrap" }}>
            <button
              type="button"
              className="vc-director-modal__btn"
              onClick={() => navigate(`/login?invitation=${encodeURIComponent(invitationCode)}`)}
            >
              Log in to respond
            </button>
            <button
              type="button"
              className="vc-director-modal__btn vc-director-modal__btn--ghost"
              onClick={() => navigate(`/register?invitation=${encodeURIComponent(invitationCode)}`)}
            >
              Register first
            </button>
          </div>
        ) : null}

        {!showAuthPrompt && invitation ? (
          <>
            {!payload?.viewer_email_matches_invite ? (
              <>
                <p className="vc-director-error" style={{ marginTop: "1rem" }}>
                  This invitation belongs to another email address. Please sign in with {invitation.invited_email}.
                </p>
                <div style={{ display: "flex", gap: "0.6rem", marginTop: "0.7rem", flexWrap: "wrap" }}>
                  <button
                    type="button"
                    className="vc-director-modal__btn vc-director-modal__btn--ghost"
                    onClick={() => void loadInvitation()}
                  >
                    Retry
                  </button>
                  <button
                    type="button"
                    className="vc-director-modal__btn"
                    onClick={onSignOutAndSwitch}
                  >
                    Sign out and log in
                  </button>
                </div>
              </>
            ) : null}
            {canRespond || canRespondToParentLink ? (
              <div style={{ display: "flex", gap: "0.6rem", marginTop: "1rem", flexWrap: "wrap" }}>
                <button
                  type="button"
                  className="vc-director-modal__btn"
                  disabled={submitting}
                  onClick={() => void onRespond("accept")}
                >
                  {submitting ? "Please wait…" : `Accept ${isParentLinkInvite ? "invitation" : "invitation"}`}
                </button>
                <button
                  type="button"
                  className="vc-director-modal__btn vc-director-modal__btn--ghost"
                  disabled={submitting}
                  onClick={() => void onRespond("decline")}
                >
                  Decline invitation
                </button>
              </div>
            ) : null}
          </>
        ) : null}
      </div>
    </div>
  );
}
