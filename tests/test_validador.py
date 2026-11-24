"""Validador del trace (tarea 6 de Datos).  [Dueño: Joel]

Cada prueba altera una copia del fixture para romper UNA regla, vuelve a calcular los checksums (para
que el único error sea el buscado, salvo en la prueba del checksum) y comprueba que el validador lo
reporta con un mensaje que dice dónde está.
"""

import copy
import json

import pytest

from ayuda_datos import C, FIXTURE, H, cargar_script
from harvest_sim.datos import calcular_checksum, cargar_trace, validar_trace


@pytest.fixture(scope="module")
def base():
    return cargar_trace(FIXTURE)


def resellar(trace):
    for t in trace["ticks"]:
        t["checksum"] = calcular_checksum({"tick": t["tick"], "cambios": t["cambios"]})
    return trace


def tick(trace, numero):
    return next(t for t in trace["ticks"] if t["tick"] == numero)


def evento(trace, tipo, condicion=lambda e: True):
    """(tick, evento) del primer evento de ese tipo que cumpla la condición."""
    for t in trace["ticks"]:
        for e in t["cambios"]:
            if e["tipo"] == tipo and condicion(e):
                return t, e
    raise AssertionError(f"no hay evento {tipo} que cumpla la condición")


def errores_de(base, alterar, sellar=True):
    trace = copy.deepcopy(base)
    alterar(trace)
    return validar_trace(resellar(trace) if sellar else trace)


def contiene(errores, *fragmentos):
    return any(all(f in e for f in fragmentos) for e in errores)


# --- Trazas válidas ------------------------------------------------------------------------------
def test_el_fixture_es_valido(base):
    assert validar_trace(base) == []


def test_las_variantes_del_generador_son_validas():
    gen = cargar_script("tools/generar_trace_ejemplo.py")
    for cambios in ({}, dict(ancho=5, capacidad_cosechadora=4, capacidad_carro=8, tasa_transferencia=2),
                    dict(tasa_transferencia=2, tasa_descarga=3)):
        assert validar_trace(gen.generar(dict(gen.CONFIG, **cambios))) == [], cambios


def test_no_falla_con_entradas_que_no_son_un_trace():
    assert validar_trace([]) == ["el trace no es un objeto JSON"]
    assert validar_trace({}) != []


# --- Estructura ----------------------------------------------------------------------------------
def test_orden_de_las_claves_del_primer_nivel(base):
    def alterar(t):
        meta = t.pop("meta")
        t["meta"] = meta
    assert contiene(errores_de(base, alterar), "orden de las claves del primer nivel")


def test_version_del_esquema(base):
    def alterar(t):
        t["schema_version"] = "2.0"
    assert contiene(errores_de(base, alterar), "schema_version", "'2.0'", "'2.1'", "'2.2'")


def test_falta_un_dato_del_mundo(base):
    def alterar(t):
        del t["mundo"]["bodega"]
    assert contiene(errores_de(base, alterar), "mundo: falta bodega")


def test_clases_de_la_ontologia(base):
    def sin_clase_en_meta(t):
        del t["meta"]["clase"]

    def clase_de_agente_incorrecta(t):
        t["agentes"][1]["clase"] = "Robot"

    def sin_clase_de_celdas(t):
        del t["mundo"]["clase_celdas"]
    assert contiene(errores_de(base, sin_clase_en_meta), "meta: falta clase")
    assert contiene(errores_de(base, clase_de_agente_incorrecta), "agentes[1]", "'Robot'", "AutonomousAgriculturalRobot")
    assert contiene(errores_de(base, sin_clase_de_celdas), "mundo: falta clase_celdas")


def test_tipos_de_agente_del_catalogo(base):
    """El tipo de agente es libre (texto no vacío): un tipo nuevo no es error; uno vacío sí."""
    def tipo_nuevo(t):
        t["agentes"][1]["tipo"] = "dron"

    def tipo_vacio(t):
        t["agentes"][1]["tipo"] = ""
    assert errores_de(base, tipo_nuevo) == []
    assert contiene(errores_de(base, tipo_vacio), "agentes[1]", "tipo debe ser texto no vacío")


@pytest.mark.parametrize("obstaculos, fragmento", [
    ([[9, 1]], "fuera del mapa"),
    ([[1, 0]], "fila de servicio"),
    ([[1, 1], [1, 1]], "repetido"),
    ("ninguno", "lista de [x, y]"),
])
def test_obstaculos_del_mundo(base, obstaculos, fragmento):
    def alterar(t):
        t["mundo"]["obstaculos"] = obstaculos
    assert contiene(errores_de(base, alterar), "obstácul" if fragmento != "lista de [x, y]" else "obstaculos", fragmento)


def test_celda_cosechada_sobre_un_obstaculo(base):
    def alterar(t):
        _, e = evento(t, "CELDA_COSECHADA")
        t["mundo"]["obstaculos"] = [e["celda"]]
    assert contiene(errores_de(base, alterar), "es un obstáculo")


def test_agente_repetido_en_el_catalogo(base):
    def alterar(t):
        t["agentes"].append(copy.deepcopy(t["agentes"][0]))
    assert contiene(errores_de(base, alterar), "id repetido")


# --- Ticks ---------------------------------------------------------------------------------------
def test_checksum_alterado(base):
    def alterar(t):
        tick(t, 4)["cambios"][0]["set"]["carga"] = 0
    assert contiene(errores_de(base, alterar, sellar=False), "tick 4", "checksum")


def test_ticks_desordenados(base):
    def alterar(t):
        t["ticks"][3], t["ticks"][4] = t["ticks"][4], t["ticks"][3]
    assert contiene(errores_de(base, alterar), "estrictamente crecientes")


def test_falta_el_tick_0(base):
    def alterar(t):
        t["ticks"].pop(0)
    errores = errores_de(base, alterar)
    assert contiene(errores, "el primer tick debe ser el 0")


def test_tick_mayor_que_total_ticks(base):
    def alterar(t):
        t["meta"]["total_ticks"] = 30
    assert contiene(errores_de(base, alterar), "mayor que meta.total_ticks")


# --- Eventos -------------------------------------------------------------------------------------
def test_tipo_de_evento_desconocido(base):
    def alterar(t):
        tick(t, 4)["cambios"].append({"tipo": "INVENTADO"})
    assert contiene(errores_de(base, alterar), "tick 4", "tipo desconocido 'INVENTADO'")


def test_faltan_campos_en_un_evento(base):
    def alterar(t):
        _, e = evento(t, "DEPOSITO")
        del e["entregado_total"]
    assert contiene(errores_de(base, alterar), "(DEPOSITO)", "faltan campos ['entregado_total']")


def test_campos_extra_en_un_evento(base):
    def alterar(t):
        _, e = evento(t, "BLOQUEO")
        e["motivo"] = "celda ocupada"
    assert contiene(errores_de(base, alterar), "(BLOQUEO)", "campos no esperados ['motivo']")


def test_tipo_de_dato_incorrecto(base):
    def alterar(t):
        _, e = evento(t, "DEPOSITO")
        e["cantidad"] = "3"
    assert contiene(errores_de(base, alterar), "(DEPOSITO)", "tipo de dato incorrecto en ['cantidad']")


def test_eventos_fuera_de_orden_dentro_del_tick(base):
    def alterar(t):
        t_, _ = evento(t, "MENSAJE_ENTREGADO")
        t_["cambios"].reverse()  # el AGENTE queda antes de la entrega
    assert contiene(errores_de(base, alterar), "fuera de orden")


# --- Agentes -------------------------------------------------------------------------------------
def test_set_con_campos_no_permitidos(base):
    def alterar(t):
        _, e = evento(t, "AGENTE", lambda e: "pose" in e["set"])
        e["set"]["intencion"] = {"accion": "MOVER", "celdas": []}
    assert contiene(errores_de(base, alterar), "campos no permitidos en set ['intencion']")


def test_agente_fuera_del_catalogo(base):
    def alterar(t):
        _, e = evento(t, "BLOQUEO")
        e["agente"] = "tractor_9"
    assert contiene(errores_de(base, alterar), "'tractor_9' no está en el catálogo")


def test_tick_0_incompleto(base):
    def alterar(t):
        del tick(t, 0)["cambios"][1]["set"]["carga"]
    assert contiene(errores_de(base, alterar), "tick 0", "carro_1", "le faltan ['carga']")


def test_orientacion_invalida(base):
    def alterar(t):
        _, e = evento(t, "AGENTE", lambda e: "pose" in e["set"])
        e["set"]["pose"]["orientacion"] = "NE"
    assert contiene(errores_de(base, alterar), "orientacion 'NE'")


def test_pose_fuera_del_mapa(base):
    def alterar(t):
        tick(t, 0)["cambios"][1]["set"]["pose"]["x"] = 99
    assert contiene(errores_de(base, alterar), "tick 0", "fuera del mapa")


def test_carga_mayor_que_la_capacidad(base):
    def alterar(t):
        _, e = evento(t, "AGENTE", lambda e: e["id"] == H and "carga" in e["set"])
        e["set"]["carga"] = 99
    assert contiene(errores_de(base, alterar), "carga 99", "capacidad (3)")


# --- Mundo ---------------------------------------------------------------------------------------
def test_celda_cosechada_dos_veces(base):
    def alterar(t):
        t_, e = evento(t, "CELDA_COSECHADA")
        t_["cambios"].append(copy.deepcopy(e))
    assert contiene(errores_de(base, alterar), "se cosecha dos veces")


def test_celda_fuera_del_campo(base):
    def alterar(t):
        _, e = evento(t, "CELDA_COSECHADA")
        e["celda"] = [1, 0]  # la fila 0 es de servicio, no es campo
    assert contiene(errores_de(base, alterar), "fuera del campo")


def test_entregado_total_inconsistente(base):
    def alterar(t):
        _, e = evento(t, "DEPOSITO")
        e["entregado_total"] = e["cantidad"] + 1
    t_, e = evento(base, "DEPOSITO")
    assert contiene(errores_de(base, alterar), f"tick {t_['tick']}", "(DEPOSITO)",
                    f"entregado_total {e['cantidad'] + 1}, se esperaba {e['cantidad']}")


# --- Mensajes ------------------------------------------------------------------------------------
def test_performativa_del_mensaje(base):
    def desconocida(t):
        _, e = evento(t, "MENSAJE_ENVIADO")
        e["performativa"] = "ordenar"

    def equivocada(t):
        _, e = evento(t, "MENSAJE_ENVIADO", lambda e: e["tipo_mensaje"] == "LLENA")
        e["performativa"] = "inform"

    def sin_performativa(t):
        _, e = evento(t, "MENSAJE_ENVIADO")
        del e["performativa"]
    assert contiene(errores_de(base, desconocida), "performativa 'ordenar'")
    assert contiene(errores_de(base, equivocada), "performativa 'inform' para LLENA", "'request'")
    assert contiene(errores_de(base, sin_performativa), "faltan campos ['performativa']")


def test_entrega_sin_envio_previo(base):
    def alterar(t):
        _, e = evento(t, "MENSAJE_ENTREGADO")
        e["id"] = 99
    assert contiene(errores_de(base, alterar), "el mensaje 99 no corresponde a un envío previo")


def test_entrega_en_debe_ser_el_tick_siguiente(base):
    def alterar(t):
        _, e = evento(t, "MENSAJE_ENVIADO")
        e["entrega_en"] += 1
    assert contiene(errores_de(base, alterar), "(MENSAJE_ENVIADO)", "entrega_en")


def test_retraso_maximo_configurable(base):
    """Con retraso_maximo=3, un mensaje que se entrega 2 ticks después es válido; con el default (1), no."""
    def alterar(t):
        t_, e = evento(t, "MENSAJE_ENVIADO")
        e["entrega_en"] += 1
        tick_entrega = next(x for x in t["ticks"] if any(c["tipo"] == "MENSAJE_ENTREGADO" and c["id"] == e["id"]
                                                         for c in x["cambios"]))
        entrega = next(c for c in tick_entrega["cambios"] if c["tipo"] == "MENSAJE_ENTREGADO" and c["id"] == e["id"])
        tick_entrega["cambios"].remove(entrega)
        destino = next((x for x in t["ticks"] if x["tick"] == e["entrega_en"]), None)
        assert destino is not None  # el fixture tiene cambios en ese tick
        destino["cambios"].insert(0, entrega)
    trace = resellar(copy.deepcopy(base))
    alterar(trace)
    resellar(trace)
    assert validar_trace(trace, retraso_maximo=3) == []
    assert contiene(validar_trace(trace), "entrega_en")


def test_aviso_por_estado_desconocido(base):
    trace = copy.deepcopy(base)
    _, e = evento(trace, "AGENTE", lambda e: "estado" in e["set"] and e["set"]["estado"] == "COSECHANDO")
    e["set"]["estado"] = "ESTADO_NUEVO"
    avisos = []
    assert validar_trace(resellar(trace), avisos=avisos) == []  # no es un error
    assert len(avisos) == 1 and "ESTADO_NUEVO" in avisos[0]


def test_mensaje_que_nunca_se_entrega(base):
    def alterar(t):
        t_, e = evento(t, "MENSAJE_ENTREGADO")
        t_["cambios"].remove(e)
    assert contiene(errores_de(base, alterar), "nunca se entregó")


def test_ids_de_mensaje_no_crecientes(base):
    def alterar(t):
        enviados = [e for x in t["ticks"] for e in x["cambios"] if e["tipo"] == "MENSAJE_ENVIADO"]
        enviados[1]["id"] = enviados[0]["id"]
    assert contiene(errores_de(base, alterar), "repetido")


# --- Línea de comandos ---------------------------------------------------------------------------
def test_cli_ok_y_errores(tmp_path, capsys, base):
    cli = cargar_script("tools/validar_trace.py")
    assert cli.main([str(FIXTURE)]) == 0
    assert capsys.readouterr().out.strip().endswith(": OK")

    roto = copy.deepcopy(base)
    roto["schema_version"] = "1.0"
    ruta_rota = tmp_path / "roto.json"
    ruta_rota.write_text(json.dumps(roto), encoding="utf-8")
    ilegible = tmp_path / "ilegible.json"
    ilegible.write_text("{esto no es json", encoding="utf-8")
    assert cli.main([str(FIXTURE), str(ruta_rota), str(ilegible)]) == 1
    salida = capsys.readouterr().out
    assert "roto.json: 1 error(es)" in salida and "schema_version" in salida
    assert "ilegible.json: no se pudo leer" in salida


# --- Formato 2.2 ---------------------------------------------------------------------------------
def test_un_trace_2_1_sigue_siendo_valido(base):
    def alterar(t):
        t["schema_version"] = "2.1"
        for x in t["ticks"]:
            for e in x["cambios"]:
                e.pop("cantidad", None) if e["tipo"] == "CELDA_COSECHADA" else None
    assert errores_de(base, alterar) == []


def test_eventos_nuevos_solo_desde_2_2(base):
    recarga = {"tipo": "RECARGA", "agente": C, "cantidad": 10.5, "nivel": 100}

    def con_recarga(version):
        def alterar(t):
            t["schema_version"] = version
            tick(t, 4)["cambios"].append(copy.deepcopy(recarga))
        return alterar
    assert errores_de(base, con_recarga("2.2")) == []
    assert contiene(errores_de(base, con_recarga("2.1")), "tipo desconocido 'RECARGA'", "desde la versión 2.2")


def test_payload_con_claves_obligatorias(base):
    def alterar(t):
        _, e = evento(t, "MENSAJE_ENVIADO", lambda e: e["tipo_mensaje"] == "LLENA")
        del e["payload"]["carga"]
    assert contiene(errores_de(base, alterar), "(MENSAJE_ENVIADO)", "al payload de LLENA le faltan ['carga']")


def test_motivo_y_regla_desconocidos_son_aviso(base):
    """Un motivo de rechazo o una regla de restricción que no están en formato no invalidan el trace."""
    trace = copy.deepcopy(base)
    _, e = evento(trace, "MENSAJE_ENVIADO", lambda e: e["tipo_mensaje"] == "LLENA")
    e.update(tipo_mensaje="RECHAZO", performativa="refuse", payload={"servicio": "cosechadora_1#1", "motivo": "otro"})
    tick(trace, 4)["cambios"].append({"tipo": "RESTRICCION", "agente": H, "regla": "regla_nueva", "detalle": "x"})
    tick(trace, 5)["cambios"].append({"tipo": "RESTRICCION", "agente": H, "regla": "R10_obstaculo", "detalle": "x"})
    avisos = []
    assert validar_trace(resellar(trace), avisos=avisos) == []
    assert any("'otro'" in a for a in avisos) and any("'regla_nueva'" in a for a in avisos)
    assert not any("R10_obstaculo" in a for a in avisos)


@pytest.mark.parametrize("nivel, valido", [(40, True), (50, True), (60, False), (-1, False), ("lleno", False)])
def test_combustible_entre_cero_y_el_tanque(base, nivel, valido):
    def alterar(t):
        t["config"]["combustible"] = {"tanque_cosechadora": 50, "tanque_carro": 30}
        tick(t, 0)["cambios"][0]["set"]["combustible"] = nivel
    errores = errores_de(base, alterar)
    assert (errores == []) == valido, errores
    if not valido:
        assert contiene(errores, "tick 0", "combustible")


def test_combustible_no_se_permite_en_2_1(base):
    def alterar(t):
        t["schema_version"] = "2.1"
        tick(t, 0)["cambios"][0]["set"]["combustible"] = 10
    assert contiene(errores_de(base, alterar), "campos no permitidos en set ['combustible']")


def test_rendimiento_del_mundo(base):
    """Mapa 4 × 3 del fixture: fila 0 en 0 y el campo en 1. Se rechazan dimensiones malas, un valor > 0
    fuera del campo y una cantidad cosechada distinta al rendimiento de su celda."""
    matriz = [[0, 0, 0, 0], [1, 1, 1, 1], [1, 1, 1, 1]]

    def con(m, cambiar_cantidad=False):
        def alterar(t):
            t["mundo"]["rendimiento"] = m
            if cambiar_cantidad:
                evento(t, "CELDA_COSECHADA")[1]["cantidad"] = 2
        return alterar
    assert errores_de(base, con(matriz)) == []
    assert contiene(errores_de(base, con(matriz[:2])), "mundo: rendimiento debe ser una matriz de 3 × 4")
    assert contiene(errores_de(base, con([[1, 0, 0, 0]] + matriz[1:])), "rendimiento de (0, 0) debe ser 0")
    assert contiene(errores_de(base, con(matriz, cambiar_cantidad=True)), "(CELDA_COSECHADA)", "cantidad 2", "es 1")


def test_retraso_maximo_por_defecto_sale_de_la_config(base):
    """Con incertidumbre.retraso_mensajes.maximo = 2 en la config del trace, entregar 2 ticks tarde es válido
    sin pasar retraso_maximo; sin esa config, no."""
    trace = copy.deepcopy(base)
    _, e = evento(trace, "MENSAJE_ENVIADO")
    e["entrega_en"] += 1
    tick_entrega = next(x for x in trace["ticks"] if any(c["tipo"] == "MENSAJE_ENTREGADO" and c["id"] == e["id"]
                                                         for c in x["cambios"]))
    entrega = next(c for c in tick_entrega["cambios"] if c["tipo"] == "MENSAJE_ENTREGADO" and c["id"] == e["id"])
    tick_entrega["cambios"].remove(entrega)
    next(x for x in trace["ticks"] if x["tick"] == e["entrega_en"])["cambios"].insert(0, entrega)
    resellar(trace)
    assert contiene(validar_trace(trace), "entrega_en")
    trace["config"]["incertidumbre"] = {"retraso_mensajes": {"probabilidad": 0.5, "maximo": 2}}
    assert validar_trace(trace) == []


def test_trace_de_ejemplo_2_2_es_valido_y_se_regenera_identico(tmp_path):
    """El guion de tools/traces_ejemplo_22.py valida (con su retraso de mensajes) y es determinista."""
    from harvest_sim.datos import escribir_trace
    fixture = FIXTURE.parent / "trace_ejemplo_22.json"
    trace = cargar_trace(fixture)
    avisos = []
    assert trace["schema_version"] == "2.2" and validar_trace(trace, avisos=avisos) == [] and avisos == []
    tipos = {e["tipo"] for t in trace["ticks"] for e in t["cambios"]}
    assert {"RECARGA", "RESTRICCION", "DEPOSITO"} <= tipos
    destino = tmp_path / "otra_vez.json"
    escribir_trace(cargar_script("tools/traces_ejemplo_22.py").generar(), destino)
    assert destino.read_bytes() == fixture.read_bytes()
