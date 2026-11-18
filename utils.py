"""Utilidades compartidas: validación, paginación y catálogo de planes."""
import re
import secrets
import unicodedata
from datetime import date, datetime
from decimal import Decimal, InvalidOperation


PLANES = {
    "basico": {
        "nombre": "Básico",
        "usuarios": 3,
        "productos": 500,
        "precio": "$299 MXN / mes",
        "precio_mes": 299,
        "descripcion": "Para negocios que están ordenando su inventario.",
        "features": [
            "Catálogo de productos y categorías",
            "Movimientos de entrada, salida y ajuste",
            "Dashboard operativo",
            "3 usuarios incluidos",
        ],
    },
    "profesional": {
        "nombre": "Profesional",
        "usuarios": 10,
        "productos": 2000,
        "precio": "$699 MXN / mes",
        "precio_mes": 699,
        "descripcion": "Para operaciones con varios responsables y sucursales.",
        "features": [
            "Todo lo del plan Básico",
            "Hasta 10 usuarios con roles",
            "Alertas de stock mínimo",
            "Historial completo de movimientos",
        ],
    },
    "empresarial": {
        "nombre": "Empresarial",
        "usuarios": 50,
        "productos": 20000,
        "precio": "$1,490 MXN / mes",
        "precio_mes": 1490,
        "descripcion": "Para empresas con catálogos y equipos grandes.",
        "features": [
            "Todo lo del plan Profesional",
            "Hasta 50 usuarios",
            "Catálogos de gran volumen",
            "Atención prioritaria",
        ],
    },
}


def limpiar(valor, maxlen=None):
    if valor is None:
        return ""
    texto = str(valor).strip()
    if maxlen is not None:
        texto = texto[:maxlen]
    return texto


def entero(valor, defecto=0, minimo=None, maximo=None):
    """Devuelve int o None si el valor no es un entero válido."""
    texto = limpiar(valor)
    if texto == "":
        return defecto
    try:
        numero = int(texto)
    except (TypeError, ValueError):
        return None
    if minimo is not None and numero < minimo:
        return None
    if maximo is not None and numero > maximo:
        return None
    return numero


def decimal(valor, defecto=Decimal("0.00")):
    """Devuelve Decimal con 2 posiciones o None si no es válido."""
    texto = limpiar(valor).replace(" ", "").replace(",", "")
    if texto == "":
        return defecto
    try:
        numero = Decimal(texto)
    except (InvalidOperation, TypeError, ValueError):
        return None
    if numero < 0:
        return None
    return numero.quantize(Decimal("0.01"))


def fecha_iso(valor):
    """Convierte YYYY-MM-DD a date. Devuelve None si no es válida."""
    texto = limpiar(valor)
    if not texto:
        return None
    try:
        return datetime.strptime(texto, "%Y-%m-%d").date()
    except ValueError:
        return None


def dias_para(fecha):
    if not fecha:
        return None
    return (fecha - date.today()).days


def slugify(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", limpiar(texto))
    texto = texto.encode("ascii", "ignore").decode("ascii").lower()
    texto = re.sub(r"[^a-z0-9]+", "-", texto).strip("-")
    return texto[:60] or "empresa"


def clave_licencia(plan: str) -> str:
    prefijo = {"basico": "BAS", "profesional": "PRO", "empresarial": "EMP"}.get(
        plan, "LIC"
    )
    anio = date.today().year
    return "PP-%s-%s-%s" % (prefijo, secrets.token_hex(2).upper(), anio)


def paginar(total: int, pagina: int, por_pagina: int):
    total = int(total or 0)
    paginas = max(1, (total + por_pagina - 1) // por_pagina)
    pagina = min(max(1, int(pagina or 1)), paginas)
    desde = (pagina - 1) * por_pagina
    return {
        "total": total,
        "pagina": pagina,
        "paginas": paginas,
        "por_pagina": por_pagina,
        "offset": desde,
        "desde_num": desde + 1 if total else 0,
        "hasta_num": min(desde + por_pagina, total),
        "hay_anterior": pagina > 1,
        "hay_siguiente": pagina < paginas,
    }
