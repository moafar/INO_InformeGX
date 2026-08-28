"""Application error handlers."""

from __future__ import annotations

from flask import Flask, render_template


def register_error_handlers(app: Flask) -> None:
    """Register minimal error pages."""

    @app.errorhandler(404)
    def not_found(_error):
        return render_template(
            "error.html",
            title="No encontrado",
            message="La página solicitada no existe.",
        ), 404

    @app.errorhandler(500)
    def server_error(_error):
        return render_template(
            "error.html",
            title="Error interno",
            message="Se produjo un error inesperado.",
        ), 500
