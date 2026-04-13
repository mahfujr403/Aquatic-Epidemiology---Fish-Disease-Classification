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
HF_MODEL_ID = os.getenv("HF_MODEL_ID", "mahfujr403/Fusion-ResNet50-EfficientNetV2_model")
HF_MODEL_FILE = os.getenv(
    "HF_MODEL_FILE",
    "Fusion-ResNet50-EfficientNetV2_model.tflite"
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
# Load Model
# ----------------------------
def load_tflite_model(model_path):
    from tflite_runtime.interpreter import Interpreter

    class TFLiteModel:
        def __init__(self, path):
            self.interpreter = Interpreter(model_path=path)
            self.interpreter.allocate_tensors()

            self.input_details = self.interpreter.get_input_details()
            self.output_details = self.interpreter.get_output_details()

        def predict(self, x):
            import numpy as np

            x = np.asarray(x)

            if x.ndim == 3:
                x = np.expand_dims(x, 0)

            input_dtype = self.input_details[0]['dtype']
            x = x.astype(input_dtype)

            # normalize if needed
            if np.issubdtype(input_dtype, np.floating):
                if x.max() > 1:
                    x = x / 255.0

            self.interpreter.set_tensor(
                self.input_details[0]['index'], x
            )

            self.interpreter.invoke()

            output = self.interpreter.get_tensor(
                self.output_details[0]['index']
            )

            return output

    return TFLiteModel(model_path)
# ----------------------------
# Load HF model at startup
# ----------------------------
MODEL_PATH = download_model_from_hf()
model = None

def get_model():
    global model
    if model is None:
        print("[INFO] Loading TFLite model...")
        model_path = download_model_from_hf()
        model = load_tflite_model(model_path)
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

app.config["MODEL"] = model
app.config["MODEL_PATH"] = MODEL_PATH
app.config["CLASS_NAMES"] = class_names
app.config["UPLOAD_DIR"] = UPLOAD_DIR
app.config["ALLOWED_EXTENSIONS"] = ALLOWED_EXTENSIONS


 
# ----------------------------
# Cloudinary config  ← FIX: was missing, causing uploads to always fall back to local
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
