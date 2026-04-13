import { useState } from "react";
import { submitContactForm } from "../api";

const ROLE_OPTIONS = [
  { value: "player", label: "Player" },
  { value: "parent", label: "Parent" },
  { value: "coach", label: "Coach" },
  { value: "director", label: "Director" },
  { value: "other", label: "Other" },
];

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function ContactUsPage() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("");
  const [message, setMessage] = useState("");
  const [phone, setPhone] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const onSubmit = async (event) => {
    event.preventDefault();
    setError("");
    setSuccess("");

    if (!name.trim()) {
      setError("Name is required.");
      return;
    }
    if (!email.trim()) {
      setError("Email is required.");
      return;
    }
    if (!EMAIL_RE.test(email.trim())) {
      setError("Enter a valid email address.");
      return;
    }
    if (!role) {
      setError("Please select your role.");
      return;
    }
    if (!message.trim()) {
      setError("Message is required.");
      return;
    }

    setLoading(true);
    try {
      const payload = await submitContactForm({
        name: name.trim(),
        email: email.trim().toLowerCase(),
        role,
        message: message.trim(),
        phone: phone.trim(),
      });
      setSuccess(payload.message || "Your message was sent successfully.");
      setName("");
      setEmail("");
      setRole("");
      setMessage("");
      setPhone("");
    } catch (requestError) {
      setError(requestError.message || "Could not send your message. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="contact-page">
      <div className="contact-page__inner">
        <header className="contact-page__header">
          <h1 className="contact-page__title">Contact Us</h1>
          <p className="contact-page__lede">
            Get in touch with us for inquiries, demos, or support.
          </p>
        </header>

        <form className="contact-form auth-form" onSubmit={onSubmit} noValidate>
          <label htmlFor="contact-name">Name</label>
          <input
            id="contact-name"
            name="name"
            type="text"
            autoComplete="name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
          />

          <label htmlFor="contact-email">Email</label>
          <input
            id="contact-email"
            name="email"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />

          <label htmlFor="contact-role">Role</label>
          <select
            id="contact-role"
            name="role"
            className="contact-form__select"
            value={role}
            onChange={(e) => setRole(e.target.value)}
            required
          >
            <option value="">Select one</option>
            {ROLE_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>

          <label htmlFor="contact-phone">Phone number (optional)</label>
          <input
            id="contact-phone"
            name="phone"
            type="tel"
            autoComplete="tel"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
          />

          <label htmlFor="contact-message">Message</label>
          <textarea
            id="contact-message"
            name="message"
            className="contact-form__textarea"
            rows={5}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            required
          />

          {error ? <p className="auth-error contact-form__feedback contact-form__feedback--error">{error}</p> : null}
          {success ? (
            <p className="contact-form__feedback contact-form__feedback--success" role="status">
              {success}
            </p>
          ) : null}

          <button className="auth-submit contact-form__submit" type="submit" disabled={loading}>
            {loading ? "Sending…" : "Send Message"}
          </button>
        </form>
      </div>
    </main>
  );
}
