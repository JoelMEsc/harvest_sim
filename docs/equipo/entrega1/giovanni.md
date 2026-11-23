# Guía de Giovanni — Interfaz (visor, CLI y dashboard)

**Tu parte en una frase:** el visor 2D que reproduce un `trace.json`, la línea de comandos que corre una simulación de principio a fin, y el **dashboard** que pide la rúbrica.

**Por qué importa:** el dashboard es **obligatorio** en la rúbrica nueva (criterio 6, 10 puntos) y es lo primero que verá el profesor. El visor y la CLI son la cara del proyecto.

**Fecha límite:** martes 17, antes de la clase. **No esperas a nadie para empezar:** el visor y el dashboard funcionan desde ya con los datos de ejemplo.

**Archivos tuyos:** `viz/viewer.py`, `viz/dashboard.py` (nuevo), `src/harvest_sim/cli.py`, `tests/test_viewer.py`, `tests/test_dashboard.py` (nuevo).

**Lee antes:** [README del equipo](README.md) §3 y §5; especificación §6.3 y §7.1; el PDF de Canvas en `reto/` (sección del dashboard).

---

## Tareas (en orden)

### 1. Visor (`viz/viewer.py`) — 2 h

- **No importa nada de `harvest_sim`**: solo `json` y `pygame` (así el mismo log servirá para Unity).
- Datos de prueba: `tests/fixtures/trace_ejemplo.json` y `python tools/generar_trace_ejemplo.py --escenarios` (3 traces en `runs/ejemplo/`).
- Cómo reconstruir el estado (todo lo que necesitas; no deduzcas nada de las posiciones):
  ```python
  traza = json.load(open(ruta, encoding="utf-8"))
  mundo = traza["mundo"]; total = traza["meta"]["total_ticks"]
  cambios_por_tick = {t["tick"]: t["cambios"] for t in traza["ticks"]}
  agentes = {}; cosechadas = set(); entregado = 0
  def avanzar_a(tick):                      # aplica los cambios de ese tick
      global entregado
      for e in cambios_por_tick.get(tick, []):
          if e["tipo"] == "AGENTE": agentes.setdefault(e["id"], {}).update(e["set"])
          elif e["tipo"] == "CELDA_COSECHADA": cosechadas.add(tuple(e["celda"]))
          elif e["tipo"] == "DEPOSITO": entregado = e["entregado_total"]
  ```
  Para retroceder, vuelve a empezar desde el tick 0 (son pocos ticks) o guarda una copia del estado cada cierto número de ticks.
- Debe mostrar (§7.1): grid; celdas cosechadas y por cosechar en colores distintos; bodega, bases y **obstáculos** (`mundo["obstaculos"]`, hoy vacío) marcados distinto; agentes con su orientación; barra de carga (`carga` / `capacidad` del catálogo `traza["agentes"]`); estado en texto; tick; estela de los últimos ticks; mensajes del tick (`MENSAJE_ENVIADO`) como texto. Controles: pausa y reanudar, paso a paso, velocidad.
- Opción `--guardar-cuadros carpeta/` que guarde un PNG cada N ticks (lo usa el dashboard para el panel del entorno).
- **Listo cuando:** reproduce los 3 traces de ejemplo de principio a fin, y `tests/test_viewer.py` (con `SDL_VIDEODRIVER=dummy`, dibuja varios ticks del fixture sin error) pasa sin `skip`.

### 2. CLI (`src/harvest_sim/cli.py`) — 1 h

```python
config = cargar_config(args.config)
trace = ejecutar(config)                                   # Carlos
escribir_trace(trace, Path(args.salida) / config.nombre / "trace.json")   # from harvest_sim.datos import escribir_trace
if not args.sin_plots:
    subprocess.run([sys.executable, "viz/plots.py", ruta_trace], check=True)   # o importa viz/plots.py con importlib
```

- Logging: `INFO` por defecto, `--silencioso` → `WARNING`, `--detallado` → `DEBUG`, formato `%(message)s` (sin fecha ni hora, §6.3).
- Código de salida distinto de 0 si algo falla (configuración inválida, `max_ticks`, etc.), con el mensaje en `stderr`.
- Mientras no exista `ejecutar`, pruébala con un `ejecutar` falso que devuelva el fixture.
- **Listo cuando:** `python -m harvest_sim.cli config/escenario_a.json` genera `runs/escenario_a/trace.json` y sus gráficas en `runs/escenario_a/plots/`.

### 3. Dashboard (`viz/dashboard.py`) — 2 h 30 min — **obligatorio**

Una página HTML estática (solo biblioteca estándar: arma el HTML con texto) que se abre en el navegador: `python viz/dashboard.py runs/escenario_a runs/escenario_b runs/escenario_c --salida runs/dashboard.html`. Lee solo archivos ya generados (trace, gráficas, tabla); no corre la simulación. Tres paneles, como pide la rúbrica:

| Panel | Qué lleva | De dónde sale |
|---|---|---|
| **Entorno** | Cuadros del visor (o una animación) de cada escenario: grid, agentes, celdas cosechadas | `viewer.py --guardar-cuadros` |
| **Indicadores** | Por escenario: tarjetas con tiempo de completación, tiempo ocioso, % ocioso, distancia media cosechadora–carro, utilización del carro, bloqueos; y la línea de tiempo de estados, el ocio acumulado y el flujo del grano | `trace["metricas"]` y `runs/<escenario>/plots/1_…` a `4_…` |
| **Experimental** | Tabla de **parámetros de cada escenario** (ancho × alto, capacidades, tasas: lo pide la rúbrica), la comparación entre escenarios, la tabla resumen, los mapas de calor y la gráfica de sensibilidad | `trace["config"]`, `runs/comparacion/`, `runs/<escenario>/plots/5_…` y `6_…`, `runs/experimentos/<nombre>/` |

- Títulos, unidades y una frase por gráfica que diga qué pregunta responde (están en el docstring de `viz/plots.py`).
- Las imágenes se referencian con rutas relativas o se incrustan en base64 (así la página funciona sola).
- Prueba de humo `tests/test_dashboard.py`: genera el dashboard con los traces de ejemplo en `tmp_path` y comprueba que el HTML tiene los tres paneles y los nombres de los escenarios.
- **Listo cuando:** con los 3 escenarios reales, `runs/dashboard.html` se abre y muestra los tres paneles; tomas capturas para el PDF.

### 4. PDF: sección 6 «Dashboard» — 30 min (martes)

Capturas de los tres paneles y una explicación breve de cada uno.

---

## Contrato con Datos

- El trace es el del [README del equipo](README.md) §3 (versión 2.1). Si te falta un dato, se agrega al log (pídeselo a Joel); el visor no lo calcula.
- Las gráficas y la tabla se generan con `python viz/plots.py runs/escenario_*/trace.json` (Joel). Nombres: `1_linea_de_tiempo_estados.png`, `2_ocioso_acumulado.png`, `3_distancia_cosechadora_carro.png`, `4_flujo_del_grano.png`, `5_mapa_espera.png`, `6_mapa_trafico.png` y `runs/comparacion/comparacion_escenarios.png`, `resumen.csv`, `resumen.md`.

## Dependencias

- **Dependes de:** nadie para el visor y el dashboard (datos de ejemplo); de Carlos (`ejecutar`) para la CLI real.
- **Dependen de ti:** el PDF (panel del dashboard) y la reproducibilidad (la CLI la usa `scripts/correr_todos.sh` de Ilan).

## Cómo probar

```bash
python tools/generar_trace_ejemplo.py --escenarios && python viz/plots.py runs/ejemplo/*/trace.json
python viz/viewer.py runs/ejemplo/ejemplo_a/trace.json
python viz/dashboard.py runs/ejemplo/ejemplo_a runs/ejemplo/ejemplo_b runs/ejemplo/ejemplo_c --salida runs/dashboard.html
SDL_VIDEODRIVER=dummy pytest tests/test_viewer.py tests/test_dashboard.py -q
```

## Definición de listo

- [ ] El visor no importa `harvest_sim` y reproduce cualquier trace 2.1.
- [ ] La CLI corre un escenario completo y devuelve un código distinto de 0 si falla.
- [ ] El dashboard tiene los tres paneles y la tabla de parámetros por escenario.
- [ ] Pruebas del visor y del dashboard sin `skip`.

## Errores comunes

- Deducir qué celdas se cosecharon a partir de la posición de la cosechadora (hay que usar `CELDA_COSECHADA`).
- Suponer que todos los ticks están en el archivo: solo están los que tienen cambios; entre uno y otro el estado se mantiene.
- Rutas absolutas en el HTML del dashboard (no funcionan en otra máquina).
