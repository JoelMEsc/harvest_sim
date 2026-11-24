"""Máquina de estados del carro (§5.2).  [Dueño: Oswaldo]

Usa un Mundo y un Buzon falsos (clases mínimas en el propio test) para no depender de los demás.

Escenario base (mapa 4 x 3, la bodega en (0, 0), la base del carro en (1, 0)):

        x=0   x=1   x=2   x=3
  y=0  [Bod]  [K]    .     .        K = carro en su base
  y=1    .     .    [C]    .        C = cosechadora llena en (2, 1); sigue (3, 1)
  y=2    .     .     .     .
"""

import json
from collections import defaultdict, deque
from types import SimpleNamespace

from harvest_sim import rutas
from harvest_sim.carro import (
    ACEPTACION,
    PROPUESTA,
    RECHAZO,
    RECHAZO_PROPUESTA,
    SOLICITUD_SERVICIO,
    Carro,
    EstadoCarro,
)
from harvest_sim.mensajes import Mensaje, TipoMensaje

BODEGA = (0, 0)
BASE_CARRO = (1, 0)
POS_COSECHADORA = (2, 1)


class AgenteFalso:
    """La cosechadora vista desde el mundo: solo posición y estado."""

    def __init__(self, agent_id, posicion, estado="LLENA_ESPERANDO"):
        self.agent_id = agent_id
        self.posicion = posicion
        self.estado = estado


class MundoFalso:
    """Lo mínimo del contrato de Mundo (§10; README del equipo §3.2 en la segunda entrega) que
    usa el carro, con la misma lógica que el real. Sin `politica`, es el mundo de v0.1."""

    bodega = BODEGA

    def __init__(self, ancho=4, alto=3, tasa_descarga=2, politica=None, num_carros=1,
                 bases=None, obstaculos=(), reserva=0.15):
        self.ancho, self.alto = ancho, alto
        self.config = SimpleNamespace(tasa_descarga=tasa_descarga)
        self._bases = bases or {"carro_1": BASE_CARRO, "cosechadora_1": (2, 0)}
        if politica is not None:  # segunda entrega
            self.config = SimpleNamespace(
                tasa_descarga=tasa_descarga, tasa_transferencia=2, num_carros=num_carros,
                num_cosechadoras=sum(1 for a in self._bases if a.startswith("cosechadora_")),
                politica=politica, combustible={"reserva": reserva},
            )
        self.obstaculos = set(obstaculos)
        self._agentes = {}
        self._reservas = {}
        self.bloqueos = []  # ticks en que se llamó registrar_bloqueo
        self.depositos = []  # (tick, cantidad)
        self.restricciones = []  # (tick, agente, regla)
        self.pisadas = []  # (tick, agente, paso, dueño anterior): reservas que pisaron la de otro
        self.tick = 0

    # --- segunda entrega

    def nuevo_tick(self, tick):
        self.tick = tick
        self._reservas = {k: v for k, v in self._reservas.items() if k[1] >= tick}

    def reservar(self, agent_id, ruta):
        desde = ruta[0][1]
        self._reservas = {k: v for k, v in self._reservas.items() if not (v == agent_id and k[1] >= desde)}
        for paso in ruta:
            dueno = self._reservas.get(paso, agent_id)
            if dueno != agent_id:  # como el mundo real, la nueva reemplaza; aquí además se anota
                self.pisadas.append((self.tick, agent_id, paso, dueno))
            self._reservas[paso] = agent_id

    def reservas(self, excepto):
        return {k: v for k, v in self._reservas.items() if v != excepto}

    def registrar_restriccion(self, agent_id, regla, detalle):
        self.restricciones.append((self.tick, agent_id, regla))

    def combustible_para(self, agent_id, celdas, ticks_encendido):
        return celdas * 1.0 + ticks_encendido * 0.5

    def registrar(self, agente):
        agente.posicion = self._bases[agente.agent_id]
        self._agentes[agente.agent_id] = agente

    def base_de(self, agent_id):
        return self._bases[agent_id]

    def posicion(self, agent_id):
        return self._agentes[agent_id].posicion

    def estado_de(self, agent_id):
        estado = self._agentes[agent_id].estado
        return getattr(estado, "value", estado)

    def ocupadas(self, excepto):
        return {a.posicion for i, a in self._agentes.items() if i != excepto}

    def bloqueadas_fijas(self, agent_id):
        bodega = {self.bodega} if agent_id.startswith("cosechadora_") else set()
        return bodega | self.obstaculos

    def camino_serpentina(self):
        camino = []
        for y in range(1, self.alto):
            xs = range(self.ancho) if y % 2 else range(self.ancho - 1, -1, -1)
            camino.extend((x, y) for x in xs)
        return camino

    def vecinos(self, celda):
        return rutas.vecinos(celda, self.ancho, self.alto)

    def ruta_bfs(self, origen, destino, bloqueadas):
        return rutas.bfs(origen, destino, self.ancho, self.alto, bloqueadas)

    def depositar(self, agent_id):
        agente = self._agentes[agent_id]
        assert agente.posicion == self.bodega, "solo se deposita en la bodega"
        cantidad, agente.carga = agente.carga, 0
        self.depositos.append((self.tick, cantidad))
        return cantidad

    def registrar_bloqueo(self, agent_id):
        assert agent_id.startswith("carro_")
        self.bloqueos.append(self.tick)


class BuzonFalso:
    """Filas FIFO por agente. `entregar` simula que el mensaje llegó a la fila; `enviados`
    guarda lo que el carro manda (con el tipo como texto)."""

    def __init__(self):
        self._filas = defaultdict(deque)
        self.enviados = []

    def entregar(self, mensaje):
        self._filas[mensaje.receptor].append(mensaje)

    def enviar(self, mensaje):
        self.enviados.append(mensaje)
        return len(self.enviados)

    def leer(self, agent_id):
        fila = self._filas[agent_id]
        return fila.popleft() if fila else None

    def hay_pendientes(self, agent_id):
        return bool(self._filas[agent_id])

    def fila(self, agent_id):
        return list(self._filas[agent_id])


def llena(x, y, carga=4):
    return Mensaje(TipoMensaje.LLENA, "cosechadora_1", "carro_1", 0, {"x": x, "y": y, "carga": carga})


def terminada(cantidad):
    return Mensaje(TipoMensaje.TRANSFERENCIA_TERMINADA, "cosechadora_1", "carro_1", 0, {"cantidad": cantidad})


def preparar(tasa_descarga=2):
    mundo, buzon = MundoFalso(tasa_descarga=tasa_descarga), BuzonFalso()
    cosechadora = AgenteFalso("cosechadora_1", None)
    carro = Carro("carro_1", capacidad=20)
    mundo.registrar(cosechadora)
    mundo.registrar(carro)
    cosechadora.posicion = POS_COSECHADORA
    return mundo, buzon, cosechadora, carro


def correr(mundo, buzon, carro, hasta, guion):
    """Corre los ticks 1..hasta. `guion[t]` se ejecuta al inicio del tick t, antes del paso del
    carro (es lo que harían la entrega de mensajes y la cosechadora). Devuelve los registros
    por tick, empezando por el 0."""
    registros = [carro.registro(0)]
    for t in range(1, hasta + 1):
        mundo.tick = t
        if t in guion:
            guion[t]()
        carro.paso(t, mundo, buzon)
        registros.append(carro.registro(t))
    return registros


def guion_ciclo(buzon, carro, carga=4):
    """LLENA en el tick 1; la cosechadora transfiere `carga` y avisa en el tick 4."""

    def transferir():
        carro.carga = carga  # lo hace el mundo (mundo.transferir); aquí basta con el efecto
        buzon.entregar(terminada(carga))

    return {1: lambda: buzon.entregar(llena(*POS_COSECHADORA, carga)), 4: transferir}


def estados(registros):
    return [r["estado"] for r in registros]


def posiciones(registros):
    return [(r["pose"]["x"], r["pose"]["y"]) for r in registros]


# --------------------------------------------------------------------------- tests


def test_carro_solo_revisa_su_fila_en_en_base():
    """Con mensajes en la fila y estado distinto de EN_BASE, no los toca ni los descarta."""
    mundo, buzon, _, carro = preparar()
    segundo = llena(3, 2)
    guion = guion_ciclo(buzon, carro)
    guion[5] = lambda: buzon.entregar(segundo)  # llega mientras el carro va a la bodega

    registros = correr(mundo, buzon, carro, 9, guion)

    # Ticks 5..9: YENDO_A_BODEGA, DESCARGANDO, REGRESANDO_A_BASE y la llegada a EN_BASE.
    for t in range(5, 10):
        assert estados(registros)[t - 1] != "EN_BASE"
    assert buzon.fila("carro_1") == [segundo]  # intacto todo ese tiempo

    # Ya en EN_BASE, el siguiente tick sí lo atiende.
    correr(mundo, buzon, carro, 1, {})
    assert carro.estado == EstadoCarro.YENDO_A_COSECHADORA
    assert buzon.fila("carro_1") == []
    assert carro.objetivo in rutas.vecinos((3, 2), mundo.ancho, mundo.alto)

    # Un LLENA que llega mientras espera la transferencia tampoco se pierde:
    # el carro lo aparta para atenderlo al volver a EN_BASE.
    mundo, buzon, _, carro = preparar()
    guion = guion_ciclo(buzon, carro)
    guion[3] = lambda: buzon.entregar(segundo)
    correr(mundo, buzon, carro, 10, guion)
    assert carro.estado == EstadoCarro.YENDO_A_COSECHADORA
    assert carro.objetivo in rutas.vecinos((3, 2), mundo.ancho, mundo.alto)


def test_carro_atiende_en_orden_fifo():
    """Con dos LLENA pendientes, atiende primero el más antiguo."""
    mundo, buzon, _, carro = preparar()
    primero, segundo = llena(*POS_COSECHADORA), llena(3, 2)
    buzon.entregar(primero)
    buzon.entregar(segundo)

    correr(mundo, buzon, carro, 1, {})

    assert carro.estado == EstadoCarro.YENDO_A_COSECHADORA
    assert carro.objetivo in rutas.vecinos(POS_COSECHADORA, mundo.ancho, mundo.alto)
    assert buzon.fila("carro_1") == [segundo]  # el segundo sigue esperando su turno


def test_carro_ciclo_completo_de_estados():
    """EN_BASE -> YENDO_A_COSECHADORA -> ESPERANDO_TRANSFERENCIA -> YENDO_A_BODEGA ->
    DESCARGANDO -> REGRESANDO_A_BASE -> EN_BASE, con las condiciones del §5.2."""
    mundo, buzon, _, carro = preparar(tasa_descarga=2)
    registros = correr(mundo, buzon, carro, 10, guion_ciclo(buzon, carro, carga=4))

    assert estados(registros) == [
        "EN_BASE",                  # 0
        "YENDO_A_COSECHADORA",      # 1  lee LLENA, elige (2, 0), sin moverse
        "ESPERANDO_TRANSFERENCIA",  # 2  un paso y llegó
        "ESPERANDO_TRANSFERENCIA",  # 3  espera inmóvil
        "YENDO_A_BODEGA",           # 4  lee TRANSFERENCIA_TERMINADA, sin moverse
        "YENDO_A_BODEGA",           # 5  (1, 0)
        "DESCARGANDO",              # 6  (0, 0): llegó; ceil(4 / 2) = 2 ticks
        "DESCARGANDO",              # 7
        "REGRESANDO_A_BASE",        # 8  deposita, sin moverse
        "EN_BASE",                  # 9  (1, 0): llegó
        "EN_BASE",                  # 10 reposo, fila vacía
    ]
    assert posiciones(registros) == [
        (1, 0), (1, 0), (2, 0), (2, 0), (2, 0), (1, 0), (0, 0), (0, 0), (0, 0), (1, 0), (1, 0),
    ]
    # Objetivo: N (2, 0) y O (1, 1) empatan a 1 paso; gana N. E (3, 1) se evita (serpentina).
    assert [r["pose"]["orientacion"] for r in registros][:3] == ["N", "N", "E"]
    assert [r["carga"]["actual"] for r in registros] == [0, 0, 0, 0, 4, 4, 4, 4, 0, 0, 0]
    assert mundo.depositos == [(8, 4)]
    assert mundo.bloqueos == []  # esperar la transferencia no es un bloqueo


def test_carro_duracion_de_descarga():
    """ceil(carga / tasa_descarga) snapshots en DESCARGANDO; una carga parcial dura menos."""
    for carga, tasa, esperado in [(4, 2, 2), (3, 2, 2), (1, 2, 1), (5, 2, 3), (20, 5, 4), (6, 10, 1)]:
        mundo, buzon, _, carro = preparar(tasa_descarga=tasa)
        registros = correr(mundo, buzon, carro, 12, guion_ciclo(buzon, carro, carga))

        ticks = [r["tick"] for r in registros if r["estado"] == "DESCARGANDO"]
        assert len(ticks) == esperado, (carga, tasa)
        assert ticks == list(range(ticks[0], ticks[0] + esperado))  # consecutivos
        # Durante la descarga la carga sigue en el carro; se deposita el tick siguiente al último.
        assert all(registros[t]["carga"]["actual"] == carga for t in ticks)
        assert mundo.depositos == [(ticks[-1] + 1, carga)]

    # La tasa también puede pasarse al construir el carro (sin mundo.config).
    mundo, buzon, _, _ = preparar()
    del mundo.config
    carro = Carro("carro_1", capacidad=20, tasa_descarga=3)
    mundo.registrar(carro)
    registros = correr(mundo, buzon, carro, 12, guion_ciclo(buzon, carro, carga=7))
    assert estados(registros).count("DESCARGANDO") == 3


def test_carro_registra_cantidad_del_mensaje():
    """Al recibir TRANSFERENCIA_TERMINADA lee `cantidad` y coincide con su carga."""
    for carga in (4, 3):  # 3 = carga parcial de la última celda
        mundo, buzon, _, carro = preparar()
        assert carro.cantidad_recibida is None
        correr(mundo, buzon, carro, 4, guion_ciclo(buzon, carro, carga))

        assert carro.estado == EstadoCarro.YENDO_A_BODEGA
        assert carro.cantidad_recibida == carga == carro.carga


def test_carro_registra_bloqueo_solo_si_no_puede_moverse():
    """§4.2: celda ocupada con desvío -> recalcula y avanza (sin bloqueo); sin ruta -> espera
    y registra un BLOQUEO por tick; esperar la transferencia nunca es un bloqueo."""
    mundo, buzon, cosechadora, carro = preparar()

    def tapar_camino():  # la cosechadora se pone en (1, 0), el siguiente paso hacia la bodega
        cosechadora.posicion = (1, 0)

    def liberar_base():
        cosechadora.posicion = (3, 0)

    guion = guion_ciclo(buzon, carro)
    guion[5] = tapar_camino
    guion[12] = liberar_base
    registros = correr(mundo, buzon, carro, 13, guion)

    pos = posiciones(registros)
    # Tick 5: (1, 0) ocupada; recalcula y rodea por abajo: (2, 1) -> (1, 1) -> (0, 1) -> (0, 0).
    assert pos[5:9] == [(2, 1), (1, 1), (0, 1), (0, 0)]
    # Ticks 10 y 11: ya descargó, pero su base (1, 0) está ocupada: no hay ruta, espera.
    assert estados(registros)[10:12] == ["REGRESANDO_A_BASE", "REGRESANDO_A_BASE"]
    assert pos[10:12] == [(0, 0), (0, 0)]
    assert mundo.bloqueos == [11]
    # Tick 12: la base se libera y llega.
    assert pos[12] == BASE_CARRO and estados(registros)[12] == "EN_BASE"


def test_carro_registro():
    """registro() trae exactamente tick, agent_id, tipo, pose, estado y carga (§6.1), sin
    intencion, objetivo ni checksum; listas y textos, no tuplas ni Enum."""
    mundo, buzon, _, carro = preparar()
    registros = correr(mundo, buzon, carro, 2, guion_ciclo(buzon, carro))

    inicial = registros[0]
    assert inicial == {
        "tick": 0,
        "agent_id": "carro_1",
        "tipo": "carro",
        "pose": {"x": 1, "y": 0, "orientacion": "N"},
        "estado": "EN_BASE",
        "carga": {"actual": 0, "capacidad": 20},
    }
    for r in registros:
        assert set(r) == {"tick", "agent_id", "tipo", "pose", "estado", "carga"}
        assert set(r["pose"]) == {"x", "y", "orientacion"}
        assert set(r["carga"]) == {"actual", "capacidad"}
        assert type(r["estado"]) is str  # .value, no el Enum
        assert r["pose"]["orientacion"] in ("N", "E", "S", "O")
        json.dumps(r)  # serializable tal cual
    assert registros[2]["pose"] == {"x": 2, "y": 0, "orientacion": "E"}
    assert registros[2]["estado"] == "ESPERANDO_TRANSFERENCIA"

    # Trace 2.2: con el combustible ya puesto por el mundo, se agrega redondeado a 2 decimales.
    carro.tanque, carro.combustible = 100.0, 87.456
    registro = carro.registro(3)
    assert set(registro) == {"tick", "agent_id", "tipo", "pose", "estado", "carga", "combustible"}
    assert registro["combustible"] == 87.46


# =========================================================== segunda entrega: carro contratista
#
# Los tipos de mensaje nuevos se usan como texto (el carro no depende de que el enum del buzón
# ya los tenga). Las cosechadoras son dobles mínimos: transfieren solo con su carro contratado.

SUBASTA = {"asignacion": "subasta"}
ESPERANDO = EstadoCarro.ESPERANDO_TRANSFERENCIA


def _manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


class CosechadoraFalsa:
    """Administradora mínima. `movimientos[t] = (posicion, estado)` la cambia al inicio del tick t.
    En LLENA_ESPERANDO, si su carro contratado está vecino y en ESPERANDO_TRANSFERENCIA, pasa a
    TRANSFIRIENDO; el tick siguiente mueve el grano y le entrega TRANSFERENCIA_TERMINADA."""

    def __init__(self, agent_id, posicion, carro_id, servicio, cantidad=4,
                 estado="LLENA_ESPERANDO", movimientos=None):
        self.agent_id, self.posicion, self.estado = agent_id, posicion, estado
        self.carro_id, self.servicio, self.cantidad = carro_id, servicio, cantidad
        self.movimientos = movimientos or {}
        self.carga = cantidad
        self.transferido_en = None

    def paso(self, tick, mundo, buzon):
        if tick in self.movimientos:
            self.posicion, self.estado = self.movimientos[tick]
        carro = mundo._agentes[self.carro_id]
        if self.estado == "TRANSFIRIENDO":
            assert _manhattan(carro.posicion, self.posicion) == 1, "el carro se fue a media transferencia"
            carro.carga += self.cantidad
            self.carga = 0
            payload = {"cantidad": self.cantidad}
            if self.servicio is not None:
                payload["servicio"] = self.servicio
            buzon.entregar(Mensaje(TipoMensaje.TRANSFERENCIA_TERMINADA, self.agent_id, self.carro_id, tick, payload))
            self.transferido_en = tick
            self.estado = "FIN"  # ya no se mueve (salvo que `movimientos` diga otra cosa)
        elif (self.estado == "LLENA_ESPERANDO" and self.transferido_en is None
              and carro.estado == ESPERANDO and _manhattan(carro.posicion, self.posicion) == 1):
            self.estado = "TRANSFIRIENDO"


def solicitud(servicio, cosechadora, celda, carga=4, capacidad=4, receptor="carro_1"):
    payload = {"servicio": servicio, "x": celda[0], "y": celda[1], "carga": carga, "capacidad": capacidad}
    return Mensaje(SOLICITUD_SERVICIO, cosechadora, receptor, 0, payload)


def aceptacion(servicio, cosechadora, receptor="carro_1"):
    return Mensaje(ACEPTACION, cosechadora, receptor, 0, {"servicio": servicio})


def contratar(buzon, cosechadora_falsa):
    """La subasta ya decidida: llamada y adjudicación de ese servicio a su carro."""
    c = cosechadora_falsa
    buzon.entregar(solicitud(c.servicio, c.agent_id, c.posicion, c.cantidad, c.cantidad, c.carro_id))
    buzon.entregar(aceptacion(c.servicio, c.agent_id, c.carro_id))


def simular(mundo, buzon, cosechadoras, carros, hasta, guion=None, parar=None):
    """Ticks 1..hasta en el orden del §3: cosechadoras y luego carros. Devuelve, por tick
    (empezando en 0), {agent_id: (posicion, estado)}."""
    guion = guion or {}

    def foto():
        return {a.agent_id: (a.posicion, getattr(a.estado, "value", a.estado)) for a in [*cosechadoras, *carros]}

    historia = [foto()]
    for t in range(1, hasta + 1):
        mundo.nuevo_tick(t)
        if t in guion:
            guion[t]()
        for agente in [*cosechadoras, *carros]:
            agente.paso(t, mundo, buzon)
        historia.append(foto())
        if parar is not None and parar():
            break
    return historia


def verificar_sin_colisiones(historia, obstaculos=frozenset()):
    """R3 (nadie comparte celda), R4 (ningún intercambio) y R10 (nadie en un obstáculo)."""
    for t, foto in enumerate(historia):
        posiciones = [pos for pos, _ in foto.values()]
        assert len(posiciones) == len(set(posiciones)), f"colisión en el tick {t}: {foto}"
        assert not set(posiciones) & set(obstaculos), f"en un obstáculo en el tick {t}"
        if t:
            antes = historia[t - 1]
            for a in foto:
                for b in foto:
                    if a < b:
                        assert not (foto[a][0] == antes[b][0] and foto[b][0] == antes[a][0]), \
                            f"intercambio {a} <-> {b} en el tick {t}"
            for a, (pos, _) in foto.items():
                assert _manhattan(pos, antes[a][0]) <= 1, f"{a} saltó en el tick {t}"


def preparar_subasta(politica=None, capacidad=20, ancho=4, alto=3):
    mundo = MundoFalso(ancho=ancho, alto=alto, politica={**SUBASTA, **(politica or {})})
    buzon = BuzonFalso()
    carro = Carro("carro_1", capacidad=capacidad)
    mundo.registrar(carro)
    return mundo, buzon, carro


def test_subasta_propone_con_estimar_costo_y_rechaza():
    """cfp -> propose con el costo de rutas.estimar_costo; refuse por capacidad o combustible."""
    mundo, buzon, carro = preparar_subasta()
    mundo.registrar(AgenteFalso("cosechadora_1", None, "COSECHANDO"))
    mundo._agentes["cosechadora_1"].posicion = POS_COSECHADORA
    buzon.entregar(solicitud("cosechadora_1#1", "cosechadora_1", POS_COSECHADORA, carga=3))
    carro.paso(1, mundo, buzon)

    (propuesta,) = buzon.enviados
    assert (propuesta.tipo, propuesta.emisor, propuesta.receptor) == (PROPUESTA, "carro_1", "cosechadora_1")
    costo = rutas.estimar_costo(BASE_CARRO, 0, POS_COSECHADORA, 4, 3, set())
    assert propuesta.payload == {"servicio": "cosechadora_1#1", "costo": costo} and costo == 1
    # Ofertar no es ganar: sigue en su base y sin servicios.
    assert carro.estado == EstadoCarro.EN_BASE and not carro.servicios

    # reject-proposal: lo olvida y nunca sale.
    buzon.entregar(Mensaje(RECHAZO_PROPUESTA, "cosechadora_1", "carro_1", 1, {"servicio": "cosechadora_1#1"}))
    for t in range(2, 8):
        carro.paso(t, mundo, buzon)
        assert carro.estado == EstadoCarro.EN_BASE
    assert not carro.servicios

    # Nunca le cabría: refuse sin_capacidad.
    buzon.entregar(solicitud("cosechadora_1#2", "cosechadora_1", POS_COSECHADORA, carga=30, capacidad=30))
    carro.paso(8, mundo, buzon)
    assert buzon.enviados[-1].tipo == RECHAZO
    assert buzon.enviados[-1].payload == {"servicio": "cosechadora_1#2", "motivo": "sin_capacidad"}

    # Sin combustible para ir, transferir, descargar y volver sin bajar de la reserva: refuse
    # combustible, con su RESTRICCION.
    carro.tanque, carro.combustible = 10.0, 3.0
    buzon.entregar(solicitud("cosechadora_1#3", "cosechadora_1", POS_COSECHADORA))
    carro.paso(9, mundo, buzon)
    assert buzon.enviados[-1].payload == {"servicio": "cosechadora_1#3", "motivo": "combustible"}
    assert mundo.restricciones == [(0, "carro_1", "combustible_reserva")]

    # Con el tanque lleno ya no rechaza por combustible aunque el viaje no alcance (agregado al
    # integrar la cosechadora): si no, en un mapa grande la cosechadora llamaría para siempre.
    carro.tanque, carro.combustible = 3.0, 3.0
    buzon.entregar(solicitud("cosechadora_1#4", "cosechadora_1", POS_COSECHADORA))
    carro.paso(10, mundo, buzon)
    assert buzon.enviados[-1].tipo == PROPUESTA


def test_subasta_costo_cuenta_la_fila():
    """El costo suma lo que le falta de su fila (traslados, transferencias y descargas, §7)."""
    # Mapa 4 x 3. Ya ganó un servicio en (2, 1) (capacidad 4) y llega una llamada desde (3, 2).
    #   fila: 1 paso + ceil(4/2) transferir + 3 a la bodega + ceil(4/2) descargar + 1 a su base = 9
    #   de su base (1, 0) a una vecina de (3, 2): 3 pasos -> 12
    casos = [({}, 12),
             # encadenar: le cabe, va directo de (2, 1): 1 + 2 = 3 ocupado + 1 paso -> 4
             ({"encadenar_servicios": True}, 4),
             # desde la bodega: 1 + 2 + 3 + 2 = 8 ocupado + 4 pasos desde (0, 0) -> 12
             ({"atender_desde_bodega": True}, 12)]
    for politica, esperado in casos:
        mundo, buzon, carro = preparar_subasta(politica)
        buzon.entregar(solicitud("cosechadora_1#1", "cosechadora_1", POS_COSECHADORA))
        buzon.entregar(aceptacion("cosechadora_1#1", "cosechadora_1"))
        buzon.entregar(solicitud("cosechadora_2#1", "cosechadora_2", (3, 2)))
        carro.paso(1, mundo, buzon)
        assert [m.payload["costo"] for m in buzon.enviados] == [1, esperado], politica
        assert [s["servicio"] for s in carro.servicios] == ["cosechadora_1#1"]


def dos_servicios(politica, capacidad):
    """Mapa 5 x 4; dos cosechadoras llenas esperando, las dos contratan a carro_1 en el tick 1."""
    bases = {"carro_1": (1, 0), "cosechadora_1": (2, 0), "cosechadora_2": (3, 0)}
    mundo = MundoFalso(ancho=5, alto=4, politica={**SUBASTA, **politica}, bases=bases)
    buzon = BuzonFalso()
    carro = Carro("carro_1", capacidad=capacidad)
    mundo.registrar(carro)
    c1 = CosechadoraFalsa("cosechadora_1", (1, 2), "carro_1", "cosechadora_1#1")
    c2 = CosechadoraFalsa("cosechadora_2", (3, 2), "carro_1", "cosechadora_2#1")
    for c in (c1, c2):
        mundo._agentes[c.agent_id] = c
    guion = {1: lambda: (contratar(buzon, c1), contratar(buzon, c2))}
    seguimiento = []  # (estado, cosechadora de su primer servicio) en cada tick

    def parar():
        seguimiento.append((carro.estado, carro.servicios[0]["cosechadora"] if carro.servicios else None))
        return (c2.transferido_en is not None and carro.estado == EstadoCarro.EN_BASE and not carro.servicios)

    historia = simular(mundo, buzon, [c1, c2], [carro], 80, guion, parar)
    assert parar(), "no terminó"
    return mundo, carro, c1, c2, historia, seguimiento


def _compactar(estados):
    """Quita repeticiones consecutivas: la secuencia de estados por la que pasó."""
    return [e for i, e in enumerate(estados) if i == 0 or e != estados[i - 1]]


def test_subasta_dos_servicios_en_orden_fifo():
    """Con dos servicios en fila los atiende en orden; solo espera junto a la cosechadora del
    servicio que está atendiendo (nunca transfiere uno que no ganó)."""
    mundo, carro, c1, c2, historia, seguimiento = dos_servicios({}, capacidad=4)
    assert c1.transferido_en < c2.transferido_en
    assert [cantidad for _, cantidad in mundo.depositos] == [4, 4]
    for (estado, cosechadora), foto in zip(seguimiento, historia[1:]):
        if estado == ESPERANDO:
            assert _manhattan(foto["carro_1"][0], foto[cosechadora][0]) == 1
    estados = _compactar([foto["carro_1"][1] for foto in historia])
    assert estados == [
        "EN_BASE", "YENDO_A_COSECHADORA", "ESPERANDO_TRANSFERENCIA", "YENDO_A_BODEGA", "DESCARGANDO",
        "REGRESANDO_A_BASE", "EN_BASE",  # sin atender_desde_bodega, regresa antes del segundo
        "YENDO_A_COSECHADORA", "ESPERANDO_TRANSFERENCIA", "YENDO_A_BODEGA", "DESCARGANDO",
        "REGRESANDO_A_BASE", "EN_BASE",
    ]
    verificar_sin_colisiones(historia)
    assert mundo.bloqueos == []


def test_subasta_encadenar_servicios():
    """encadenar_servicios: si le cabe, atiende los dos antes de ir a la bodega (un solo depósito)."""
    mundo, carro, c1, c2, historia, _ = dos_servicios({"encadenar_servicios": True}, capacidad=20)
    assert mundo.depositos and [cantidad for _, cantidad in mundo.depositos] == [8]
    estados = _compactar([foto["carro_1"][1] for foto in historia])
    assert estados == [
        "EN_BASE", "YENDO_A_COSECHADORA", "ESPERANDO_TRANSFERENCIA",
        "YENDO_A_COSECHADORA", "ESPERANDO_TRANSFERENCIA",  # directo a la segunda
        "YENDO_A_BODEGA", "DESCARGANDO", "REGRESANDO_A_BASE", "EN_BASE",
    ]
    verificar_sin_colisiones(historia)

    # Si no le cabe (capacidad 4), va a la bodega entre los dos aunque pueda encadenar.
    mundo, *_ = dos_servicios({"encadenar_servicios": True}, capacidad=4)
    assert [cantidad for _, cantidad in mundo.depositos] == [4, 4]


def test_subasta_atender_desde_bodega():
    """atender_desde_bodega: de la bodega va directo al siguiente servicio, sin pasar por su base."""
    mundo, carro, c1, c2, historia, _ = dos_servicios({"atender_desde_bodega": True}, capacidad=4)
    estados = _compactar([foto["carro_1"][1] for foto in historia])
    assert estados == [
        "EN_BASE", "YENDO_A_COSECHADORA", "ESPERANDO_TRANSFERENCIA", "YENDO_A_BODEGA", "DESCARGANDO",
        "YENDO_A_COSECHADORA", "ESPERANDO_TRANSFERENCIA", "YENDO_A_BODEGA", "DESCARGANDO",
        "REGRESANDO_A_BASE", "EN_BASE",
    ]
    assert [cantidad for _, cantidad in mundo.depositos] == [4, 4]


def test_subasta_acompana_a_la_cosechadora():
    """Despacho anticipado: va a la posición ACTUAL de la cosechadora y la sigue mientras cosecha;
    nunca se para en su siguiente celda; transfiere cuando ella se llena (§6)."""
    mundo, buzon, carro = preparar_subasta(ancho=6, alto=3)
    movimientos = {4: ((3, 1), "COSECHANDO"), 5: ((4, 1), "COSECHANDO"), 6: ((4, 1), "LLENA_ESPERANDO")}
    cosechadora = CosechadoraFalsa("cosechadora_1", (2, 1), "carro_1", "cosechadora_1#1",
                                   estado="COSECHANDO", movimientos=movimientos)
    mundo._agentes["cosechadora_1"] = cosechadora
    historia = simular(mundo, buzon, [cosechadora], [carro], 8, {1: lambda: contratar(buzon, cosechadora)})

    carro_pos = [foto["carro_1"][0] for foto in historia]
    assert carro_pos[:7] == [(1, 0), (1, 0), (2, 0), (2, 0), (3, 0), (4, 0), (4, 0)]
    serpentina = mundo.camino_serpentina()
    for foto in historia[2:7]:
        pos_cos = foto["cosechadora_1"][0]
        siguiente = serpentina[serpentina.index(pos_cos) + 1]
        assert _manhattan(foto["carro_1"][0], pos_cos) == 1  # siempre a su lado
        assert foto["carro_1"][0] != siguiente  # sin taparle el camino
    assert cosechadora.transferido_en == 7
    assert carro.estado == EstadoCarro.YENDO_A_BODEGA and carro.carga == 4
    verificar_sin_colisiones(historia)


def pasillo(politica, hueco=2):
    """Escenario tipo E en chico: mapa 5 x 5, muro en y = 2 con un hueco en x = `hueco`. Cada
    carro atiende a la cosechadora del otro lado, así que se cruzan por el hueco dos veces.

          x=0  x=1  x=2  x=3  x=4
      y=0 Bod  K1   K2   B    B
      y=1  .    .    .    .    .
      y=2  #    #    _    #    #        (hueco = 2)
      y=3  .    .    .    .    .
      y=4  .   C1    .   C2    .
    """
    obstaculos = {(x, 2) for x in range(5) if x != hueco}
    bases = {"carro_1": (1, 0), "carro_2": (2, 0), "cosechadora_1": (3, 0), "cosechadora_2": (4, 0)}
    mundo = MundoFalso(ancho=5, alto=5, politica=politica, num_carros=2, bases=bases, obstaculos=obstaculos)
    buzon = BuzonFalso()
    carros = [Carro("carro_1", capacidad=20), Carro("carro_2", capacidad=20)]
    for carro in carros:
        mundo.registrar(carro)
    servicio = politica["asignacion"] == "subasta"
    c1 = CosechadoraFalsa("cosechadora_1", (1, 4), "carro_2", "cosechadora_1#1" if servicio else None)
    c2 = CosechadoraFalsa("cosechadora_2", (3, 4), "carro_1", "cosechadora_2#1" if servicio else None)
    for c in (c1, c2):
        mundo._agentes[c.agent_id] = c

    def avisar():
        for c in (c1, c2):
            if servicio:
                contratar(buzon, c)
            else:
                buzon.entregar(Mensaje(TipoMensaje.LLENA, c.agent_id, c.carro_id, 0,
                                       {"x": c.posicion[0], "y": c.posicion[1], "carga": c.cantidad}))

    def parar():
        return (len(mundo.depositos) == 2
                and all(k.estado == EstadoCarro.EN_BASE and not k.servicios for k in carros))

    historia = simular(mundo, buzon, [c1, c2], carros, 120, {1: avisar}, parar)
    return mundo, carros, historia, obstaculos, parar()


def test_pasillo_dos_carros_sin_colisiones_ni_bloqueos():
    """Rutas en el tiempo: dos carros por un hueco de 1 celda, 0 colisiones, 0 intercambios y
    0 BLOQUEO, en subasta y en directa con varios carros (estrategia base del escenario E)."""
    politicas = (SUBASTA, {"asignacion": "directa"}, {**SUBASTA, "atender_desde_bodega": True},
                 {**SUBASTA, "encadenar_servicios": True})
    for politica in politicas:
        for hueco in (2, 4):
            mundo, carros, historia, obstaculos, termino = pasillo(politica, hueco)
            caso = (politica, hueco)
            assert termino, f"no terminó: {caso}"
            assert sorted(c for _, c in mundo.depositos) == [4, 4], caso
            verificar_sin_colisiones(historia, obstaculos)
            assert mundo.bloqueos == [], caso
            assert mundo.pisadas == [], caso  # nadie tuvo que desalojar a nadie

            # Uno de los dos tuvo que ceder el paso (R3 o R4), y cada restricción se registra
            # una vez por desvío, no en cada tick.
            reglas = {regla for _, _, regla in mundo.restricciones}
            assert reglas & {"R3_celda_ocupada", "R4_intercambio"}, caso
            vistas = {(t, a, r) for t, a, r in mundo.restricciones}
            assert not any((t + 1, a, r) in vistas for t, a, r in vistas), caso
            # Con el hueco en una orilla (x = 4) el muro alarga las rutas de los dos: R10.
            if hueco == 4:
                assert {a for _, a, r in mundo.restricciones if r == "R10_obstaculo"} == {"carro_1", "carro_2"}


def test_va_a_recargar_si_no_le_alcanza():
    """§9: con un servicio ganado y poco combustible, se queda en su base hasta recargar
    (una sola RESTRICCION combustible_reserva) y luego sale."""
    mundo, buzon, carro = preparar_subasta()
    carro.tanque, carro.combustible = 10.0, 2.0
    carro.servicios.append({"servicio": "cosechadora_1#1", "cosechadora": "cosechadora_1",
                            "x": 2, "y": 1, "carga": 4, "capacidad": 4})
    for t in range(1, 4):
        carro.paso(t, mundo, buzon)
        assert carro.estado == EstadoCarro.EN_BASE
    assert [r for _, _, r in mundo.restricciones] == ["combustible_reserva"]
    carro.combustible = 10.0  # el mundo lo recargó en la base
    carro.paso(4, mundo, buzon)
    assert carro.estado == EstadoCarro.YENDO_A_COSECHADORA

    # Modo directa: el LLENA se guarda hasta tener el tanque lleno.
    mundo, buzon, _, carro = preparar()
    carro.tanque, carro.combustible = 10.0, 2.0
    mundo.combustible_para = lambda agent_id, celdas, ticks: celdas + ticks * 0.5
    mundo.registrar_restriccion = lambda *args: None
    mundo.config.tasa_transferencia = 2
    buzon.entregar(llena(*POS_COSECHADORA))
    for t in range(1, 4):
        carro.paso(t, mundo, buzon)
        assert carro.estado == EstadoCarro.EN_BASE
    carro.combustible = 10.0
    carro.paso(4, mundo, buzon)
    assert carro.estado == EstadoCarro.YENDO_A_COSECHADORA
