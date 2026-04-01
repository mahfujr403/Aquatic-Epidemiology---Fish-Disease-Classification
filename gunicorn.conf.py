import os

# Render is currently scanning for port 3000 in this project, so bind there by default.
# GUNICORN_BIND still allows an explicit override if the platform configuration changes.
bind = os.getenv("GUNICORN_BIND", "0.0.0.0:3000")
workers = int(os.getenv('WEB_CONCURRENCY', '1'))
threads = int(os.getenv('GUNICORN_THREADS', '2'))
timeout = int(os.getenv('GUNICORN_TIMEOUT', '120'))
accesslog = '-'
errorlog = '-'
loglevel = os.getenv('GUNICORN_LOG_LEVEL', 'info')
