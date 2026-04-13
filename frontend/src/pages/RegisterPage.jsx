import { useState } from "react";
import { registerUser } from "../api";

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

  const onSubmit = async (event) => {
    event.preventDefault();
    setError("");
    setSuccess("");

    if (!firstName.trim() || !lastName.trim()) {
      setError("First name and last name are required.");
      return;
    }
    if (!email.trim()) {
      setError("Email is required.");
      return;
    }
    if (!dateOfBirth) {
      setError("Date of birth is required.");
      return;
    }
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
      const payload = await registerUser({
        firstName: firstName.trim(),
        lastName: lastName.trim(),
        email: email.trim().toLowerCase(),
        password,
        dateOfBirth,
      });
      setSuccess(
        payload.message ||
          "Registration received. A director will review your account; you will get an email when you can log in.",
      );
      setTimeout(() => navigate("/login"), 2800);
    } catch (requestError) {
      setError(requestError.message || "Could not create account.");
    } finally {
      setLoading(false);
    }
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
        <p>Create an account to join your club, connect with your team, and access the tools for your role.</p>

        <form className="auth-form auth-form--register" onSubmit={onSubmit}>
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

          {error ? <p className="auth-error">{error}</p> : null}
          {success ? <p className="auth-success">{success}</p> : null}

          <button className="auth-submit" type="submit" disabled={loading}>
            {loading ? "CREATING..." : "Create Account"}
          </button>
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
