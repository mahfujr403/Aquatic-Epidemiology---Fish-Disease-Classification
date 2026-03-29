from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required
from . import db, models
from .auth_routes import admin_required
from sqlalchemy import func
import math

admin_bp = Blueprint('admin', __name__)


@admin_bp.route('/admin', methods=['GET'])
@login_required
@admin_required
def admin_panel():
    status   = request.args.get('status', 'all')      # all | correct | wrong
    reviewed = request.args.get('reviewed', 'all')    # all | reviewed | unreviewed
    page     = request.args.get('page', 1, type=int) or 1
    per_page = 12

    q = models.Feedback.query.order_by(models.Feedback.created_at.desc())

    # filter by prediction correctness
    if status == 'correct':
        q = q.filter(models.Feedback.is_corrected == False)
    elif status == 'wrong':
        q = q.filter(models.Feedback.is_corrected == True)

    # filter by handled/reviewed state
    if reviewed == 'reviewed':
        q = q.filter(models.Feedback.handled == True)
    elif reviewed == 'unreviewed':
        q = q.filter(models.Feedback.handled == False)

    # pagination for admin feedback list
    total_items = q.count()
    total_pages = math.ceil(total_items / per_page) if total_items else 1
    page = max(1, min(page, total_pages))
    feedback_items = q.offset((page - 1) * per_page).limit(per_page).all()

    # stats for the header strip
    total_fb     = models.Feedback.query.count()
    unreviewed_n = models.Feedback.query.filter_by(handled=False).count()
    wrong_n      = models.Feedback.query.filter_by(is_corrected=True).count()
    reviewed_n   = models.Feedback.query.filter_by(handled=True).count()

    stats = {
        'total':      total_fb,
        'unreviewed': unreviewed_n,
        'wrong':      wrong_n,
        'reviewed':   reviewed_n,
    }

    # average confidence across all feedback-associated predictions
    try:
        avg_conf = db.session.query(func.avg(models.Prediction.confidence))\
            .join(models.Feedback, models.Feedback.prediction_id == models.Prediction.id)\
            .scalar()
    except Exception:
        avg_conf = None

    # normalize to None when no data
    stats['avg_confidence'] = float(avg_conf) if avg_conf is not None else None

    pagination = {
        'page': page,
        'per_page': per_page,
        'total': total_items,
        'total_pages': total_pages,
        'has_prev': page > 1,
        'has_next': page < total_pages,
    }

    return render_template(
        'admin.html',
        feedback_items=feedback_items,
        status=status,
        reviewed=reviewed,
        stats=stats,
        pagination=pagination,
    )


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
    return redirect(url_for('admin.admin_panel',
                            status=request.form.get('status', 'all'),
                            reviewed=request.form.get('reviewed', 'all')))


@admin_bp.route('/admin/feedback/<int:feedback_id>/reject', methods=['POST'])
@login_required
@admin_required
def reject_feedback(feedback_id):
    fb = models.Feedback.query.get_or_404(feedback_id)
    fb.handled = True
    db.session.commit()
    flash('Feedback rejected.', 'success')
    return redirect(url_for('admin.admin_panel',
                            status=request.form.get('status', 'all'),
                            reviewed=request.form.get('reviewed', 'all')))


@admin_bp.route('/admin/model/add', methods=['POST'])
@login_required
@admin_required
def add_model():
    name     = request.form.get('name', '').strip()
    metrics  = request.form.get('metrics', '').strip()
    version  = request.form.get('version', '').strip()
    filename = request.form.get('filename', '').strip()

    if not name or not version or not filename:
        flash('name, version and filename are required.', 'error')
        return redirect(url_for('admin.admin_panel'))

    item = models.ModelRegistry(name=name, metrics=metrics, version=version, filename=filename)
    db.session.add(item)
    db.session.commit()

    flash('Model registry entry added.', 'success')
    return redirect(url_for('admin.admin_panel'))


@admin_bp.route('/init-db')
def init_db():
    db.create_all()
    model_path = current_app.config.get('MODEL_PATH', '')
    if model_path and not models.ModelRegistry.query.filter_by(filename=model_path).first():
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