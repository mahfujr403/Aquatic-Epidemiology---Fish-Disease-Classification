"""
aquadiag/activity_logger.py
────────────────────────────
Non-blocking request logging middleware.

Every HTTP request is captured (IP, user-agent, path, method, status,
response-time) and written to the `request_logs` table via a background
worker thread, so the request/response cycle is never delayed.

Sensitive paths (login POST bodies, passwords) are never stored.
IP addresses are partially masked for GDPR-friendliness unless
FULL_IP_LOGGING=1 is set in the environment.
"""

from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import queue
import threading
import time
from datetime import datetime, timezone

from flask import Flask, g, request


# ──────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────
FULL_IP_LOGGING: bool = os.getenv("FULL_IP_LOGGING", "0") == "1"

# Paths that should never be logged (health probes, static assets)
_SKIP_PREFIXES: tuple[str, ...] = (
    "/static/",
    "/favicon.ico",
)

# Background queue — unbounded is fine for low-traffic free tier;
# use maxsize=10_000 in production to shed load gracefully.
_log_queue: queue.Queue = queue.Queue()

_worker_started = False
_worker_lock = threading.Lock()


# ──────────────────────────────────────────────
# IP masking
# ──────────────────────────────────────────────
def _mask_ip(raw_ip: str) -> str:
    """
    Privacy-safe IP representation.
    IPv4  192.168.1.42  → 192.168.1.x
    IPv6  2001:db8::1   → 2001:db8::x
    Falls back to a SHA-256 hash prefix if parsing fails.
    """
    if FULL_IP_LOGGING:
        return raw_ip
    try:
        addr = ipaddress.ip_address(raw_ip)
        if addr.version == 4:
            parts = raw_ip.rsplit(".", 1)
            return f"{parts[0]}.x"
        else:
            return raw_ip.rsplit(":", 1)[0] + ":x"
    except ValueError:
        return hashlib.sha256(raw_ip.encode()).hexdigest()[:12]


def _get_real_ip() -> str:
    """
    Resolve the real client IP, respecting Render / Cloudflare headers.
    """
    for header in ("X-Forwarded-For", "CF-Connecting-IP", "X-Real-IP"):
        value = request.headers.get(header, "")
        if value:
            # X-Forwarded-For may be a comma-separated list; take the first
            return value.split(",")[0].strip()
    return request.remote_addr or "unknown"


# ──────────────────────────────────────────────
# Background writer thread
# ──────────────────────────────────────────────
def _start_worker(app: Flask) -> None:
    """Start a single daemon thread that drains the log queue."""
    global _worker_started
    with _worker_lock:
        if _worker_started:
            return
        _worker_started = True

    def _worker() -> None:
        from aquadiag import db
        from aquadiag.models import RequestLog

        while True:
            try:
                entry: dict = _log_queue.get(timeout=2)
            except queue.Empty:
                continue

            try:
                with app.app_context():
                    log = RequestLog(**entry)
                    db.session.add(log)
                    db.session.commit()
            except Exception as exc:  # noqa: BLE001
                # Never crash the worker; fall back to stderr
                app.logger.warning("[activity_logger] DB write failed: %s", exc)
                try:
                    db.session.rollback()
                except Exception:  # noqa: BLE001
                    pass
            finally:
                _log_queue.task_done()

    t = threading.Thread(target=_worker, daemon=True, name="activity-logger")
    t.start()


# ──────────────────────────────────────────────
# Flask hooks
# ──────────────────────────────────────────────
def init_activity_logger(app: Flask) -> None:
    """
    Register before/after request hooks and start the background worker.

    Usage (in app.py, after db.init_app):
        from aquadiag.activity_logger import init_activity_logger
        init_activity_logger(app)
    """

    @app.before_request
    def _before() -> None:
        g._req_start = time.monotonic()

    @app.after_request
    def _after(response):
        # Skip static files and health probes to reduce noise
        path: str = request.path
        if any(path.startswith(p) for p in _SKIP_PREFIXES):
            return response

        elapsed_ms = round((time.monotonic() - g.get("_req_start", time.monotonic())) * 1000, 2)
        raw_ip = _get_real_ip()

        entry = dict(
            ip_address=_mask_ip(raw_ip),
            user_agent=(request.user_agent.string or "")[:512],
            method=request.method,
            path=path,
            query_string=(request.query_string.decode("utf-8", errors="replace") or None),
            status_code=response.status_code,
            response_time_ms=elapsed_ms,
            referrer=(request.referrer or None)[:512] if request.referrer else None,
            user_id=None,  # filled below if authenticated
            timestamp=datetime.now(timezone.utc),
        )

        # Attach authenticated user id when available (Flask-Login)
        try:
            from flask_login import current_user
            if current_user and current_user.is_authenticated:
                entry["user_id"] = getattr(current_user, "id", None)
        except Exception:  # noqa: BLE001
            pass

        _log_queue.put_nowait(entry)
        return response

    _start_worker(app)
    app.logger.info("[activity_logger] Request logging initialised ✓")