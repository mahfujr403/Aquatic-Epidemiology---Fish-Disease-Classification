from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from . import db
from . import models
import os
import uuid
from tensorflow.keras.preprocessing.image import load_img, img_to_array
import numpy as np

pred_bp = Blueprint('pred', __name__)


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
            flash('Invalid file type.', 'error')
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
        top_idx = int(np.argmax(prediction))
        top_class = current_app.config.get('CLASS_NAMES', [])[top_idx]
        top_confidence = float(prediction[top_idx])

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
            confidence=f"{top_confidence*100:.2f}%",
            prediction_id=pred_row.id,
            image_path=image_path,
            class_names=current_app.config.get('CLASS_NAMES', []),
        )

    except Exception as e:
        return render_template('prediction.html', error=f'Error: {str(e)}'), 500


@pred_bp.route('/history', methods=['GET'])
@login_required
def history():
    items = (
        models.Prediction.query.filter_by(user_id=current_user.id)
        .order_by(models.Prediction.created_at.desc())
        .all()
    )
    return render_template('history.html', items=items)


@pred_bp.route('/feedback', methods=['POST'])
@login_required
def submit_feedback():
    prediction_id = request.form.get('prediction_id', type=int)
    is_corrected = request.form.get('is_corrected') == 'true'
    corrected_label = request.form.get('corrected_label', '').strip()
    note = request.form.get('note', '').strip()

    pred = models.Prediction.query.get_or_404(prediction_id)
    if pred.user_id != current_user.id and current_user.role != 'admin':
        flash('You are not allowed to submit feedback for this prediction.', 'error')
        return redirect(url_for('pred.history'))

    if is_corrected and not corrected_label:
        flash('Corrected label is required when prediction is wrong.', 'error')
        return redirect(url_for('pred.history'))

    fb = models.Feedback(
        corrected_label=corrected_label if is_corrected else pred.predicted_class,
        is_corrected=is_corrected,
        note=note,
        prediction_id=pred.id,
        user_id=current_user.id,
    )
    db.session.add(fb)
    db.session.commit()

    flash('Feedback submitted.', 'success')
    return redirect(url_for('pred.history'))
