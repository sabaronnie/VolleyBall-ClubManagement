
import { useEffect, useId, useMemo, useState } from "react";
import {
  getCountries,
  getCountryCallingCode,
  parsePhoneNumberFromString,
} from "libphonenumber-js";

const DEFAULT_COUNTRY_CODE = "LB";

function flagForCountry(countryCode) {
  return countryCode
    .toUpperCase()
    .replace(/./g, (char) => String.fromCodePoint(127397 + char.charCodeAt(0)));
}

function buildCountries() {
  const countries = getCountries().map((code) => ({
    code,
    dialCode: `+${getCountryCallingCode(code)}`,
    flag: flagForCountry(code),
  }));

  return countries.sort((a, b) => {
    if (a.code === DEFAULT_COUNTRY_CODE) return -1;
    if (b.code === DEFAULT_COUNTRY_CODE) return 1;
    const byDial = Number(a.dialCode.slice(1)) - Number(b.dialCode.slice(1));
    return byDial || a.code.localeCompare(b.code);
  });
}

function countryByCode(countries, countryCode) {
  return countries.find((country) => country.code === countryCode) || countries[0];
}

function parseEmergencyContact(value, countries) {
  const rawValue = String(value || "").trim();
  if (!rawValue) {
    return { countryCode: DEFAULT_COUNTRY_CODE, nationalNumber: "" };
  }

  const parsed = parsePhoneNumberFromString(rawValue);
  const countryCode = parsed?.country || DEFAULT_COUNTRY_CODE;
  const country = countryByCode(countries, countryCode);
  const dialDigits = country.dialCode.replace(/\D/g, "");
  const rawDigits = rawValue.replace(/\D/g, "");
  const nationalNumber =
    rawDigits.startsWith(dialDigits) ? rawDigits.slice(dialDigits.length) : rawDigits;

  return { countryCode: country.code, nationalNumber };
}

function normalizePhone(country, value) {
  const rawValue = String(value || "").trim();
  if (!rawValue) return { normalized: "", error: "" };

  const valueWithDialCode = rawValue.startsWith("+") ? rawValue : `${country.dialCode}${rawValue}`;
  const parsed = parsePhoneNumberFromString(valueWithDialCode);

  if (!parsed || parsed.countryCallingCode !== country.dialCode.slice(1) || !parsed.isValid()) {
    return { normalized: "", error: "Enter a valid emergency contact phone number." };
  }

  return { normalized: parsed.number, error: "" };
}

export default function EmergencyContactForm({
  value = "",
  canEdit = true,
  onSave,
  disabledReason = "",
}) {
  const id = useId();
  const countries = useMemo(() => buildCountries(), []);
  const initialValue = parseEmergencyContact(value, countries);
  const [countryCode, setCountryCode] = useState(initialValue.countryCode);
  const [draft, setDraft] = useState(initialValue.nationalNumber);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    const next = parseEmergencyContact(value, countries);
    setCountryCode(next.countryCode);
    setDraft(next.nationalNumber);
    setPickerOpen(false);
    setMessage("");
    setError("");
  }, [countries, value]);

  const selectedCountry = countryByCode(countries, countryCode);
  const currentPhone = normalizePhone(selectedCountry, draft);
  const savedPhone = (value || "").trim();
  const isUnchanged = !currentPhone.error && currentPhone.normalized === savedPhone;

  const submit = async (event) => {
    event.preventDefault();
    if (!canEdit || saving || !onSave) {
      return;
    }

    const nextPhone = normalizePhone(selectedCountry, draft);
    if (nextPhone.error) {
      setMessage("");
      setError(nextPhone.error);
      return;
    }

    setSaving(true);
    setMessage("");
    setError("");
    try {
      const result = await onSave(nextPhone.normalized, selectedCountry.code);
      setMessage(result?.message || "Emergency contact updated.");
    } catch (err) {
      setError(err.message || "Could not update emergency contact.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <form className="vc-emergency-contact-form" onSubmit={submit}>
      <label className="vc-emergency-contact-form__label" htmlFor={`${id}-number`}>
        Emergency Contact
      </label>
      <div
        className="vc-emergency-contact-form__picker"
        onBlur={(event) => {
          if (!event.currentTarget.contains(event.relatedTarget)) {
            setPickerOpen(false);
          }
        }}
      >
        <button
          type="button"
          className="vc-emergency-contact-form__picker-button"
          aria-label="Emergency contact country code"
          aria-expanded={pickerOpen}
          disabled={!canEdit || saving}
          onClick={() => setPickerOpen((open) => !open)}
        >
          <span aria-hidden="true">{selectedCountry.flag}</span>
          <span>{selectedCountry.dialCode}</span>
          <span aria-hidden="true" className="vc-emergency-contact-form__chevron">
            ▾
          </span>
        </button>
        {pickerOpen ? (
          <div className="vc-emergency-contact-form__picker-menu" role="listbox">
            {countries.map((country) => (
              <button
                key={country.code}
                type="button"
                className="vc-emergency-contact-form__picker-option"
                role="option"
                aria-selected={country.code === selectedCountry.code}
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => {
                  setCountryCode(country.code);
                  setPickerOpen(false);
                  setMessage("");
                  setError("");
                }}
              >
                <span aria-hidden="true">{country.flag}</span>
                <span>{country.dialCode}</span>
              </button>
            ))}
          </div>
        ) : null}
      </div>
      <input
        id={`${id}-number`}
        className="vc-emergency-contact-form__input"
        type="tel"
        inputMode="tel"
        value={draft}
        placeholder="Phone number"
        disabled={!canEdit || saving}
        onChange={(event) => {
          setDraft(event.target.value);
          setMessage("");
          setError("");
        }}
      />
      <button
        type="submit"
        className="vc-emergency-contact-form__button"
        disabled={!canEdit || saving || isUnchanged}
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
