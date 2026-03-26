import os
import uuid
from datetime import datetime
from functools import wraps

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    jsonify,
)
from flask_cors import CORS
from dotenv import load_dotenv

# load environment from .env (if present)
load_dotenv()


def _parse_env_example(path=None):
    """Return list of variable names declared in .env.example (ignores comments)."""
    if path is None:
        path = os.path.join(os.path.dirname(__file__), ".env.example")
    keys = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key = line.split("=", 1)[0].strip()
                    # skip lines that are not simple KEY=VALUE
                    if key:
                        keys.append(key)
    except FileNotFoundError:
        return []
    return keys


def _check_env_against_example():
    missing = []
    keys = _parse_env_example()
    for k in keys:
        if os.getenv(k) in (None, ""):
            missing.append(k)

    # Admin credentials are required for admin login flow
    admin_missing = [k for k in ("ADMIN_EMAIL", "ADMIN_PASSWORD") if k in missing]
    if admin_missing:
        raise RuntimeError(
            f"Missing required admin environment variables: {', '.join(admin_missing)}.\n"
            "Set them in your environment or in a .env file (see .env.example)."
        )

    if missing:
        print("Warning: the following env variables from .env.example are not set:", ", ".join(missing))


# validate env vars at startup (will raise if admin creds missing)
_check_env_against_example()
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    login_required,
    logout_user,
    current_user,
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from tensorflow.keras.preprocessing.image import load_img, img_to_array
from tensorflow.keras.models import load_model
import numpy as np

# App setup
app = Flask(__name__, template_folder="templates", static_folder="static")
CORS(app)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "change-me")

# Database configuration - use env DATABASE_URL for production
database_url = os.getenv("DATABASE_URL", "sqlite:///app.db")
# SQLAlchemy expects the 'postgresql' dialect; some providers give 'postgres://'
if isinstance(database_url, str) and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"

# Upload settings
UPLOAD_DIR = os.path.join("static", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

# Model & classes
MODEL_PATH = "models/ensemble-ResNet50-EfficientNetV2_model.h5"
if os.path.exists(MODEL_PATH):
    model = load_model(MODEL_PATH)
else:
    model = None

class_names = [
    "Bacterial Red disease",
    "Bacterial diseases - Aeromoniasis",
    "Bacterial gill disease",
    "Fungal diseases Saprolegniasis",
    "Healthy Fish",
    "Parasitic diseases",
    "Viral diseases White tail disease",
]


#############
# DB Models
#############

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
    image_path = db.Column(db.String(500), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    feedbacks = db.relationship("Feedback", backref="prediction", lazy=True)
    dataset_samples = db.relationship("DatasetSample", backref="prediction", lazy=True)


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


@login_manager.user_loader
def load_user(user_id):
    # Support in-memory env-admin users with IDs like "env:email"
    try:
        if isinstance(user_id, str) and user_id.startswith("env:"):
            email = user_id.split(":", 1)[1]
            class EnvAdmin(UserMixin):
                def __init__(self, email):
                    self.email = email
                    self.id = f"env:{email}"
                    self.username = email.split("@")[0]
                    self.role = "admin"

                def get_id(self):
                    return self.id

            return EnvAdmin(email)

        uid = int(user_id)
    except (ValueError, TypeError):
        return None

    try:
        return User.query.get(uid)
    except Exception:
        # If DB/table is unavailable, don't crash the app; return None
        return None


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != "admin":
            flash("Admin access required.", "error")
            return redirect(url_for("index"))
        return fn(*args, **kwargs)

    return wrapper


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


#################
# Routes
#################


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not email or not username or not password:
            flash("All fields are required.", "error")
            return redirect(url_for("register"))

        if User.query.filter((User.email == email) | (User.username == username)).first():
            flash("Email or username already exists.", "error")
            return redirect(url_for("register"))

        user = User(email=email, username=username, role="user")
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        flash("Registration successful. Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()

        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            flash("Invalid email or password.", "error")
            return redirect(url_for("login"))

        login_user(user)
        flash("Logged in successfully.", "success")
        return redirect(url_for("predict_get"))

    return render_template("login.html")


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "").strip()

        admin_email = os.getenv("ADMIN_EMAIL")
        admin_password = os.getenv("ADMIN_PASSWORD")

        if admin_email and admin_password and email == admin_email and password == admin_password:
            user = User.query.filter_by(email=email).first()
            if not user:
                username = os.getenv("ADMIN_USERNAME") or email.split("@")[0]
                user = User(email=email, username=username, role="admin")
                user.set_password(password)
                db.session.add(user)
                db.session.commit()

            login_user(user)
            flash("Admin logged in successfully.", "success")
            return redirect(url_for("admin_panel"))

        flash("Invalid admin credentials.", "error")
        return redirect(url_for("admin_login"))

    return render_template("admin_login.html")


@app.route("/admin/panel")
@login_required
@admin_required
def admin_panel_alias():
    return admin_panel()


@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out.", "success")
    return redirect(url_for("index"))


@app.route("/predict", methods=["GET"])
@login_required
def predict_get():
    return render_template("prediction.html", class_names=class_names)


@app.route("/predict", methods=["POST"])
@login_required
def predict_disease():
    try:
        image = request.files.get("image")
        if not image or image.filename == "":
            flash("Please upload an image.", "error")
            return redirect(url_for("predict_get"))

        if not allowed_file(image.filename):
            flash("Invalid file type.", "error")
            return redirect(url_for("predict_get"))

        ext = image.filename.rsplit(".", 1)[1].lower()
        unique_name = f"{uuid.uuid4()}.{ext}"
        image_path = os.path.join(UPLOAD_DIR, unique_name)
        image.save(image_path)

        if model is None:
            flash("Model not available on server.", "error")
            return redirect(url_for("predict_get"))

        img = load_img(image_path, target_size=(224, 224))
        img_array = img_to_array(img)
        img_array = np.expand_dims(img_array, axis=0)

        prediction = model.predict(img_array)[0]
        top_idx = int(np.argmax(prediction))
        top_class = class_names[top_idx]
        top_confidence = float(prediction[top_idx])

        pred_row = Prediction(
            predicted_class=top_class,
            confidence=top_confidence,
            model_used=os.path.basename(MODEL_PATH),
            image_path=image_path,
            user_id=current_user.id,
        )
        db.session.add(pred_row)
        db.session.commit()

        return render_template(
            "prediction.html",
            success=True,
            disease=top_class,
            confidence=f"{top_confidence*100:.2f}%",
            prediction_id=pred_row.id,
            image_path=image_path,
            class_names=class_names,
        )

    except Exception as e:
        return render_template("prediction.html", error=f"Error: {str(e)}"), 500


@app.route("/history", methods=["GET"])
@login_required
def history():
    items = (
        Prediction.query.filter_by(user_id=current_user.id)
        .order_by(Prediction.created_at.desc())
        .all()
    )
    return render_template("history.html", items=items)


@app.route("/feedback", methods=["POST"])
@login_required
def submit_feedback():
    prediction_id = request.form.get("prediction_id", type=int)
    is_corrected = request.form.get("is_corrected") == "true"
    corrected_label = request.form.get("corrected_label", "").strip()
    note = request.form.get("note", "").strip()

    pred = Prediction.query.get_or_404(prediction_id)
    if pred.user_id != current_user.id and current_user.role != "admin":
        flash("You are not allowed to submit feedback for this prediction.", "error")
        return redirect(url_for("history"))

    if is_corrected and not corrected_label:
        flash("Corrected label is required when prediction is wrong.", "error")
        return redirect(url_for("history"))

    fb = Feedback(
        corrected_label=corrected_label if is_corrected else pred.predicted_class,
        is_corrected=is_corrected,
        note=note,
        prediction_id=pred.id,
        user_id=current_user.id,
    )
    db.session.add(fb)
    db.session.commit()

    flash("Feedback submitted.", "success")
    return redirect(url_for("history"))


@app.route("/admin", methods=["GET"])
@login_required
@admin_required
def admin_panel():
    status = request.args.get("status", "all")
    q = Feedback.query.order_by(Feedback.created_at.desc())
    if status == "correct":
        q = q.filter(Feedback.is_corrected == False)
    elif status == "wrong":
        q = q.filter(Feedback.is_corrected == True)

    feedback_items = q.all()
    return render_template("admin.html", feedback_items=feedback_items, status=status)


@app.route("/admin/feedback/<int:feedback_id>/approve", methods=["POST"])
@login_required
@admin_required
def approve_feedback(feedback_id):
    fb = Feedback.query.get_or_404(feedback_id)

    if fb.is_corrected:
        split = request.form.get("split", "train")
        sample = DatasetSample(
            approved=True,
            image_path=fb.prediction.image_path,
            label=fb.corrected_label,
            prediction_id=fb.prediction_id,
            split=split,
        )
        db.session.add(sample)

    fb.handled = True
    db.session.commit()
    flash("Feedback approved and dataset sample saved.", "success")
    return redirect(url_for("admin_panel"))


@app.route("/admin/feedback/<int:feedback_id>/reject", methods=["POST"])
@login_required
@admin_required
def reject_feedback(feedback_id):
    fb = Feedback.query.get_or_404(feedback_id)
    fb.handled = True
    db.session.commit()
    flash("Feedback rejected.", "success")
    return redirect(url_for("admin_panel"))


@app.route("/admin/model/add", methods=["POST"])
@login_required
@admin_required
def add_model():
    name = request.form.get("name", "").strip()
    metrics = request.form.get("metrics", "").strip()
    version = request.form.get("version", "").strip()
    filename = request.form.get("filename", "").strip()

    if not name or not version or not filename:
        flash("name, version and filename are required.", "error")
        return redirect(url_for("admin_panel"))

    item = ModelRegistry(name=name, metrics=metrics, version=version, filename=filename)
    db.session.add(item)
    db.session.commit()

    flash("Model registry entry added.", "success")
    return redirect(url_for("admin_panel"))


@app.route("/init-db")
def init_db():
    db.create_all()
    # seed model
    if not ModelRegistry.query.filter_by(filename=os.path.basename(MODEL_PATH)).first():
        db.session.add(
            ModelRegistry(
                name=os.path.basename(MODEL_PATH),
                metrics='{"note":"initial"}',
                version="1.0",
                filename=os.path.basename(MODEL_PATH),
            )
        )
        db.session.commit()

    return "Database initialized."


# Note: /create-admin removed. Admin credentials are supplied via env vars.


if __name__ == "__main__":
    app.run(port=3000, debug=True)
