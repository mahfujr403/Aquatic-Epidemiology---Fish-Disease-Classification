from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from . import db


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="user")
    username = db.Column(db.String(100), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    predictions = db.relationship("Prediction", backref="user", lazy=True)
    feedbacks = db.relationship("Feedback", backref="user", lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Prediction(db.Model):
    __tablename__ = "predictions"
    id = db.Column(db.Integer, primary_key=True)
    predicted_class = db.Column(db.String(255), nullable=False)
    confidence = db.Column(db.Float, nullable=False)
    model_used = db.Column(db.String(255), nullable=False)
    model_id = db.Column(db.Integer, db.ForeignKey("models.id"), nullable=True)
    image_path = db.Column(db.String(500), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    feedbacks = db.relationship("Feedback", backref="prediction", lazy=True)
    dataset_samples = db.relationship("DatasetSample", backref="prediction", lazy=True)
    scores = db.relationship("PredictionScore", backref="prediction", lazy=True)


class Feedback(db.Model):
    __tablename__ = "feedback"
    id = db.Column(db.Integer, primary_key=True)
    corrected_label = db.Column(db.String(255), nullable=True)
    is_corrected = db.Column(db.Boolean, nullable=False, default=False)
    note = db.Column(db.Text, nullable=True)
    prediction_id = db.Column(db.Integer, db.ForeignKey("predictions.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    handled = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class DatasetSample(db.Model):
    __tablename__ = "dataset_samples"
    id = db.Column(db.Integer, primary_key=True)
    approved = db.Column(db.Boolean, nullable=False, default=False)
    image_path = db.Column(db.String(500), nullable=False)
    label = db.Column(db.String(255), nullable=False)
    prediction_id = db.Column(db.Integer, db.ForeignKey("predictions.id"), nullable=False)
    split = db.Column(db.String(20), nullable=False, default="train")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ModelRegistry(db.Model):
    __tablename__ = "models"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    metrics = db.Column(db.Text, nullable=True)
    version = db.Column(db.String(100), nullable=False)
    filename = db.Column(db.String(255), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    predictions = db.relationship("Prediction", backref="model_entry", lazy=True)


class ClassLabel(db.Model):
    __tablename__ = "classes"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, unique=True)


class PredictionScore(db.Model):
    __tablename__ = "prediction_scores"
    id = db.Column(db.Integer, primary_key=True)
    prediction_id = db.Column(db.Integer, db.ForeignKey("predictions.id"), nullable=False)
    class_id = db.Column(db.Integer, db.ForeignKey("classes.id"), nullable=False)
    score = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

