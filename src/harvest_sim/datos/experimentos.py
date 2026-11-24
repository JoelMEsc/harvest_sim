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


# Métricas que se resumen por defecto (escalares del nivel superior; las que falten se omiten).
METRICAS_RESUMEN = [
    "tiempo_completacion", "tiempo_ocioso_cosechadora", "porcentaje_ocioso", "espera_promedio_por_ciclo",
    "distancia_total", "distancia_cosechadora_carro_promedio", "utilizacion_carro", "ticks_bloqueados",
    "num_ciclos", "tiempo_ocioso_total", "combustible_usado", "restricciones", "respuesta_promedio",
    "costo_total",
]

# Sentido de cada métrica al comparar contra la línea base (decisión del 2026-11-16, ampliada el
# 2026-11-24): "menor" = menos es mejor; "mayor" = más es mejor; "neutro" = informativa.
SENTIDO_METRICAS = {
    "tiempo_completacion": "menor", "tick_fin_cosecha": "menor", "tiempo_ocioso_cosechadora": "menor",
    "porcentaje_ocioso": "menor", "tiempo_transfiriendo": "menor", "espera_promedio_por_ciclo": "menor",
    "num_ciclos": "neutro", "distancia_cosechadora": "menor", "distancia_carro": "menor", "distancia_total": "menor",
    "distancia_cosechadora_carro_promedio": "menor", "distancia_cosechadora_carro_minima": "neutro",
    "distancia_cosechadora_carro_maxima": "menor", "utilizacion_carro": "mayor", "ticks_bloqueados": "menor",
    "colisiones": "menor", "grano_cosechado_total": "mayor", "grano_total_entregado": "mayor",
    "grano_esperado_total": "neutro", "porcentaje_entregado": "mayor", "tiempo_ocioso_total": "menor",
    "combustible_usado": "menor", "combustible_comprado": "menor", "recargas": "neutro",
    "combustible_minimo": "neutro", "restricciones": "menor", "servicios": "neutro",
    "propuestas_por_servicio": "neutro", "respuesta_promedio": "menor", "costo_total": "menor",
}
VEREDICTOS = ("mejora", "empeora", "igual", "no concluyente", "informativa", "sin datos")


def sentido_de_metrica(metrica: str) -> str:
    """'menor', 'mayor' o 'neutro'. Los términos de J (`costo_<término>`) son 'menor'."""
    if metrica.startswith("costo_"):
        return "menor"
    return SENTIDO_METRICAS.get(metrica, "neutro")


def aplicar_cambios(config: dict, cambios: dict) -> dict:
    """Copia de `config` con los cambios aplicados; una clave con punto entra a una sección
    (`"politica.umbral_aviso": 0.6` cambia config["politica"]["umbral_aviso"])."""
    nueva = dict(config)
    for clave, valor in cambios.items():
        if "." in clave:
            seccion, campo = clave.split(".", 1)
            nueva[seccion] = aplicar_cambios(dict(nueva.get(seccion) or {}), {campo: valor})
        else:
            nueva[clave] = valor
    return nueva


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
    """Las métricas del nivel superior que son un número (o None), sin `por_agente` ni diccionarios, más
    cada término de J como `costo_<término>`."""
    escalares = {k: v for k, v in metricas.items()
                 if v is None or (isinstance(v, (int, float)) and not isinstance(v, bool))}
    for termino, valor in ((metricas.get("costo") or {}).get("terminos") or {}).items():
        escalares[f"costo_{termino}"] = valor
    return escalares


def _una_corrida(tarea: tuple) -> dict:
    """Corre una configuración y arma su fila (función de módulo para poder usar varios procesos)."""
    simulador, config, fila = tarea
    return {**fila, **metricas_escalares(calcular_metricas(simulador(config)))}


def correr_experimento(escenarios: dict[str, dict], barrido: dict[str, list] | None = None, repeticiones: int = 1,
                       simulador: Callable[[dict], dict] | None = None, estrategias: list[str] | None = None,
                       seeds: list[int] | None = None, procesos: int = 1) -> list[dict]:
    """Una fila por corrida: escenario, estrategia (si se dan), valores del barrido, repetición, seed y
    métricas escalares (con los términos de J).

    - `estrategias`: nombres de ESTRATEGIAS; cada una se aplica con `aplicar_estrategia`.
    - `barrido`: {parámetro: [valores]}; las claves con punto entran a una sección (`politica.umbral_aviso`).
    - Seeds: la lista `seeds` si se da (repeticiones = su largo); si no, `seed del escenario + r`.
      Con las mismas seeds para todas las estrategias, la comparación contra la base es pareada.
    - `procesos` > 1 corre en paralelo; el orden de las filas no cambia.
    """
    if seeds is not None:
        if not seeds:
            raise ValueError("seeds no puede estar vacía")
        repeticiones = len(seeds)
    if repeticiones < 1:
        raise ValueError("repeticiones debe ser >= 1")
    simulador = simulador or simulador_real
    tareas = []
    for nombre, base in escenarios.items():
        for estrategia in (estrategias or [None]):
            con_estrategia = aplicar_estrategia(base, estrategia) if estrategia else base
            for combo in combinaciones(barrido):
                for r in range(repeticiones):
                    seed = seeds[r] if seeds is not None else base.get("seed", 0) + r
                    config = {**aplicar_cambios(con_estrategia, combo), "seed": seed,
                              "nombre": base.get("nombre", nombre)}
                    fila = {"escenario": nombre, **({"estrategia": estrategia} if estrategia else {}),
                            **combo, "repeticion": r, "seed": seed}
                    tareas.append((simulador, config, fila))
    if procesos > 1:
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(max_workers=procesos) as ejecutor:
            return list(ejecutor.map(_una_corrida, tareas))
    return [_una_corrida(t) for t in tareas]


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
    parametros = list(parametros or [])
    if any("estrategia" in f for f in filas) and "estrategia" not in parametros:
        parametros.insert(0, "estrategia")
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


def comparar_contra_base(filas: list[dict], metricas: list[str] | None = None, base: str = "base",
                         parametros: list[str] | None = None) -> list[dict]:
    """Comparación **pareada por seed** de cada estrategia contra `base` (decisión D2 del 2026-11-24).

    Para cada escenario (y valores de `parametros`), estrategia y métrica: con las seeds que tienen las dos,
    diferencia = estrategia − base seed por seed; se reportan media base, media estrategia, diferencia
    media, IC 95 % de la diferencia (t de Student), cambio % y veredicto:
    - "informativa" si la métrica no tiene sentido de mejora; "sin datos" si no hay pares;
    - "igual" si todas las diferencias son 0; "no concluyente" si el IC cruza el 0;
    - si no, "mejora" o "empeora" según el sentido de la métrica.
    """
    parametros = parametros or []
    metricas = metricas or [m for m in METRICAS_RESUMEN if any(m in f for f in filas)]
    grupos: dict[tuple, dict[str, dict[int, dict]]] = {}
    for f in filas:
        clave = (f["escenario"], *(f.get(p) for p in parametros))
        grupos.setdefault(clave, {}).setdefault(f.get("estrategia"), {})[f["seed"]] = f
    comparacion = []
    for clave, por_estrategia in grupos.items():
        de_base = por_estrategia.get(base, {})
        for estrategia, por_seed in por_estrategia.items():
            if estrategia == base:
                continue
            for m in metricas:
                pares = [(de_base[s][m], por_seed[s][m]) for s in sorted(por_seed)
                         if s in de_base and de_base[s].get(m) is not None and por_seed[s].get(m) is not None]
                fila = {"escenario": clave[0], **dict(zip(parametros, clave[1:])), "estrategia": estrategia,
                        "metrica": m, "pares": len(pares)}
                sentido = sentido_de_metrica(m)
                if not pares:
                    fila["veredicto"] = "sin datos" if sentido != "neutro" else "informativa"
                    comparacion.append(fila)
                    continue
                difs = [b - a for a, b in pares]
                media_base = statistics.fmean(a for a, _ in pares)
                diferencia, _, ic = intervalo_95(difs)
                if sentido == "neutro":
                    veredicto = "informativa"
                elif all(d == 0 for d in difs):
                    veredicto = "igual"
                elif diferencia - ic <= 0 <= diferencia + ic:
                    veredicto = "no concluyente"
                else:
                    veredicto = "mejora" if (diferencia < 0) == (sentido == "menor") else "empeora"
                fila.update({
                    "media_base": round(media_base, 4),
                    "media_estrategia": round(statistics.fmean(b for _, b in pares), 4),
                    "diferencia": round(diferencia, 4), "ic95": round(ic, 4),
                    "cambio_pct": round(100 * diferencia / media_base, 2) if media_base else None,
                    "veredicto": veredicto,
                })
                comparacion.append(fila)
    return comparacion


def ablacion_costo(filas: list[dict], parametros: list[str] | None = None) -> list[dict]:
    """Ablación de J (especificación §11): por escenario, el orden de las estrategias por J medio (menor
    primero) con todos los términos y con cada término quitado (peso 0). `cambia_orden` dice si quitar ese
    término cambia qué estrategia es mejor. Usa las columnas `costo_total` y `costo_<término>`."""
    parametros = parametros or []
    terminos = sorted({c[len("costo_"):] for f in filas for c in f if c.startswith("costo_") and c != "costo_total"})
    grupos: dict[tuple, dict[str, list[dict]]] = {}
    for f in filas:
        if f.get("costo_total") is None:
            continue
        clave = (f["escenario"], *(f.get(p) for p in parametros))
        grupos.setdefault(clave, {}).setdefault(f.get("estrategia"), []).append(f)
    salida = []
    for clave, por_estrategia in grupos.items():
        def orden(sin_termino=None):
            medias = {}
            for estrategia, grupo in por_estrategia.items():
                valores = [g["costo_total"] - (g.get(f"costo_{sin_termino}") or 0 if sin_termino else 0)
                           for g in grupo]
                medias[estrategia] = round(statistics.fmean(valores), 4)
            return sorted(medias, key=lambda e: (medias[e], str(e))), medias
        completo, medias = orden()
        salida.append({"escenario": clave[0], **dict(zip(parametros, clave[1:])), "sin_termino": "ninguno",
                       "orden": " < ".join(map(str, completo)), "cambia_orden": False,
                       **{f"J_{e}": medias[e] for e in completo}})
        for termino in terminos:
            orden_t, medias_t = orden(termino)
            salida.append({"escenario": clave[0], **dict(zip(parametros, clave[1:])), "sin_termino": termino,
                           "orden": " < ".join(map(str, orden_t)), "cambia_orden": orden_t != completo,
                           **{f"J_{e}": medias_t[e] for e in orden_t}})
    return salida


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
