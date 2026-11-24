"""Mundo: layout, serpentina y movimiento de grano (R5-R9).  [Dueño: Ilan, escritos desde la especificación]

Estos tests los escribe quien NO implementa el mundo, a partir de la especificación.
Activos desde la integración del 17 de noviembre.
"""

from dataclasses import dataclass, field
import pytest


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
        {"tipo": "CELDA_COSECHADA", "celda": [1, 1], "agente": "cosechadora_1", "cantidad": 1},
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


# ---------------------------------------------------------------------------------------------------
# Segunda entrega: franjas, obstáculos, reservas, azar, rendimiento, duraciones y combustible
# ---------------------------------------------------------------------------------------------------

from pathlib import Path  # noqa: E402

CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"


def mundo_de(nombre=None, **cambios):
    """Mundo de un escenario de config/ o de la configuración de prueba con cambios."""
    from dataclasses import replace
    from harvest_sim.config import cargar_config
    from harvest_sim.mundo import Mundo

    config = cargar_config(CONFIG_DIR / f"{nombre}.json") if nombre else crear_config()
    return Mundo(replace(config, **cambios) if cambios else config)


@pytest.mark.parametrize("nombre,tamanos", [("escenario_d", [40, 30]), ("escenario_e", [28, 27]),
                                             ("escenario_f", None)])
def test_franjas(nombre, tamanos):
    """Las franjas cubren cada celda libre del campo una sola vez, sin obstáculos, con filas contiguas
    y tamaños lo más parejos posible (D: 40/30; E: 28/27, calculados a mano en el plan)."""
    from harvest_sim.datos.campo import celdas_de_campo

    mundo = mundo_de(nombre)
    caminos = [mundo.camino(f"cosechadora_{j}") for j in range(1, mundo.config.num_cosechadoras + 1)]
    todas = [c for camino in caminos for c in camino]
    assert len(todas) == len(set(todas))
    assert set(todas) == celdas_de_campo(mundo.descripcion())
    assert not set(todas) & mundo.obstaculos
    for filas in mundo.franjas():
        assert filas == list(range(filas[0], filas[-1] + 1))
    if tamanos:
        assert [len(c) for c in caminos] == tamanos


def test_una_franja_es_la_serpentina_de_v0_1():
    mundo = mundo_de()
    esperado = []
    for y in range(1, mundo.alto):
        columnas = range(mundo.ancho) if y % 2 else range(mundo.ancho - 1, -1, -1)
        esperado.extend((x, y) for x in columnas)
    assert mundo.camino_serpentina() == mundo.camino("cosechadora_1") == esperado


def test_obstaculos_bloqueados_para_todos():
    mundo = mundo_de("escenario_e")
    assert (0, 3) in mundo.bloqueadas_fijas("carro_1")
    assert (0, 0) in mundo.bloqueadas_fijas("cosechadora_1") and (0, 0) not in mundo.bloqueadas_fijas("carro_1")
    ruta = mundo.ruta_bfs((1, 2), (1, 4), set())
    assert (4, 3) in ruta and not set(ruta) & mundo.obstaculos  # cruza por el hueco


def test_reservar_reemplaza_las_futuras_y_reservas_excepto():
    mundo = mundo_de()
    mundo.reservar("carro_1", [((1, 0), 5), ((1, 1), 6), ((1, 2), 7)])
    mundo.reservar("carro_1", [((1, 1), 6), ((2, 1), 7)])  # desde el tick 6
    mundo.reservar("cosechadora_1", [((3, 3), 6)])
    assert mundo.reservas(excepto="cosechadora_1") == {((1, 0), 5): "carro_1", ((1, 1), 6): "carro_1",
                                                       ((2, 1), 7): "carro_1"}
    assert mundo.reservas(excepto="carro_1") == {((3, 3), 6): "cosechadora_1"}
    mundo.reservar("cosechadora_1", [((2, 1), 7)])  # ya es del carro: gana quien reservó primero
    assert mundo.reservas()[((2, 1), 7)] == "carro_1"


def test_nuevo_tick_olvida_las_reservas_pasadas():
    mundo = mundo_de()
    mundo.reservar("carro_1", [((1, 0), 5), ((1, 1), 6)])
    mundo.nuevo_tick(6)
    assert mundo.reservas() == {((1, 1), 6): "carro_1"}


def test_azar_reproducible_por_fuente():
    a, b = mundo_de(), mundo_de()
    secuencia = [a.azar("duracion").random() for _ in range(3)]
    b.azar("otra_fuente").random()  # usar otra fuente no cambia esta
    assert [b.azar("duracion").random() for _ in range(3)] == secuencia
    assert a.azar("duracion") is a.azar("duracion")


def test_rendimiento_fijo_no_usa_el_generador():
    mundo = mundo_de()
    assert "rendimiento" not in mundo._azar
    assert mundo.rendimiento((1, 1)) == 1 and mundo.rendimiento((0, 0)) == 0
    assert "rendimiento" not in mundo.descripcion()


def test_rendimiento_sorteado_reproducible_y_en_la_descripcion():
    incertidumbre = {"rendimiento": {"minimo": 1, "maximo": 3}, "duracion_extra_maxima": 0,
                     "retraso_mensajes": {"probabilidad": 0.0, "maximo": 0}}
    a, b = mundo_de(incertidumbre=incertidumbre), mundo_de(incertidumbre=incertidumbre)
    matriz = a.descripcion()["rendimiento"]
    assert matriz == b.descripcion()["rendimiento"]
    assert matriz[0] == [0] * a.ancho  # fila de servicio
    assert {v for fila in matriz[1:] for v in fila} <= {1, 2, 3}
    assert a.grano_total == sum(map(sum, matriz))


def test_cosechar_usa_el_rendimiento():
    incertidumbre = {"rendimiento": {"minimo": 2, "maximo": 2}, "duracion_extra_maxima": 0,
                     "retraso_mensajes": {"probabilidad": 0.0, "maximo": 0}}
    from harvest_sim.mundo import Mundo
    from dataclasses import replace
    mundo = Mundo(replace(crear_config(), incertidumbre=incertidumbre))
    cosechadora = DummyAgente("cosechadora_1", capacidad=10)
    mundo.registrar(cosechadora)
    cosechadora.posicion = (1, 1)
    assert mundo.cosechar("cosechadora_1", (1, 1)) == 2 and cosechadora.carga == 2
    assert mundo.drenar_eventos()[0]["cantidad"] == 2
    assert mundo.grano_cosechado() == 2
    assert "rendimiento" in mundo.descripcion()  # 2 != grano_por_celda


def test_duracion_sin_y_con_extra():
    mundo = mundo_de()
    assert mundo.duracion(5, 2) == 3 and "duracion" not in mundo._azar
    incertidumbre = {"rendimiento": {"minimo": 1, "maximo": 1}, "duracion_extra_maxima": 2,
                     "retraso_mensajes": {"probabilidad": 0.0, "maximo": 0}}
    con_extra = mundo_de(incertidumbre=incertidumbre)
    valores = {con_extra.duracion(5, 2) for _ in range(50)}
    assert valores <= {3, 4, 5} and len(valores) > 1


def _combustible(**cambios):
    from harvest_sim.config import COMBUSTIBLE_POR_DEFECTO
    return {**COMBUSTIBLE_POR_DEFECTO, "tanque_carro": 10, "tanque_cosechadora": 20, **cambios}


def test_combustible_consumo_y_recarga_solo_en_base():
    mundo = mundo_de(combustible=_combustible())
    carro = DummyAgente("carro_1")
    mundo.registrar(carro)
    assert (carro.tanque, carro.combustible) == (10.0, 10.0)
    carro.estado, carro.posicion = "YENDO_A_BODEGA", (1, 1)
    mundo.actualizar_combustible(carro, se_movio=True)           # -1.0 por celda
    carro.estado = "DESCARGANDO"
    mundo.actualizar_combustible(carro, se_movio=False)          # -0.5 encendido
    assert carro.combustible == 8.5
    carro.estado = "EN_BASE"                                     # fuera de su base: no recarga
    mundo.actualizar_combustible(carro, se_movio=False)
    assert carro.combustible == 8.5 and mundo.drenar_eventos() == []
    carro.posicion = mundo.base_de("carro_1")                    # en su base y apagado: recarga todo
    mundo.actualizar_combustible(carro, se_movio=False)
    assert carro.combustible == 10.0
    assert mundo.drenar_eventos() == [{"tipo": "RECARGA", "agente": "carro_1", "cantidad": 1.5, "nivel": 10.0}]


def test_recarga_a_tasa_por_tick():
    mundo = mundo_de(combustible=_combustible(tasa_recarga=1))
    carro = DummyAgente("carro_1")
    mundo.registrar(carro)
    carro.combustible = 7.5
    mundo.actualizar_combustible(carro, se_movio=False)
    assert carro.combustible == 8.5
    assert mundo.drenar_eventos()[0]["cantidad"] == 1


def test_combustible_nunca_negativo():
    mundo = mundo_de(combustible=_combustible())
    cosechadora = DummyAgente("cosechadora_1", estado="COSECHANDO")
    mundo.registrar(cosechadora)
    cosechadora.combustible, cosechadora.posicion = 1.0, (1, 1)
    mundo.actualizar_combustible(cosechadora, se_movio=True)    # gastaría 2.0
    assert cosechadora.combustible == 0.0


def test_combustible_para():
    mundo = mundo_de()
    assert mundo.combustible_para("carro_1", 10, 4) == 10 * 1.0 + 4 * 0.5
    assert mundo.combustible_para("cosechadora_1", 3, 0) == 6.0


def test_restriccion_registrada_y_regla_validada():
    mundo = mundo_de()
    mundo.registrar(DummyAgente("carro_1"))
    mundo.registrar_restriccion("carro_1", "R3_celda_ocupada", "esperó a cosechadora_1")
    assert mundo.drenar_eventos() == [{"tipo": "RESTRICCION", "agente": "carro_1", "regla": "R3_celda_ocupada",
                                       "detalle": "esperó a cosechadora_1"}]
    with pytest.raises(ValueError, match="regla desconocida"):
        mundo.registrar_restriccion("carro_1", "R99", "x")
