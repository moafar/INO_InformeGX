"""Authentication routes."""

from __future__ import annotations

from urllib.parse import urljoin, urlsplit

from flask import Blueprint, abort, current_app, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from services.auth import authenticate_user
from services.csrf import validate_csrf_token
from services.signature_profile import (
    MAX_SIGNATURE_IMAGE_BYTES,
    PNG_MIME_TYPE,
    clear_signature_profile_from_session,
    signature_profile_for_user,
    store_signature_profile_in_session,
    validate_signature_png,
)
from repositories.drafts import release_locks_for_user
from repositories.users import save_user_signature_profile
from services.report_controls import MEDICO


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
    release_locks_for_user(int(current_user.get_id()))
    logout_user()
    clear_signature_profile_from_session()
    return redirect(url_for("auth.login"))


@auth_bp.route("/signature-profile", methods=["GET", "POST"])
@login_required
def signature_profile():
    """Create or update the authenticated physician's complete signature profile."""
    if current_user.role != MEDICO:
        abort(403)
    error = None
    status = 200
    current_profile = signature_profile_for_user(current_user)
    form_values = {
        "signature_name": current_profile.name,
        "profession_specialty": current_profile.profession_specialty,
        "professional_registration": current_profile.professional_registration,
        "institutional_line": current_profile.institutional_line,
    }
    if request.method == "POST":
        form_values = {
            "signature_name": request.form.get("signature_name", "").strip(),
            "profession_specialty": request.form.get("profession_specialty", "").strip(),
            "professional_registration": request.form.get("professional_registration", "").strip(),
            "institutional_line": request.form.get("institutional_line", "").strip(),
        }
        form_values["signature_name"] = form_values["signature_name"] or current_profile.name
        if not validate_csrf_token(request.form.get("csrf_token")):
            error, status = "Formulario no válido.", 400
        elif not form_values["profession_specialty"] or not form_values["professional_registration"]:
            error, status = "Profesión / especialidad y registro profesional son obligatorios.", 400
        elif (
            len(form_values["signature_name"]) > 200
            or len(form_values["profession_specialty"]) > 200
            or len(form_values["professional_registration"]) > 120
            or len(form_values["institutional_line"]) > 300
            or any("\x00" in value for value in form_values.values())
        ):
            error, status = "Los datos del perfil de firma no son válidos.", 400
        else:
            upload = request.files.get("signature_image")
            content = None
            if upload is not None and upload.filename:
                content = upload.stream.read(MAX_SIGNATURE_IMAGE_BYTES + 1)
            try:
                if content is not None:
                    validate_signature_png(content)
                save_user_signature_profile(
                    user_id=int(current_user.get_id()),
                    actor_user_id=int(current_user.get_id()),
                    actor_username=current_user.username,
                    signature_name=form_values["signature_name"],
                    profession_specialty=form_values["profession_specialty"],
                    professional_registration=form_values["professional_registration"],
                    institutional_line=form_values["institutional_line"],
                    signature_image_content=content,
                    signature_image_mime_type=PNG_MIME_TYPE if content is not None else None,
                )
            except ValueError as caught:
                error, status = str(caught), 400
            else:
                return redirect(url_for("auth.signature_profile", updated="1"))
    return render_template(
        "signature_profile.html",
        error=error,
        updated=request.args.get("updated") == "1",
        form_values=form_values,
    ), status
