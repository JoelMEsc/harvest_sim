"""Métricas, series por tick y mapas por celda, calculadas desde el log.  [Joel]

Funcionan igual con cualquier número de agentes (regla registrada en docs/decisiones.md):

- Magnitudes de cada agente (ocio, transferencia, distancia recorrida, utilización, espera por ciclo):
  el nivel superior de las métricas lleva el PROMEDIO entre los agentes de ese tipo, y el detalle de
  cada uno va en `por_agente[agent_id]`.
- Magnitudes del sistema (completación, fin de la cosecha, distancia total, bloqueos, colisiones,
  ciclos, mensajes, grano): un solo valor (total).
- Distancia cosechadora–carro: para cada cosechadora, en cada tick, la distancia Manhattan (en celdas)
  al carro MÁS CERCANO.

Todas aceptan un trace o una LineaDeTiempo (si reciben el trace, arman la línea una sola vez). Los
promedios se redondean a 4 decimales y, si son enteros, se dejan como enteros (23, no 23.0).
"""

from __future__ import annotations

from .campo import grano_esperado
from .formato import (
    CARRO,
    COSECHADORA,
    EN_BASE,
    LLENA,
    LLENA_ESPERANDO,
    TRANSFERENCIA_TERMINADA,
    TRANSFIRIENDO,
)
from .linea_de_tiempo import LineaDeTiempo, linea_de_tiempo


def _numero(valor, decimales: int = 4):
    """Redondea y deja como entero si no tiene parte decimal."""
    if valor is None:
        return None
    valor = round(valor, decimales)
    return int(valor) if float(valor).is_integer() else valor


def _promedio(valores, decimales: int = 4):
    valores = [v for v in valores if v is not None]
    return _numero(sum(valores) / len(valores), decimales) if valores else None


def _manhattan(a, b) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _distancia_recorrida(linea: LineaDeTiempo, agente: str) -> int:
    """Ticks en que la celda (x, y) del agente cambió respecto al tick anterior (girar no cuenta)."""
    return sum(1 for t in range(1, linea.num_ticks) if linea.celda(agente, t) != linea.celda(agente, t - 1))


def _ticks_por_estado(linea: LineaDeTiempo, agente: str) -> dict[str, int]:
    cuenta: dict[str, int] = {}
    for estado in linea.estado[agente]:
        if estado is not None:
            cuenta[estado] = cuenta.get(estado, 0) + 1
    return cuenta


def _rachas(linea: LineaDeTiempo, agente: str, estado: str) -> list[int]:
    """Largo de cada racha consecutiva de ticks en `estado`."""
    rachas, racha = [], 0
    for e in linea.estado[agente]:
        if e == estado:
            racha += 1
        elif racha:
            rachas.append(racha)
            racha = 0
    if racha:
        rachas.append(racha)
    return rachas


def distancias_al_carro(linea: LineaDeTiempo, cosechadora: str) -> list[int | None]:
    """Por tick, distancia Manhattan de la cosechadora al carro más cercano (None si no hay carros)."""
    carros = linea.ids(CARRO)
    salida = []
    for t in linea.ticks:
        h = linea.celda(cosechadora, t)
        celdas = [linea.celda(c, t) for c in carros]
        celdas = [c for c in celdas if c is not None]
        salida.append(min(_manhattan(h, c) for c in celdas) if h is not None and celdas else None)
    return salida


def _colisiones(linea: LineaDeTiempo) -> int:
    """Ticks con dos agentes en la misma celda o intercambiando posiciones."""
    ids = linea.ids()
    total = 0
    for t in linea.ticks:
        actual = [(a, linea.celda(a, t)) for a in ids]
        actual = [(a, c) for a, c in actual if c is not None]
        celdas = [c for _, c in actual]
        hubo = len(set(celdas)) < len(celdas)
        if not hubo and t > 0:
            for i, (a, ca) in enumerate(actual):
                for b, cb in actual[i + 1:]:
                    if linea.celda(a, t - 1) == cb and linea.celda(b, t - 1) == ca:
                        hubo = True
        total += hubo
    return total


def calcular_metricas(fuente) -> dict:
    """Métricas de una corrida, A PARTIR DEL LOG (no modifica el trace).

    Los ticks que se cuentan son 0..meta.total_ticks, ambos incluidos (T = total_ticks + 1).
    Nivel superior (promedio = entre los agentes de ese tipo; total = del sistema):
    - agentes: {"cosechadoras": n, "carros": m}.
    - tiempo_completacion: meta.total_ticks.
    - tick_fin_cosecha: tick del último MENSAJE_ENVIADO TRANSFERENCIA_TERMINADA (None si no hay).
    - tiempo_ocioso_cosechadora (promedio): ticks en LLENA_ESPERANDO.
    - porcentaje_ocioso (promedio): ticks ociosos entre T, en % (2 decimales).
    - tiempo_transfiriendo (promedio): ticks en TRANSFIRIENDO.
    - espera_promedio_por_ciclo: largo medio de las rachas de LLENA_ESPERANDO de todas las cosechadoras.
    - num_ciclos (total): mensajes LLENA enviados.
    - distancia_cosechadora / distancia_carro (promedio): ticks en que la celda del agente cambió.
    - distancia_total (total): suma de la distancia de todos los agentes.
    - distancia_cosechadora_carro_promedio / _minima / _maxima: sobre cada cosechadora y cada tick, al carro más cercano.
    - utilizacion_carro (promedio): fracción de T con el carro fuera de EN_BASE (4 decimales).
    - ticks_bloqueados (total): eventos BLOQUEO.
    - colisiones (total): ticks con dos agentes en la misma celda o intercambiando posiciones.
    - mensajes_enviados (total): {tipo_mensaje: n}.
    - grano_cosechado_total, grano_total_entregado, grano_esperado_total (campo.grano_esperado) y
      porcentaje_entregado (entregado / esperado, en %, 2 decimales; None si no se conoce el esperado).
    - por_agente: {agent_id: {...}} con el detalle de cada agente (incluye ticks_por_estado y espera_por_ciclo).
    """
    linea = linea_de_tiempo(fuente)
    T = linea.num_ticks
    cosechadoras, carros = linea.ids(COSECHADORA), linea.ids(CARRO)
    tipo_de = {a["id"]: a.get("tipo") for a in linea.agentes}

    bloqueos = {a: 0 for a in linea.ids()}
    mensajes: dict[str, int] = {}
    llenas_por_agente: dict[str, int] = {}
    terminadas = []
    for t in linea.ticks:
        for ev in linea.eventos[t]:
            if ev["tipo"] == "BLOQUEO":
                bloqueos[ev["agente"]] = bloqueos.get(ev["agente"], 0) + 1
            elif ev["tipo"] == "MENSAJE_ENVIADO":
                mensajes[ev["tipo_mensaje"]] = mensajes.get(ev["tipo_mensaje"], 0) + 1
                if ev["tipo_mensaje"] == LLENA:
                    llenas_por_agente[ev["de"]] = llenas_por_agente.get(ev["de"], 0) + 1
                elif ev["tipo_mensaje"] == TRANSFERENCIA_TERMINADA:
                    terminadas.append(t)

    por_agente: dict[str, dict] = {}
    todas_las_esperas: list[int] = []
    todas_las_distancias: list[int] = []
    for a in linea.ids():
        tipo = tipo_de.get(a)
        estados = _ticks_por_estado(linea, a)
        detalle: dict = {"tipo": tipo}
        if tipo == COSECHADORA:
            ocioso = estados.get(LLENA_ESPERANDO, 0)
            esperas = _rachas(linea, a, LLENA_ESPERANDO)
            al_carro = [d for d in distancias_al_carro(linea, a) if d is not None]
            todas_las_esperas += esperas
            todas_las_distancias += al_carro
            detalle.update(
                tiempo_ocioso=ocioso,
                porcentaje_ocioso=round(100 * ocioso / T, 2),
                tiempo_transfiriendo=estados.get(TRANSFIRIENDO, 0),
                num_ciclos=llenas_por_agente.get(a, 0),
                espera_por_ciclo=esperas,
                distancia=_distancia_recorrida(linea, a),
                distancia_al_carro_promedio=_promedio(al_carro),
            )
        elif tipo == CARRO:
            detalle.update(
                distancia=_distancia_recorrida(linea, a),
                utilizacion=round(1 - estados.get(EN_BASE, 0) / T, 4),
            )
        else:
            detalle.update(distancia=_distancia_recorrida(linea, a))
        detalle.update(ticks_bloqueados=bloqueos.get(a, 0), ticks_por_estado=estados)
        por_agente[a] = detalle

    def de(ids, clave):
        return [por_agente[a][clave] for a in ids]

    entregado = linea.entregado[-1]
    esperado = grano_esperado(linea.mundo)
    grano = linea.mundo.get("grano_por_celda", 1)
    ocioso_total = sum(de(cosechadoras, "tiempo_ocioso"))
    return {
        "agentes": {"cosechadoras": len(cosechadoras), "carros": len(carros)},
        "tiempo_completacion": linea.total_ticks,
        "tick_fin_cosecha": max(terminadas) if terminadas else None,
        "tiempo_ocioso_cosechadora": _promedio(de(cosechadoras, "tiempo_ocioso")),
        "porcentaje_ocioso": round(100 * ocioso_total / (T * len(cosechadoras)), 2) if cosechadoras else None,
        "tiempo_transfiriendo": _promedio(de(cosechadoras, "tiempo_transfiriendo")),
        "espera_promedio_por_ciclo": _promedio(todas_las_esperas),
        "num_ciclos": mensajes.get(LLENA, 0),
        "distancia_cosechadora": _promedio(de(cosechadoras, "distancia")),
        "distancia_carro": _promedio(de(carros, "distancia")),
        "distancia_total": sum(d["distancia"] for d in por_agente.values()),
        "distancia_cosechadora_carro_promedio": _promedio(todas_las_distancias),
        "distancia_cosechadora_carro_minima": min(todas_las_distancias) if todas_las_distancias else None,
        "distancia_cosechadora_carro_maxima": max(todas_las_distancias) if todas_las_distancias else None,
        "utilizacion_carro": _promedio(de(carros, "utilizacion")),
        "ticks_bloqueados": sum(bloqueos.values()),
        "colisiones": _colisiones(linea),
        "mensajes_enviados": mensajes,
        "grano_cosechado_total": linea.cosechadas[-1] * grano,
        "grano_total_entregado": entregado,
        "grano_esperado_total": esperado,
        "porcentaje_entregado": round(100 * entregado / esperado, 2) if esperado else None,
        "por_agente": por_agente,
    }


def series_temporales(fuente) -> dict:
    """Series por tick (0..meta.total_ticks), una lista con un valor por tick:

    - tick.
    - ocioso_acumulado: ticks en LLENA_ESPERANDO acumulados hasta ese tick, PROMEDIO por cosechadora.
    - distancia_cosechadora_carro: distancia de cada cosechadora a su carro más cercano, PROMEDIO.
    - cosechado_acumulado: grano cosechado hasta ese tick.
    - en_transito: grano que llevan los agentes (suma de las cargas).
    - entregado_en_bodega: grano acumulado en la bodega (cosechado = en tránsito + en bodega).
    - bloqueos_acumulados: eventos BLOQUEO hasta ese tick (total).
    - por_agente: {id: {"carga": [...]}}; las cosechadoras además llevan "ocioso_acumulado" y "distancia_al_carro".
    """
    linea = linea_de_tiempo(fuente)
    cosechadoras = linea.ids(COSECHADORA)
    grano = linea.mundo.get("grano_por_celda", 1)
    por_agente: dict[str, dict] = {a: {"carga": [c or 0 for c in linea.carga[a]]} for a in linea.ids()}
    for h in cosechadoras:
        acumulado, n = [], 0
        for e in linea.estado[h]:
            n += e == LLENA_ESPERANDO
            acumulado.append(n)
        por_agente[h]["ocioso_acumulado"] = acumulado
        por_agente[h]["distancia_al_carro"] = distancias_al_carro(linea, h)

    bloqueos, n = [], 0
    for t in linea.ticks:
        n += sum(1 for ev in linea.eventos[t] if ev["tipo"] == "BLOQUEO")
        bloqueos.append(n)
    return {
        "tick": list(linea.ticks),
        "ocioso_acumulado": [_promedio([por_agente[h]["ocioso_acumulado"][t] for h in cosechadoras])
                             for t in linea.ticks],
        "distancia_cosechadora_carro": [_promedio([por_agente[h]["distancia_al_carro"][t] for h in cosechadoras])
                                        for t in linea.ticks],
        "cosechado_acumulado": [c * grano for c in linea.cosechadas],
        "en_transito": [sum(por_agente[a]["carga"][t] for a in linea.ids()) for t in linea.ticks],
        "entregado_en_bodega": list(linea.entregado),
        "bloqueos_acumulados": bloqueos,
        "por_agente": por_agente,
    }


CRITERIOS_MAPA = ("espera", "trafico")


def mapa_por_celda(fuente, criterio: str) -> list[list[int]]:
    """Matriz alto x ancho (fila = y, columna = x) con un conteo por celda:

    - "espera": ticks que las cosechadoras pasan en LLENA_ESPERANDO en cada celda (dónde espera).
    - "trafico": veces que un agente ENTRA a cada celda (la del tick 0 cuenta como entrada).
    """
    if criterio not in CRITERIOS_MAPA:
        raise ValueError(f"criterio {criterio!r} no es uno de {list(CRITERIOS_MAPA)}")
    linea = linea_de_tiempo(fuente)
    ancho, alto = linea.mundo.get("ancho"), linea.mundo.get("alto")
    if not ancho or not alto:
        raise ValueError("el mundo del trace no trae ancho y alto")
    mapa = [[0] * ancho for _ in range(alto)]
    if criterio == "espera":
        for h in linea.ids(COSECHADORA):
            for t in linea.ticks:
                c = linea.celda(h, t)
                if linea.estado[h][t] == LLENA_ESPERANDO and c is not None:
                    mapa[c[1]][c[0]] += 1
    else:
        for a in linea.ids():
            for t in linea.ticks:
                c = linea.celda(a, t)
                if c is not None and (t == 0 or c != linea.celda(a, t - 1)):
                    mapa[c[1]][c[0]] += 1
    return mapa
