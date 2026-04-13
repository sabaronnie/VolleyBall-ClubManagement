import { useState } from "react";
import { registerUser, verifyRegistrationOtp } from "../api";

const AUTH_TOKEN_KEY = "netup.auth.token";
const AUTH_USER_KEY = "netup.auth.user";

function notifyAuthStateChanged() {
  window.dispatchEvent(new Event("auth-state-changed"));
}

function navigate(path) {
  window.history.pushState({}, "", path);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

export default function RegisterPage() {
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [dateOfBirth, setDateOfBirth] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [awaitingOtp, setAwaitingOtp] = useState(false);
  const [otp, setOtp] = useState("");

  const sendVerificationCode = async () => {
    setError("");
    setSuccess("");

    if (!firstName.trim() || !lastName.trim()) {
      setError("First name and last name are required.");
      return false;
    }
    if (!email.trim()) {
      setError("Email is required.");
      return false;
    }
    if (!dateOfBirth) {
      setError("Date of birth is required.");
      return false;
    }
    if (!password) {
      setError("Password is required.");
      return false;
    }
    if (password !== confirmPassword) {
      setError("Password and confirmation do not match.");
      return false;
    }

    setLoading(true);
    try {
      const payload = await registerUser({
        firstName: firstName.trim(),
        lastName: lastName.trim(),
        email: email.trim().toLowerCase(),
        password,
        dateOfBirth,
      });
      setAwaitingOtp(true);
      setOtp("");
      setSuccess(
        payload.message ||
          "We sent a verification code to your email. Enter it below to finish creating your account.",
      );
      return true;
    } catch (requestError) {
      setError(requestError.message || "Could not create account.");
      return false;
    } finally {
      setLoading(false);
    }
  };

  const verifyCode = async () => {
    setError("");
    setSuccess("");

    if (!otp.trim()) {
      setError("Verification code is required.");
      return;
    }

    setLoading(true);
    try {
      const payload = await verifyRegistrationOtp({
        email: email.trim().toLowerCase(),
        otp: otp.trim(),
      });
      localStorage.setItem(AUTH_TOKEN_KEY, payload.token || "");
      localStorage.setItem(AUTH_USER_KEY, JSON.stringify(payload.user || {}));
      notifyAuthStateChanged();
      setSuccess(payload.message || "Registration complete. You are now signed in.");
      window.setTimeout(() => navigate("/"), 250);
    } catch (requestError) {
      setError(requestError.message || "Could not verify the code.");
    } finally {
      setLoading(false);
    }
  };

  const onSubmit = async (event) => {
    event.preventDefault();
    if (awaitingOtp) {
      await verifyCode();
      return;
    }
    await sendVerificationCode();
  };

  return (
    <main className="auth-page auth-page--register">
      <section className="register-shell">
        <div className="register-brand">
          <div className="register-wordmark">
            <h1>Net</h1>
            <h1>Up</h1>
          </div>
          <img src="/auth/logo-ball.png" alt="" />
          <h2>Register</h2>
        </div>
        {awaitingOtp ? (
          <p className="auth-flow-hint auth-flow-hint--register">
            Enter the verification code sent to <strong>{email}</strong>.
          </p>
        ) : (
          <p>
            Create an account to join your club, then confirm the verification code sent to your email to finish
            signing up.
          </p>
        )}

        <form className="auth-form auth-form--register" onSubmit={onSubmit}>
          {awaitingOtp ? (
            <>
              <label htmlFor="register-otp">Verification Code</label>
              <input
                id="register-otp"
                inputMode="numeric"
                autoComplete="one-time-code"
                value={otp}
                onChange={(event) => setOtp(event.target.value)}
                placeholder="Enter the 6-digit code"
              />
            </>
          ) : (
            <>
              <label htmlFor="register-first-name">First Name</label>
              <input
                id="register-first-name"
                value={firstName}
                onChange={(event) => setFirstName(event.target.value)}
                autoComplete="given-name"
              />

              <label htmlFor="register-last-name">Last Name</label>
              <input
                id="register-last-name"
                value={lastName}
                onChange={(event) => setLastName(event.target.value)}
                autoComplete="family-name"
              />

              <label htmlFor="register-email">Email</label>
              <input
                id="register-email"
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                autoComplete="email"
              />

              <label htmlFor="register-dob">Date of birth</label>
              <input
                id="register-dob"
                type="date"
                value={dateOfBirth}
                onChange={(event) => setDateOfBirth(event.target.value)}
                autoComplete="bday"
                required
              />

              <label htmlFor="register-password">Password</label>
              <div className="password-field">
                <input
                  id="register-password"
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  autoComplete="new-password"
                />
                <button
                  className="password-toggle"
                  type="button"
                  onClick={() => setShowPassword((previous) => !previous)}
                >
                  {showPassword ? "Hide" : "Show"}
                </button>
              </div>

              <label htmlFor="register-confirm-password">Confirm Password</label>
              <div className="password-field">
                <input
                  id="register-confirm-password"
                  type={showConfirmPassword ? "text" : "password"}
                  value={confirmPassword}
                  onChange={(event) => setConfirmPassword(event.target.value)}
                  autoComplete="new-password"
                />
                <button
                  className="password-toggle"
                  type="button"
                  onClick={() => setShowConfirmPassword((previous) => !previous)}
                >
                  {showConfirmPassword ? "Hide" : "Show"}
                </button>
              </div>
            </>
          )}

          {error ? <p className="auth-error">{error}</p> : null}
          {success ? <p className="auth-success">{success}</p> : null}

          <button className="auth-submit" type="submit" disabled={loading}>
            {loading ? (awaitingOtp ? "VERIFYING..." : "REGISTERING...") : awaitingOtp ? "Verify & Sign In" : "Register"}
          </button>

          {awaitingOtp ? (
            <button
              type="button"
              className="auth-submit auth-submit--secondary"
              disabled={loading}
              onClick={() => void sendVerificationCode()}
            >
              {loading ? "PLEASE WAIT..." : "Resend Code"}
            </button>
          ) : null}
        </form>

        <p className="auth-switch auth-switch--light">
          Already have an account?{" "}
          <button type="button" onClick={() => navigate("/login")}>
            Log in
          </button>
        </p>
      </section>
    </main>
  );
}
