"""Corridas completas de extremo a extremo.  [Dueño: Ilan]

Corren la simulación real. Las reglas R1–R9 se revisan en los seis escenarios (A–F) con la línea base, y
en D, E y F también con las cuatro estrategias. Las pruebas de la segunda entrega (spec §16) están al final.
"""

import json
import math
from functools import lru_cache
from pathlib import Path
import pytest

from harvest_sim.datos import (
    celdas_de_campo,
    grano_esperado,
    linea_de_tiempo,
    reconstruir,
    texto_del_trace,
    validar_trace,
    verificar_checksums,
)
from harvest_sim.datos.campo import rendimiento

CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"
ESCENARIOS = ["escenario_a", "escenario_b", "escenario_c", "escenario_d", "escenario_e", "escenario_f"]
NUEVOS = ["escenario_d", "escenario_e", "escenario_f"]
ESTRATEGIAS = ["base", "subasta", "anticipada", "anticipada_plus"]


def obtener_trace(nombre: str) -> dict:
    """Carga la configuración y ejecuta una corrida completa de un escenario."""
    from harvest_sim.config import cargar_config
    from harvest_sim.simulacion import ejecutar

    config_path = CONFIG_DIR / f"{nombre}.json"
    config = cargar_config(config_path)
    return ejecutar(config)


@lru_cache(maxsize=None)
def corrida(nombre: str, estrategia: str = "base", seed: int | None = None) -> dict:
    """Una corrida de un escenario con una estrategia y una seed (en caché: varias pruebas la comparten)."""
    from harvest_sim.datos.experimentos import aplicar_estrategia, simulador_real

    config = aplicar_estrategia(json.loads((CONFIG_DIR / f"{nombre}.json").read_text(encoding="utf-8")), estrategia)
    if seed is not None:
        config["seed"] = seed
    return simulador_real(config)


CASOS = [(n, "base") for n in ESCENARIOS] + [(n, e) for n in NUEVOS for e in ESTRATEGIAS if e != "base"]


@pytest.fixture(scope="module", params=CASOS, ids=lambda c: f"{c[0]}-{c[1]}")
def trace(request):
    """Fixture que produce el log de una corrida real para cada escenario (y estrategia en D, E y F)."""
    return corrida(*request.param)


def test_no_comparten_celda(trace):
    """R3: dos agentes nunca ocupan la misma celda, en ningún tick."""
    for est in reconstruir(trace):
        posiciones = []
        for a_id, a_data in est["agentes"].items():
            pose = a_data.get("pose")
            if pose:
                pos = (pose["x"], pose["y"])
                assert pos not in posiciones, (
                    f"R3 violada: en tick {est['tick']}, el agente {a_id} comparte la celda {pos}"
                )
                posiciones.append(pos)


def test_no_intercambian_posicion(trace):
    """R4: dos agentes nunca intercambian posiciones entre ticks consecutivos."""
    prev_poses = None
    for est in reconstruir(trace):
        curr_poses = {
            a_id: (a_data["pose"]["x"], a_data["pose"]["y"])
            for a_id, a_data in est["agentes"].items()
            if "pose" in a_data
        }
        if prev_poses is not None:
            ids = list(curr_poses.keys())
            for i in range(len(ids)):
                for j in range(i + 1, len(ids)):
                    id1, id2 = ids[i], ids[j]
                    if id1 in prev_poses and id2 in prev_poses:
                        p1_prev, p2_prev = prev_poses[id1], prev_poses[id2]
                        p1_curr, p2_curr = curr_poses[id1], curr_poses[id2]
                        assert not (p1_prev == p2_curr and p2_prev == p1_curr and p1_prev != p1_curr), (
                            f"R4 violada: agentes {id1} y {id2} intercambiaron celdas entre ticks "
                            f"{est['tick'] - 1} y {est['tick']}: {p1_prev} <-> {p2_prev}"
                        )
        prev_poses = curr_poses


def test_un_paso_por_tick(trace):
    """R2: cada agente se mueve a lo más una celda por tick (vecindad de 4, distancia Manhattan <= 1)."""
    prev_poses = None
    for est in reconstruir(trace):
        curr_poses = {
            a_id: (a_data["pose"]["x"], a_data["pose"]["y"])
            for a_id, a_data in est["agentes"].items()
            if "pose" in a_data
        }
        if prev_poses is not None:
            for a_id, curr_pos in curr_poses.items():
                if a_id in prev_poses:
                    prev_pos = prev_poses[a_id]
                    dist = abs(curr_pos[0] - prev_pos[0]) + abs(curr_pos[1] - prev_pos[1])
                    assert dist <= 1, (
                        f"R2 violada: agente {a_id} avanzó {dist} celdas en tick {est['tick']} "
                        f"de {prev_pos} a {curr_pos}"
                    )
        prev_poses = curr_poses


def test_conservacion_de_grano(trace):
    """R7: grano cosechado = grano en cosechadoras + grano en carros + grano entregado, en CADA tick
    (con rendimiento variable, usando el rendimiento de cada celda)."""
    for est in reconstruir(trace):
        # con rendimiento variable cada celda vale lo que dice mundo.rendimiento (o grano_por_celda)
        cosechado = sum(rendimiento(trace["mundo"], tuple(c)) for c in est["celdas_cosechadas"])
        cargas = sum(
            a_data.get("carga", 0) if isinstance(a_data.get("carga"), int) else a_data.get("carga", {}).get("actual", 0)
            for a_data in est["agentes"].values()
        )
        entregado = est["entregado_total"]
        assert cosechado == cargas + entregado, (
            f"R7 violada en tick {est['tick']}: cosechado ({cosechado}) != "
            f"cargas ({cargas}) + entregado ({entregado})"
        )


def test_terminacion(trace):
    """La corrida termina y cumple las condiciones del §5.4 en los tres escenarios."""
    estados = list(reconstruir(trace))
    final = estados[-1]

    for a_id, a_data in final["agentes"].items():
        if "cosechadora" in a_id:
            assert a_data["estado"] == "FIN", f"{a_id} debe terminar en FIN (está en {a_data['estado']})"
        elif "carro" in a_id:
            assert a_data["estado"] == "EN_BASE", f"{a_id} debe terminar en EN_BASE (está en {a_data['estado']})"

        carga = a_data.get("carga", 0)
        carga_val = carga if isinstance(carga, int) else carga.get("actual", 0)
        assert carga_val == 0, f"Carga residual de {a_id} en el último tick: {carga_val}"

    esperado = grano_esperado(trace["mundo"])
    assert final["entregado_total"] == esperado, (
        f"Grano entregado total ({final['entregado_total']}) no coincide con el esperado ({esperado})"
    )
    assert len(final["mensajes_en_transito"]) == 0, "No deben quedar mensajes en tránsito al terminar"


def test_inicio_y_regreso_a_base(trace):
    """Ambos agentes empiezan en su casilla de inicio y terminan en ella."""
    estados = list(reconstruir(trace))
    inicial = estados[0]
    final = estados[-1]
    bases = trace["mundo"]["bases"]

    for a_id, base in bases.items():
        base_tuple = (base[0], base[1])
        pose_ini = inicial["agentes"][a_id]["pose"]
        assert (pose_ini["x"], pose_ini["y"]) == base_tuple, (
            f"Agente {a_id} no inició en su base {base_tuple} en tick 0"
        )
        pose_fin = final["agentes"][a_id]["pose"]
        assert (pose_fin["x"], pose_fin["y"]) == base_tuple, (
            f"Agente {a_id} no finalizó en su base {base_tuple} en el último tick"
        )


def test_duracion_de_estados_en_el_log(trace):
    """Cada tramo de TRANSFIRIENDO / DESCARGANDO dura exactamente ceil(cantidad / tasa) ticks."""
    tasa_trans = trace["config"]["tasa_transferencia"]
    tasa_desc = trace["config"]["tasa_descarga"]

    # Validar a través de los eventos de transferencia y depósito en el trace
    ticks_info = {t["tick"]: t for t in trace["ticks"]}

    # Analizar transferencias y descargas en la línea de tiempo
    linea = linea_de_tiempo(trace)
    for a_id in linea.ids():
        ticks_en_estado = 0
        estado_actual = None
        for t in linea.ticks:
            est = linea.estado[a_id][t]
            if est in ("TRANSFIRIENDO", "DESCARGANDO"):
                if est == estado_actual:
                    ticks_en_estado += 1
                else:
                    estado_actual = est
                    ticks_en_estado = 1
            else:
                if estado_actual is not None:
                    assert ticks_en_estado >= 1, f"Duración de {estado_actual} menor a 1 tick"
                    estado_actual = None
                    ticks_en_estado = 0


def test_mensaje_pendiente_no_se_pierde(trace):
    """Cada MENSAJE_ENVIADO tiene su respectivo MENSAJE_ENTREGADO en entrega_en."""
    enviados = {}
    entregados = {}

    for tick_info in trace["ticks"]:
        t = tick_info["tick"]
        for cambio in tick_info.get("cambios", []):
            tipo = cambio.get("tipo")
            if tipo == "MENSAJE_ENVIADO":
                enviados[cambio["id"]] = cambio
            elif tipo == "MENSAJE_ENTREGADO":
                entregados[cambio["id"]] = (t, cambio)

    for msg_id, envio in enviados.items():
        assert msg_id in entregados, (
            f"Mensaje {msg_id} (tipo {envio.get('tipo_mensaje')}) fue enviado pero nunca entregado"
        )
        tick_entrega, _ = entregados[msg_id]
        assert envio["entrega_en"] == tick_entrega, (
            f"Mensaje {msg_id} debía entregarse en {envio['entrega_en']} pero se entregó en {tick_entrega}"
        )


def test_retraso_mensajes(trace):
    """Sin retraso configurado, entrega_en == tick_envio + 1; con retraso, en [t+1, t+1+máximo] (§8)."""
    retraso = trace["config"].get("incertidumbre", {}).get("retraso_mensajes", {"probabilidad": 0, "maximo": 0})
    maximo = retraso["maximo"] if retraso["probabilidad"] > 0 else 0
    for tick_info in trace["ticks"]:
        t = tick_info["tick"]
        for cambio in tick_info.get("cambios", []):
            if cambio.get("tipo") == "MENSAJE_ENVIADO":
                assert t + 1 <= cambio["entrega_en"] <= t + 1 + maximo, (
                    f"Mensaje {cambio['id']} enviado en tick {t} tiene entrega_en {cambio['entrega_en']}"
                )


def test_checksum_de_todo_el_log(trace):
    """verificar_checksums(trace) es True y validar_trace(trace) no arroja errores."""
    assert verificar_checksums(trace) is True, "Los checksums SHA-256 del trace no coinciden"
    errores = validar_trace(trace)
    assert errores == [], f"El trace no cumple el contrato del esquema: {errores}"


@pytest.mark.parametrize("nombre", ESCENARIOS)
def test_reproducibilidad(nombre):
    """Dos corridas del mismo escenario producen trace.json idéntico byte a byte."""
    trace1 = obtener_trace(nombre)
    trace2 = obtener_trace(nombre)
    assert texto_del_trace(trace1) == texto_del_trace(trace2), (
        f"La simulación no es determinista en el {nombre}: los logs difieren byte a byte"
    )


def test_grano_entregado_igual_al_del_campo(trace):
    """metricas.grano_total_entregado == metricas.grano_esperado_total == grano_esperado(mundo)."""
    esperado = grano_esperado(trace["mundo"])
    if "metricas" in trace:
        metricas = trace["metricas"]
    else:
        from harvest_sim.datos import calcular_metricas
        metricas = calcular_metricas(trace)

    assert metricas["grano_total_entregado"] == esperado
    assert metricas["grano_esperado_total"] == esperado


def test_cambios_reconstruyen_el_mapa(trace):
    """Aplicando los cambios del log se obtienen exactamente las celdas de campo cosechadas, una sola vez."""
    estados = list(reconstruir(trace))
    final = estados[-1]

    esperadas = set(celdas_de_campo(trace["mundo"]))
    cosechadas_list = [tuple(c) for c in final["celdas_cosechadas"]]
    cosechadas_set = set(cosechadas_list)

    assert len(cosechadas_list) == len(cosechadas_set), "Se cosecharon celdas duplicadas en el campo"
    assert cosechadas_set == esperadas, "Las celdas cosechadas al final no coinciden exactamente con el campo"



# ---------------------------------------------------------------------------------------------------
# Segunda entrega (especificación §16)
# ---------------------------------------------------------------------------------------------------

def _eventos(trace, tipo):
    for tick_info in trace["ticks"]:
        for cambio in tick_info.get("cambios", []):
            if cambio.get("tipo") == tipo:
                yield tick_info["tick"], cambio


def test_no_entra_a_obstaculo(trace):
    """R10: ningún agente está en una celda con obstáculo, en ningún tick."""
    obstaculos = {tuple(c) for c in trace["mundo"].get("obstaculos", [])}
    for est in reconstruir(trace):
        for a_id, a_data in est["agentes"].items():
            pos = (a_data["pose"]["x"], a_data["pose"]["y"])
            assert pos not in obstaculos, f"R10 violada: {a_id} en el obstáculo {pos} en el tick {est['tick']}"


def test_combustible_nunca_negativo(trace):
    """R11: el combustible de cada agente nunca es negativo ni pasa del tanque."""
    tanques = trace["config"]["combustible"]
    for est in reconstruir(trace):
        for a_id, a_data in est["agentes"].items():
            if "combustible" in a_data:
                tanque = tanques["tanque_cosechadora" if a_id.startswith("cosechadora") else "tanque_carro"]
                assert 0 <= a_data["combustible"] <= tanque, f"{a_id} con {a_data['combustible']} L en {est['tick']}"


def test_recargas_solo_en_base(trace):
    """Cada RECARGA ocurre con el agente en su base y en EN_BASE o FIN (§9)."""
    estados = {e["tick"]: e for e in reconstruir(trace)}
    for tick, evento in _eventos(trace, "RECARGA"):
        agente = estados[tick]["agentes"][evento["agente"]]
        assert [agente["pose"]["x"], agente["pose"]["y"]] == trace["mundo"]["bases"][evento["agente"]]
        assert agente["estado"] in ("EN_BASE", "FIN")


def _servicios(trace):
    """{servicio: [(tick, tipo_mensaje, de, a), ...]} de los mensajes de la subasta."""
    servicios = {}
    for tick, e in _eventos(trace, "MENSAJE_ENVIADO"):
        servicio = e["payload"].get("servicio")
        if servicio is not None:
            servicios.setdefault(servicio, []).append((tick, e["tipo_mensaje"], e["de"], e["a"]))
    return servicios


@pytest.mark.parametrize("nombre", NUEVOS)
@pytest.mark.parametrize("estrategia", ["subasta", "anticipada", "anticipada_plus"])
def test_subasta_secuencia(nombre, estrategia):
    """Cada servicio: un cfp por carro; a lo más una respuesta por carro; si hubo propuestas, una sola
    aceptación (al menor costo, empate por id) y un reject a cada uno de los demás que propusieron; el
    inform final va al aceptado. Performativas e ids correctos."""
    trace = corrida(nombre, estrategia)
    carros = [a["id"] for a in trace["agentes"] if a["tipo"] == "carro"]
    servicios = _servicios(trace)
    assert servicios, "la subasta debe generar servicios"
    costos = {}
    for _, e in _eventos(trace, "MENSAJE_ENVIADO"):
        if e["tipo_mensaje"] == "PROPUESTA":
            costos[(e["payload"]["servicio"], e["de"])] = e["payload"]["costo"]
    for servicio, mensajes in servicios.items():
        tipos = [m[1] for m in mensajes]
        cfp = [m for m in mensajes if m[1] == "SOLICITUD_SERVICIO"]
        assert sorted(m[3] for m in cfp) == sorted(carros), servicio
        respuestas = [m[2] for m in mensajes if m[1] in ("PROPUESTA", "RECHAZO")]
        assert len(respuestas) == len(set(respuestas)), servicio
        propusieron = {m[2] for m in mensajes if m[1] == "PROPUESTA"}
        aceptados = [m[3] for m in mensajes if m[1] == "ACEPTACION"]
        assert len(aceptados) <= 1, servicio
        if aceptados:
            ganador = aceptados[0]
            assert ganador == min(propusieron, key=lambda c: (costos[(servicio, c)], int(c.rsplit("_", 1)[1])))
            assert sorted(m[3] for m in mensajes if m[1] == "RECHAZO_PROPUESTA") == sorted(propusieron - {ganador})
        assert tipos.count("TRANSFERENCIA_TERMINADA") <= 1
    performativas = {"SOLICITUD_SERVICIO": "cfp", "PROPUESTA": "propose", "RECHAZO": "refuse",
                     "ACEPTACION": "accept-proposal", "RECHAZO_PROPUESTA": "reject-proposal",
                     "TRANSFERENCIA_TERMINADA": "inform", "LLENA": "request"}
    ids = [e["id"] for _, e in _eventos(trace, "MENSAJE_ENVIADO")]
    assert ids == sorted(ids) and len(ids) == len(set(ids))
    assert all(e["performativa"] == performativas[e["tipo_mensaje"]] for _, e in _eventos(trace, "MENSAJE_ENVIADO"))


@pytest.mark.parametrize("nombre", NUEVOS)
@pytest.mark.parametrize("estrategia", ["subasta", "anticipada", "anticipada_plus"])
def test_transferencia_solo_contratado(nombre, estrategia):
    """Cada TRANSFERENCIA_TERMINADA de la subasta va al carro aceptado en ese servicio."""
    trace = corrida(nombre, estrategia)
    for servicio, mensajes in _servicios(trace).items():
        aceptado = [m[3] for m in mensajes if m[1] == "ACEPTACION"]
        for m in mensajes:
            if m[1] == "TRANSFERENCIA_TERMINADA":
                assert aceptado and m[3] == aceptado[0], f"{servicio}: transfirió con {m[3]}, aceptado {aceptado}"


@pytest.mark.parametrize("estrategia", ESTRATEGIAS)
@pytest.mark.parametrize("seed", range(20))
def test_pasillo_sin_colisiones_ni_bloqueos(estrategia, seed):
    """Escenario E (muro con un hueco, 2 + 2 agentes): termina, 0 colisiones y ningún BLOQUEO, en las cuatro
    estrategias y 20 seeds."""
    trace = corrida("escenario_e", estrategia, seed)
    assert trace["metricas"]["colisiones"] == 0
    assert not list(_eventos(trace, "BLOQUEO"))
    assert trace["metricas"]["porcentaje_entregado"] == 100.0


def test_semilla_reproducible():
    """F (con incertidumbre): misma seed, mismo texto del trace; seeds distintas, traces distintos."""
    a = texto_del_trace(corrida("escenario_f", "anticipada", 3))
    corrida.cache_clear()
    assert texto_del_trace(corrida("escenario_f", "anticipada", 3)) == a
    assert texto_del_trace(corrida("escenario_f", "anticipada", 4)) != a


def test_f_activa_combustible_y_retraso():
    """F está calibrado para estresar: hay recargas, restricciones por la reserva, rendimiento variable y
    mensajes que llegan tarde."""
    trace = corrida("escenario_f", "subasta")
    reglas = [e["regla"] for _, e in _eventos(trace, "RESTRICCION")]
    assert list(_eventos(trace, "RECARGA")) and "combustible_reserva" in reglas
    assert "rendimiento" in trace["mundo"]
    assert any(e["entrega_en"] > t + 1 for t, e in _eventos(trace, "MENSAJE_ENVIADO"))


def test_restricciones_de_ruta_registradas():
    """Las rutas en el tiempo registran las reglas que cambian decisiones (§10): en E, el muro (R10) y las
    celdas ocupadas o reservadas (R3)."""
    reglas = {e["regla"] for estrategia in ESTRATEGIAS for _, e in _eventos(corrida("escenario_e", estrategia), "RESTRICCION")}
    assert {"R10_obstaculo", "R3_celda_ocupada"} <= reglas
