from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required
from . import db, models
from .auth_routes import admin_required

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/admin', methods=['GET'])
@login_required
@admin_required
def admin_panel():
    status = request.args.get('status', 'all')
    q = models.Feedback.query.order_by(models.Feedback.created_at.desc())
    if status == 'correct':
        q = q.filter(models.Feedback.is_corrected == False)
    elif status == 'wrong':
        q = q.filter(models.Feedback.is_corrected == True)

    feedback_items = q.all()
    return render_template('admin.html', feedback_items=feedback_items, status=status)


@admin_bp.route('/admin/feedback/<int:feedback_id>/approve', methods=['POST'])
@login_required
@admin_required
def approve_feedback(feedback_id):
    fb = models.Feedback.query.get_or_404(feedback_id)

    if fb.is_corrected:
        split = request.form.get('split', 'train')
        sample = models.DatasetSample(
            approved=True,
            image_path=fb.prediction.image_path,
            label=fb.corrected_label,
            prediction_id=fb.prediction_id,
            split=split,
        )
        db.session.add(sample)

    fb.handled = True
    db.session.commit()
    flash('Feedback approved and dataset sample saved.', 'success')
    return redirect(url_for('admin.admin_panel'))


@admin_bp.route('/admin/feedback/<int:feedback_id>/reject', methods=['POST'])
@login_required
@admin_required
def reject_feedback(feedback_id):
    fb = models.Feedback.query.get_or_404(feedback_id)
    fb.handled = True
    db.session.commit()
    flash('Feedback rejected.', 'success')
    return redirect(url_for('admin.admin_panel'))


@admin_bp.route('/admin/model/add', methods=['POST'])
@login_required
@admin_required
def add_model():
    name = request.form.get('name', '').strip()
    metrics = request.form.get('metrics', '').strip()
    version = request.form.get('version', '').strip()
    filename = request.form.get('filename', '').strip()

    if not name or not version or not filename:
        flash('name, version and filename are required.', 'error')
        return redirect(url_for('admin_panel'))

    item = models.ModelRegistry(name=name, metrics=metrics, version=version, filename=filename)
    db.session.add(item)
    db.session.commit()

    flash('Model registry entry added.', 'success')
    return redirect(url_for('admin.admin_panel'))


@admin_bp.route('/init-db')
def init_db():
    db.create_all()
    # seed model
    model_path = current_app.config.get('MODEL_PATH', '')
    if (model_path and not models.ModelRegistry.query.filter_by(filename=model_path).first()):
        db.session.add(
            models.ModelRegistry(
                name=model_path,
                metrics='{"note":"initial"}',
                version='1.0',
                filename=model_path,
            )
        )
        db.session.commit()

    return 'Database initialized.'
