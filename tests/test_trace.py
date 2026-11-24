"""Trace 2.2: checksum, TraceBuilder, línea de tiempo, reconstrucción, escritura y fixture.  [Dueño: Joel]

Los valores esperados están calculados a mano a partir de un guion de 20 ticks (tests/ayuda_datos.py):
no salen del código que se prueba.
"""

import copy

import pytest

from ayuda_datos import (
    AGENTES, C, CONFIG, FIXTURE, H, MUNDO, TOTAL, bloqueo, cargar_script, cel, construir_trace, deposito,
    enviado, entregado, por_tick, pose, registro,
)
from harvest_sim.datos import (
    SCHEMA_VERSION,
    TraceBuilder,
    calcular_checksum,
    celdas_de_campo,
    cargar_trace,
    con_checksum,
    escribir_trace,
    linea_de_tiempo,
    reconstruir,
    verificar_checksums,
)
from harvest_sim.datos.formato import CLASE_AGENTE, CLASE_CELDAS, CLASE_REGISTRO


def test_checksum_es_estable_e_ignora_el_campo_checksum():
    """Humo del contrato: 16 hex, independiente del orden de claves, ignora `checksum`."""
    registro_ = {"tick": 3, "agent_id": "carro_1", "estado": "EN_BASE"}
    c = calcular_checksum(registro_)
    assert len(c) == 16 and all(ch in "0123456789abcdef" for ch in c)
    assert c == calcular_checksum({"estado": "EN_BASE", "agent_id": "carro_1", "tick": 3})
    assert c == calcular_checksum({**registro_, "checksum": "otro"})
    assert con_checksum(registro_)["checksum"] == c


def test_estructura_trace_v2_2():
    """El trace construido tiene schema_version 2.2, meta, config, mundo, agentes, ticks (arreglo
    ordenado) y metricas, coherentes con el config, y las clases de la ontología las pone el builder."""
    trace, _ = construir_trace()
    assert list(trace) == ["schema_version", "meta", "config", "mundo", "agentes", "ticks", "metricas"]
    assert trace["schema_version"] == "2.2" == SCHEMA_VERSION
    assert trace["meta"] == {"escenario": "ejemplo_mini", "seed": 0, "total_ticks": TOTAL, "clase": CLASE_REGISTRO}
    assert trace["config"] == CONFIG and trace["mundo"] == {**MUNDO, "clase_celdas": CLASE_CELDAS}
    assert trace["agentes"] == [{"id": a["id"], "tipo": a["tipo"], "clase": CLASE_AGENTE, "capacidad": a["capacidad"],
                                 "base": a["base"]} for a in AGENTES]
    assert list(trace["agentes"][0]) == ["id", "tipo", "clase", "capacidad", "base"]
    assert trace["metricas"] == {}
    assert isinstance(trace["ticks"], list)
    numeros = [t["tick"] for t in trace["ticks"]]
    assert numeros == sorted(set(numeros))
    assert all(list(t) == ["tick", "cambios", "checksum"] for t in trace["ticks"])


def test_ticks_sin_cambios_no_aparecen():
    """Un tick sin cambios no aparece; el tick 0 siempre aparece; meta.total_ticks es el último tick."""
    trace, _ = construir_trace()
    presentes = [t["tick"] for t in trace["ticks"]]
    assert presentes == [t for t in range(TOTAL + 1) if t not in (12, 18, 20)]
    assert trace["meta"]["total_ticks"] == 20  # el último tick no tiene cambios y aun así cuenta

    b = TraceBuilder({}, {}, [])
    b.agregar_tick(0, [], [])  # el tick 0 aparece aunque esté vacío
    assert [t["tick"] for t in b.construir()["ticks"]] == [0]


def test_diff_de_agente_solo_campos_que_cambian():
    """Un AGENTE.set contiene solo los campos que cambiaron y cada campo va completo."""
    trace, _ = construir_trace()
    ticks = por_tick(trace)
    # tick 0: los tres campos de cada agente
    sets0 = {e["id"]: e["set"] for e in ticks[0]["cambios"]}
    assert sets0 == {
        H: {"pose": pose(2, 0, "S"), "estado": "EN_BASE", "carga": 0},
        C: {"pose": pose(1, 0, "N"), "estado": "EN_BASE", "carga": 0},
    }
    # tick 1: solo el estado de la cosechadora; el carro, quieto, no genera nada
    assert ticks[1]["cambios"] == [{"tipo": "AGENTE", "id": H, "set": {"estado": "YENDO_A_CAMPO"}}]
    # tick 5: pose entera y carga, sin estado; la carga es un entero
    agente5 = [e for e in ticks[5]["cambios"] if e["tipo"] == "AGENTE"]
    assert agente5 == [{"tipo": "AGENTE", "id": H, "set": {"pose": pose(1, 1, "E"), "carga": 2}}]
    assert isinstance(agente5[0]["set"]["carga"], int)


def test_diff_ignora_campos_extra_y_no_depende_de_referencias():
    """Los campos que no son pose, estado ni carga se ignoran, y el builder no se confunde si el
    agente muta su propio registro entre ticks."""
    b = TraceBuilder(CONFIG, MUNDO, AGENTES)
    r = registro(0, H, {"pose": pose(2, 0, "S"), "estado": "EN_BASE", "carga": 0})
    r["intencion"] = {"accion": "NINGUNA", "celdas": []}
    r["objetivo"] = None
    b.agregar_tick(0, [r], [])
    r["pose"]["x"] = 3  # el agente muta su registro en el lugar
    b.agregar_tick(1, [r], [])
    ticks = b.construir()["ticks"]
    assert set(ticks[0]["cambios"][0]["set"]) == {"pose", "estado", "carga"}
    assert ticks[1]["cambios"] == [{"tipo": "AGENTE", "id": H, "set": {"pose": pose(3, 0, "S")}}]


def test_orden_de_eventos_dentro_del_tick():
    """Orden fijo: MENSAJE_ENTREGADO, AGENTE (cosechadora y luego carro), CELDA_COSECHADA,
    DEPOSITO y BLOQUEO (en el orden recibido), MENSAJE_ENVIADO."""
    trace, _ = construir_trace()
    tick14 = por_tick(trace)[14]["cambios"]
    assert [e["tipo"] for e in tick14] == ["MENSAJE_ENTREGADO", "AGENTE", "AGENTE", "CELDA_COSECHADA"]
    assert [e["id"] for e in tick14 if e["tipo"] == "AGENTE"] == [H, C]

    b = TraceBuilder(CONFIG, MUNDO, AGENTES)
    base = {H: dict(pose=pose(2, 0, "S"), estado="EN_BASE", carga=0),
            C: dict(pose=pose(1, 0, "N"), estado="EN_BASE", carga=0)}
    b.agregar_tick(0, [registro(0, a, base[a]) for a in (H, C)], [])
    nuevo = {H: dict(base[H], carga=1), C: dict(base[C], estado="YENDO_A_COSECHADORA")}
    revueltos = [
        enviado(7, "LLENA", H, C, {}, 2),
        bloqueo(C),
        deposito(C, 4, 4),
        cel([0, 1]),
        entregado(6, H),
    ]
    b.agregar_tick(1, [registro(1, a, nuevo[a]) for a in (H, C)], revueltos)
    cambios = b.construir()["ticks"][1]["cambios"]
    assert [e["tipo"] for e in cambios] == [
        "MENSAJE_ENTREGADO", "AGENTE", "AGENTE", "BLOQUEO", "DEPOSITO", "CELDA_COSECHADA", "MENSAJE_ENVIADO",
    ]


def test_entradas_invalidas():
    """Ticks no crecientes, eventos AGENTE o desconocidos en `eventos` y construir sin ticks fallan."""
    b = TraceBuilder(CONFIG, MUNDO, AGENTES)
    with pytest.raises(ValueError):
        b.construir()
    b.agregar_tick(0, [], [])
    with pytest.raises(ValueError):
        b.agregar_tick(0, [], [])
    with pytest.raises(ValueError):
        b.agregar_tick(1, [], [{"tipo": "AGENTE", "id": H, "set": {}}])
    with pytest.raises(ValueError):
        b.agregar_tick(1, [], [{"tipo": "INVENTADO"}])


def test_reconstruir_estado_por_tick():
    """reconstruir(trace) devuelve el estado de cada tick, incluidos los ticks sin cambios."""
    trace, entradas = construir_trace()
    estados = list(reconstruir(trace))
    assert [e["tick"] for e in estados] == list(range(TOTAL + 1))
    # coincide con el estado completo que tenía cada agente en cada tick
    for e, (t, regs, _) in zip(estados, entradas):
        esperado = {r["agent_id"]: {"pose": r["pose"], "estado": r["estado"], "carga": r["carga"]["actual"]}
                    for r in regs}
        assert e["agentes"] == esperado, t
    # valores calculados a mano
    assert estados[12]["eventos"] == []
    assert estados[12]["agentes"][H]["estado"] == "TRANSFIRIENDO"  # se arrastra desde el tick 11
    assert estados[7]["celdas_cosechadas"] == [[0, 1], [1, 1], [2, 1], [3, 1]]
    assert estados[7]["mensajes_en_transito"] == [1] and estados[8]["mensajes_en_transito"] == []
    assert estados[13]["mensajes_en_transito"] == [2] and estados[14]["mensajes_en_transito"] == []
    assert estados[18]["entregado_total"] == 0 and estados[19]["entregado_total"] == 4
    assert [e["tipo"] for e in estados[17]["eventos"]] == ["AGENTE", "BLOQUEO"]
    assert estados[20]["agentes"][C]["estado"] == "REGRESANDO_A_BASE"
    # cada elemento es una copia independiente
    estados[0]["agentes"][H]["carga"] = 99
    assert list(reconstruir(trace))[0]["agentes"][H]["carga"] == 0
    # con copiar=False se comparten listas (más rápido) pero los valores son los mismos
    assert [e["celdas_cosechadas"][:] for e in reconstruir(trace, copiar=False)][7] == [[0, 1], [1, 1], [2, 1], [3, 1]]
    # ticks desordenados se rechazan
    malo = copy.deepcopy(trace)
    malo["ticks"][1], malo["ticks"][2] = malo["ticks"][2], malo["ticks"][1]
    with pytest.raises(ValueError):
        list(reconstruir(malo))


def test_checksum_de_cada_tick_del_log():
    """Cada tick de un trace verifica su checksum al recalcularlo; una alteración se detecta."""
    trace, _ = construir_trace()
    assert verificar_checksums(trace)
    for t in trace["ticks"]:
        assert t["checksum"] == calcular_checksum({"tick": t["tick"], "cambios": t["cambios"]})
    alterado = copy.deepcopy(trace)
    alterado["ticks"][5]["cambios"][0]["set"]["carga"] = 3
    assert not verificar_checksums(alterado)
    sin_checksum = copy.deepcopy(trace)
    del sin_checksum["ticks"][0]["checksum"]
    assert not verificar_checksums(sin_checksum)


def test_escritura_reproducible(tmp_path):
    """Escribir dos veces el mismo trace produce archivos idénticos; schema_version queda primero."""
    trace1, _ = construir_trace()
    trace2, _ = construir_trace()  # otra corrida con el mismo guion
    a = tmp_path / "a" / "trace.json"  # la carpeta no existe: se crea
    b = tmp_path / "b.json"
    escribir_trace(trace1, a)
    escribir_trace(trace2, b)
    bytes_a = a.read_bytes()
    assert bytes_a == b.read_bytes()
    assert bytes_a.startswith(b'{\n  "schema_version": "2.2",')
    assert bytes_a.endswith(b"}\n") and b"\r" not in bytes_a
    # cada tick en una sola línea y las coordenadas del primer nivel en una línea
    texto = bytes_a.decode("utf-8")
    lineas_de_tick = [linea for linea in texto.splitlines() if linea.startswith('    {"tick": ')]
    assert len(lineas_de_tick) == len(trace1["ticks"])
    assert '"bodega": [0, 0],' in texto
    leido = cargar_trace(a)
    assert leido == trace1 and verificar_checksums(leido)


def test_fixture_es_valido_y_verificable():
    """El fixture existe, es esquema 2.2, pasa los checksums y se puede reconstruir completo."""
    trace = cargar_trace(FIXTURE)
    assert trace["schema_version"] == "2.2" and verificar_checksums(trace)
    numeros = [t["tick"] for t in trace["ticks"]]
    assert numeros[0] == 0 and numeros == sorted(set(numeros))
    assert [e["tick"] for e in reconstruir(trace)] == list(range(trace["meta"]["total_ticks"] + 1))


def test_fixture_se_regenera_identico(tmp_path):
    """Correr el generador de nuevo produce exactamente el mismo archivo (es determinista)."""
    destino = tmp_path / "otra_vez.json"
    escribir_trace(cargar_script("tools/generar_trace_ejemplo.py").generar(), destino)
    assert destino.read_bytes() == FIXTURE.read_bytes()


def test_fixture_cumple_las_reglas_y_cubre_los_casos():
    """Desde el log: inicio y fin en las bases, R2 (un paso por tick), R3 (nunca la misma celda), R7
    (conservación de grano) y los casos que necesitan las métricas: espera, carga parcial final,
    bloqueo, depósitos y mensajes bien emparejados."""
    trace = cargar_trace(FIXTURE)
    estados = list(reconstruir(trace))
    bases = {a["id"]: tuple(a["base"]) for a in trace["agentes"]}
    posicion = lambda e, a: (e["agentes"][a]["pose"]["x"], e["agentes"][a]["pose"]["y"])  # noqa: E731

    # inicio y fin
    assert {a: posicion(estados[0], a) for a in (H, C)} == bases
    assert {a: posicion(estados[-1], a) for a in (H, C)} == bases
    assert estados[-1]["agentes"][H]["estado"] == "FIN" and estados[-1]["agentes"][C]["estado"] == "EN_BASE"

    # R2, R3 y R7 en cada tick
    for anterior, e in zip(estados, estados[1:]):
        for a in (H, C):
            (x0, y0), (x1, y1) = posicion(anterior, a), posicion(e, a)
            assert abs(x0 - x1) + abs(y0 - y1) <= 1, (e["tick"], a)
    for e in estados:
        assert posicion(e, H) != posicion(e, C), e["tick"]
        en_agentes = sum(e["agentes"][a]["carga"] for a in (H, C))
        assert len(e["celdas_cosechadas"]) == en_agentes + e["entregado_total"], e["tick"]

    campo = len(celdas_de_campo(trace["mundo"]))
    assert len(estados[-1]["celdas_cosechadas"]) == campo == estados[-1]["entregado_total"]
    assert len({tuple(c) for c in estados[-1]["celdas_cosechadas"]}) == campo  # ninguna celda dos veces

    eventos = [(e["tick"], ev) for e in estados for ev in e["eventos"]]
    # espera por el carro, bloqueo y depósitos
    assert any(e["agentes"][H]["estado"] == "LLENA_ESPERANDO" for e in estados)
    assert sum(1 for _, ev in eventos if ev["tipo"] == "BLOQUEO") >= 1
    assert sum(ev["cantidad"] for _, ev in eventos if ev["tipo"] == "DEPOSITO") == campo
    # carga parcial final: la última carga que avisa la cosechadora es menor que su capacidad
    llenas = [ev["payload"]["carga"] for _, ev in eventos
              if ev["tipo"] == "MENSAJE_ENVIADO" and ev["tipo_mensaje"] == "LLENA"]
    assert llenas[-1] < trace["agentes"][0]["capacidad"] and len(llenas) >= 2
    # cada mensaje enviado se entrega en el tick siguiente, con id único y creciente
    enviados = [(t, ev) for t, ev in eventos if ev["tipo"] == "MENSAJE_ENVIADO"]
    entregas = {ev["id"]: t for t, ev in eventos if ev["tipo"] == "MENSAJE_ENTREGADO"}
    assert [ev["id"] for _, ev in enviados] == list(range(1, len(enviados) + 1))
    for t, ev in enviados:
        assert ev["entrega_en"] == t + 1 and entregas[ev["id"]] == t + 1


def test_linea_de_tiempo_coincide_con_reconstruir():
    """La línea de tiempo (una pasada) da, en cada tick, los mismos valores que reconstruir."""
    for trace in (construir_trace()[0], cargar_trace(FIXTURE)):
        linea = linea_de_tiempo(trace)
        assert linea_de_tiempo(linea) is linea  # si ya es una línea de tiempo, no la rehace
        assert list(linea.ticks) == list(range(trace["meta"]["total_ticks"] + 1))
        for e in reconstruir(trace):
            t = e["tick"]
            for a, campos in e["agentes"].items():
                p = campos["pose"]
                assert linea.pose[a][t] == (p["x"], p["y"], p["orientacion"])
                assert (linea.estado[a][t], linea.carga[a][t]) == (campos["estado"], campos["carga"])
            assert linea.cosechadas[t] == len(e["celdas_cosechadas"])
            assert linea.entregado[t] == e["entregado_total"]
            assert list(linea.en_transito[t]) == e["mensajes_en_transito"]
            assert linea.eventos[t] == e["eventos"]
        assert linea.ids("cosechadora") == [H] and linea.ids("carro") == [C] and linea.ids() == [H, C]
    # valores calculados a mano sobre el guion
    linea = linea_de_tiempo(construir_trace()[0])
    assert linea.celdas_nuevas[14] == [(3, 2)] and linea.cosechadas[13] == 4
    assert linea.celda(C, 17) == (0, 0)


def test_builder_sigue_el_combustible_solo_si_viene():
    """2.2: si el registro trae `combustible`, se registra cuando cambia (2 decimales); si no, el log es el de 2.1."""
    b = TraceBuilder(CONFIG, MUNDO, AGENTES)
    base = {"pose": pose(2, 0, "S"), "estado": "EN_BASE", "carga": 0}
    for t, litros in enumerate([100, 100, 99.4567, 99.4567]):
        r = registro(t, H, base)
        r["combustible"] = litros
        b.agregar_tick(t, [r], [])
    ticks = {t["tick"]: t["cambios"] for t in b.construir()["ticks"]}
    assert ticks[0][0]["set"]["combustible"] == 100.0
    assert 1 not in ticks and 3 not in ticks                      # sin cambios, el tick no aparece
    assert ticks[2] == [{"tipo": "AGENTE", "id": H, "set": {"combustible": 99.46}}]

    sin = TraceBuilder(CONFIG, MUNDO, AGENTES)
    sin.agregar_tick(0, [registro(0, H, base)], [])
    assert "combustible" not in sin.construir()["ticks"][0]["cambios"][0]["set"]
