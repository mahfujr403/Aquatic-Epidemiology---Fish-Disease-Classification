from flask import Blueprint, render_template, request, redirect, url_for, flash
from sqlalchemy.exc import IntegrityError
from . import db
import re
from .models import User
from functools import wraps
from flask_login import current_user


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated or getattr(current_user, 'role', None) != 'admin':
            flash('Admin access required.', 'error')
            return redirect(url_for('index'))
        return fn(*args, **kwargs)

    return wrapper

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        form = {
            'email': request.form.get('email', '').strip().lower(),
            'username': request.form.get('username', '').strip(),
            'password': request.form.get('password', ''),
            'confirm_password': request.form.get('confirm_password', ''),
            'terms': request.form.get('terms'),
        }

        errors = {}

        # Username validation
        if not form['username']:
            errors['username'] = '⚠ Username is required.'
        elif len(form['username']) < 3:
            errors['username'] = '⚠ Username must be at least 3 characters.'
        elif len(form['username']) > 30:
            errors['username'] = '⚠ Username must be 30 characters or fewer.'
        elif not re.match(r'^[a-zA-Z0-9_]+$', form['username']):
            errors['username'] = '⚠ Only letters, numbers, and underscores allowed.'

        # Email validation
        if not form['email']:
            errors['email'] = '⚠ Email address is required.'
        else:
            if not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', form['email']):
                errors['email'] = '⚠ Please enter a valid email address.'

        # Collect password fields (no server-side enforcement)
        pw = form['password'] or ''
        conf = form['confirm_password'] or ''

        # Terms must be checked
        if form.get('terms') not in ('on', 'true', '1'):
            errors['terms'] = '⚠ You must agree to the Terms of Service to continue.'

        # Uniqueness checks
        if 'email' not in errors and User.query.filter_by(email=form['email']).first():
            errors['email'] = '⚠ Email already exists. Please log in or use another email.'

        if 'username' not in errors and User.query.filter_by(username=form['username']).first():
            errors['username'] = '⚠ Username already taken. Choose another.'

        if errors:
            return render_template('register.html', errors=errors, form_data={'email': form['email'], 'username': form['username']})

        user = User(email=form['email'], username=form['username'], role='user')
        user.set_password(pw)
        db.session.add(user)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            errors['email'] = '⚠ Email already exists. Please log in or use another email.'
            return render_template('register.html', errors=errors, form_data={'email': form['email'], 'username': form['username']})

        flash('Registration successful. Please log in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('register.html', errors={}, form_data={})


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()

        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            flash('Invalid email or password.', 'error')
            return redirect(url_for('auth.login'))

        from flask_login import login_user
        login_user(user)
        flash('Logged in successfully.', 'success')
        return redirect(url_for('pred.predict_get'))

    return render_template('login.html')


@auth_bp.route('/logout')
def logout():
    from flask_login import logout_user
    logout_user()
    # Redirect to homepage with a flag so the homepage can show a modal (avoid using flash here)
    return redirect(url_for('index', logged_out=1))


@auth_bp.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()

        admin_email = None
        admin_password = None
        try:
            import os
            admin_email = os.getenv('ADMIN_EMAIL')
            admin_password = os.getenv('ADMIN_PASSWORD')
        except Exception:
            pass

        if admin_email and admin_password and email == admin_email and password == admin_password:
            user = User.query.filter_by(email=email).first()
            if not user:
                username = os.getenv('ADMIN_USERNAME') or email.split('@')[0]
                user = User(email=email, username=username, role='admin')
                user.set_password(password)
                db.session.add(user)
                db.session.commit()

            from flask_login import login_user
            login_user(user)
            flash('Admin logged in successfully.', 'success')
            return redirect(url_for('admin.admin_panel'))

        flash('Invalid admin credentials.', 'error')
        return redirect(url_for('auth.admin_login'))

    return render_template('admin_login.html')
