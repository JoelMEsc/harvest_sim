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
from harvest_sim.carro import Carro, EstadoCarro
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
    """Lo mínimo del contrato de Mundo (§10) que usa el carro, con la misma lógica que el real."""

    bodega = BODEGA

    def __init__(self, ancho=4, alto=3, tasa_descarga=2):
        self.ancho, self.alto = ancho, alto
        self.config = SimpleNamespace(tasa_descarga=tasa_descarga)
        self._bases = {"carro_1": BASE_CARRO, "cosechadora_1": (2, 0)}
        self._agentes = {}
        self.bloqueos = []  # ticks en que se llamó registrar_bloqueo
        self.depositos = []  # (tick, cantidad)
        self.tick = 0

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
        return {self.bodega} if agent_id.startswith("cosechadora_") else set()

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
        assert agent_id == "carro_1"
        self.bloqueos.append(self.tick)


class BuzonFalso:
    """Filas FIFO por agente. `entregar` simula que el mensaje llegó a la fila."""

    def __init__(self):
        self._filas = defaultdict(deque)

    def entregar(self, mensaje):
        self._filas[mensaje.receptor].append(mensaje)

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
