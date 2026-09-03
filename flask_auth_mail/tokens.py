from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from flask import current_app
import logging

logger = logging.getLogger("flask_auth_mail")

def _get_serializer(salt=None):
    secret_key = current_app.config.get("SECRET_KEY")
    if not secret_key:
        raise ValueError("SECRET_KEY must be set in the application configuration.")
    if salt is None:
        salt = "password-reset-salt"
    return URLSafeTimedSerializer(secret_key, salt=salt)

def gerar_token(data, salt=None):
    """
    Generates a secure, cryptographically signed temporary token containing data.
    
    :param data: The payload to serialize (e.g. user ID, email, dict)
    :param salt: Optional salt to customize signature safety
    :return: A signed URL-safe string token
    """
    serializer = _get_serializer(salt)
    return serializer.dumps(data)

def validar_token(token, salt=None, max_age=None):
    """
    Validates a signed token and decodes its payload.
    
    :param token: The signed token string
    :param salt: Optional salt value matching the one used to generate the token
    :param max_age: Optional expiration in seconds (defaults to RESET_TOKEN_EXPIRATION config value)
    :return: The deserialized payload if valid and active, or None if expired or invalid.
    """
    if max_age is None:
        max_age = current_app.config.get("RESET_TOKEN_EXPIRATION", 900)
    serializer = _get_serializer(salt)
    try:
        return serializer.loads(token, max_age=max_age)
    except SignatureExpired:
        logger.warning("Token validation failed: token has expired.")
        return None
    except BadSignature:
        logger.warning("Token validation failed: token signature is invalid.")
        return None
