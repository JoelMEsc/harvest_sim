# Guía del equipo — entrega del martes 17 de noviembre

Este es el punto de partida. Cada quien tiene su carpeta con una guía paso a paso:

| Persona | Rol | Guía | Estado al martes 17 |
|---|---|---|---|
| Carlos | Mundo (configuración, mundo, simulación) | [carlos/guia.md](carlos/guia.md) | **Hecho e integrado** |
| Oswaldo | Rutas y carro | [oswaldo/guia.md](oswaldo/guia.md) | **Hecho e integrado** |
| Emilio | Mensajes y cosechadora | [emilio/guia.md](emilio/guia.md) | **Hecho e integrado** |
| Mario Giovanni | Interfaz (visor, CLI y dashboard) | [giovanni/guia.md](giovanni/guia.md) | **Hecho e integrado** |
| Ilan | Pruebas, CI, scripts y README | [ilan/guia.md](ilan/guia.md) | **Hecho e integrado** |
| Joel | Datos (trace, métricas, gráficas, experimentos) | [joel/estado.md](joel/estado.md) | **Hecho e integrado**; falta el PDF |

**Fecha límite:** martes 17 de noviembre, **antes de la clase**. Se entrega **un PDF** en Canvas (rúbrica nueva, §5 de este documento) y el repositorio con `main` actualizado.

**Lee en este orden:** este archivo completo (15 min), tu guía (30 min) y las secciones de la [especificación](../especificacion_primera_entrega.md) que tu guía cita.

---

## 1. El proyecto en un minuto

Una **cosechadora** recorre un campo en cuadrícula en serpentina. Cuando se llena, le manda un mensaje `LLENA` al **carro**, que va por el grano, lo recibe y lo lleva a la **bodega** `(0, 0)`. El tiempo que la cosechadora pasa llena esperando al carro es el **tiempo ocioso**, la métrica principal. Esta entrega es la **línea base reactiva**: el carro sale solo cuando la cosechadora ya está llena. Las mejoras se compararán contra ella.

```
simulacion.ejecutar(config)  ──►  trace.json  ──►  visor (Giovanni)
   (Carlos, con Oswaldo y Emilio)     │        ──►  métricas, gráficas, experimentos (Joel)
                                      │        ──►  pruebas de integración (Ilan)
                                      └── único contrato entre todos
```

**Regla de oro:** Python (la simulación) es la única fuente de verdad. El visor y las gráficas **solo leen** `trace.json`; no deciden nada ni importan la simulación.

## 2. Orden de trabajo (quién destraba a quién)

```
Hoy (lunes)                                   Martes temprano
──────────────────────────────────────────    ──────────────────────────────
Oswaldo: rutas.py ─┐
Emilio:  Buzon ────┼─► Oswaldo: carro.py ─┐
Carlos:  config + mundo ─► Emilio: cosechadora.py ─┼─► Carlos: simulacion.ejecutar ─► corridas reales (Joel)
                                                    │                                ─► CLI y visor con log real (Giovanni)
Giovanni: visor con el fixture (no espera) ─────────┘                                ─► pruebas de integración (Ilan)
Ilan: CI + pruebas desde la especificación (no espera)
```

| Bloque | Hora objetivo | Hito |
|---|---|---|
| Lunes tarde | `rutas.py` (Oswaldo), `Buzon` (Emilio), `config.py` y la parte de layout de `mundo.py` (Carlos), CI (Ilan), visor leyendo el fixture (Giovanni) | Cada uno con sus pruebas pasando |
| Lunes noche | `carro.py` y `cosechadora.py` con dobles de prueba; funciones de grano y eventos del mundo | Pruebas de agentes pasando |
| Lunes noche (tarde) | `simulacion.ejecutar` y `cli.py` | **Una corrida completa de los 3 escenarios**, aunque sea fea |
| Martes temprano | Corridas reales, gráficas, experimentos, visor y dashboard con el log real, pruebas de integración sin `skip` | Todo junto en `development` |
| Martes, antes de la clase | Joel arma y sube el PDF; `development` → `main` | Entrega |

**Si te atoras más de 30 minutos, avisa en el chat.** Mejor una corrida fea que corre que piezas perfectas aisladas.

## 3. El contrato: formato del trace 2.1

Todo el equipo produce o consume este archivo. **Lo arma `TraceBuilder` de Joel**: nadie escribe el JSON a mano. Lo que cada quien debe entregar es lo de §3.2. La definición completa está en `src/harvest_sim/datos/formato.py` y la valida `tools/validar_trace.py`.

### 3.1 Forma del archivo

```json
{
  "schema_version": "2.1",
  "meta": {"escenario": "escenario_a", "seed": 0, "total_ticks": 49, "clase": "AccountabilityRecord"},
  "config": {"...": "copia de la configuración usada"},
  "mundo": {"ancho": 8, "alto": 7, "bodega": [0, 0], "bases": {"carro_1": [1, 0], "cosechadora_1": [2, 0]},
            "grano_por_celda": 1, "obstaculos": [], "clase_celdas": "SemanticMapCell"},
  "agentes": [{"id": "cosechadora_1", "tipo": "cosechadora", "clase": "AutonomousAgriculturalRobot",
               "capacidad": 10, "base": [2, 0]}, "..."],
  "ticks": [
    {"tick": 0, "cambios": [{"tipo": "AGENTE", "id": "cosechadora_1",
                              "set": {"pose": {"x": 2, "y": 0, "orientacion": "S"}, "estado": "EN_BASE", "carga": 0}}, "..."],
     "checksum": "e6cdae2a6603ded6"},
    {"tick": 7, "cambios": [
        {"tipo": "AGENTE", "id": "cosechadora_1", "set": {"pose": {"x": 3, "y": 1, "orientacion": "E"}, "carga": 4, "estado": "LLENA_ESPERANDO"}},
        {"tipo": "CELDA_COSECHADA", "celda": [3, 1], "agente": "cosechadora_1"},
        {"tipo": "MENSAJE_ENVIADO", "id": 1, "tipo_mensaje": "LLENA", "performativa": "request",
         "de": "cosechadora_1", "a": "carro_1", "payload": {"x": 3, "y": 1, "carga": 4}, "entrega_en": 8}],
     "checksum": "..."}
  ],
  "metricas": {"...": "las calcula calcular_metricas"}
}
```

- `ticks` solo trae los ticks con cambios (el 0 siempre). Un `AGENTE.set` solo trae los campos que cambiaron.
- `meta.clase`, `agentes[].clase` y `mundo.clase_celdas` los pone `TraceBuilder` (ver [docs/ontologia.md](../ontologia.md)).
- No se guardan rutas, intenciones ni objetivos: solo **hechos**.

### 3.2 Lo que cada módulo entrega

| Quién | Qué entrega | Forma exacta |
|---|---|---|
| Emilio y Oswaldo | `agente.registro(tick)` en cada tick | `{"tick": t, "agent_id": "carro_1", "tipo": "carro", "pose": {"x": 3, "y": 2, "orientacion": "S"}, "estado": "YENDO_A_COSECHADORA", "carga": {"actual": 0, "capacidad": 20}}` (sin `intencion`, sin `objetivo`, sin `checksum`; listas, no tuplas) |
| Carlos (`Mundo`) | `mundo.descripcion()` | `{"ancho", "alto", "bodega": [0, 0], "bases": {id: [x, y]}, "grano_por_celda", "obstaculos": [[x, y], ...]}` |
| Carlos (`Mundo`) | `mundo.drenar_eventos()`: devuelve los eventos del tick y vacía la lista | `{"tipo": "CELDA_COSECHADA", "celda": [x, y], "agente": id}` (en `cosechar`); `{"tipo": "DEPOSITO", "agente": id, "cantidad": n, "entregado_total": total}` (en `depositar`); `{"tipo": "BLOQUEO", "agente": id}` (en `registrar_bloqueo`) |
| Emilio (`Buzon`) | `buzon.drenar_eventos()`: devuelve los eventos del tick y vacía la lista | `{"tipo": "MENSAJE_ENVIADO", "id": n, "tipo_mensaje": "LLENA", "performativa": "request", "de": id, "a": id, "payload": {...}, "entrega_en": tick + 1}` (en `enviar`); `{"tipo": "MENSAJE_ENTREGADO", "id": n, "a": id}` (en `entregar`) |
| Oswaldo y Emilio | Llamar `mundo.registrar_bloqueo(agent_id)` | En cada tick en que el agente **quería moverse y no pudo** porque la celda estaba ocupada (no al esperar al carro) |
| Carlos (`simulacion`) | Armar el trace | Ver la guía de Carlos, tarea 5 (son ~15 líneas) |

La `performativa` es el acto comunicativo del mensaje (KQML / FIPA-ACL): `LLENA` → `"request"` y `TRANSFERENCIA_TERMINADA` → `"inform"`. Está en `harvest_sim.datos.formato.PERFORMATIVAS`: **impórtala, no la escribas a mano**.

### 3.3 Vocabulario compartido

Los nombres de estados, tipos de agente, mensajes y clases de la ontología están en `src/harvest_sim/datos/formato.py`. Usen esos mismos textos (sus `Enum` deben tener exactamente esos valores; la especificación §10 los lista). Si alguien usa un estado nuevo, el validador avisa.

## 4. El campo, los obstáculos y el grano esperado

Una sola fórmula para todos (en `harvest_sim/datos/campo.py`; nadie la vuelve a escribir):

```
celdas_de_campo(mundo) = celdas (x, y) con 0 <= x < ancho y 1 <= y < alto, menos los obstáculos
grano_esperado(mundo)  = número de celdas de campo × grano_por_celda
```

La configuración trae una sección de obstáculos, **vacía en los tres escenarios de esta entrega**:

```json
"obstaculos": {"celdas": [], "regiones": []}
```

Formato cuando se usen: `"celdas": [[3, 2], [4, 2]]` y `"regiones": [{"inicio": [1, 4], "tamano": [2, 3]}]` (rectángulo que empieza en `inicio` (x, y) y mide `tamano` (ancho, alto)). `expandir_obstaculos(seccion, ancho, alto)` valida la sección (dentro del mapa, nada en la fila 0, el campo libre alcanzable desde la bodega) y devuelve la lista de celdas que va en `mundo.obstaculos`. **En esta entrega la simulación no recorre obstáculos:** si la lista no está vacía, `cargar_config` falla con «obstáculos aún no soportados» (igual que con `num_carros` ≠ 1).

## 5. La entrega: rúbrica nueva y reparto del PDF

Fuente: anuncio de Canvas en `reto/` (PDF «Mejoras a la presentación de Semana 2 e implementación»). **El dashboard es obligatorio**. Basta con 2D. Se piden al menos 3 escenarios justificados, variar parámetros, comparar contra un método base y analizar resultados.

| Criterio (puntos) | Qué pide | Sección del PDF | Responsable (escribe) | Insumo |
|---|---|---|---|---|
| 1. Formulación (10) | Problema, variables, supuestos, indicadores, arquitectura del agente y comunicación | 1. Problema y arquitectura | Carlos, con Emilio (mensajes y performativas) | Especificación §1–§5, [ontologia.md](../ontologia.md) |
| 2. Modelado del entorno (15) | Grid 2D, elementos, reglas, parámetros modificables | 2. Entorno | Carlos y Oswaldo | Especificación §2–§4, configuraciones |
| 3. Implementación (15) | Ejecutable, separado en configuración, modelo, experimentos, datos y visualización | 3. Implementación | Ilan | Estructura del repo, README |
| 4. Diseño experimental (15) | 3 escenarios justificados, barrido de parámetros, repeticiones | 4. Experimentos | Joel | `tools/correr_experimento.py`, especificación §8 |
| 5. Métricas (15) | Indicadores ligados al problema, variabilidad, comparación con método base | 5. Métricas y resultados | Joel | Tabla resumen, gráficas |
| 6. Visualización y dashboard (10) | Panel entorno, panel indicadores, panel experimental | 6. Dashboard | Giovanni | Visor, gráficas y tabla de Joel |
| 7. Análisis crítico (10) | Por qué un escenario es mejor, sensibilidad, límites | 7. Análisis | Joel, con todos | Resultados |
| 8. Reproducibilidad (10) | Código, scripts, README, configuraciones, resultados, conclusiones | 8. Reproducibilidad y conclusiones | Ilan | `scripts/`, README |

Cada responsable le manda a Joel su sección (texto e imágenes) **antes del martes a mediodía**. **Joel arma y sube el documento final.**

## 6. Comandos que ya funcionan

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && pip install -e .
pytest                                                       # 230 pasan, ninguna en skip
python tools/generar_trace_ejemplo.py --escenarios           # 3 traces de ejemplo en runs/ejemplo/
python tools/validar_trace.py runs/ejemplo/*/trace.json      # valida el contrato
python viz/plots.py runs/ejemplo/*/trace.json                # 6 gráficas por corrida + comparación y tabla
python tools/correr_experimento.py config/experimentos/tasa_transferencia.json --simulador ejemplo
```

Cuando exista la simulación, los mismos comandos funcionan con `runs/escenario_*/trace.json` y sin `--simulador ejemplo`.

## 7. Git (resumen; el detalle está en el [plan de trabajo](../plan_de_trabajo.md) §7)

```bash
git switch branch-TU-NOMBRE && git fetch origin && git merge origin/development
# ... trabajar SOLO en tus archivos, commits pequeños ...
pytest && git push origin branch-TU-NOMBRE      # y PR branch-TU-NOMBRE -> development
```

Nadie hace push directo a `development` ni a `main`. Cada archivo tiene un solo dueño. Si necesitas un cambio en un archivo ajeno, se lo pides a su dueño.
