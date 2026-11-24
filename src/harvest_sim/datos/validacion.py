"""Validador del trace: el contrato de los formatos 2.1 y 2.2, ejecutable.  [Joel]

    errores = validar_trace(trace)                       # [] si es válido
    avisos = []; validar_trace(trace, avisos=avisos)     # además, avisos que no invalidan el trace
"""

from __future__ import annotations

from .campo import celdas_de_campo
from .formato import (
    CAMPOS_AGENTE,
    CAMPOS_AGENTE_OBLIGATORIOS,
    CAMPOS_EVENTO,
    CAMPOS_EVENTO_OPCIONALES,
    EVENTOS_DESDE,
    MOTIVOS_RECHAZO,
    PAYLOAD_POR_TIPO,
    REGLAS_RESTRICCION,
    RECHAZO,
    VERSIONES_ACEPTADAS,
    CATEGORIA,
    CLASE_AGENTE,
    CLASE_CELDAS,
    CLASE_REGISTRO,
    CLAVES_TICK,
    CLAVES_TRACE,
    ESTADOS_CONOCIDOS,
    ORIENTACIONES,
    PERFORMATIVAS,
    PERFORMATIVAS_VALIDAS,
    SCHEMA_VERSION,
)
from .trace import calcular_checksum


def _es_entero(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _es_celda(v) -> bool:
    return isinstance(v, list) and len(v) == 2 and all(_es_entero(c) for c in v)


def _es_numero(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _tiene_tipo(valor, tipo) -> bool:
    if tipo is int:
        return _es_entero(valor)
    if tipo is float:
        return _es_numero(valor)
    return isinstance(valor, tipo)


def _version(texto) -> tuple[int, ...]:
    try:
        return tuple(int(p) for p in str(texto).split("."))
    except ValueError:
        return (0,)


def _retraso_de_config(trace: dict) -> int:
    """1 + el retraso máximo de mensajes de la configuración del trace (1 si no hay incertidumbre)."""
    config = trace.get("config") if isinstance(trace.get("config"), dict) else {}
    retraso = ((config.get("incertidumbre") or {}).get("retraso_mensajes") or {}).get("maximo", 0)
    return 1 + retraso if _es_entero(retraso) and retraso >= 0 else 1


def validar_trace(trace, retraso_maximo: int | None = None, avisos: list[str] | None = None) -> list[str]:
    """Revisa que un trace cumpla el formato (2.1 o 2.2, el contrato del log) y que sus datos sean consistentes.

    Devuelve la lista de errores (vacía si el trace es válido); no se detiene en el primero. Cada mensaje
    dice dónde está el problema, por ejemplo: "tick 14, evento 2 (DEPOSITO): entregado_total 7, se esperaba 6".

    Revisa: estructura (claves y su orden, versión, meta con su clase, mundo con obstáculos y clase de
    celdas, catálogo de agentes con su clase); ticks (arreglo estrictamente creciente que empieza en 0, sin
    pasar de total_ticks, checksum correcto); eventos (tipo conocido, campos obligatorios y sin campos
    extra, tipos de dato, orden por categoría); agentes (solo pose, estado y carga; en el catálogo;
    completos en el tick 0; orientación válida; carga entre 0 y la capacidad; dentro del mapa); mundo
    (celdas cosechadas dentro del campo, fuera de obstáculos y una sola vez; entregado_total acumulado); y
    mensajes (ids crecientes, performativa válida, claves del payload, entrega entre 1 y `retraso_maximo`
    ticks después del envío y una sola vez). En 2.2, además: combustible entre 0 y el tanque, recargas,
    restricciones, cantidad de cada celda cosechada y `mundo.rendimiento`.

    `retraso_maximo` por defecto: 1 + `config.incertidumbre.retraso_mensajes.maximo` del trace (1 si no hay).

    Si se pasa una lista en `avisos`, agrega ahí lo que no invalida el trace pero conviene revisar
    (por ejemplo, un estado, una regla de restricción o un motivo de rechazo que no están en `formato`).

    No revisa las reglas físicas de la simulación (un paso por tick, celdas compartidas, intercambios,
    conservación del grano): esas las prueban las pruebas de integración (Ilan, con `reconstruir`) y las del
    mundo y las rutas (Carlos y Oswaldo).
    """
    errores: list[str] = []
    error = errores.append
    aviso = avisos.append if avisos is not None else (lambda _: None)
    if not isinstance(trace, dict):
        return ["el trace no es un objeto JSON"]

    # --- Estructura del primer nivel ---
    claves = list(trace)
    faltan = [c for c in CLAVES_TRACE if c not in trace]
    sobran = [c for c in claves if c not in CLAVES_TRACE]
    if faltan:
        error(f"faltan claves en el primer nivel: {faltan}")
    if sobran:
        error(f"claves no esperadas en el primer nivel: {sobran}")
    if not faltan and not sobran and claves != CLAVES_TRACE:
        error(f"orden de las claves del primer nivel: {claves}; se esperaba {CLAVES_TRACE}")
    version = trace.get("schema_version")
    if version not in VERSIONES_ACEPTADAS:
        error(f"schema_version es {version!r}; se esperaba una de {list(VERSIONES_ACEPTADAS)} (actual: {SCHEMA_VERSION!r})")
    v = _version(version if version in VERSIONES_ACEPTADAS else SCHEMA_VERSION)
    if retraso_maximo is None:
        retraso_maximo = _retraso_de_config(trace)
    config = trace.get("config") if isinstance(trace.get("config"), dict) else {}
    tanques = {}
    if isinstance(config.get("combustible"), dict):
        for tipo_agente in ("cosechadora", "carro"):
            t = config["combustible"].get(f"tanque_{tipo_agente}")
            if _es_numero(t):
                tanques[tipo_agente] = t

    meta = trace.get("meta")
    total = None
    if not isinstance(meta, dict):
        error("meta debe ser un objeto con escenario, seed, total_ticks y clase")
    else:
        for c in ("escenario", "seed", "total_ticks", "clase"):
            if c not in meta:
                error(f"meta: falta {c}")
        if "total_ticks" in meta:
            if _es_entero(meta["total_ticks"]) and meta["total_ticks"] >= 0:
                total = meta["total_ticks"]
            else:
                error(f"meta: total_ticks debe ser un entero >= 0, es {meta['total_ticks']!r}")
        if "clase" in meta and meta["clase"] != CLASE_REGISTRO:
            error(f"meta: clase {meta['clase']!r}; se esperaba {CLASE_REGISTRO!r}")

    mundo = trace.get("mundo")
    ancho = alto = None
    if not isinstance(mundo, dict):
        error("mundo debe ser un objeto")
        mundo = {}
    else:
        for c in ("ancho", "alto", "bodega", "bases", "grano_por_celda", "obstaculos", "clase_celdas"):
            if c not in mundo:
                error(f"mundo: falta {c}")
        if _es_entero(mundo.get("ancho")) and mundo["ancho"] >= 1:
            ancho = mundo["ancho"]
        elif "ancho" in mundo:
            error(f"mundo: ancho debe ser un entero >= 1, es {mundo['ancho']!r}")
        if _es_entero(mundo.get("alto")) and mundo["alto"] >= 2:
            alto = mundo["alto"]
        elif "alto" in mundo:
            error(f"mundo: alto debe ser un entero >= 2, es {mundo['alto']!r}")
        if "bodega" in mundo and not _es_celda(mundo["bodega"]):
            error(f"mundo: bodega debe ser [x, y], es {mundo['bodega']!r}")
        if "bases" in mundo and not (isinstance(mundo["bases"], dict)
                                     and all(_es_celda(v) for v in mundo["bases"].values())):
            error("mundo: bases debe ser un objeto {agent_id: [x, y]}")
        if "grano_por_celda" in mundo and not (_es_entero(mundo["grano_por_celda"]) and mundo["grano_por_celda"] >= 1):
            error(f"mundo: grano_por_celda debe ser un entero >= 1, es {mundo['grano_por_celda']!r}")
        if "clase_celdas" in mundo and mundo["clase_celdas"] != CLASE_CELDAS:
            error(f"mundo: clase_celdas {mundo['clase_celdas']!r}; se esperaba {CLASE_CELDAS!r}")
        if "obstaculos" in mundo:
            obs = mundo["obstaculos"]
            if not (isinstance(obs, list) and all(_es_celda(c) for c in obs)):
                error("mundo: obstaculos debe ser una lista de [x, y]")
                mundo = {k: v for k, v in mundo.items() if k != "obstaculos"}
            else:
                vistas = set()
                ocupadas = [tuple(mundo["bodega"])] if _es_celda(mundo.get("bodega")) else []
                if isinstance(mundo.get("bases"), dict):
                    ocupadas += [tuple(b) for b in mundo["bases"].values() if _es_celda(b)]
                for x, y in obs:
                    if (x, y) in vistas:
                        error(f"mundo: obstáculo ({x}, {y}) repetido")
                    vistas.add((x, y))
                    if ancho is not None and alto is not None and not (0 <= x < ancho and 0 <= y < alto):
                        error(f"mundo: obstáculo ({x}, {y}) fuera del mapa")
                    elif y == 0 or (x, y) in ocupadas:
                        error(f"mundo: obstáculo ({x}, {y}) en la fila de servicio, la bodega o una base")

    def dentro_del_mapa(x, y):
        return ancho is None or alto is None or (0 <= x < ancho and 0 <= y < alto)

    campo = celdas_de_campo(mundo) if ancho is not None and alto is not None else None
    rendimiento = None
    if "rendimiento" in mundo:
        r = mundo["rendimiento"]
        filas_ok = (isinstance(r, list) and alto is not None and len(r) == alto
                    and all(isinstance(f, list) and len(f) == ancho for f in r))
        if not filas_ok or not all(_es_entero(c) and c >= 0 for f in r for c in f):
            error(f"mundo: rendimiento debe ser una matriz de {alto} × {ancho} enteros >= 0")
        else:
            rendimiento = r
            for y, fila in enumerate(r):
                for x, valor in enumerate(fila):
                    if campo is not None and (x, y) in campo and valor < 1:
                        error(f"mundo: rendimiento de la celda de campo ({x}, {y}) debe ser >= 1, es {valor}")
                    elif campo is not None and (x, y) not in campo and valor != 0:
                        error(f"mundo: rendimiento de ({x}, {y}) debe ser 0 (no es campo), es {valor}")
    con_obstaculo = {tuple(c) for c in mundo.get("obstaculos", [])}

    catalogo: dict[str, dict] = {}
    agentes = trace.get("agentes")
    if not isinstance(agentes, list):
        error("agentes debe ser un arreglo")
        agentes = []
    for i, a in enumerate(agentes):
        pref = f"agentes[{i}]"
        if not isinstance(a, dict) or any(c not in a for c in ("id", "tipo", "clase", "capacidad", "base")):
            error(f"{pref}: debe tener id, tipo, clase, capacidad y base")
            continue
        if not isinstance(a["id"], str):
            error(f"{pref}: id debe ser texto")
            continue
        if a["id"] in catalogo:
            error(f"{pref}: id repetido {a['id']!r}")
            continue
        if not (isinstance(a["tipo"], str) and a["tipo"]):
            error(f"{pref}: tipo debe ser texto no vacío, es {a['tipo']!r}")
        if a["clase"] != CLASE_AGENTE:
            error(f"{pref}: clase {a['clase']!r}; se esperaba {CLASE_AGENTE!r}")
        if not (_es_entero(a["capacidad"]) and a["capacidad"] >= 1):
            error(f"{pref}: capacidad debe ser un entero >= 1, es {a['capacidad']!r}")
        if not _es_celda(a["base"]):
            error(f"{pref}: base debe ser [x, y], es {a['base']!r}")
        elif isinstance(mundo.get("bases"), dict) and mundo["bases"].get(a["id"]) not in (None, a["base"]):
            error(f"{pref}: base {a['base']} no coincide con mundo.bases ({mundo['bases'][a['id']]})")
        catalogo[a["id"]] = a

    # --- Ticks: forma, orden y checksum ---
    ticks = trace.get("ticks")
    if not isinstance(ticks, list):
        error("ticks debe ser un arreglo")
        return errores
    por_tick: dict[int, list] = {}
    anterior = None
    for i, t in enumerate(ticks):
        if not isinstance(t, dict) or list(t) != CLAVES_TICK:
            error(f"ticks[{i}]: debe tener exactamente {CLAVES_TICK} en ese orden")
            continue
        n = t["tick"]
        if not _es_entero(n):
            error(f"ticks[{i}]: tick debe ser un entero, es {n!r}")
            continue
        if anterior is None and n != 0:
            error(f"ticks[{i}]: el primer tick debe ser el 0, es {n}")
        if anterior is not None and n <= anterior:
            error(f"ticks[{i}]: los ticks deben ser estrictamente crecientes ({n} después de {anterior})")
            continue
        anterior = n
        if total is not None and n > total:
            error(f"tick {n}: es mayor que meta.total_ticks ({total})")
            continue
        if t["checksum"] != calcular_checksum(t):
            error(f"tick {n}: el checksum no coincide (el tick está alterado o dañado)")
        if not isinstance(t["cambios"], list):
            error(f"tick {n}: cambios debe ser un arreglo")
            continue
        por_tick[n] = t["cambios"]
    if not por_tick:
        return errores
    if total is None:
        total = max(por_tick)

    # --- Recorrido tick a tick: eventos y estado ---
    estado = {a: {} for a in catalogo}
    celdas: set[tuple[int, int]] = set()
    entregado = 0
    enviados: dict[int, tuple] = {}
    entregados: set[int] = set()
    ultimo_id = 0
    estados_raros: set[str] = set()

    def agente_conocido(pref, nombre, campo_="agente"):
        if nombre not in catalogo:
            error(f"{pref}: {campo_} {nombre!r} no está en el catálogo de agentes")
            return False
        return True

    for tick in range(total + 1):
        ultima_categoria = -1
        agentes_en_tick: set[str] = set()
        for n, e in enumerate(por_tick.get(tick, []), 1):
            pref = f"tick {tick}, evento {n}"
            if not isinstance(e, dict):
                error(f"{pref}: el evento debe ser un objeto")
                continue
            tipo = e.get("tipo")
            if tipo not in CAMPOS_EVENTO or v < _version(EVENTOS_DESDE.get(tipo, "0")):
                error(f"{pref}: tipo desconocido {tipo!r}" + (f" (existe desde la versión {EVENTOS_DESDE[tipo]})"
                                                             if tipo in EVENTOS_DESDE else ""))
                continue
            pref = f"{pref} ({tipo})"
            campos = dict(CAMPOS_EVENTO[tipo])
            for campo_opcional, tipo_campo in CAMPOS_EVENTO_OPCIONALES.get(tipo, {}).items():
                if campo_opcional in e:
                    campos[campo_opcional] = tipo_campo
            faltantes = [c for c in campos if c not in e]
            if faltantes:
                error(f"{pref}: faltan campos {faltantes}")
                continue
            extra = sorted(set(e) - {"tipo"} - set(campos))
            if extra:
                error(f"{pref}: campos no esperados {extra}")
            malos = [c for c, tp in campos.items() if not _tiene_tipo(e[c], tp)]
            if malos:
                error(f"{pref}: tipo de dato incorrecto en {malos}")
                continue
            if CATEGORIA[tipo] < ultima_categoria:
                error(f"{pref}: fuera de orden (dentro del tick van entregas, agentes, mundo y envíos)")
            ultima_categoria = max(ultima_categoria, CATEGORIA[tipo])

            if tipo == "AGENTE":
                ident, nuevos = e["id"], e["set"]
                if not agente_conocido(pref, ident, "id"):
                    continue
                if ident in agentes_en_tick:
                    error(f"{pref}: el agente {ident!r} aparece dos veces en el mismo tick")
                agentes_en_tick.add(ident)
                if not nuevos:
                    error(f"{pref}: set vacío")
                permitidos = CAMPOS_AGENTE if v >= (2, 2) else CAMPOS_AGENTE_OBLIGATORIOS
                no_permitidos = sorted(set(nuevos) - set(permitidos))
                if no_permitidos:
                    error(f"{pref}: campos no permitidos en set {no_permitidos} (solo {', '.join(permitidos)})")
                if "combustible" in nuevos and "combustible" in permitidos:
                    nivel, tanque = nuevos["combustible"], tanques.get(catalogo[ident].get("tipo"))
                    if not _es_numero(nivel) or nivel < 0 or (tanque is not None and nivel > tanque + 1e-9):
                        error(f"{pref}: combustible {nivel!r} debe ser un número entre 0 y el tanque ({tanque})")
                if "pose" in nuevos:
                    p = nuevos["pose"]
                    if not (isinstance(p, dict) and set(p) == {"x", "y", "orientacion"}
                            and _es_entero(p["x"]) and _es_entero(p["y"])):
                        error(f"{pref}: pose debe ser {{x, y, orientacion}} con x e y enteros")
                    else:
                        if p["orientacion"] not in ORIENTACIONES:
                            error(f"{pref}: orientacion {p['orientacion']!r} no es una de {list(ORIENTACIONES)}")
                        if not dentro_del_mapa(p["x"], p["y"]):
                            error(f"{pref}: pose ({p['x']}, {p['y']}) fuera del mapa")
                        estado[ident]["pose"] = (p["x"], p["y"])
                if "estado" in nuevos:
                    if isinstance(nuevos["estado"], str) and nuevos["estado"]:
                        estado[ident]["estado"] = nuevos["estado"]
                        if nuevos["estado"] not in ESTADOS_CONOCIDOS and nuevos["estado"] not in estados_raros:
                            estados_raros.add(nuevos["estado"])
                            aviso(f"{pref}: estado {nuevos['estado']!r} no está en formato.ESTADOS_CONOCIDOS")
                    else:
                        error(f"{pref}: estado debe ser texto no vacío")
                if "carga" in nuevos:
                    c, cap = nuevos["carga"], catalogo[ident].get("capacidad")
                    if not _es_entero(c) or c < 0 or (_es_entero(cap) and c > cap):
                        error(f"{pref}: carga {c!r} debe ser un entero entre 0 y la capacidad ({cap})")
                    else:
                        estado[ident]["carga"] = c

            elif tipo == "CELDA_COSECHADA":
                agente_conocido(pref, e["agente"])
                if not _es_celda(e["celda"]):
                    error(f"{pref}: celda debe ser [x, y]")
                    continue
                x, y = e["celda"]
                if (x, y) in con_obstaculo:
                    error(f"{pref}: celda ({x}, {y}) es un obstáculo, no se cosecha")
                elif campo is not None and (x, y) not in campo:
                    error(f"{pref}: celda ({x}, {y}) fuera del campo (el campo son las filas y >= 1 del mapa)")
                if (x, y) in celdas:
                    error(f"{pref}: la celda ({x}, {y}) se cosecha dos veces")
                celdas.add((x, y))
                if "cantidad" in e:
                    if e["cantidad"] < 1:
                        error(f"{pref}: cantidad {e['cantidad']} debe ser >= 1")
                    elif rendimiento is not None and dentro_del_mapa(x, y) and e["cantidad"] != rendimiento[y][x]:
                        error(f"{pref}: cantidad {e['cantidad']}, el rendimiento de ({x}, {y}) es {rendimiento[y][x]}")

            elif tipo == "DEPOSITO":
                agente_conocido(pref, e["agente"])
                if e["cantidad"] < 0:
                    error(f"{pref}: cantidad negativa ({e['cantidad']})")
                esperado = entregado + e["cantidad"]
                if e["entregado_total"] != esperado:
                    error(f"{pref}: entregado_total {e['entregado_total']}, se esperaba {esperado}")
                entregado = e["entregado_total"]

            elif tipo == "BLOQUEO":
                agente_conocido(pref, e["agente"])

            elif tipo == "RECARGA":
                if agente_conocido(pref, e["agente"]):
                    tanque = tanques.get(catalogo[e["agente"]].get("tipo"))
                    if e["cantidad"] < 0 or e["nivel"] < 0 or (tanque is not None and e["nivel"] > tanque + 1e-9):
                        error(f"{pref}: cantidad {e['cantidad']} y nivel {e['nivel']} deben ser >= 0 y el nivel "
                              f"no mayor que el tanque ({tanque})")

            elif tipo == "RESTRICCION":
                agente_conocido(pref, e["agente"])
                if e["regla"] not in REGLAS_RESTRICCION:
                    aviso(f"{pref}: regla {e['regla']!r} no está en formato.REGLAS_RESTRICCION")

            elif tipo == "MENSAJE_ENVIADO":
                agente_conocido(pref, e["de"], "de")
                agente_conocido(pref, e["a"], "a")
                if e["id"] in enviados:
                    error(f"{pref}: id {e['id']} repetido")
                elif e["id"] <= ultimo_id:
                    error(f"{pref}: id {e['id']} no es creciente (el anterior fue {ultimo_id})")
                esperada = PERFORMATIVAS.get(e["tipo_mensaje"])
                if e["performativa"] not in PERFORMATIVAS_VALIDAS:
                    error(f"{pref}: performativa {e['performativa']!r} no es una de {list(PERFORMATIVAS_VALIDAS)}")
                elif esperada is not None and e["performativa"] != esperada:
                    error(f"{pref}: performativa {e['performativa']!r} para {e['tipo_mensaje']}; se esperaba {esperada!r}")
                faltan_payload = [c for c in PAYLOAD_POR_TIPO.get(e["tipo_mensaje"], ()) if c not in e["payload"]]
                if faltan_payload:
                    error(f"{pref}: al payload de {e['tipo_mensaje']} le faltan {faltan_payload}")
                if e["tipo_mensaje"] not in PAYLOAD_POR_TIPO:
                    aviso(f"{pref}: tipo_mensaje {e['tipo_mensaje']!r} no está en formato.TIPOS_MENSAJE")
                if e["tipo_mensaje"] == RECHAZO and e["payload"].get("motivo") not in MOTIVOS_RECHAZO \
                        and "motivo" in e["payload"]:
                    aviso(f"{pref}: motivo {e['payload']['motivo']!r} no está en formato.MOTIVOS_RECHAZO")
                if not tick + 1 <= e["entrega_en"] <= tick + retraso_maximo:
                    rango = f"{tick + 1} (el tick siguiente)" if retraso_maximo == 1 else \
                        f"entre {tick + 1} y {tick + retraso_maximo}"
                    error(f"{pref}: entrega_en {e['entrega_en']}, se esperaba {rango}")
                enviados.setdefault(e["id"], (tick, e["a"], e["entrega_en"]))
                ultimo_id = max(ultimo_id, e["id"])

            elif tipo == "MENSAJE_ENTREGADO":
                if e["id"] not in enviados:
                    error(f"{pref}: el mensaje {e['id']} no corresponde a un envío previo")
                    continue
                _, destinatario, entrega_en = enviados[e["id"]]
                if e["id"] in entregados:
                    error(f"{pref}: el mensaje {e['id']} se entrega dos veces")
                if tick != entrega_en:
                    error(f"{pref}: el mensaje {e['id']} se entrega en el tick {tick}, se esperaba {entrega_en}")
                if e["a"] != destinatario:
                    error(f"{pref}: el mensaje {e['id']} se entrega a {e['a']!r} pero se envió a {destinatario!r}")
                entregados.add(e["id"])

        if tick == 0:
            for a, campos_a in estado.items():
                ausentes = [c for c in CAMPOS_AGENTE_OBLIGATORIOS if c not in campos_a]
                if ausentes:
                    error(f"tick 0: al agente {a!r} le faltan {ausentes} (el tick 0 es el estado inicial completo)")

    for ident, (enviado_en, _, entrega_en) in sorted(enviados.items()):
        if ident not in entregados and entrega_en <= total:
            error(f"el mensaje {ident} (enviado en el tick {enviado_en}) nunca se entregó")
    return errores
