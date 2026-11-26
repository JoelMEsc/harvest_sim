#!/usr/bin/env bash
# ==============================================================================
# correr_todos.sh — Ejecución integral de la línea base de harvest_sim
#
# Flujo:
#   1. Ejecuta la simulación de los escenarios A–G con la CLI (A–F línea base;
#      G es el campo real de El Pueblito, con mapa y R13)
#   2. Valida los archivos trace.json generados (esquemas 2.1, 2.2 y 2.3)
#   3. Genera las gráficas individuales, mapas, comparación y tablas de resumen
#   4. Ejecuta los experimentos: tasa de transferencia (primera entrega) y el
#      principal de la segunda entrega (D, E, F × 4 estrategias × 20 seeds,
#      comparación pareada contra la base y ablación de J) y el del terreno
#      real (G × 4 estrategias × 20 seeds)
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
    echo "==> [1/5] Ejecutando la simulación de los escenarios A–G..."
    TRACES=()
    ESCENARIOS_DASHBOARD=()
    for e in a b c d e f g; do
        python -m harvest_sim.cli "config/escenario_${e}.json" --sin-plots --silencioso
        TRACES+=("runs/escenario_${e}/trace.json")
        ESCENARIOS_DASHBOARD+=("runs/escenario_${e}")
    done
    RUNS_BASE="runs"
    EXPERIMENTO_FLAG=""
fi

echo "==> [2/5] Validando formato y contrato de traces generados..."
python tools/validar_trace.py "${TRACES[@]}"

echo "==> [3/5] Generando gráficas, mapas, comparación y tabla resumen..."
# La comparación junta A–F; G (campo real, ~10 veces más largo) lleva solo sus gráficas propias.
COMPARABLES=()
for t in "${TRACES[@]}"; do
    [[ "${t}" == *escenario_g/* ]] || COMPARABLES+=("${t}")
done
python viz/plots.py "${COMPARABLES[@]}"
if [[ "${MODO_EJEMPLO}" != "true" ]]; then
    python viz/plots.py runs/escenario_g/trace.json --sin-comparacion
fi

echo "==> [4/5] Ejecutando experimentos..."
if [[ -n "${EXPERIMENTO_FLAG}" ]]; then
    python tools/correr_experimento.py config/experimentos/tasa_transferencia.json ${EXPERIMENTO_FLAG}
else
    python tools/correr_experimento.py config/experimentos/tasa_transferencia.json
    PROCESOS="$(python -c 'import os; print(max(1, (os.cpu_count() or 2) - 1))')"
    python tools/correr_experimento.py config/experimentos/estrategias.json --procesos "${PROCESOS}"
    python tools/correr_experimento.py config/experimentos/terreno_g_estrategias.json --procesos "${PROCESOS}"
fi

echo "==> [5/5] Exportando cuadros del visor y construyendo dashboard..."
if [[ -f viz/dashboard.py ]]; then
    for i in "${!TRACES[@]}"; do
        python viz/viewer.py "${TRACES[$i]}" --guardar-cuadros "${ESCENARIOS_DASHBOARD[$i]}/cuadros"
    done
    python viz/dashboard.py "${ESCENARIOS_DASHBOARD[@]}" --salida runs/dashboard.html
    echo "Dashboard generado en: runs/dashboard.html"
else
    echo "Aviso: viz/dashboard.py aún no está disponible en esta rama; omitiendo."
fi

echo "=================================================================="
echo " Ejecución completada exitosamente."
echo "=================================================================="
