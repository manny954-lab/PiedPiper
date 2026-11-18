"""Configuración central de PiedPiper Inventario."""
import os
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "si", "sí", "yes", "on"}


class Config:
    # --- Seguridad -----------------------------------------------------
    SECRET_KEY = os.getenv("SECRET_KEY", "piedpiper-dev-secret-cambia-esto")
    SESSION_COOKIE_NAME = "pp_session"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _bool_env("COOKIE_SECURE", False)
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    MAX_CONTENT_LENGTH = 2 * 1024 * 1024

    # --- Base de datos --------------------------------------------------
    DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
    DB_PORT = int(os.getenv("DB_PORT", "3306"))
    DB_USER = os.getenv("DB_USER", "piedpiper")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DB_NAME = os.getenv("DB_NAME", "piedpiper_erp")
    DB_CHARSET = "utf8mb4"

    # --- Producto -------------------------------------------------------
    APP_NOMBRE = "PiedPiper Inventario"
    APP_VERSION = "1.0.0"
    DEMO_MODE = _bool_env("DEMO_MODE", True)
    SOPORTE_EMAIL = os.getenv("SOPORTE_EMAIL", "soporte@piedpiper.software")
