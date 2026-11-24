"""Tipos de mensaje y buzón central.  [Bloque B]

Especificación: §4.4 y §4.5. Todos los mensajes pasan por el Buzon, aunque la
comunicación sea directa; así un despachador podrá insertarse después.
"""

from __future__ import annotations

import logging
from collections import deque
from copy import deepcopy
from dataclasses import dataclass, field
from enum import Enum

from harvest_sim.datos.formato import PERFORMATIVAS


logger = logging.getLogger("harvest_sim.mensajes")


class TipoMensaje(str, Enum):
    LLENA = "LLENA"                                    # request; payload: x, y, carga
    TRANSFERENCIA_TERMINADA = "TRANSFERENCIA_TERMINADA"  # inform; payload: cantidad (y servicio en subasta)
    # Contract Net (segunda entrega §7): la cosechadora administra, los carros ofertan
    SOLICITUD_SERVICIO = "SOLICITUD_SERVICIO"          # cfp; payload: servicio, x, y, carga, capacidad
    PROPUESTA = "PROPUESTA"                            # propose; payload: servicio, costo
    RECHAZO = "RECHAZO"                                # refuse; payload: servicio, motivo
    ACEPTACION = "ACEPTACION"                          # accept-proposal; payload: servicio
    RECHAZO_PROPUESTA = "RECHAZO_PROPUESTA"            # reject-proposal; payload: servicio


@dataclass
class Mensaje:
    tipo: TipoMensaje
    emisor: str
    receptor: str
    tick_envio: int
    payload: dict = field(default_factory=dict)
    id: int = 0  # lo asigna el Buzon al enviar (1, 2, 3, ...)
    entrega_en: int = 0  # tick en que se entrega; lo asigna el Buzon al enviar


class Buzon:
    """Fila FIFO de entrada por agente. Un mensaje enviado en el tick t se lee desde t+1, o más tarde
    si le toca retraso (segunda entrega §8): con probabilidad `probabilidad` llega U{1..maximo}
    ticks después. Con probabilidad 0 (o sin generador) nunca se llama al azar: es la línea base."""

    def __init__(self, azar=None, probabilidad: float = 0.0, maximo: int = 0) -> None:
        self._azar = azar
        self._probabilidad = probabilidad
        self._maximo = maximo
        self._siguiente_id = 1
        self._en_transito: list[Mensaje] = []
        self._entradas: dict[str, deque[Mensaje]] = {}
        self._eventos: list[dict] = []

    def enviar(self, mensaje: Mensaje) -> int:
        """Asigna un id único y creciente, encola el mensaje para entregarlo en tick+1
        y lo registra para el log. Devuelve el id.
        También imprime el envío con logging.getLogger("harvest_sim.mensajes") (§6.3):
        t=014 | MSG #1 LLENA cosechadora_1 -> carro_1 {x: 5, y: 1, carga: 10} (se entrega en t=015)"""
        mensaje.id = self._siguiente_id
        self._siguiente_id += 1

        pendiente = deepcopy(mensaje)
        self._en_transito.append(pendiente)

        entrega_en = pendiente.tick_envio + 1
        # maximo >= 1 evita randint(1, 0) si alguien pide retraso sin máximo
        if self._azar is not None and self._probabilidad > 0 and self._maximo >= 1:
            if self._azar.random() < self._probabilidad:
                entrega_en += self._azar.randint(1, self._maximo)
        pendiente.entrega_en = entrega_en
        mensaje.entrega_en = entrega_en

        self._eventos.append({
            "tipo": "MENSAJE_ENVIADO",
            "id": pendiente.id,
            "tipo_mensaje": pendiente.tipo.value,
            "performativa": PERFORMATIVAS[pendiente.tipo.value],
            "de": pendiente.emisor,
            "a": pendiente.receptor,
            "payload": deepcopy(pendiente.payload),
            "entrega_en": entrega_en,
        })

        contenido = ", ".join(
            f"{clave}: {valor}"
            for clave, valor in pendiente.payload.items()
        )

        logger.info(
            "t=%03d | MSG #%d %s %s -> %s {%s} "
            "(se entrega en t=%03d)",
            pendiente.tick_envio,
            pendiente.id,
            pendiente.tipo.value,
            pendiente.emisor,
            pendiente.receptor,
            contenido,
            entrega_en,
        )

        return pendiente.id

    def entregar(self, tick: int) -> None:
        """Inicio de cada tick: pasa a los buzones de entrada los mensajes con entrega_en == tick.
        Imprime cada entrega: t=015 | MSG #1 entregado a carro_1"""
        pendientes = []

        # en el orden de su id (con retraso, uno enviado antes puede llegar después)
        for mensaje in sorted(self._en_transito, key=lambda m: m.id):
            if mensaje.entrega_en == tick:
                fila = self._entradas.setdefault(
                    mensaje.receptor, deque()
                )
                fila.append(mensaje)

                self._eventos.append({
                    "tipo": "MENSAJE_ENTREGADO",
                    "id": mensaje.id,
                    "a": mensaje.receptor,
                })

                logger.info(
                    "t=%03d | MSG #%d entregado a %s",
                    tick,
                    mensaje.id,
                    mensaje.receptor,
                )
            else:
                pendientes.append(mensaje)

        self._en_transito = pendientes

    def leer(self, agent_id: str) -> Mensaje | None:
        """Saca el siguiente mensaje de la fila de `agent_id` (FIFO), o None si está vacía."""
        fila = self._entradas.get(agent_id)

        if fila:
            return fila.popleft()

        return None

    def hay_pendientes(self, agent_id: str) -> bool:
        if self._entradas.get(agent_id):
            return True

        return any(
            mensaje.receptor == agent_id
            for mensaje in self._en_transito
        )

    def drenar_eventos(self) -> list[dict]:
        """Devuelve los eventos acumulados para el log y vacía la lista."""
        eventos = self._eventos
        self._eventos = []
        return eventos