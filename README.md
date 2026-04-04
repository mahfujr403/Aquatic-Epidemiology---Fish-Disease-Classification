# Fish Disease Classification

An efficient, production-ready Flask web application for automatic fish disease detection using a memory-optimized TFLite classification model. Designed for constrained servers and scalable cloud deployment.

---

## Overview

- Problem: Rapid identification of common infectious and non-infectious diseases in cultured fish from imagery, to support aquaculture disease surveillance and rapid response.
- Solution: A lightweight web service that accepts fish images, runs on-device-style inference with a TFLite fusion classifier (ResNet50 + EfficientNetV2 features), and provides an authenticated UX for prediction history, feedback, and admin model management.

This repository contains the full backend, model loader, prediction flow, and utilities required to deploy the service as a production web app.

---

## Research Publication

- IEEE paper: "PLACEHOLDER — Fish Disease Detection with Fused Backbones" — link: [placeholder link](#)  
- DOI: 10.XXXX/IEEE.XXXXXXX (placeholder)

Provide the final citation and DOI here when available.

---

## Live Demo

Live service: https://fish-disease-classification.onrender.com

---

## Key Features

- Authenticated user accounts with Flask-Login and role-based admin access.
- Single-image upload prediction endpoint with client-side and server-side validation.
- Lazy download of a hosted TFLite model from Hugging Face (avoids shipping large binaries in repo).
- Memory-efficient inference using `tflite-runtime` (no TensorFlow runtime required in production).
- Prediction history, per-user statistics, and paginated history UI.
- User feedback pipeline (corrected labels, notes) with `Feedback` model and admin handling.
- Optional Cloudinary image storage with secure upload fallback to local storage when credentials are absent.
- Admin model registry and dataset sample tracking for controlled model rollouts.

---

## Machine Learning Pipeline (inference flow)

1. Model hosting: `.tflite` artifact stored on Hugging Face model repo (configurable via `HF_MODEL_ID` and `HF_MODEL_FILE`).
2. Lazy download: `hf_hub_download` copies the `.tflite` into `models/` when first needed (`aquadiag/model_loader.py`, `app.py`).
3. Interpreter: `tflite_runtime.Interpreter` (or TF Lite Python fallback) is instantiated and tensors allocated.
4. Preprocessing: incoming images resized to 224×224, converted to RGB, cast to the interpreter input dtype and normalized (/255 when float input expected).
5. Inference: model returns a probability vector for 7 classes; top prediction saved to DB and returned to the UI.

Notes: The `scripts/run_prediction_test.py` helper validates the downloaded `.tflite` on a dummy image.

---

## User Features

- Authentication: register/login, role (`user`, `admin`) management.
- Prediction UI: upload an image, receive top class and confidence, view full probability breakdown.
- History: per-user paginated prediction history with simple analytics (counts, average confidence).
- Feedback: users may mark predictions incorrect and submit corrected labels and notes.
- Admin panel: manage models, review feedback, approve dataset samples.

---

## System Architecture

- Flask application with three blueprints: `auth_routes`, `prediction_routes`, `admin_routes`.
- Persistence: SQLAlchemy models stored in `DATABASE_URL` (SQLite by default; PostgreSQL supported).
- Model artifacts stored on disk under `models/` and referenced in `ModelRegistry`.
- Optional external image storage via Cloudinary; otherwise saved under `static/uploads`.
- Deployed with Gunicorn on Render; environment-based configuration drives model/source selection.

Diagram (conceptual):

- Client -> Flask (uploads) -> Preprocess -> TFLite Interpreter -> Result -> DB (Prediction + Feedback)

---

## Tech Stack

- Python 3.x
- Flask, Flask-Login, Flask-SQLAlchemy
- tflite-runtime (or TensorFlow Lite Python API as fallback)
- NumPy, Pillow
- Hugging Face Hub (`huggingface_hub`) for artifact hosting
- Gunicorn for production WSGI
- Optional: Cloudinary for image hosting

Dependencies: see `requirements.txt` for pinned versions.

---

## Model Details

- Format: TensorFlow Lite (`.tflite`) — optimized for low-memory inference.
- Architecture: fused classifier built from ResNet50 and EfficientNetV2 feature extractors (feature concatenation or ensemble fusion), final dense head producing 7-way softmax.
- Classes (index order matters):
  1. Bacterial Red disease
  2. Bacterial diseases - Aeromoniasis
  3. Bacterial gill disease
  4. Fungal diseases Saprolegniasis
  5. Healthy Fish
  6. Parasitic diseases
  7. Viral diseases White tail disease
- Optimizations: conversion to TFLite, optionally with post-training quantization to reduce memory and latency.

---

## Project Structure

```
.
├── app.py
├── a.py
├── create_db.py
├── requirements.txt
├── runtime.txt
├── gunicorn.conf.py
├── README.md
├── .env.example
├── .gitignore
├── aquadiag/
│   ├── __init__.py
│   ├── admin_routes.py
│   ├── auth_routes.py
│   ├── model_loader.py
│   ├── models.py
│   └── prediction_routes.py
├── models/  (contains Fusion-ResNet50-EfficientNetV2_model.tflite)
├── scripts/
│   ├── download_models_hf.py
│   └── run_prediction_test.py
├── static/
│   ├── css/
│   └── js/
└── templates/
```

---

## Installation (developer)

1. Clone the repo.
2. Create & activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

3. Configure environment variables (see `.env.example`).
4. Initialize the database:

```powershell
python create_db.py
```

5. Run locally:

```powershell
python app.py
```

6. Use `scripts/run_prediction_test.py` to validate model loading.

---

## Environment Variables

- `SECRET_KEY` — Flask secret key
- `DATABASE_URL` — SQLAlchemy connection string (default: `sqlite:///app.db`)
- `HF_MODEL_ID` — Hugging Face repo id for the `.tflite` artifact
- `HF_MODEL_FILE` — filename of the `.tflite` model in the HF repo
- `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET` — optional Cloudinary credentials
- `CLOUDINARY_FOLDER` — optional upload folder
- `PORT` — server port for local runs

See `.env.example` for a template.

---

## UI Screenshots

Place screenshots in `assets/screenshots/` and reference here:

- `assets/screenshots/index.png` — landing page and upload UI
- `assets/screenshots/prediction.png` — prediction result with breakdown
- `assets/screenshots/history.png` — user history and stats
- `assets/screenshots/admin.png` — admin panel model registry

---

## Deployment (Render + Gunicorn)

- Gunicorn command used in production:

```bash
gunicorn -w 4 -b 0.0.0.0:$PORT app:app
```

- Render: configure a Python service, set build and start commands, and add environment variables (`SECRET_KEY`, `DATABASE_URL`, HF variables, Cloudinary credentials).

---

## Performance and Memory Optimizations

- TFLite runtime: uses `tflite-runtime` to avoid the full TensorFlow dependency and reduce memory footprint.
- Lazy downloading: model is downloaded and loaded only when the first prediction is requested.
- Input preprocessing is minimal and performed in-memory; images are resized to 224×224 to match model input.
- Predictions are single-image, synchronous calls to the interpreter — minimal memory overhead compared to full TF.

---

## Future Improvements

- Add a lightweight async inference queue with worker pool for higher throughput.
- Add representative dataset generator and quantization-aware training to improve quantized accuracy.
- Add automated model evaluation and CI that verifies `.tflite` outputs against a reference set.
- Add multi-image batch endpoint and confidence calibration.

---

## Use Cases

- On-farm disease triage via mobile-uploaded photos.
- Research datasets where low-cost inference servers analyze images at scale.
- Teaching and demonstrations for resource-constrained ML deployment.

---

## Author

Mahfujur Rahman — IEEE-published researcher and ML practitioner.

---

## Contact

- Email: mahfujur@example.com  
- GitHub: https://github.com/mahfujr403

---

## Note for Recruiters

- This project demonstrates an end-to-end production deployment: research-led model design (fused backbones) combined with engineering practices for low-memory inference and cloud deployment.  
- The service is live and running on Render, illustrating real-world operational experience.  
- The code emphasizes optimization under resource constraints (no TF runtime required in production, lazy loading, TFLite conversion), reproducible model hosting (Hugging Face), and product features (auth, history, feedback, admin).


