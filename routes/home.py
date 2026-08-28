"""Protected search route."""

from __future__ import annotations

from flask import Blueprint, render_template, request
from flask_login import login_required

from services.csrf import validate_csrf_token
from services.search import SearchResult, search_by_patient_id_num


home_bp = Blueprint("home", __name__)


@home_bp.route("/", methods=["GET", "POST"])
@login_required
def index():
    """Render the protected search page."""
    result = SearchResult(studies=[])
    error = None

    if request.method == "POST":
        if not validate_csrf_token(request.form.get("csrf_token")):
            return render_template("index.html", result=result, error="Formulario no válido."), 400

        result = search_by_patient_id_num(request.form.get("patient_id_num"))
        error = result.error

    return render_template("index.html", result=result, error=error)
