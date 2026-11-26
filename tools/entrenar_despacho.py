#!/usr/bin/env python3
"""Entrena el despacho aprendido (mejora M1) de un escenario con Q-learning o SARSA.  [Joel]

    python tools/entrenar_despacho.py config/escenario_d.json --algoritmo qlearning --episodios 300
    python tools/entrenar_despacho.py config/escenario_g.json --algoritmo sarsa --episodios 40

Cada episodio es una corrida completa con la seed 1000 + episodio (la evaluación usa las seeds 0 a 19, que
nunca se ven al entrenar). La exploración ε baja en línea recta de --epsilon a 0.01. Escribe:

    config/aprendizaje/qtabla_<algoritmo>_<escenario>.json   la tabla Q, sus visitas y los hiperparámetros
    runs/aprendizaje/<algoritmo>_<escenario>/curva.csv       una fila por episodio (recompensa, ocio, ticks…)

Especificación: docs/especificacion_mejoras.md §M1. La tabla se versiona; la curva se regenera.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from harvest_sim.aprendizaje import ALGORITMOS, PARAMETROS, Despachador, ruta_tabla  # noqa: E402
from harvest_sim.config import cargar_config  # noqa: E402
from harvest_sim.datos.experimentos import aplicar_estrategia  # noqa: E402
from harvest_sim.simulacion import ejecutar  # noqa: E402

SEMILLA_ENTRENAMIENTO = 1000
COLUMNAS = ["episodio", "seed", "epsilon", "recompensa", "tiempo_ocioso_total", "tiempo_completacion",
            "servicios", "decisiones", "cliffs", "estados"]


def correr(config: dict, despachador: Despachador) -> dict:
    """Una corrida con el despachador dado (aprendiendo o no); devuelve las métricas del trace."""
    with tempfile.TemporaryDirectory() as carpeta:
        ruta = Path(carpeta) / "config.json"
        ruta.write_text(json.dumps(config), encoding="utf-8")
        return ejecutar(cargar_config(ruta), despachador)["metricas"]


def entrenar(base: dict, algoritmo: str, episodios: int, parametros: dict | None = None,
             semilla_inicial: int = SEMILLA_ENTRENAMIENTO, al_terminar_episodio=None) -> tuple[Despachador, list[dict]]:
    """Entrena una tabla nueva y devuelve el despachador y la curva (una fila por episodio)."""
    config = aplicar_estrategia(base, algoritmo)
    despachador = Despachador(algoritmo, parametros, aprender=True, semilla=semilla_inicial)
    epsilon_inicial = despachador.parametros["epsilon"]
    curva = []
    for ep in range(episodios):
        despachador.parametros["epsilon"] = max(0.01, epsilon_inicial * (1 - ep / max(1, episodios - 1)))
        seed = semilla_inicial + ep
        m = correr({**config, "seed": seed}, despachador)
        fila = {"episodio": ep, "seed": seed, "epsilon": round(despachador.parametros["epsilon"], 4),
                "recompensa": round(despachador.recompensa_episodio, 2),
                "tiempo_ocioso_total": m["tiempo_ocioso_total"], "tiempo_completacion": m["tiempo_completacion"],
                "servicios": m.get("servicios"), "decisiones": despachador.decisiones, "cliffs": despachador.cliffs,
                "estados": len(despachador.q)}
        curva.append(fila)
        if al_terminar_episodio:
            al_terminar_episodio(fila)
    despachador.parametros["epsilon"] = epsilon_inicial
    despachador.aprender = False
    return despachador, curva


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("config", help="escenario, p. ej. config/escenario_d.json")
    parser.add_argument("--algoritmo", choices=ALGORITMOS, default="qlearning")
    parser.add_argument("--episodios", type=int, default=200)
    for clave, valor in PARAMETROS.items():
        parser.add_argument(f"--{clave.replace('_', '-')}", type=float, default=valor)
    parser.add_argument("--tabla", help="dónde guardar la tabla (default: config/aprendizaje/qtabla_<alg>_<escenario>.json)")
    parser.add_argument("--curva", help="CSV de la curva (default: runs/aprendizaje/<alg>_<escenario>/curva.csv)")
    args = parser.parse_args(argv)
    if args.episodios < 1:
        parser.error("--episodios debe ser >= 1")
    logging.disable(logging.WARNING)
    base = json.loads(Path(args.config).read_text(encoding="utf-8"))
    if base.get("mapa"):
        # el mapa se busca junto al JSON del escenario; desde un directorio temporal, en config/
        base["mapa"] = str((Path(args.config).resolve().parent / base["mapa"]).resolve())
    nombre = base["nombre"]
    parametros = {clave: getattr(args, clave) for clave in PARAMETROS}
    inicio = time.time()

    def avance(fila):
        print(f"ep {fila['episodio']:4d}  ε={fila['epsilon']:.3f}  R={fila['recompensa']:9.1f}  "
              f"ocio={fila['tiempo_ocioso_total']:5d}  ticks={fila['tiempo_completacion']:5d}  "
              f"cliffs={fila['cliffs']:3d}  estados={fila['estados']:3d}  ({time.time() - inicio:.0f} s)", flush=True)

    despachador, curva = entrenar(base, args.algoritmo, args.episodios, parametros, al_terminar_episodio=avance)
    tabla = Path(args.tabla) if args.tabla else ruta_tabla({"aviso": args.algoritmo}, nombre)
    despachador.guardar(tabla, escenario=nombre, episodios=args.episodios,
                        semillas_entrenamiento=[SEMILLA_ENTRENAMIENTO, SEMILLA_ENTRENAMIENTO + args.episodios - 1])
    salida_curva = Path(args.curva) if args.curva else RAIZ / "runs" / "aprendizaje" / f"{args.algoritmo}_{nombre}" / "curva.csv"
    salida_curva.parent.mkdir(parents=True, exist_ok=True)
    with salida_curva.open("w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=COLUMNAS)
        escritor.writeheader()
        escritor.writerows(curva)
    print(f"tabla: {tabla}\ncurva: {salida_curva}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
