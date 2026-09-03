import logging
import requests
from flask import current_app

logger = logging.getLogger("flask_auth_mail")

class EmailSendError(Exception):
    """Custom exception raised when email sending fails."""
    pass

class BaseEmailProvider:
    """
    Base class for email providers. Subclass this to implement other provider backends
    (e.g., SendGrid, Mailgun, SMTP).
    """
    def send(self, to, subject, html):
        raise NotImplementedError("Subclasses must implement the send method.")

class ResendEmailProvider(BaseEmailProvider):
    """
    Email provider backend that delivers email via Resend's REST API.
    """
    def __init__(self, api_key=None, email_from=None):
        self.api_key = api_key
        self.email_from = email_from

    def send(self, to, subject, html):
        api_key = self.api_key or current_app.config.get("RESEND_API_KEY")
        email_from = self.email_from or current_app.config.get("EMAIL_FROM")

        if not api_key:
            raise EmailSendError("RESEND_API_KEY is not configured in the Flask application settings.")
        if not email_from:
            raise EmailSendError("EMAIL_FROM is not configured in the Flask application settings.")

        url = "https://api.resend.com/emails"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        # Structure the recipient parameter: can be single string or list
        recipients = [to] if isinstance(to, str) else to
        
        payload = {
            "from": email_from,
            "to": recipients,
            "subject": subject,
            "html": html
        }

        try:
            logger.info(f"Sending email to recipients: {recipients} with subject: '{subject}'")
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            
            if response.status_code not in (200, 201):
                error_msg = f"Resend API returned status {response.status_code}: {response.text}"
                logger.error(error_msg)
                raise EmailSendError(error_msg)
                
            return response.json()
        except requests.RequestException as e:
            error_msg = f"Network exception when connecting to Resend API: {e}"
            logger.error(error_msg)
            raise EmailSendError(error_msg) from e

def enviar_email(destinatario, assunto, html):
    """
    Sends an email using the active application's email provider.
    
    :param destinatario: Recipient email address (string or list of strings)
    :param assunto: Subject of the email
    :param html: HTML content of the email
    """
    auth_mail = current_app.extensions.get("auth_mail")
    if not auth_mail:
        raise RuntimeError("FlaskAuthMail extension is not initialized on the current app.")
    return auth_mail.email_provider.send(destinatario, assunto, html)
