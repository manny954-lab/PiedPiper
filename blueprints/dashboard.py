"""Dashboard operativo."""
from datetime import date, timedelta

from flask import Blueprint, g, render_template

from db import query_all, query_one
from security import login_required

bp = Blueprint("dashboard", __name__)

DIAS_CORTOS = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]


@bp.get("/")
@login_required
def index():
    if not g.empresa_id:
        return render_template("dashboard/index.html", sin_empresa=True)

    eid = g.empresa_id

    kpis = query_one(
        """
        SELECT COUNT(*) AS productos,
               COALESCE(SUM(activo), 0) AS activos,
               COALESCE(SUM(CASE WHEN activo = 1 THEN stock ELSE 0 END), 0) AS unidades,
               COALESCE(SUM(CASE WHEN activo = 1 THEN stock * precio_compra ELSE 0 END), 0) AS valor,
               COALESCE(SUM(CASE WHEN activo = 1 AND stock <= stock_minimo THEN 1 ELSE 0 END), 0) AS bajos,
               COALESCE(SUM(CASE WHEN activo = 1 AND stock = 0 THEN 1 ELSE 0 END), 0) AS agotados
          FROM productos
         WHERE empresa_id = %s
        """,
        (eid,),
    )

    mov_hoy = query_one(
        "SELECT COUNT(*) AS n FROM movimientos WHERE empresa_id = %s AND DATE(creado_en) = CURDATE()",
        (eid,),
    )["n"]

    inicio = date.today() - timedelta(days=6)
    filas = query_all(
        """
        SELECT DATE(creado_en) AS dia,
               COALESCE(SUM(CASE WHEN tipo = 'entrada' THEN cantidad ELSE 0 END), 0) AS entradas,
               COALESCE(SUM(CASE WHEN tipo = 'salida' THEN cantidad ELSE 0 END), 0) AS salidas
          FROM movimientos
         WHERE empresa_id = %s AND creado_en >= %s AND tipo IN ('entrada', 'salida')
         GROUP BY DATE(creado_en)
        """,
        (eid, inicio),
    )
    por_dia = {f["dia"]: f for f in filas}

    serie = []
    maximo = 1
    for fila in filas:
        maximo = max(maximo, int(fila["entradas"] or 0), int(fila["salidas"] or 0))
    for i in range(7):
        dia = inicio + timedelta(days=i)
        datos = por_dia.get(dia, {"entradas": 0, "salidas": 0})
        entradas = int(datos["entradas"] or 0)
        salidas = int(datos["salidas"] or 0)
        serie.append(
            {
                "etiqueta": "%s %s" % (DIAS_CORTOS[dia.weekday()], dia.day),
                "entradas": entradas,
                "salidas": salidas,
                "h_entrada": round(entradas * 100 / maximo, 1),
                "h_salida": round(salidas * 100 / maximo, 1),
                "hoy": dia == date.today(),
            }
        )

    categorias = query_all(
        """
        SELECT COALESCE(c.nombre, 'Sin categoría') AS nombre,
               COALESCE(SUM(p.stock), 0) AS unidades,
               COUNT(p.id) AS productos
          FROM productos p
          LEFT JOIN categorias c ON c.id = p.categoria_id
         WHERE p.empresa_id = %s AND p.activo = 1
         GROUP BY c.id, c.nombre
         ORDER BY unidades DESC
         LIMIT 5
        """,
        (eid,),
    )
    max_cat = max([int(c["unidades"] or 0) for c in categorias] + [1])
    for c in categorias:
        c["ancho"] = round(int(c["unidades"] or 0) * 100 / max_cat, 1)

    bajos = query_all(
        """
        SELECT p.id, p.nombre, p.sku, p.stock, p.stock_minimo, p.unidad,
               COALESCE(c.nombre, 'Sin categoría') AS categoria
          FROM productos p
          LEFT JOIN categorias c ON c.id = p.categoria_id
         WHERE p.empresa_id = %s AND p.activo = 1 AND p.stock <= p.stock_minimo
         ORDER BY (p.stock - p.stock_minimo) ASC, p.stock ASC
         LIMIT 6
        """,
        (eid,),
    )
    for p in bajos:
        minimo = int(p["stock_minimo"] or 0)
        referencia = max(minimo * 2, 1)
        p["llenado"] = min(100, round(int(p["stock"] or 0) * 100 / referencia, 1))

    recientes = query_all(
        """
        SELECT m.*, p.nombre AS producto, p.sku, COALESCE(u.nombre, 'Sistema') AS usuario
          FROM movimientos m
          JOIN productos p ON p.id = m.producto_id
          LEFT JOIN usuarios u ON u.id = m.usuario_id
         WHERE m.empresa_id = %s
         ORDER BY m.creado_en DESC, m.id DESC
         LIMIT 8
        """,
        (eid,),
    )

    return render_template(
        "dashboard/index.html",
        sin_empresa=False,
        kpis=kpis,
        mov_hoy=mov_hoy,
        serie=serie,
        categorias=categorias,
        bajos=bajos,
        recientes=recientes,
    )
