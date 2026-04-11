import { useState } from "react";
import { loginWithPassword, registerUser } from "../api";

const ROLE_OPTIONS = [
  { value: "player", label: "Player" },
  { value: "parent", label: "Parent" },
  { value: "coach", label: "Coach" },
  { value: "director", label: "Director" },
];

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
  const [role, setRole] = useState(ROLE_OPTIONS[0].value);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const selectedRole = ROLE_OPTIONS.find((option) => option.value === role);

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
      await registerUser({
        firstName: firstName.trim(),
        lastName: lastName.trim(),
        email: email.trim().toLowerCase(),
        password,
      });
      const authPayload = await loginWithPassword({
        email: email.trim().toLowerCase(),
        password,
      });
      localStorage.setItem(AUTH_TOKEN_KEY, authPayload.token || "");
      localStorage.setItem(AUTH_USER_KEY, JSON.stringify(authPayload.user || {}));
      notifyAuthStateChanged();
      setSuccess("Account created successfully.");
      setTimeout(() => navigate("/"), 500);
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
        </div>
        <h2>Sign in</h2>
        <p>Join NetUp and manage your volleyball experience</p>

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

          <div className="register-role-row">
            <label htmlFor="register-role">Select Role</label>
            <div className="role-dropdown">
              <button
                id="register-role"
                type="button"
                className="role-dropdown-trigger"
                onClick={() => setDropdownOpen((previous) => !previous)}
                aria-expanded={dropdownOpen}
              >
                <span>{selectedRole?.label || "Select role"}</span>
                <span className="role-dropdown-caret">⌄</span>
              </button>
              {dropdownOpen ? (
                <div className="role-dropdown-menu">
                  {ROLE_OPTIONS.map((option) => (
                    <button
                      key={option.value}
                      type="button"
                      className="role-dropdown-option"
                      onClick={() => {
                        setRole(option.value);
                        setDropdownOpen(false);
                      }}
                    >
                      <span className="role-radio" aria-hidden="true" />
                      {option.label}
                    </button>
                  ))}
                </div>
              ) : null}
            </div>
          </div>

          <label htmlFor="register-email">Email</label>
          <input
            id="register-email"
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            autoComplete="email"
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
