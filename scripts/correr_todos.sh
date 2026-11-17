#!/usr/bin/env bash
# ==============================================================================
# correr_todos.sh — Ejecución integral de la línea base de harvest_sim
#
# Flujo:
#   1. Ejecuta la simulación para los tres escenarios (A, B, C) con la CLI
#   2. Valida los archivos trace.json generados contra el esquema 2.1
#   3. Genera las gráficas individuales, mapas, comparación y tablas de resumen
#   4. Ejecuta el experimento de barrido de parámetros (tasa de transferencia)
#   5. Construye el dashboard interactivo (si viz/dashboard.py está disponible)
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${ROOT_DIR}"

export SDL_VIDEODRIVER=dummy
export MPLBACKEND=Agg

echo "=================================================================="
echo " harvest_sim — Ejecución integral de todos los escenarios"
echo "=================================================================="

MODO_EJEMPLO=false
if [[ "${1:-}" == "--ejemplo" ]]; then
    MODO_EJEMPLO=true
    echo "==> MODO EJEMPLO activado (usando generador de datos de ejemplo)"
fi

if [[ "${MODO_EJEMPLO}" == "true" ]]; then
    echo "==> [1/5] Generando traces de ejemplo para escenarios A, B y C..."
    python tools/generar_trace_ejemplo.py --escenarios
    RUNS_BASE="runs/ejemplo"
    TRACES=(
        "${RUNS_BASE}/ejemplo_a/trace.json"
        "${RUNS_BASE}/ejemplo_b/trace.json"
        "${RUNS_BASE}/ejemplo_c/trace.json"
    )
    EXPERIMENTO_FLAG="--simulador ejemplo"
    ESCENARIOS_DASHBOARD=(
        "${RUNS_BASE}/ejemplo_a"
        "${RUNS_BASE}/ejemplo_b"
        "${RUNS_BASE}/ejemplo_c"
    )
else
    echo "==> [1/5] Ejecutando simulación para escenario_a, escenario_b y escenario_c..."
    python -m harvest_sim.cli config/escenario_a.json
    python -m harvest_sim.cli config/escenario_b.json
    python -m harvest_sim.cli config/escenario_c.json
    RUNS_BASE="runs"
    TRACES=(
        "runs/escenario_a/trace.json"
        "runs/escenario_b/trace.json"
        "runs/escenario_c/trace.json"
    )
    EXPERIMENTO_FLAG=""
    ESCENARIOS_DASHBOARD=(
        "runs/escenario_a"
        "runs/escenario_b"
        "runs/escenario_c"
    )
fi

echo "==> [2/5] Validando formato y contrato de traces generados..."
python tools/validar_trace.py "${TRACES[@]}"

echo "==> [3/5] Generando gráficas, mapas, comparación y tabla resumen..."
python viz/plots.py "${TRACES[@]}"

echo "==> [4/5] Ejecutando experimento de tasa de transferencia..."
if [[ -n "${EXPERIMENTO_FLAG}" ]]; then
    python tools/correr_experimento.py config/experimentos/tasa_transferencia.json ${EXPERIMENTO_FLAG}
else
    python tools/correr_experimento.py config/experimentos/tasa_transferencia.json
fi

echo "==> [5/5] Construyendo dashboard..."
if [[ -f viz/dashboard.py ]]; then
    python viz/dashboard.py "${ESCENARIOS_DASHBOARD[@]}" --salida runs/dashboard.html
    echo "Dashboard generado en: runs/dashboard.html"
else
    echo "Aviso: viz/dashboard.py aún no está disponible en esta rama; omitiendo."
fi

echo "=================================================================="
echo " Ejecución completada exitosamente."
echo "=================================================================="
