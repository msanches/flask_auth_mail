from flask import Blueprint, current_app, render_template
import os
import logging
from flask_login import login_user

from .config import init_config
from .models import init_models
from .email_service import ResendEmailProvider, enviar_email, EmailSendError, BaseEmailProvider
from .tokens import gerar_token, validar_token
from .otp import gerar_otp, validar_otp

# Define a Blueprint to expose the emails templates
templates_dir = os.path.join(os.path.dirname(__file__), 'templates')
auth_mail_bp = Blueprint('auth_mail', __name__, template_folder=templates_dir)

logger = logging.getLogger("flask_auth_mail")

class AuthMail:
    def __init__(self, app=None, db=None):
        self.db = db
        self.otp_model = None
        self.email_provider = None
        self._find_user_by_email = None
        
        if app is not None:
            self.init_app(app, db)

    def init_app(self, app, db=None):
        self.db = db or self.db or app.extensions.get("sqlalchemy")
        if not self.db:
            raise RuntimeError("FlaskAuthMail: SQLAlchemy db object must be provided to init_app or exist in app.extensions['sqlalchemy'].")

        # Initialize configurations on Flask app object
        init_config(app)

        # Register models bound to the db instance
        self.otp_model = init_models(self.db)

        # Setup email provider (Resend API)
        api_key = app.config.get("RESEND_API_KEY")
        email_from = app.config.get("EMAIL_FROM")
        self.email_provider = ResendEmailProvider(api_key, email_from)

        # Register the templates blueprint
        app.register_blueprint(auth_mail_bp)

        # Save extension instance on app
        if not hasattr(app, "extensions"):
            app.extensions = {}
        app.extensions["auth_mail"] = self

    def find_user_by_email_loader(self, callback):
        """
        Decorator to register a callback function that locates a user based on their email.
        
        Example:
            @auth_mail.find_user_by_email_loader
            def get_user_by_email(email):
                return User.query.filter_by(email=email).first()
        """
        self._find_user_by_email = callback
        return callback


def enviar_codigo_login(email):
    """
    Looks up the user by their email address, generates a 6-digit OTP code,
    renders the verification template, and sends the OTP code via email.
    
    If the user is not found, simulates successful request behaviour to prevent timing attacks.
    
    :param email: The user's email address
    :return: True if the code was generated and sent successfully (or simulated successfully).
    """
    auth_mail = current_app.extensions.get("auth_mail")
    if not auth_mail:
        raise RuntimeError("FlaskAuthMail: The AuthMail extension is not initialized on this Flask application.")

    if not auth_mail._find_user_by_email:
        raise RuntimeError("FlaskAuthMail: No user loader callback is registered. Register one using '@auth_mail.find_user_by_email_loader'.")

    user = auth_mail._find_user_by_email(email)
    if not user:
        # Prevent user enumeration / timing attacks. Just log and return True.
        logger.info(f"FlaskAuthMail: Request for login code on non-existent email '{email}' was simulated.")
        return True

    # Retrieve user ID string/int
    user_id = getattr(user, "id", None) or (user.get_id() if hasattr(user, "get_id") else str(user))

    # Generate OTP (Value error raised if within 60s resend interval)
    code = gerar_otp(user_id)

    # Render template with variables
    expires_in_minutes = current_app.config.get("OTP_EXPIRATION", 300) // 60
    html = render_template(
        'emails/login_code.html',
        app_name=current_app.name or "App",
        code=code,
        expires_in_minutes=expires_in_minutes
    )

    # Send the email using the active provider
    enviar_email(email, f"Código de login para {current_app.name or 'sua conta'}", html)
    return True


def validar_codigo_login(email, code, remember=False):
    """
    Finds the user by email, validates the submitted OTP code, and logs them in
    via Flask-Login's login_user helper upon success.
    
    :param email: The user's email address
    :param code: The 6-digit verification code
    :param remember: Whether to set a persistent remember-me cookie (default: False)
    :return: True if validation succeeded and user is logged in, False otherwise.
    """
    auth_mail = current_app.extensions.get("auth_mail")
    if not auth_mail:
        raise RuntimeError("FlaskAuthMail: The AuthMail extension is not initialized on this Flask application.")

    if not auth_mail._find_user_by_email:
        raise RuntimeError("FlaskAuthMail: No user loader callback is registered. Register one using '@auth_mail.find_user_by_email_loader'.")

    user = auth_mail._find_user_by_email(email)
    if not user:
        logger.warning(f"FlaskAuthMail: Login attempt with code failed because user '{email}' does not exist.")
        return False

    user_id = getattr(user, "id", None) or (user.get_id() if hasattr(user, "get_id") else str(user))

    if validar_otp(user_id, code):
        login_user(user, remember=remember)
        return True

    return False

__all__ = [
    'AuthMail',
    'enviar_email',
    'gerar_token',
    'validar_token',
    'gerar_otp',
    'enviar_codigo_login',
    'validar_codigo_login',
    'EmailSendError',
    'BaseEmailProvider'
]
