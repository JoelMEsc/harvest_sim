"""Máquina de estados de la cosechadora (§5.1).  [Dueño: Emilio]

Usa un Mundo y un Buzon falsos (clases mínimas en el propio test) para no depender de los demás.
"""

from collections import deque
from types import SimpleNamespace

import pytest

import harvest_sim.cosechadora as modulo_cosechadora
from harvest_sim.cosechadora import Cosechadora, EstadoCosechadora
from harvest_sim.mensajes import TipoMensaje


class BuzonFalso:
    def __init__(self):
        self.enviados = []

    def enviar(self, mensaje):
        mensaje.id = len(self.enviados) + 1
        self.enviados.append(mensaje)
        return mensaje.id


class MundoFalso:
    def __init__(self, agente, celdas=3, tasa=2):
        self.agente = agente
        self.ancho = max(3, celdas)
        self.alto = 3
        self.bodega = (0, 0)
        self.config = SimpleNamespace(tasa_transferencia=tasa)

        self.base = (2, 0)
        self.camino = [(x, 1) for x in range(celdas)]
        self.cosechadas = set()
        self.bloqueos = []

        self.carro_posicion = (1, 0)
        self.carro_estado = "EN_BASE"
        self.carro_carga = 0
        self.carro_capacidad = agente.capacidad * 2

        agente.posicion = self.base

    def base_de(self, agent_id):
        return self.base

    def camino_serpentina(self):
        return list(self.camino)

    def posicion(self, agent_id):
        if agent_id == self.agente.agent_id:
            return self.agente.posicion
        return self.carro_posicion

    def estado_de(self, agent_id):
        if agent_id == self.agente.agent_id:
            return self.agente.estado.value
        return self.carro_estado

    def ocupadas(self, excepto):
        return {self.carro_posicion}

    def bloqueadas_fijas(self, agent_id):
        return {self.bodega}

    def vecinos(self, celda):
        x, y = celda

        return [
            (nx, ny)
            for nx, ny in (
                (x, y - 1),
                (x + 1, y),
                (x, y + 1),
                (x - 1, y),
            )
            if 0 <= nx < self.ancho and 0 <= ny < self.alto
        ]

    def ruta_bfs(self, origen, destino, bloqueadas):
        if origen == destino:
            return []

        cola = deque([(origen, [])])
        visitadas = {origen}

        while cola:
            celda, ruta = cola.popleft()

            for vecina in self.vecinos(celda):
                if vecina in bloqueadas or vecina in visitadas:
                    continue

                nueva_ruta = ruta + [vecina]

                if vecina == destino:
                    return nueva_ruta

                visitadas.add(vecina)
                cola.append((vecina, nueva_ruta))

        return None

    def cosechar(self, agent_id, celda):
        assert celda == self.agente.posicion
        assert celda in self.camino
        assert celda not in self.cosechadas
        assert self.agente.carga < self.agente.capacidad

        self.cosechadas.add(celda)
        self.agente.carga += 1
        return 1

    def transferir(self, de, a, cantidad):
        assert self.carro_posicion in self.vecinos(self.agente.posicion)

        transferida = min(
            cantidad,
            self.agente.carga,
            self.carro_capacidad - self.carro_carga,
        )

        self.agente.carga -= transferida
        self.carro_carga += transferida
        return transferida

    def registrar_bloqueo(self, agent_id):
        self.bloqueos.append(agent_id)

    def preparar_carro(self):
        # Sitúa el carro junto a la cosechadora, fuera de la fila cosechable.
        x, y = self.agente.posicion
        self.carro_posicion = (x, y + 1)
        self.carro_estado = "ESPERANDO_TRANSFERENCIA"
        self.carro_carga = 0


@pytest.fixture(autouse=True)
def sustituir_duracion_pendiente(monkeypatch):
    # Doble de la función de Carlos mientras no esté implementada.
    def duracion_falsa(cantidad, tasa):
        return max(1, (cantidad + tasa - 1) // tasa)

    monkeypatch.setattr(
        modulo_cosechadora,
        "duracion_ticks",
        duracion_falsa,
    )


def crear_caso(capacidad=2, celdas=3, tasa=2):
    agente = Cosechadora("cosechadora_1", capacidad)
    mundo = MundoFalso(agente, celdas=celdas, tasa=tasa)
    buzon = BuzonFalso()
    return agente, mundo, buzon


def avanzar_hasta(agente, mundo, buzon, estado, desde=1):
    for tick in range(desde, desde + 100):
        agente.paso(tick, mundo, buzon)

        if agente.estado == estado:
            return tick

    pytest.fail(f"No se alcanzó el estado {estado.value}.")


def test_cosechadora_ciclo_completo_de_estados():
    """EN_BASE -> YENDO_A_CAMPO -> COSECHANDO -> LLENA_ESPERANDO -> TRANSFIRIENDO ->
    COSECHANDO ... -> REGRESANDO_A_BASE -> FIN, con las condiciones del §5.1."""
    agente, mundo, buzon = crear_caso()
    estados = [agente.estado]

    for tick in range(1, 100):
        if agente.estado == EstadoCosechadora.LLENA_ESPERANDO:
            mundo.preparar_carro()

        posicion_anterior = agente.posicion
        agente.paso(tick, mundo, buzon)

        distancia = (
            abs(agente.posicion[0] - posicion_anterior[0])
            + abs(agente.posicion[1] - posicion_anterior[1])
        )

        assert distancia <= 1
        assert agente.posicion != mundo.bodega
        assert agente.posicion != mundo.carro_posicion
        assert len(mundo.cosechadas) == agente.carga + sum(
            mensaje.payload["cantidad"]
            for mensaje in buzon.enviados
            if mensaje.tipo == TipoMensaje.TRANSFERENCIA_TERMINADA
        )

        if agente.estado != estados[-1]:
            estados.append(agente.estado)

        if agente.estado == EstadoCosechadora.FIN:
            break
    else:
        pytest.fail("La cosechadora no terminó.")

    assert estados == [
        EstadoCosechadora.EN_BASE,
        EstadoCosechadora.YENDO_A_CAMPO,
        EstadoCosechadora.COSECHANDO,
        EstadoCosechadora.LLENA_ESPERANDO,
        EstadoCosechadora.TRANSFIRIENDO,
        EstadoCosechadora.COSECHANDO,
        EstadoCosechadora.LLENA_ESPERANDO,
        EstadoCosechadora.TRANSFIRIENDO,
        EstadoCosechadora.REGRESANDO_A_BASE,
        EstadoCosechadora.FIN,
    ]

    assert agente.posicion == mundo.base
    assert agente.carga == 0
    assert mundo.cosechadas == set(mundo.camino)

    mensajes_antes = len(buzon.enviados)
    agente.paso(tick + 1, mundo, buzon)

    assert agente.estado == EstadoCosechadora.FIN
    assert agente.posicion == mundo.base
    assert len(buzon.enviados) == mensajes_antes


@pytest.mark.parametrize("celdas", [2, 3])
def test_envia_llena_al_llenarse(celdas):
    """Al llegar carga == capacidad envía LLENA con x, y, carga y pasa a LLENA_ESPERANDO."""
    agente, mundo, buzon = crear_caso(capacidad=2, celdas=celdas)

    tick = avanzar_hasta(
        agente, mundo, buzon, EstadoCosechadora.LLENA_ESPERANDO
    )

    assert agente.carga == 2
    assert len(buzon.enviados) == 1

    mensaje = buzon.enviados[0]
    assert mensaje.tipo == TipoMensaje.LLENA
    assert mensaje.emisor == agente.agent_id
    assert mensaje.receptor == "carro_1"
    assert mensaje.tick_envio == tick
    assert mensaje.payload == {"x": 1, "y": 1, "carga": 2}

    # Seguir esperando no debe repetir la solicitud.
    agente.paso(tick + 1, mundo, buzon)
    assert len(buzon.enviados) == 1


def test_carga_parcial_final():
    """Si el campo no es múltiplo de la capacidad, la última carga parcial también envía LLENA."""
    agente, mundo, buzon = crear_caso(capacidad=5, celdas=3)

    avanzar_hasta(
        agente, mundo, buzon, EstadoCosechadora.LLENA_ESPERANDO
    )

    assert agente.carga == 3
    assert mundo.cosechadas == set(mundo.camino)
    assert len(buzon.enviados) == 1
    assert buzon.enviados[0].payload["carga"] == 3


def test_transferencia_no_se_activa_si_el_carro_solo_pasa():
    """Carro vecino que NO está en ESPERANDO_TRANSFERENCIA no dispara la transferencia (R5)."""
    agente, mundo, buzon = crear_caso()

    tick = avanzar_hasta(
        agente, mundo, buzon, EstadoCosechadora.LLENA_ESPERANDO
    )

    mundo.preparar_carro()
    mundo.carro_estado = "YENDO_A_BODEGA"

    agente.paso(tick + 1, mundo, buzon)
    assert agente.estado == EstadoCosechadora.LLENA_ESPERANDO

    # Estar listo tampoco basta si el carro está lejos.
    mundo.carro_estado = "ESPERANDO_TRANSFERENCIA"
    mundo.carro_posicion = (2, 2)

    agente.paso(tick + 2, mundo, buzon)
    assert agente.estado == EstadoCosechadora.LLENA_ESPERANDO

    mundo.preparar_carro()
    agente.paso(tick + 3, mundo, buzon)

    assert agente.estado == EstadoCosechadora.TRANSFIRIENDO
    assert agente.carga == 2
    assert mundo.carro_carga == 0


@pytest.mark.parametrize(
    "cantidad,tasa,snapshots_esperados",
    [(1, 4, 1), (3, 2, 2), (5, 2, 3)],
)
def test_duracion_de_transferencia_depende_de_la_cantidad(
    cantidad, tasa, snapshots_esperados
):
    """ceil(cantidad / tasa_transferencia) snapshots en TRANSFIRIENDO."""
    agente, mundo, buzon = crear_caso(
        capacidad=cantidad + 1,
        celdas=cantidad,
        tasa=tasa,
    )

    tick = avanzar_hasta(
        agente, mundo, buzon, EstadoCosechadora.LLENA_ESPERANDO
    )

    mundo.preparar_carro()

    for desplazamiento in range(1, snapshots_esperados + 1):
        agente.paso(tick + desplazamiento, mundo, buzon)

        assert agente.registro(tick + desplazamiento)["estado"] == (
            "TRANSFIRIENDO"
        )
        assert agente.carga == cantidad
        assert mundo.carro_carga == 0

    agente.paso(tick + snapshots_esperados + 1, mundo, buzon)

    assert agente.estado == EstadoCosechadora.REGRESANDO_A_BASE
    assert agente.carga == 0
    assert mundo.carro_carga == cantidad


def test_cantidad_en_mensaje_de_fin_de_transferencia():
    """TRANSFERENCIA_TERMINADA lleva `cantidad` igual a lo cedido (incluida la carga parcial)."""
    agente, mundo, buzon = crear_caso(capacidad=5, celdas=3)

    tick = avanzar_hasta(
        agente, mundo, buzon, EstadoCosechadora.LLENA_ESPERANDO
    )

    carga_antes = agente.carga
    mundo.preparar_carro()

    tick_final = avanzar_hasta(
        agente,
        mundo,
        buzon,
        EstadoCosechadora.REGRESANDO_A_BASE,
        desde=tick + 1,
    )

    mensajes = [
        mensaje
        for mensaje in buzon.enviados
        if mensaje.tipo == TipoMensaje.TRANSFERENCIA_TERMINADA
    ]

    assert len(mensajes) == 1
    assert mensajes[0].tick_envio == tick_final
    assert mensajes[0].payload == {"cantidad": 3}
    assert mensajes[0].payload["cantidad"] == carga_antes - agente.carga
    assert mensajes[0].payload["cantidad"] == mundo.carro_carga


def test_espera_si_la_siguiente_celda_esta_ocupada():
    """§4.2: no recalcula la serpentina; espera un tick y registra un bloqueo."""
    agente, mundo, buzon = crear_caso(capacidad=5, celdas=3)

    tick = avanzar_hasta(
        agente, mundo, buzon, EstadoCosechadora.COSECHANDO
    )

    mundo.carro_posicion = (1, 1)
    posicion_antes = agente.posicion
    carga_antes = agente.carga

    agente.paso(tick + 1, mundo, buzon)

    assert agente.posicion == posicion_antes
    assert agente.carga == carga_antes
    assert agente.estado == EstadoCosechadora.COSECHANDO
    assert mundo.bloqueos == [agente.agent_id]
    assert (1, 1) not in mundo.cosechadas

    mundo.carro_posicion = (1, 0)
    agente.paso(tick + 2, mundo, buzon)

    assert agente.posicion == (1, 1)
    assert agente.carga == carga_antes + 1
    assert mundo.bloqueos == [agente.agent_id]


def test_cosechadora_registro():
    """registro() trae tick, agent_id, tipo, pose, estado y carga, sin checksum."""
    agente, mundo, buzon = crear_caso()

    assert agente.registro(0) == {
        "tick": 0,
        "agent_id": "cosechadora_1",
        "tipo": "cosechadora",
        "pose": {
            "x": 2,
            "y": 0,
            "orientacion": "S",
        },
        "estado": "EN_BASE",
        "carga": {
            "actual": 0,
            "capacidad": 2,
        },
    }

    tick = avanzar_hasta(
        agente, mundo, buzon, EstadoCosechadora.LLENA_ESPERANDO
    )

    registro = agente.registro(tick)

    assert registro["pose"] == {
        "x": 1,
        "y": 1,
        "orientacion": "E",
    }
    assert registro["estado"] == "LLENA_ESPERANDO"
    assert registro["carga"] == {"actual": 2, "capacidad": 2}