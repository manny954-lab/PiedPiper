#!/usr/bin/env bash
# ============================================================
# PiedPiper Inventario · control de la base de datos local
# Uso:
#   bash db.sh estado      # ver si MariaDB está activo
#   bash db.sh iniciar     # arrancar MariaDB
#   bash db.sh detener     # apagar MariaDB
#   bash db.sh reiniciar   # reiniciar MariaDB
#   bash db.sh habilitar   # arrancar siempre con el sistema
#   bash db.sh verificar   # probar la conexión con los datos del .env
#   bash db.sh seed        # aplicar esquema + datos demo (sin borrar)
#   bash db.sh reset       # borrar y recrear la base (pide confirmación)
# ============================================================
set -euo pipefail

cd "$(dirname "$0")"

CMD="${1:-ayuda}"
SUDO=""
if [ "$(id -u)" -ne 0 ]; then
  SUDO="sudo"
fi

_verificar() {
  python3 - <<'PY'
import os
import sys

from dotenv import load_dotenv

load_dotenv(".env")

import pymysql

try:
    conn = pymysql.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "piedpiper"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "piedpiper_erp"),
        connect_timeout=5,
    )
    conn.close()
except Exception as exc:
    print("Sin conexión → %s" % exc)
    sys.exit(1)

print("Conexión OK → %s:%s/%s" % (
    os.getenv("DB_HOST", "127.0.0.1"),
    os.getenv("DB_PORT", "3306"),
    os.getenv("DB_NAME", "piedpiper_erp"),
))
PY
}

case "$CMD" in
  iniciar | start)
    $SUDO systemctl start mariadb
    echo "MariaDB iniciado."
    _verificar || true
    ;;
  detener | stop)
    $SUDO systemctl stop mariadb
    echo "MariaDB detenido. Los datos siguen guardados en disco."
    ;;
  reiniciar | restart)
    $SUDO systemctl restart mariadb
    echo "MariaDB reiniciado."
    _verificar || true
    ;;
  estado | status)
    systemctl status mariadb --no-pager --lines=0 || true
    _verificar || true
    ;;
  habilitar | enable)
    $SUDO systemctl enable --now mariadb
    echo "MariaDB quedó habilitado para arrancar con el sistema."
    ;;
  verificar | check)
    _verificar
    ;;
  seed)
    python3 seed.py
    ;;
  reset)
    python3 seed.py --fresh
    ;;
  ayuda | help | *)
    cat <<'TXT'
PiedPiper Inventario · control de MariaDB

  bash db.sh estado      Ver si MariaDB y la base responden
  bash db.sh iniciar     Arrancar el servidor MariaDB
  bash db.sh detener     Apagar el servidor (los datos se conservan)
  bash db.sh reiniciar   Reiniciar el servidor
  bash db.sh habilitar   Arrancar siempre con el sistema
  bash db.sh verificar   Probar la conexión definida en .env
  bash db.sh seed        Crear esquema y datos demo sin borrar nada
  bash db.sh reset       Borrar y recrear la base (pide confirmación)

phpMyAdmin: http://127.0.0.1/phpmyadmin/
TXT
    ;;
esac
