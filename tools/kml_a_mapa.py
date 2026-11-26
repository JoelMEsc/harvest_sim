#!/usr/bin/env python3
"""Convierte el KML del cultivo en el mapa de celdas de la simulación.  [Oswaldo / Joel]

    python tools/kml_a_mapa.py                                         # config/mapas/el_pueblito.convertidor.json
    python tools/kml_a_mapa.py config/mapas/otro.convertidor.json
    python tools/kml_a_mapa.py --figura docs/figuras/terreno/el_pueblito_mapa.png

Lee la configuración del convertidor (KML, tamaño de celda, tolerancias; docs/especificacion_terreno.md §4),
escribe el mapa (§5) junto a ella e imprime el reporte: rumbo de cada lote, cada soldadura de caminos, área
y tamaño de la cuadrícula. Falla con un mensaje claro si un camino queda suelto, un lote no tiene entrada o
el área no cuadra: eso se corrige en el KML (Google Earth), no aquí.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))  # permite correrlo sin instalar el paquete (pip install -e .)

from harvest_sim.mapa.convertir import ErrorMapa, construir_desde_config  # noqa: E402


def dibujar(mapa: dict, ruta: Path) -> None:
    """Figura del mapa: celdas por tipo y, encima, las formas reales del KML."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    from matplotlib.colors import ListedColormap
    from matplotlib.patches import Patch

    s, w, h = mapa["tamano_celda_m"], mapa["ancho"], mapa["alto"]
    g = np.zeros((h, w))
    lotes = sorted(mapa["lotes"])
    for x, y in mapa["caminos"]:
        g[y, x] = 1
    for x, y in mapa["obstaculos"]:
        g[y, x] = 2
    for i, n in enumerate(lotes):
        for x, y in mapa["lotes"][n]:
            g[y, x] = 3 + i
    patio = 3 + len(lotes)
    for x, y in [mapa["bodega"]] + mapa["bases"]:
        g[y, x] = patio
    tonos = ["#e8c547", "#d8ae2f", "#c69a1f", "#b5891a", "#a27a17"][:len(lotes)]
    colores = ["#eeeeee", "#a1887f", "#2e7d32"] + tonos + ["#c62828"]
    fig, ax = plt.subplots(figsize=(11, 11 * h / w + 1))
    ax.imshow(g, cmap=ListedColormap(colores), origin="lower", extent=(0, w * s, 0, h * s), vmin=0, vmax=patio,
              interpolation="nearest")
    formas = mapa["geo"]["formas"]
    for pol in formas["lotes"].values():
        xs, ys = zip(*(pol + [pol[0]]))
        ax.plot(xs, ys, color="#212121", lw=1)
    for lin in formas["caminos"]:
        xs, ys = zip(*lin)
        ax.plot(xs, ys, color="#4e342e", lw=1.4)
    for pol in formas["obstaculos"]:
        xs, ys = zip(*(pol + [pol[0]]))
        ax.plot(xs, ys, color="#1b5e20", lw=1)
    leyenda = [Patch(color=colores[1], label="camino"), Patch(color=colores[2], label="obstáculo")] + \
              [Patch(color=tonos[i], label=f"lote {n}") for i, n in enumerate(lotes)] + \
              [Patch(color=colores[-1], label="bodega y bases"), Patch(color=colores[0], label="fuera de campo")]
    ax.legend(handles=leyenda, loc="upper right", fontsize=8, framealpha=0.9)
    ax.set_title(f"{mapa['nombre']}: {w} × {h} celdas de {s:g} m, rumbo de los surcos "
                 f"{mapa['geo']['rumbo_grados']:.1f}° (x = a lo largo de los surcos)", fontsize=10)
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    ruta.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(ruta, dpi=110, bbox_inches="tight")
    plt.close(fig)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="KML del cultivo -> mapa de celdas (config/mapas/*.json).")
    parser.add_argument("config", nargs="?", default=str(RAIZ / "config" / "mapas" / "el_pueblito.convertidor.json"))
    parser.add_argument("--figura", help="además, guarda una figura del mapa en esta ruta (PNG)")
    args = parser.parse_args(argv)
    try:
        mapa, reporte, salida = construir_desde_config(args.config)
    except ErrorMapa as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    salida.write_text(json.dumps(mapa, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    for linea in reporte:
        print(linea)
    print(f"escrito: {salida}")
    if args.figura:
        dibujar(mapa, Path(args.figura))
        print(f"figura: {args.figura}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
