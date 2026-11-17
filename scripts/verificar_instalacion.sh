#!/usr/bin/env bash
# ==============================================================================
# verificar_instalacion.sh — Verificación en un entorno limpio desde cero
#
# Flujo:
#   1. Crea un directorio temporal con un entorno virtual nuevo
#   2. Instala dependencias desde requirements.txt e instala el paquete con pip
#   3. Ejecuta la suite de pruebas automatizadas (pytest)
#   4. Ejecuta scripts/correr_todos.sh para verificar el pipeline completo
#   5. Limpia automáticamente la carpeta temporal al finalizar
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${ROOT_DIR}"

export SDL_VIDEODRIVER=dummy
export MPLBACKEND=Agg

TMP_DIR="$(mktemp -d -t harvest_sim_verif_XXXXXX)"
echo "==> Creando entorno virtual temporal en: ${TMP_DIR}"

cleanup() {
    echo "==> Limpiando carpeta temporal de verificación..."
    rm -rf "${TMP_DIR}"
}
trap cleanup EXIT

# Seleccionar binario de Python 3.12 preferentemente, o python3
PYTHON_BIN="python3"
if command -v python3.12 >/dev/null 2>&1; then
    PYTHON_BIN="python3.12"
fi

echo "==> Usando ${PYTHON_BIN} para crear el entorno virtual..."
"${PYTHON_BIN}" -m venv "${TMP_DIR}/venv"
source "${TMP_DIR}/venv/bin/activate"

echo "==> Actualizando pip e instalando dependencias..."
pip install --upgrade pip
pip install -r requirements.txt
pip install -e .

echo "==> Ejecutando suite de pruebas con pytest..."
pytest -q

echo "==> Ejecutando scripts/correr_todos.sh..."
bash scripts/correr_todos.sh "$@"

echo "=================================================================="
echo " Verificación de instalación completada con éxito."
echo "=================================================================="
