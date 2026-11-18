#!/usr/bin/env bash
# ============================================================
# PiedPiper Inventario · arranque en desarrollo
# Uso: bash run.sh [host] [puerto]
#
# Verifica que MariaDB responda; si está apagado intenta
# arrancarlo (pedirá la contraseña de sudo) antes de servir.
# ============================================================
set -euo pipefail

cd "$(dirname "$0")"

HOST="${1:-127.0.0.1}"
PORT="${2:-5000}"

if [ -d ".venv" ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

_db_ok() {
  python3 - <<'PY' >/dev/null 2>&1
import os
import pymysql
from dotenv import load_dotenv

load_dotenv(".env")
conn = pymysql.connect(
    host=os.getenv("DB_HOST", "127.0.0.1"),
    port=int(os.getenv("DB_PORT", "3306")),
    user=os.getenv("DB_USER", "piedpiper"),
    password=os.getenv("DB_PASSWORD", ""),
    database=os.getenv("DB_NAME", "piedpiper_erp"),
    connect_timeout=4,
)
conn.close()
PY
}

if ! _db_ok; then
  echo "La base de datos no responde; intentando arrancar MariaDB…"
  if command -v systemctl >/dev/null 2>&1; then
    sudo systemctl start mariadb || true
    for _ in 1 2 3 4 5 6 7 8 9 10; do
      _db_ok && break
      sleep 1
    done
  fi
fi

if ! _db_ok; then
  cat <<'TXT'

No se pudo conectar a la base de datos.

Revisa:
  1. Que MariaDB esté activo:      bash db.sh estado
  2. Que la base exista:           phpMyAdmin → http://127.0.0.1/phpmyadmin/
     (ejecuta database/crear_base.sql como root, una sola vez)
  3. Los datos de conexión en:     .env

Después vuelve a ejecutar:  bash run.sh

TXT
  exit 1
fi

export FLASK_APP=app
export FLASK_DEBUG="${FLASK_DEBUG:-1}"

echo "PiedPiper Inventario · http://${HOST}:${PORT}"
exec python -m flask run --host "$HOST" --port "$PORT"
