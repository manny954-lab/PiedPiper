"""Licencias: administración global y vista de la empresa."""
from datetime import date, timedelta

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from db import execute, query_all, query_one
from security import login_required, role_required
from utils import PLANES, fecha_iso, limpiar

bp = Blueprint("licencias", __name__, url_prefix="/licencias")

ESTADOS = ("activa", "prueba", "suspendida", "vencida")


def _listado():
    licencias = query_all(
        """
        SELECT l.*, e.nombre AS empresa, e.activa AS empresa_activa,
               (SELECT COUNT(*) FROM usuarios u
                 WHERE u.empresa_id = l.empresa_id AND u.activo = 1) AS usuarios,
               (SELECT COUNT(*) FROM productos p
                 WHERE p.empresa_id = l.empresa_id) AS productos
          FROM licencias l
          JOIN empresas e ON e.id = l.empresa_id
         ORDER BY FIELD(l.estado, 'vencida', 'suspendida', 'prueba', 'activa'), l.vence ASC
        """
    )
    for lic in licencias:
        lic["dias"] = (lic["vence"] - date.today()).days if lic["vence"] else None
    return licencias


@bp.get("")
@login_required
@role_required("superadmin")
def index():
    licencias = _listado()
    resumen = {
        "total": len(licencias),
        "activas": sum(1 for l in licencias if l["estado"] == "activa"),
        "por_vencer": sum(
            1 for l in licencias
            if l["dias"] is not None and 0 <= l["dias"] <= 30 and l["estado"] in ("activa", "prueba")
        ),
        "vencidas": sum(1 for l in licencias if l["dias"] is not None and l["dias"] < 0),
    }
    return render_template("licencias/index.html", licencias=licencias, resumen=resumen)


@bp.get("/mi-licencia")
@login_required
def mi_licencia():
    if g.user["rol"] == "superadmin":
        return redirect(url_for("licencias.index"))

    plan = PLANES.get(g.licencia["plan"]) if g.licencia else None
    return render_template(
        "licencias/mi_licencia.html",
        licencia=g.licencia,
        plan=plan,
        dias=g.licencia_dias,
        ok=g.licencia_ok,
        motivo=g.licencia_motivo,
    )


def _formulario(form, licencia):
    datos = {
        "plan": form.get("plan", licencia["plan"]),
        "estado": form.get("estado", licencia["estado"]),
        "inicio": limpiar(form.get("inicio"), 10),
        "vence": limpiar(form.get("vence"), 10),
        "max_usuarios": limpiar(form.get("max_usuarios"), 8),
        "max_productos": limpiar(form.get("max_productos"), 10),
        "notas": limpiar(form.get("notas"), 255),
    }
    errores = {}

    if datos["plan"] not in PLANES:
        errores["plan"] = "Selecciona un plan válido."
    if datos["estado"] not in ESTADOS:
        errores["estado"] = "Selecciona un estado válido."

    inicio = fecha_iso(datos["inicio"])
    vence = fecha_iso(datos["vence"])
    if not inicio:
        errores["inicio"] = "Indica la fecha de inicio."
    if not vence:
        errores["vence"] = "Indica la fecha de vencimiento."
    if inicio and vence and vence < inicio:
        errores["vence"] = "El vencimiento no puede ser anterior al inicio."

    try:
        max_usuarios = int(datos["max_usuarios"])
        if max_usuarios < 1:
            raise ValueError
        if max_usuarios < int(licencia["usuarios"]):
            errores["max_usuarios"] = (
                "La empresa ya tiene %s usuarios activos." % licencia["usuarios"]
            )
    except (TypeError, ValueError):
        errores["max_usuarios"] = "Indica un límite válido."

    try:
        max_productos = int(datos["max_productos"])
        if max_productos < 1:
            raise ValueError
        if max_productos < int(licencia["productos"]):
            errores["max_productos"] = (
                "La empresa ya tiene %s productos registrados." % licencia["productos"]
            )
    except (TypeError, ValueError):
        errores["max_productos"] = "Indica un límite válido."

    return datos, errores, inicio, vence


@bp.route("/<int:licencia_id>/editar", methods=["GET", "POST"])
@login_required
@role_required("superadmin")
def editar(licencia_id):
    licencia = query_one(
        """
        SELECT l.*, e.nombre AS empresa,
               (SELECT COUNT(*) FROM usuarios u
                 WHERE u.empresa_id = l.empresa_id AND u.activo = 1) AS usuarios,
               (SELECT COUNT(*) FROM productos p
                 WHERE p.empresa_id = l.empresa_id) AS productos
          FROM licencias l
          JOIN empresas e ON e.id = l.empresa_id
         WHERE l.id = %s
        """,
        (licencia_id,),
    )
    if not licencia:
        abort(404, description="La licencia no existe.")

    datos = {
        "plan": licencia["plan"],
        "estado": licencia["estado"],
        "inicio": licencia["inicio"].isoformat(),
        "vence": licencia["vence"].isoformat(),
        "max_usuarios": str(licencia["max_usuarios"]),
        "max_productos": str(licencia["max_productos"]),
        "notas": licencia["notas"] or "",
    }
    errores = {}

    if request.method == "POST":
        datos, errores, inicio, vence = _formulario(request.form, licencia)
        if not errores:
            execute(
                """UPDATE licencias
                      SET plan = %s, estado = %s, inicio = %s, vence = %s,
                          max_usuarios = %s, max_productos = %s, notas = %s
                    WHERE id = %s""",
                (
                    datos["plan"],
                    datos["estado"],
                    inicio,
                    vence,
                    int(datos["max_usuarios"]),
                    int(datos["max_productos"]),
                    datos["notas"] or None,
                    licencia_id,
                ),
            )
            flash("Licencia actualizada.", "success")
            return redirect(url_for("licencias.index"))

    return render_template(
        "licencias/form.html",
        licencia=licencia,
        datos=datos,
        errores=errores,
        planes=PLANES,
        estados=ESTADOS,
        dias=(licencia["vence"] - date.today()).days,
    )


@bp.post("/<int:licencia_id>/renovar")
@login_required
@role_required("superadmin")
def renovar(licencia_id):
    licencia = query_one(
        "SELECT id, empresa_id, vence, estado FROM licencias WHERE id = %s",
        (licencia_id,),
    )
    if not licencia:
        abort(404)
    base = max(date.today(), licencia["vence"])
    nuevo_vence = base + timedelta(days=365)
    execute(
        "UPDATE licencias SET vence = %s, estado = 'activa' WHERE id = %s",
        (nuevo_vence, licencia_id),
    )
    flash(
        "Licencia renovada por 12 meses. Nuevo vencimiento: %s."
        % nuevo_vence.strftime("%d/%m/%Y"),
        "success",
    )
    return redirect(url_for("licencias.index"))
