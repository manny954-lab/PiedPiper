"""Autenticación: login, logout y cuenta del usuario."""
import threading
import time
from datetime import date

from flask import (
    Blueprint,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

from db import execute, query_one
from security import csrf_token, login_required, rotar_csrf

bp = Blueprint("auth", __name__)

_DUMMY_HASH = generate_password_hash("piedpiper-dummy-password")
_INTENTOS = {}
_LOCK = threading.Lock()
MAX_INTENTOS = 6
VENTANA_SEGUNDOS = 300

DEMO_CUENTAS = [
    ("Administrador global", "admin@piedpiper.software", "PiedPiper2026!"),
    ("Admin. de empresa", "admin@demo.mx", "Demo2026!"),
    ("Operador", "operador@demo.mx", "Operador2026!"),
]


def _intentos_recientes(clave):
    ahora = time.monotonic()
    with _LOCK:
        lista = [t for t in _INTENTOS.get(clave, []) if ahora - t < VENTANA_SEGUNDOS]
        if lista:
            _INTENTOS[clave] = lista
        else:
            _INTENTOS.pop(clave, None)
        return lista


def _registrar_fallo(clave):
    with _LOCK:
        _INTENTOS.setdefault(clave, []).append(time.monotonic())


def _limpiar_intentos(clave):
    with _LOCK:
        _INTENTOS.pop(clave, None)


def _destino_seguro(valor):
    if valor and valor.startswith("/") and not valor.startswith("//"):
        return valor
    return url_for("dashboard.index")


def _validar_password(password, confirmacion, errores, campo="password"):
    if not password or len(password) < 8:
        errores[campo] = "Usa al menos 8 caracteres."
    elif not any(c.isalpha() for c in password) or not any(c.isdigit() for c in password):
        errores[campo] = "Combina letras y números."
    elif password != confirmacion:
        errores["password_confirmar"] = "Las contraseñas no coinciden."


@bp.route("/login", methods=["GET", "POST"])
def login():
    if getattr(g, "user", None):
        return redirect(url_for("dashboard.index"))

    next_url = request.values.get("next", "")
    email = ""
    errores = {}
    recordar = False

    if request.method == "POST":
        csrf_token()
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        recordar = request.form.get("recordar") == "1"

        if not email or "@" not in email or len(email) > 160:
            errores["email"] = "Ingresa un correo válido."
        if not password:
            errores["password"] = "Ingresa tu contraseña."

        if not errores:
            clave = "%s|%s" % (request.remote_addr or "local", email)
            if len(_intentos_recientes(clave)) >= MAX_INTENTOS:
                flash(
                    "Demasiados intentos fallidos. Espera unos minutos antes de volver a intentar.",
                    "error",
                )
                return render_template(
                    "auth/login.html",
                    email=email,
                    errores={},
                    next_url=next_url,
                    recordar=recordar,
                    demo_cuentas=DEMO_CUENTAS if current_app.config["DEMO_MODE"] else [],
                ), 429

            usuario = query_one(
                """
                SELECT u.*, e.nombre AS empresa_nombre, e.activa AS empresa_activa,
                       l.estado AS licencia_estado, l.vence AS licencia_vence
                  FROM usuarios u
                  LEFT JOIN empresas e ON e.id = u.empresa_id
                  LEFT JOIN licencias l ON l.empresa_id = u.empresa_id
                 WHERE u.email = %s
                """,
                (email,),
            )

            hash_guardado = usuario["password_hash"] if usuario else _DUMMY_HASH
            password_ok = check_password_hash(hash_guardado, password)

            if not usuario or not password_ok:
                _registrar_fallo(clave)
                flash("Correo o contraseña incorrectos.", "error")
                return render_template(
                    "auth/login.html",
                    email=email,
                    errores={},
                    next_url=next_url,
                    recordar=recordar,
                    demo_cuentas=DEMO_CUENTAS if current_app.config["DEMO_MODE"] else [],
                )

            if not usuario["activo"]:
                flash("Tu cuenta está desactivada. Contacta al administrador.", "error")
                return render_template(
                    "auth/login.html",
                    email=email,
                    errores={},
                    next_url=next_url,
                    recordar=False,
                    demo_cuentas=DEMO_CUENTAS if current_app.config["DEMO_MODE"] else [],
                )

            _limpiar_intentos(clave)

            session.clear()
            session["user_id"] = usuario["id"]
            session.permanent = bool(recordar)
            rotar_csrf()

            if usuario["rol"] == "superadmin":
                primera = query_one("SELECT id FROM empresas ORDER BY id LIMIT 1")
                session["empresa_id"] = primera["id"] if primera else None
            else:
                session["empresa_id"] = usuario["empresa_id"]

            execute("UPDATE usuarios SET ultimo_acceso = NOW() WHERE id = %s", (usuario["id"],))

            flash("Bienvenido de nuevo, %s." % usuario["nombre"].split()[0], "success")

            if usuario["rol"] != "superadmin":
                if not usuario["empresa_activa"]:
                    flash("La empresa está desactivada. Revisa el estado de la licencia.", "warning")
                elif usuario["licencia_vence"] and usuario["licencia_vence"] < date.today():
                    flash("La licencia de la empresa está vencida.", "warning")
                elif usuario["licencia_estado"] == "suspendida":
                    flash("La licencia de la empresa está suspendida.", "warning")

            return redirect(_destino_seguro(next_url))

    return render_template(
        "auth/login.html",
        email=email,
        errores=errores,
        next_url=next_url,
        recordar=recordar,
        demo_cuentas=DEMO_CUENTAS if current_app.config["DEMO_MODE"] else [],
    )


@bp.post("/logout")
@login_required
def logout():
    session.clear()
    flash("Sesión cerrada correctamente.", "info")
    return redirect(url_for("auth.login"))


@bp.route("/cuenta", methods=["GET", "POST"])
@login_required
def cuenta():
    errores = {}
    tab = request.args.get("tab", "perfil")

    if request.method == "POST":
        accion = request.form.get("accion")

        if accion == "perfil":
            tab = "perfil"
            nombre = (request.form.get("nombre") or "").strip()
            if not nombre or len(nombre) < 3 or len(nombre) > 120:
                errores["nombre"] = "Escribe tu nombre completo (3 a 120 caracteres)."
            if not errores:
                execute(
                    "UPDATE usuarios SET nombre = %s WHERE id = %s",
                    (nombre, g.user["id"]),
                )
                flash("Tus datos se actualizaron.", "success")
                return redirect(url_for("auth.cuenta"))

        elif accion == "password":
            tab = "password"
            actual = request.form.get("password_actual") or ""
            nueva = request.form.get("password") or ""
            confirmar = request.form.get("password_confirmar") or ""

            if not check_password_hash(g.user.get("password_hash", ""), actual):
                errores["password_actual"] = "La contraseña actual no es correcta."
            _validar_password(nueva, confirmar, errores)
            if nueva and actual and nueva == actual:
                errores["password"] = "La nueva contraseña debe ser diferente a la actual."

            if not errores:
                execute(
                    "UPDATE usuarios SET password_hash = %s WHERE id = %s",
                    (generate_password_hash(nueva), g.user["id"]),
                )
                flash("Contraseña actualizada. Úsala en tu próximo inicio de sesión.", "success")
                return redirect(url_for("auth.cuenta", tab="password"))

    return render_template("auth/cuenta.html", errores=errores, tab=tab)
