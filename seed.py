#!/usr/bin/env python3
"""Crea la base de datos, aplica ``schema.sql`` y carga datos de demostración.

Ejemplos:
    python seed.py
    python seed.py --fresh --yes
    python seed.py --user root --password mi_clave --no-demo
"""
import argparse
import os
import random
import re
import sys
from datetime import date, datetime, time, timedelta
from pathlib import Path

import pymysql
from dotenv import load_dotenv
from pymysql.cursors import DictCursor
from werkzeug.security import generate_password_hash

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def env(nombre, defecto=""):
    return os.getenv(nombre, defecto)


def argumentos():
    parser = argparse.ArgumentParser(description="Inicializa PiedPiper Inventario")
    parser.add_argument("--host", default=env("DB_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(env("DB_PORT", "3306")))
    parser.add_argument("--user", default=env("DB_USER", "piedpiper"))
    parser.add_argument("--password", default=env("DB_PASSWORD", ""))
    parser.add_argument("--database", default=env("DB_NAME", "piedpiper_erp"))
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Elimina la base de datos antes de crearla (¡borra todo!).",
    )
    parser.add_argument(
        "--yes", action="store_true", help="Confirma --fresh sin preguntar."
    )
    parser.add_argument(
        "--no-demo", action="store_true", help="Crea solo el esquema, sin datos demo."
    )
    return parser.parse_args()


def conectar(args, con_base=True):
    kwargs = dict(
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        charset="utf8mb4",
        cursorclass=DictCursor,
        autocommit=True,
        connect_timeout=8,
    )
    if con_base:
        kwargs["database"] = args.database
    return pymysql.connect(**kwargs)


def aplicar_esquema(conn):
    ruta = BASE_DIR / "schema.sql"
    contenido = ruta.read_text(encoding="utf-8")
    sentencias = [s.strip() for s in contenido.split(";") if s.strip()]
    with conn.cursor() as cur:
        for sentencia in sentencias:
            cur.execute(sentencia)
    print("  Esquema aplicado (%s sentencias)." % len(sentencias))


def insertar(cur, sql, params):
    cur.execute(sql, params)
    return cur.lastrowid


def crear_usuarios(cur, empresas, claves):
    usuarios = [
        (None, "Administrador Global", "admin@piedpiper.software", "PiedPiper2026!", "superadmin"),
        (empresas["demo"], "Mariana Ortega", "admin@demo.mx", "Demo2026!", "admin"),
        (empresas["demo"], "Diego Salinas", "operador@demo.mx", "Operador2026!", "operador"),
        (empresas["norte"], "Laura Medina", "admin@norte.mx", "Norte2026!", "admin"),
        (empresas["norte"], "Raúl Ibarra", "operador@norte.mx", "Operador2026!", "operador"),
    ]
    ids = {}
    for empresa_id, nombre, email, password, rol in usuarios:
        ids[email] = insertar(
            cur,
            """INSERT INTO usuarios (empresa_id, nombre, email, password_hash, rol, activo)
               VALUES (%s, %s, %s, %s, %s, 1)""",
            (empresa_id, nombre, email, generate_password_hash(password), rol),
        )
    return ids


def crear_categorias(cur, empresa_id, definiciones):
    ids = {}
    for nombre, descripcion in definiciones:
        ids[nombre] = insertar(
            cur,
            """INSERT INTO categorias (empresa_id, nombre, descripcion, activo)
               VALUES (%s, %s, %s, 1)""",
            (empresa_id, nombre, descripcion),
        )
    return ids


def crear_productos(cur, empresa_id, categorias, filas):
    ids = []
    for sku, nombre, categoria, compra, venta, stock, minimo, unidad, ubicacion in filas:
        ids.append(
            insertar(
                cur,
                """INSERT INTO productos
                    (empresa_id, categoria_id, sku, nombre, descripcion, unidad,
                     ubicacion, precio_compra, precio_venta, stock, stock_minimo, activo)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1)""",
                (
                    empresa_id,
                    categorias.get(categoria),
                    sku,
                    nombre,
                    None,
                    unidad,
                    ubicacion,
                    compra,
                    venta,
                    stock,
                    minimo,
                ),
            )
        )
    return ids


def cargar_demo(conn):
    rng = random.Random(20261118)
    hoy = date.today()

    with conn.cursor() as cur:
        empresa_demo = insertar(
            cur,
            """INSERT INTO empresas
                (nombre, slug, rfc, correo, telefono, direccion, activa)
               VALUES (%s, %s, %s, %s, %s, %s, 1)""",
            (
                "PiedPiper Demo",
                "piedpiper-demo",
                "PPD260101AB1",
                "contacto@demo.mx",
                "+52 55 5555 0101",
                "Av. Reforma 120, Ciudad de México",
            ),
        )
        empresa_norte = insertar(
            cur,
            """INSERT INTO empresas
                (nombre, slug, rfc, correo, telefono, direccion, activa)
               VALUES (%s, %s, %s, %s, %s, %s, 1)""",
            (
                "Norte Logística",
                "norte-logistica",
                "NLO240315K92",
                "operaciones@norte.mx",
                "+52 81 8333 2200",
                "Carretera Miguel Alemán km 18, Monterrey",
            ),
        )

        insertar(
            cur,
            """INSERT INTO licencias
                (empresa_id, clave, plan, estado, max_usuarios, max_productos,
                 inicio, vence, notas)
               VALUES (%s, %s, 'profesional', 'activa', 10, 2000, CURDATE(), %s, %s)""",
            (
                empresa_demo,
                "PP-PRO-DEMO-2026",
                hoy + timedelta(days=365),
                "Licencia de demostración anual.",
            ),
        )
        insertar(
            cur,
            """INSERT INTO licencias
                (empresa_id, clave, plan, estado, max_usuarios, max_productos,
                 inicio, vence, notas)
               VALUES (%s, %s, 'basico', 'prueba', 3, 500, CURDATE(), %s, %s)""",
            (
                empresa_norte,
                "PP-BAS-NORTE-2026",
                hoy + timedelta(days=21),
                "Periodo de prueba de 21 días.",
            ),
        )

        usuarios = crear_usuarios(
            cur,
            {"demo": empresa_demo, "norte": empresa_norte},
            {},
        )

        cat_demo = crear_categorias(
            cur,
            empresa_demo,
            [
                ("Cómputo", "Equipo de cómputo y periféricos."),
                ("Redes", "Infraestructura de conectividad."),
                ("Almacén", "Consumibles y material de empaque."),
                ("Papelería", "Insumos de oficina."),
                ("Seguridad", "Equipo de protección y seguridad."),
            ],
        )
        cat_norte = crear_categorias(
            cur,
            empresa_norte,
            [
                ("Llantas", "Llantas para unidad pesada."),
                ("Lubricantes", "Aceites y fluidos."),
                ("Refacciones", "Filtros, frenos y componentes."),
            ],
        )

        filas_demo = [
                ("LAP-001", "Laptop Lenovo ThinkPad E14", "Cómputo", 24500, 28900, 8, 3, "pza", "A-01"),
                ("MON-002", 'Monitor Dell P2422H 24"', "Cómputo", 4200, 5290, 14, 4, "pza", "A-02"),
                ("TEC-003", "Teclado mecánico Keychron K2", "Cómputo", 1850, 2490, 6, 2, "pza", "A-03"),
                ("MOU-004", "Mouse Logitech MX Master 3S", "Cómputo", 1950, 2650, 3, 4, "pza", "A-03"),
                ("ROU-005", "Router MikroTik hEX S", "Redes", 1850, 2450, 12, 3, "pza", "B-01"),
                ("SWI-006", "Switch TP-Link TL-SG108", "Redes", 780, 1150, 21, 5, "pza", "B-01"),
                ("APU-007", "Access Point Ubiquiti U6 Lite", "Redes", 2650, 3390, 7, 3, "pza", "B-02"),
                ("CAB-008", "Cable UTP Cat6 305 m", "Redes", 2850, 3890, 2, 3, "rollo", "B-03"),
                ("CAJ-009", "Caja de archivo carta", "Almacén", 22, 39, 180, 40, "pza", "C-01"),
                ("CIN-010", "Cinta adhesiva industrial", "Almacén", 38, 65, 0, 12, "pza", "C-01"),
                ("GUA-011", "Guantes de nitrilo caja 100", "Almacén", 145, 240, 34, 10, "caja", "C-02"),
                ("BOL-012", "Bolsa 30x40 cm (100 pz)", "Almacén", 65, 110, 55, 15, "paq", "C-02"),
                ("PAP-013", "Resma papel carta 500 hojas", "Papelería", 78, 135, 96, 20, "paq", "D-01"),
                ("TON-014", "Tóner HP 26A", "Papelería", 1650, 2290, 4, 2, "pza", "D-02"),
                ("PLU-015", "Pluma gel negra (12 pz)", "Papelería", 85, 149, 42, 10, "paq", "D-01"),
                ("LIB-016", "Libreta profesional 100 hojas", "Papelería", 35, 69, 28, 8, "pza", "D-03"),
                ("EXT-017", "Extintor PQS 6 kg", "Seguridad", 890, 1350, 11, 3, "pza", "E-01"),
                ("BOT-018", "Botiquín industrial 50 piezas", "Seguridad", 540, 890, 6, 2, "pza", "E-01"),
                ("CHA-019", "Chaleco reflectante", "Seguridad", 120, 220, 25, 8, "pza", "E-02"),
                ("CAN-020", "Candado de seguridad 50 mm", "Seguridad", 145, 259, 1, 5, "pza", "E-03"),
        ]
        productos_demo = crear_productos(cur, empresa_demo, cat_demo, filas_demo)

        filas_norte = [
                ("LLA-001", "Llanta 295/80 R22.5", "Llantas", 5800, 7600, 18, 6, "pza", "P-01"),
                ("ACE-002", "Aceite motor 15W-40 (20 L)", "Lubricantes", 1450, 1990, 22, 5, "cubeta", "P-02"),
                ("FIL-003", "Filtro de aire Fleetguard", "Refacciones", 480, 720, 9, 4, "pza", "P-03"),
                ("FIL-004", "Filtro de aceite Donaldson", "Refacciones", 320, 520, 31, 10, "pza", "P-03"),
                ("BOM-005", "Bomba de agua", "Refacciones", 2400, 3400, 3, 2, "pza", "P-04"),
                ("BAL-006", "Balata de freno (juego)", "Refacciones", 1250, 1850, 14, 4, "juego", "P-04"),
                ("REF-007", "Refrigerante 50/50 (5 L)", "Lubricantes", 240, 380, 0, 6, "garrafa", "P-02"),
                ("TOR-008", "Tornillería grado 8 (caja)", "Refacciones", 390, 590, 8, 3, "caja", "P-05"),
        ]
        productos_norte = crear_productos(cur, empresa_norte, cat_norte, filas_norte)

        motivos = {
            "entrada": [
                "Compra a proveedor",
                "Reposición de stock",
                "Devolución de cliente",
                "Traslado de almacén",
            ],
            "salida": [
                "Venta mostrador",
                "Pedido en línea",
                "Consumo interno",
                "Entrega a sucursal",
            ],
            "ajuste": [
                "Ajuste por conteo físico",
                "Merma de almacén",
                "Corrección de captura",
            ],
        }

        def insertar_movimiento(empresa_id, producto_id, usuario_id, tipo, cantidad,
                                anterior, resultante, motivo, referencia, fecha_hora):
            cur.execute(
                """INSERT INTO movimientos
                    (empresa_id, producto_id, usuario_id, tipo, cantidad,
                     stock_anterior, stock_resultante, motivo, referencia, creado_en)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    empresa_id,
                    producto_id,
                    usuario_id,
                    tipo,
                    cantidad,
                    anterior,
                    resultante,
                    motivo,
                    referencia,
                    fecha_hora,
                ),
            )

        admin_demo = usuarios["admin@demo.mx"]
        operador_demo = usuarios["operador@demo.mx"]
        admin_norte = usuarios["admin@norte.mx"]

        def generar_eventos(productos, usuarios, total, dias_max):
            eventos = []
            for _ in range(total):
                tipo = rng.choices(
                    ["entrada", "salida", "ajuste"], weights=[40, 50, 10], k=1
                )[0]
                if tipo == "entrada":
                    cantidad = rng.randint(3, 18)
                elif tipo == "salida":
                    cantidad = rng.randint(1, 12)
                else:
                    cantidad = rng.randint(15, 60)
                eventos.append(
                    {
                        "producto_id": rng.choice(productos),
                        "usuario_id": rng.choice(usuarios),
                        "tipo": tipo,
                        "cantidad": cantidad,
                        "motivo": rng.choice(motivos[tipo]),
                        "fecha": datetime.combine(
                            hoy - timedelta(days=rng.randint(0, dias_max)),
                            time(rng.randint(8, 18), rng.randint(0, 59)),
                        ),
                    }
                )
            eventos.sort(key=lambda ev: ev["fecha"])
            return eventos

        def simular_eventos(eventos, stock, empresa_id, numeracion):
            contador = 0
            for ev in eventos:
                actual = stock[ev["producto_id"]]
                if ev["tipo"] == "salida":
                    if ev["cantidad"] > actual:
                        continue
                    nuevo = actual - ev["cantidad"]
                elif ev["tipo"] == "entrada":
                    nuevo = actual + ev["cantidad"]
                else:
                    nuevo = ev["cantidad"]

                stock[ev["producto_id"]] = nuevo
                prefijo = {"entrada": "OC", "salida": "FAC", "ajuste": "AJ"}[ev["tipo"]]
                insertar_movimiento(
                    empresa_id,
                    ev["producto_id"],
                    ev["usuario_id"],
                    ev["tipo"],
                    ev["cantidad"],
                    actual,
                    nuevo,
                    ev["motivo"],
                    "%s-%04d" % (prefijo, numeracion + contador),
                    ev["fecha"],
                )
                contador += 1

        def fijar_stock_bajo(empresa_id, usuario_id, sku_ids, stock, objetivos):
            for sku, objetivo in objetivos.items():
                producto_id = sku_ids.get(sku)
                if not producto_id:
                    continue
                actual = stock[producto_id]
                if actual <= objetivo:
                    continue
                insertar_movimiento(
                    empresa_id,
                    producto_id,
                    usuario_id,
                    "ajuste",
                    objetivo,
                    actual,
                    objetivo,
                    "Ajuste por conteo físico",
                    "AJ-DEMO",
                    datetime.combine(hoy, time(23, 45)),
                )
                stock[producto_id] = objetivo

        # --- Empresa demo: historial coherente con el stock final ---
        stock_demo = {
            pid: max(int(fila[5]), 6)
            for pid, fila in zip(productos_demo, filas_demo)
        }
        simular_eventos(
            generar_eventos(productos_demo, [admin_demo, operador_demo], 80, 9),
            stock_demo,
            empresa_demo,
            1000,
        )
        sku_demo = {fila[0]: pid for pid, fila in zip(productos_demo, filas_demo)}
        fijar_stock_bajo(
            empresa_demo,
            admin_demo,
            sku_demo,
            stock_demo,
            {"MOU-004": 3, "CAB-008": 2, "CIN-010": 0, "CAN-020": 1, "TON-014": 2},
        )
        for producto_id, valor in stock_demo.items():
            cur.execute(
                "UPDATE productos SET stock = %s WHERE id = %s",
                (valor, producto_id),
            )

        # --- Segunda empresa: volumen menor ---
        stock_norte = {
            pid: max(int(fila[5]), 5)
            for pid, fila in zip(productos_norte, filas_norte)
        }
        simular_eventos(
            generar_eventos(productos_norte, [admin_norte], 14, 9),
            stock_norte,
            empresa_norte,
            2000,
        )
        sku_norte = {fila[0]: pid for pid, fila in zip(productos_norte, filas_norte)}
        fijar_stock_bajo(
            empresa_norte,
            admin_norte,
            sku_norte,
            stock_norte,
            {"REF-007": 0, "BOM-005": 2},
        )
        for producto_id, valor in stock_norte.items():
            cur.execute(
                "UPDATE productos SET stock = %s WHERE id = %s",
                (valor, producto_id),
            )

    conn.commit()
    return empresa_demo, empresa_norte


def main():
    args = argumentos()

    if not re.fullmatch(r"[A-Za-z0-9_]+", args.database):
        print("Nombre de base de datos inválido.", file=sys.stderr)
        return 2

    if args.fresh and not args.yes:
        print("Esto eliminará la base de datos «%s» y todos sus datos." % args.database)
        respuesta = input("Escribe SI para continuar: ").strip()
        if respuesta != "SI":
            print("Cancelado.")
            return 1

    print("PiedPiper Inventario · inicialización")
    print("  Servidor : %s:%s" % (args.host, args.port))
    print("  Base     : %s" % args.database)
    print("  Usuario  : %s" % args.user)

    try:
        conn = conectar(args, con_base=False)
    except Exception as exc:
        print("\nNo fue posible conectar a MariaDB: %s" % exc, file=sys.stderr)
        print("Revisa DB_USER / DB_PASSWORD en .env o los parámetros del comando.", file=sys.stderr)
        return 1

    try:
        with conn.cursor() as cur:
            if args.fresh:
                cur.execute("DROP DATABASE IF EXISTS `%s`" % args.database)
                print("  Base anterior eliminada.")
            cur.execute(
                "CREATE DATABASE IF NOT EXISTS `%s` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci" % args.database
            )
        conn.select_db(args.database)
        aplicar_esquema(conn)

        if args.no_demo:
            print("  Datos demo omitidos (--no-demo).")
        else:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) AS n FROM empresas")
                existentes = cur.fetchone()["n"]
            if existentes:
                print("  Ya existen empresas registradas; se conservan los datos actuales.")
            else:
                cargar_demo(conn)
                print("  Datos de demostración cargados.")
    except Exception as exc:
        print("\nError durante la inicialización: %s" % exc, file=sys.stderr)
        return 1
    finally:
        conn.close()

    print("\nListo. Accesos de demostración:")
    print("  Superadmin : admin@piedpiper.software / PiedPiper2026!")
    print("  Admin demo : admin@demo.mx            / Demo2026!")
    print("  Operador   : operador@demo.mx         / Operador2026!")
    print("\nArranca la aplicación con:")
    print("  flask --app app run --debug")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
