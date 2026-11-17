"""Línea de tiempo: el estado de cada tick, armado en UNA sola pasada por el trace.  [Joel]

El trace solo guarda lo que cambia. Para saber cómo estaba todo en el tick t hay que partir del tick 0 y
aplicar los cambios uno por uno: eso es una "pasada". Antes, cada métrica y cada gráfica hacía su propia
pasada (unas 9 por trace) y copiaba la lista completa de celdas cosechadas en cada tick (costo ticks x
celdas). Ahora se hace una sola, sin copias, y todo lo demás lee de aquí:

    linea = linea_de_tiempo(trace)          # una pasada
    linea.estado["cosechadora_1"][30]       # estado en el tick 30
    calcular_metricas(linea); series_temporales(linea)   # reutilizan la misma línea

`reconstruir(trace)` sigue disponible (la usan las pruebas de integración) y se construye sobre esta.
"""

from __future__ import annotations

import copy
from collections.abc import Iterator
from dataclasses import dataclass, field


@dataclass(frozen=True)
class LineaDeTiempo:
    """Valores por tick (listas de largo total_ticks + 1, indexadas por el número de tick)."""

    total_ticks: int
    mundo: dict
    agentes: list[dict]                               # el catálogo del trace (y los ids que solo aparecen en eventos)
    pose: dict[str, list[tuple[int, int, str] | None]]  # (x, y, orientación) de cada agente
    estado: dict[str, list[str | None]]
    carga: dict[str, list[int | None]]
    celdas_nuevas: list[list[tuple[int, int]]]        # celdas cosechadas EN ese tick (casi siempre vacío)
    cosechadas: list[int]                             # celdas cosechadas hasta ese tick, inclusive
    entregado: list[int]                              # grano en la bodega
    en_transito: list[tuple[int, ...]]                # ids de mensajes enviados y aún no entregados
    eventos: list[list[dict]]                         # los eventos de cada tick (referencias al trace, sin copiar)
    _por_tipo: dict[str, list[str]] = field(default_factory=dict, repr=False)

    @property
    def ticks(self) -> range:
        return range(self.total_ticks + 1)

    @property
    def num_ticks(self) -> int:
        return self.total_ticks + 1

    def ids(self, tipo: str | None = None) -> list[str]:
        """Ids de los agentes (de un tipo, si se indica), en el orden del catálogo."""
        if tipo is None:
            return list(self.pose)
        return list(self._por_tipo.get(tipo, []))

    def celda(self, agente: str, tick: int) -> tuple[int, int] | None:
        p = self.pose[agente][tick]
        return None if p is None else (p[0], p[1])


def _revisar_orden(trace: dict) -> None:
    total = trace["meta"]["total_ticks"]
    anterior = -1
    for t in trace["ticks"]:
        if t["tick"] <= anterior or t["tick"] > total:
            raise ValueError(f"ticks fuera de orden o mayores que total_ticks: {t['tick']}")
        anterior = t["tick"]


def linea_de_tiempo(fuente) -> LineaDeTiempo:
    """Arma la línea de tiempo de un trace en una pasada. Si ya recibe una LineaDeTiempo, la devuelve."""
    if isinstance(fuente, LineaDeTiempo):
        return fuente
    trace = fuente
    _revisar_orden(trace)
    total = trace["meta"]["total_ticks"]
    catalogo = list(trace.get("agentes", []))
    ids = [a["id"] for a in catalogo]
    for t in trace["ticks"]:  # agentes que aparecen en eventos sin estar en el catálogo
        for e in t["cambios"]:
            if e.get("tipo") == "AGENTE" and e["id"] not in ids:
                ids.append(e["id"])
    por_tipo: dict[str, list[str]] = {}
    for a in catalogo:
        por_tipo.setdefault(a.get("tipo"), []).append(a["id"])

    actual = {a: {"pose": None, "estado": None, "carga": None} for a in ids}
    pose = {a: [] for a in ids}
    estado = {a: [] for a in ids}
    carga = {a: [] for a in ids}
    celdas_nuevas, cosechadas, entregado, en_transito, eventos = [], [], [], [], []
    n_celdas = total_entregado = 0
    transito: list[int] = []
    ticks = trace["ticks"]
    i = 0
    for tick in range(total + 1):
        evs: list[dict] = []
        if i < len(ticks) and ticks[i]["tick"] == tick:
            evs = ticks[i]["cambios"]
            i += 1
        nuevas = []
        for e in evs:
            tipo = e["tipo"]
            if tipo == "AGENTE":
                a = actual[e["id"]]
                s = e["set"]
                if "pose" in s:
                    a["pose"] = (s["pose"]["x"], s["pose"]["y"], s["pose"]["orientacion"])
                if "estado" in s:
                    a["estado"] = s["estado"]
                if "carga" in s:
                    a["carga"] = s["carga"]
            elif tipo == "CELDA_COSECHADA":
                nuevas.append((e["celda"][0], e["celda"][1]))
            elif tipo == "DEPOSITO":
                total_entregado = e["entregado_total"]
            elif tipo == "MENSAJE_ENVIADO":
                transito.append(e["id"])
            elif tipo == "MENSAJE_ENTREGADO" and e["id"] in transito:
                transito.remove(e["id"])
            # BLOQUEO no cambia el estado: queda en `eventos` para las métricas
        for a in ids:
            pose[a].append(actual[a]["pose"])
            estado[a].append(actual[a]["estado"])
            carga[a].append(actual[a]["carga"])
        n_celdas += len(nuevas)
        celdas_nuevas.append(nuevas)
        cosechadas.append(n_celdas)
        entregado.append(total_entregado)
        en_transito.append(tuple(transito))
        eventos.append(evs)

    return LineaDeTiempo(
        total_ticks=total, mundo=trace.get("mundo", {}), agentes=catalogo, pose=pose, estado=estado,
        carga=carga, celdas_nuevas=celdas_nuevas, cosechadas=cosechadas, entregado=entregado,
        en_transito=en_transito, eventos=eventos, _por_tipo=por_tipo,
    )


def reconstruir(fuente, copiar: bool = True) -> Iterator[dict]:
    """Estado completo de cada tick 0..meta.total_ticks (incluidos los ticks sin cambios).

    Cada elemento:
        {"tick": t,
         "agentes": {id: {"pose": {x, y, orientacion}, "estado", "carga"}},
         "celdas_cosechadas": [[x, y], ...],      # en el orden en que se cosecharon
         "entregado_total": n,
         "mensajes_en_transito": [id, ...],       # enviados y aún no entregados
         "eventos": [...]}                        # los eventos de ese tick ([] si se omitió)

    Con `copiar=True` (por defecto) cada elemento es una copia independiente. Con `copiar=False`,
    `celdas_cosechadas` y `eventos` se comparten entre ticks (más rápido; no los modifiques).
    """
    linea = linea_de_tiempo(fuente)
    celdas: list[list[int]] = []
    for t in linea.ticks:
        agentes = {}
        for a in linea.ids():
            p, est, c = linea.pose[a][t], linea.estado[a][t], linea.carga[a][t]
            campos = {}
            if p is not None:
                campos["pose"] = {"x": p[0], "y": p[1], "orientacion": p[2]}
            if est is not None:
                campos["estado"] = est
            if c is not None:
                campos["carga"] = c
            if campos:
                agentes[a] = campos
        celdas.extend([x, y] for x, y in linea.celdas_nuevas[t])
        yield {
            "tick": t,
            "agentes": agentes,
            "celdas_cosechadas": [list(c) for c in celdas] if copiar else celdas,
            "entregado_total": linea.entregado[t],
            "mensajes_en_transito": list(linea.en_transito[t]),
            "eventos": copy.deepcopy(linea.eventos[t]) if copiar else linea.eventos[t],
        }
