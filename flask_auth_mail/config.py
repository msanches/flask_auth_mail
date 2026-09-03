import os

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

def init_config(app):
    """
    Initializes default configuration parameters on the Flask app configuration.
    Uses environment variables as defaults if not explicitly set.
    """
    if load_dotenv:
        load_dotenv(override=True)


    # Secret Key for itsdangerous signing
    app.config.setdefault("SECRET_KEY", os.environ.get("SECRET_KEY"))
    
    # Resend credentials
    app.config.setdefault("RESEND_API_KEY", os.environ.get("RESEND_API_KEY"))
    app.config.setdefault("EMAIL_FROM", os.environ.get("EMAIL_FROM", "onboarding@resend.dev"))
    
    # Expirations and limits
    app.config.setdefault("OTP_EXPIRATION", int(os.environ.get("OTP_EXPIRATION", 300)))
    app.config.setdefault("RESET_TOKEN_EXPIRATION", int(os.environ.get("RESET_TOKEN_EXPIRATION", 900)))
    app.config.setdefault("OTP_MAX_ATTEMPTS", int(os.environ.get("OTP_MAX_ATTEMPTS", 3)))
    app.config.setdefault("OTP_LOCKOUT_DURATION", int(os.environ.get("OTP_LOCKOUT_DURATION", 3600)))
    app.config.setdefault("OTP_RESEND_INTERVAL", int(os.environ.get("OTP_RESEND_INTERVAL", 60)))

