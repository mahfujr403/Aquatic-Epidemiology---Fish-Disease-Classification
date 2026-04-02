import os
import tensorflow as tf
from huggingface_hub import hf_hub_download

from app import HF_MODEL_FILE, HF_MODEL_ID

MODEL_REPO = "YOUR_USERNAME/fish-disease-model"
MODEL_FILE = "final_model.keras"

def load_model_from_hf():
    print("⬇️ Downloading model from HuggingFace...")

    model_path = hf_hub_download(
        repo_id=HF_MODEL_ID,
        filename=HF_MODEL_FILE,
        repo_type="model"
    )

    print("📦 Model downloaded at:", model_path)

    model = tf.keras.models.load_model(model_path, compile=False)

    print("✅ Model loaded successfully")
    return model