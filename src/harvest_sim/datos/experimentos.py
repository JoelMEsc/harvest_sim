"""Experimentos: escenarios x barrido de parámetros x repeticiones, y su resumen estadístico.  [Joel]

Es el criterio 4 de la rúbrica (diseño experimental): correr varios escenarios, variar parámetros,
repetir cuando hay aleatoriedad y comparar. La idea es la de `Experiment` de AgentPy, sin dependencias.

    filas = correr_experimento({"escenario_a": cfg_a, "escenario_b": cfg_b},
                               barrido={"capacidad_carro": [10, 20, 40]}, repeticiones=1)
    resumen = resumen_por_grupo(filas, ["capacidad_carro"])

`simulador(config_dict) -> trace` es la función que corre una simulación. Por defecto es la del equipo
(`simulador_real`: config.cargar_config + simulacion.ejecutar); en las pruebas, y mientras la simulación
no exista, se puede usar el generador de ejemplo (tools/generar_trace_ejemplo.py).
"""

from __future__ import annotations

import csv
import itertools
import json
import math
import statistics
import tempfile
from collections.abc import Callable
from pathlib import Path

from .metricas import calcular_metricas

# Valor crítico t de Student (dos colas, 95 %) por grados de libertad; con más de 30 se usa 1.96.
_T_95 = [12.706, 4.303, 3.182, 2.776, 2.571, 2.447, 2.365, 2.306, 2.262, 2.228, 2.201, 2.179, 2.160, 2.145,
         2.131, 2.120, 2.110, 2.101, 2.093, 2.086, 2.080, 2.074, 2.069, 2.064, 2.060, 2.056, 2.052, 2.048,
         2.045, 2.042]

# Estrategias de coordinación que se comparan (especificación de la segunda entrega §2). Cada una
# cambia solo la sección `politica` de la configuración; `base` es la línea base (= v0.1).
ESTRATEGIAS = {
    "base": {"politica": {"asignacion": "directa", "umbral_aviso": 1.0,
                          "atender_desde_bodega": False, "encadenar_servicios": False}},
    "subasta": {"politica": {"asignacion": "subasta", "umbral_aviso": 1.0,
                             "atender_desde_bodega": False, "encadenar_servicios": False}},
    "anticipada": {"politica": {"asignacion": "subasta", "umbral_aviso": 0.7,
                                "atender_desde_bodega": False, "encadenar_servicios": False}},
    "anticipada_plus": {"politica": {"asignacion": "subasta", "umbral_aviso": 0.7,
                                     "atender_desde_bodega": True, "encadenar_servicios": True}},
}


def aplicar_estrategia(config: dict, estrategia: str) -> dict:
    """Copia de `config` con la estrategia aplicada: mezcla cada sección de la estrategia sobre la de la
    configuración (las claves que la estrategia no menciona se conservan). Error claro si no existe."""
    if estrategia not in ESTRATEGIAS:
        raise ValueError(f"estrategia {estrategia!r} no es una de {list(ESTRATEGIAS)}")
    nueva = dict(config)
    for seccion, cambios in ESTRATEGIAS[estrategia].items():
        nueva[seccion] = {**(config.get(seccion) or {}), **cambios}
    return nueva


# Métricas que se resumen por defecto (escalares del nivel superior).
METRICAS_RESUMEN = [
    "tiempo_completacion", "tiempo_ocioso_cosechadora", "porcentaje_ocioso", "espera_promedio_por_ciclo",
    "distancia_total", "distancia_cosechadora_carro_promedio", "utilizacion_carro", "ticks_bloqueados",
    "num_ciclos",
]


def simulador_real(config: dict) -> dict:
    """Corre la simulación del equipo con una configuración dada como dict."""
    from harvest_sim.config import cargar_config
    from harvest_sim.simulacion import ejecutar

    with tempfile.TemporaryDirectory() as carpeta:
        ruta = Path(carpeta) / "config.json"
        ruta.write_text(json.dumps(config), encoding="utf-8")
        return ejecutar(cargar_config(ruta))


def combinaciones(barrido: dict[str, list] | None) -> list[dict]:
    """{"a": [1, 2], "b": [3]} -> [{"a": 1, "b": 3}, {"a": 2, "b": 3}] (producto cartesiano, en orden)."""
    if not barrido:
        return [{}]
    claves = list(barrido)
    return [dict(zip(claves, valores)) for valores in itertools.product(*(barrido[c] for c in claves))]


def metricas_escalares(metricas: dict) -> dict:
    """Las métricas del nivel superior que son un número (o None), sin `por_agente` ni diccionarios."""
    return {k: v for k, v in metricas.items() if v is None or (isinstance(v, (int, float)) and not isinstance(v, bool))}


def correr_experimento(escenarios: dict[str, dict], barrido: dict[str, list] | None = None, repeticiones: int = 1,
                       simulador: Callable[[dict], dict] | None = None) -> list[dict]:
    """Una fila por corrida: escenario, valores del barrido, repetición, seed y métricas escalares.

    En la repetición r la seed es `seed del escenario + r` (con una simulación determinista todas las
    repeticiones dan lo mismo, y el resumen lo dice).
    """
    if repeticiones < 1:
        raise ValueError("repeticiones debe ser >= 1")
    simulador = simulador or simulador_real
    filas = []
    for nombre, base in escenarios.items():
        for combo in combinaciones(barrido):
            for r in range(repeticiones):
                seed = base.get("seed", 0) + r
                config = {**base, **combo, "seed": seed, "nombre": base.get("nombre", nombre)}
                metricas = calcular_metricas(simulador(config))
                filas.append({"escenario": nombre, **combo, "repeticion": r, "seed": seed,
                              **metricas_escalares(metricas)})
    return filas


def intervalo_95(valores: list[float]) -> tuple[float, float, float]:
    """(media, desviación estándar muestral, medio ancho del intervalo de confianza del 95 %).
    Con un solo valor, la desviación y el intervalo son 0."""
    media = statistics.fmean(valores)
    if len(valores) < 2:
        return media, 0.0, 0.0
    desv = statistics.stdev(valores)
    gl = len(valores) - 1
    t = _T_95[gl - 1] if gl <= len(_T_95) else 1.96
    return media, desv, t * desv / math.sqrt(len(valores))


def resumen_por_grupo(filas: list[dict], parametros: list[str] | None = None,
                      metricas: list[str] | None = None) -> list[dict]:
    """Agrupa por escenario y valores de `parametros`; por cada métrica da media, desviación e IC 95 %.

    Columnas: escenario, <parámetros>, n, variacion ("sin variación" si todas las repeticiones dieron lo
    mismo), y <métrica>_media, <métrica>_desv, <métrica>_ic95 (4 decimales).
    """
    parametros = parametros or []
    metricas = metricas or [m for m in METRICAS_RESUMEN if any(m in f for f in filas)]
    grupos: dict[tuple, list[dict]] = {}
    for f in filas:
        grupos.setdefault((f["escenario"], *(f.get(p) for p in parametros)), []).append(f)
    resumen = []
    for clave, grupo in grupos.items():
        fila = {"escenario": clave[0], **dict(zip(parametros, clave[1:])), "n": len(grupo)}
        hay_variacion = False
        for m in metricas:
            valores = [g[m] for g in grupo if g.get(m) is not None]
            if not valores:
                fila.update({f"{m}_media": None, f"{m}_desv": None, f"{m}_ic95": None})
                continue
            media, desv, ic = intervalo_95(valores)
            hay_variacion |= desv > 0
            fila.update({f"{m}_media": round(media, 4), f"{m}_desv": round(desv, 4), f"{m}_ic95": round(ic, 4)})
        fila["variacion"] = "con variación" if hay_variacion else "sin variación"
        resumen.append(fila)
    return resumen


def escribir_csv(filas: list[dict], ruta: str | Path) -> Path:
    """Escribe las filas en CSV (columnas = unión de claves, en orden de aparición). Crea la carpeta."""
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    columnas: list[str] = []
    for f in filas:
        columnas += [c for c in f if c not in columnas]
    with open(ruta, "w", encoding="utf-8", newline="") as archivo:
        w = csv.writer(archivo, lineterminator="\n")
        w.writerow(columnas)
        for f in filas:
            w.writerow(["" if f.get(c) is None else f.get(c) for c in columnas])
    return ruta
