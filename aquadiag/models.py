from datetime import datetime, timezone
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from . import db


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id            = db.Column(db.Integer, primary_key=True)
    email         = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role          = db.Column(db.String(20),  nullable=False, default="user")
    username      = db.Column(db.String(100), nullable=False, unique=True)
    created_at    = db.Column(db.DateTime,    default=datetime.utcnow)

    predictions = db.relationship("Prediction", backref="user",   lazy=True)
    feedbacks   = db.relationship("Feedback",   backref="user",   lazy=True)
    request_logs = db.relationship("RequestLog", backref="user",  lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Prediction(db.Model):
    __tablename__   = "predictions"
    id              = db.Column(db.Integer,     primary_key=True)
    predicted_class = db.Column(db.String(255), nullable=False)
    confidence      = db.Column(db.Float,       nullable=False)
    model_used      = db.Column(db.String(255), nullable=False)
    model_id        = db.Column(db.Integer, db.ForeignKey("models.id"), nullable=True)
    image_path      = db.Column(db.String(500), nullable=False)
    user_id         = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at      = db.Column(db.DateTime,    default=datetime.utcnow)

    feedbacks       = db.relationship("Feedback",       backref="prediction", lazy=True)
    dataset_samples = db.relationship("DatasetSample",  backref="prediction", lazy=True)
    scores          = db.relationship("PredictionScore", backref="prediction", lazy=True)


class Feedback(db.Model):
    __tablename__    = "feedback"
    id               = db.Column(db.Integer,  primary_key=True)
    corrected_label  = db.Column(db.String(255), nullable=True)
    is_corrected     = db.Column(db.Boolean,  nullable=False, default=False)
    note             = db.Column(db.Text,     nullable=True)
    prediction_id    = db.Column(db.Integer,  db.ForeignKey("predictions.id"), nullable=False)
    user_id          = db.Column(db.Integer,  db.ForeignKey("users.id"),       nullable=False)
    handled          = db.Column(db.Boolean,  nullable=False, default=False)
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)


class DatasetSample(db.Model):
    __tablename__ = "dataset_samples"
    id            = db.Column(db.Integer,     primary_key=True)
    approved      = db.Column(db.Boolean,     nullable=False, default=False)
    image_path    = db.Column(db.String(500), nullable=False)
    label         = db.Column(db.String(255), nullable=False)
    prediction_id = db.Column(db.Integer, db.ForeignKey("predictions.id"), nullable=False)
    split         = db.Column(db.String(20),  nullable=False, default="train")
    created_at    = db.Column(db.DateTime,    default=datetime.utcnow)


class ModelRegistry(db.Model):
    __tablename__ = "models"
    id          = db.Column(db.Integer,     primary_key=True)
    name        = db.Column(db.String(255), nullable=False)
    metrics     = db.Column(db.Text,        nullable=True)
    version     = db.Column(db.String(100), nullable=False)
    filename    = db.Column(db.String(255), nullable=False, unique=True)
    created_at  = db.Column(db.DateTime,    default=datetime.utcnow)
    predictions = db.relationship("Prediction", backref="model_entry", lazy=True)


class ClassLabel(db.Model):
    __tablename__ = "classes"
    id   = db.Column(db.Integer,     primary_key=True)
    name = db.Column(db.String(255), nullable=False, unique=True)


class PredictionScore(db.Model):
    __tablename__ = "prediction_scores"
    id            = db.Column(db.Integer, primary_key=True)
    prediction_id = db.Column(db.Integer, db.ForeignKey("predictions.id"), nullable=False)
    class_id      = db.Column(db.Integer, db.ForeignKey("classes.id"),     nullable=False)
    score         = db.Column(db.Float,   nullable=False)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)


# ─────────────────────────────────────────────────────────────
#  REQUEST LOG  — one row per HTTP request (written async)
# ─────────────────────────────────────────────────────────────
class RequestLog(db.Model):
    """
    Stores visitor activity for analytics / security auditing.

    Populated by the background worker in activity_logger.py.
    IP addresses are masked by default (last octet replaced with 'x')
    unless FULL_IP_LOGGING=1 is set in the environment.
    """
    __tablename__ = "request_logs"

    id               = db.Column(db.Integer,     primary_key=True)

    # Who
    ip_address       = db.Column(db.String(64),  nullable=False, index=True)
    user_agent       = db.Column(db.String(512),  nullable=True)
    user_id          = db.Column(
                           db.Integer,
                           db.ForeignKey("users.id"),
                           nullable=True,
                           index=True,
                       )

    # What
    method           = db.Column(db.String(10),  nullable=False)
    path             = db.Column(db.String(512), nullable=False, index=True)
    query_string     = db.Column(db.Text,        nullable=True)
    status_code      = db.Column(db.Integer,     nullable=False, index=True)

    # Performance
    response_time_ms = db.Column(db.Float,       nullable=True)

    # Context
    referrer         = db.Column(db.String(512), nullable=True)
    timestamp        = db.Column(
                           db.DateTime(timezone=True),
                           default=lambda: datetime.now(timezone.utc),
                           nullable=False,
                           index=True,
                       )

    def to_dict(self) -> dict:
        return {
            "id":               self.id,
            "ip_address":       self.ip_address,
            "user_agent":       self.user_agent,
            "user_id":          self.user_id,
            "method":           self.method,
            "path":             self.path,
            "query_string":     self.query_string,
            "status_code":      self.status_code,
            "response_time_ms": self.response_time_ms,
            "referrer":         self.referrer,
            "timestamp":        self.timestamp.isoformat() if self.timestamp else None,
        }