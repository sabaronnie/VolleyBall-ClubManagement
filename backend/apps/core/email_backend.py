"""
SMTP backend that uses certifi's CA bundle for TLS.

Fixes SSLCertVerificationError on some macOS + Python installs where the
interpreter does not ship a usable default CA store for smtplib STARTTLS.
"""

import ssl

import certifi
from django.core.mail.backends.smtp import EmailBackend as DjangoSmtpEmailBackend
from django.utils.functional import cached_property


class CertifiSmtpEmailBackend(DjangoSmtpEmailBackend):
    @cached_property
    def ssl_context(self):
        if self.ssl_certfile or self.ssl_keyfile:
            ssl_context = ssl.SSLContext(protocol=ssl.PROTOCOL_TLS_CLIENT)
            ssl_context.load_cert_chain(self.ssl_certfile, self.ssl_keyfile)
            return ssl_context
        return ssl.create_default_context(cafile=certifi.where())
