import { useLayoutEffect, useState } from "react";
import { confirmPasswordReset, loginWithPassword, requestPasswordReset } from "../api";

const AUTH_TOKEN_KEY = "netup.auth.token";
const AUTH_USER_KEY = "netup.auth.user";
const RESET_EMAIL_KEY = "netup.passwordReset.email";
const RESET_OTP_KEY = "netup.passwordReset.otp";

function notifyAuthStateChanged() {
  window.dispatchEvent(new Event("auth-state-changed"));
}

function navigate(path) {
  window.history.pushState({}, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

function clearResetSession() {
  sessionStorage.removeItem(RESET_EMAIL_KEY);
  sessionStorage.removeItem(RESET_OTP_KEY);
}

function AuthLoginChrome({ title, children, footer }) {
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
            <h2 className="login-title">{title}</h2>
          </div>
          {children}
          {footer}
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

export function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [otp, setOtp] = useState("");
  const [codeSent, setCodeSent] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const onSendCode = async (event) => {
    event.preventDefault();
    setError("");

    if (!email.trim()) {
      setError("Email is required.");
      return;
    }

    setLoading(true);
    try {
      await requestPasswordReset({ email: email.trim().toLowerCase() });
      setCodeSent(true);
    } catch (requestError) {
      setError(requestError.message || "Could not send reset code.");
    } finally {
      setLoading(false);
    }
  };

  const onContinueToNewPassword = (event) => {
    event.preventDefault();
    setError("");

    const normalizedEmail = email.trim().toLowerCase();
    const trimmedOtp = otp.trim();

    if (!trimmedOtp) {
      setError("Enter the verification code from your email.");
      return;
    }

    if (!/^\d{6}$/.test(trimmedOtp)) {
      setError("Use the 6-digit code from your email.");
      return;
    }

    sessionStorage.setItem(RESET_EMAIL_KEY, normalizedEmail);
    sessionStorage.setItem(RESET_OTP_KEY, trimmedOtp);
    navigate("/forgot-password/reset");
  };

  return (
    <AuthLoginChrome
      title="RESET PASSWORD"
      footer={
        <p className="auth-switch">
          Remember your password?{" "}
          <button type="button" onClick={() => navigate("/login")}>
            Log in
          </button>
        </p>
      }
    >
      {!codeSent ? (
        <form className="auth-form auth-form--login" onSubmit={onSendCode}>
          <p className="auth-flow-hint">
            Enter the email for your account. We will send you a verification code.
          </p>
          <label htmlFor="reset-email">Email</label>
          <input
            id="reset-email"
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="Enter your email"
            autoComplete="email"
          />

          {error ? <p className="auth-error">{error}</p> : null}

          <button className="auth-submit" type="submit" disabled={loading}>
            {loading ? "SENDING..." : "SEND CODE"}
          </button>
        </form>
      ) : (
        <form className="auth-form auth-form--login" onSubmit={onContinueToNewPassword}>
          <p className="auth-flow-hint">
            We sent a code to <strong>{email.trim().toLowerCase()}</strong>. Enter it below, then choose a new
            password on the next screen.
          </p>

          <label htmlFor="reset-email-readonly">Email</label>
          <input
            id="reset-email-readonly"
            type="email"
            value={email}
            readOnly
            className="auth-input-readonly"
          />

          <label htmlFor="reset-otp">Verification code</label>
          <input
            id="reset-otp"
            type="text"
            inputMode="numeric"
            autoComplete="one-time-code"
            maxLength={6}
            value={otp}
            onChange={(event) => setOtp(event.target.value.replace(/\D/g, "").slice(0, 6))}
            placeholder="6-digit code"
          />

          {error ? <p className="auth-error">{error}</p> : null}

          <button className="auth-submit" type="submit">
            CONTINUE
          </button>

          <button
            className="forgot-link"
            type="button"
            onClick={() => {
              setCodeSent(false);
              setOtp("");
              setError("");
            }}
          >
            Use a different email
          </button>
        </form>
      )}
    </AuthLoginChrome>
  );
}

export function ResetPasswordPage() {
  const [resetSession] = useState(() => ({
    email: sessionStorage.getItem(RESET_EMAIL_KEY) || "",
    otp: sessionStorage.getItem(RESET_OTP_KEY) || "",
  }));
  const { email, otp } = resetSession;

  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useLayoutEffect(() => {
    if (!email || !otp) {
      navigate("/forgot-password");
    }
  }, [email, otp]);

  const onSubmit = async (event) => {
    event.preventDefault();
    setError("");

    if (!password) {
      setError("Password is required.");
      return;
    }
    if (password !== confirmPassword) {
      setError("Password and confirmation do not match.");
      return;
    }

    setLoading(true);
    try {
      await confirmPasswordReset({
        email,
        otp,
        new_password: password,
      });
      const authPayload = await loginWithPassword({ email, password });
      clearResetSession();
      localStorage.setItem(AUTH_TOKEN_KEY, authPayload.token || "");
      localStorage.setItem(AUTH_USER_KEY, JSON.stringify(authPayload.user || {}));
      notifyAuthStateChanged();
      navigate("/");
    } catch (requestError) {
      setError(requestError.message || "Could not reset password.");
    } finally {
      setLoading(false);
    }
  };

  if (!email || !otp) {
    return null;
  }

  return (
    <AuthLoginChrome
      title="NEW PASSWORD"
      footer={
        <p className="auth-switch">
          <button type="button" onClick={() => navigate("/login")}>
            Back to log in
          </button>
        </p>
      }
    >
      <form className="auth-form auth-form--login" onSubmit={onSubmit}>
        <p className="auth-flow-hint">Choose a new password for <strong>{email}</strong>.</p>

        <label htmlFor="new-password">New password</label>
        <div className="password-field">
          <input
            id="new-password"
            type={showPassword ? "text" : "password"}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            autoComplete="new-password"
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

        <label htmlFor="confirm-new-password">Confirm password</label>
        <div className="password-field">
          <input
            id="confirm-new-password"
            type={showConfirmPassword ? "text" : "password"}
            value={confirmPassword}
            onChange={(event) => setConfirmPassword(event.target.value)}
            autoComplete="new-password"
          />
          <button
            className="password-toggle"
            type="button"
            onClick={() => setShowConfirmPassword((previous) => !previous)}
            aria-label={showConfirmPassword ? "Hide password" : "Show password"}
          >
            {showConfirmPassword ? "Hide" : "Show"}
          </button>
        </div>

        {error ? <p className="auth-error">{error}</p> : null}

        <button className="auth-submit" type="submit" disabled={loading}>
          {loading ? "SAVING..." : "SAVE AND LOG IN"}
        </button>
      </form>
    </AuthLoginChrome>
  );
}
