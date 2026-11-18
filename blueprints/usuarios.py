"""Gestión de usuarios de la empresa con límites de licencia."""
import re

from pymysql.err import IntegrityError
from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for
from werkzeug.security import generate_password_hash

from db import execute, query_all, query_one
from security import empresa_requerida, login_required, role_required
from utils import limpiar

bp = Blueprint("usuarios", __name__, url_prefix="/usuarios")

ROLES_EMPRESA = ("admin", "operador")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _usuarios():
    return query_all(
        """SELECT id, nombre, email, rol, activo, ultimo_acceso, creado_en
             FROM usuarios
            WHERE empresa_id = %s
            ORDER BY activo DESC, rol ASC, nombre ASC""",
        (g.empresa_id,),
    )


def _admins_activos(excluir=None):
    if excluir:
        row = query_one(
            """SELECT COUNT(*) AS n FROM usuarios
                WHERE empresa_id = %s AND rol = 'admin' AND activo = 1 AND id <> %s""",
            (g.empresa_id, excluir),
        )
    else:
        row = query_one(
            """SELECT COUNT(*) AS n FROM usuarios
                WHERE empresa_id = %s AND rol = 'admin' AND activo = 1""",
            (g.empresa_id,),
        )
    return row["n"]


def _validar_password(password, confirmacion, errores):
    if len(password) < 8:
        errores["password"] = "Usa al menos 8 caracteres."
    elif not any(c.isalpha() for c in password) or not any(c.isdigit() for c in password):
        errores["password"] = "Combina letras y números."
    elif password != confirmacion:
        errores["password_confirmar"] = "Las contraseñas no coinciden."


@bp.get("")
@login_required
@empresa_requerida
@role_required("admin", "superadmin")
def index():
    usuarios = _usuarios()
    activos = sum(1 for u in usuarios if u["activo"])
    maximo = int(g.licencia["max_usuarios"]) if g.licencia else 0
    uso = round(activos * 100 / maximo, 1) if maximo else 0
    return render_template(
        "usuarios/index.html",
        usuarios=usuarios,
        activos=activos,
        maximo=maximo,
        uso=min(100, uso),
    )


@bp.route("/nuevo", methods=["GET", "POST"])
@login_required
@empresa_requerida
@role_required("admin", "superadmin")
def nuevo():
    datos = {"nombre": "", "email": "", "rol": "operador", "activo": 1}
    errores = {}
    maximo = int(g.licencia["max_usuarios"]) if g.licencia else 0
    activos = query_one(
        "SELECT COUNT(*) AS n FROM usuarios WHERE empresa_id = %s AND activo = 1",
        (g.empresa_id,),
    )["n"]

    if maximo and activos >= maximo:
        flash(
            "Tu licencia permite %s usuarios activos. Desactiva uno o amplía el plan."
            % maximo,
            "warning",
        )
        return redirect(url_for("usuarios.index"))

    if request.method == "POST":
        datos = {
            "nombre": limpiar(request.form.get("nombre"), 120),
            "email": limpiar(request.form.get("email"), 160).lower(),
            "rol": request.form.get("rol", "operador"),
            "activo": 1 if request.form.get("activo") else 0,
        }
        password = request.form.get("password") or ""
        confirmacion = request.form.get("password_confirmar") or ""

        if len(datos["nombre"]) < 3:
            errores["nombre"] = "Escribe el nombre completo."
        if not EMAIL_RE.match(datos["email"]):
            errores["email"] = "Ingresa un correo válido."
        if datos["rol"] not in ROLES_EMPRESA:
            errores["rol"] = "Selecciona un rol válido."
        _validar_password(password, confirmacion, errores)

        if not errores and query_one(
            "SELECT id FROM usuarios WHERE email = %s", (datos["email"],)
        ):
            errores["email"] = "Este correo ya está registrado en el sistema."

        if not errores:
            try:
                execute(
                    """INSERT INTO usuarios
                        (empresa_id, nombre, email, password_hash, rol, activo)
                       VALUES (%s, %s, %s, %s, %s, %s)""",
                    (
                        g.empresa_id,
                        datos["nombre"],
                        datos["email"],
                        generate_password_hash(password),
                        datos["rol"],
                        datos["activo"],
                    ),
                )
                flash("Usuario «%s» creado." % datos["nombre"], "success")
                return redirect(url_for("usuarios.index"))
            except IntegrityError:
                errores["email"] = "Este correo ya está registrado."

    return render_template(
        "usuarios/form.html", modo="nuevo", usuario=None, datos=datos, errores=errores
    )


@bp.route("/<int:usuario_id>/editar", methods=["GET", "POST"])
@login_required
@empresa_requerida
@role_required("admin", "superadmin")
def editar(usuario_id):
    usuario = query_one(
        "SELECT * FROM usuarios WHERE id = %s AND empresa_id = %s",
        (usuario_id, g.empresa_id),
    )
    if not usuario:
        abort(404, description="El usuario no pertenece a esta empresa.")

    es_yo = usuario["id"] == g.user["id"]
    datos = {
        "nombre": usuario["nombre"],
        "email": usuario["email"],
        "rol": usuario["rol"],
        "activo": usuario["activo"],
    }
    errores = {}
    password = ""

    if request.method == "POST":
        datos = {
            "nombre": limpiar(request.form.get("nombre"), 120),
            "email": limpiar(request.form.get("email"), 160).lower(),
            "rol": request.form.get("rol", "operador"),
            "activo": 1 if request.form.get("activo") else 0,
        }
        password = request.form.get("password") or ""
        confirmacion = request.form.get("password_confirmar") or ""

        if len(datos["nombre"]) < 3:
            errores["nombre"] = "Escribe el nombre completo."
        if not EMAIL_RE.match(datos["email"]):
            errores["email"] = "Ingresa un correo válido."
        if datos["rol"] not in ROLES_EMPRESA:
            errores["rol"] = "Selecciona un rol válido."

        if es_yo:
            if datos["rol"] != "admin":
                errores["rol"] = "No puedes quitarte el rol de administrador."
            if not datos["activo"]:
                errores["activo"] = "No puedes desactivar tu propia cuenta."

        if usuario["rol"] == "admin" and usuario["activo"]:
            queda_sin_admin = (datos["rol"] != "admin" or not datos["activo"])
            if queda_sin_admin and not _admins_activos(excluir=usuario_id):
                errores["rol"] = "Debe existir al menos un administrador activo."

        if usuario["activo"] == 0 and datos["activo"] == 1 and g.licencia:
            activos = query_one(
                "SELECT COUNT(*) AS n FROM usuarios WHERE empresa_id = %s AND activo = 1",
                (g.empresa_id,),
            )["n"]
            if activos >= int(g.licencia["max_usuarios"]):
                errores["activo"] = "La licencia no permite reactivar más usuarios."

        if password:
            _validar_password(password, confirmacion, errores)

        if not errores and query_one(
            "SELECT id FROM usuarios WHERE email = %s AND id <> %s",
            (datos["email"], usuario_id),
        ):
            errores["email"] = "Este correo ya está registrado por otro usuario."

        if not errores:
            try:
                if password:
                    execute(
                        """UPDATE usuarios SET nombre = %s, email = %s, rol = %s,
                               activo = %s, password_hash = %s
                             WHERE id = %s AND empresa_id = %s""",
                        (
                            datos["nombre"],
                            datos["email"],
                            datos["rol"],
                            datos["activo"],
                            generate_password_hash(password),
                            usuario_id,
                            g.empresa_id,
                        ),
                    )
                else:
                    execute(
                        """UPDATE usuarios SET nombre = %s, email = %s, rol = %s,
                               activo = %s
                             WHERE id = %s AND empresa_id = %s""",
                        (
                            datos["nombre"],
                            datos["email"],
                            datos["rol"],
                            datos["activo"],
                            usuario_id,
                            g.empresa_id,
                        ),
                    )
                flash("Usuario actualizado.", "success")
                return redirect(url_for("usuarios.index"))
            except IntegrityError:
                errores["email"] = "Este correo ya está registrado."

    return render_template(
        "usuarios/form.html",
        modo="editar",
        usuario=usuario,
        datos=datos,
        errores=errores,
    )


@bp.post("/<int:usuario_id>/estado")
@login_required
@empresa_requerida
@role_required("admin", "superadmin")
def cambiar_estado(usuario_id):
    usuario = query_one(
        "SELECT id, nombre, rol, activo FROM usuarios WHERE id = %s AND empresa_id = %s",
        (usuario_id, g.empresa_id),
    )
    if not usuario:
        abort(404)
    if usuario["id"] == g.user["id"]:
        flash("No puedes desactivar tu propia cuenta.", "warning")
        return redirect(url_for("usuarios.index"))

    nuevo = 0 if usuario["activo"] else 1

    if usuario["rol"] == "admin" and usuario["activo"] and not nuevo:
        if not _admins_activos(excluir=usuario_id):
            flash("Debe existir al menos un administrador activo.", "warning")
            return redirect(url_for("usuarios.index"))

    if nuevo and g.licencia:
        activos = query_one(
            "SELECT COUNT(*) AS n FROM usuarios WHERE empresa_id = %s AND activo = 1",
            (g.empresa_id,),
        )["n"]
        if activos >= int(g.licencia["max_usuarios"]):
            flash("La licencia no permite reactivar más usuarios.", "warning")
            return redirect(url_for("usuarios.index"))

    execute(
        "UPDATE usuarios SET activo = %s WHERE id = %s AND empresa_id = %s",
        (nuevo, usuario_id, g.empresa_id),
    )
    flash(
        "Usuario «%s» %s." % (usuario["nombre"], "reactivado" if nuevo else "desactivado"),
        "success",
    )
    return redirect(url_for("usuarios.index"))
