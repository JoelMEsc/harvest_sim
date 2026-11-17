
"""Bucle principal de la simulación y condición de término.

Especificación: secciones 4.1, 5.4 y 6.
"""

from __future__ import annotations

import logging
from dataclasses import asdict

from .config import Config
from .mundo import Mundo
from .cosechadora import Cosechadora
from .carro import Carro
from .mensajes import Buzon
from .datos import TraceBuilder, calcular_metricas
from .datos.formato import COSECHADORA, CARRO, FIN, EN_BASE


registrador = logging.getLogger("harvest_sim.simulacion")


def ejecutar(config: Config) -> dict:
    """Ejecuta una simulación completa y devuelve su trace con métricas."""

    mundo = Mundo(config)
    buzon = Buzon()

    cosechadora = Cosechadora(
        "cosechadora_1", config.capacidad_cosechadora
    )
    carro = Carro(
        "carro_1", config.capacidad_carro
    )

    agentes = [cosechadora, carro]

    for agente in agentes:
        mundo.registrar(agente)

    # crear el catálogo estático de agentes
    catalogo = []
    for agente, tipo in (
        (cosechadora, COSECHADORA),
        (carro, CARRO),
    ):
        catalogo.append({
            "id": agente.agent_id,
            "tipo": tipo,
            "capacidad": agente.capacidad,
            "base": list(mundo.base_de(agente.agent_id)),
        })

    constructor = TraceBuilder(
        asdict(config),
        mundo.descripcion(),
        catalogo,
    )

    # el tick cero representa el estado inicial
    constructor.agregar_tick(
        0,
        [agente.registro(0) for agente in agentes],
        [],
    )

    for tick in range(1, config.max_ticks + 1):

        # entregar los mensajes enviados en el tick anterior
        buzon.entregar(tick)

        # ejecutar primero la cosechadora y después el carro
        for agente in agentes:
            estado_anterior = agente.estado
            posicion_anterior = agente.posicion

            agente.paso(tick, mundo, buzon)

            if agente.estado != estado_anterior:
                registrador.info(
                    "t=%03d | %s | %s -> %s",
                    tick,
                    agente.agent_id,
                    getattr(estado_anterior, "value", estado_anterior),
                    getattr(agente.estado, "value", agente.estado),
                )

            if agente.posicion != posicion_anterior:
                registrador.debug(
                    "t=%03d | %s | movimiento %s -> %s",
                    tick,
                    agente.agent_id,
                    posicion_anterior,
                    agente.posicion,
                )

        # recoger los eventos producidos durante este tick
        eventos = buzon.drenar_eventos() + mundo.drenar_eventos()

        for evento in eventos:
            if evento["tipo"] == "DEPOSITO":
                registrador.info(
                    "t=%03d | %s deposita %d en la bodega (entregado: %d/%d)",
                    tick,
                    evento["agente"],
                    evento["cantidad"],
                    evento["entregado_total"],
                    mundo.grano_total,
                )

            elif evento["tipo"] == "CELDA_COSECHADA":
                registrador.debug(
                    "t=%03d | %s cosecha la celda %s",
                    tick,
                    evento["agente"],
                    evento["celda"],
                )

        # guardar el estado al final del tick
        constructor.agregar_tick(
            tick,
            [agente.registro(tick) for agente in agentes],
            eventos,
        )

        # comprobar si todas las operaciones han terminado
        if (
            cosechadora.estado == FIN
            and carro.estado == EN_BASE
            and not buzon.hay_pendientes(carro.agent_id)
            and carro.carga == 0
            and mundo.entregado == mundo.grano_total
        ):
            break

    else:
        mensaje = (
            f"simulación inconclusa: se alcanzó max_ticks={config.max_ticks}; "
            f"grano entregado: {mundo.entregado}/{mundo.grano_total}"
        )
        registrador.error("t=%03d | %s", config.max_ticks, mensaje)
        raise RuntimeError(mensaje)

    # construir el trace y calcular las métricas desde sus eventos
    trace = constructor.construir()
    trace["metricas"] = calcular_metricas(trace)

    return trace
