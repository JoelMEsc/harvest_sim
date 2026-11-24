
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
    retraso = config.incertidumbre["retraso_mensajes"]
    buzon = Buzon(mundo.azar("mensajes"), retraso["probabilidad"], retraso["maximo"])

    # orden del tick y del catálogo: cosechadoras y luego carros, por id (spec §3)
    cosechadoras = [
        Cosechadora(f"cosechadora_{j}", config.capacidad_cosechadora)
        for j in range(1, config.num_cosechadoras + 1)
    ]
    carros = [
        Carro(f"carro_{i}", config.capacidad_carro)
        for i in range(1, config.num_carros + 1)
    ]
    agentes = cosechadoras + carros

    for agente in agentes:
        mundo.registrar(agente)

    # crear el catálogo estático de agentes
    catalogo = []
    for agente in agentes:
        catalogo.append({
            "id": agente.agent_id,
            "tipo": COSECHADORA if agente in cosechadoras else CARRO,
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

        # olvidar las reservas pasadas y entregar los mensajes que llegan en este tick
        mundo.nuevo_tick(tick)
        buzon.entregar(tick)
        inicio = {agente.agent_id: agente.posicion for agente in agentes}

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

        # combustible: consumo y recarga después de que todos actuaron (spec §9)
        for agente in agentes:
            mundo.actualizar_combustible(agente, agente.posicion != inicio[agente.agent_id])

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

            elif evento["tipo"] == "RECARGA":
                registrador.info(
                    "t=%03d | %s recarga %.2f L (nivel: %.2f)",
                    tick, evento["agente"], evento["cantidad"], evento["nivel"],
                )

            elif evento["tipo"] == "RESTRICCION":
                registrador.info(
                    "t=%03d | %s RESTRICCION %s: %s",
                    tick, evento["agente"], evento["regla"], evento["detalle"],
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
        if _terminado(mundo, buzon, cosechadoras, carros):
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


def _terminado(mundo: Mundo, buzon: Buzon, cosechadoras: list, carros: list) -> bool:
    """Término (spec §3): todas las cosechadoras en FIN; todos los carros en EN_BASE, vacíos y sin
    servicios en cola; ningún mensaje pendiente; todo el grano entregado."""
    return (
        all(c.estado == FIN for c in cosechadoras)
        and all(c.estado == EN_BASE and c.carga == 0 and not getattr(c, "servicios", ()) for c in carros)
        and not any(buzon.hay_pendientes(a.agent_id) for a in cosechadoras + carros)
        and mundo.entregado == mundo.grano_total
    )
