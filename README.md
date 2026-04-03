# Aquatic Epidemiology — Fish Disease Classification

Professional repository README for the Fish Disease Classification web app.

## Project Overview

- **Purpose:** Web application for detecting common fish diseases from images using a custom fused classification model (ResNet50 + EfficientNetV2) exported as a TensorFlow Lite model.
- **Primary features:** image upload UI, user accounts, prediction history, feedback collection (label corrections), admin model registry and dataset sample tracking, optional Cloudinary upload, and lazy model downloading from Hugging Face.

## Contents

- `app.py` — Flask application entrypoint and TFLite model loader.
- `aquadiag/` — Flask application package (blueprints, models, model loader).
  - `model_loader.py` — lazy download + TFLite interpreter wrapper.
  - `prediction_routes.py` — prediction endpoint + image handling, Cloudinary integration, DB persistence.
  - `models.py` — SQLAlchemy models: `User`, `Prediction`, `Feedback`, `DatasetSample`, `ModelRegistry`.
- `models/` — contains local `.tflite` model files (also downloaded from Hugging Face by default).
- `scripts/` — utility scripts (download from HF, run a local prediction test).
- `templates/`, `static/` — UI templates and assets.

## Class labels

The app expects a 7-class model with the following labels (order matters):

1. Bacterial Red disease
2. Bacterial diseases - Aeromoniasis
3. Bacterial gill disease
4. Fungal diseases Saprolegniasis
5. Healthy Fish
6. Parasitic diseases
7. Viral diseases White tail disease

## Tech Stack

- Python 3.8+ (use a virtualenv)
- Flask (web framework)
- Flask-Login, Flask-SQLAlchemy
- TensorFlow Lite or tflite-runtime for inference
- NumPy, Pillow for image processing
- Hugging Face Hub for model hosting and download
- Gunicorn for production WSGI
- Optional: Cloudinary for remote image storage

See `requirements.txt` for exact versions used.

## Quickstart — Local development

1. Create & activate virtualenv (Windows example):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. Environment variables (example `.env`):

```
SECRET_KEY=change-me
DATABASE_URL=sqlite:///app.db   # or your Postgres URL
# Optional (for Hugging Face model hosting):
HF_MODEL_ID=mahfujr403/Fusion-ResNet50-EfficientNetV2_model
HF_MODEL_FILE=Fusion-ResNet50-EfficientNetV2_model.tflite

# Optional Cloudinary settings if using remote uploads
CLOUDINARY_CLOUD_NAME=...
CLOUDINARY_API_KEY=...
CLOUDINARY_API_SECRET=...
```

3. Create DB tables:

```powershell
python create_db.py
```

4. Start the dev server:

```powershell
python app.py
```

5. Visit `http://localhost:3000/` and register/login to use the prediction UI.

## Test the model locally

- There's a helper script that downloads the TFLite model and runs a dummy prediction:

```powershell
python scripts/run_prediction_test.py
```

This confirms the `.tflite` file loads and produces a probability vector.

## Model details — fused custom classification model

This repository uses a custom fused model named `Fusion-ResNet50-EfficientNetV2_model.tflite`.

What "fused" likely means here (typical approaches):

- Model fusion by concatenating features from two pretrained backbones (ResNet50 and EfficientNetV2), followed by a small classifier head trained on top of the concatenated features.
- Alternatively, an ensemble of two backbones with averaged/logit fusion followed by calibration.

Recommended high-level steps to reproduce/train such a model (TensorFlow / Keras):

1. Prepare dataset with labelled images for the seven classes. Use stratified splits (train/val/test) and maintain consistent image sizing (224x224 used by the app).
2. Build two backbone feature extractors (pretrained on ImageNet):

```py
from tensorflow.keras.applications import ResNet50, EfficientNetV2B0
from tensorflow.keras.layers import GlobalAveragePooling2D, Concatenate, Dense, Input
from tensorflow.keras.models import Model

inp = Input((224,224,3))
back1 = ResNet50(include_top=False, input_tensor=inp, pooling=None)
back2 = EfficientNetV2B0(include_top=False, input_tensor=inp, pooling=None)

f1 = GlobalAveragePooling2D()(back1.output)
f2 = GlobalAveragePooling2D()(back2.output)
merged = Concatenate()([f1, f2])
head = Dense(256, activation='relu')(merged)
out = Dense(7, activation='softmax')(head)
model = Model(inputs=inp, outputs=out)
```

3. Train with class-balanced augmentation, appropriate learning rate schedule, and early stopping. Monitor validation metrics (accuracy, per-class recall/precision, confusion matrix).
4. Optionally fine-tune backbones (unfreeze last blocks) for improved accuracy.
5. Convert to TFLite for inference on the server (or edge):

```py
import tensorflow as tf
converter = tf.lite.TFLiteConverter.from_keras_model(model)
converter.optimizations = [tf.lite.Optimize.DEFAULT]  # optional
converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS]
# For quantization you may need a representative dataset generator
tflite_model = converter.convert()
open('Fusion-ResNet50-EfficientNetV2_model.tflite','wb').write(tflite_model)
```

6. (Optional) Quantize to reduce size/latency. Test accuracy after conversion.
7. Push `.tflite` to a model hosting solution (Hugging Face Model Hub is used here).

Notes: this repo does not contain full training code. The above is a reproducible pattern to create the same fused architecture.

## How the app uses the model

- At startup (lazy): the app downloads `HF_MODEL_FILE` from `HF_MODEL_ID` using `huggingface_hub.hf_hub_download` (see `app.py` and `aquadiag/model_loader.py`).
- The TFLite interpreter expects images resized to `224x224` and normalized to either `[0,1]` or dtype-compatible values (the provided preprocessing divides by 255 when needed).
- Inference returns a probability vector; the app shows top class + full breakdown and stores a `Prediction` row in the DB.

## Extending or updating the model (developer steps)

1. Train a new `.tflite` file following the training steps above.
2. Test locally with `scripts/run_prediction_test.py`.
3. Upload the `.tflite` to a model host (Hugging Face recommended):

```bash
# create a new repo on HF, then use `huggingface_hub` to upload
from huggingface_hub import HfApi
api = HfApi()
# api.create_repo('username/YourModel', repo_type='model')
# api.upload_file(repo_id='username/YourModel', path_or_fileobj='model.tflite', path_in_repo='model.tflite')
```

4. Update `.env` or environment variables: `HF_MODEL_ID` and `HF_MODEL_FILE`.
5. Restart the app; it will download the new model automatically.

## Deployment notes

- `gunicorn` is included for production WSGI: example command:

```bash
gunicorn -w 4 -b 0.0.0.0:8000 app:app
```

- `runtime.txt` is present for Heroku-style deployments (specify Python version if needed).
- Ensure environment variables for `SECRET_KEY` and `DATABASE_URL` are set in the production environment. For a managed DB, use Postgres and set `DATABASE_URL` accordingly.

## Security & Privacy

- Do not commit secrets to the repository. Use environment variables for `SECRET_KEY`, Cloudinary credentials, and any other secrets.
- Validate and sanitize uploaded files (the app restricts extensions to common image formats).

## GitHub push checklist

1. Initialize git (if not already):

```bash
git init
git add .
git commit -m "Initial import: Aquatic Epidemiology - Fish Disease Classification"
git branch -M main
git remote add origin <your-git-remote-url>
git push -u origin main
```

2. Add a `.gitignore` (if not present) to avoid committing large model binaries — prefer storing models on Hugging Face or another model registry. Example entries:

```
models/*.tflite
.venv/
__pycache__/
.env
```

## Troubleshooting

- If the TFLite interpreter fails to load: ensure you installed either `tflite-runtime` (lightweight) or `tensorflow` for your platform.
- If model download fails, check network access to Hugging Face and that `HF_MODEL_ID` and `HF_MODEL_FILE` are correct.

## Contributing

- Add dataset samples to `uploads/` and use `DatasetSample`/admin UI for approval flows.
- When improving the model, provide evaluation metrics (per-class precision/recall, confusion matrix) and add a new `ModelRegistry` row via admin.

## License & Authors

This repo was prepared by the project author. Add a LICENSE file if you want to publish under a specific license.

---
If you'd like, I can also:
- add a `.gitignore` and recommended `.env.example` file,
- create a short training notebook example showing how to implement the fused model,
- or prepare a GitHub Actions workflow to build and validate the `.tflite` artifact and upload to Hugging Face.
