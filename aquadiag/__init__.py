"""aquadiag package
Provide the shared extensions (db, login_manager) so modules can import
them without creating circular imports with the application module.

Modules in this package should import `db` and `login_manager` from here:
	from aquadiag import db, login_manager

"""
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

# Create extension instances here (uninitialized). The application will
# initialize them by calling `init_app` in `app.py`.
db = SQLAlchemy()
login_manager = LoginManager()

# Note: do not import app here. Keep this file lightweight to avoid
# circular imports when other modules import `aquadiag`.
