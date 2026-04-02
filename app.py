import os
import json
import uuid
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

import tensorflow as tf
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
HF_MODEL_ID = os.getenv("HF_MODEL_ID", "your-username/your-model-repo")
HF_MODEL_FILE = os.getenv(
    "HF_MODEL_FILE",
    "Fusion-ResNet50-EfficientNetV2_model.keras"
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
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
        cache_dir=MODEL_DIR
    )

    # Copy to fixed local path (optional but stable for Flask)
    import shutil
    shutil.copy(model_path, MODEL_PATH)

    print("[INFO] Model downloaded successfully.")
    return MODEL_PATH


# ----------------------------
# Keras compatibility (important for HF / Render)
# ----------------------------
from keras.layers import InputLayer as _InputLayer
from keras.mixed_precision import Policy as _Policy


class _CompatInputLayer(_InputLayer):
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
    @classmethod
    def from_config(cls, config):
        if isinstance(config, dict):
            return cls(config.get("name", "float32"))
        return cls(config)


def _sanitize_keras_config(value):
    if isinstance(value, dict):
        class_name = value.get("class_name")
        config = value.get("config")
        if class_name == "DTypePolicy" and isinstance(config, dict):
            return config.get("name", "float32")
        return {k: _sanitize_keras_config(v) for k, v in value.items()}

    if isinstance(value, list):
        return [_sanitize_keras_config(v) for v in value]

    return value


# ----------------------------
# Load Model
# ----------------------------
def load_prediction_model(model_path):
    if not os.path.exists(model_path):
        return None

    custom_objects = {
        "InputLayer": _CompatInputLayer,
        "DTypePolicy": _CompatDTypePolicy,
        "Policy": _CompatDTypePolicy,
    }

    try:
        model = tf.keras.models.load_model(model_path, compile=False)
        print("[INFO] Model loaded normally.")
        return model

    except Exception as e1:
        print("[WARNING] Normal load failed:", e1)

        try:
            import h5py
            from keras.models import model_from_json
            from keras.utils import custom_object_scope

            with h5py.File(model_path, "r") as f:
                raw_config = f.attrs.get("model_config")

            if isinstance(raw_config, bytes):
                raw_config = raw_config.decode("utf-8")

            config = json.loads(raw_config)
            config = _sanitize_keras_config(config)

            with custom_object_scope(custom_objects):
                model = model_from_json(json.dumps(config))

            model.load_weights(model_path)

            print("[INFO] Model loaded via fallback method.")
            return model

        except Exception as e2:
            print("[ERROR] Fallback failed:", e2)
            return None


# ----------------------------
# Load HF model at startup
# ----------------------------
MODEL_PATH = download_model_from_hf()
model = load_prediction_model(MODEL_PATH)

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

app.config["MODEL"] = model
app.config["CLASS_NAMES"] = class_names
app.config["UPLOAD_DIR"] = UPLOAD_DIR
app.config["ALLOWED_EXTENSIONS"] = ALLOWED_EXTENSIONS

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
                    self.email = email
                    self.id = f"env:{email}"
                    self.username = email.split("@")[0]
                    self.role = "admin"

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