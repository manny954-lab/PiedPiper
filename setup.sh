#!/usr/bin/env bash
# ============================================================
# PiedPiper Inventario · instalación local
# Uso: bash setup.sh
# ============================================================
set -euo pipefail

cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"

echo "PiedPiper Inventario · configuración"
echo "------------------------------------"

if ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo "ERROR: no se encontró $PYTHON. Instala Python 3.9 o superior." >&2
  exit 1
fi

if [ ! -d ".venv" ]; then
  echo "→ Creando entorno virtual .venv"
  "$PYTHON" -m venv .venv
else
  echo "→ Reutilizando entorno virtual .venv"
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo "→ Instalando dependencias"
python -m pip install --upgrade pip >/dev/null
python -m pip install -r requirements.txt

if [ ! -f ".env" ]; then
  echo "→ Creando .env desde .env.example"
  cp .env.example .env
  echo "  Edita .env con tus credenciales de MariaDB antes de continuar."
else
  echo "→ .env ya existe; no se modificó"
fi

echo
echo "Siguientes pasos:"
echo "  1. Asegúrate de tener MariaDB en marcha."
echo "  2. Crea el usuario y la base (como root):"
echo "       CREATE USER 'piedpiper'@'localhost' IDENTIFIED BY 'PiedPiper2026!';"
echo "       GRANT ALL PRIVILEGES ON piedpiper_erp.* TO 'piedpiper'@'localhost';"
echo "       FLUSH PRIVILEGES;"
echo "  3. Carga el esquema y los datos demo:"
echo "       source .venv/bin/activate && python seed.py"
echo "  4. Arranca la aplicación:"
echo "       bash run.sh"
echo
echo "Listo."
