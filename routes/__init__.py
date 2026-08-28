"""HTTP route registration."""

from __future__ import annotations

from flask import Flask

from .auth import auth_bp
from .errors import register_error_handlers
from .home import home_bp
from .studies import studies_bp


def register_routes(app: Flask) -> None:
    """Register blueprints and error handlers."""
    app.register_blueprint(auth_bp)
    app.register_blueprint(home_bp)
    app.register_blueprint(studies_bp)
    register_error_handlers(app)
