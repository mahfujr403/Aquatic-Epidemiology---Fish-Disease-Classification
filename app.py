import os
import json
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
import re
from flask_cors import CORS
from dotenv import load_dotenv

# load environment from .env (if present)
load_dotenv()


from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.exc import IntegrityError
from werkzeug.utils import secure_filename
from keras.utils import custom_object_scope
import tensorflow as tf
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

from aquadiag import db, login_manager

# Initialize extensions from aquadiag package
db.init_app(app)
login_manager.init_app(app)
setattr(login_manager, "login_view", "auth.login")

# import modular routes and models from package
from aquadiag import models
from aquadiag.auth_routes import auth_bp
from aquadiag.prediction_routes import pred_bp
from aquadiag.admin_routes import admin_bp

app.register_blueprint(auth_bp)
app.register_blueprint(pred_bp)
app.register_blueprint(admin_bp)

# Upload settings
UPLOAD_DIR = os.path.join("static", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

# Model & classes
from scripts.download_models_gdrive import download_models

# Attempt to download models from Google Drive (if MODEL_DRIVE_MAP env var is set)
try:
    download_models()
except Exception:
    # non-fatal; proceed and let load_model fail if models are missing
    pass

from keras.layers import InputLayer as _InputLayer
from keras.mixed_precision import Policy as _Policy


class _CompatInputLayer(_InputLayer):
    """Backward-compatible InputLayer for older H5 configs."""

    def __init__(self, *args, **kwargs):
        if "batch_shape" in kwargs:
            kwargs["batch_input_shape"] = kwargs.pop("batch_shape")
        super().__init__(*args, **kwargs)

    @classmethod
    def from_config(cls, config):
        config = config.copy()
        if "batch_shape" in config:
            config["batch_input_shape"] = config.pop("batch_shape")
        return super().from_config(config)


class _CompatDTypePolicy(_Policy):
    """Compatibility shim for saved Keras dtype policy configs."""

    @classmethod
    def from_config(cls, config):
        if isinstance(config, dict):
            return cls(config.get("name", "float32"))
        return cls(config)


def _sanitize_keras_config(value):
    """Convert serialized Keras dtype policy objects to plain dtype names."""
    if isinstance(value, dict):
        class_name = value.get("class_name")
        config = value.get("config")
        if class_name == "DTypePolicy" and isinstance(config, dict):
            return config.get("name", "float32")
        return {key: _sanitize_keras_config(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_sanitize_keras_config(item) for item in value]
    return value


def _load_prediction_model(model_path):
    """Load the saved fish disease model with compatibility fallbacks."""
    if not os.path.exists(model_path):
        return None

    custom_objects = {
        "InputLayer": _CompatInputLayer,
        "DTypePolicy": _CompatDTypePolicy,
        "Policy": _CompatDTypePolicy,
    }

    try:
        return tf.keras.models.load_model(MODEL_PATH, compile=False)
    except Exception as primary_exc:
        try:
            import h5py
            from keras.models import model_from_json

            with h5py.File(model_path, "r") as handle:
                raw_config = handle.attrs.get("model_config")
                if not raw_config:
                    raise ValueError("Missing model_config in H5 file")

            if isinstance(raw_config, bytes):
                raw_config = raw_config.decode("utf-8")

            model_config = json.loads(raw_config)
            sanitized_config = _sanitize_keras_config(model_config)
            with custom_object_scope(custom_objects):
                model = model_from_json(
                    json.dumps(sanitized_config),
                    custom_objects=custom_objects,
                )
            model.load_weights(model_path)
            print("[INFO] Loaded model via sanitized H5 fallback.")
            return model
        except Exception as fallback_exc:
            print(f"[WARNING] Could not load model: {primary_exc}")
            print(f"[WARNING] Sanitized fallback also failed: {fallback_exc}")
            return None


# MODEL_PATH = "models/ensemble-ResNet50-EfficientNetV2_model.h5"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "models", "Fusion-ResNet50-EfficientNetV2_model.keras")
model = _load_prediction_model(MODEL_PATH)


class_names = [
    "Bacterial Red disease",
    "Bacterial diseases - Aeromoniasis",
    "Bacterial gill disease",
    "Fungal diseases Saprolegniasis",
    "Healthy Fish",
    "Parasitic diseases",
    "Viral diseases White tail disease",
]

# Expose model and related config to blueprints via app.config
app.config['MODEL'] = model
app.config['MODEL_PATH'] = MODEL_PATH
app.config['CLASS_NAMES'] = class_names
app.config['UPLOAD_DIR'] = UPLOAD_DIR
app.config['ALLOWED_EXTENSIONS'] = ALLOWED_EXTENSIONS

# Cloudinary configuration (read from environment if set)
app.config['CLOUDINARY_CLOUD_NAME'] = os.getenv('CLOUDINARY_CLOUD_NAME')
app.config['CLOUDINARY_API_KEY'] = os.getenv('CLOUDINARY_API_KEY')
app.config['CLOUDINARY_API_SECRET'] = os.getenv('CLOUDINARY_API_SECRET')
app.config['CLOUDINARY_FOLDER'] = os.getenv('CLOUDINARY_FOLDER', 'aquadiag/uploads')


#############
# DB models live in aquadiag.models (package)
#############


@login_manager.user_loader
def load_user(user_id):
    # Support in-memory env-admin users with IDs like "env:email"
    try:
        if isinstance(user_id, str) and user_id.startswith("env:"):
            email = user_id.split(":", 1)[1]
            class EnvAdmin(object):
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



#################
# Routes
#################


@app.route("/", methods=["GET"])
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





# Note: /create-admin removed. Admin credentials are supplied via env vars.


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "3000"))
    app.run(host="0.0.0.0", port=port, debug=True)
