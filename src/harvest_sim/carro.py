"""Carro recolector: agente con estado; en la segunda entrega, contratista de la subasta.  [Oswaldo]

Especificación primera entrega: §5.2 (tabla de estados y transiciones), §4.2 (conflictos de
celda), §4.3 (duraciones) y §5.3 (reposo en EN_BASE).
Especificación segunda entrega: §5 (reservas espacio-tiempo), §6 (acompañar, fila de
servicios, atender_desde_bodega, encadenar_servicios), §7 (Contract Net: el carro es el
contratista), §9 (combustible y reserva) y §10 (restricciones registradas).

Dos modos, según `mundo.config.politica["asignacion"]`:
  - "directa" (línea base): exactamente la máquina de estados de v0.1. Solo lee su buzón en
    EN_BASE y atiende LLENA. Con un solo carro se mueve con rutas.siguiente_paso, como antes.
  - "subasta": lee su buzón en cada tick, oferta por cada SOLICITUD_SERVICIO, guarda los
    servicios ganados en una fila FIFO y acompaña a la cosechadora de cada uno.
Con subasta o con más de un carro, el movimiento usa reservas en el tiempo (rutas.bfs_tiempo).

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
from .datos.formato import CARRO, R13_CULTIVO_EN_PIE
from .mensajes import Mensaje, TipoMensaje

if TYPE_CHECKING:
    from .mensajes import Buzon
    from .mundo import Mundo

Celda = tuple[int, int]

registrador = logging.getLogger("harvest_sim.carro")

# Desplazamiento (dx, dy) del último movimiento -> orientación. y crece hacia abajo: N es y - 1.
ORIENTACION: dict[Celda, str] = {(0, -1): "N", (1, 0): "E", (0, 1): "S", (-1, 0): "O"}

# Tipos de mensaje (README del equipo §3.3). Se comparan por su texto para no depender de
# que el enum del buzón ya los tenga (lo agrega Emilio en mensajes.py).
LLENA = "LLENA"
TRANSFERENCIA_TERMINADA = "TRANSFERENCIA_TERMINADA"
SOLICITUD_SERVICIO = "SOLICITUD_SERVICIO"
PROPUESTA = "PROPUESTA"
RECHAZO = "RECHAZO"
ACEPTACION = "ACEPTACION"
RECHAZO_PROPUESTA = "RECHAZO_PROPUESTA"

# Estados de la cosechadora que el carro percibe con mundo.estado_de.
ESPERANDO_CARRO = ("LLENA_ESPERANDO", "TRANSFIRIENDO")
# Estados en que un agente no se mueve por su cuenta (su celda sigue ocupada).
QUIETOS = frozenset({"EN_BASE", "ESPERANDO_TRANSFERENCIA", "LLENA_ESPERANDO", "TRANSFIRIENDO", "FIN"})
# Estados de viaje del carro: el único caso en que se le puede pedir que se haga a un lado.
VIAJANDO = frozenset({"YENDO_A_COSECHADORA", "YENDO_A_BODEGA", "REGRESANDO_A_BASE"})

# Valores por defecto de la especificación §2 (= línea base).
POLITICA_POR_DEFECTO = {
    "asignacion": "directa",
    "umbral_aviso": 1.0,
    "atender_desde_bodega": False,
    "encadenar_servicios": False,
    "espera_propuestas": 2,
    "reintento_subasta": 3,
}
RESERVA_POR_DEFECTO = 0.15

COMBUSTIBLE_RESERVA = "combustible_reserva"


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


def _tipo(mensaje: Mensaje) -> str:
    """El tipo del mensaje como texto (sirve con el enum del buzón o con un texto)."""
    return getattr(mensaje.tipo, "value", mensaje.tipo)


def _tipo_mensaje(texto: str):
    """El miembro del enum si el buzón ya lo tiene; si no, el texto (solo pasa en pruebas)."""
    try:
        return TipoMensaje(texto)
    except ValueError:
        return texto


class Carro:
    """Máquina de estados del §5.2 (primera entrega) y contratista del §7 (segunda).

    Atributos públicos: agent_id, capacidad, estado, carga, posicion (la asigna
    Mundo.registrar), orientacion y la memoria del agente: objetivo (celda donde se
    estaciona junto a la cosechadora), ruta (celdas que faltan, modo v0.1) y cantidad_recibida
    (la `cantidad` del último TRANSFERENCIA_TERMINADA).
    Segunda entrega: servicios (fila FIFO de servicios ganados; cada uno es un dict con
    servicio, cosechadora, x, y, carga y capacidad), combustible y tanque (los pone el mundo
    al registrarlo; None mientras tanto).

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
        self.combustible: float | None = None
        self.tanque: float | None = None

        # Memoria (§5.2).
        self.objetivo: Celda | None = None
        self.ruta: list[Celda] = []
        self.cantidad_recibida: int | None = None
        self._destino: Celda | None = None
        self._ticks_restantes = 0
        # LLENA que se sacaron de la fila sin poder atenderlos todavía. Nunca se descartan:
        # se atienden primero al volver a EN_BASE (regla del carro ocupado).
        self._llenas_guardadas: deque[Mensaje] = deque()

        # Contratista (§7).
        self.servicios: deque[dict] = deque()
        self._solicitudes: dict[str, dict] = {}  # payload de cada llamada a la que se ofertó
        # Rutas en el tiempo (§5): lo que queda de la ruta después del paso de este tick.
        self._plan_restante: list[rutas.PasoEnTiempo] = []
        self._plan: tuple[Celda | None, list[rutas.PasoEnTiempo]] = (None, [])  # (destino, ruta)
        self._desalojo: Celda | None = None  # celda de salida que reclama si quedó encerrado
        self._tick_actual = 0
        # Restricciones ya registradas en este tramo, para no repetirlas cada tick (§10).
        self._tramo: tuple | None = None
        self._restricciones_del_tramo: set[str] = set()
        self._esperando_recarga = False

    # ------------------------------------------------------------------ paso

    def paso(self, tick: int, mundo: Mundo, buzon: Buzon) -> None:
        """Un tick: en modo directa, la tabla del §5.2; en modo subasta, el contratista del §7."""
        if self.posicion is None:
            raise RuntimeError("El carro debe registrarse en el mundo antes de avanzar.")

        self._plan_restante = []
        self._tick_actual = tick
        inicio = self.posicion
        politica = self._politica(mundo)
        if politica["asignacion"] == "subasta":
            self._paso_subasta(tick, mundo, buzon, politica)
        else:
            self._paso_directa(tick, mundo, buzon)

        if self._con_reservas(mundo):
            if self.posicion == inicio:
                self._ceder_paso(tick, mundo)
            self._reservar(tick, mundo)

    def _paso_directa(self, tick: int, mundo: Mundo, buzon: Buzon) -> None:
        """Línea base (v0.1): solo lee su buzón en EN_BASE y atiende LLENA."""
        if self.estado == EstadoCarro.EN_BASE:
            self._atender_llena(mundo, buzon)

        elif self.estado == EstadoCarro.YENDO_A_COSECHADORA:
            if self._avanzar(tick, mundo):
                self.estado = EstadoCarro.ESPERANDO_TRANSFERENCIA

        elif self.estado == EstadoCarro.ESPERANDO_TRANSFERENCIA:
            self._esperar_transferencia(mundo, buzon)

        elif self.estado == EstadoCarro.YENDO_A_BODEGA:
            if self._avanzar(tick, mundo):
                self._empezar_descarga(mundo)

        elif self.estado == EstadoCarro.DESCARGANDO:
            if self._descargar(mundo):
                self._ir_a(mundo.base_de(self.agent_id), EstadoCarro.REGRESANDO_A_BASE, mundo)

        elif self.estado == EstadoCarro.REGRESANDO_A_BASE:
            if self._avanzar(tick, mundo):
                self._llegar_a_base()

    def _paso_subasta(self, tick: int, mundo: Mundo, buzon: Buzon, politica: dict) -> None:
        """Contratista: lee todo su buzón (en cualquier estado) y luego actúa según su estado."""
        if self._leer_buzon_subasta(tick, mundo, buzon, politica):
            return  # acaba de terminar una transferencia: ese tick no se mueve

        if self.estado == EstadoCarro.EN_BASE:
            if self.servicios and self._listo_para_salir(mundo):
                self.estado = EstadoCarro.YENDO_A_COSECHADORA

        elif self.estado in (EstadoCarro.YENDO_A_COSECHADORA, EstadoCarro.ESPERANDO_TRANSFERENCIA):
            self._acompanar(tick, mundo)

        elif self.estado == EstadoCarro.YENDO_A_BODEGA:
            if self._avanzar(tick, mundo):
                self._empezar_descarga(mundo)

        elif self.estado == EstadoCarro.DESCARGANDO:
            if self._descargar(mundo):
                self._despues_de_descargar(mundo, politica)

        elif self.estado == EstadoCarro.REGRESANDO_A_BASE:
            if self._avanzar(tick, mundo):
                self._llegar_a_base()

    # ------------------------------------------------------- modo directa

    def _atender_llena(self, mundo: Mundo, buzon: Buzon) -> None:
        """EN_BASE: toma el LLENA más antiguo (FIFO), elige la celda objetivo y calcula la ruta."""
        if self._esperando_recarga and not self._tanque_lleno():
            return  # recargando en la base; el LLENA sigue guardado
        mensaje = self._siguiente_llena(buzon)
        if mensaje is None:
            return

        cosechadora = (mensaje.payload["x"], mensaje.payload["y"])
        if not self._listo_para_salir(mundo, cosechadora, mensaje.payload.get("carga", self.capacidad)):
            self._llenas_guardadas.appendleft(mensaje)
            return

        objetivo = rutas.elegir_celda_objetivo(
            self.posicion,
            cosechadora,
            mundo.ancho,
            mundo.alto,
            bloqueadas=self._ocupadas_para_objetivo(mundo) | {mundo.bodega} | self._obstaculos(mundo)
            | self._bloqueadas(mundo),
            evitar=self._siguiente_del_camino(mundo, mensaje.emisor, cosechadora),
        )
        if objetivo is None:
            # Ninguna vecina alcanzable por ahora: el mensaje no se descarta, se reintenta.
            self._llenas_guardadas.appendleft(mensaje)
            return

        self.objetivo = objetivo
        self._ir_a(objetivo, EstadoCarro.YENDO_A_COSECHADORA, mundo)

    def _esperar_transferencia(self, mundo: Mundo, buzon: Buzon) -> None:
        """ESPERANDO_TRANSFERENCIA: espera inmóvil el TRANSFERENCIA_TERMINADA (no es un bloqueo)."""
        mensaje = buzon.leer(self.agent_id)
        while mensaje is not None and _tipo(mensaje) != TRANSFERENCIA_TERMINADA:
            if _tipo(mensaje) == LLENA:
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

        self._ir_a(mundo.bodega, EstadoCarro.YENDO_A_BODEGA, mundo)

    def _siguiente_llena(self, buzon: Buzon) -> Mensaje | None:
        """Primero los LLENA guardados; si no hay, el siguiente de la fila (uno por tick)."""
        if self._llenas_guardadas:
            return self._llenas_guardadas.popleft()

        mensaje = buzon.leer(self.agent_id)
        if mensaje is not None and _tipo(mensaje) != LLENA:
            registrador.warning("%s: mensaje %s inesperado en EN_BASE", self.agent_id, _tipo(mensaje))
            return None
        return mensaje

    # ------------------------------------------------------ modo subasta

    def _leer_buzon_subasta(self, tick: int, mundo: Mundo, buzon: Buzon, politica: dict) -> bool:
        """Procesa todos los mensajes de la fila. Devuelve True si terminó una transferencia."""
        termino_transferencia = False
        mensaje = buzon.leer(self.agent_id)
        while mensaje is not None:
            tipo = _tipo(mensaje)
            servicio = mensaje.payload.get("servicio")

            if tipo == SOLICITUD_SERVICIO:
                self._responder_solicitud(tick, mundo, buzon, politica, mensaje)
            elif tipo == ACEPTACION:
                solicitud = self._solicitudes.pop(servicio, None)
                if solicitud is None:
                    registrador.warning("%s: ACEPTACION de %s sin propuesta", self.agent_id, servicio)
                else:
                    self.servicios.append(solicitud)
            elif tipo == RECHAZO_PROPUESTA:
                self._solicitudes.pop(servicio, None)
            elif tipo == TRANSFERENCIA_TERMINADA:
                self._terminar_servicio(mundo, politica, mensaje)
                termino_transferencia = True
            else:
                registrador.warning("%s: mensaje %s inesperado en modo subasta", self.agent_id, tipo)
            mensaje = buzon.leer(self.agent_id)
        return termino_transferencia

    def _responder_solicitud(
        self, tick: int, mundo: Mundo, buzon: Buzon, politica: dict, mensaje: Mensaje
    ) -> None:
        """SOLICITUD_SERVICIO (cfp) -> PROPUESTA (propose) o RECHAZO (refuse) (§7)."""
        payload = mensaje.payload
        servicio = payload["servicio"]
        solicitud = {
            "servicio": servicio,
            "cosechadora": mensaje.emisor,
            "x": payload["x"],
            "y": payload["y"],
            "carga": payload["carga"],
            "capacidad": payload.get("capacidad", payload["carga"]),
        }

        if solicitud["carga"] > self.capacidad:
            self._enviar(buzon, RECHAZO, mensaje.emisor, tick, {"servicio": servicio, "motivo": "sin_capacidad"})
            return

        estimacion = self._estimar_fila(mundo, politica, solicitud)
        if estimacion is None:
            self._enviar(buzon, RECHAZO, mensaje.emisor, tick, {"servicio": servicio, "motivo": "sin_ruta"})
            return
        costo, celdas, ticks_encendido = estimacion

        # Con el tanque lleno no se rechaza por combustible (igual que _listo_para_salir): si el viaje no
        # alcanza ni con el tanque lleno, rechazar siempre dejaría a la cosechadora llamando para siempre.
        if not self._alcanza(mundo, celdas, ticks_encendido) and not self._tanque_lleno():
            self._enviar(buzon, RECHAZO, mensaje.emisor, tick, {"servicio": servicio, "motivo": "combustible"})
            mundo.registrar_restriccion(
                self.agent_id, COMBUSTIBLE_RESERVA,
                f"rechaza {servicio}: no le alcanza el combustible sin bajar de la reserva",
            )
            return

        self._solicitudes[servicio] = solicitud
        self._enviar(buzon, PROPUESTA, mensaje.emisor, tick, {"servicio": servicio, "costo": costo})

    def _terminar_servicio(self, mundo: Mundo, politica: dict, mensaje: Mensaje) -> None:
        """TRANSFERENCIA_TERMINADA (inform): quita el servicio atendido y decide a dónde va."""
        servicio = mensaje.payload.get("servicio")
        for indice, pendiente in enumerate(self.servicios):
            if pendiente["servicio"] == servicio or (servicio is None and pendiente["cosechadora"] == mensaje.emisor):
                del self.servicios[indice]
                break
        else:
            registrador.warning("%s: TRANSFERENCIA_TERMINADA de %s que no tenía", self.agent_id, servicio)
        self.cantidad_recibida = mensaje.payload.get("cantidad")

        if politica["encadenar_servicios"] and self.servicios and self._le_cabe(self.servicios[0]):
            self.estado = EstadoCarro.YENDO_A_COSECHADORA
        else:
            self._ir_a(mundo.bodega, EstadoCarro.YENDO_A_BODEGA, mundo)

    def _acompanar(self, tick: int, mundo: Mundo) -> None:
        """Va hacia la posición ACTUAL de la cosechadora de su primer servicio (§6).

        Recalcula la celda objetivo en cada tick (una vecina libre que no sea la siguiente del
        camino de la cosechadora). Al quedar en ella pasa a ESPERANDO_TRANSFERENCIA; si la
        cosechadora se aleja, vuelve a YENDO_A_COSECHADORA. Mientras ella espera o transfiere y
        el carro ya es vecino, no se mueve (la transferencia exige que sigan vecinos).
        """
        servicio = self.servicios[0]
        cosechadora = servicio["cosechadora"]
        pos_cosechadora = mundo.posicion(cosechadora)

        if (self.posicion in mundo.vecinos(pos_cosechadora)
                and mundo.estado_de(cosechadora) in ESPERANDO_CARRO):
            self.objetivo = self.posicion
            self.estado = EstadoCarro.ESPERANDO_TRANSFERENCIA
            return

        # Mientras la cosechadora se traslada (rodea un obstáculo o cambia de lote), el carro no se estaciona
        # en las celdas que ella necesita (mundo.paso_de): en un pasillo de una celda la dejaba encerrada para
        # siempre (ella no se llena y el carro solo se mueve después de la transferencia).
        paso = self._paso_de(mundo, cosechadora)
        objetivo = rutas.elegir_celda_objetivo(
            self.posicion,
            pos_cosechadora,
            mundo.ancho,
            mundo.alto,
            bloqueadas=self._ocupadas_para_objetivo(mundo) | {mundo.bodega} | self._obstaculos(mundo)
            | self._bloqueadas(mundo) | paso,
            evitar=self._siguiente_del_camino(mundo, cosechadora, pos_cosechadora),
        )
        if paso and getattr(mundo, "hileras", False):
            # con hileras, la cosechadora se traslada por pasillos de rastrojo de una celda (cabeceras): el carro
            # no la persigue mientras se mueve; solo libra su paso y espera a que vuelva a cosechar
            objetivo = None
        if objetivo is None and paso:
            # no hay dónde esperar junto a ella sin estorbar: se hace a un lado si estorba, o espera donde está
            self.estado = EstadoCarro.YENDO_A_COSECHADORA
            if self.posicion in paso:
                prohibidas = (self._ocupadas_para_objetivo(mundo) | {mundo.bodega} | self._obstaculos(mundo)
                              | self._bloqueadas(mundo))
                libres = sorted(v for v in mundo.vecinos(self.posicion) if v not in paso and v not in prohibidas)
                if not libres:
                    # pasillo de una celda (rastrojo entre cultivo en pie): no hay lado libre, así que avanza por
                    # el pasillo hasta la primera celda fuera del paso de la cosechadora
                    libres = self._fuera_del_paso(mundo, paso, prohibidas)
                if libres:
                    self.objetivo = self._destino = libres[0]
                    self._avanzar(tick, mundo)
                    return
            if getattr(mundo, "hileras", False):
                # espera quieto: suelta el plan viejo para no reservar una ruta que no va a tomar (esas reservas
                # fantasma hacían que la cosechadora pospusiera su traslado para siempre)
                self._plan = (None, [])
                self.objetivo = self._destino = self.posicion
            return
        if objetivo is None:
            # Ninguna vecina libre por ahora (otros agentes alrededor): espera cerca.
            self.estado = EstadoCarro.YENDO_A_COSECHADORA
            return

        self.objetivo = objetivo
        if self.posicion == objetivo:
            self.estado = EstadoCarro.ESPERANDO_TRANSFERENCIA
            return

        self.estado = EstadoCarro.YENDO_A_COSECHADORA
        self._destino = objetivo
        if self._avanzar(tick, mundo):
            self.estado = EstadoCarro.ESPERANDO_TRANSFERENCIA

    def _despues_de_descargar(self, mundo: Mundo, politica: dict) -> None:
        """atender_desde_bodega: con servicios en fila va directo; si no, regresa a su base."""
        if politica["atender_desde_bodega"] and self.servicios and self._listo_para_salir(mundo):
            self.estado = EstadoCarro.YENDO_A_COSECHADORA
        else:
            self._ir_a(mundo.base_de(self.agent_id), EstadoCarro.REGRESANDO_A_BASE, mundo)

    def _le_cabe(self, servicio: dict) -> bool:
        """¿Cabe lo que traerá esa cosechadora? Se usa su capacidad y no la carga anunciada:
        con despacho anticipado ella sigue cosechando hasta llenarse."""
        return self.capacidad - self.carga >= servicio["capacidad"]

    def _estimar_fila(
        self, mundo: Mundo, politica: dict, nueva: dict
    ) -> tuple[int, int, int] | None:
        """(costo, celdas, ticks_encendido) de atender toda su fila y luego `nueva` (§7).

        costo = ticks hasta quedar junto a la cosechadora de `nueva` (rutas.estimar_costo con
        ticks_ocupado = lo que le falta de su fila). celdas y ticks_encendido cubren además
        llevar todo a la bodega y volver a su base: es lo que pide la reserva de combustible.
        Las duraciones usan la fórmula determinista ceil(cantidad / tasa): llamar a
        mundo.duracion para estimar sortearía el extra aleatorio y cambiaría la secuencia.
        """
        config = mundo.config
        # con mapa: lo que el carro puede pisar ahora (sin fuera de campo ni cultivo en pie, R12 y R13)
        obstaculos = self._obstaculos(mundo) | self._bloqueadas(mundo)
        base, bodega = mundo.base_de(self.agent_id), mundo.bodega
        cache: dict[Celda, dict[Celda, int]] = {}

        def distancia(a: Celda, b: Celda) -> int:
            if a not in cache:
                cache[a] = rutas.distancias(a, mundo.ancho, mundo.alto, obstaculos)
            return cache[a].get(b, abs(a[0] - b[0]) + abs(a[1] - b[1]))

        def junto_a(a: Celda, cosechadora: Celda) -> tuple[int, Celda]:
            pasos = rutas.estimar_costo(a, 0, cosechadora, mundo.ancho, mundo.alto, obstaculos)
            if pasos is None:
                return distancia(a, cosechadora), cosechadora
            return pasos, cosechadora

        ticks = celdas = encendido = 0
        pos, carga = self.posicion, self.carga

        def a_la_bodega() -> None:
            nonlocal ticks, celdas, encendido, pos, carga
            pasos = distancia(pos, bodega)
            descarga = duracion_descarga(carga, self._tasa_descarga(mundo))
            ticks += pasos + descarga
            celdas += pasos
            encendido += descarga
            pos, carga = bodega, 0
            if not politica["atender_desde_bodega"]:
                ticks += distancia(bodega, base)
                celdas += distancia(bodega, base)
                pos = base

        # Lo que le falta de lo que está haciendo ahora.
        if self.estado == EstadoCarro.YENDO_A_BODEGA:
            a_la_bodega()
        elif self.estado == EstadoCarro.DESCARGANDO:
            ticks += self._ticks_restantes + 1
            encendido += self._ticks_restantes + 1
            pos, carga = bodega, 0
            if not politica["atender_desde_bodega"]:
                ticks += distancia(bodega, base)
                celdas += distancia(bodega, base)
                pos = base
        elif self.estado == EstadoCarro.REGRESANDO_A_BASE:
            ticks += distancia(pos, base)
            celdas += distancia(pos, base)
            pos = base

        # Su fila de servicios, en orden, y al final la nueva.
        fila = [*self.servicios, nueva]
        for indice, servicio in enumerate(fila):
            if indice > 0:
                encadena = (politica["encadenar_servicios"]
                            and self.capacidad - carga >= servicio["capacidad"])
                if not encadena:
                    a_la_bodega()
            cosechadora = (servicio["x"], servicio["y"])
            if servicio is nueva:
                costo = rutas.estimar_costo(pos, ticks, cosechadora, mundo.ancho, mundo.alto, obstaculos)
                if costo is None:
                    return None
            pasos, pos = junto_a(pos, cosechadora)
            transferencia = duracion_descarga(servicio["capacidad"], config.tasa_transferencia)
            ticks += pasos + transferencia
            celdas += pasos
            encendido += transferencia
            carga = min(self.capacidad, carga + servicio["capacidad"])

        # Para el combustible: llevar la última carga a la bodega y volver a la base.
        pasos = distancia(pos, bodega)
        celdas += pasos + distancia(bodega, base)
        encendido += duracion_descarga(carga, self._tasa_descarga(mundo))
        return costo, celdas, encendido

    # ---------------------------------------------------------- combustible

    def _alcanza(self, mundo: Mundo, celdas: int, ticks_encendido: int) -> bool:
        """¿Puede gastar eso sin bajar de reserva × tanque (§9)? Sin tanque, siempre."""
        if self.tanque is None or self.combustible is None or not hasattr(mundo, "combustible_para"):
            return True
        litros = mundo.combustible_para(self.agent_id, celdas, ticks_encendido)
        return self.combustible - litros >= self._reserva(mundo) * self.tanque

    def _listo_para_salir(self, mundo: Mundo, cosechadora: Celda | None = None, carga: int | None = None) -> bool:
        """Antes de salir a un servicio: si no le alcanza el combustible para ir, atender y volver,
        se queda (o regresa) a recargar en su base. Con el tanque lleno sale de todos modos."""
        if self.tanque is None or self.combustible is None or not hasattr(mundo, "combustible_para"):
            return True
        if cosechadora is None:
            servicio = self.servicios[0]
            cosechadora, carga = (servicio["x"], servicio["y"]), servicio["capacidad"]
        base, bodega = mundo.base_de(self.agent_id), mundo.bodega
        dist = rutas.distancias(cosechadora, mundo.ancho, mundo.alto, self._obstaculos(mundo) | self._bloqueadas(mundo))

        def d(a: Celda, b: Celda) -> int:
            return abs(a[0] - b[0]) + abs(a[1] - b[1])

        celdas = (dist.get(self.posicion, d(self.posicion, cosechadora))
                  + dist.get(bodega, d(cosechadora, bodega)) + d(bodega, base))
        encendido = (duracion_descarga(carga, mundo.config.tasa_transferencia)
                     + duracion_descarga(self.carga + carga, self._tasa_descarga(mundo)))
        if self._alcanza(mundo, celdas, encendido) or self._tanque_lleno():
            self._esperando_recarga = False
            return True

        if not self._esperando_recarga:
            mundo.registrar_restriccion(
                self.agent_id, COMBUSTIBLE_RESERVA,
                f"va a recargar antes de salir: {self.combustible:.2f} L no alcanzan",
            )
            self._esperando_recarga = True
        # En la base espera la recarga (la hace el mundo); desde la bodega,
        # _despues_de_descargar lo manda primero a su base.
        return False

    def _tanque_lleno(self) -> bool:
        return self.tanque is None or self.combustible is None or self.combustible >= self.tanque

    # --------------------------------------------------- movimiento y estados

    def _ir_a(self, destino: Celda, estado: EstadoCarro, mundo: Mundo) -> None:
        self._fijar_destino(destino, mundo)
        self.estado = estado

    def _llegar_a_base(self) -> None:
        self._destino = None
        self.objetivo = None
        self.estado = EstadoCarro.EN_BASE

    def _empezar_descarga(self, mundo: Mundo) -> None:
        """Llegó a la bodega: calcula la duración al entrar al estado (§4.3)."""
        duracion = self._duracion_real(self.carga, self._tasa_descarga(mundo), mundo)
        # El tick de entrada ya cuenta como el primero de los `duracion` snapshots.
        self._ticks_restantes = duracion - 1
        self.estado = EstadoCarro.DESCARGANDO

    def _descargar(self, mundo: Mundo) -> bool:
        """DESCARGANDO: decrementa; al agotarse, el mundo deposita (carga = 0, evento DEPOSITO).
        Devuelve True el tick en que depositó."""
        if self._ticks_restantes > 0:
            self._ticks_restantes -= 1
            return False
        mundo.depositar(self.agent_id)
        return True

    @staticmethod
    def _duracion_real(cantidad: int, tasa: int, mundo: Mundo) -> int:
        """mundo.duracion (con el extra aleatorio, §8) si existe; si no, la fórmula de v0.1."""
        duracion = getattr(mundo, "duracion", None)
        return duracion(cantidad, tasa) if duracion is not None else duracion_descarga(cantidad, tasa)

    def _fijar_destino(self, destino: Celda, mundo: Mundo) -> None:
        """Calcula la ruta BFS hacia `destino` tratando a los otros agentes como bloqueados."""
        self._destino = destino
        bloqueadas = mundo.ocupadas(self.agent_id) | self._bloqueadas(mundo)
        # Si ahora no hay ruta (destino ocupado), se queda vacía y siguiente_paso la recalcula.
        self.ruta = mundo.ruta_bfs(self.posicion, destino, bloqueadas) or []

    def _avanzar(self, tick: int, mundo: Mundo) -> bool:
        """Un paso hacia el destino. Devuelve True si llegó."""
        if self.posicion == self._destino:
            return True
        if self._con_reservas(mundo):
            return self._avanzar_reservando(tick, mundo)

        # Un solo carro en modo directa: la regla de la primera entrega (§4.2), sin cambios.
        paso, self.ruta = rutas.siguiente_paso(
            self.posicion,
            self.ruta,
            self._destino,
            mundo.ancho,
            mundo.alto,
            mundo.ocupadas(self.agent_id),
            self._bloqueadas(mundo),
        )
        if paso is None:
            # Quería moverse y no pudo porque otro agente le tapa el paso.
            mundo.registrar_bloqueo(self.agent_id)
            return False

        self._mover_a(paso)
        return self.posicion == self._destino

    def _avanzar_reservando(self, tick: int, mundo: Mundo) -> bool:
        """Un paso con rutas en el tiempo (§5). Devuelve True si llegó.

        Compromiso con el plan: si lo que reservó el tick anterior sigue siendo válido con las
        reservas actuales de los demás, lo cumple; solo lo cambia por una ruta que llegue
        estrictamente antes. Replanear sin compromiso deja que un agente posponga para siempre
        un movimiento que otro está esperando (el BFS prefiere esperar primero, y cada tick
        vuelve a «esperar un tick más»). Una espera planeada no es bloqueo; BLOQUEO solo si no
        hay ninguna ruta en el tiempo aunque sin otros agentes sí la habría.
        """
        bloqueadas = self._bloqueadas(mundo) | self._obstaculos(mundo)
        reservas = self._reservas_de_otros(tick, mundo)
        ruta = self._planear(tick - 1, mundo, bloqueadas, reservas)
        vigente = self._plan_vigente(tick, mundo, bloqueadas, reservas)
        if vigente is not None and (ruta is None or ruta[-1][1] >= vigente[-1][1]):
            ruta = vigente
        espacial = rutas.bfs(self.posicion, self._destino, mundo.ancho, mundo.alto, bloqueadas)
        if ruta is None:
            if espacial is not None:
                mundo.registrar_bloqueo(self.agent_id)
                self._pedir_paso(mundo, bloqueadas, reservas)
            return False
        if (espacial is not None and len(ruta) > len(espacial)
                and ruta[-1][1] > tick + rutas.HORIZONTE):
            # Solo llega después del horizonte: alguien le tapa el paso todo ese tiempo. Si es
            # un carro en viaje que está justo en su camino, le pide que se haga a un lado.
            self._pedir_paso(mundo, bloqueadas, reservas)

        self._registrar_desvio(tick, mundo, bloqueadas, reservas)
        celda, _ = ruta[0]
        self._guardar_plan(ruta[1:])
        if getattr(mundo, "hileras", False):
            self.orientacion, self._giro = rutas.progreso_de_giro(
                self.posicion, self.orientacion, ruta, *mundo.costos_de_giro(carro=True), getattr(self, "_giro", None))
        if celda != self.posicion:
            self._mover_a(celda)
        return self.posicion == self._destino

    def _guardar_plan(self, plan: list[rutas.PasoEnTiempo]) -> None:
        """Lo que queda de la ruta: se reserva en este tick y se intenta cumplir en el siguiente."""
        self._plan_restante = plan
        self._plan = (self._destino, plan)

    def _plan_vigente(
        self, tick: int, mundo: Mundo, bloqueadas: set[Celda], reservas: rutas.Reservas
    ) -> list[rutas.PasoEnTiempo] | None:
        """El plan del tick anterior si sigue siendo válido: mismo destino, empieza en este tick
        y, dentro del horizonte, no pisa reservas de otros, no se intercambia y puede quedarse en
        el destino. None si ya no sirve."""
        destino, plan = self._plan
        if destino != self._destino or not plan or plan[0][1] != tick or plan[-1][0] != destino:
            return None
        limite = tick + rutas.HORIZONTE
        anterior = (self.posicion, tick - 1)
        for celda, t in plan:
            c0, t0 = anterior
            if celda in bloqueadas or (celda != c0 and celda not in mundo.vecinos(c0)):
                return None
            if t <= limite:
                if (celda, t) in reservas:
                    return None
                otro = reservas.get((celda, t0))
                if celda != c0 and otro is not None and reservas.get((c0, t)) == otro:
                    return None
            anterior = (celda, t)
        celda_final, t_final = plan[-1]
        permanencia = self._permanencia(mundo)
        hasta = limite if permanencia is None or t_final > limite else t_final + permanencia
        if any((celda_final, t) in reservas for t in range(t_final + 1, hasta + 1)):
            return None
        return plan

    def _planear(
        self, desde_tick: int, mundo: Mundo, bloqueadas: set[Celda], reservas: rutas.Reservas
    ) -> list[rutas.PasoEnTiempo] | None:
        """bfs_tiempo desde (posicion, desde_tick) hasta el destino.

        Horizonte + 1 para revisar hasta desde_tick + 1 + HORIZONTE, lo mismo que se reserva.
        """
        planear = getattr(mundo, "planear_con_rumbo", None)
        if callable(planear):  # con hileras, A* con rumbo; sin hileras, el BFS de siempre
            return planear(self.posicion, self.orientacion, self._destino, desde_tick, bloqueadas, reservas,
                           rutas.HORIZONTE + 1, self._permanencia(mundo), carro=True)
        return rutas.bfs_tiempo(
            self.posicion, self._destino, desde_tick, mundo.ancho, mundo.alto,
            bloqueadas, reservas, rutas.HORIZONTE + 1, self._permanencia(mundo),
        )

    def _permanencia(self, mundo: Mundo) -> int | None:
        """Cuánto se queda en el destino: en la bodega, lo que dura la descarga (después se va,
        y otro carro puede planear entrar); en los demás destinos, todo el horizonte."""
        if self.estado == EstadoCarro.YENDO_A_BODEGA and self._destino == mundo.bodega:
            return duracion_descarga(self.carga, self._tasa_descarga(mundo))
        return None

    def _reservas_de_otros(self, tick: int, mundo: Mundo) -> rutas.Reservas:
        """Reservas de los demás, completadas con lo que el carro percibe:

        - las celdas que ocupan ahora (regla R3 conservadora: el primer paso nunca entra a una
          celda ocupada, aunque ese agente no haya reservado);
        - un agente quieto (en su base, esperando o transfiriendo) se queda en su última celda
          reservada todo el horizonte. Sin esto, quien actúa antes en el tick puede planear pasar
          por la celda de un carro estacionado justo en el borde del horizonte y, tick tras tick,
          ir recortando su reserva hasta quedar esperando a que «se quite» alguien que nunca se
          va. A los que se mueven no se les extiende: cuentan solo sus reservas.
        """
        reservas = dict(mundo.reservas(excepto=self.agent_id))
        for celda in sorted(mundo.ocupadas(self.agent_id)):
            reservas.setdefault((celda, tick), "ocupada")

        limite = tick + rutas.HORIZONTE + 1
        por_agente: dict[str, dict[int, Celda]] = {}
        for (celda, t), agente in reservas.items():
            por_agente.setdefault(agente, {})[t] = celda
        for agente, (posicion, estado) in self._otros_agentes(mundo).items():
            if estado not in QUIETOS:
                continue
            suyas = por_agente.get(agente, {})
            celda = posicion
            for t in range(tick, limite + 1):
                celda = suyas.get(t, celda)
                reservas.setdefault((celda, t), agente)
        return reservas

    def _otros_agentes(self, mundo: Mundo) -> dict[str, tuple[Celda, str]]:
        """{agent_id: (posicion, estado)} de los demás agentes (ids del §3 de la especificación)."""
        config = getattr(mundo, "config", None)
        ids = [f"carro_{i}" for i in range(1, getattr(config, "num_carros", 1) + 1)]
        ids += [f"cosechadora_{j}" for j in range(1, getattr(config, "num_cosechadoras", 1) + 1)]
        otros = {}
        for agente in ids:
            if agente == self.agent_id:
                continue
            try:
                otros[agente] = (mundo.posicion(agente), mundo.estado_de(agente))
            except KeyError:
                continue  # ese agente no existe en este mundo
        return otros

    def _pedir_paso(self, mundo: Mundo, bloqueadas: set[Celda], reservas: rutas.Reservas) -> None:
        """Le tapan el paso (sin ruta, o solo después del horizonte): reclama la siguiente celda
        del camino más corto si ahí está parado un carro EN VIAJE. A las cosechadoras y a los
        carros quietos o descargando nunca se les pide (su lugar es parte de su trabajo).

        _reservar reserva esa celda desde este tick, así que el carro que está ahí no puede
        quedarse (bfs_tiempo no espera en una celda reservada por otro, y _ceder_paso lo hace a un
        lado si no está planeando). Así se deshacen los «abrazos» de dos carros que se esperan
        mutuamente (la bodega con una sola salida, la entrada de un pasillo). Si los dos se
        reclaman al mismo tiempo, gana el de id menor.
        """
        otros = self._otros_agentes(mundo)
        salida = rutas.bfs(self.posicion, self._destino, mundo.ancho, mundo.alto,
                           bloqueadas | self._celdas_fijas(mundo))
        if not salida:
            return
        en_viaje = {pos: a for a, (pos, estado) in otros.items() if a.startswith("carro_") and estado in VIAJANDO}
        # El primer carro en viaje parado en el camino, aunque no esté pegado.
        celda = next((c for c in salida if c in en_viaje), None)
        if celda is None:
            return  # nadie parado en el camino: espera por reservas, no por alguien que estorba
        estorbo = en_viaje[celda]
        if estorbo < self.agent_id and any(
                reservas.get((c, self._tick_actual)) == estorbo for c in (self.posicion, *salida)):
            return  # el otro ya me pidió paso a mí y tiene prioridad
        self._desalojo = celda

    def _ocupadas_para_objetivo(self, mundo: Mundo) -> set[Celda]:
        """Qué celdas descarta al elegir dónde estacionarse. Con un solo carro en modo directa,
        todas las ocupadas (v0.1). Con rutas en el tiempo, solo las de quienes no se van a mover:
        de los carros en viaje se encarga bfs_tiempo; descartarlos podía dejarlo sin objetivo
        justo cuando el que estorba necesita que él avance."""
        if self._con_reservas(mundo):
            return self._celdas_fijas(mundo)
        return mundo.ocupadas(self.agent_id)

    def _celdas_fijas(self, mundo: Mundo) -> set[Celda]:
        """Celdas de los agentes que no se van a mover para dejar pasar: cosechadoras y carros
        quietos o descargando. Los carros en viaje no cuentan (se mueven, o ceden el paso)."""
        return {pos for agente, (pos, estado) in self._otros_agentes(mundo).items()
                if not agente.startswith("carro_") or estado not in VIAJANDO}

    def _ceder_paso(self, tick: int, mundo: Mundo) -> None:
        """Si otro carro reclamó la celda donde este quedó parado (ver _pedir_paso), se hace a un
        lado: a la primera vecina (N, E, S, O) libre ahora y, de preferencia, también el tick que
        sigue. Solo en viaje: quieto o descargando, su lugar es parte de su trabajo."""
        if self.estado.value not in VIAJANDO:
            return
        de_otros = mundo.reservas(excepto=self.agent_id)
        reclamante = de_otros.get((self.posicion, tick))
        if reclamante is None or not reclamante.startswith("carro_"):
            return
        if self._desalojo is not None and reclamante > self.agent_id:
            return  # yo también pedí paso y tengo prioridad
        ocupadas = mundo.ocupadas(self.agent_id)
        bloqueadas = self._bloqueadas(mundo) | self._obstaculos(mundo)
        libres = [c for c in mundo.vecinos(self.posicion)
                  if c not in ocupadas and c not in bloqueadas and (c, tick) not in de_otros]
        if not libres:
            return
        horizonte = range(tick, tick + rutas.HORIZONTE + 2)
        # Primero una vecina que nadie usa en todo el horizonte (un hueco a un lado del camino),
        # luego una libre también el tick siguiente; en empate, el orden N, E, S, O.
        mejor = min(libres, key=lambda c: (any((c, t) in de_otros for t in horizonte),
                                           (c, tick + 1) in de_otros))
        self._mover_a(mejor)
        self._guardar_plan([])

    def _registrar_desvio(self, tick: int, mundo: Mundo, bloqueadas: set[Celda], reservas: rutas.Reservas) -> None:
        """RESTRICCION (§10) si la ruta rodeó un obstáculo o esquivó a otro agente; una vez por
        regla en cada tramo (un tramo = mismo estado y mismo servicio o destino)."""
        servicio = self.servicios[0]["servicio"] if (
            self.estado == EstadoCarro.YENDO_A_COSECHADORA and self.servicios) else self._destino
        tramo = (self.estado, servicio)
        if tramo != self._tramo:
            self._tramo, self._restricciones_del_tramo = tramo, set()

        reglas = rutas.clasificar_desvio(
            self.posicion, self._destino, tick - 1, mundo.ancho, mundo.alto,
            bloqueadas, self._obstaculos(mundo), reservas, rutas.HORIZONTE + 1,
            self._permanencia(mundo),
        )
        # R13: la ruta se alarga por rodear el cultivo en pie (docs/especificacion_terreno.md §7)
        if getattr(mundo, "respetar_cultivo", False) and self._destino is not None:
            sin_cultivo = rutas.bfs(self.posicion, self._destino, mundo.ancho, mundo.alto,
                                    bloqueadas - mundo.cultivo_en_pie())
            con_cultivo = rutas.bfs(self.posicion, self._destino, mundo.ancho, mundo.alto, bloqueadas)
            if sin_cultivo is not None and con_cultivo is not None and len(con_cultivo) > len(sin_cultivo):
                reglas = list(reglas) + [R13_CULTIVO_EN_PIE]
        for regla in reglas:
            if regla not in self._restricciones_del_tramo:
                self._restricciones_del_tramo.add(regla)
                mundo.registrar_restriccion(
                    self.agent_id, regla, f"desvío de {self.posicion} a {self._destino}"
                )

    def _reservar(self, tick: int, mundo: Mundo) -> None:
        """Reserva lo que queda de su ruta (o su celda, si está quieto) hasta tick + HORIZONTE.

        - Si acaba de pasar de un estado quieto a uno de viaje sin moverse (por ejemplo, terminó
          de descargar), planea ya la ruta desde (posicion, tick) y la reserva.
        - DESCARGANDO reserva la bodega solo hasta el tick en que deposita (ya sabe cuándo se va),
          y al ir a la bodega la reserva solo lo que dura la descarga (_permanencia).
        - Se corta antes de cualquier (celda, t) que ya tenga otro agente.
        """
        viajando = self.estado in (
            EstadoCarro.YENDO_A_COSECHADORA, EstadoCarro.YENDO_A_BODEGA, EstadoCarro.REGRESANDO_A_BASE,
        )
        if (not self._plan_restante and viajando
                and self._destino is not None and self.posicion != self._destino):
            bloqueadas = self._bloqueadas(mundo) | self._obstaculos(mundo)
            reservas = dict(mundo.reservas(excepto=self.agent_id))
            self._guardar_plan(self._planear(tick, mundo, bloqueadas, reservas) or [])

        if self._desalojo is not None:
            # Encerrado: su celda ahora y la de salida desde ya (ver _pedir_paso). Esta reserva sí
            # puede pisar la de quien espera en la salida: es justo lo que lo obliga a moverse.
            salida, self._desalojo = self._desalojo, None
            mundo.reservar(self.agent_id, [(self.posicion, tick)] + [(salida, t) for t in range(tick, tick + 3)])
            return

        # Un tick más de lo que revisa al planear (tick + HORIZONTE): quien actúa antes en el tick
        # siguiente planea hasta ese tick + 1, y no debe encontrar un hueco al final de esta
        # reserva (si no, puede reservar el destino justo cuando este carro todavía lo usa).
        permanencia = self._permanencia(mundo) if self._plan_restante else None
        pasos = rutas.reservas_de_ruta(
            self.posicion, self._plan_restante, tick, rutas.HORIZONTE + 1, permanencia
        )
        if self.estado == EstadoCarro.DESCARGANDO:
            pasos = self._reservas_de_descarga(tick, mundo) or pasos

        de_otros = mundo.reservas(excepto=self.agent_id)
        propias = []
        for paso in pasos:
            if paso in de_otros:
                break
            propias.append(paso)
        if propias:
            mundo.reservar(self.agent_id, propias)

    def _reservas_de_descarga(self, tick: int, mundo: Mundo) -> list[rutas.PasoEnTiempo] | None:
        """DESCARGANDO: la bodega hasta el tick del depósito y, desde ahí, su salida hacia la base.

        Así los demás saben cuándo y por dónde se va, y no planean entrar a la bodega si él no
        tiene por dónde salir (la bodega puede quedar con una sola salida si hay un carro
        estacionado en (1, 0)). Sin salida posible devuelve None: reserva la bodega todo el
        horizonte. La ruta real la vuelve a planear al terminar de descargar.
        """
        deposito = tick + self._ticks_restantes + 1  # ese tick todavía sigue en la bodega
        limite = tick + rutas.HORIZONTE + 1
        estancia = [(self.posicion, t) for t in range(tick, min(deposito, limite) + 1)]
        if deposito >= limite:
            return estancia
        bloqueadas = self._bloqueadas(mundo) | self._obstaculos(mundo)
        salida = rutas.bfs_tiempo(
            self.posicion, mundo.base_de(self.agent_id), deposito, mundo.ancho, mundo.alto,
            bloqueadas, self._reservas_de_otros(tick, mundo), limite - deposito,
        )
        if salida is None:
            return None
        return estancia + [(celda, t) for celda, t in salida if t <= limite]

    def _mover_a(self, celda: Celda) -> None:
        delta = (celda[0] - self.posicion[0], celda[1] - self.posicion[1])
        if delta not in ORIENTACION:
            raise ValueError(f"{self.agent_id}: movimiento no válido de {self.posicion} a {celda}")
        self.orientacion = ORIENTACION[delta]
        self.posicion = celda

    # ---------------------------------------------------------- auxiliares

    @staticmethod
    def _politica(mundo: Mundo) -> dict:
        politica = dict(POLITICA_POR_DEFECTO)
        politica.update(getattr(getattr(mundo, "config", None), "politica", None) or {})
        return politica

    def _con_reservas(self, mundo: Mundo) -> bool:
        """Rutas en el tiempo con subasta o con varios carros; con uno solo en directa, v0.1 (§5.6)."""
        config = getattr(mundo, "config", None)
        return (self._politica(mundo)["asignacion"] == "subasta"
                or getattr(config, "num_carros", 1) > 1)

    def _bloqueadas(self, mundo: Mundo) -> set[Celda]:
        """Lo que el carro no puede pisar ahora: con mapa, las fijas más el cultivo en pie (R12, R13); si el
        mundo no lo sabe (dobles de prueba), las fijas de siempre."""
        para = getattr(mundo, "bloqueadas_para", None)
        return para(self.agent_id) if callable(para) else mundo.bloqueadas_fijas(self.agent_id)

    @staticmethod
    def _obstaculos(mundo: Mundo) -> set[Celda]:
        return {tuple(celda) for celda in getattr(mundo, "obstaculos", ())}

    def _reserva(self, mundo: Mundo) -> float:
        combustible = getattr(getattr(mundo, "config", None), "combustible", None) or {}
        return combustible.get("reserva", RESERVA_POR_DEFECTO)

    def _fuera_del_paso(self, mundo: Mundo, paso: set[Celda], prohibidas: set[Celda]) -> list[Celda]:
        """La celda más cercana (BFS por donde el carro puede andar) que no está en `paso`; [] si no hay."""
        vistos = {self.posicion}
        frente = [self.posicion]
        while frente:
            siguiente = []
            for celda in frente:
                for v in mundo.vecinos(celda):
                    if v in vistos or v in prohibidas:
                        continue
                    if v not in paso:
                        return [v]
                    vistos.add(v)
                    siguiente.append(v)
            frente = sorted(siguiente)
        return []

    @staticmethod
    def _paso_de(mundo: Mundo, cosechadora: str) -> set[Celda]:
        """Lo que la cosechadora necesita libre para su traslado (mundo.paso_de); vacío en mundos de prueba."""
        paso_de = getattr(mundo, "paso_de", None)
        return paso_de(cosechadora) if callable(paso_de) else set()

    @staticmethod
    def _siguiente_del_camino(mundo: Mundo, cosechadora: str, celda: Celda) -> set[Celda]:
        """La celda que sigue a `celda` en el camino de esa cosechadora (§4.2, regla 4).
        Usa su franja (mundo.camino) si el mundo ya la tiene; si no, la serpentina completa."""
        camino_de = getattr(mundo, "camino", None)
        camino = camino_de(cosechadora) if camino_de is not None else mundo.camino_serpentina()
        try:
            indice = camino.index(celda)
        except ValueError:
            return set()
        return {camino[indice + 1]} if indice + 1 < len(camino) else set()

    def _enviar(self, buzon: Buzon, tipo: str, receptor: str, tick: int, payload: dict) -> None:
        buzon.enviar(Mensaje(
            tipo=_tipo_mensaje(tipo),
            emisor=self.agent_id,
            receptor=receptor,
            tick_envio=tick,
            payload=payload,
        ))

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
        """Snapshot del tick: tick, agent_id, tipo, pose, estado y carga (trace 2.1), más
        combustible (trace 2.2) cuando el mundo ya lo puso."""
        if self.posicion is None:
            raise RuntimeError("El carro debe registrarse en el mundo antes de generar su registro.")
        registro = {
            "tick": tick,
            "agent_id": self.agent_id,
            "tipo": CARRO,
            "pose": {"x": self.posicion[0], "y": self.posicion[1], "orientacion": self.orientacion},
            "estado": self.estado.value,
            "carga": {"actual": self.carga, "capacidad": self.capacidad},
        }
        if self.combustible is not None:
            registro["combustible"] = round(self.combustible, 2)
        return registro
