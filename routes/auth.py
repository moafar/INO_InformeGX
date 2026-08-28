"""Authentication routes."""

from __future__ import annotations

from urllib.parse import urljoin, urlsplit

from flask import Blueprint, current_app, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from services.auth import authenticate_user
from services.csrf import validate_csrf_token
from services.signature_profile import (
    clear_signature_profile_from_session,
    store_signature_profile_in_session,
)


auth_bp = Blueprint("auth", __name__)


def _is_safe_next_url(target: str) -> bool:
    base_url = urlsplit(request.host_url)
    test_url = urlsplit(urljoin(request.host_url, target))
    return test_url.scheme in {"http", "https"} and base_url.netloc == test_url.netloc


def _resolve_next_url() -> str:
    target = request.args.get("next")
    if target and _is_safe_next_url(target):
        return target
    return url_for("home.index")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Render and process the login form."""
    if current_user.is_authenticated:
        return redirect(url_for("home.index"))

    error = None
    username = ""

    if request.method == "POST":
        if not validate_csrf_token(request.form.get("csrf_token")):
            return (
                render_template(
                    "login.html",
                    error="Formulario no válido.",
                    username=username,
                    app_name=current_app.config.get("APP_NAME", "Ergo App"),
                ),
                400,
            )
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        user = authenticate_user(username, password)
        if user is not None:
            login_user(user, remember=False)
            store_signature_profile_in_session(user)
            return redirect(_resolve_next_url())
        error = "Credenciales incorrectas."

    return render_template(
        "login.html",
        error=error,
        username=username,
        app_name=current_app.config.get("APP_NAME", "Ergo App"),
    )


@auth_bp.post("/logout")
@login_required
def logout():
    """Log out the current user."""
    if not validate_csrf_token(request.form.get("csrf_token")):
        return redirect(url_for("home.index"))
    logout_user()
    clear_signature_profile_from_session()
    return redirect(url_for("auth.login"))
