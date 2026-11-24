"""Cosechadora de la segunda entrega: franja, subasta (Contract Net), obstáculos y combustible.  [Dueño: Emilio]

Usan el Mundo y el Buzon reales con carros falsos (DummyCarro): así se prueba la cosechadora sola, con la
API del mundo de verdad, sin depender del carro.
"""

from dataclasses import replace

import pytest

from harvest_sim.config import COMBUSTIBLE_POR_DEFECTO, POLITICA_POR_DEFECTO, Config
from harvest_sim.cosechadora import Cosechadora, EstadoCosechadora
from harvest_sim.mensajes import Buzon, Mensaje, TipoMensaje
from harvest_sim.mundo import Mundo


class DummyCarro:
    def __init__(self, agent_id, capacidad=40):
        self.agent_id, self.capacidad, self.carga = agent_id, capacidad, 0
        self.estado, self.posicion = "EN_BASE", None


def preparar(capacidad=10, politica=None, combustible=None, obstaculos=None, ancho=10, alto=4, carros=2):
    config = Config(nombre="t", seed=0, ancho=ancho, alto=alto, num_carros=carros, num_cosechadoras=1,
                    grano_por_celda=1, capacidad_cosechadora=capacidad, capacidad_carro=40,
                    tasa_transferencia=2, tasa_descarga=4, max_ticks=500,
                    obstaculos=obstaculos or {"celdas": [], "regiones": []},
                    politica={**POLITICA_POR_DEFECTO, **(politica or {})},
                    combustible={**COMBUSTIBLE_POR_DEFECTO, **(combustible or {})})
    mundo, buzon = Mundo(config), Buzon()
    cosechadora = Cosechadora("cosechadora_1", capacidad)
    mundo.registrar(cosechadora)
    carros = [DummyCarro(f"carro_{i}") for i in range(1, carros + 1)]
    for carro in carros:
        mundo.registrar(carro)
    return mundo, buzon, cosechadora, carros


def correr(cosechadora, mundo, buzon, hasta, desde=1, alto_en=None):
    """Avanza ticks (entregando mensajes como la simulación) hasta `hasta` o hasta que alto_en(tick) sea verdad."""
    for tick in range(desde, hasta + 1):
        mundo.nuevo_tick(tick)
        buzon.entregar(tick)
        cosechadora.paso(tick, mundo, buzon)
        if alto_en and alto_en(tick):
            return tick
    return hasta


def enviados(buzon, tipo):
    return [e for e in buzon.drenar_eventos() if e["tipo"] == "MENSAJE_ENVIADO" and e["tipo_mensaje"] == tipo]


SUBASTA = {"asignacion": "subasta"}


def test_llamada_al_llegar_al_umbral_y_sigue_cosechando():
    """Con umbral 0.7 y capacidad 10, la llamada sale a las 7 unidades, a cada carro, y sigue cosechando."""
    mundo, buzon, cosechadora, _ = preparar(politica={**SUBASTA, "umbral_aviso": 0.7})
    tick = correr(cosechadora, mundo, buzon, 60, alto_en=lambda t: cosechadora.servicio is not None)
    eventos = buzon.drenar_eventos()
    llamadas = [e for e in eventos if e.get("tipo_mensaje") == "SOLICITUD_SERVICIO"]
    assert cosechadora.carga == 7
    assert [e["a"] for e in llamadas] == ["carro_1", "carro_2"]
    assert all(e["performativa"] == "cfp" for e in llamadas)
    assert llamadas[0]["payload"] == {"servicio": "cosechadora_1#1", "x": cosechadora.posicion[0],
                                      "y": cosechadora.posicion[1], "carga": 7, "capacidad": 10}
    correr(cosechadora, mundo, buzon, tick + 1, desde=tick + 1)
    assert cosechadora.estado == EstadoCosechadora.COSECHANDO and cosechadora.carga == 8  # despacho anticipado


def _proponer(buzon, tick, ofertas, servicio="cosechadora_1#1"):
    for carro, costo in ofertas.items():
        buzon.enviar(Mensaje(tipo=TipoMensaje.PROPUESTA, emisor=carro, receptor="cosechadora_1",
                             tick_envio=tick, payload={"servicio": servicio, "costo": costo}))


@pytest.mark.parametrize("ofertas,ganador", [({"carro_1": 9, "carro_2": 4}, "carro_2"),
                                             ({"carro_2": 5, "carro_1": 5}, "carro_1")])  # empate: menor id
def test_gana_el_menor_costo_y_los_demas_reciben_rechazo(ofertas, ganador):
    mundo, buzon, cosechadora, _ = preparar(politica=SUBASTA)
    llamada = correr(cosechadora, mundo, buzon, 80, alto_en=lambda t: cosechadora.servicio is not None)
    buzon.drenar_eventos()
    _proponer(buzon, llamada + 1, ofertas)
    correr(cosechadora, mundo, buzon, llamada + 2, desde=llamada + 1)  # espera_propuestas = 2
    eventos = [e for e in buzon.drenar_eventos() if e["tipo"] == "MENSAJE_ENVIADO" and e["de"] == "cosechadora_1"]
    assert cosechadora.contratado == ganador
    assert [(e["tipo_mensaje"], e["a"]) for e in eventos] == [
        ("ACEPTACION", ganador), ("RECHAZO_PROPUESTA", next(c for c in ofertas if c != ganador))]


def test_sin_propuestas_reintenta_con_un_servicio_nuevo():
    mundo, buzon, cosechadora, _ = preparar(politica={**SUBASTA, "reintento_subasta": 3})
    llamada = correr(cosechadora, mundo, buzon, 80, alto_en=lambda t: cosechadora.servicio is not None)
    buzon.drenar_eventos()
    decision = llamada + 2
    correr(cosechadora, mundo, buzon, decision, desde=llamada + 1)
    assert cosechadora.servicio is None
    correr(cosechadora, mundo, buzon, decision + 3, desde=decision + 1)
    llamadas = [e for e in buzon.drenar_eventos() if e.get("tipo_mensaje") == "SOLICITUD_SERVICIO"]
    assert {e["payload"]["servicio"] for e in llamadas} == {"cosechadora_1#2"}


def test_la_espera_cuenta_el_retraso_de_ida_y_vuelta():
    mundo, buzon, cosechadora, _ = preparar(politica=SUBASTA)
    mundo = Mundo(replace(mundo.config, incertidumbre={**mundo.config.incertidumbre,
                                                       "retraso_mensajes": {"probabilidad": 0.5, "maximo": 2}}))
    assert Cosechadora._retraso_maximo(mundo) == 2  # la decisión espera 2 + 2·2 ticks


def test_no_transfiere_con_un_carro_no_contratado():
    mundo, buzon, cosechadora, carros = preparar(politica=SUBASTA, capacidad=3)
    llamada = correr(cosechadora, mundo, buzon, 80, alto_en=lambda t: cosechadora.servicio is not None)
    _proponer(buzon, llamada + 1, {"carro_1": 3})
    correr(cosechadora, mundo, buzon, llamada + 2, desde=llamada + 1)
    assert cosechadora.contratado == "carro_1" and cosechadora.estado == EstadoCosechadora.LLENA_ESPERANDO
    x, y = cosechadora.posicion
    carros[1].posicion, carros[1].estado = (x, y + 1), "ESPERANDO_TRANSFERENCIA"  # carro_2: vecino y listo
    correr(cosechadora, mundo, buzon, llamada + 5, desde=llamada + 3)
    assert cosechadora.estado == EstadoCosechadora.LLENA_ESPERANDO
    carros[1].posicion = (9, 3)
    carros[0].posicion, carros[0].estado = (x, y + 1), "ESPERANDO_TRANSFERENCIA"  # ahora el contratado
    correr(cosechadora, mundo, buzon, llamada + 6, desde=llamada + 6)
    assert cosechadora.estado == EstadoCosechadora.TRANSFIRIENDO


def test_se_traslada_sin_cosechar_alrededor_de_un_obstaculo():
    """Fila 2 con un obstáculo en x=2: la serpentina salta de (3,2) a (1,2) sin cosechar en el camino."""
    mundo, buzon, cosechadora, _ = preparar(capacidad=40, ancho=6, alto=3, carros=1,
                                            obstaculos={"celdas": [[2, 2]], "regiones": []})
    camino = mundo.camino("cosechadora_1")
    assert (3, 2) in camino and camino[camino.index((3, 2)) + 1] == (1, 2)
    estados = []
    correr(cosechadora, mundo, buzon, 60, alto_en=lambda t: estados.append(cosechadora.estado) or
           cosechadora.estado == EstadoCosechadora.LLENA_ESPERANDO)
    assert mundo.grano_cosechado() == len(camino)
    assert all(c != (2, 2) for c in mundo._cosechadas)
    i = estados.index(EstadoCosechadora.YENDO_A_CAMPO, 2)  # el segundo tramo de traslado (el salto)
    assert EstadoCosechadora.COSECHANDO in estados[i:]


def test_va_a_recargar_cuando_no_le_alcanza_y_vuelve():
    """Tanque chico: tras transferir, si la siguiente carga y el regreso no caben en la reserva, registra
    RESTRICCION combustible_reserva, vuelve a su base, recarga y regresa a la siguiente celda del camino."""
    mundo, buzon, cosechadora, carros = preparar(capacidad=4, carros=1, ancho=12, alto=4,
                                                 combustible={"tanque_cosechadora": 30, "reserva": 0.15})
    carro = carros[0]

    def junto_a_la_cosechadora(tick):
        if cosechadora.estado in (EstadoCosechadora.LLENA_ESPERANDO, EstadoCosechadora.TRANSFIRIENDO):
            if cosechadora.estado == EstadoCosechadora.LLENA_ESPERANDO:
                x, y = cosechadora.posicion
                carro.posicion = (x, y + 1) if y + 1 < mundo.alto else (x, y - 1)
                carro.estado = "ESPERANDO_TRANSFERENCIA"
        else:
            carro.posicion, carro.estado, carro.carga = (1, 0), "EN_BASE", 0
        return False

    restricciones, siguiente = [], None
    for tick in range(1, 400):
        mundo.nuevo_tick(tick)
        buzon.entregar(tick)
        junto_a_la_cosechadora(tick)
        antes = cosechadora.posicion
        cosechadora.paso(tick, mundo, buzon)
        mundo.actualizar_combustible(cosechadora, cosechadora.posicion != antes)
        eventos = mundo.drenar_eventos()
        restricciones += [e for e in eventos if e["tipo"] == "RESTRICCION"]
        if restricciones and siguiente is None:
            siguiente = cosechadora._camino[cosechadora._siguiente]
        if siguiente and cosechadora.estado == EstadoCosechadora.COSECHANDO and cosechadora._recargando is False \
                and cosechadora.posicion == siguiente:
            break
    else:
        pytest.fail("no volvió a cosechar después de recargar")
    assert restricciones[0]["regla"] == "combustible_reserva"
    assert cosechadora.combustible > 0


def test_en_fin_vacia_su_buzon():
    """Un mensaje viejo que llega cuando ya terminó se lee y se descarta: si no, hay_pendientes nunca baja."""
    mundo, buzon, cosechadora, _ = preparar(politica=SUBASTA)
    cosechadora.estado = EstadoCosechadora.FIN
    _proponer(buzon, 5, {"carro_1": 3}, servicio="cosechadora_1#9")
    correr(cosechadora, mundo, buzon, 6, desde=6)
    assert not buzon.hay_pendientes("cosechadora_1")


def test_directa_con_varios_carros_avisa_a_su_carro_asignado():
    """Modo directa: cosechadora j -> carro ((j − 1) mod n) + 1; con LLENA como en v0.1."""
    mundo, buzon, cosechadora, _ = preparar(capacidad=3)
    correr(cosechadora, mundo, buzon, 60, alto_en=lambda t: cosechadora.estado == EstadoCosechadora.LLENA_ESPERANDO)
    llenas = [e for e in buzon.drenar_eventos() if e.get("tipo_mensaje") == "LLENA"]
    assert [(e["a"], e["performativa"]) for e in llenas] == [("carro_1", "request")]
