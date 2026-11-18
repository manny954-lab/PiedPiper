"""Registro y consulta de movimientos de inventario."""
from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from db import query_all, query_one, tx
from security import empresa_requerida, login_required
from utils import entero, fecha_iso, limpiar, paginar

bp = Blueprint("movimientos", __name__, url_prefix="/movimientos")

POR_PAGINA = 15
TIPOS = ("entrada", "salida", "ajuste")


class _StockInsuficiente(Exception):
    def __init__(self, fila):
        self.fila = fila
        super().__init__("stock insuficiente")


def _productos_activos():
    return query_all(
        """SELECT id, nombre, sku, stock, unidad FROM productos
            WHERE empresa_id = %s AND activo = 1 ORDER BY nombre""",
        (g.empresa_id,),
    )


@bp.get("")
@login_required
@empresa_requerida
def index():
    tipo = request.args.get("tipo", "")
    if tipo not in TIPOS:
        tipo = ""
    q = limpiar(request.args.get("q"), 80)
    desde_txt = limpiar(request.args.get("desde"), 10)
    hasta_txt = limpiar(request.args.get("hasta"), 10)
    desde = fecha_iso(desde_txt)
    hasta = fecha_iso(hasta_txt)
    pagina = entero(request.args.get("page"), 1, minimo=1) or 1

    where = ["m.empresa_id = %s"]
    params = [g.empresa_id]

    if tipo:
        where.append("m.tipo = %s")
        params.append(tipo)
    if q:
        like = "%" + q + "%"
        where.append("(p.nombre LIKE %s OR p.sku LIKE %s OR m.referencia LIKE %s OR m.motivo LIKE %s)")
        params.extend([like, like, like, like])
    if desde:
        where.append("m.creado_en >= %s")
        params.append(desde)
    if hasta:
        where.append("m.creado_en < DATE_ADD(%s, INTERVAL 1 DAY)")
        params.append(hasta)

    where_sql = " AND ".join(where)

    resumen = query_one(
        """SELECT COUNT(*) AS total,
                  COALESCE(SUM(CASE WHEN m.tipo = 'entrada' THEN m.cantidad ELSE 0 END), 0) AS entradas,
                  COALESCE(SUM(CASE WHEN m.tipo = 'salida' THEN m.cantidad ELSE 0 END), 0) AS salidas
             FROM movimientos m
             JOIN productos p ON p.id = m.producto_id
            WHERE """
        + where_sql,
        tuple(params),
    )

    pag = paginar(resumen["total"], pagina, POR_PAGINA)

    movimientos = query_all(
        """SELECT m.*, p.nombre AS producto, p.sku, p.unidad,
                  COALESCE(u.nombre, 'Sistema') AS usuario
             FROM movimientos m
             JOIN productos p ON p.id = m.producto_id
             LEFT JOIN usuarios u ON u.id = m.usuario_id
            WHERE """
        + where_sql
        + """ ORDER BY m.creado_en DESC, m.id DESC
              LIMIT %s OFFSET %s""",
        tuple(params) + (POR_PAGINA, pag["offset"]),
    )

    return render_template(
        "movimientos/index.html",
        movimientos=movimientos,
        resumen=resumen,
        pag=pag,
        tipo=tipo,
        tipos=TIPOS,
        q=q,
        desde=desde_txt,
        hasta=hasta_txt,
    )


@bp.route("/nuevo", methods=["GET", "POST"])
@login_required
@empresa_requerida
def nuevo():
    productos = _productos_activos()
    errores = {}
    datos = {
        "tipo": request.args.get("tipo", "entrada"),
        "producto_id": request.args.get("producto", ""),
        "cantidad": "",
        "motivo": "",
        "referencia": "",
    }
    if datos["tipo"] not in TIPOS:
        datos["tipo"] = "entrada"

    if request.method == "POST":
        datos = {
            "tipo": request.form.get("tipo", ""),
            "producto_id": request.form.get("producto_id", ""),
            "cantidad": limpiar(request.form.get("cantidad"), 20),
            "motivo": limpiar(request.form.get("motivo"), 200),
            "referencia": limpiar(request.form.get("referencia"), 80),
        }

        if datos["tipo"] not in TIPOS:
            errores["tipo"] = "Selecciona un tipo de movimiento."
        producto_id = entero(datos["producto_id"], None, minimo=1)
        if not producto_id:
            errores["producto_id"] = "Selecciona un producto."
        cantidad = entero(datos["cantidad"], None, minimo=0, maximo=1000000)
        if cantidad is None:
            errores["cantidad"] = "Indica una cantidad válida."
        elif datos["tipo"] in ("entrada", "salida") and cantidad <= 0:
            errores["cantidad"] = "La cantidad debe ser mayor que cero."
        if datos["tipo"] == "ajuste" and not datos["motivo"]:
            errores["motivo"] = "Explica el motivo del ajuste de inventario."

        producto = None
        if producto_id:
            producto = query_one(
                """SELECT id, nombre, sku, stock, unidad FROM productos
                    WHERE id = %s AND empresa_id = %s""",
                (producto_id, g.empresa_id),
            )
            if not producto:
                errores["producto_id"] = "El producto no pertenece a esta empresa."

        if not errores:
            try:
                with tx() as cur:
                    cur.execute(
                        """SELECT id, nombre, stock, unidad FROM productos
                            WHERE id = %s AND empresa_id = %s AND activo = 1
                            FOR UPDATE""",
                        (producto_id, g.empresa_id),
                    )
                    actual = cur.fetchone()
                    if not actual:
                        errores["producto_id"] = "El producto no está disponible."
                        raise _StockInsuficiente(None)

                    anterior = int(actual["stock"])
                    if datos["tipo"] == "entrada":
                        nuevo_stock = anterior + cantidad
                    elif datos["tipo"] == "salida":
                        if cantidad > anterior:
                            raise _StockInsuficiente(actual)
                        nuevo_stock = anterior - cantidad
                    else:
                        nuevo_stock = cantidad

                    cur.execute(
                        "UPDATE productos SET stock = %s, actualizado_en = NOW() WHERE id = %s AND empresa_id = %s",
                        (nuevo_stock, producto_id, g.empresa_id),
                    )
                    cur.execute(
                        """INSERT INTO movimientos
                            (empresa_id, producto_id, usuario_id, tipo, cantidad,
                             stock_anterior, stock_resultante, motivo, referencia)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                        (
                            g.empresa_id,
                            producto_id,
                            g.user["id"],
                            datos["tipo"],
                            cantidad,
                            anterior,
                            nuevo_stock,
                            datos["motivo"] or None,
                            datos["referencia"] or None,
                        ),
                    )
                flash(
                    "Movimiento registrado. «%s» queda con %s %s."
                    % (producto["nombre"], nuevo_stock, producto["unidad"]),
                    "success",
                )
                return redirect(url_for("movimientos.index"))
            except _StockInsuficiente as exc:
                if exc.fila:
                    errores["cantidad"] = (
                        "Stock insuficiente: solo hay %s %s disponibles."
                        % (exc.fila["stock"], exc.fila["unidad"])
                    )

    return render_template(
        "movimientos/form.html",
        productos=productos,
        datos=datos,
        errores=errores,
        tipos=TIPOS,
    )
