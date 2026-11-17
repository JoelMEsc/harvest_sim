"""Mundo: layout, serpentina y movimiento de grano (R5-R9).  [Dueño: Ilan, escritos desde la especificación]

Estos tests los escribe quien NO implementa el mundo, a partir de la especificación.
Se marcan `skip` hasta que `mundo.py` entre a development; entonces se quita el decorador.
"""

from dataclasses import dataclass, field
import pytest

pendiente = pytest.mark.skip(reason="pendiente — espera mundo.py (Carlos)")

class DummyAgente:
    """Doble de prueba para aislar el Mundo de la implementación de los agentes."""
    def __init__(self, agent_id: str, capacidad: int = 20, carga: int = 0, estado: str = "EN_BASE"):
        self.agent_id = agent_id
        self.capacidad = capacidad
        self.carga = carga
        self.estado = estado
        self.posicion = (0, 0)

def crear_config(
    ancho: int = 8,
    alto: int = 7,
    num_carros: int = 1,
    num_cosechadoras: int = 1,
    grano_por_celda: int = 1,
    capacidad_cosechadora: int = 10,
    capacidad_carro: int = 20,
    tasa_transferencia: int = 2,
    tasa_descarga: int = 4,
    max_ticks: int = 5000,
):
    from harvest_sim.config import Config
    try:
        return Config(
            nombre="test",
            seed=0,
            ancho=ancho,
            alto=alto,
            num_carros=num_carros,
            num_cosechadoras=num_cosechadoras,
            grano_por_celda=grano_por_celda,
            capacidad_cosechadora=capacidad_cosechadora,
            capacidad_carro=capacidad_carro,
            tasa_transferencia=tasa_transferencia,
            tasa_descarga=tasa_descarga,
            max_ticks=max_ticks,
            obstaculos={"celdas": [], "regiones": []},
        )
    except TypeError:
        return Config(
            nombre="test",
            seed=0,
            ancho=ancho,
            alto=alto,
            num_carros=num_carros,
            num_cosechadoras=num_cosechadoras,
            grano_por_celda=grano_por_celda,
            capacidad_cosechadora=capacidad_cosechadora,
            capacidad_carro=capacidad_carro,
            tasa_transferencia=tasa_transferencia,
            tasa_descarga=tasa_descarga,
            max_ticks=max_ticks,
        )


@pendiente
def test_casillas_de_inicio():
    """Bodega (0,0); bases de carros (1..n,0); de cosechadoras (n+1..n+m,0), con n y m genéricos."""
    from harvest_sim.mundo import Mundo

    # Escenario base: n=1, m=1
    config_base = crear_config(ancho=8, alto=7, num_carros=1, num_cosechadoras=1)
    mundo = Mundo(config_base)
    assert mundo.bodega == (0, 0)
    assert mundo.base_de("carro_1") == (1, 0)
    assert mundo.base_de("cosechadora_1") == (2, 0)

    # Caso genérico: n=2 carros, m=3 cosechadoras (ancho >= 1+2+3 = 6)
    config_gen = crear_config(ancho=10, alto=7, num_carros=2, num_cosechadoras=3)
    mundo_gen = Mundo(config_gen)
    assert mundo_gen.bodega == (0, 0)
    assert mundo_gen.base_de("carro_1") == (1, 0)
    assert mundo_gen.base_de("carro_2") == (2, 0)
    assert mundo_gen.base_de("cosechadora_1") == (3, 0)
    assert mundo_gen.base_de("cosechadora_2") == (4, 0)
    assert mundo_gen.base_de("cosechadora_3") == (5, 0)


@pendiente
def test_serpentina_cubre_todo_el_campo():
    """El camino visita cada celda del campo (y >= 1) exactamente una vez; empieza en (0,1)."""
    from harvest_sim.mundo import Mundo

    ancho, alto = 8, 7
    config = crear_config(ancho=ancho, alto=alto)
    mundo = Mundo(config)
    camino = mundo.camino_serpentina()

    assert camino[0] == (0, 1), "El camino serpentina debe iniciar en (0, 1)"
    celdas_esperadas = {(x, y) for y in range(1, alto) for x in range(ancho)}
    assert set(camino) == celdas_esperadas, "Debe visitar todas las celdas con y >= 1"
    assert len(camino) == len(celdas_esperadas), "No debe haber celdas repetidas en el camino"

def test_serpentina_alterna_direccion():
    """Fila 1 de izquierda a derecha, fila 2 de derecha a izquierda, etc."""
    from harvest_sim.mundo import Mundo

    ancho, alto = 6, 5
    config = crear_config(ancho=ancho, alto=alto)
    mundo = Mundo(config)
    camino = mundo.camino_serpentina()

    for idx, y in enumerate(range(1, alto)):
        tramo_fila = camino[idx * ancho : (idx + 1) * ancho]
        if y % 2 != 0:  # Fila impar (1, 3, ...): izquierda a derecha
            assert tramo_fila == [(x, y) for x in range(ancho)]
        else:           # Fila par (2, 4, ...): derecha a izquierda
            assert tramo_fila == [(x, y) for x in range(ancho - 1, -1, -1)]

def test_transferencia_solo_entre_vecinos():
    """R5: transferir con agentes no vecinos falla."""
    from harvest_sim.mundo import Mundo

    config = crear_config()
    mundo = Mundo(config)
    cosechadora = DummyAgente("cosechadora_1", capacidad=10, carga=10)
    carro = DummyAgente("carro_1", capacidad=20, carga=0)
    mundo.registrar(cosechadora)
    mundo.registrar(carro)

    # Caso lejanos (distancia Manhattan > 1)
    cosechadora.posicion = (2, 2)
    carro.posicion = (5, 5)
    with pytest.raises(ValueError, match="vecinos"):
        mundo.transferir("cosechadora_1", "carro_1", 5)

    # Caso diagonales (distancia Manhattan = 2)
    carro.posicion = (3, 3)
    with pytest.raises(ValueError, match="vecinos"):
        mundo.transferir("cosechadora_1", "carro_1", 5)

def test_transferencia_respeta_capacidad():
    """R6: δ = min(q_cosechadora, Q_carro - q_carro); incluir caso con capacidad libre < carga."""
    from harvest_sim.mundo import Mundo

    config = crear_config()
    mundo = Mundo(config)
    cosechadora = DummyAgente("cosechadora_1", capacidad=10, carga=10)
    carro = DummyAgente("carro_1", capacidad=20, carga=0)
    mundo.registrar(cosechadora)
    mundo.registrar(carro)

    # Posicionados como vecinos (4-vecindad)
    cosechadora.posicion = (2, 2)
    carro.posicion = (2, 3)

    # Caso 1: Capacidad libre del carro suficiente
    delta = mundo.transferir("cosechadora_1", "carro_1", 10)
    assert delta == 10
    assert cosechadora.carga == 0
    assert carro.carga == 10

    # Caso 2: Capacidad libre menor que la carga a transferir
    cosechadora.carga = 8
    carro.capacidad = 10
    carro.carga = 7  # Espacio libre = 3
    delta = mundo.transferir("cosechadora_1", "carro_1", 8)
    assert delta == 3
    assert cosechadora.carga == 5
    assert carro.carga == 10

def test_celda_cosechada_una_vez():
    """R8: cosechar dos veces la misma celda no produce grano la segunda vez (o falla)."""
    from harvest_sim.mundo import Mundo

    config = crear_config(grano_por_celda=1)
    mundo = Mundo(config)
    cosechadora = DummyAgente("cosechadora_1", capacidad=10, carga=0)
    mundo.registrar(cosechadora)

    celda = (0, 1)
    cosechadora.posicion = celda

    # Primera cosecha: exitosa
    grano = mundo.cosechar("cosechadora_1", celda)
    assert grano == config.grano_por_celda
    assert mundo.grano_cosechado() == config.grano_por_celda

    # Segunda cosecha de la misma celda: debe fallar con error
    with pytest.raises(ValueError, match="cosechada"):
        mundo.cosechar("cosechadora_1", celda)

def test_cosechadora_no_entra_a_bodega():
    """R9: bloqueadas_fijas de una cosechadora incluye (0,0); la del carro no."""
    from harvest_sim.mundo import Mundo

    config = crear_config()
    mundo = Mundo(config)
    cosechadora = DummyAgente("cosechadora_1")
    carro = DummyAgente("carro_1")
    mundo.registrar(cosechadora)
    mundo.registrar(carro)

    assert (0, 0) in mundo.bloqueadas_fijas("cosechadora_1")
    assert (0, 0) not in mundo.bloqueadas_fijas("carro_1")

def test_deposito_actualiza_entregado():
    """depositar() mueve la carga del carro a `entregado` y deja su carga en 0."""
    from harvest_sim.mundo import Mundo

    config = crear_config()
    mundo = Mundo(config)
    carro = DummyAgente("carro_1", capacidad=20, carga=15)
    mundo.registrar(carro)

    assert mundo.entregado == 0

    # Depositar fuera de bodega debe fallar
    carro.posicion = (1, 1)
    with pytest.raises(ValueError, match="bodega"):
        mundo.depositar("carro_1")

    # Depositar en la bodega (0, 0)
    carro.posicion = (0, 0)
    depositado = mundo.depositar("carro_1")
    assert depositado == 15
    assert carro.carga == 0
    assert mundo.entregado == 15

def test_duracion_ticks():
    """ceil(cantidad / tasa), mínimo 1: (10,2)->5, (3,2)->2, (1,4)->1."""
    from harvest_sim.mundo import duracion_ticks

    assert duracion_ticks(10, 2) == 5
    assert duracion_ticks(3, 2) == 2
    assert duracion_ticks(1, 4) == 1
    assert duracion_ticks(0, 2) == 1  # Duración mínima de 1 tick

def test_cosechar_registra_cambio():
    """cosechar agrega {tipo: CELDA_COSECHADA, celda, agente}; depositar agrega
    {tipo: DEPOSITO, agente, cantidad, entregado_total}; drenar_eventos vacía la lista."""
    from harvest_sim.mundo import Mundo

    config = crear_config()
    mundo = Mundo(config)
    cosechadora = DummyAgente("cosechadora_1", capacidad=10, carga=0)
    carro = DummyAgente("carro_1", capacidad=20, carga=0)
    mundo.registrar(cosechadora)
    mundo.registrar(carro)

    # 1. Cosechar una celda
    cosechadora.posicion = (1, 1)
    mundo.cosechar("cosechadora_1", (1, 1))

    # 2. Depositar grano en la bodega
    carro.posicion = (0, 0)
    carro.carga = 10
    mundo.depositar("carro_1")

    # 3. Drenar eventos acumulados
    eventos = mundo.drenar_eventos()
    assert eventos == [
        {"tipo": "CELDA_COSECHADA", "celda": [1, 1], "agente": "cosechadora_1"},
        {"tipo": "DEPOSITO", "agente": "carro_1", "cantidad": 10, "entregado_total": 10},
    ]

    # 4. Segunda llamada a drenar_eventos debe devolver lista vacía
    assert mundo.drenar_eventos() == []

def test_registrar_bloqueo():
    """registrar_bloqueo registra {tipo: BLOQUEO, agente: id} y drenar_eventos lo vacía."""
    from harvest_sim.mundo import Mundo

    config = crear_config()
    mundo = Mundo(config)
    carro = DummyAgente("carro_1")
    mundo.registrar(carro)

    mundo.registrar_bloqueo("carro_1")
    eventos = mundo.drenar_eventos()
    assert eventos == [{"tipo": "BLOQUEO", "agente": "carro_1"}]
    assert mundo.drenar_eventos() == []

def test_descripcion_del_mundo():
    """descripcion() trae ancho, alto, bodega, bases (con listas, no tuplas), grano_por_celda y obstaculos."""
    from harvest_sim.mundo import Mundo

    config = crear_config(ancho=8, alto=7, grano_por_celda=1)
    mundo = Mundo(config)
    desc = mundo.descripcion()

    assert desc["ancho"] == 8
    assert desc["alto"] == 7
    assert desc["bodega"] == [0, 0]
    assert isinstance(desc["bodega"], list)
    assert desc["bases"] == {"carro_1": [1, 0], "cosechadora_1": [2, 0]}
    assert isinstance(desc["bases"]["carro_1"], list)
    assert isinstance(desc["bases"]["cosechadora_1"], list)
    assert desc["grano_por_celda"] == 1
    assert desc["obstaculos"] == []
