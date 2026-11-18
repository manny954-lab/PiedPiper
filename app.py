"""PiedPiper Inventario — punto de entrada de la aplicación Flask.

Ejecutar en desarrollo:
    flask --app app run --debug
o:
    python app.py
"""
from datetime import date

import pymysql
from flask import Flask, render_template, request, url_for

from blueprints.auth import bp as auth_bp
from blueprints.categorias import bp as categorias_bp
from blueprints.dashboard import bp as dashboard_bp
from blueprints.empresas import bp as empresas_bp
from blueprints.licencias import bp as licencias_bp
from blueprints.movimientos import bp as movimientos_bp
from blueprints.productos import bp as productos_bp
from blueprints.usuarios import bp as usuarios_bp
from config import Config
from db import init_app as init_db, query_one
from security import csrf_token, init_app as init_security
from utils import PLANES

ROLES = {
    "superadmin": "Superadministrador",
    "admin": "Administrador",
    "operador": "Operador",
}

MESES = [
    "ene", "feb", "mar", "abr", "may", "jun",
    "jul", "ago", "sep", "oct", "nov", "dic",
]


def crear_app(config_object=Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_object)

    init_db(app)
    init_security(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(productos_bp)
    app.register_blueprint(categorias_bp)
    app.register_blueprint(movimientos_bp)
    app.register_blueprint(usuarios_bp)
    app.register_blueprint(empresas_bp)
    app.register_blueprint(licencias_bp)

    registrar_filtros(app)
    registrar_contexto(app)
    registrar_errores(app)
    registrar_cli(app)
    return app


def registrar_filtros(app: Flask) -> None:
    @app.template_filter("money")
    def money(valor):
        try:
            numero = float(valor or 0)
        except (TypeError, ValueError):
            numero = 0.0
        return "${:,.2f}".format(numero)

    @app.template_filter("numero")
    def numero(valor):
        try:
            return "{:,}".format(int(valor or 0))
        except (TypeError, ValueError):
            return "0"

    @app.template_filter("fecha")
    def fecha(valor):
        if not valor:
            return "—"
        return "%02d %s %s" % (valor.day, MESES[valor.month - 1], valor.year)

    @app.template_filter("fecha_hora")
    def fecha_hora(valor):
        if not valor:
            return "—"
        return "%02d %s %s · %s" % (
            valor.day,
            MESES[valor.month - 1],
            valor.year,
            valor.strftime("%H:%M"),
        )

    @app.template_filter("iniciales")
    def iniciales(nombre):
        partes = [p for p in (nombre or "").split() if p]
        return "".join(p[0].upper() for p in partes[:2]) or "?"

    @app.template_filter("signed")
    def signed(valor):
        try:
            return "{:+,}".format(int(valor))
        except (TypeError, ValueError):
            return "0"


def registrar_contexto(app: Flask) -> None:
    @app.context_processor
    def inyectar_globales():
        return {
            "csrf_token": csrf_token,
            "PLANES": PLANES,
            "ROLES": ROLES,
            "hoy": date.today(),
            "app_nombre": app.config["APP_NOMBRE"],
            "app_version": app.config["APP_VERSION"],
            "demo_mode": app.config["DEMO_MODE"],
            "soporte_email": app.config["SOPORTE_EMAIL"],
            "ruta_activa": (request.endpoint or "").split(".")[0],
        }

    @app.template_global()
    def url_con_args(**kwargs):
        """Construye una URL conservando los filtros actuales."""
        params = dict(request.args)
        for clave, valor in kwargs.items():
            if valor is None or valor == "":
                params.pop(clave, None)
            else:
                params[clave] = valor
        destino = dict(request.view_args or {})
        destino.update(params)
        return url_for(request.endpoint or "dashboard.index", **destino)


def registrar_errores(app: Flask) -> None:
    from werkzeug.exceptions import HTTPException

    titulos = {
        400: "Solicitud no válida",
        403: "Acceso restringido",
        404: "Página no encontrada",
        405: "Método no permitido",
    }

    @app.errorhandler(HTTPException)
    def error_http(e):
        titulo = titulos.get(e.code, "Algo salió mal")
        mensaje = e.description
        if e.code == 404:
            mensaje = "La ruta que buscas no existe o fue movida."
        if e.code == 405:
            mensaje = "Esta ruta no admite el método utilizado."
        return (
            render_template(
                "errors/error.html",
                codigo=e.code,
                titulo=titulo,
                mensaje=mensaje,
            ),
            e.code,
        )

    @app.errorhandler(pymysql.err.OperationalError)
    def error_base_datos(e):
        app.logger.error("Error de conexión a MariaDB: %s", e)
        return (
            render_template(
                "errors/db.html",
                detalle=str(e),
            ),
            503,
        )

    @app.errorhandler(500)
    def error_interno(e):
        app.logger.exception("Error interno no controlado")
        return (
            render_template(
                "errors/error.html",
                codigo=500,
                titulo="Error interno",
                mensaje="Ocurrió un error inesperado. Revisa los registros del servidor.",
            ),
            500,
        )


def registrar_cli(app: Flask) -> None:
    import click

    @app.cli.command("check-db")
    def check_db():
        """Verifica la conexión y muestra la versión de MariaDB."""
        try:
            row = query_one(
                "SELECT VERSION() AS version, DATABASE() AS base, NOW() AS ahora"
            )
            click.echo("Conexión OK")
            click.echo("  Base de datos : %s" % row["base"])
            click.echo("  MariaDB       : %s" % row["version"])
            click.echo("  Hora servidor : %s" % row["ahora"])
        except Exception as exc:  # pragma: no cover - comando manual
            click.echo("No fue posible conectar: %s" % exc, err=True)
            raise SystemExit(1)


app = crear_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
