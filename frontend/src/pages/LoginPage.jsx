import { useState } from "react";
import { loginWithPassword } from "../api";

const AUTH_TOKEN_KEY = "netup.auth.token";
const AUTH_USER_KEY = "netup.auth.user";

function notifyAuthStateChanged() {
  window.dispatchEvent(new Event("auth-state-changed"));
}

function navigate(path) {
  window.history.pushState({}, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

export default function LoginPage() {
  const invitationCode = new URLSearchParams(window.location.search).get("invitation") || "";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const onSubmit = async (event) => {
    event.preventDefault();
    setError("");

    if (!email.trim()) {
      setError("Email is required.");
      return;
    }
    if (!password) {
      setError("Password is required.");
      return;
    }

    setLoading(true);
    try {
      const payload = await loginWithPassword({
        email: email.trim().toLowerCase(),
        password,
      });
      localStorage.setItem(AUTH_TOKEN_KEY, payload.token || "");
      localStorage.setItem(AUTH_USER_KEY, JSON.stringify(payload.user || {}));
      notifyAuthStateChanged();
      navigate(invitationCode ? `/invitation/${encodeURIComponent(invitationCode)}` : "/");
    } catch (requestError) {
      setError(requestError.message || "Could not log in.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="auth-page auth-page--login">
      <section className="login-left-panel">
        <div className="login-content-block">
          <div className="login-brand-lockup">
            <div className="login-brand-wordmark">
              <h1>Net</h1>
              <h1>Up</h1>
            </div>
            <img src="/auth/logo-ball.png" alt="" />
            <h2 className="login-title">Login</h2>
          </div>

          <form className="auth-form auth-form--login" onSubmit={onSubmit}>
            <label htmlFor="login-email">Email</label>
            <input
              id="login-email"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="Enter your email"
              autoComplete="email"
            />

            <label htmlFor="login-password">Password</label>
            <div className="password-field">
              <input
                id="login-password"
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="Enter your password"
                autoComplete="current-password"
              />
              <button
                className="password-toggle"
                type="button"
                onClick={() => setShowPassword((previous) => !previous)}
                aria-label={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? "Hide" : "Show"}
              </button>
            </div>

            {error ? <p className="auth-error">{error}</p> : null}

            <button className="auth-submit" type="submit" disabled={loading}>
              {loading ? "LOGGING IN..." : "LOGIN"}
            </button>

            <button className="forgot-link" type="button" onClick={() => navigate("/forgot-password")}>
              Forgot Password?
            </button>
          </form>

          <p className="auth-switch">
            Don&apos;t have an account?{" "}
            <button
              type="button"
              onClick={() =>
                navigate(
                  invitationCode
                    ? `/register?invitation=${encodeURIComponent(invitationCode)}`
                    : "/register",
                )
              }
            >
              Create one
            </button>
          </p>
        </div>
      </section>

      <div className="login-right-visual" aria-hidden="true" />

      <img className="shape-blue" src="/auth/shape-blue.png" alt="" aria-hidden="true" />
      <img className="shape-red" src="/auth/shape-red.png" alt="" aria-hidden="true" />
      <img className="player-jump" src="/auth/player-jump.png" alt="" aria-hidden="true" />
      <img className="player-dive" src="/auth/player-dive.png" alt="" aria-hidden="true" />
    </main>
  );
}
