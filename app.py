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
import re
from flask_cors import CORS
from dotenv import load_dotenv

# load environment from .env (if present)
load_dotenv()


from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.exc import IntegrityError
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

from aquadiag import db, login_manager

# Initialize extensions from aquadiag package
db.init_app(app)
login_manager.init_app(app)
login_manager.login_view = "auth.login"

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
    return admin_panel()





@app.route("/predict", methods=["GET"])
@login_required
def predict_get():
    return render_template("prediction.html", class_names=class_names)





# Note: /create-admin removed. Admin credentials are supplied via env vars.


if __name__ == "__main__":
    app.run(port=3000, debug=True)
