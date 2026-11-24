"""Buzón y mensajes.  [Dueño: Emilio]"""

import pytest

import logging

from harvest_sim.mensajes import Buzon, Mensaje, TipoMensaje


def test_fifo():
    """La fila de entrada respeta el orden de llegada."""
    buzon = Buzon()

    for carga in (3, 6, 9):
        buzon.enviar(Mensaje(
            tipo=TipoMensaje.LLENA,
            emisor="cosechadora_1",
            receptor="carro_1",
            tick_envio=0,
            payload={"x": 2, "y": 1, "carga": carga},
        ))

    buzon.entregar(1)

    # Los mensajes permanecen disponibles aunque el carro no los lea aún.
    buzon.entregar(2)

    for carga_esperada in (3, 6, 9):
        mensaje = buzon.leer("carro_1")
        assert mensaje is not None
        assert mensaje.payload["carga"] == carga_esperada

    assert buzon.leer("carro_1") is None
    assert buzon.leer("agente_sin_mensajes") is None


def test_ids_de_mensaje():
    """Los id son únicos y crecientes (1, 2, 3, ...) y aparecen en los eventos."""
    buzon = Buzon()
    ids = []

    for receptor in ("carro_1", "carro_2", "carro_1"):
        mensaje = Mensaje(
            tipo=TipoMensaje.LLENA,
            emisor="cosechadora_1",
            receptor=receptor,
            tick_envio=0,
            payload={"x": 2, "y": 1, "carga": 5},
        )

        identificador = buzon.enviar(mensaje)
        ids.append(identificador)

        assert mensaje.id == identificador

    assert ids == [1, 2, 3]

    eventos = buzon.drenar_eventos()
    assert [evento["id"] for evento in eventos] == [1, 2, 3]

    buzon.entregar(1)

    # Cada receptor tiene su propia fila.
    primero = buzon.leer("carro_1")
    segundo = buzon.leer("carro_1")
    otro_receptor = buzon.leer("carro_2")

    assert primero is not None
    assert segundo is not None
    assert otro_receptor is not None

    assert [primero.id, segundo.id] == [1, 3]
    assert otro_receptor.id == 2


def test_mensaje_se_lee_al_tick_siguiente():
    """Un mensaje enviado en t no es visible en t; sí en t+1."""
    buzon = Buzon()

    assert not buzon.hay_pendientes("carro_1")

    buzon.enviar(Mensaje(
        tipo=TipoMensaje.LLENA,
        emisor="cosechadora_1",
        receptor="carro_1",
        tick_envio=7,
        payload={"x": 3, "y": 1, "carga": 10},
    ))

    # Un mensaje en tránsito también cuenta como pendiente.
    assert buzon.hay_pendientes("carro_1")

    buzon.entregar(7)
    assert buzon.leer("carro_1") is None

    buzon.entregar(8)
    assert buzon.hay_pendientes("carro_1")

    # Repetir la entrega no debe duplicar el mensaje.
    buzon.entregar(8)

    mensaje = buzon.leer("carro_1")
    assert mensaje is not None
    assert mensaje.tipo == TipoMensaje.LLENA
    assert mensaje.tick_envio == 7

    assert buzon.leer("carro_1") is None
    assert not buzon.hay_pendientes("carro_1")


def test_eventos_de_mensajes_para_el_log():
    """drenar_eventos() devuelve envíos y entregas con el formato acordado."""
    buzon = Buzon()

    casos = [
        (
            TipoMensaje.LLENA,
            {"x": 3, "y": 1, "carga": 10},
            "request",
            7,
        ),
        (
            TipoMensaje.TRANSFERENCIA_TERMINADA,
            {"cantidad": 10},
            "inform",
            8,
        ),
    ]

    for identificador, (tipo, payload, performativa, tick) in enumerate(
        casos, start=1
    ):
        buzon.enviar(Mensaje(
            tipo=tipo,
            emisor="cosechadora_1",
            receptor="carro_1",
            tick_envio=tick,
            payload=payload,
        ))

        assert buzon.drenar_eventos() == [{
            "tipo": "MENSAJE_ENVIADO",
            "id": identificador,
            "tipo_mensaje": tipo.value,
            "performativa": performativa,
            "de": "cosechadora_1",
            "a": "carro_1",
            "payload": payload,
            "entrega_en": tick + 1,
        }]

        assert buzon.drenar_eventos() == []

        # Recoger los eventos no debe eliminar mensajes en tránsito.
        assert buzon.hay_pendientes("carro_1")

        buzon.entregar(tick + 1)

        assert buzon.drenar_eventos() == [{
            "tipo": "MENSAJE_ENTREGADO",
            "id": identificador,
            "a": "carro_1",
        }]

        assert buzon.drenar_eventos() == []

        # Tampoco debe eliminar mensajes ya entregados.
        recibido = buzon.leer("carro_1")
        assert recibido is not None
        assert recibido.id == identificador
        assert recibido.payload == payload


def test_log_de_consola_de_mensajes(caplog):
    """El Buzon emite un registro de log por cada envío y por cada entrega (§6.3)."""
    buzon = Buzon()

    with caplog.at_level(logging.INFO, logger="harvest_sim.mensajes"):
        buzon.enviar(Mensaje(
            tipo=TipoMensaje.LLENA,
            emisor="cosechadora_1",
            receptor="carro_1",
            tick_envio=14,
            payload={"x": 5, "y": 1, "carga": 10},
        ))

        buzon.entregar(15)

    mensajes_log = [
        registro.getMessage()
        for registro in caplog.records
        if registro.name == "harvest_sim.mensajes"
    ]

    assert mensajes_log == [
        "t=014 | MSG #1 LLENA cosechadora_1 -> carro_1 "
        "{x: 5, y: 1, carga: 10} (se entrega en t=015)",
        "t=015 | MSG #1 entregado a carro_1",
    ]

# ---------------------------------------------------------------------------------------------------
# Segunda entrega: tipos de la subasta y retraso aleatorio (§7 y §8)
# ---------------------------------------------------------------------------------------------------

import random  # noqa: E402

from harvest_sim.datos.formato import PERFORMATIVAS  # noqa: E402
from harvest_sim.mensajes import Buzon, Mensaje, TipoMensaje  # noqa: E402


def _mensaje(tick, receptor="carro_1", tipo=TipoMensaje.LLENA):
    return Mensaje(tipo=tipo, emisor="cosechadora_1", receptor=receptor, tick_envio=tick, payload={})


def test_los_siete_tipos_tienen_performativa():
    assert {t.value for t in TipoMensaje} == set(PERFORMATIVAS)
    assert PERFORMATIVAS[TipoMensaje.SOLICITUD_SERVICIO.value] == "cfp"
    assert PERFORMATIVAS[TipoMensaje.ACEPTACION.value] == "accept-proposal"


def test_sin_probabilidad_no_se_llama_al_generador():
    class AzarProhibido:
        def random(self):
            raise AssertionError("con probabilidad 0 no se llama al generador")
        randint = random

    buzon = Buzon(AzarProhibido(), 0.0, 3)
    buzon.enviar(_mensaje(4))
    assert buzon.drenar_eventos()[0]["entrega_en"] == 5


def test_retraso_dentro_del_rango_y_entrega_en_ese_tick():
    buzon = Buzon(random.Random(7), 1.0, 2)
    for tick in range(10):
        buzon.enviar(_mensaje(tick))
    eventos = buzon.drenar_eventos()
    entregas = {e["id"]: e["entrega_en"] for e in eventos}
    assert all(t + 2 <= entregas[i + 1] <= t + 3 for i, t in enumerate(range(10)))
    assert len(set(entregas.values())) > 1
    for tick in range(20):
        buzon.entregar(tick)
        for e in buzon.drenar_eventos():
            assert entregas[e["id"]] == tick  # se entrega exactamente en su entrega_en
    while buzon.leer("carro_1") is not None:
        pass
    assert not buzon.hay_pendientes("carro_1")


def test_maximo_cero_no_retrasa_aunque_haya_probabilidad():
    buzon = Buzon(random.Random(1), 1.0, 0)
    buzon.enviar(_mensaje(3))
    assert buzon.drenar_eventos()[0]["entrega_en"] == 4


def test_en_empate_se_entrega_por_id():
    buzon = Buzon()
    for receptor in ("carro_2", "carro_1", "carro_2"):
        buzon.enviar(_mensaje(1, receptor))
    buzon.drenar_eventos()
    buzon.entregar(2)
    assert [e["id"] for e in buzon.drenar_eventos()] == [1, 2, 3]
