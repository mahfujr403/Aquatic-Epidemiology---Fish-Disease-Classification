import os
import shutil
from huggingface_hub import hf_hub_download, login, HfApi

# Configure these to match your HF repo and filename
REPO_ID = os.getenv("HF_MODEL_ID", "mahfujr403/Fusion-ResNet50-EfficientNetV2_model")
FILENAME = os.getenv("HF_MODEL_FILE", "Fusion-ResNet50-EfficientNetV2_model.tflite")

LOCAL_DIR = os.path.join("models")
os.makedirs(LOCAL_DIR, exist_ok=True)
LOCAL_PATH = os.path.join(LOCAL_DIR, FILENAME)

# If the model isn't present locally, download it from HF to `models/`
if not os.path.exists(LOCAL_PATH):
    print(f"[INFO] Local model not found at {LOCAL_PATH}. Downloading from Hugging Face...")
    model_file = hf_hub_download(repo_id=REPO_ID, filename=FILENAME)
    shutil.copy(model_file, LOCAL_PATH)
    print(f"[INFO] Model downloaded to {LOCAL_PATH}.")
else:
    print(f"[INFO] Found local model at {LOCAL_PATH}.")

# By default do not upload. Set UPLOAD_TO_HF=1 to enable upload behavior.
if os.getenv("UPLOAD_TO_HF") == "1":
    token = os.getenv("HF_TOKEN")
    if not token:
        raise RuntimeError("HF_TOKEN not set. Cannot upload.")
    login(token=token)
    api = HfApi()
    print("[INFO] Uploading model file to Hugging Face repo...")
    api.upload_file(
        path_or_fileobj=LOCAL_PATH,
        path_in_repo=FILENAME,
        repo_id=REPO_ID,
        repo_type="model",
    )
    print("[INFO] Upload complete.")
else:
    print("[INFO] UPLOAD_TO_HF not set. Skipping upload step.")