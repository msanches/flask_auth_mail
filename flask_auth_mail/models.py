from datetime import datetime, timezone

def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)

def init_models(db):
    """
    Dynamically registers and returns the OTPCode model using the provided SQLAlchemy database object.
    This pattern ensures the model inherits from the app's specific db.Model class.
    """
    # Prevent duplicate class definitions if init_app is called multiple times (e.g. in test suites)
    for cls in db.Model.__subclasses__():
        if getattr(cls, '__tablename__', None) == 'flask_auth_mail_otp':
            return cls

    class OTPCode(db.Model):
        __tablename__ = 'flask_auth_mail_otp'
        
        id = db.Column(db.Integer, primary_key=True)
        user_id = db.Column(db.String(255), nullable=False, index=True)
        code_hash = db.Column(db.String(255), nullable=False)
        expires_at = db.Column(db.DateTime, nullable=False)
        attempts = db.Column(db.Integer, default=0, nullable=False)
        used = db.Column(db.Boolean, default=False, nullable=False)
        locked_until = db.Column(db.DateTime, nullable=True)
        created_at = db.Column(db.DateTime, default=_utcnow, nullable=False)

        def __repr__(self):
            return f"<OTPCode id={self.id} user_id={self.user_id} used={self.used} attempts={self.attempts}>"

    return OTPCode
