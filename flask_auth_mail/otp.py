import secrets
import string
from datetime import datetime, timedelta, timezone
import logging
from flask import current_app
from werkzeug.security import generate_password_hash, check_password_hash

logger = logging.getLogger("flask_auth_mail")

def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)

def _get_otp_model_and_db():
    auth_mail = current_app.extensions.get("auth_mail")
    if not auth_mail or not auth_mail.otp_model or not auth_mail.db:
        raise RuntimeError("FlaskAuthMail extension is not initialized or db is not registered.")
    return auth_mail.otp_model, auth_mail.db

def gerar_otp(user_id):
    """
    Generates a cryptographically secure 6-digit OTP code, hashes it,
    saves the OTP record to the database, and returns the raw code.
    
    Checks the minimum interval configuration to prevent spam and
    verifies if the user is in a temporary lockout period due to failed attempts.
    
    :param user_id: ID of the user (e.g. integer or string)
    :return: 6-digit numeric OTP code string
    """
    OTPCode, db = _get_otp_model_and_db()
    
    now = _utcnow()
    resend_interval = current_app.config.get("OTP_RESEND_INTERVAL", 60)
    
    # Query for the last generated OTP for this user
    last_otp = OTPCode.query.filter_by(user_id=str(user_id)).order_by(OTPCode.created_at.desc()).first()
    if last_otp:
        # Check if user is locked out from too many failed attempts
        if last_otp.locked_until and now < last_otp.locked_until:
            remaining_seconds = int((last_otp.locked_until - now).total_seconds())
            remaining_minutes = max(1, (remaining_seconds + 59) // 60)
            logger.warning(f"OTP generation blocked: User {user_id} is locked out for {remaining_minutes} more minutes.")
            raise ValueError(f"Muitas tentativas incorretas. Conta bloqueada temporariamente. Tente novamente em {remaining_minutes} minutos.")

        # Check resend rate-limit interval
        elapsed = (now - last_otp.created_at).total_seconds()
        if elapsed < resend_interval:
            logger.warning(f"OTP generation rate limit hit for user {user_id}.")
            raise ValueError(f"A code was already sent. Please wait {int(resend_interval - elapsed)} seconds.")

    # Generate 6-digit numeric OTP
    code = "".join(secrets.choice(string.digits) for _ in range(6))
    code_hash = generate_password_hash(code)
    
    expiration_seconds = current_app.config.get("OTP_EXPIRATION", 300)
    expires_at = now + timedelta(seconds=expiration_seconds)
    
    otp_record = OTPCode(
        user_id=str(user_id),
        code_hash=code_hash,
        expires_at=expires_at,
        attempts=0,
        used=False,
        locked_until=None,
        created_at=now
    )
    
    db.session.add(otp_record)
    db.session.commit()
    
    logger.info(f"New OTP generated and stored for user_id {user_id}.")
    return code

def validar_otp(user_id, code):
    """
    Validates an OTP code for a user. Increments attempt counts on failure.
    Locks user out if maximum attempts reached. Invalidates (marks as used) upon success.
    
    :param user_id: ID of the user
    :param code: 6-digit numeric code input
    :return: True if the code matches and is valid, False otherwise
    """
    OTPCode, db = _get_otp_model_and_db()
    now = _utcnow()
    
    # Find the latest active (non-used) OTP for the user
    otp_record = OTPCode.query.filter_by(user_id=str(user_id), used=False).order_by(OTPCode.created_at.desc()).first()
    if not otp_record:
        logger.info(f"OTP verification failed: no unused OTP found for user {user_id}.")
        return False

    max_attempts = current_app.config.get("OTP_MAX_ATTEMPTS", 3)
    lockout_duration = current_app.config.get("OTP_LOCKOUT_DURATION", 3600)
    
    # Check if this OTP is currently locked out
    if otp_record.locked_until and now < otp_record.locked_until:
        logger.warning(f"OTP verification blocked: User {user_id} is locked out until {otp_record.locked_until}.")
        return False

    if otp_record.attempts >= max_attempts:
        logger.warning(f"OTP verification failed: max attempts ({max_attempts}) reached for user {user_id}.")
        return False
        
    if now > otp_record.expires_at:
        logger.info(f"OTP verification failed: OTP expired for user {user_id}.")
        return False
        
    # Verify code hash using Werkzeug security
    if check_password_hash(otp_record.code_hash, code):
        otp_record.used = True
        db.session.commit()
        logger.info(f"OTP verified successfully for user {user_id}.")
        return True
    else:
        otp_record.attempts += 1
        if otp_record.attempts >= max_attempts:
            otp_record.locked_until = now + timedelta(seconds=lockout_duration)
            logger.warning(f"OTP verification failed: max attempts ({max_attempts}) reached for user {user_id}. Locked for {lockout_duration}s.")
        else:
            logger.warning(f"OTP verification failed: invalid code. Attempts: {otp_record.attempts}/{max_attempts} for user {user_id}")
        db.session.commit()
        return False

