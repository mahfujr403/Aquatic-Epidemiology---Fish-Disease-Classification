import os
import numpy as np
from huggingface_hub import hf_hub_download

# Global model variable (lazy loading)
model = None

# Hugging Face config
HF_MODEL_ID = os.getenv(
    "HF_MODEL_ID",
    "mahfujr403/Fusion-ResNet50-EfficientNetV2_model"
)
HF_MODEL_FILE = os.getenv(
    "HF_MODEL_FILE",
    "Fusion-ResNet50-EfficientNetV2_model.tflite"
)

# Model storage path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, "..", "models")
os.makedirs(MODEL_DIR, exist_ok=True)

MODEL_PATH = os.path.join(MODEL_DIR, HF_MODEL_FILE)


# ----------------------------
# Download model (only once)
# ----------------------------
def download_model():
    if os.path.exists(MODEL_PATH):
        print("[INFO] Model already exists locally.")
        return MODEL_PATH

    print("[INFO] Downloading model from Hugging Face...")

    model_path = hf_hub_download(
        repo_id=HF_MODEL_ID,
        filename=HF_MODEL_FILE,
        cache_dir=MODEL_DIR
    )

    import shutil
    shutil.copy(model_path, MODEL_PATH)

    print("[INFO] Model downloaded successfully.")
    return MODEL_PATH


# ----------------------------
# Load TFLite model
# ----------------------------
def load_tflite_model(path):
    from tflite_runtime.interpreter import Interpreter

    class TFLiteModel:
        def __init__(self, path):
            self.interpreter = Interpreter(model_path=path)
            self.interpreter.allocate_tensors()

            self.input_details = self.interpreter.get_input_details()
            self.output_details = self.interpreter.get_output_details()

        # Provide a convenience predict() that runs inference on the
        # TFLite interpreter. This implementation DOES NOT perform any
        # normalization (no /255 scaling) so it matches the preprocessing
        # used in `prediction_routes.py` (which passes raw floats in 0-255).
        def predict(self, x):
            x = np.asarray(x)

            # ensure batch dimension
            if x.ndim == 3:
                x = np.expand_dims(x, axis=0)

            input_dtype = self.input_details[0]['dtype']

            # If model expects floating dtype, cast directly (no scaling).
            if np.issubdtype(input_dtype, np.floating):
                x_in = x.astype(input_dtype)
            else:
                # model expects integer (e.g., uint8). If caller provided
                # floats in 0-255 range, round before casting.
                if np.issubdtype(x.dtype, np.floating):
                    x_in = np.rint(x).astype(input_dtype)
                else:
                    x_in = x.astype(input_dtype)

            # set input tensor and invoke
            self.interpreter.set_tensor(self.input_details[0]['index'], x_in)
            self.interpreter.invoke()

            output = self.interpreter.get_tensor(self.output_details[0]['index'])
            return output

    return TFLiteModel(path)


# ----------------------------
# Lazy load model (IMPORTANT)
# ----------------------------
def get_model():
    global model

    if model is None:
        print("[INFO] Lazy loading TFLite model...")
        model_path = download_model()
        model = load_tflite_model(model_path)

    return model