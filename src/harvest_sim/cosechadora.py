"""Cosechadora: agente reactivo con estado.  [Bloque B]

Especificación: §5.1 (tabla de estados y transiciones). Camino fijo: serpentina.
"""

from __future__ import annotations

from enum import Enum

from .mensajes import Buzon, Mensaje, TipoMensaje
from .mundo import Mundo, duracion_ticks


class EstadoCosechadora(str, Enum):
    EN_BASE = "EN_BASE"
    YENDO_A_CAMPO = "YENDO_A_CAMPO"
    COSECHANDO = "COSECHANDO"
    LLENA_ESPERANDO = "LLENA_ESPERANDO"
    TRANSFIRIENDO = "TRANSFIRIENDO"
    REGRESANDO_A_BASE = "REGRESANDO_A_BASE"
    FIN = "FIN"


class Cosechadora:
    def __init__(self, agent_id: str, capacidad: int) -> None:
        self.agent_id = agent_id
        self.capacidad = capacidad
        self.estado = EstadoCosechadora.EN_BASE
        self.carga = 0

        # Mundo.registrar() asigna la posición inicial antes de ejecutar pasos.
        self.posicion: tuple[int, int] | None = None
        self.orientacion = "S"

        self._base: tuple[int, int] | None = None
        self._camino: list[tuple[int, int]] = []
        self._indice = 0
        self._ticks_restantes = 0
        self._cantidad_transferencia = 0

        # Esta entrega contempla una cosechadora y un carro.
        self._carro_id = "carro_1"

    def paso(self, tick: int, mundo: Mundo, buzon: Buzon) -> None:
        """Implementar la tabla del §5.1. Recordar:
        - Evaluación de carga tras cosechar: enviar LLENA si carga == capacidad o si fue
          la última celda del camino (carga parcial).
        - Iniciar la transferencia solo si el carro está vecino Y en ESPERANDO_TRANSFERENCIA.
        - Duración = ceil(cantidad / tasa_transferencia), calculada al entrar a TRANSFIRIENDO.
        - Al salir de TRANSFIRIENDO: mundo.transferir(...) y enviar TRANSFERENCIA_TERMINADA
          con `cantidad`.
        - Conflictos de celda: espera si la siguiente celda del camino está ocupada (§4.2).
        """
        if self.posicion is None:
            raise RuntimeError(
                "La cosechadora debe registrarse en el mundo antes de avanzar."
            )

        if self.estado == EstadoCosechadora.FIN:
            return

        if self.estado == EstadoCosechadora.EN_BASE:
            self._base = mundo.base_de(self.agent_id)
            self._camino = list(mundo.camino_serpentina())

            if not self._camino:
                raise ValueError("El campo debe tener al menos una celda.")

            self._indice = 0
            self.estado = EstadoCosechadora.YENDO_A_CAMPO
            return

        if self.estado == EstadoCosechadora.YENDO_A_CAMPO:
            destino = self._camino[0]

            if self.posicion != destino:
                if not self._avanzar_hacia(destino, mundo):
                    return

            if self.posicion == destino:
                self._cosechar_y_evaluar(tick, mundo, buzon)

            return

        if self.estado == EstadoCosechadora.COSECHANDO:
            siguiente = self._camino[self._indice + 1]

            if siguiente in mundo.ocupadas(self.agent_id):
                mundo.registrar_bloqueo(self.agent_id)
                return

            self._mover_a(siguiente)
            self._indice += 1
            self._cosechar_y_evaluar(tick, mundo, buzon)
            return

        if self.estado == EstadoCosechadora.LLENA_ESPERANDO:
            carro_vecino = (
                mundo.posicion(self._carro_id)
                in mundo.vecinos(self.posicion)
            )
            carro_listo = (
                mundo.estado_de(self._carro_id)
                == "ESPERANDO_TRANSFERENCIA"
            )

            if carro_vecino and carro_listo:
                # El carro llega vacío y puede recibir toda la carga
                # según las restricciones de esta entrega.
                self._cantidad_transferencia = self.carga

                duracion = duracion_ticks(
                    self._cantidad_transferencia,
                    mundo.config.tasa_transferencia,
                )

                # El tick de entrada ya cuenta como el primer snapshot.
                self._ticks_restantes = duracion - 1
                self.estado = EstadoCosechadora.TRANSFIRIENDO

            return

        if self.estado == EstadoCosechadora.TRANSFIRIENDO:
            if self._ticks_restantes > 0:
                self._ticks_restantes -= 1
                return

            cantidad = mundo.transferir(
                self.agent_id,
                self._carro_id,
                self._cantidad_transferencia,
            )

            buzon.enviar(Mensaje(
                tipo=TipoMensaje.TRANSFERENCIA_TERMINADA,
                emisor=self.agent_id,
                receptor=self._carro_id,
                tick_envio=tick,
                payload={"cantidad": cantidad},
            ))

            if self._indice == len(self._camino) - 1:
                self.estado = EstadoCosechadora.REGRESANDO_A_BASE
            else:
                self.estado = EstadoCosechadora.COSECHANDO

            return

        if self.estado == EstadoCosechadora.REGRESANDO_A_BASE:
            if self.posicion == self._base:
                self.estado = EstadoCosechadora.FIN
                return

            self._avanzar_hacia(self._base, mundo)

    def _cosechar_y_evaluar(
        self, tick: int, mundo: Mundo, buzon: Buzon
    ) -> None:
        """Cosecha mediante el mundo y solicita al carro cuando corresponde."""
        mundo.cosechar(self.agent_id, self.posicion)

        ultima_celda = self._indice == len(self._camino) - 1

        if self.carga == self.capacidad or ultima_celda:
            buzon.enviar(Mensaje(
                tipo=TipoMensaje.LLENA,
                emisor=self.agent_id,
                receptor=self._carro_id,
                tick_envio=tick,
                payload={
                    "x": self.posicion[0],
                    "y": self.posicion[1],
                    "carga": self.carga,
                },
            ))

            self.estado = EstadoCosechadora.LLENA_ESPERANDO
        else:
            self.estado = EstadoCosechadora.COSECHANDO

    def _avanzar_hacia(
        self, destino: tuple[int, int], mundo: Mundo
    ) -> bool:
        """Avanza por BFS hacia el campo o la base, evitando celdas ocupadas."""
        ocupadas = mundo.ocupadas(self.agent_id)
        fijas = mundo.bloqueadas_fijas(self.agent_id)

        ruta = mundo.ruta_bfs(
            self.posicion,
            destino,
            fijas | ocupadas,
        )

        if ruta is None:
            # Solo se cuenta como bloqueo si las ocupaciones
            # impiden una ruta que existiría sin otros agentes.
            ruta_sin_agentes = mundo.ruta_bfs(
                self.posicion,
                destino,
                fijas,
            )

            if ruta_sin_agentes:
                mundo.registrar_bloqueo(self.agent_id)

            return False

        if ruta:
            self._mover_a(ruta[0])

        return True

    def _mover_a(self, destino: tuple[int, int]) -> None:
        """Actualiza la posición y orientación con un movimiento de una celda."""
        dx = destino[0] - self.posicion[0]
        dy = destino[1] - self.posicion[1]

        direcciones = {
            (0, -1): "N",
            (1, 0): "E",
            (0, 1): "S",
            (-1, 0): "O",
        }

        if (dx, dy) not in direcciones:
            raise ValueError("El movimiento debe ser a una celda vecina.")

        self.orientacion = direcciones[(dx, dy)]
        self.posicion = destino

    def registro(self, tick: int) -> dict:
        if self.posicion is None:
            raise RuntimeError(
                "La cosechadora debe registrarse antes de generar su registro."
            )

        return {
            "tick": tick,
            "agent_id": self.agent_id,
            "tipo": "cosechadora",
            "pose": {
                "x": self.posicion[0],
                "y": self.posicion[1],
                "orientacion": self.orientacion,
            },
            "estado": self.estado.value,
            "carga": {
                "actual": self.carga,
                "capacidad": self.capacidad,
            },
        }