import phonenumbers
from phonenumbers.phonenumberutil import NumberParseException


def normalize_emergency_contact(value, country_code=None):
    """Return (E.164 phone, error). Blank values are allowed."""
    raw_value = (value or "").strip()
    if not raw_value:
        return "", None

    region = (country_code or "").strip().upper() or None
    if region and region not in phonenumbers.SUPPORTED_REGIONS:
        return None, "Select a supported phone code before saving this emergency contact."

    try:
        parsed = phonenumbers.parse(raw_value, None if raw_value.startswith("+") else region)
    except NumberParseException:
        return None, "Enter a valid emergency contact phone number."

    if region:
        expected_calling_code = phonenumbers.country_code_for_region(region)
        if parsed.country_code != expected_calling_code:
            return None, "Enter a phone number that matches the selected phone code."

    if not phonenumbers.is_valid_number(parsed):
        return None, "Enter a valid emergency contact phone number."

    normalized = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
    if len(normalized) > 30:
        return None, "Emergency contact phone number is too long."

    return normalized, None
