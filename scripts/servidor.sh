#!/usr/bin/env bash
# ==============================================================================
# servidor.sh — Levanta el servidor FastAPI de harvest_sim (para Unity y otros clientes)
#
# Uso:
#   bash scripts/servidor.sh                 # simulación real en http://127.0.0.1:8000
#   bash scripts/servidor.sh --ejemplo       # traces de ejemplo, sin simulación
#   PUERTO=9000 bash scripts/servidor.sh
#
# Rutas: /api/salud, /api/escenarios, /api/escenarios/{nombre}/trace?seed=&estrategia=,
# POST /api/simulaciones. Documentación interactiva en /docs.
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${SCRIPT_DIR}/.."

if [[ "${1:-}" == "--ejemplo" ]]; then
    export HARVEST_SIMULADOR=ejemplo
fi

exec python -m uvicorn harvest_sim.servidor:app --host "${HOST:-127.0.0.1}" --port "${PUERTO:-8000}"
