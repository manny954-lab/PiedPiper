"""Capa de acceso a MariaDB con PyMySQL.

Todas las consultas de la aplicación pasan por estos helpers y usan
parámetros (``%s``); nunca se interpola texto del usuario en el SQL.
"""
from contextlib import contextmanager

import pymysql
from flask import current_app, g
from pymysql.cursors import DictCursor


def get_db() -> pymysql.connections.Connection:
    """Devuelve la conexión de la petición actual (se crea si no existe)."""
    if "db" not in g:
        cfg = current_app.config
        g.db = pymysql.connect(
            host=cfg["DB_HOST"],
            port=cfg["DB_PORT"],
            user=cfg["DB_USER"],
            password=cfg["DB_PASSWORD"],
            database=cfg["DB_NAME"],
            charset=cfg["DB_CHARSET"],
            cursorclass=DictCursor,
            autocommit=False,
            connect_timeout=6,
            read_timeout=20,
            write_timeout=20,
        )
    return g.db


def close_db(exc=None) -> None:
    db = g.pop("db", None)
    if db is not None:
        try:
            db.close()
        except Exception:  # pragma: no cover - cierre defensivo
            pass


def query_one(sql: str, params=()):
    with get_db().cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()


def query_all(sql: str, params=()):
    with get_db().cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def execute(sql: str, params=(), commit: bool = True):
    """Ejecuta una sentencia y devuelve el lastrowid."""
    db = get_db()
    try:
        with db.cursor() as cur:
            cur.execute(sql, params)
            last_id = cur.lastrowid
        if commit:
            db.commit()
        return last_id
    except Exception:
        db.rollback()
        raise


@contextmanager
def tx():
    """Transacción explícita: commit al salir, rollback ante cualquier error."""
    db = get_db()
    try:
        with db.cursor() as cur:
            yield cur
        db.commit()
    except Exception:
        db.rollback()
        raise


def init_app(app) -> None:
    app.teardown_appcontext(close_db)
