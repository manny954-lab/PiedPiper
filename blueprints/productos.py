"""CRUD de productos con aislamiento por empresa."""
from pymysql.err import IntegrityError

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from db import execute, query_all, query_one, tx
from security import empresa_requerida, login_required, role_required
from utils import decimal, entero, limpiar, paginar

bp = Blueprint("productos", __name__, url_prefix="/productos")

POR_PAGINA = 12

ORDENES = {
    "nombre": "p.nombre ASC",
    "-nombre": "p.nombre DESC",
    "sku": "p.sku ASC",
    "-sku": "p.sku DESC",
    "stock": "p.stock ASC",
    "-stock": "p.stock DESC",
    "precio": "p.precio_venta ASC",
    "-precio": "p.precio_venta DESC",
    "actualizado": "p.actualizado_en DESC",
}

ESTADOS = ("todos", "activo", "inactivo", "bajo", "agotado")


def _categorias():
    return query_all(
        """SELECT id, nombre, activo FROM categorias
            WHERE empresa_id = %s ORDER BY nombre""",
        (g.empresa_id,),
    )


@bp.get("")
@login_required
@empresa_requerida
def index():
    q = limpiar(request.args.get("q"), 80)
    categoria = entero(request.args.get("categoria"), None, minimo=1)
    estado = request.args.get("estado", "todos")
    if estado not in ESTADOS:
        estado = "todos"
    orden = request.args.get("orden", "nombre")
    if orden not in ORDENES:
        orden = "nombre"
    pagina = entero(request.args.get("page"), 1, minimo=1) or 1

    where = ["p.empresa_id = %s"]
    params = [g.empresa_id]

    if q:
        like = "%" + q + "%"
        where.append("(p.nombre LIKE %s OR p.sku LIKE %s OR p.descripcion LIKE %s)")
        params.extend([like, like, like])
    if categoria:
        where.append("p.categoria_id = %s")
        params.append(categoria)
    if estado == "activo":
        where.append("p.activo = 1")
    elif estado == "inactivo":
        where.append("p.activo = 0")
    elif estado == "bajo":
        where.append("p.activo = 1 AND p.stock <= p.stock_minimo AND p.stock > 0")
    elif estado == "agotado":
        where.append("p.activo = 1 AND p.stock = 0")

    where_sql = " AND ".join(where)

    resumen = query_one(
        """SELECT COUNT(*) AS total,
                  COALESCE(SUM(p.stock), 0) AS unidades,
                  COALESCE(SUM(p.stock * p.precio_compra), 0) AS valor
             FROM productos p
            WHERE """
        + where_sql,
        tuple(params),
    )

    pag = paginar(resumen["total"], pagina, POR_PAGINA)

    productos = query_all(
        """SELECT p.*, COALESCE(c.nombre, 'Sin categoría') AS categoria
             FROM productos p
             LEFT JOIN categorias c ON c.id = p.categoria_id
            WHERE """
        + where_sql
        + " ORDER BY "
        + ORDENES[orden]
        + " LIMIT %s OFFSET %s",
        tuple(params) + (POR_PAGINA, pag["offset"]),
    )

    return render_template(
        "productos/index.html",
        productos=productos,
        categorias=_categorias(),
        resumen=resumen,
        pag=pag,
        q=q,
        categoria=categoria,
        estado=estado,
        orden=orden,
        estados=ESTADOS,
    )


def _formulario(form, es_nuevo):
    datos = {
        "nombre": limpiar(form.get("nombre"), 140),
        "sku": limpiar(form.get("sku"), 40).upper(),
        "categoria_id": limpiar(form.get("categoria_id")),
        "unidad": limpiar(form.get("unidad"), 20) or "pza",
        "ubicacion": limpiar(form.get("ubicacion"), 60),
        "descripcion": limpiar(form.get("descripcion"), 300),
        "precio_compra": limpiar(form.get("precio_compra"), 20),
        "precio_venta": limpiar(form.get("precio_venta"), 20),
        "stock": limpiar(form.get("stock"), 20) if es_nuevo else "0",
        "stock_minimo": limpiar(form.get("stock_minimo"), 20),
        "activo": 1 if form.get("activo") else 0,
    }
    errores = {}
    limpio = {}

    if not datos["nombre"]:
        errores["nombre"] = "El nombre del producto es obligatorio."
    if len(datos["nombre"]) > 140:
        errores["nombre"] = "Máximo 140 caracteres."

    if not datos["sku"]:
        errores["sku"] = "El SKU o código es obligatorio."

    categoria_id = None
    if datos["categoria_id"]:
        categoria_id = entero(datos["categoria_id"], None, minimo=1)
        if not categoria_id:
            errores["categoria_id"] = "Selecciona una categoría válida."
        else:
            existe = query_one(
                "SELECT id FROM categorias WHERE id = %s AND empresa_id = %s",
                (categoria_id, g.empresa_id),
            )
            if not existe:
                errores["categoria_id"] = "La categoría no pertenece a esta empresa."

    precio_compra = decimal(datos["precio_compra"])
    if precio_compra is None:
        errores["precio_compra"] = "Indica un precio de compra válido."
    precio_venta = decimal(datos["precio_venta"])
    if precio_venta is None:
        errores["precio_venta"] = "Indica un precio de venta válido."

    stock = entero(datos["stock"], 0, minimo=0, maximo=100000000)
    if stock is None:
        errores["stock"] = "El stock debe ser un entero positivo."
    stock_minimo = entero(datos["stock_minimo"], 0, minimo=0, maximo=100000000)
    if stock_minimo is None:
        errores["stock_minimo"] = "El stock mínimo debe ser un entero positivo."

    if not datos["unidad"]:
        errores["unidad"] = "Indica la unidad de medida."

    if not errores:
        limpio = {
            "nombre": datos["nombre"],
            "sku": datos["sku"],
            "categoria_id": categoria_id,
            "unidad": datos["unidad"],
            "ubicacion": datos["ubicacion"],
            "descripcion": datos["descripcion"],
            "precio_compra": precio_compra,
            "precio_venta": precio_venta,
            "stock": stock or 0,
            "stock_minimo": stock_minimo or 0,
            "activo": datos["activo"],
        }

    return datos, errores, limpio


def _sku_duplicado(sku, producto_id=None):
    if producto_id:
        return query_one(
            "SELECT id FROM productos WHERE empresa_id = %s AND sku = %s AND id <> %s",
            (g.empresa_id, sku, producto_id),
        )
    return query_one(
        "SELECT id FROM productos WHERE empresa_id = %s AND sku = %s",
        (g.empresa_id, sku),
    )


@bp.route("/nuevo", methods=["GET", "POST"])
@login_required
@empresa_requerida
@role_required("admin", "superadmin")
def nuevo():
    if g.licencia and int(g.licencia["productos_usados"]) >= int(g.licencia["max_productos"]):
        flash(
            "Alcanzaste el límite de %s productos de tu licencia."
            % g.licencia["max_productos"],
            "warning",
        )
        return redirect(url_for("productos.index"))

    errores = {}
    datos = {
        "nombre": "",
        "sku": "",
        "categoria_id": "",
        "unidad": "pza",
        "ubicacion": "",
        "descripcion": "",
        "precio_compra": "0.00",
        "precio_venta": "0.00",
        "stock": "0",
        "stock_minimo": "0",
        "activo": 1,
    }

    if request.method == "POST":
        datos, errores, limpio = _formulario(request.form, es_nuevo=True)
        if not errores and _sku_duplicado(datos["sku"]):
            errores["sku"] = "Ya existe un producto con este SKU."

        if not errores:
            try:
                with tx() as cur:
                    cur.execute(
                        """
                        INSERT INTO productos
                            (empresa_id, categoria_id, sku, nombre, descripcion,
                             unidad, ubicacion, precio_compra, precio_venta,
                             stock, stock_minimo, activo)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            g.empresa_id,
                            limpio["categoria_id"],
                            limpio["sku"],
                            limpio["nombre"],
                            limpio["descripcion"],
                            limpio["unidad"],
                            limpio["ubicacion"],
                            limpio["precio_compra"],
                            limpio["precio_venta"],
                            limpio["stock"],
                            limpio["stock_minimo"],
                            limpio["activo"],
                        ),
                    )
                    producto_id = cur.lastrowid
                    if limpio["stock"] > 0:
                        cur.execute(
                            """
                            INSERT INTO movimientos
                                (empresa_id, producto_id, usuario_id, tipo, cantidad,
                                 stock_anterior, stock_resultante, motivo, referencia)
                            VALUES (%s, %s, %s, 'entrada', %s, 0, %s, %s, %s)
                            """,
                            (
                                g.empresa_id,
                                producto_id,
                                g.user["id"],
                                limpio["stock"],
                                limpio["stock"],
                                "Carga inicial de inventario",
                                "ALTA",
                            ),
                        )
                flash("Producto «%s» creado correctamente." % limpio["nombre"], "success")
                return redirect(url_for("productos.index"))
            except IntegrityError:
                errores["sku"] = "El SKU ya existe en esta empresa."

    return render_template(
        "productos/form.html",
        modo="nuevo",
        producto=None,
        datos=datos,
        errores=errores,
        categorias=_categorias(),
    )


@bp.route("/<int:producto_id>/editar", methods=["GET", "POST"])
@login_required
@empresa_requerida
@role_required("admin", "superadmin")
def editar(producto_id):
    producto = query_one(
        "SELECT * FROM productos WHERE id = %s AND empresa_id = %s",
        (producto_id, g.empresa_id),
    )
    if not producto:
        abort(404, description="El producto no existe en esta empresa.")

    errores = {}

    if request.method == "POST":
        datos, errores, limpio = _formulario(request.form, es_nuevo=False)
        if not errores and _sku_duplicado(datos["sku"], producto_id):
            errores["sku"] = "Ya existe otro producto con este SKU."

        if not errores:
            try:
                execute(
                    """
                    UPDATE productos
                       SET categoria_id = %s, sku = %s, nombre = %s, descripcion = %s,
                           unidad = %s, ubicacion = %s, precio_compra = %s,
                           precio_venta = %s, stock_minimo = %s, activo = %s,
                           actualizado_en = NOW()
                     WHERE id = %s AND empresa_id = %s
                    """,
                    (
                        limpio["categoria_id"],
                        limpio["sku"],
                        limpio["nombre"],
                        limpio["descripcion"],
                        limpio["unidad"],
                        limpio["ubicacion"],
                        limpio["precio_compra"],
                        limpio["precio_venta"],
                        limpio["stock_minimo"],
                        limpio["activo"],
                        producto_id,
                        g.empresa_id,
                    ),
                )
                flash("Producto actualizado.", "success")
                return redirect(url_for("productos.index"))
            except IntegrityError:
                errores["sku"] = "El SKU ya existe en esta empresa."
    else:
        datos = {
            "nombre": producto["nombre"],
            "sku": producto["sku"],
            "categoria_id": str(producto["categoria_id"] or ""),
            "unidad": producto["unidad"],
            "ubicacion": producto["ubicacion"] or "",
            "descripcion": producto["descripcion"] or "",
            "precio_compra": "%.2f" % producto["precio_compra"],
            "precio_venta": "%.2f" % producto["precio_venta"],
            "stock": str(producto["stock"]),
            "stock_minimo": str(producto["stock_minimo"]),
            "activo": producto["activo"],
        }

    return render_template(
        "productos/form.html",
        modo="editar",
        producto=producto,
        datos=datos,
        errores=errores,
        categorias=_categorias(),
    )


@bp.post("/<int:producto_id>/estado")
@login_required
@empresa_requerida
@role_required("admin", "superadmin")
def cambiar_estado(producto_id):
    producto = query_one(
        "SELECT id, nombre, activo FROM productos WHERE id = %s AND empresa_id = %s",
        (producto_id, g.empresa_id),
    )
    if not producto:
        abort(404)

    nuevo_estado = 0 if producto["activo"] else 1
    if nuevo_estado and g.licencia:
        if int(g.licencia["productos_usados"]) >= int(g.licencia["max_productos"]):
            flash("La licencia no permite reactivar más productos.", "warning")
            return redirect(url_for("productos.index"))

    execute(
        "UPDATE productos SET activo = %s, actualizado_en = NOW() WHERE id = %s AND empresa_id = %s",
        (nuevo_estado, producto_id, g.empresa_id),
    )
    flash(
        "Producto «%s» %s." % (
            producto["nombre"],
            "reactivado" if nuevo_estado else "desactivado",
        ),
        "success",
    )
    volver = request.form.get("volver") or ""
    if not volver.startswith("/") or volver.startswith("//"):
        volver = url_for("productos.index")
    return redirect(volver)
