import os
import json
import uuid
from functools import wraps
from datetime import datetime, timezone

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

import numpy as np

from huggingface_hub import hf_hub_download

# ----------------------------
# Flask setup
# ----------------------------
app = Flask(__name__, template_folder="templates", static_folder="static")
CORS(app)

app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "change-me")

# ----------------------------
# DB config
# ----------------------------
database_url = os.getenv("DATABASE_URL", "sqlite:///app.db")
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

from aquadiag import db, login_manager

db.init_app(app)
login_manager.init_app(app)
login_manager.login_view = "auth.login"

from aquadiag import models
from aquadiag.auth_routes import auth_bp
from aquadiag.prediction_routes import pred_bp
from aquadiag.admin_routes import admin_bp

app.register_blueprint(auth_bp)
app.register_blueprint(pred_bp)
app.register_blueprint(admin_bp)

# ----------------------------
# Upload config
# ----------------------------
UPLOAD_DIR = os.path.join("static", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

# ----------------------------
# Hugging Face Model Config
# ----------------------------
HF_MODEL_ID   = os.getenv("HF_MODEL_ID",   "mahfujr403/Fusion-ResNet50-EfficientNetV2_model")
HF_MODEL_FILE = os.getenv("HF_MODEL_FILE", "Fusion-ResNet50-EfficientNetV2_model.tflite")

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, "models")
os.makedirs(MODEL_DIR, exist_ok=True)

MODEL_PATH = os.path.join(MODEL_DIR, HF_MODEL_FILE)


# ----------------------------
# Download model from Hugging Face
# ----------------------------
def download_model_from_hf():
    if os.path.exists(MODEL_PATH):
        print("[INFO] Model already exists locally.")
        return MODEL_PATH

    print("[INFO] Downloading model from Hugging Face...")
    model_path = hf_hub_download(
        repo_id=HF_MODEL_ID,
        filename=HF_MODEL_FILE,
        cache_dir=MODEL_DIR,
    )
    import shutil
    shutil.copy(model_path, MODEL_PATH)
    print("[INFO] Model downloaded successfully.")
    return MODEL_PATH


# ----------------------------
# Load Model
# ----------------------------
def load_tflite_model(model_path):
    from tflite_runtime.interpreter import Interpreter

    class TFLiteModel:
        def __init__(self, path):
            self.interpreter = Interpreter(model_path=path)
            self.interpreter.allocate_tensors()
            self.input_details  = self.interpreter.get_input_details()
            self.output_details = self.interpreter.get_output_details()

        def predict(self, x):
            x = np.asarray(x)
            if x.ndim == 3:
                x = np.expand_dims(x, 0)
            input_dtype = self.input_details[0]["dtype"]
            x = x.astype(input_dtype)
            if np.issubdtype(input_dtype, np.floating) and x.max() > 1:
                x = x / 255.0
            self.interpreter.set_tensor(self.input_details[0]["index"], x)
            self.interpreter.invoke()
            return self.interpreter.get_tensor(self.output_details[0]["index"])

    return TFLiteModel(model_path)


# ----------------------------
# Lazy model loader
# ----------------------------
MODEL_PATH = download_model_from_hf()
model = None

def get_model():
    global model
    if model is None:
        print("[INFO] Loading TFLite model...")
        model = load_tflite_model(download_model_from_hf())
    return model


# ----------------------------
# Classes
# ----------------------------
class_names = [
    "Bacterial Red disease",
    "Bacterial diseases - Aeromoniasis",
    "Bacterial gill disease",
    "Fungal diseases Saprolegniasis",
    "Healthy Fish",
    "Parasitic diseases",
    "Viral diseases White tail disease",
]

app.config["MODEL"]              = model
app.config["MODEL_PATH"]         = MODEL_PATH
app.config["CLASS_NAMES"]        = class_names
app.config["UPLOAD_DIR"]         = UPLOAD_DIR
app.config["ALLOWED_EXTENSIONS"] = ALLOWED_EXTENSIONS
app.config["CONFIDENCE_THRESHOLD"] = float(os.getenv("CONFIDENCE_THRESHOLD", "0.75"))
app.config["UNKNOWN_LABEL"]        = os.getenv("UNKNOWN_LABEL", "Unknown")

# ----------------------------
# Cloudinary config
# ----------------------------
app.config["CLOUDINARY_CLOUD_NAME"] = os.getenv("CLOUDINARY_CLOUD_NAME")
app.config["CLOUDINARY_API_KEY"]    = os.getenv("CLOUDINARY_API_KEY")
app.config["CLOUDINARY_API_SECRET"] = os.getenv("CLOUDINARY_API_SECRET")
app.config["CLOUDINARY_FOLDER"]     = os.getenv("CLOUDINARY_FOLDER", "aquadiag/uploads")


# ----------------------------
# Login manager
# ----------------------------
@login_manager.user_loader
def load_user(user_id):
    try:
        if isinstance(user_id, str) and user_id.startswith("env:"):
            email = user_id.split(":", 1)[1]

            class EnvAdmin:
                def __init__(self, email):
                    self.email    = email
                    self.id       = f"env:{email}"
                    self.username = email.split("@")[0]
                    self.role     = "admin"

                def get_id(self):
                    return self.id

            return EnvAdmin(email)

        uid = int(user_id)
        return models.User.query.get(uid)
    except Exception:
        return None


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != "admin":
            flash("Admin access required.", "error")
            return redirect(url_for("index"))
        return fn(*args, **kwargs)
    return wrapper


# ═══════════════════════════════════════════════════════
# ①  HEALTH CHECK ENDPOINT
#    — Render free tier sleeps after 15 min of inactivity.
#    — This lightweight endpoint is hit by GitHub Actions
#      every 10 min to keep the dyno awake.
#    — Returns 200 JSON quickly (no DB query) so it never
#      misrepresents the app as healthy when the DB is down.
# ═══════════════════════════════════════════════════════
@app.route("/health")
def health():
    """
    Lightweight liveness probe.
    Always returns HTTP 200 as long as Flask is running.
    Called by the GitHub Actions keep-alive workflow.
    """
    return jsonify(
        status="ok",
        timestamp=datetime.now(timezone.utc).isoformat(),
        service="aquadiag",
    ), 200


# ═══════════════════════════════════════════════════════
# ②  READINESS CHECK ENDPOINT  (optional, deeper probe)
#    — Checks DB connectivity.
#    — Returns 503 if the DB is unavailable so load
#      balancers / monitors know the app is degraded.
# ═══════════════════════════════════════════════════════
@app.route("/health/ready")
def health_ready():
    """
    Deeper readiness probe — verifies DB is reachable.
    Returns 503 if the database connection fails.
    """
    try:
        db.session.execute(db.text("SELECT 1"))
        db_ok = True
    except Exception as exc:
        app.logger.error("[health/ready] DB check failed: %s", exc)
        db_ok = False

    payload = {
        "status":    "ok" if db_ok else "degraded",
        "database":  "ok" if db_ok else "unavailable",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return jsonify(payload), 200 if db_ok else 503


# ═══════════════════════════════════════════════════════
# ③  ANALYTICS ENDPOINT  (admin-only)
#    — Returns the last 500 request logs as JSON.
#    — Useful for building a quick dashboard or feeding
#      into a visualisation tool (Metabase, Grafana, etc.)
# ═══════════════════════════════════════════════════════
@app.route("/admin/analytics/logs")
@login_required
@admin_required
def analytics_logs():
    """
    Returns the 500 most recent request log entries as JSON.
    Protected by admin_required — never exposed publicly.
    """
    from sqlalchemy import text as sa_text

    try:
        logs = (
            models.RequestLog.query
            .order_by(models.RequestLog.timestamp.desc())
            .limit(500)
            .all()
        )
        return jsonify(
            count=len(logs),
            logs=[r.to_dict() for r in logs],
        ), 200
    except Exception as exc:
        return jsonify(error=str(exc)), 500


@app.route("/admin/analytics/summary")
@login_required
@admin_required
def analytics_summary():
    """
    Returns aggregated statistics:
      - Total requests (last 24 h, last 7 d, all time)
      - Top 10 paths
      - Top 10 IPs
      - Average response time
      - Status code breakdown
    """
    from sqlalchemy import func
    from datetime import timedelta

    now = datetime.now(timezone.utc)

    try:
        total_all  = models.RequestLog.query.count()
        total_24h  = models.RequestLog.query.filter(
            models.RequestLog.timestamp >= now - timedelta(hours=24)
        ).count()
        total_7d   = models.RequestLog.query.filter(
            models.RequestLog.timestamp >= now - timedelta(days=7)
        ).count()

        avg_rt = db.session.query(
            func.avg(models.RequestLog.response_time_ms)
        ).scalar() or 0

        top_paths = (
            db.session.query(
                models.RequestLog.path,
                func.count(models.RequestLog.id).label("hits"),
            )
            .group_by(models.RequestLog.path)
            .order_by(func.count(models.RequestLog.id).desc())
            .limit(10)
            .all()
        )

        top_ips = (
            db.session.query(
                models.RequestLog.ip_address,
                func.count(models.RequestLog.id).label("hits"),
            )
            .group_by(models.RequestLog.ip_address)
            .order_by(func.count(models.RequestLog.id).desc())
            .limit(10)
            .all()
        )

        status_breakdown = (
            db.session.query(
                models.RequestLog.status_code,
                func.count(models.RequestLog.id).label("count"),
            )
            .group_by(models.RequestLog.status_code)
            .order_by(models.RequestLog.status_code)
            .all()
        )

        return jsonify(
            totals={
                "all_time": total_all,
                "last_24h": total_24h,
                "last_7d":  total_7d,
            },
            avg_response_time_ms=round(float(avg_rt), 2),
            top_paths=[{"path": p, "hits": h} for p, h in top_paths],
            top_ips=[{"ip": ip, "hits": h} for ip, h in top_ips],
            status_codes=[{"code": c, "count": n} for c, n in status_breakdown],
        ), 200

    except Exception as exc:
        return jsonify(error=str(exc)), 500


# ----------------------------
# Routes
# ----------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/admin/panel")
@login_required
@admin_required
def admin_panel_alias():
    return redirect(url_for("admin.admin_panel"))


@app.route("/predict", methods=["GET"])
@login_required
def predict_get():
    return render_template("prediction.html", class_names=class_names)


# ----------------------------
# Run
# ----------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port, debug=True)
