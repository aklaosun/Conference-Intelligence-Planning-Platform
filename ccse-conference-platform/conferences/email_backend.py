"""Transactional mail over HTTPS, including on Render's Free web service."""
import base64
from email.utils import parseaddr
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.mail.backends.base import BaseEmailBackend
from django.core.validators import validate_email
import requests


class EmailDeliveryError(RuntimeError):
    """Safe operational error; never includes a key, body, or recipient."""


def address(value):
    name, email = parseaddr(value)
    validate_email(email)
    return dict(email=email, **({'name': name} if name else {}))


class BrevoEmailBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        sent = 0
        for message in email_messages or []:
            if not message.recipients():
                continue
            try:
                self._send(message)
            except (EmailDeliveryError, ImproperlyConfigured):
                if not self.fail_silently:
                    raise
            else:
                sent += 1
        return sent

    def _send(self, message):
        key = getattr(settings, 'BREVO_API_KEY', '').strip()
        if not getattr(settings, 'WORKSPACE_EMAIL_ENABLED', False) or not key:
            raise ImproperlyConfigured('Email is disabled or BREVO_API_KEY is missing.')
        # Apply Django's normal header-injection checks before transmitting.
        message.message()
        payload = {'sender': address(message.from_email), 'subject': message.subject,
                   'textContent': message.body or 'CCSE Conference Workspace notification.'}
        for attr in ('to', 'cc', 'bcc'):
            if getattr(message, attr):
                payload[attr] = [address(value) for value in getattr(message, attr)]
        if message.reply_to:
            payload['replyTo'] = address(message.reply_to[0])
        for content, kind in getattr(message, 'alternatives', []):
            if kind == 'text/html':
                payload['htmlContent'] = content
        if 'IdempotencyKey' in message.extra_headers:
            payload['headers'] = {'IdempotencyKey': message.extra_headers['IdempotencyKey']}
        attachments = []
        for attachment in message.attachments:
            if not isinstance(attachment, tuple) or len(attachment) != 3:
                raise EmailDeliveryError('Unsupported email attachment. Use a named file attachment.')
            filename, content, _ = attachment
            raw = content.encode('utf-8') if isinstance(content, str) else content
            attachments.append({'name': filename, 'content': base64.b64encode(raw).decode('ascii')})
        if attachments:
            payload['attachment'] = attachments
        try:
            response = requests.post('https://api.brevo.com/v3/smtp/email',
                headers={'api-key': key, 'accept': 'application/json'}, json=payload,
                timeout=(10, 20), allow_redirects=False)
        except requests.RequestException:
            raise EmailDeliveryError('Brevo connection failed or timed out. Check its activity log before retrying.') from None
        if response.status_code != 201:
            hints = {400: 'Verify the sender address and message configuration.',
                     401: 'Check the Brevo API key in the server environment.',
                     403: 'Verify the sender and activate transactional email in Brevo.',
                     429: 'The email quota or rate limit was reached. Try later.'}
            raise EmailDeliveryError(f'Brevo did not accept the email (HTTP {response.status_code}). '
                + hints.get(response.status_code, 'Check Brevo service status and activity logs.'))
        try:
            if not response.json().get('messageId'):
                raise ValueError
        except (ValueError, TypeError, AttributeError):
            raise EmailDeliveryError('Brevo returned an unexpected response. Check its activity log before retrying.') from None
