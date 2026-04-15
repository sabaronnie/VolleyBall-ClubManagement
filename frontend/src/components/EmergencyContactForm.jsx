import { useEffect, useState } from "react";

export default function EmergencyContactForm({
  value = "",
  canEdit = true,
  onSave,
  disabledReason = "",
}) {
  const [draft, setDraft] = useState(value || "");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    setDraft(value || "");
    setMessage("");
    setError("");
  }, [value]);

  const submit = async (event) => {
    event.preventDefault();
    if (!canEdit || saving || !onSave) {
      return;
    }

    setSaving(true);
    setMessage("");
    setError("");
    try {
      const result = await onSave(draft.trim());
      setMessage(result?.message || "Emergency contact updated.");
    } catch (err) {
      setError(err.message || "Could not update emergency contact.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <form className="vc-emergency-contact-form" onSubmit={submit}>
      <label className="vc-emergency-contact-form__label" htmlFor="dashboard-emergency-contact">
        Emergency Contact
      </label>
      <input
        id="dashboard-emergency-contact"
        className="vc-emergency-contact-form__input"
        type="tel"
        inputMode="tel"
        value={draft}
        placeholder="Phone number"
        disabled={!canEdit || saving}
        onChange={(event) => setDraft(event.target.value)}
      />
      <button
        type="submit"
        className="vc-emergency-contact-form__button"
        disabled={!canEdit || saving || draft.trim() === (value || "").trim()}
      >
        {saving ? "Saving..." : "Save"}
      </button>
      {!canEdit && disabledReason ? (
        <span className="vc-emergency-contact-form__hint">{disabledReason}</span>
      ) : null}
      {message ? <span className="vc-emergency-contact-form__success">{message}</span> : null}
      {error ? <span className="vc-emergency-contact-form__error">{error}</span> : null}
    </form>
  );
}
