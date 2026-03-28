from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from . import db
from . import models
import os
import uuid
import math
from sqlalchemy import func
from tensorflow.keras.preprocessing.image import load_img, img_to_array
import numpy as np

pred_bp = Blueprint('pred', __name__)


def _feedback_redirect_target():
    """Return a safe local redirect target for feedback flow."""
    next_url = (request.form.get('next') or '').strip()
    if next_url.startswith('/') and not next_url.startswith('//'):
        return next_url

    ref = request.referrer or ''
    if '/history' in ref:
        return url_for('pred.history')
    return url_for('pred.predict_get')


@pred_bp.route('/predict', methods=['GET'])
@login_required
def predict_get():
    class_names = current_app.config.get('CLASS_NAMES', [])
    return render_template('prediction.html', class_names=class_names)


@pred_bp.route('/predict', methods=['POST'])
@login_required
def predict_disease():
    try:
        image = request.files.get('image')
        if not image or image.filename == '':
            flash('Please upload an image.', 'error')
            return redirect(url_for('pred.predict_get'))

        allowed = current_app.config.get('ALLOWED_EXTENSIONS', set())
        if '.' not in image.filename or image.filename.rsplit('.', 1)[1].lower() not in allowed:
            flash('Invalid file type. Please upload PNG, JPG, JPEG, WEBP or GIF.', 'error')
            return redirect(url_for('pred.predict_get'))

        ext = image.filename.rsplit('.', 1)[1].lower()
        unique_name = f"{uuid.uuid4()}.{ext}"
        upload_dir = current_app.config.get('UPLOAD_DIR', os.path.join('static', 'uploads'))
        os.makedirs(upload_dir, exist_ok=True)
        image_path = os.path.join(upload_dir, unique_name)
        image.save(image_path)

        model = current_app.config.get('MODEL')
        if model is None:
            flash('Model not available on server.', 'error')
            return redirect(url_for('pred.predict_get'))

        img = load_img(image_path, target_size=(224, 224))
        img_array = img_to_array(img)
        img_array = np.expand_dims(img_array, axis=0)

        prediction = model.predict(img_array)[0]
        class_names = current_app.config.get('CLASS_NAMES', [])

        top_idx = int(np.argmax(prediction))
        top_class = class_names[top_idx]
        top_confidence = float(prediction[top_idx])

        # Build sorted all-predictions list for breakdown display
        all_predictions = sorted(
            [(class_names[i], float(prediction[i]) * 100) for i in range(len(class_names))],
            key=lambda x: x[1],
            reverse=True,
        )

        pred_row = models.Prediction(
            predicted_class=top_class,
            confidence=top_confidence,
            model_used=os.path.basename(current_app.config.get('MODEL_PATH', '')),
            image_path=image_path,
            user_id=current_user.id,
        )
        db.session.add(pred_row)
        db.session.commit()

        return render_template(
            'prediction.html',
            success=True,
            disease=top_class,
            confidence=f"{top_confidence * 100:.2f}%",
            confidence_raw=top_confidence,          # raw float for JS animation
            all_predictions=all_predictions,        # list of (name, pct) for breakdown bars
            prediction_id=pred_row.id,
            image_path=image_path,
            class_names=class_names,
        )

    except Exception as e:
        return render_template(
            'prediction.html',
            error=f'Error: {str(e)}',
            class_names=current_app.config.get('CLASS_NAMES', []),
        ), 500


@pred_bp.route('/history', methods=['GET'])
@login_required
def history():
    page = request.args.get('page', 1, type=int) or 1
    per_page = 10

    base_q = models.Prediction.query.filter_by(user_id=current_user.id)
    q = base_q.order_by(models.Prediction.created_at.desc())

    total = q.count()
    total_pages = math.ceil(total / per_page) if total else 1
    page = max(1, min(page, total_pages))

    items = q.offset((page - 1) * per_page).limit(per_page).all()

    pagination = {
        'page': page,
        'per_page': per_page,
        'total': total,
        'total_pages': total_pages,
        'has_prev': page > 1,
        'has_next': page < total_pages,
    }

    healthy = base_q.filter(models.Prediction.predicted_class == 'Healthy Fish').count()
    diseased = max(total - healthy, 0)
    avg_conf_raw = (
        db.session.query(func.avg(models.Prediction.confidence))
        .filter(models.Prediction.user_id == current_user.id)
        .scalar()
    ) or 0.0

    history_stats = {
        'total': total,
        'healthy': healthy,
        'diseased': diseased,
        'avg_conf': round(float(avg_conf_raw) * 100, 1) if total else 0.0,
    }

    return render_template('history.html', items=items, pagination=pagination, history_stats=history_stats)


@pred_bp.route('/feedback', methods=['POST'])
@login_required
def submit_feedback():
    target = _feedback_redirect_target()
    prediction_id = request.form.get('prediction_id', type=int)
    is_corrected = request.form.get('is_corrected') == 'true'
    corrected_label = request.form.get('corrected_label', '').strip()
    note = request.form.get('note', '').strip()

    pred = models.Prediction.query.get_or_404(prediction_id)
    if pred.user_id != current_user.id and current_user.role != 'admin':
        flash('You are not allowed to submit feedback for this prediction.', 'error')
        return redirect(target)

    if is_corrected and not corrected_label:
        flash('Corrected label is required when prediction is wrong.', 'error')
        return redirect(target)

    fb = models.Feedback(
        corrected_label=corrected_label if is_corrected else pred.predicted_class,
        is_corrected=is_corrected,
        note=note,
        prediction_id=pred.id,
        user_id=current_user.id,
    )
    db.session.add(fb)
    db.session.commit()

    flash('Feedback submitted. Thank you!', 'success')
    return redirect(target)