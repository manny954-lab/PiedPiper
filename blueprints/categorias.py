"""CRUD de categorías por empresa."""
from pymysql.err import IntegrityError

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from db import execute, query_all, query_one
from security import empresa_requerida, login_required, role_required
from utils import limpiar

bp = Blueprint("categorias", __name__, url_prefix="/categorias")


def _listado():
    return query_all(
        """
        SELECT c.id, c.nombre, c.descripcion, c.activo, c.creada_en,
               COUNT(p.id) AS productos,
               COALESCE(SUM(p.stock), 0) AS unidades
          FROM categorias c
          LEFT JOIN productos p
                 ON p.categoria_id = c.id AND p.empresa_id = c.empresa_id
         WHERE c.empresa_id = %s
         GROUP BY c.id, c.nombre, c.descripcion, c.activo, c.creada_en
         ORDER BY c.nombre
        """,
        (g.empresa_id,),
    )


@bp.get("")
@login_required
@empresa_requerida
def index():
    categorias = _listado()
    resumen = {
        "total": len(categorias),
        "activas": sum(1 for c in categorias if c["activo"]),
        "productos": sum(int(c["productos"]) for c in categorias),
        "unidades": sum(int(c["unidades"]) for c in categorias),
    }
    return render_template("categorias/index.html", categorias=categorias, resumen=resumen)


def _formulario(form, categoria_id=None):
    datos = {
        "nombre": limpiar(form.get("nombre"), 80),
        "descripcion": limpiar(form.get("descripcion"), 200),
        "activo": 1 if form.get("activo") else 0,
    }
    errores = {}

    if not datos["nombre"]:
        errores["nombre"] = "El nombre de la categoría es obligatorio."

    if not errores:
        if categoria_id:
            duplicada = query_one(
                """SELECT id FROM categorias
                    WHERE empresa_id = %s AND nombre = %s AND id <> %s""",
                (g.empresa_id, datos["nombre"], categoria_id),
            )
        else:
            duplicada = query_one(
                "SELECT id FROM categorias WHERE empresa_id = %s AND nombre = %s",
                (g.empresa_id, datos["nombre"]),
            )
        if duplicada:
            errores["nombre"] = "Ya existe una categoría con ese nombre."

    return datos, errores


@bp.route("/nueva", methods=["GET", "POST"])
@login_required
@empresa_requerida
@role_required("admin", "superadmin")
def nueva():
    datos = {"nombre": "", "descripcion": "", "activo": 1}
    errores = {}

    if request.method == "POST":
        datos, errores = _formulario(request.form)
        if not errores:
            try:
                execute(
                    """INSERT INTO categorias (empresa_id, nombre, descripcion, activo)
                       VALUES (%s, %s, %s, %s)""",
                    (g.empresa_id, datos["nombre"], datos["descripcion"], datos["activo"]),
                )
                flash("Categoría «%s» creada." % datos["nombre"], "success")
                return redirect(url_for("categorias.index"))
            except IntegrityError:
                errores["nombre"] = "Ya existe una categoría con ese nombre."

    return render_template(
        "categorias/form.html", modo="nueva", categoria=None, datos=datos, errores=errores
    )


@bp.route("/<int:categoria_id>/editar", methods=["GET", "POST"])
@login_required
@empresa_requerida
@role_required("admin", "superadmin")
def editar(categoria_id):
    categoria = query_one(
        "SELECT * FROM categorias WHERE id = %s AND empresa_id = %s",
        (categoria_id, g.empresa_id),
    )
    if not categoria:
        abort(404, description="La categoría no existe en esta empresa.")

    if request.method == "POST":
        datos, errores = _formulario(request.form, categoria_id)
        if not errores:
            try:
                execute(
                    """UPDATE categorias
                          SET nombre = %s, descripcion = %s, activo = %s
                        WHERE id = %s AND empresa_id = %s""",
                    (
                        datos["nombre"],
                        datos["descripcion"],
                        datos["activo"],
                        categoria_id,
                        g.empresa_id,
                    ),
                )
                flash("Categoría actualizada.", "success")
                return redirect(url_for("categorias.index"))
            except IntegrityError:
                errores["nombre"] = "Ya existe una categoría con ese nombre."
    else:
        datos = {
            "nombre": categoria["nombre"],
            "descripcion": categoria["descripcion"] or "",
            "activo": categoria["activo"],
        }

    return render_template(
        "categorias/form.html",
        modo="editar",
        categoria=categoria,
        datos=datos,
        errores=errores,
    )


@bp.post("/<int:categoria_id>/eliminar")
@login_required
@empresa_requerida
@role_required("admin", "superadmin")
def eliminar(categoria_id):
    categoria = query_one(
        "SELECT id, nombre FROM categorias WHERE id = %s AND empresa_id = %s",
        (categoria_id, g.empresa_id),
    )
    if not categoria:
        abort(404)

    asociados = query_one(
        "SELECT COUNT(*) AS n FROM productos WHERE categoria_id = %s AND empresa_id = %s",
        (categoria_id, g.empresa_id),
    )["n"]
    if asociados:
        flash(
            "No se puede eliminar «%s»: tiene %s productos asociados. "
            "Reasígnalos o desactiva la categoría." % (categoria["nombre"], asociados),
            "warning",
        )
        return redirect(url_for("categorias.index"))

    execute(
        "DELETE FROM categorias WHERE id = %s AND empresa_id = %s",
        (categoria_id, g.empresa_id),
    )
    flash("Categoría eliminada.", "success")
    return redirect(url_for("categorias.index"))
