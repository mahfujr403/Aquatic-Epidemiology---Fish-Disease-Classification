from PIL import Image
import numpy as np
from keras.utils import img_to_array
import os
import sys

# ensure project root is on sys.path so we can import `a.py` when running from scripts/
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import tensorflow as tf
from huggingface_hub import hf_hub_download


def load_tflite_model(path):
    try:
        interpreter = tf.lite.Interpreter(model_path=path)
    except Exception:
        from tflite_runtime.interpreter import Interpreter

        interpreter = Interpreter(model_path=path)
    interpreter.allocate_tensors()
    return interpreter


def main():
    # HF repo and filename (match app.py)
    REPO_ID = os.getenv("HF_MODEL_ID", "mahfujr403/Fusion-ResNet50-EfficientNetV2_model")
    FILENAME = os.getenv("HF_MODEL_FILE", "Fusion-ResNet50-EfficientNetV2_model.tflite")

    model_dir = os.path.join(ROOT, 'models')
    os.makedirs(model_dir, exist_ok=True)
    model_path = os.path.join(model_dir, FILENAME)

    if not os.path.exists(model_path):
        print('[INFO] model not found locally, downloading from HF...')
        tmp = hf_hub_download(repo_id=REPO_ID, filename=FILENAME)
        import shutil

        shutil.copy(tmp, model_path)
        print('[INFO] downloaded to', model_path)

    interp = load_tflite_model(model_path)

    input_details = interp.get_input_details()
    output_details = interp.get_output_details()

    # create dummy image and preprocess like prediction route
    img = Image.new('RGB', (224, 224), (128, 128, 128))
    arr = img_to_array(img)
    arr = np.expand_dims(arr, axis=0)

    # prepare input
    in_dtype = input_details[0]['dtype']
    inp = arr.astype(in_dtype)
    if np.issubdtype(in_dtype, np.floating) and inp.max() > 2.0:
        inp = inp / 255.0

    interp.set_tensor(input_details[0]['index'], inp.astype(input_details[0]['dtype']))
    interp.invoke()

    out = interp.get_tensor(output_details[0]['index'])

    probs = out[0] if out.ndim == 2 else out.flatten()

    # class names (same as app.py)
    class_names = [
        "Bacterial Red disease",
        "Bacterial diseases - Aeromoniasis",
        "Bacterial gill disease",
        "Fungal diseases Saprolegniasis",
        "Healthy Fish",
        "Parasitic diseases",
        "Viral diseases White tail disease",
    ]

    top_idx = int(np.argmax(probs))
    top_score = float(probs[top_idx])
    top_label = class_names[top_idx] if top_idx < len(class_names) else str(top_idx)

    print(f'Top prediction: {top_label} (idx={top_idx}) score={top_score}')
    print('All scores (len=', len(probs), '):')
    print(probs.tolist())


if __name__ == '__main__':
    main()
