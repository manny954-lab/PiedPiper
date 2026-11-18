"""Administración global de empresas (solo superadministrador)."""
import re
from datetime import date, timedelta

from pymysql.err import IntegrityError
from flask import Blueprint, abort, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import generate_password_hash

from db import execute, query_all, query_one, tx
from security import login_required, role_required
from utils import PLANES, clave_licencia, fecha_iso, limpiar, slugify

bp = Blueprint("empresas", __name__, url_prefix="/empresas")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
ESTADOS_LICENCIA = ("activa", "prueba", "suspendida", "vencida")


def _listado():
    empresas = query_all(
        """
        SELECT e.*, l.id AS licencia_id, l.plan, l.estado AS licencia_estado,
               l.vence, l.inicio, l.max_usuarios, l.max_productos,
               (SELECT COUNT(*) FROM usuarios u WHERE u.empresa_id = e.id) AS usuarios,
               (SELECT COUNT(*) FROM productos p WHERE p.empresa_id = e.id) AS productos
          FROM empresas e
          LEFT JOIN licencias l ON l.empresa_id = e.id
         ORDER BY e.activa DESC, e.nombre ASC
        """
    )
    for e in empresas:
        e["dias"] = (e["vence"] - date.today()).days if e["vence"] else None
    return empresas


@bp.get("")
@login_required
@role_required("superadmin")
def index():
    empresas = _listado()
    activas = [e for e in empresas if e["activa"]]
    vigentes = [
        e for e in activas
        if e["licencia_estado"] in ("activa", "prueba") and e["dias"] is not None and e["dias"] >= 0
    ]
    mrr = sum(
        PLANES.get(e["plan"], {}).get("precio_mes", 0)
        for e in vigentes
        if e["licencia_estado"] == "activa"
    )
    resumen = {
        "empresas": len(empresas),
        "activas": len(activas),
        "vigentes": len(vigentes),
        "mrr": mrr,
    }
    return render_template("empresas/index.html", empresas=empresas, resumen=resumen)


def _validar_empresa(form, empresa_id=None):
    datos = {
        "nombre": limpiar(form.get("nombre"), 120),
        "slug": slugify(form.get("slug") or form.get("nombre") or ""),
        "rfc": limpiar(form.get("rfc"), 20).upper(),
        "correo": limpiar(form.get("correo"), 160).lower(),
        "telefono": limpiar(form.get("telefono"), 40),
        "direccion": limpiar(form.get("direccion"), 220),
        "activa": 1 if form.get("activa") else 0,
    }
    errores = {}

    if len(datos["nombre"]) < 3:
        errores["nombre"] = "Escribe el nombre de la empresa."
    if datos["correo"] and not EMAIL_RE.match(datos["correo"]):
        errores["correo"] = "El correo no tiene un formato válido."

    if empresa_id:
        duplicado = query_one(
            "SELECT id FROM empresas WHERE slug = %s AND id <> %s",
            (datos["slug"], empresa_id),
        )
    else:
        duplicado = query_one("SELECT id FROM empresas WHERE slug = %s", (datos["slug"],))
    if duplicado:
        errores["slug"] = "Ese identificador ya está en uso."

    return datos, errores


@bp.route("/nueva", methods=["GET", "POST"])
@login_required
@role_required("superadmin")
def nueva():
    datos = {
        "nombre": "",
        "slug": "",
        "rfc": "",
        "correo": "",
        "telefono": "",
        "direccion": "",
        "activa": 1,
    }
    licencia = {
        "plan": "profesional",
        "estado": "activa",
        "vence": (date.today() + timedelta(days=365)).isoformat(),
        "max_usuarios": str(PLANES["profesional"]["usuarios"]),
        "max_productos": str(PLANES["profesional"]["productos"]),
        "notas": "",
    }
    admin = {"admin_nombre": "", "admin_email": ""}
    errores = {}

    if request.method == "POST":
        datos, errores = _validar_empresa(request.form)
        licencia = {
            "plan": request.form.get("plan", "basico"),
            "estado": request.form.get("estado", "activa"),
            "vence": limpiar(request.form.get("vence"), 10),
            "max_usuarios": limpiar(request.form.get("max_usuarios"), 8),
            "max_productos": limpiar(request.form.get("max_productos"), 10),
            "notas": limpiar(request.form.get("notas"), 255),
        }
        admin = {
            "admin_nombre": limpiar(request.form.get("admin_nombre"), 120),
            "admin_email": limpiar(request.form.get("admin_email"), 160).lower(),
        }
        password = request.form.get("admin_password") or ""
        confirmacion = request.form.get("admin_password_confirmar") or ""

        if licencia["plan"] not in PLANES:
            errores["plan"] = "Selecciona un plan válido."
        if licencia["estado"] not in ESTADOS_LICENCIA:
            errores["estado"] = "Selecciona un estado válido."
        vence = fecha_iso(licencia["vence"])
        if not vence:
            errores["vence"] = "Indica la fecha de vencimiento."

        try:
            max_usuarios = int(licencia["max_usuarios"])
            if max_usuarios < 1 or max_usuarios > 100000:
                raise ValueError
        except (TypeError, ValueError):
            errores["max_usuarios"] = "Indica un límite válido."
            max_usuarios = 0
        try:
            max_productos = int(licencia["max_productos"])
            if max_productos < 1 or max_productos > 10000000:
                raise ValueError
        except (TypeError, ValueError):
            errores["max_productos"] = "Indica un límite válido."
            max_productos = 0

        if len(admin["admin_nombre"]) < 3:
            errores["admin_nombre"] = "Escribe el nombre del administrador."
        if not EMAIL_RE.match(admin["admin_email"]):
            errores["admin_email"] = "Ingresa un correo válido."
        elif query_one("SELECT id FROM usuarios WHERE email = %s", (admin["admin_email"],)):
            errores["admin_email"] = "Ese correo ya está registrado."
        if len(password) < 8:
            errores["admin_password"] = "Usa al menos 8 caracteres."
        elif not any(c.isalpha() for c in password) or not any(c.isdigit() for c in password):
            errores["admin_password"] = "Combina letras y números."
        elif password != confirmacion:
            errores["admin_password_confirmar"] = "Las contraseñas no coinciden."

        if not errores:
            try:
                with tx() as cur:
                    cur.execute(
                        """INSERT INTO empresas
                            (nombre, slug, rfc, correo, telefono, direccion, activa)
                           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                        (
                            datos["nombre"],
                            datos["slug"],
                            datos["rfc"] or None,
                            datos["correo"] or None,
                            datos["telefono"] or None,
                            datos["direccion"] or None,
                            1,
                        ),
                    )
                    empresa_id = cur.lastrowid
                    cur.execute(
                        """INSERT INTO licencias
                            (empresa_id, clave, plan, estado, max_usuarios,
                             max_productos, inicio, vence, notas)
                           VALUES (%s, %s, %s, %s, %s, %s, CURDATE(), %s, %s)""",
                        (
                            empresa_id,
                            clave_licencia(licencia["plan"]),
                            licencia["plan"],
                            licencia["estado"],
                            max_usuarios,
                            max_productos,
                            vence,
                            licencia["notas"] or None,
                        ),
                    )
                    cur.execute(
                        """INSERT INTO usuarios
                            (empresa_id, nombre, email, password_hash, rol, activo)
                           VALUES (%s, %s, %s, %s, 'admin', 1)""",
                        (
                            empresa_id,
                            admin["admin_nombre"],
                            admin["admin_email"],
                            generate_password_hash(password),
                        ),
                    )
                flash(
                    "Empresa «%s» creada con su licencia y administrador." % datos["nombre"],
                    "success",
                )
                return redirect(url_for("empresas.index"))
            except IntegrityError:
                errores["nombre"] = "El identificador o el correo ya están en uso."

    return render_template(
        "empresas/form.html",
        modo="nueva",
        empresa=None,
        datos=datos,
        licencia=licencia,
        admin=admin,
        errores=errores,
        planes=PLANES,
        estados=ESTADOS_LICENCIA,
    )


@bp.route("/<int:empresa_id>/editar", methods=["GET", "POST"])
@login_required
@role_required("superadmin")
def editar(empresa_id):
    empresa = query_one("SELECT * FROM empresas WHERE id = %s", (empresa_id,))
    if not empresa:
        abort(404, description="La empresa no existe.")

    datos = {
        "nombre": empresa["nombre"],
        "slug": empresa["slug"],
        "rfc": empresa["rfc"] or "",
        "correo": empresa["correo"] or "",
        "telefono": empresa["telefono"] or "",
        "direccion": empresa["direccion"] or "",
        "activa": empresa["activa"],
    }
    errores = {}

    if request.method == "POST":
        datos, errores = _validar_empresa(request.form, empresa_id)
        if not errores:
            try:
                execute(
                    """UPDATE empresas
                          SET nombre = %s, slug = %s, rfc = %s, correo = %s,
                              telefono = %s, direccion = %s, activa = %s
                        WHERE id = %s""",
                    (
                        datos["nombre"],
                        datos["slug"],
                        datos["rfc"] or None,
                        datos["correo"] or None,
                        datos["telefono"] or None,
                        datos["direccion"] or None,
                        datos["activa"],
                        empresa_id,
                    ),
                )
                flash("Empresa actualizada.", "success")
                return redirect(url_for("empresas.index"))
            except IntegrityError:
                errores["slug"] = "Ese identificador ya está en uso."

    licencia = query_one("SELECT * FROM licencias WHERE empresa_id = %s", (empresa_id,))
    return render_template(
        "empresas/form.html",
        modo="editar",
        empresa=empresa,
        datos=datos,
        licencia=licencia,
        admin=None,
        errores=errores,
        planes=PLANES,
        estados=ESTADOS_LICENCIA,
    )


@bp.post("/<int:empresa_id>/estado")
@login_required
@role_required("superadmin")
def cambiar_estado(empresa_id):
    empresa = query_one("SELECT id, nombre, activa FROM empresas WHERE id = %s", (empresa_id,))
    if not empresa:
        abort(404)
    nuevo = 0 if empresa["activa"] else 1
    execute("UPDATE empresas SET activa = %s WHERE id = %s", (nuevo, empresa_id))
    flash(
        "Empresa «%s» %s." % (
            empresa["nombre"],
            "activada" if nuevo else "desactivada",
        ),
        "success",
    )
    return redirect(url_for("empresas.index"))


@bp.post("/contexto")
@login_required
@role_required("superadmin")
def contexto():
    valor = (request.form.get("empresa_id") or "").strip()
    if valor in ("", "0"):
        session["empresa_id"] = None
        flash("Contexto global: sin empresa activa.", "info")
    else:
        try:
            empresa_id = int(valor)
        except ValueError:
            empresa_id = None
        empresa = (
            query_one("SELECT id, nombre FROM empresas WHERE id = %s", (empresa_id,))
            if empresa_id
            else None
        )
        if not empresa:
            abort(400, description="La empresa seleccionada no existe.")
        session["empresa_id"] = empresa["id"]
        flash("Ahora trabajas en «%s»." % empresa["nombre"], "success")

    volver = request.form.get("volver") or ""
    if not volver.startswith("/") or volver.startswith("//"):
        volver = url_for("dashboard.index")
    return redirect(volver)
