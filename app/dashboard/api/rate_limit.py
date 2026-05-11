"""
Flask-Limiter instance for the Dashboard API.

Usage in views:
    from app.dashboard.api.rate_limit import limiter

    @bp.route("/heavy-endpoint", methods=["POST"])
    @limiter.limit("20/minute")
    def heavy():
        ...

init_app(app) is called in create_app().
"""

try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address

    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=["200/minute"],
        # In-memory storage — fine for single-instance deployment.
        # Swap to Redis storage_uri="redis://..." for multi-instance.
        storage_uri="memory://",
    )
    _LIMITER_AVAILABLE = True
except ImportError:
    import logging
    logging.getLogger(__name__).warning(
        "flask-limiter not installed — rate limiting disabled"
    )
    _LIMITER_AVAILABLE = False

    # Stub so imports in routes don't fail
    class _NoopLimiter:
        def limit(self, *args, **kwargs):
            def decorator(f):
                return f
            return decorator

        def init_app(self, app):
            pass

        def exempt(self, f):
            return f

    limiter = _NoopLimiter()
