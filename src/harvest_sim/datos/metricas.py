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

from .campo import celdas_de_campo, grano_esperado, tiene_mapa
from .formato import (
    ACEPTACION,
    CARRO,
    COSECHADORA,
    EN_BASE,
    LLENA_ESPERANDO,
    PROPUESTA,
    RECHAZO,
    SOLICITUD_SERVICIO,
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
    - num_ciclos (total): transferencias terminadas (TRANSFERENCIA_TERMINADA enviados); en la línea base es igual
      al número de LLENA, y sigue valiendo con la subasta.
    - distancia_cosechadora / distancia_carro (promedio): ticks en que la celda del agente cambió.
    - distancia_total (total): suma de la distancia de todos los agentes.
    - distancia_cosechadora_carro_promedio / _minima / _maxima: sobre cada cosechadora y cada tick, al carro más cercano.
    - utilizacion_carro (promedio): fracción de T con el carro fuera de EN_BASE (4 decimales).
    - ticks_bloqueados (total): eventos BLOQUEO.
    - colisiones (total): ticks con dos agentes en la misma celda o intercambiando posiciones.
    - mensajes_enviados (total): {tipo_mensaje: n}.
    - grano_cosechado_total, grano_total_entregado, grano_esperado_total (campo.grano_esperado) y
      porcentaje_entregado (entregado / esperado, en %, 2 decimales; None si no se conoce el esperado).
      El grano cosechado suma `cantidad` de cada CELDA_COSECHADA (2.2) o el rendimiento de la celda.
    Segunda entrega (decisiones del 2026-11-24; None o vacío si el trace no trae esos datos):
    - tiempo_ocioso_total: ticks en LLENA_ESPERANDO sumados entre todas las cosechadoras (lo usa J).
    - combustible_usado, combustible_comprado, recargas, combustible_minimo (totales; por agente en por_agente):
      usado = inicial − final + recargado; comprado = nivel inicial + recargado (se paga lo que se carga);
      mínimo = el menor nivel al final de un tick (el log no ve el nivel dentro del tick).
    - restricciones (total) y restricciones_por_regla ({regla: n}).
    - servicios (llamadas SOLICITUD_SERVICIO distintas), propuestas_por_servicio (media), rechazos_por_motivo,
      respuesta_promedio (ticks desde la primera llamada de un servicio hasta que su cosechadora empieza a
      transferir).
    - costo: {"pesos", "terminos": {nombre: peso · valor}, "total"} y costo_total (J, especificación §11).
    - por_agente: {agent_id: {...}} con el detalle de cada agente (incluye ticks_por_estado y espera_por_ciclo).
    Despacho aprendido (solo si el log trae eventos DECISION_DESPACHO; docs/especificacion_mejoras.md §M1):
    - decisiones_despacho (total), pedidos_tabla (pidió porque la tabla lo prefería), pedidos_respaldo (pidió
      por el umbral, en un estado que la tabla no conoce) y cliffs_despacho (la tolva se llenó sin carro).
    Terreno real (solo si el mundo trae mapa, trace 2.3; docs/especificacion_terreno.md §13):
    - metros_carro_camino, metros_carro_rastrojo, metros_carro_cultivo (totales de los carros) y
      porcentaje_carro_rastrojo: compactación del suelo (ver `suelo_de_carros`).
    - entradas_de_lado, pasos_sobre_cultivo, vueltas_instantaneas y eficiencia_campo: qué tan realista es el
      movimiento de las cosechadoras respecto a las hileras (ver `movimiento_cosechadoras`).
    """
    linea = linea_de_tiempo(fuente)
    T = linea.num_ticks
    cosechadoras, carros = linea.ids(COSECHADORA), linea.ids(CARRO)
    tipo_de = {a["id"]: a.get("tipo") for a in linea.agentes}

    bloqueos = {a: 0 for a in linea.ids()}
    mensajes: dict[str, int] = {}
    ciclos_por_agente: dict[str, int] = {}
    terminadas = []
    restricciones_por_agente: dict[str, int] = {}
    restricciones_por_regla: dict[str, int] = {}
    recargado: dict[str, float] = {}
    recargas_por_agente: dict[str, int] = {}
    llamadas: dict[str, tuple[int, str]] = {}   # servicio -> (tick de la primera llamada, cosechadora)
    propuestas = 0
    rechazos_por_motivo: dict[str, int] = {}
    ganados: dict[str, int] = {}
    decisiones: dict[tuple[str, str], int] = {}  # (accion, origen) -> n (M1, DECISION_DESPACHO)
    for t in linea.ticks:
        for ev in linea.eventos[t]:
            if ev["tipo"] == "BLOQUEO":
                bloqueos[ev["agente"]] = bloqueos.get(ev["agente"], 0) + 1
            elif ev["tipo"] == "RESTRICCION":
                restricciones_por_agente[ev["agente"]] = restricciones_por_agente.get(ev["agente"], 0) + 1
                restricciones_por_regla[ev["regla"]] = restricciones_por_regla.get(ev["regla"], 0) + 1
            elif ev["tipo"] == "DECISION_DESPACHO":
                par = (ev["accion"], ev["origen"])
                decisiones[par] = decisiones.get(par, 0) + 1
            elif ev["tipo"] == "RECARGA":
                recargado[ev["agente"]] = recargado.get(ev["agente"], 0) + ev["cantidad"]
                recargas_por_agente[ev["agente"]] = recargas_por_agente.get(ev["agente"], 0) + 1
            elif ev["tipo"] == "MENSAJE_ENVIADO":
                tipo_m = ev["tipo_mensaje"]
                mensajes[tipo_m] = mensajes.get(tipo_m, 0) + 1
                if tipo_m == TRANSFERENCIA_TERMINADA:
                    terminadas.append(t)
                    ciclos_por_agente[ev["de"]] = ciclos_por_agente.get(ev["de"], 0) + 1
                elif tipo_m == SOLICITUD_SERVICIO:
                    llamadas.setdefault(ev["payload"].get("servicio"), (t, ev["de"]))
                elif tipo_m == PROPUESTA:
                    propuestas += 1
                elif tipo_m == RECHAZO:
                    motivo = ev["payload"].get("motivo")
                    rechazos_por_motivo[motivo] = rechazos_por_motivo.get(motivo, 0) + 1
                elif tipo_m == ACEPTACION:
                    ganados[ev["a"]] = ganados.get(ev["a"], 0) + 1

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
                num_ciclos=ciclos_por_agente.get(a, 0),
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
        if tipo == CARRO and llamadas:
            detalle["servicios_ganados"] = ganados.get(a, 0)
        detalle.update(ticks_bloqueados=bloqueos.get(a, 0), ticks_por_estado=estados)
        detalle.update(_combustible(linea, a, recargado.get(a, 0.0), recargas_por_agente.get(a, 0)))
        if restricciones_por_agente or restricciones_por_regla:
            detalle["restricciones"] = restricciones_por_agente.get(a, 0)
        por_agente[a] = detalle

    def de(ids, clave):
        return [por_agente[a][clave] for a in ids]

    entregado = linea.entregado[-1]
    esperado = grano_esperado(linea.mundo)
    ocioso_total = sum(de(cosechadoras, "tiempo_ocioso"))
    con_combustible = [d for d in por_agente.values() if d.get("combustible_usado") is not None]

    def total(clave, decimales=2):
        return round(sum(d[clave] for d in con_combustible), decimales) if con_combustible else None

    respuestas = []
    for servicio, (tick_llamada, cosechadora) in llamadas.items():
        estados_h = linea.estado.get(cosechadora, [])
        inicio = next((t for t in range(tick_llamada + 1, linea.num_ticks)
                       if estados_h[t] == TRANSFIRIENDO and estados_h[t - 1] != TRANSFIRIENDO), None)
        if inicio is not None:
            respuestas.append(inicio - tick_llamada)
    metricas = {
        "agentes": {"cosechadoras": len(cosechadoras), "carros": len(carros)},
        "tiempo_completacion": linea.total_ticks,
        "tick_fin_cosecha": max(terminadas) if terminadas else None,
        "tiempo_ocioso_cosechadora": _promedio(de(cosechadoras, "tiempo_ocioso")),
        "porcentaje_ocioso": round(100 * ocioso_total / (T * len(cosechadoras)), 2) if cosechadoras else None,
        "tiempo_transfiriendo": _promedio(de(cosechadoras, "tiempo_transfiriendo")),
        "espera_promedio_por_ciclo": _promedio(todas_las_esperas),
        "num_ciclos": len(terminadas),
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
        "grano_cosechado_total": linea.grano_cosechado[-1],
        "grano_total_entregado": entregado,
        "grano_esperado_total": esperado,
        "porcentaje_entregado": round(100 * entregado / esperado, 2) if esperado else None,
        "tiempo_ocioso_total": ocioso_total,
        "combustible_usado": total("combustible_usado"),
        "combustible_comprado": total("combustible_comprado"),
        "recargas": sum(d["recargas"] for d in con_combustible) if con_combustible else None,
        "combustible_minimo": (min(d["combustible_minimo"] for d in con_combustible) if con_combustible else None),
        "restricciones": sum(restricciones_por_regla.values()),
        "restricciones_por_regla": restricciones_por_regla,
        "servicios": len(llamadas) if llamadas else None,
        "propuestas_por_servicio": _numero(propuestas / len(llamadas)) if llamadas else None,
        "rechazos_por_motivo": rechazos_por_motivo,
        "respuesta_promedio": _promedio(respuestas),
    }
    if tiene_mapa(linea.mundo):
        metricas.update(suelo_de_carros(linea))
        metricas.update(movimiento_cosechadoras(linea))
    if decisiones:
        metricas.update(
            decisiones_despacho=sum(decisiones.values()),
            pedidos_tabla=decisiones.get(("pedir", "tabla"), 0),
            pedidos_respaldo=decisiones.get(("pedir", "umbral"), 0),
            cliffs_despacho=decisiones.get(("pedir", "forzada"), 0),
        )
    metricas["costo"] = costo_j(metricas, linea.config)
    metricas["costo_total"] = metricas["costo"]["total"]
    metricas["por_agente"] = por_agente
    return metricas


def movimiento_cosechadoras(fuente) -> dict:
    """Realismo del movimiento de las cosechadoras respecto a las hileras, desde el log
    (plan de hileras y rutas, fase H0). Las hileras van a lo largo del eje x de la cuadrícula: con mapa, la
    cuadrícula está girada con el rumbo de los surcos; sin mapa, es la convención de la serpentina.

    - entradas_de_lado: la cosechadora entra de lado (cambia de y) a una celda y la cosecha en ese tick, o sea,
      corta una hilera con el cabezal atravesado. Con hileras reales debe ser 0.
    - pasos_sobre_cultivo: entra a una celda de campo todavía en pie y no la cosecha (la pisa). Debe ser 0.
    - vueltas_instantaneas: invierte su rumbo (E↔O, N↔S) entre dos movimientos seguidos sin haberse detenido
      al menos 2 ticks a dar la vuelta (una vuelta en K): una vuelta de 180° con radio 0 y sin tiempo. Debe ser 0.
    - eficiencia_campo: celdas cosechadas / ticks en que alguna cosechadora estuvo fuera de la base (en %).
    """
    linea = linea_de_tiempo(fuente)
    campo = celdas_de_campo(linea.mundo)
    cosechadoras = linea.ids(COSECHADORA)
    cosechadas: set[tuple[int, int]] = set()
    lado = pisadas = vueltas = activos = 0
    rumbo_anterior: dict[str, str | None] = {a: None for a in cosechadoras}
    quieta: dict[str, int] = {a: 0 for a in cosechadoras}  # ticks sin moverse desde el último movimiento
    opuesto = {"N": "S", "S": "N", "E": "O", "O": "E"}
    for t in linea.ticks:
        nuevas = {tuple(c) for c in linea.celdas_nuevas[t]}
        if t > 0:
            for a in cosechadoras:
                if linea.estado[a][t] not in (EN_BASE, "FIN"):
                    activos += 1
                antes, ahora = linea.pose[a][t - 1], linea.pose[a][t]
                if antes is None or ahora is None or antes[:2] == ahora[:2]:
                    quieta[a] += 1
                    continue
                celda = ahora[:2]
                if celda in nuevas:
                    lado += ahora[1] != antes[1]
                elif celda in campo and celda not in cosechadas:
                    pisadas += 1
                if rumbo_anterior[a] is not None and opuesto[rumbo_anterior[a]] == ahora[2] and quieta[a] < 2:
                    vueltas += 1
                rumbo_anterior[a] = ahora[2]
                quieta[a] = 0
        cosechadas |= nuevas
    return {"entradas_de_lado": lado, "pasos_sobre_cultivo": pisadas, "vueltas_instantaneas": vueltas,
            "eficiencia_campo": round(100 * len(cosechadas) / activos, 2) if activos else None}


def suelo_de_carros(fuente) -> dict:
    """Metros que recorren los carros según el suelo que pisan, desde el log (sin campos nuevos en el trace).

    Cada vez que la celda de un carro cambia, cuenta `tamano_celda_m` metros en la celda a la que entra:
    rastrojo si es campo ya cosechado (en ese tick o antes), cultivo si es campo todavía en pie (con R13
    debe ser 0) y camino en cualquier otro caso (caminos, patio de la bodega y bases). El rastrojo es el
    suelo que se compacta; el camino ya está compactado."""
    linea = linea_de_tiempo(fuente)
    s = linea.mundo.get("tamano_celda_m") or 1
    campo = celdas_de_campo(linea.mundo)
    cosechadas: set[tuple[int, int]] = set()
    pasos = {"camino": 0, "rastrojo": 0, "cultivo": 0}
    carros = linea.ids(CARRO)
    for t in linea.ticks:
        cosechadas.update(tuple(c) for c in linea.celdas_nuevas[t])
        if t == 0:
            continue
        for a in carros:
            celda = linea.celda(a, t)
            if celda is None or celda == linea.celda(a, t - 1):
                continue
            if celda not in campo:
                pasos["camino"] += 1
            else:
                pasos["rastrojo" if celda in cosechadas else "cultivo"] += 1
    total = sum(pasos.values())
    return {"metros_carro_camino": _numero(pasos["camino"] * s, 2),
            "metros_carro_rastrojo": _numero(pasos["rastrojo"] * s, 2),
            "metros_carro_cultivo": _numero(pasos["cultivo"] * s, 2),
            "porcentaje_carro_rastrojo": round(100 * pasos["rastrojo"] / total, 2) if total else None}


# Pesos por defecto de J (especificación de la segunda entrega §2 y §11).
PESOS_COSTO = {"tiempo": 1.0, "distancia": 0.5, "colisiones": 1000.0, "ocio": 5.0, "combustible": 0.2,
               "restricciones": 10.0}
# Métrica de la que sale cada término de J.
TERMINOS_COSTO = {"tiempo": "tiempo_completacion", "distancia": "distancia_total", "colisiones": "colisiones",
                  "ocio": "tiempo_ocioso_total", "combustible": "combustible_usado",
                  "restricciones": "restricciones"}


def costo_j(metricas: dict, config: dict | None = None, pesos: dict | None = None) -> dict:
    """J = suma de peso · valor de cada término (especificación §11). Pesos: `pesos`, o los de
    `config.costo.pesos`, o los por defecto; un término sin dato (por ejemplo, sin combustible) vale 0."""
    pesos = {**PESOS_COSTO, **(((config or {}).get("costo") or {}).get("pesos") or {}), **(pesos or {})}
    terminos = {nombre: _numero(pesos[nombre] * (metricas.get(clave) or 0))
                for nombre, clave in TERMINOS_COSTO.items()}
    return {"pesos": pesos, "terminos": terminos, "total": _numero(sum(terminos.values()))}


def _combustible(linea: LineaDeTiempo, agente: str, recargado: float, recargas: int) -> dict:
    """Combustible de un agente desde el log (vacío si el trace no lo trae)."""
    niveles = [c for c in linea.combustible.get(agente, []) if c is not None]
    if not niveles:
        return {}
    inicial, final = niveles[0], niveles[-1]
    return {"combustible_usado": round(inicial - final + recargado, 2),
            "combustible_comprado": round(inicial + recargado, 2),
            "recargas": recargas, "combustible_minimo": min(niveles)}


def series_temporales(fuente) -> dict:
    """Series por tick (0..meta.total_ticks), una lista con un valor por tick:

    - tick.
    - ocioso_acumulado: ticks en LLENA_ESPERANDO acumulados hasta ese tick, PROMEDIO por cosechadora.
    - distancia_cosechadora_carro: distancia de cada cosechadora a su carro más cercano, PROMEDIO.
    - cosechado_acumulado: grano cosechado hasta ese tick.
    - en_transito: grano que llevan los agentes (suma de las cargas).
    - entregado_en_bodega: grano acumulado en la bodega (cosechado = en tránsito + en bodega).
    - bloqueos_acumulados: eventos BLOQUEO hasta ese tick (total).
    - por_agente: {id: {"carga": [...]}}; las cosechadoras además llevan "ocioso_acumulado" y "distancia_al_carro";
      si el trace trae combustible, cada agente lleva "combustible" (None antes de conocerlo).
    """
    linea = linea_de_tiempo(fuente)
    cosechadoras = linea.ids(COSECHADORA)
    por_agente: dict[str, dict] = {a: {"carga": [c or 0 for c in linea.carga[a]]} for a in linea.ids()}
    for a in linea.ids():
        if any(c is not None for c in linea.combustible.get(a, [])):
            por_agente[a]["combustible"] = list(linea.combustible[a])
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
        "cosechado_acumulado": list(linea.grano_cosechado),
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
