"""Application factory for the web app."""

from __future__ import annotations

import os

from flask import Flask, redirect, request, url_for
from flask_login import LoginManager

from config import (
    get_config_class,
    resolve_app_database_url,
    resolve_clinical_database_url,
    resolve_cookie_secure,
    resolve_secret_key,
)
from db import init_app as init_db
from repositories.users import get_user_by_id
from services.csrf import generate_csrf_token
from services.signature_profile import store_signature_profile_in_session
from routes import register_routes


login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = None


@login_manager.user_loader
def load_user(user_id: str):
    """Return the authenticated user for Flask-Login."""
    user = get_user_by_id(user_id)
    if user is not None:
        store_signature_profile_in_session(user)
    return user


@login_manager.unauthorized_handler
def unauthorized():
    """Redirect anonymous users to the login page."""
    return redirect(url_for("auth.login", next=request.path))


def create_app(config_name: str | None = None) -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__)
    config_class = get_config_class(config_name)
    app.config.from_object(config_class)

    environment = app.config["ENVIRONMENT"]
    app.config["APP_DATABASE_URL"] = resolve_app_database_url(
        environment,
        os.environ.get("APP_DATABASE_URL"),
    )
    app.config["CLINICAL_DATABASE_URL"] = resolve_clinical_database_url(
        environment,
        os.environ.get("CLINICAL_DATABASE_URL"),
    )
    app.config["SECRET_KEY"] = resolve_secret_key(
        environment,
        os.environ.get("SECRET_KEY"),
    )
    app.config["SESSION_COOKIE_SECURE"] = resolve_cookie_secure(
        environment,
        os.environ.get("SESSION_COOKIE_SECURE"),
    )
    app.config["REMEMBER_COOKIE_SECURE"] = app.config["SESSION_COOKIE_SECURE"]
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["REMEMBER_COOKIE_HTTPONLY"] = True
    app.config["REMEMBER_COOKIE_SAMESITE"] = "Lax"

    app.secret_key = app.config["SECRET_KEY"]

    login_manager.init_app(app)
    app.jinja_env.globals["csrf_token"] = generate_csrf_token
    init_db(app)
    register_routes(app)

    return app
