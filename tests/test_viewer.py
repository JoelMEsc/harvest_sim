"""Pruebas de la interfaz de Giovanni con un doble del contrato trace 2.1."""
import copy
import importlib.util
import json
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]


def cargar_script(ruta):
    spec = importlib.util.spec_from_file_location(Path(ruta).stem, RAIZ / ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def trace_de_prueba(nombre="prueba_a"):
    """Guion para la interfaz, no resultados de una simulación ni reemplazo de Datos."""
    return {
        "schema_version": "2.1",
        "meta": {"escenario": nombre, "total_ticks": 20, "seed": 0},
        "config": {"nombre": nombre, "ancho": 4, "alto": 3, "capacidad_cosechadora": 3,
                   "capacidad_carro": 6, "tasa_transferencia": 1, "tasa_descarga": 2,
                   "grano_por_celda": 1, "num_carros": 1, "num_cosechadoras": 1},
        "mundo": {"ancho": 4, "alto": 3, "bodega": [0, 0], "bases": {"carro_1": [1, 0],
                  "cosechadora_1": [2, 0]}, "obstaculos": [], "grano_por_celda": 1},
        "agentes": [{"id": "cosechadora_1", "tipo": "cosechadora", "capacidad": 3, "base": [2, 0]},
                    {"id": "carro_1", "tipo": "carro", "capacidad": 6, "base": [1, 0]}],
        "ticks": [{"tick": 0, "cambios": [
            {"tipo": "AGENTE", "id": "cosechadora_1", "set": {"pose": {"x": 2, "y": 0, "orientacion": "S"}, "estado": "EN_BASE", "carga": 0}},
            {"tipo": "AGENTE", "id": "carro_1", "set": {"pose": {"x": 1, "y": 0, "orientacion": "N"}, "estado": "EN_BASE", "carga": 0}}]},
            {"tick": 3, "cambios": [
                {"tipo": "AGENTE", "id": "cosechadora_1", "set": {"carga": 1, "estado": "LLENA_ESPERANDO", "pose": {"x": 0, "y": 1, "orientacion": "O"}}},
                {"tipo": "CELDA_COSECHADA", "celda": [0, 1], "agente": "cosechadora_1"},
                {"tipo": "MENSAJE_ENVIADO", "id": 1, "tipo_mensaje": "LLENA", "performativa": "request", "de": "cosechadora_1", "a": "carro_1", "payload": {"x": 0, "y": 1, "carga": 1}, "entrega_en": 4}]},
            {"tick": 5, "cambios": [{"tipo": "AGENTE", "id": "cosechadora_1", "set": {"carga": 0}}]},
            {"tick": 20, "cambios": [{"tipo": "DEPOSITO", "entregado_total": 1, "cantidad": 1, "agente": "carro_1"}]}],
        "metricas": {"tiempo_completacion": 20, "tiempo_ocioso_cosechadora": 3, "porcentaje_ocioso": 15,
                     "distancia_cosechadora_carro_promedio": 2, "utilizacion_carro": .5, "ticks_bloqueados": 0}}


@pytest.fixture
def viewer(monkeypatch):
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    modulo = cargar_script("viz/viewer.py")
    yield modulo
    modulo.pygame.quit()


def test_visor_dibuja_varios_ticks_sin_errores(viewer):
    rep = viewer.Reproductor(trace_de_prueba())
    for tick in range(rep.total + 1):
        rep.ir_a(tick)
        assert viewer.dibujar(rep).get_width() >= 900
    assert rep.entregado == 1 and rep.cosechadas == {(0, 1)}
    assert all(len(estela) == 12 for estela in rep.estelas.values())


def test_cambios_parciales_ticks_vacios_y_retroceso(viewer):
    trace = trace_de_prueba()
    rep = viewer.Reproductor(trace)
    inicial = copy.deepcopy(rep.agentes)
    rep.ir_a(3)
    assert len(rep.mensajes) == 1
    rep.ir_a(4)
    assert not rep.mensajes and rep.agentes["cosechadora_1"]["carga"] == 1
    rep.ir_a(5)
    assert rep.agentes["cosechadora_1"]["pose"] == {"x": 0, "y": 1, "orientacion": "O"}
    assert rep.agentes["cosechadora_1"]["carga"] == 0
    rep.ir_a(1)
    assert rep.agentes == inicial and rep.cosechadas == set() and rep.entregado == 0
    assert trace["ticks"][0]["cambios"][0]["set"]["carga"] == 0
    rep.ir_a(100)
    assert rep.tick == 20 and rep.entregado == 1


def test_no_deduce_cosecha_de_la_posicion(viewer):
    trace = trace_de_prueba()
    trace["ticks"][1]["cambios"][1]["celda"] = [3, 2]
    rep = viewer.Reproductor(trace)
    rep.ir_a(3)
    assert rep.cosechadas == {(3, 2)}


def test_visor_22_muestra_combustible_alertas_y_varios_agentes(viewer):
    trace = trace_de_prueba()
    trace["schema_version"] = "2.2"
    trace["config"]["combustible"] = {"tanque_cosechadora": 100, "tanque_carro": 80}
    trace["mundo"]["rendimiento"] = [[0] * 4, [1, 2, 3, 4], [4, 3, 2, 1]]
    trace["agentes"].append({"id": "carro_2", "tipo": "carro", "capacidad": 6, "base": [3, 0]})
    trace["mundo"]["bases"]["carro_2"] = [3, 0]
    trace["ticks"][0]["cambios"].append({"tipo": "AGENTE", "id": "carro_2", "set": {
        "pose": {"x": 3, "y": 0, "orientacion": "N"}, "estado": "EN_BASE", "carga": 0, "combustible": 80}})
    trace["ticks"][0]["cambios"][0]["set"]["combustible"] = 100
    trace["ticks"][0]["cambios"][1]["set"]["combustible"] = 80
    trace["ticks"][1]["cambios"].extend([
        {"tipo": "AGENTE", "id": "carro_2", "set": {"combustible": 65}},
        {"tipo": "RECARGA", "agente": "carro_2", "cantidad": 15, "nivel": 80},
        {"tipo": "RESTRICCION", "agente": "carro_2", "regla": "reserva", "detalle": "pasillo ocupado"},
    ])
    rep = viewer.Reproductor(trace)
    rep.ir_a(3)
    assert rep.agentes["carro_2"]["combustible"] == 65
    assert {e["tipo"] for e in rep.eventos} == {"RECARGA", "RESTRICCION"}
    assert viewer.dibujar(rep).get_width() >= 900
    rep.ir_a(4)
    assert rep.eventos == [] and rep.agentes["carro_2"]["combustible"] == 65
    rep.ir_a(0)
    assert rep.agentes["carro_2"]["combustible"] == 80


def test_exporta_png_inicial_intermedios_y_final(viewer, tmp_path):
    ruta = tmp_path / "trace.json"
    ruta.write_text(json.dumps(trace_de_prueba()))
    carpeta = tmp_path / "cuadros"
    assert viewer.main([str(ruta), "--guardar-cuadros", str(carpeta), "--cada", "7"]) == 0
    assert [p.name for p in sorted(carpeta.glob("*.png"))] == [
        "tick_000000.png", "tick_000007.png", "tick_000014.png", "tick_000020.png"]
    assert all(p.read_bytes().startswith(b"\x89PNG\r\n\x1a\n") for p in carpeta.glob("*.png"))


def test_obstaculos_tienen_color_distinto(viewer):
    trace = trace_de_prueba()
    normal = viewer.dibujar(viewer.Reproductor(trace))
    trace["mundo"]["obstaculos"] = [[3, 2]]
    obstaculo = viewer.dibujar(viewer.Reproductor(trace))
    pos = (28 + 3 * 58 + 10, 120 + 2 * 58 + 20)
    assert normal.get_at(pos) != obstaculo.get_at(pos)


def test_reexportar_no_mezcla_cuadros_de_corridas_anteriores(viewer, tmp_path):
    rep = viewer.Reproductor(trace_de_prueba())
    viewer.guardar_cuadros(rep, tmp_path, 7)
    nota = tmp_path / "tick_notas.png"
    nota.write_bytes(b"archivo ajeno a la exportacion")
    trace_corto = trace_de_prueba()
    trace_corto["meta"]["total_ticks"] = 5
    trace_corto["ticks"] = trace_corto["ticks"][:-1]
    viewer.guardar_cuadros(viewer.Reproductor(trace_corto), tmp_path, 3)
    assert sorted(p.name for p in tmp_path.glob("tick_*.png") if p != nota) == [
        "tick_000000.png", "tick_000003.png", "tick_000005.png"]
    assert nota.read_bytes() == b"archivo ajeno a la exportacion"


def test_errores_de_entrada(viewer, tmp_path, capsys):
    assert viewer.main([str(tmp_path / "ausente.json")]) == 2
    assert "error:" in capsys.readouterr().err
    with pytest.raises(ValueError, match="positivo"):
        viewer.guardar_cuadros(viewer.Reproductor(trace_de_prueba()), tmp_path, 0)
    trace = trace_de_prueba()
    trace["schema_version"] = "1.0"
    with pytest.raises(ValueError, match="2.1"):
        viewer.Reproductor(trace)
    trace["schema_version"] = "2.1"
    trace["ticks"].append(trace["ticks"][0])
    with pytest.raises(ValueError, match="crecientes"):
        viewer.Reproductor(trace)


def test_ventana_procesa_pasos_retroceso_y_salida(viewer, monkeypatch):
    pg = viewer.pygame
    lotes = iter([[pg.event.Event(pg.KEYDOWN, key=pg.K_END)],
                  [pg.event.Event(pg.KEYDOWN, key=pg.K_LEFT)],
                  [pg.event.Event(pg.QUIT)]])
    monkeypatch.setattr(pg.event, "get", lambda: next(lotes))
    rep = viewer.Reproductor(trace_de_prueba())
    viewer.reproducir(rep)
    assert rep.tick == 19 and rep.entregado == 0


def test_fixture_y_tres_ejemplos_del_equipo(viewer):
    generador = cargar_script("tools/generar_trace_ejemplo.py")
    traces = [json.loads((RAIZ / "tests/fixtures/trace_ejemplo.json").read_text())]
    traces += [generador.generar(cfg) for cfg in generador.escenarios_de_ejemplo().values()]
    for trace in traces:
        rep = viewer.Reproductor(trace)
        for tick in range(rep.total + 1):
            rep.ir_a(tick)
            assert viewer.dibujar(rep).get_height() >= 620
        depositos = [e["entregado_total"] for t in trace["ticks"] for e in t["cambios"] if e["tipo"] == "DEPOSITO"]
        assert rep.entregado == depositos[-1]
        assert len(rep.cosechadas) == trace["mundo"]["ancho"] * (trace["mundo"]["alto"] - 1)


# CLI pertenece al mismo bloque de interfaz; sus dobles quedan en este archivo asignado.
@pytest.fixture
def cli_preparada(monkeypatch):
    from harvest_sim import cli
    from types import SimpleNamespace
    config = SimpleNamespace(nombre="escenario_prueba")
    trace = json.loads((RAIZ / "tests/fixtures/trace_ejemplo.json").read_text())
    monkeypatch.setattr(cli, "cargar_config", lambda ruta: config)
    monkeypatch.setattr(cli, "ejecutar", lambda cfg: trace)
    return cli, config, trace


def test_cli_genera_trace_y_graficas_desde_otro_directorio(cli_preparada, monkeypatch, tmp_path):
    cli, config, trace = cli_preparada
    monkeypatch.chdir(tmp_path)
    assert cli.main(["config.json", "--salida", "resultados"]) == 0
    salida = tmp_path / "resultados" / config.nombre
    assert json.loads((salida / "trace.json").read_text()) == trace
    assert len(list((salida / "plots").glob("*.png"))) == 6


def test_cli_sin_plots_no_lanza_subproceso(cli_preparada, monkeypatch, tmp_path):
    cli, config, trace = cli_preparada
    def prohibido(*args, **kwargs):
        pytest.fail("--sin-plots no debe generar gráficas")
    monkeypatch.setattr(cli.subprocess, "run", prohibido)
    assert cli.main(["config.json", "--salida", str(tmp_path), "--sin-plots"]) == 0
    assert (tmp_path / config.nombre / "trace.json").exists()


def test_cli_silenciosa_genera_graficas_sin_imprimir_rutas(cli_preparada, tmp_path, capfd):
    cli, config, _ = cli_preparada
    assert cli.main(["config.json", "--salida", str(tmp_path), "--silencioso"]) == 0
    assert len(list((tmp_path / config.nombre / "plots").glob("*.png"))) == 6
    assert capfd.readouterr().out == ""


@pytest.mark.parametrize("etapa,excepcion", [
    ("cargar_config", ValueError("configuración inválida")),
    ("ejecutar", RuntimeError("se alcanzó max_ticks")),
    ("escribir_trace", OSError("sin espacio"))])
def test_cli_informa_fallos(cli_preparada, monkeypatch, tmp_path, capsys, etapa, excepcion):
    cli, _, _ = cli_preparada
    def fallar(*args):
        raise excepcion
    monkeypatch.setattr(cli, etapa, fallar)
    assert cli.main(["config.json", "--salida", str(tmp_path)]) == 1
    assert str(excepcion) in capsys.readouterr().err
    assert not list(tmp_path.rglob("trace.json"))


def test_cli_fallo_de_plots_no_se_reporta_como_exito(cli_preparada, monkeypatch, tmp_path, capsys):
    cli, _, _ = cli_preparada
    def fallar(*args, **kwargs):
        raise cli.subprocess.CalledProcessError(2, "plots.py")
    monkeypatch.setattr(cli.subprocess, "run", fallar)
    assert cli.main(["config.json", "--salida", str(tmp_path)]) == 1
    assert "plots.py" in capsys.readouterr().err


@pytest.mark.parametrize("opciones,nivel", [([], 20), (["--silencioso"], 30), (["--detallado"], 10)])
def test_cli_niveles_de_logging(cli_preparada, monkeypatch, tmp_path, opciones, nivel):
    cli, _, _ = cli_preparada
    llamadas = []
    monkeypatch.setattr(cli.logging, "basicConfig", lambda **kwargs: llamadas.append(kwargs))
    assert cli.main(["config.json", "--salida", str(tmp_path), "--sin-plots", *opciones]) == 0
    assert llamadas == [{"level": nivel, "format": "%(message)s"}]


def test_cli_rechaza_nombre_con_escape_de_carpeta(cli_preparada, tmp_path, capsys):
    cli, config, _ = cli_preparada
    config.nombre = "../fuera"
    assert cli.main(["config.json", "--salida", str(tmp_path)]) == 1
    assert "sin rutas" in capsys.readouterr().err


def test_cli_sobrescribe_seed_y_estrategia_sin_cambiar_config_original(cli_preparada, monkeypatch, tmp_path):
    from dataclasses import make_dataclass
    from harvest_sim.datos import experimentos

    cli, _, trace = cli_preparada
    ConfigPrueba = make_dataclass("ConfigPrueba", [("nombre", str), ("seed", int), ("politica", dict)], frozen=True)
    original = ConfigPrueba("escenario_prueba", 0, {"asignacion": "directa", "espera_propuestas": 2})
    recibidas = []
    monkeypatch.setattr(cli, "cargar_config", lambda _: original)
    monkeypatch.setattr(cli, "ejecutar", lambda cfg: recibidas.append(cfg) or trace)
    monkeypatch.setattr(experimentos, "ESTRATEGIAS", {"anticipada": {"asignacion": "subasta", "umbral_aviso": .7}}, raising=False)
    assert cli.main(["config.json", "--salida", str(tmp_path), "--sin-plots", "--seed", "3", "--estrategia", "anticipada"]) == 0
    assert recibidas[0].seed == 3
    assert recibidas[0].politica == {"asignacion": "subasta", "espera_propuestas": 2, "umbral_aviso": .7}
    assert original.seed == 0 and original.politica == {"asignacion": "directa", "espera_propuestas": 2}


def test_cli_rechaza_seed_negativa_y_estrategia_sin_contrato(cli_preparada, monkeypatch, tmp_path, capsys):
    from harvest_sim.datos import experimentos

    cli, _, _ = cli_preparada
    assert cli.main(["config.json", "--salida", str(tmp_path), "--seed", "-1"]) == 1
    assert "--seed" in capsys.readouterr().err
    # sin el contrato de Datos (ESTRATEGIAS) la CLI lo dice; la prueba no depende de que ya exista
    with monkeypatch.context() as m:
        m.delattr(experimentos, "ESTRATEGIAS", raising=False)
        assert cli.main(["config.json", "--salida", str(tmp_path), "--estrategia", "subasta"]) == 1
        assert "ESTRATEGIAS" in capsys.readouterr().err
    # con el contrato, pero con una configuración sin politica, el error nombra la politica
    m2 = {"subasta": {"politica": {"asignacion": "subasta"}}}
    monkeypatch.setattr(experimentos, "ESTRATEGIAS", m2, raising=False)
    assert cli.main(["config.json", "--salida", str(tmp_path), "--estrategia", "subasta"]) == 1
    assert "politica" in capsys.readouterr().err


def test_visor_23_dibuja_caminos_y_fuera_del_predio(viewer):
    """Con mapa (2.3) los caminos van en color de terracería, lo de fuera del predio queda casi blanco y la
    fila 0 ya no es de servicio."""
    trace = json.loads((RAIZ / "tests" / "fixtures" / "trace_ejemplo_23.json").read_text(encoding="utf-8"))
    mundo = trace["mundo"]
    rep = viewer.Reproductor(trace)
    superficie = viewer.dibujar(rep)
    celda = max(2, min(58, 650 // max(mundo["ancho"], mundo["alto"])))

    def color(pos):
        return superficie.get_at((28 + pos[0] * celda + celda // 3, 120 + pos[1] * celda + celda // 3))

    especiales = {tuple(mundo["bodega"])} | {tuple(b) for b in mundo["bases"].values()}
    camino = next(tuple(c) for c in mundo["caminos"] if tuple(c) not in especiales)
    assert color(camino) == viewer.pygame.Color(viewer.CAMINO)
    assert color(tuple(mundo["fuera_de_campo"][0])) == viewer.pygame.Color(viewer.FUERA)
    campo_fila_0 = [(x, 0) for x in range(mundo["ancho"])
                    if (x, 0) not in {tuple(c) for c in mundo["caminos"] + mundo["fuera_de_campo"] + mundo["obstaculos"]}
                    and (x, 0) not in especiales]
    for pos in campo_fila_0:
        assert color(pos) != viewer.pygame.Color(viewer.SERVICIO)
