"""Corridas completas de extremo a extremo.  [Dueño: Ilan]

Activos desde la integración del 17 de noviembre: corren la simulación real con los tres escenarios.
"""

import math
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

CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"
ESCENARIOS = ["escenario_a", "escenario_b", "escenario_c"]


def obtener_trace(nombre: str) -> dict:
    """Carga la configuración y ejecuta una corrida completa de un escenario."""
    from harvest_sim.config import cargar_config
    from harvest_sim.simulacion import ejecutar

    config_path = CONFIG_DIR / f"{nombre}.json"
    config = cargar_config(config_path)
    return ejecutar(config)


@pytest.fixture(scope="module", params=ESCENARIOS)
def trace(request):
    """Fixture que produce el log de una corrida real para cada escenario."""
    return obtener_trace(request.param)


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
    """R7: grano cosechado = grano en cosechadora + grano en carro + grano entregado, en CADA tick."""
    grano_por_celda = trace["mundo"]["grano_por_celda"]
    for est in reconstruir(trace):
        cosechado = len(est["celdas_cosechadas"]) * grano_por_celda
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


def test_mensajes_viajan_al_tick_siguiente(trace):
    """En el log, entrega_en == tick_envio + 1 para todos los mensajes enviados."""
    for tick_info in trace["ticks"]:
        t = tick_info["tick"]
        for cambio in tick_info.get("cambios", []):
            if cambio.get("tipo") == "MENSAJE_ENVIADO":
                assert cambio["entrega_en"] == t + 1, (
                    f"Mensaje {cambio['id']} enviado en tick {t} tiene entrega_en {cambio['entrega_en']} != {t + 1}"
                )


def test_checksum_de_todo_el_log(trace):
    """verificar_checksums(trace) es True y validar_trace(trace) no arroja errores."""
    assert verificar_checksums(trace) is True, "Los checksums SHA-256 del trace no coinciden"
    errores = validar_trace(trace)
    assert errores == [], f"El trace no cumple el contrato del esquema 2.1: {errores}"


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
