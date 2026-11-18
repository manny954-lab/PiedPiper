"""Sesión, CSRF, roles y aislamiento por empresa (multi-tenant)."""
import hmac
import secrets
from datetime import date
from functools import wraps

from flask import abort, flash, g, redirect, request, session, url_for

from db import query_all, query_one

USER_SQL = """
    SELECT u.id, u.empresa_id, u.nombre, u.email, u.password_hash,
           u.rol, u.activo, u.ultimo_acceso, u.creado_en,
           e.nombre AS empresa_nombre, e.slug AS empresa_slug,
           e.activa AS empresa_activa
      FROM usuarios u
      LEFT JOIN empresas e ON e.id = u.empresa_id
     WHERE u.id = %s
"""

LICENCIA_SQL = """
    SELECT l.*,
           (SELECT COUNT(*) FROM usuarios u
             WHERE u.empresa_id = l.empresa_id AND u.activo = 1) AS usuarios_usados,
           (SELECT COUNT(*) FROM productos p
             WHERE p.empresa_id = l.empresa_id) AS productos_usados
      FROM licencias l
     WHERE l.empresa_id = %s
"""


def csrf_token() -> str:
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_urlsafe(32)
    return session["_csrf"]


def rotar_csrf() -> None:
    session["_csrf"] = secrets.token_urlsafe(32)


def csrf_protect():
    if request.method == "POST" and request.endpoint != "static":
        enviado = request.form.get("csrf_token", "") or request.headers.get(
            "X-CSRF-Token", ""
        )
        esperado = session.get("_csrf", "")
        if not enviado or not esperado or not hmac.compare_digest(enviado, esperado):
            abort(
                400,
                description=(
                    "El token de seguridad no es válido o la sesión expiró. "
                    "Recarga la página e inténtalo de nuevo."
                ),
            )


def cargar_contexto():
    """Carga usuario, empresa activa y licencia una vez por petición."""
    g.user = None
    g.empresa = None
    g.empresa_id = None
    g.empresas = []
    g.licencia = None
    g.licencia_ok = True
    g.licencia_motivo = None
    g.licencia_dias = None
    g.alertas_stock = 0

    if request.endpoint == "static":
        return None

    uid = session.get("user_id")
    if not uid:
        return None

    user = query_one(USER_SQL, (uid,))
    if not user or not user["activo"]:
        session.clear()
        flash("Tu sesión terminó o la cuenta fue desactivada.", "warning")
        return redirect(url_for("auth.login"))

    g.user = user

    if user["rol"] == "superadmin":
        g.empresas = query_all(
            "SELECT id, nombre, slug, activa FROM empresas ORDER BY nombre"
        )
        ids = {e["id"] for e in g.empresas}
        eid = session.get("empresa_id")
        if eid not in ids:
            eid = g.empresas[0]["id"] if g.empresas else None
            session["empresa_id"] = eid
        g.empresa_id = eid
        g.empresa = next((e for e in g.empresas if e["id"] == eid), None)
    else:
        if not user["empresa_id"]:
            session.clear()
            flash("Tu cuenta no tiene una empresa asignada.", "error")
            return redirect(url_for("auth.login"))
        g.empresa_id = user["empresa_id"]
        g.empresa = query_one(
            "SELECT id, nombre, slug, activa FROM empresas WHERE id = %s",
            (g.empresa_id,),
        )
        if not g.empresa:
            session.clear()
            flash("La empresa de tu cuenta ya no existe.", "error")
            return redirect(url_for("auth.login"))

    if g.empresa_id:
        g.alertas_stock = query_one(
            """SELECT COUNT(*) AS n FROM productos
                WHERE empresa_id = %s AND activo = 1 AND stock <= stock_minimo""",
            (g.empresa_id,),
        )["n"]

    if g.empresa:
        lic = query_one(LICENCIA_SQL, (g.empresa_id,))
        g.licencia = lic
        if lic:
            dias = (lic["vence"] - date.today()).days
            g.licencia_dias = dias
            if not g.empresa["activa"]:
                g.licencia_ok = False
                g.licencia_motivo = "empresa_inactiva"
            elif lic["estado"] == "suspendida":
                g.licencia_ok = False
                g.licencia_motivo = "suspendida"
            elif lic["estado"] == "vencida" or dias < 0:
                g.licencia_ok = False
                g.licencia_motivo = "vencida"
        else:
            g.licencia_ok = False
            g.licencia_motivo = "sin_licencia"

    # El superadministrador puede entrar a dar soporte aunque la licencia
    # esté vencida; los usuarios de empresa quedan contenidos.
    if g.user["rol"] != "superadmin" and not g.licencia_ok:
        permitidos = {
            "static",
            "auth.logout",
            "auth.cuenta",
            "licencias.mi_licencia",
        }
        if request.endpoint not in permitidos and request.endpoint is not None:
            flash(
                "El acceso está restringido por el estado de la licencia.",
                "warning",
            )
            return redirect(url_for("licencias.mi_licencia"))

    return None


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not getattr(g, "user", None):
            flash("Inicia sesión para continuar.", "info")
            destino = request.path if request.method == "GET" else None
            return redirect(url_for("auth.login", next=destino) if destino else url_for("auth.login"))
        return fn(*args, **kwargs)

    return wrapper


def role_required(*roles):
    def decorador(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not getattr(g, "user", None):
                return redirect(url_for("auth.login"))
            if g.user["rol"] not in roles:
                abort(403, description="Tu rol no tiene permiso para esta sección.")
            return fn(*args, **kwargs)

        return wrapper

    return decorador


def empresa_requerida(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not getattr(g, "empresa_id", None):
            flash("Selecciona una empresa para operar el inventario.", "warning")
            return redirect(url_for("dashboard.index"))
        return fn(*args, **kwargs)

    return wrapper


def init_app(app) -> None:
    app.before_request(csrf_protect)
    app.before_request(cargar_contexto)
