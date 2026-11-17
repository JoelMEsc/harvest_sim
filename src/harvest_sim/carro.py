"""Carro recolector: agente reactivo con estado.  [Oswaldo]

Especificación: §5.2 (tabla de estados y transiciones), §4.2 (conflictos de celda),
§4.3 (duraciones) y §5.3 (reposo en EN_BASE).

Convención de tiempo (igual que el simulador de referencia, tools/generar_trace_ejemplo.py):
  - Una transición que sale de un estado "quieto" (EN_BASE, ESPERANDO_TRANSFERENCIA,
    DESCARGANDO) no incluye movimiento en ese tick.
  - En los estados de viaje, el carro da su paso y, si con ese paso llegó, cambia de
    estado en el mismo tick (no pierde un tick parado en la meta).
"""

from __future__ import annotations

import logging
from collections import deque
from enum import Enum
from typing import TYPE_CHECKING

from . import rutas
from .datos.formato import CARRO
from .mensajes import Mensaje, TipoMensaje

if TYPE_CHECKING:
    from .mensajes import Buzon
    from .mundo import Mundo

Celda = tuple[int, int]

registrador = logging.getLogger("harvest_sim.carro")

# Desplazamiento (dx, dy) del último movimiento -> orientación. y crece hacia abajo: N es y - 1.
ORIENTACION: dict[Celda, str] = {(0, -1): "N", (1, 0): "E", (0, 1): "S", (-1, 0): "O"}


class EstadoCarro(str, Enum):
    EN_BASE = "EN_BASE"
    YENDO_A_COSECHADORA = "YENDO_A_COSECHADORA"
    ESPERANDO_TRANSFERENCIA = "ESPERANDO_TRANSFERENCIA"
    YENDO_A_BODEGA = "YENDO_A_BODEGA"
    DESCARGANDO = "DESCARGANDO"
    REGRESANDO_A_BASE = "REGRESANDO_A_BASE"


def duracion_descarga(cantidad: int, tasa: int) -> int:
    """ceil(cantidad / tasa), al menos 1 tick (§4.3). Misma fórmula que mundo.duracion_ticks."""
    if tasa <= 0:
        raise ValueError("tasa_descarga debe ser un entero positivo")
    return max(1, (cantidad + tasa - 1) // tasa)


class Carro:
    """Máquina de estados del §5.2.

    Atributos públicos: agent_id, capacidad, estado, carga, posicion (la asigna
    Mundo.registrar), orientacion y la memoria del agente: objetivo (celda donde se
    estaciona junto a la cosechadora), ruta (celdas que faltan) y cantidad_recibida
    (la `cantidad` del último TRANSFERENCIA_TERMINADA).

    `tasa_descarga` es opcional: si no se pasa, se lee de `mundo.config.tasa_descarga`
    al empezar a descargar (así lo hace también la cosechadora con su tasa).
    """

    def __init__(self, agent_id: str, capacidad: int, tasa_descarga: int | None = None) -> None:
        self.agent_id = agent_id
        self.capacidad = capacidad
        self.tasa_descarga = tasa_descarga
        self.estado = EstadoCarro.EN_BASE
        self.carga = 0
        self.posicion: Celda | None = None
        self.orientacion = "N"

        # Memoria (§5.2).
        self.objetivo: Celda | None = None
        self.ruta: list[Celda] = []
        self.cantidad_recibida: int | None = None
        self._destino: Celda | None = None
        self._ticks_restantes = 0
        # LLENA que se sacaron de la fila sin poder atenderlos todavía. Nunca se descartan:
        # se atienden primero al volver a EN_BASE (regla del carro ocupado).
        self._llenas_guardadas: deque[Mensaje] = deque()

    # ------------------------------------------------------------------ paso

    def paso(self, tick: int, mundo: Mundo, buzon: Buzon) -> None:
        """Un tick de la tabla del §5.2."""
        if self.posicion is None:
            raise RuntimeError("El carro debe registrarse en el mundo antes de avanzar.")

        if self.estado == EstadoCarro.EN_BASE:
            self._atender_llena(mundo, buzon)

        elif self.estado == EstadoCarro.YENDO_A_COSECHADORA:
            if self._avanzar(mundo):
                self.estado = EstadoCarro.ESPERANDO_TRANSFERENCIA

        elif self.estado == EstadoCarro.ESPERANDO_TRANSFERENCIA:
            self._esperar_transferencia(mundo, buzon)

        elif self.estado == EstadoCarro.YENDO_A_BODEGA:
            if self._avanzar(mundo):
                self._empezar_descarga(mundo)

        elif self.estado == EstadoCarro.DESCARGANDO:
            self._descargar(mundo)

        elif self.estado == EstadoCarro.REGRESANDO_A_BASE:
            if self._avanzar(mundo):
                self._destino = None
                self.objetivo = None
                self.estado = EstadoCarro.EN_BASE

    # ------------------------------------------------------------ estados

    def _atender_llena(self, mundo: Mundo, buzon: Buzon) -> None:
        """EN_BASE: toma el LLENA más antiguo (FIFO), elige la celda objetivo y calcula la ruta."""
        mensaje = self._siguiente_llena(buzon)
        if mensaje is None:
            return

        cosechadora = (mensaje.payload["x"], mensaje.payload["y"])
        objetivo = rutas.elegir_celda_objetivo(
            self.posicion,
            cosechadora,
            mundo.ancho,
            mundo.alto,
            bloqueadas=mundo.ocupadas(self.agent_id) | {mundo.bodega},
            evitar=self._siguiente_de_serpentina(mundo, cosechadora),
        )
        if objetivo is None:
            # Ninguna vecina alcanzable por ahora: el mensaje no se descarta, se reintenta.
            self._llenas_guardadas.appendleft(mensaje)
            return

        self.objetivo = objetivo
        self._fijar_destino(objetivo, mundo)
        self.estado = EstadoCarro.YENDO_A_COSECHADORA

    def _esperar_transferencia(self, mundo: Mundo, buzon: Buzon) -> None:
        """ESPERANDO_TRANSFERENCIA: espera inmóvil el TRANSFERENCIA_TERMINADA (no es un bloqueo)."""
        mensaje = buzon.leer(self.agent_id)
        while mensaje is not None and mensaje.tipo != TipoMensaje.TRANSFERENCIA_TERMINADA:
            if mensaje.tipo == TipoMensaje.LLENA:
                self._llenas_guardadas.append(mensaje)  # para después; nunca se descarta
            mensaje = buzon.leer(self.agent_id)
        if mensaje is None:
            return

        # La transferencia física ya la hizo el mundo; el carro solo registra la cantidad.
        self.cantidad_recibida = mensaje.payload["cantidad"]
        if self.cantidad_recibida != self.carga:
            registrador.warning(
                "%s: TRANSFERENCIA_TERMINADA dice %s, pero la carga es %s",
                self.agent_id, self.cantidad_recibida, self.carga,
            )

        self._fijar_destino(mundo.bodega, mundo)
        self.estado = EstadoCarro.YENDO_A_BODEGA

    def _empezar_descarga(self, mundo: Mundo) -> None:
        """Llegó a la bodega: calcula la duración al entrar al estado (§4.3)."""
        duracion = duracion_descarga(self.carga, self._tasa_descarga(mundo))
        # El tick de entrada ya cuenta como el primero de los `duracion` snapshots.
        self._ticks_restantes = duracion - 1
        self.estado = EstadoCarro.DESCARGANDO

    def _descargar(self, mundo: Mundo) -> None:
        """DESCARGANDO: decrementa; al agotarse, el mundo deposita (carga = 0, evento DEPOSITO)."""
        if self._ticks_restantes > 0:
            self._ticks_restantes -= 1
            return

        mundo.depositar(self.agent_id)
        self._fijar_destino(mundo.base_de(self.agent_id), mundo)
        self.estado = EstadoCarro.REGRESANDO_A_BASE

    # --------------------------------------------------------- auxiliares

    def _siguiente_llena(self, buzon: Buzon) -> Mensaje | None:
        """Primero los LLENA guardados; si no hay, el siguiente de la fila (uno por tick)."""
        if self._llenas_guardadas:
            return self._llenas_guardadas.popleft()

        mensaje = buzon.leer(self.agent_id)
        if mensaje is not None and mensaje.tipo != TipoMensaje.LLENA:
            registrador.warning("%s: mensaje %s inesperado en EN_BASE", self.agent_id, mensaje.tipo)
            return None
        return mensaje

    @staticmethod
    def _siguiente_de_serpentina(mundo: Mundo, celda: Celda) -> set[Celda]:
        """La celda que sigue a `celda` en el camino de la cosechadora (§4.2, regla 4)."""
        camino = mundo.camino_serpentina()
        try:
            indice = camino.index(celda)
        except ValueError:
            return set()
        return {camino[indice + 1]} if indice + 1 < len(camino) else set()

    def _fijar_destino(self, destino: Celda, mundo: Mundo) -> None:
        """Calcula la ruta BFS hacia `destino` tratando a los otros agentes como bloqueados."""
        self._destino = destino
        bloqueadas = mundo.ocupadas(self.agent_id) | mundo.bloqueadas_fijas(self.agent_id)
        # Si ahora no hay ruta (destino ocupado), se queda vacía y siguiente_paso la recalcula.
        self.ruta = mundo.ruta_bfs(self.posicion, destino, bloqueadas) or []

    def _avanzar(self, mundo: Mundo) -> bool:
        """Un paso hacia el destino con resolución de conflictos (§4.2). Devuelve True si llegó."""
        if self.posicion == self._destino:
            return True

        paso, self.ruta = rutas.siguiente_paso(
            self.posicion,
            self.ruta,
            self._destino,
            mundo.ancho,
            mundo.alto,
            mundo.ocupadas(self.agent_id),
            mundo.bloqueadas_fijas(self.agent_id),
        )
        if paso is None:
            # Quería moverse y no pudo porque otro agente le tapa el paso.
            mundo.registrar_bloqueo(self.agent_id)
            return False

        self._mover_a(paso)
        return self.posicion == self._destino

    def _mover_a(self, celda: Celda) -> None:
        delta = (celda[0] - self.posicion[0], celda[1] - self.posicion[1])
        if delta not in ORIENTACION:
            raise ValueError(f"{self.agent_id}: movimiento no válido de {self.posicion} a {celda}")
        self.orientacion = ORIENTACION[delta]
        self.posicion = celda

    def _tasa_descarga(self, mundo: Mundo) -> int:
        if self.tasa_descarga is not None:
            return self.tasa_descarga
        config = getattr(mundo, "config", None)
        if config is None:
            raise RuntimeError(
                "El carro necesita tasa_descarga: pásala a Carro(...) o expón mundo.config."
            )
        return config.tasa_descarga

    # ------------------------------------------------------------ registro

    def registro(self, tick: int) -> dict:
        """Snapshot del tick para el trace 2.1: exactamente estas 6 claves (sin intencion ni objetivo)."""
        if self.posicion is None:
            raise RuntimeError("El carro debe registrarse en el mundo antes de generar su registro.")
        return {
            "tick": tick,
            "agent_id": self.agent_id,
            "tipo": CARRO,
            "pose": {"x": self.posicion[0], "y": self.posicion[1], "orientacion": self.orientacion},
            "estado": self.estado.value,
            "carga": {"actual": self.carga, "capacidad": self.capacidad},
        }
