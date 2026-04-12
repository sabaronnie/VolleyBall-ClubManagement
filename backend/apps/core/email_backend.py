"""
SMTP backend that uses certifi's CA bundle for TLS when available.

Fixes SSLCertVerificationError on some macOS + Python installs where the
interpreter does not ship a usable default CA store for smtplib STARTTLS.
If certifi is not installed, falls back to the interpreter default CA store.
"""

import ssl

from django.core.mail.backends.smtp import EmailBackend as DjangoSmtpEmailBackend
from django.utils.functional import cached_property

try:
    import certifi
except ImportError:  # pragma: no cover - optional dependency at runtime
    certifi = None


class CertifiSmtpEmailBackend(DjangoSmtpEmailBackend):
    @cached_property
    def ssl_context(self):
        if self.ssl_certfile or self.ssl_keyfile:
            ssl_context = ssl.SSLContext(protocol=ssl.PROTOCOL_TLS_CLIENT)
            ssl_context.load_cert_chain(self.ssl_certfile, self.ssl_keyfile)
            return ssl_context
        if certifi is not None:
            return ssl.create_default_context(cafile=certifi.where())
        return ssl.create_default_context()
