"""Cosechadora: agente híbrido y administradora del servicio (Contract Net).  [Bloque B]

Especificación: §5.1 de la primera entrega (tabla de estados) y §3, §4, §5, §6, §7 y §9 de la segunda.

Dos modos, según `config.politica["asignacion"]`:
- `directa` (línea base): al llenarse envía LLENA a su carro asignado, carro ((j − 1) mod n) + 1.
  Con una cosechadora y un carro es exactamente la cosechadora de v0.1.
- `subasta`: al llegar al umbral de aviso (o llenarse, o cosechar su última celda) llama a todos los
  carros (SOLICITUD_SERVICIO, cfp), recoge PROPUESTA / RECHAZO, adjudica al menor costo (empate: menor
  id) con ACEPTACION y descarta a los demás con RECHAZO_PROPUESTA. Sigue cosechando mientras le quepa
  (despacho anticipado) y transfiere solo con el carro contratado.

Con varios agentes (o subasta) se mueve con rutas en el tiempo y reserva sus celdas (§5), con la
misma convención que el carro: en el tick t planea con `rutas.bfs_tiempo(pos, destino, t − 1, ...)`.
No hay estados nuevos: ir a recargar usa REGRESANDO_A_BASE y EN_BASE.
"""

from __future__ import annotations

import logging
from enum import Enum

from . import rutas
from .config import POLITICA_POR_DEFECTO
from .datos.formato import COMBUSTIBLE_RESERVA, R14_HILERAS, R3_CELDA_OCUPADA, R9_BODEGA
from .mensajes import Buzon, Mensaje, TipoMensaje
from .mundo import Mundo, duracion_ticks

Celda = tuple[int, int]

registrador = logging.getLogger("harvest_sim.cosechadora")

DIRECCIONES = {(0, -1): "N", (1, 0): "E", (0, 1): "S", (-1, 0): "O"}


class EstadoCosechadora(str, Enum):
    EN_BASE = "EN_BASE"
    YENDO_A_CAMPO = "YENDO_A_CAMPO"
    COSECHANDO = "COSECHANDO"
    LLENA_ESPERANDO = "LLENA_ESPERANDO"
    TRANSFIRIENDO = "TRANSFIRIENDO"
    REGRESANDO_A_BASE = "REGRESANDO_A_BASE"
    FIN = "FIN"


# Estados en que la cosechadora no se mueve: reserva su celda todo el horizonte (lo pide el carro).
QUIETA = (
    EstadoCosechadora.EN_BASE,
    EstadoCosechadora.LLENA_ESPERANDO,
    EstadoCosechadora.TRANSFIRIENDO,
    EstadoCosechadora.FIN,
)


# Estados (de cualquier agente) en que su celda sigue ocupada todo el horizonte.
AGENTES_QUIETOS = frozenset({"EN_BASE", "ESPERANDO_TRANSFERENCIA", "DESCARGANDO", "LLENA_ESPERANDO",
                             "TRANSFIRIENDO", "FIN"})


class Cosechadora:
    def __init__(self, agent_id: str, capacidad: int) -> None:
        self.agent_id = agent_id
        self.capacidad = capacidad
        self.estado = EstadoCosechadora.EN_BASE
        self.carga = 0

        # Mundo.registrar() asigna la posición inicial y el combustible antes de ejecutar pasos.
        self.posicion: Celda | None = None
        self.orientacion = "S"
        self.combustible: float | None = None
        self.tanque: float | None = None

        self._base: Celda | None = None
        self._camino: list[Celda] = []
        self._siguiente = 0  # índice en _camino de la siguiente celda por cosechar
        self._ticks_restantes = 0
        self._cantidad_transferencia = 0
        self._recargando = False
        # Ticks que esperó (con el motor encendido) entre llenarse y terminar la transferencia la
        # última vez: la estimación de combustible usa la experiencia, no solo la teoría.
        self._espera_ultima = 0
        self._lleno_desde: int | None = None
        # Celda a la que vuelve después de recargar si se fue con grano (regreso de emergencia).
        self._retorno: Celda | None = None
        # Hileras (plan de hileras y rutas): la vuelta de cabecera hacia la pasada siguiente dura lo que la curva
        # de Dubins; se cuenta desde que sale de la pasada. None = no está dando una vuelta.
        self._vuelta_total: int | None = None
        self._vuelta_ticks = 0
        self.ticks_en_vueltas = 0
        self._giro: tuple[str, int] | None = None  # giro en el sitio en curso (A* con rumbo)

        # Administración del servicio (§7).
        self._num_servicio = 0
        self.servicio: str | None = None
        self._tick_llamada = 0
        self.propuestas: dict[str, float] = {}
        self.contratado: str | None = None
        self._pendiente = False  # pidió carro y la subasta quedó sin propuestas: reintentar
        self._reintento_en = 0

        # Rutas en el tiempo y registro de esperas (§5 y §10).
        self._plan: list[rutas.PasoEnTiempo] = []
        self.cruces_cultivo = 0  # ticks de traslado sin ruta por camino o rastrojo (R13, con mapa)
        self._plan_guardado: tuple[Celda | None, list[rutas.PasoEnTiempo]] = (None, [])
        self._espera_desde: int | None = None
        self._bloqueo_registrado = False
        self._tramo = None
        self._reglas_del_tramo: set[str] = set()

    # ------------------------------------------------------------------ paso

    def paso(self, tick: int, mundo: Mundo, buzon: Buzon) -> None:
        if self.posicion is None:
            raise RuntimeError(
                "La cosechadora debe registrarse en el mundo antes de avanzar."
            )

        self._plan = []
        politica = self._politica(mundo)
        subasta = politica["asignacion"] == "subasta"

        # Se lee el buzón ANTES del return de FIN: un mensaje viejo sin leer dejaría pendientes
        # para siempre y la simulación nunca terminaría.
        if subasta:
            self._leer_buzon(buzon)

        if self.estado != EstadoCosechadora.FIN:
            if subasta:
                self._decidir(tick, mundo, buzon, politica)
                if (self._pendiente and self.servicio is None and tick >= self._reintento_en
                        and self.estado in (EstadoCosechadora.COSECHANDO, EstadoCosechadora.LLENA_ESPERANDO)):
                    self._llamar(tick, mundo, buzon)
            self._maquina(tick, mundo, buzon, politica)

        if self._con_reservas(mundo):
            self._reservar(tick, mundo)

    def _maquina(self, tick: int, mundo: Mundo, buzon: Buzon, politica: dict) -> None:
        if self.estado == EstadoCosechadora.EN_BASE:
            if not self._camino:
                self._base = mundo.base_de(self.agent_id)
                camino = getattr(mundo, "camino", None)
                self._camino = list(camino(self.agent_id) if callable(camino) else mundo.camino_serpentina())
                if not self._camino:
                    raise ValueError("El campo debe tener al menos una celda.")
                self._siguiente = 0
                self.estado = EstadoCosechadora.YENDO_A_CAMPO
            elif self._recargando and self._tanque_lleno():
                self._recargando = False
                self.estado = EstadoCosechadora.YENDO_A_CAMPO
            return

        if self.estado in (EstadoCosechadora.COSECHANDO, EstadoCosechadora.LLENA_ESPERANDO):
            if self._debe_volver(mundo, politica):
                mundo.registrar_restriccion(
                    self.agent_id, COMBUSTIBLE_RESERVA,
                    f"regresa a recargar con {self.carga} de grano: {self.combustible:.2f} L solo alcanzan para volver",
                )
                if self.estado == EstadoCosechadora.LLENA_ESPERANDO:
                    self._retorno = self.posicion
                if self.servicio is not None:
                    # libera la llamada sin adjudicar; al volver pide carro otra vez
                    self.servicio, self.propuestas, self._pendiente = None, {}, True
                    self._reintento_en = tick
                self._recargando = True
                self.estado = EstadoCosechadora.REGRESANDO_A_BASE
                self._avanzar_hacia(self._base, tick, mundo)
                return

        if self.estado == EstadoCosechadora.COSECHANDO:
            siguiente = self._camino[self._siguiente]
            entrada = self._entrada(siguiente, mundo)
            if siguiente not in mundo.vecinos(self.posicion) or (entrada is not None and self.posicion != entrada):
                # un obstáculo separa las dos celdas, o (con hileras) es una pasada nueva: se llega a su celda de
                # entrada en la cabecera y se entra de frente (R14), con la vuelta de Dubins
                if entrada is not None:
                    self._vuelta_total = mundo.ticks_de_vuelta(self.posicion, self.orientacion, siguiente)
                    self._vuelta_ticks = 0
                    if mundo.es_vuelta_de_cabecera(self.posicion, siguiente):
                        # vuelta de fin de pasada a una pasada cercana: su curva va al log (2.4) para Unity
                        puntos = mundo.trayectoria_de_vuelta(self.posicion, self.orientacion, siguiente)
                        if len(puntos) >= 2:
                            mundo.registrar_trayectoria(self.agent_id, "vuelta", puntos, max(1, self._vuelta_total))
                    if siguiente in mundo.vecinos(self.posicion):
                        # sin la regla habría entrado de lado a la pasada (cortando las hileras con el cabezal)
                        mundo.registrar_restriccion(
                            self.agent_id, R14_HILERAS,
                            f"entra a la pasada {list(siguiente)} desde la cabecera {list(entrada)}, no de lado")
                self.estado = EstadoCosechadora.YENDO_A_CAMPO
            else:
                if self._celda_ocupada(siguiente, tick, mundo):
                    self._esperar(tick, mundo, f"espera a que se libere {list(siguiente)}")
                    return
                self._dejar_de_esperar()
                self._mover_a(siguiente)
                self._cosechar_y_evaluar(tick, mundo, buzon, politica)
                return

        if self.estado == EstadoCosechadora.YENDO_A_CAMPO:
            objetivo = self._camino[self._siguiente]
            entrada = None if self._retorno is not None else self._entrada(objetivo, mundo)
            if entrada is not None:
                # hileras: ir a la celda de cabecera de la pasada, completar la vuelta y entrar de frente
                if self._vuelta_total is not None:
                    self._vuelta_ticks += 1
                    self.ticks_en_vueltas += 1
                if self.posicion != entrada:
                    self._avanzar_hacia(entrada, tick, mundo)
                    return
                if self._vuelta_total is not None and self._vuelta_ticks < self._vuelta_total:
                    return  # sigue dando la vuelta en la cabecera
                if self._celda_ocupada(objetivo, tick, mundo):
                    self._esperar(tick, mundo, f"espera a que se libere {list(objetivo)}")
                    return
                self._dejar_de_esperar()
                self._vuelta_total = None
                self._mover_a(objetivo)
                self._cosechar_y_evaluar(tick, mundo, buzon, politica)
                return
            destino = self._retorno or objetivo
            if self.posicion != destino and not self._avanzar_hacia(destino, tick, mundo):
                return
            if self.posicion == destino:
                if self._retorno is not None:
                    # volvió llena a donde esperaba: el carro (asignado o contratado) sigue en camino
                    self._retorno = None
                    self.estado = EstadoCosechadora.LLENA_ESPERANDO
                    if politica["asignacion"] == "subasta" and self.servicio is None and self.contratado is None:
                        self._llamar(tick, mundo, buzon)
                    return
                self._cosechar_y_evaluar(tick, mundo, buzon, politica)
            return

        if self.estado == EstadoCosechadora.LLENA_ESPERANDO:
            carro = self._carro_que_transfiere(mundo, politica)
            if (
                carro is not None
                and mundo.posicion(carro) in mundo.vecinos(self.posicion)
                and mundo.estado_de(carro) == "ESPERANDO_TRANSFERENCIA"
            ):
                self._cantidad_transferencia = self.carga
                duracion = self._duracion(self._cantidad_transferencia, mundo.config.tasa_transferencia, mundo)
                # El tick de entrada ya cuenta como el primer snapshot.
                self._ticks_restantes = duracion - 1
                self.estado = EstadoCosechadora.TRANSFIRIENDO
            return

        if self.estado == EstadoCosechadora.TRANSFIRIENDO:
            if self._ticks_restantes > 0:
                self._ticks_restantes -= 1
                return
            self._terminar_transferencia(tick, mundo, buzon, politica)
            return

        if self.estado == EstadoCosechadora.REGRESANDO_A_BASE:
            if self.posicion == self._base:
                self.estado = EstadoCosechadora.EN_BASE if self._recargando else EstadoCosechadora.FIN
                return
            self._avanzar_hacia(self._base, tick, mundo)

    # ------------------------------------------------------------- cosecha

    def _cosechar_y_evaluar(self, tick: int, mundo: Mundo, buzon: Buzon, politica: dict) -> None:
        """Cosecha mediante el mundo y decide si pide carro (en el mismo tick, como el LLENA de v0.1)."""
        mundo.cosechar(self.agent_id, self.posicion)
        self._siguiente += 1

        ultima = self._siguiente >= len(self._camino)
        llena = ultima or not self._cabe(self._camino[self._siguiente], mundo)

        if politica["asignacion"] == "subasta":
            sin_servicio = self.servicio is None and self.contratado is None and not self._pendiente
            umbral = self.carga >= politica["umbral_aviso"] * self.capacidad
            # M1: con aviso aprendido, la tabla Q decide; llenarse sin carro en camino es el cliff.
            despachador = getattr(mundo, "despachador", None) if politica.get("aviso", "umbral") != "umbral" else None
            if sin_servicio and despachador is not None:
                if llena:
                    despachador.forzada(self, mundo)
                if llena or despachador.decidir(self, mundo, umbral):
                    self._llamar(tick, mundo, buzon)
            elif sin_servicio and (llena or umbral):
                self._llamar(tick, mundo, buzon)
        elif llena:
            self._enviar(buzon, TipoMensaje.LLENA, self._carro_asignado(mundo), tick, {
                "x": self.posicion[0],
                "y": self.posicion[1],
                "carga": self.carga,
            })

        if llena:
            self._lleno_desde = tick
        self.estado = EstadoCosechadora.LLENA_ESPERANDO if llena else EstadoCosechadora.COSECHANDO

    @staticmethod
    def _entrada(celda: Celda, mundo: Mundo) -> Celda | None:
        """Con hileras: la celda de cabecera desde la que se entra a la pasada que empieza en `celda`."""
        if not getattr(mundo, "hileras", False):
            return None
        entrada = mundo.entrada_de_pasada(celda)
        return entrada[0] if entrada else None

    def _bloqueadas_traslado(self, destino: Celda, mundo: Mundo) -> tuple[set[Celda], bool]:
        """Celdas fijas que el traslado evita y si tiene que cruzar cultivo en pie. R13
        (docs/especificacion_terreno.md §7): en traslado, la cosechadora va por camino y rastrojo; solo si
        no existe esa ruta cruza su propio cultivo en pie (se cuenta en cruces_cultivo). Con hileras (R14)
        nunca cruza las pasadas en pie: si no hay ruta por rastrojo, solo puede pasar por cabecera en pie."""
        bloqueadas = mundo.bloqueadas_fijas(self.agent_id)
        if getattr(mundo, "hileras", False):
            en_pie = mundo.cultivo_en_pie() - {destino, self.posicion}
            for evitar, cruza in ((bloqueadas | en_pie, False), (bloqueadas | (en_pie - mundo.cabecera), True)):
                if rutas.bfs(self.posicion, destino, mundo.ancho, mundo.alto, evitar) is not None:
                    return evitar, cruza
            return bloqueadas, True
        if getattr(mundo, "respetar_cultivo", False):
            evitar = bloqueadas | (mundo.cultivo_en_pie() - {destino, self.posicion})
            if rutas.bfs(self.posicion, destino, mundo.ancho, mundo.alto, evitar) is not None:
                return evitar, False
            return bloqueadas, True
        return bloqueadas, False

    def celdas_de_paso(self, mundo: Mundo) -> set[Celda]:
        """En traslado (YENDO_A_CAMPO): el destino y los dos siguientes pasos de la ruta más corta sin
        agentes. El carro contratado espera fuera de ellas; si se detuviera ahí, en un pasillo de una celda
        la cosechadora no podría pasar ni llenarse, y el carro solo se mueve después de la transferencia."""
        if self.estado != EstadoCosechadora.YENDO_A_CAMPO or self.posicion is None:
            return set()
        if self._retorno is None and self._siguiente >= len(self._camino):
            return set()
        destino = self._retorno or self._entrada(self._camino[self._siguiente], mundo) or self._camino[self._siguiente]
        ruta = rutas.bfs(self.posicion, destino, mundo.ancho, mundo.alto, self._bloqueadas_traslado(destino, mundo)[0])
        if getattr(mundo, "hileras", False):
            # con hileras el carro no la persigue mientras se traslada, sino que espera: tiene que esperar fuera de
            # toda su ruta (en un camino o un pasillo de una celda bloquearía a cualquier distancia)
            return {destino} | set(ruta or [])
        return {destino} | set((ruta or [])[:2])

    def _cabe(self, celda: Celda, mundo: Mundo) -> bool:
        rendimiento = getattr(mundo, "rendimiento", None)
        if callable(rendimiento):
            return self.carga + rendimiento(celda) <= self.capacidad
        return self.carga < self.capacidad

    def _terminar_transferencia(self, tick: int, mundo: Mundo, buzon: Buzon, politica: dict) -> None:
        subasta = politica["asignacion"] == "subasta"
        carro = self._carro_que_transfiere(mundo, politica)
        cantidad = mundo.transferir(self.agent_id, carro, self._cantidad_transferencia)
        if self._lleno_desde is not None:
            self._espera_ultima = tick - self._lleno_desde
            self._lleno_desde = None
        payload = {"servicio": self.servicio, "cantidad": cantidad} if subasta else {"cantidad": cantidad}
        self._enviar(buzon, TipoMensaje.TRANSFERENCIA_TERMINADA, carro, tick, payload)
        if subasta:
            self.servicio, self.contratado, self.propuestas = None, None, {}

        if self.carga > 0:
            # el carro no tenía lugar para todo: se pide otro servicio
            self.estado = EstadoCosechadora.LLENA_ESPERANDO
            if subasta:
                self._llamar(tick, mundo, buzon)
            else:
                self._enviar(buzon, TipoMensaje.LLENA, carro, tick,
                             {"x": self.posicion[0], "y": self.posicion[1], "carga": self.carga})
            return

        if self._siguiente >= len(self._camino):
            self.estado = EstadoCosechadora.REGRESANDO_A_BASE
        elif not self._alcanza_siguiente_carga(mundo, politica):
            mundo.registrar_restriccion(
                self.agent_id, COMBUSTIBLE_RESERVA,
                f"va a recargar: {self.combustible:.2f} L no alcanzan para la siguiente carga",
            )
            self._recargando = True
            self.estado = EstadoCosechadora.REGRESANDO_A_BASE
        else:
            self.estado = EstadoCosechadora.COSECHANDO

    # --------------------------------------------------------------- subasta

    def _llamar(self, tick: int, mundo: Mundo, buzon: Buzon) -> None:
        """SOLICITUD_SERVICIO (cfp) a cada carro. Un reintento es un servicio nuevo (#n + 1)."""
        envio = tick
        self._num_servicio += 1
        self.servicio = f"{self.agent_id}#{self._num_servicio}"
        self._tick_llamada = envio
        self.propuestas = {}
        self.contratado = None
        self._pendiente = False
        for carro in self._carros(mundo):
            self._enviar(buzon, TipoMensaje.SOLICITUD_SERVICIO, carro, envio, {
                "servicio": self.servicio,
                "x": self.posicion[0],
                "y": self.posicion[1],
                "carga": self.carga,
                "capacidad": self.capacidad,
            })

    def _leer_buzon(self, buzon: Buzon) -> None:
        mensaje = buzon.leer(self.agent_id)
        while mensaje is not None:
            tipo = getattr(mensaje.tipo, "value", mensaje.tipo)
            servicio = mensaje.payload.get("servicio")
            vigente = servicio is not None and servicio == self.servicio and self.contratado is None
            if tipo == TipoMensaje.PROPUESTA.value and vigente:
                self.propuestas[mensaje.emisor] = mensaje.payload["costo"]
            elif tipo == TipoMensaje.RECHAZO.value and vigente:
                pass  # el carro no participa; queda en el log con su motivo
            else:
                registrador.warning("%s descarta %s de %s (servicio %s)", self.agent_id, tipo,
                                    mensaje.emisor, servicio)
            mensaje = buzon.leer(self.agent_id)

    def _decidir(self, tick: int, mundo: Mundo, buzon: Buzon, politica: dict) -> None:
        """Al vencer la espera: ACEPTACION al menor costo (empate: menor id) y RECHAZO_PROPUESTA a los
        demás que propusieron; sin propuestas, reintento tras `reintento_subasta` ticks."""
        if self.servicio is None or self.contratado is not None:
            return
        # 2 · retraso: pueden llegar tarde la llamada y la respuesta (decisión D-C)
        if tick < self._tick_llamada + politica["espera_propuestas"] + 2 * self._retraso_maximo(mundo):
            return
        if not self.propuestas:
            registrador.info("t=%03d | %s: %s sin propuestas; reintenta en %d ticks", tick, self.agent_id,
                             self.servicio, politica["reintento_subasta"])
            self.servicio = None
            self._pendiente = True
            self._reintento_en = tick + politica["reintento_subasta"]
            return
        ganador = min(self.propuestas, key=lambda carro: (self.propuestas[carro], _orden_id(carro)))
        self.contratado = ganador
        self._enviar(buzon, TipoMensaje.ACEPTACION, ganador, tick, {"servicio": self.servicio})
        for carro in sorted(self.propuestas, key=_orden_id):
            if carro != ganador:
                self._enviar(buzon, TipoMensaje.RECHAZO_PROPUESTA, carro, tick, {"servicio": self.servicio})

    @staticmethod
    def _retraso_maximo(mundo: Mundo) -> int:
        incertidumbre = getattr(getattr(mundo, "config", None), "incertidumbre", None) or {}
        retraso = incertidumbre.get("retraso_mensajes") or {}
        return retraso.get("maximo", 0) if retraso.get("probabilidad", 0) > 0 else 0

    def _carro_que_transfiere(self, mundo: Mundo, politica: dict) -> str | None:
        if politica["asignacion"] == "subasta":
            return self.contratado
        return self._carro_asignado(mundo)

    def _carro_asignado(self, mundo: Mundo) -> str:
        """Modo directa: cosechadora j -> carro ((j − 1) mod n) + 1 (spec §2)."""
        n = getattr(getattr(mundo, "config", None), "num_carros", 1)
        j = _orden_id(self.agent_id)
        return f"carro_{(j - 1) % n + 1}"

    @staticmethod
    def _carros(mundo: Mundo) -> list[str]:
        n = getattr(getattr(mundo, "config", None), "num_carros", 1)
        return [f"carro_{i}" for i in range(1, n + 1)]

    # ------------------------------------------------------------ combustible

    def _alcanza_siguiente_carga(self, mundo: Mundo, politica: dict) -> bool:
        """¿Alcanza para la SIGUIENTE carga (las celdas hasta llenarse, la espera de la transferencia)
        y volver a la base sin bajar de la reserva? Se estima solo la siguiente carga: con todo lo que
        falta del camino, un tanque chico nunca alcanzaría. La espera es la mayor entre la teórica y
        la última que vivió (en subasta esperar al carro puede tardar mucho más), y el regreso lleva un
        margen del 25 %. Con el tanque lleno sale de todos modos."""
        if self.combustible is None or self.tanque is None or not hasattr(mundo, "combustible_para"):
            return True
        if self._tanque_lleno():
            return True
        rendimiento = getattr(mundo, "rendimiento", lambda celda: 1)
        carga, celdas, final = self.carga, 0, self.posicion
        for celda in self._camino[self._siguiente:]:
            if carga + rendimiento(celda) > self.capacidad:
                break
            carga += rendimiento(celda)
            celdas += abs(celda[0] - final[0]) + abs(celda[1] - final[1])
            final = celda
        regreso = mundo.ruta_bfs(final, self._base, mundo.bloqueadas_fijas(self.agent_id))
        distancia = len(regreso) if regreso is not None else abs(final[0] - self._base[0]) + abs(final[1] - self._base[1])
        # margen del 25 % en el regreso por desvíos y esperas en la ruta (rutas en el tiempo)
        celdas += distancia + (distancia + 3) // 4
        teoria = duracion_ticks(max(carga, 1), mundo.config.tasa_transferencia) + politica["espera_propuestas"]
        encendido = max(teoria, self._espera_ultima)
        litros = mundo.combustible_para(self.agent_id, celdas, encendido)
        reserva = mundo.config.combustible["reserva"] * self.tanque
        return self.combustible - litros >= reserva

    def _debe_volver(self, mundo: Mundo, politica: dict) -> bool:
        """Regla de seguridad de la reserva (§9) durante el trabajo: si lo que queda apenas alcanza para
        volver a la base (con 25 % de margen) sin bajar de la reserva, regresa ya. Cubre las esperas
        largas al carro con el motor encendido, que la estimación previa no puede prever.
        No se va si ya hay un carro en camino por su grano (contratado en subasta, o el asignado al que
        avisó con LLENA en directa): ese carro la seguiría hasta su base y se estorbarían."""
        if self.combustible is None or self.tanque is None or not hasattr(mundo, "combustible_para"):
            return False
        if self.contratado is not None:
            return False
        if politica["asignacion"] == "directa" and self.estado == EstadoCosechadora.LLENA_ESPERANDO:
            return False
        if self._base is None or self.posicion == self._base:
            return False
        ruta = mundo.ruta_bfs(self.posicion, self._base, mundo.bloqueadas_fijas(self.agent_id))
        distancia = len(ruta) if ruta is not None else abs(self.posicion[0] - self._base[0]) + abs(self.posicion[1] - self._base[1])
        litros = mundo.combustible_para(self.agent_id, distancia + (distancia + 3) // 4, 2)
        return self.combustible - litros < mundo.config.combustible["reserva"] * self.tanque

    def _tanque_lleno(self) -> bool:
        return self.combustible is None or self.tanque is None or self.combustible >= self.tanque

    # ----------------------------------------------------------------- movimiento

    def _con_reservas(self, mundo: Mundo) -> bool:
        """Rutas en el tiempo salvo en la línea base de una cosechadora y un carro (v0.1 intacto)."""
        config = getattr(mundo, "config", None)
        if config is None or not hasattr(mundo, "reservar"):
            return False
        return (self._politica(mundo)["asignacion"] == "subasta"
                or getattr(config, "num_carros", 1) > 1
                or getattr(config, "num_cosechadoras", 1) > 1)

    def _celda_ocupada(self, celda: Celda, tick: int, mundo: Mundo) -> bool:
        if celda in mundo.ocupadas(self.agent_id):
            return True
        if self._con_reservas(mundo):
            return (celda, tick) in mundo.reservas(excepto=self.agent_id)
        return False

    def _esperar(self, tick: int, mundo: Mundo, detalle: str) -> None:
        """La siguiente celda del camino está ocupada. En v0.1 es un BLOQUEO (§4.2). Con reservas es una
        espera decidida por la regla R3 (una RESTRICCION por espera) y solo es BLOQUEO si dura más que
        el horizonte (§5.5)."""
        if not self._con_reservas(mundo):
            mundo.registrar_bloqueo(self.agent_id)
            return
        if self._espera_desde is None:
            self._espera_desde = tick
            mundo.registrar_restriccion(self.agent_id, R3_CELDA_OCUPADA, detalle)
        elif tick - self._espera_desde > rutas.HORIZONTE and not self._bloqueo_registrado:
            self._bloqueo_registrado = True
            mundo.registrar_bloqueo(self.agent_id)

    def _dejar_de_esperar(self) -> None:
        self._espera_desde = None
        self._bloqueo_registrado = False

    def _avanzar_hacia(self, destino: Celda, tick: int, mundo: Mundo) -> bool:
        """Da un paso hacia `destino`. Devuelve False si no pudo avanzar (bloqueo de v0.1 o sin plan)."""
        if not self._con_reservas(mundo):
            return self._avanzar_v01(destino, mundo)

        bloqueadas, cruza = self._bloqueadas_traslado(destino, mundo)
        if cruza:
            self.cruces_cultivo += 1
        reservas = self._reservas_de_otros(tick, mundo)
        planear = getattr(mundo, "planear_con_rumbo", None)
        if callable(planear):  # con hileras, A* con rumbo; sin hileras, el BFS de siempre
            plan = planear(self.posicion, self.orientacion, destino, tick - 1, bloqueadas, reservas)
        else:
            plan = rutas.bfs_tiempo(self.posicion, destino, tick - 1, mundo.ancho, mundo.alto, bloqueadas, reservas)
        # Compromiso con el plan (la misma regla del carro): como el BFS en el tiempo prefiere esperar,
        # replanear cada tick puede posponer la salida para siempre. Si el plan anterior sigue valiendo,
        # se cumple; solo se cambia por uno que llegue antes.
        previo = self._plan_vigente(tick, destino, mundo, bloqueadas, reservas)
        if previo is not None and (plan is None or previo[-1][1] <= plan[-1][1]):
            plan = previo
        self._plan_guardado = (destino, plan[1:] if plan else [])
        if plan is None:
            self._esperar(tick, mundo, f"sin ruta libre hacia {list(destino)}")
            return False
        if not plan:
            return True
        self._dejar_de_esperar()
        self._registrar_desvio(tick, destino, mundo, bloqueadas, reservas)
        celda, _ = plan[0]
        self._plan = plan[1:]
        if getattr(mundo, "hileras", False):
            self.orientacion, self._giro = rutas.progreso_de_giro(
                self.posicion, self.orientacion, plan, *mundo.costos_de_giro(), self._giro)
        if celda != self.posicion:
            self._mover_a(celda)
            return True
        return False  # espera planeada: no es bloqueo (§5.5)

    def _avanzar_v01(self, destino: Celda, mundo: Mundo) -> bool:
        """BFS evitando celdas ocupadas (primera entrega)."""
        ocupadas = mundo.ocupadas(self.agent_id)
        fijas = mundo.bloqueadas_fijas(self.agent_id)
        ruta = mundo.ruta_bfs(self.posicion, destino, fijas | ocupadas)

        if ruta is None:
            # Solo se cuenta como bloqueo si las ocupaciones impiden una ruta que existiría sin otros
            # agentes.
            if mundo.ruta_bfs(self.posicion, destino, fijas):
                mundo.registrar_bloqueo(self.agent_id)
            return False

        if ruta:
            self._mover_a(ruta[0])

        return True

    def _plan_vigente(self, tick, destino, mundo, bloqueadas, reservas):
        """Lo que queda del plan del tick anterior, si sigue siendo válido: mismo destino, empieza en
        este tick, cada paso es esperar o ir a un vecino, y ninguna (celda, t) la tiene otro."""
        guardado_destino, guardado = self._plan_guardado
        if guardado_destino != destino or not guardado or guardado[0][1] != tick:
            return None
        anterior = self.posicion
        for celda, t in guardado:
            if celda in bloqueadas or (celda, t) in reservas:
                return None
            if celda != anterior and celda not in mundo.vecinos(anterior):
                return None
            anterior = celda
        return list(guardado)

    def _reservas_de_otros(self, tick: int, mundo: Mundo) -> rutas.Reservas:
        """Reservas de los demás más lo que percibe (la misma regla que el carro):
        - las celdas ocupadas ahora (R3: el primer paso nunca entra a una celda ocupada);
        - un agente quieto (en su base, esperando, transfiriendo o descargando) se queda en su celda
          todo el horizonte. Sin esto, la cosechadora planea pasar por la celda de un carro
          estacionado suponiendo que se irá, y lo espera para siempre."""
        reservas = dict(mundo.reservas(excepto=self.agent_id))
        for celda in sorted(mundo.ocupadas(self.agent_id)):
            reservas.setdefault((celda, tick), "ocupada")
        config = mundo.config
        otros = [f"cosechadora_{j}" for j in range(1, config.num_cosechadoras + 1)]
        otros += [f"carro_{i}" for i in range(1, config.num_carros + 1)]
        for agente in otros:
            if agente == self.agent_id:
                continue
            try:
                posicion, estado = mundo.posicion(agente), mundo.estado_de(agente)
            except KeyError:
                continue
            if estado in AGENTES_QUIETOS:
                for t in range(tick, tick + rutas.HORIZONTE + 2):
                    reservas.setdefault((posicion, t), agente)
        return reservas

    def _registrar_desvio(self, tick, destino, mundo, bloqueadas, reservas) -> None:
        """Una RESTRICCION por regla y por tramo (no una por tick), como el carro (§10)."""
        tramo = (self.estado, destino)
        if tramo != self._tramo:
            self._tramo, self._reglas_del_tramo = tramo, set()
        obstaculos = set(getattr(mundo, "obstaculos", ()))
        reglas = rutas.clasificar_desvio(self.posicion, destino, tick - 1, mundo.ancho, mundo.alto,
                                         bloqueadas, obstaculos, reservas)
        # R9: la bodega (prohibida para las cosechadoras) alarga la ruta
        sin_bodega = rutas.bfs(self.posicion, destino, mundo.ancho, mundo.alto, bloqueadas - {mundo.bodega})
        con_bodega = rutas.bfs(self.posicion, destino, mundo.ancho, mundo.alto, bloqueadas)
        if sin_bodega is not None and con_bodega is not None and len(con_bodega) > len(sin_bodega):
            reglas.append(R9_BODEGA)
        for regla in reglas:
            if regla not in self._reglas_del_tramo:
                self._reglas_del_tramo.add(regla)
                mundo.registrar_restriccion(self.agent_id, regla, f"desvío hacia {list(destino)}")

    def _reservar(self, tick: int, mundo: Mundo) -> None:
        """Reserva sus celdas del horizonte para que los carros la rodeen (§5)."""
        limite = tick + rutas.HORIZONTE + 1
        if self.estado in QUIETA:
            propias = [(self.posicion, t) for t in range(tick, limite + 1)]
        elif self.estado == EstadoCosechadora.COSECHANDO:
            propias = [(self.posicion, tick)]
            celda = self.posicion
            for i, t in enumerate(range(tick + 1, limite + 1)):
                indice = self._siguiente + i
                if indice >= len(self._camino) or self._camino[indice] not in mundo.vecinos(celda):
                    break
                celda = self._camino[indice]
                propias.append((celda, t))
            ultimo = propias[-1][1]
            propias += [(celda, t) for t in range(ultimo + 1, limite + 1)]
        else:
            propias = rutas.reservas_de_ruta(self.posicion, self._plan, tick)
        mundo.reservar(self.agent_id, propias)

    def _mover_a(self, destino: Celda) -> None:
        """Actualiza la posición y orientación con un movimiento de una celda."""
        dx = destino[0] - self.posicion[0]
        dy = destino[1] - self.posicion[1]

        if (dx, dy) not in DIRECCIONES:
            raise ValueError("El movimiento debe ser a una celda vecina.")

        self.orientacion = DIRECCIONES[(dx, dy)]
        self.posicion = destino

    # ------------------------------------------------------------------ apoyo

    @staticmethod
    def _politica(mundo: Mundo) -> dict:
        politica = dict(POLITICA_POR_DEFECTO)
        politica.update(getattr(getattr(mundo, "config", None), "politica", None) or {})
        return politica

    @staticmethod
    def _duracion(cantidad: int, tasa: int, mundo: Mundo) -> int:
        """mundo.duracion (con el extra aleatorio, §8) si existe; si no, la fórmula de v0.1."""
        duracion = getattr(mundo, "duracion", None)
        return duracion(cantidad, tasa) if callable(duracion) else duracion_ticks(cantidad, tasa)

    def _enviar(self, buzon: Buzon, tipo: TipoMensaje, receptor: str, tick: int, payload: dict) -> None:
        buzon.enviar(Mensaje(tipo=tipo, emisor=self.agent_id, receptor=receptor, tick_envio=tick,
                             payload=payload))

    def registro(self, tick: int) -> dict:
        if self.posicion is None:
            raise RuntimeError(
                "La cosechadora debe registrarse antes de generar su registro."
            )

        registro = {
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
        if self.combustible is not None:
            registro["combustible"] = round(self.combustible, 2)
        return registro


def _orden_id(agent_id: str) -> int:
    """Número del id (carro_10 va después de carro_2)."""
    return int(agent_id.rsplit("_", 1)[1])
