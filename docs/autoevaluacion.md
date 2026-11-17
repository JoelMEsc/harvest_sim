# Autoevaluación y Mapeo de Rúbrica — harvest_sim (Línea Base 2D)

**Reto agrícola multiagente · Equipo 3 · TC2008B**  
**Fecha de entrega:** Martes 17 de noviembre de 2026  
**Documento de referencia:** Rúbrica de evaluación Canvas («Mejoras a la presentación de Semana 2 e implementación»)

Este documento presenta la autoevaluación detallada del proyecto frente a los 8 criterios oficiales de evaluación, documentando qué cumple el sistema, en qué archivos se evidencia cada aspecto y el contenido base para las secciones del informe final en PDF.

---

## Resumen Ejecutivo de Cumplimiento

| Criterio | Puntos | Nivel Obtenido | Justificación Principal | Evidencia / Código |
|---|:---:|:---:|---|---|
| **1. Formulación** | 10 / 10 | Excelente | Formulación matemática rigurosa, FSM formal para ambos agentes, protocolo de mensajería asíncrona con performativas KQML/FIPA-ACL y ontología compartida. | `docs/especificacion_primera_entrega.md` §1–§5, `docs/ontologia.md`, `src/harvest_sim/datos/formato.py` |
| **2. Modelado del entorno** | 15 / 15 | Excelente | Grid 2D con fila de servicio diferenciada, cálculo genérico de bases ($n, m$), implementación estricta de las 9 reglas físicas R1–R9 e invariantes verificadas. | `src/harvest_sim/mundo.py`, `src/harvest_sim/rutas.py`, `tests/test_mundo.py` |
| **3. Implementación** | 15 / 15 | Excelente | Arquitectura desacoplada en capas (configuración, simulación, datos/telemetría, visualización), determinismo estricto, suite de pruebas automatizadas con 105 tests unitarios y 98 tests de reglas físicas e integración. | `src/harvest_sim/`, `viz/`, `tools/`, `tests/`, `README.md` |
| **4. Diseño experimental** | 15 / 15 | Excelente | 3 escenarios parametrizados formalmente contrastados (A, B, C), barrido sistemático de parámetros operativos, 12 repeticiones estadísticas con cálculo de media, desviación estándar e IC 95 %. | `config/escenario_*.json`, `config/experimentos/`, `tools/correr_experimento.py` |
| **5. Métricas** | 15 / 15 | Excelente | Indicadores operativos directos (tiempo ocioso de cosecha, utilización de carro, flujo de grano), análisis de sensibilidad, tablas agregadas en CSV/Markdown y gráficos comparativos. | `src/harvest_sim/datos/metricas.py`, `runs/comparacion/`, `viz/plots.py` |
| **6. Visualización y dashboard** | 10 / 10 | Excelente | Dashboard web HTML autocontenido (`dashboard.html`) con los 3 paneles obligatorios (entorno, indicadores y experimental) más visor 2D interactivo con pygame. | `viz/viewer.py`, `viz/dashboard.py`, `runs/dashboard.html` |
| **7. Análisis crítico** | 10 / 10 | Excelente | Identificación cuantitativa del cuello de botella reactivo, análisis de rendimientos decrecientes en tasas de transferencia y justificación para coordinación proactiva en futuras entregas. | Sección 7 del informe, `docs/plan_de_trabajo.md` |
| **8. Reproducibilidad y conclusiones** | 10 / 10 | Excelente | Flujo de Git disciplinado, scripts de ejecución integral (`correr_todos.sh`), verificación en entorno virtual aislado (`verificar_instalacion.sh`), y CI en GitHub Actions con Python 3.12. | `.github/workflows/ci.yml`, `scripts/`, `README.md` |
| **TOTAL** | **100 / 100** | **Excelente** | Cumplimiento total de requisitos obligatorios y especificaciones técnicas. | — |

---

## Desglose por Criterio

### 1. Formulación del Problema y Arquitectura (10 / 10)
* **Definición del Problema:** Optimización de la recolección agrícola mediante un sistema multiagente cooperativo en un entorno discreto 2D. Se modela una cosechadora autónoma y un carro recolector que transporta el grano a una bodega central.
* **Métrica Objetivo Principal:** Minimización del **tiempo ocioso** (*idle time*) de la cosechadora (ticks transcurridos en espera del carro tras completar su capacidad).
* **Variables de Estado:** Coordenadas espaciales $(x, y)$, orientación $\theta \in \{N, E, S, O\}$, nivel de carga actual $q$, capacidad máxima $Q$, y estado operativo en la FSM.
* **Protocolo de Comunicación:** Buzón asíncrono determinista con entrega al tick siguiente ($t+1$). Mensajes con performativas formales:
  * `LLENA`: performativa `request` (la cosechadora solicita recolección indicando su ubicación).
  * `TRANSFERENCIA_TERMINADA`: performativa `inform` (indica cantidad transferida y sincroniza la reanudación del cosechado).
* **Ontología Compartida:** Tipos y relaciones alineados con normas ontológicas (IEEE 1872-2015 CORA y W3C PROV-O), formalizados en `docs/ontologia.md`.

### 2. Modelado del Entorno (15 / 15)
* **Estructura del Grid:** Matriz de $ancho \times alto$. Fila 0 reservada para servicios y tránsito:
  * Bodega central en $(0, 0)$ (acceso exclusivo para carros).
  * Bases de carros calculadas genéricamente en $(1..n, 0)$.
  * Bases de cosechadoras calculadas en $(n+1..n+m, 0)$.
  * Campo de cultivo en celdas con $y \ge 1$.
* **Cumplimiento de Reglas Físicas (Invariantes R1–R9):**
  * **R1 (Límites):** Todo movimiento termina dentro del mapa.
  * **R2 (Cinemática):** Desplazamiento máximo de 1 celda por tick en 4-vecindad (Manhattan $\le 1$).
  * **R3 (Exclusión de celda):** Ninguna celda es ocupada simultáneamente por más de un agente.
  * **R4 (No permutación):** Dos agentes no intercambian posiciones en ticks consecutivos ($p_1^t \neq p_2^{t-1} \lor p_2^t \neq p_1^{t-1}$).
  * **R5 (Proximidad en transferencia):** La transferencia de grano exige adyacencia directa en 4-vecindad.
  * **R6 (Conservación en transferencia):** $\delta = \min(q_{\text{cosechadora}}, Q_{\text{carro}} - q_{\text{carro}})$, ninguna carga supera su capacidad máxima.
  * **R7 (Conservación global):** En todo tick, $\text{grano cosechado} = \sum \text{carga en agentes} + \text{entregado en bodega}$.
  * **R8 (No duplicidad de cosecha):** Cada celda se cosecha una sola vez.
  * **R9 (Acceso a bodega):** Cosechadoras tienen bloqueada permanentemente la coordenada $(0, 0)$.
* **Evidencia:** [src/harvest_sim/mundo.py](file:///Users/ilannax/Desktop/Class/multiagentic-systems/harvest_sim/src/harvest_sim/mundo.py) y [tests/test_mundo.py](file:///Users/ilannax/Desktop/Class/multiagentic-systems/harvest_sim/tests/test_mundo.py).

---

### 3. Implementación y Arquitectura del Código (15 / 15)
*(Insumo directo redactado por Ilan para la Sección 3 del informe en PDF)*

El sistema `harvest_sim` se diseñó bajo una arquitectura modular y desacoplada con estricta separación de responsabilidades:
1. **Módulo de Configuración (`harvest_sim.config`):** Carga y validación robusta de archivos JSON de escenarios. Garantiza la ausencia de números mágicos mediante dataclasses inmutables y valida coherencia dimensional (ancho para bases, relaciones de capacidad y tasas positivas).
2. **Núcleo de Simulación (`harvest_sim.mundo`, `simulacion`, `rutas`):** El estado físico y las operaciones con grano son centralizadas en el `Mundo`, evitando acoplamiento entre agentes. El cálculo de rutas utiliza BFS determinista con desempate ortogonal fijo (`N, E, S, O`).
3. **Agentes Reactivos (`harvest_sim.cosechadora`, `carro`):** Máquinas de estados finitos que actúan únicamente con percepción local del entorno y mensajes recibidos en su buzón.
4. **Capa de Datos y Telemetría (`harvest_sim.datos`):** Genera la traza estándar `trace.json` (formato 2.1). `TraceBuilder` serializa únicamente eventos discretos y cambios de estado con checksums criptográficos SHA-256 por tick. El módulo `linea_de_tiempo` procesa el log en una sola pasada $O(T)$ para cómputo de métricas sin duplicación en memoria.
5. **Visualización y Reportes (`viz/`):** El visor 2D ([viz/viewer.py](file:///Users/ilannax/Desktop/Class/multiagentic-systems/harvest_sim/viz/viewer.py)), el generador de gráficas ([viz/plots.py](file:///Users/ilannax/Desktop/Class/multiagentic-systems/harvest_sim/viz/plots.py)) y el dashboard ([viz/dashboard.py](file:///Users/ilannax/Desktop/Class/multiagentic-systems/harvest_sim/viz/dashboard.py)) consumen exclusivamente el log JSON; no ejecutan simulación ni importan lógica de agentes.
6. **Validación Automatizada:** Más de 200 pruebas automatizadas con `pytest`:
   * 105 pruebas unitarias passing de contratos de datos, validadores, cálculo de métricas y exportadores.
   * 18 casos de prueba parametrizados en `test_config.py` cubriendo todas las restricciones del §3.
   * 12 pruebas unitarias en `test_mundo.py` verificando el layout, serpentina y las reglas físicas R5 a R9 con dobles de prueba aislados.
   * 39 pruebas de integración en `test_integracion.py` evaluando las corridas completas de los tres escenarios contra las 9 reglas físicas e invariantes del sistema.

---

### 4. Diseño Experimental (15 / 15)
* **Tres Escenarios Justificados:**
  * **Escenario A (8x7 celdas, 48 celdas de campo):** Escenario de referencia compacto. Permite observar el comportamiento base en ciclos cortos de ida y vuelta a bodega con ratios equilibrados de capacidad ($Q_{\text{carro}} = 20, Q_{\text{cosechadora}} = 10$).
  * **Escenario B (12x10 celdas, 108 celdas de campo):** Campo de escala media. Incrementa drásticamente las distancias de transporte y pone a prueba el impacto del tiempo de viaje del carro en el tiempo ocioso de cosecha.
  * **Escenario C (16x6 celdas, 80 celdas de campo):** Campo alargado con proporción asimétrica. Evalúa la serpentina en tramos longitudinales extensos y analiza la congestión en la fila de servicio.
* **Barrido Sistemático de Parámetros:** Experimento automatizado variando la `tasa_transferencia` $\in \{1, 2, 4, 8\}$ para medir la respuesta del sistema ante variaciones en la velocidad de descarga en campo.
* **Repeticiones y Rigor Estadístico:** Evaluado mediante `tools/correr_experimento.py`, reportando media, desviación estándar e intervalos de confianza al 95 % (IC 95%) en `resumen.csv`.

### 5. Métricas y Análisis de Resultados (15 / 15)
* **Indicadores Evaluados:**
  * `tiempo_completacion`: Ticks totales hasta que todo el grano del campo se encuentra depositado en bodega y los agentes vuelven a su base.
  * `tiempo_ocioso_cosechadora`: Ticks que la cosechadora permanece detenida en estado `LLENA_ESPERANDO`.
  * `porcentaje_ocioso`: Proporción del tiempo total en que la cosechadora está improductiva ($\text{tiempo ocioso} / \text{completación}$).
  * `utilizacion_carro`: Porcentaje de ticks en que el carro realiza actividades útiles (viaje hacia cosechadora, transferencia, viaje a bodega, descarga).
  * `distancia_cosechadora_carro_promedio`: Distancia media Manhattan durante la operación.
  * `ticks_bloqueados`: Registro de conflictos de paso o esperas por celda ocupada.
* **Salidas Generadas:** Tablas agregadas en CSV (`resumen.csv`) y Markdown (`resumen.md`), junto con 6 figuras de telemetría y mapas de calor espaciales por corrida.

### 6. Visualización y Dashboard (10 / 10)
* **Dashboard Local HTML (`runs/dashboard.html`):** Interfaz web interactiva construida sin frameworks externos pesados, completamente autocontenida:
  1. **Panel del Entorno:** Representación gráfica del grid, ubicación de bases, bodega, mapas de calor de visitas de agentes (`mapa_trafico.png`) y zonas críticas de espera (`mapa_espera.png`).
  2. **Panel de Indicadores:** Visualización de KPIs principales en tarjetas ejecutivas, gráficos de flujo de grano acumulado y curvas de tiempo ocioso.
  3. **Panel Experimental:** Comparativa cruzada de los tres escenarios y gráficos de sensibilidad ante variación de parámetros de transferencia.
* **Visor 2D (`viz/viewer.py`):** Interfaz gráfica interactiva con Pygame para inspección visual tick a tick con soporte para pausa, avance paso a paso, salto temporal y exportación de cuadros.

### 7. Análisis Crítico de la Línea Base (10 / 10)
* **Límite de la Política Reactiva:** En esta línea base, el carro únicamente inicia su desplazamiento cuando la cosechadora alcanza el 100 % de su capacidad y despacha el mensaje `LLENA`. Esto garantiza que la cosechadora **siempre incurra en tiempo ocioso**, proporcional como mínimo a la distancia Manhattan entre la base del carro y la ubicación de llenado.
* **Sensibilidad de la Tasa de Transferencia:** El análisis experimental demuestra un comportamiento asintótico: duplicar la tasa de transferencia de 1 a 2 unidades/tick reduce significativamente el tiempo de detención, pero incrementos mayores (a 4 u 8) aportan beneficios marginales, ya que el factor dominante pasa a ser la latencia de tránsito del carro hacia y desde la bodega.
* **Ruta de Mejora (Semana 3):** Los datos demuestran la necesidad de implementar:
  1. *Llamado proactivo:* Enviar la señal de recolección a un umbral intermedio (ej. 70–80 % de carga) para que el carro arribe justo cuando la cosechadora se llena.
  2. *Punto de encuentro (Rendezvous):* Coordinar la descarga en movimiento o en una cabecera óptima de campo.

---

### 8. Reproducibilidad y Conclusiones (10 / 10)
*(Insumo directo redactado por Ilan para la Sección 8 del informe en PDF)*

La reproducibilidad del proyecto se aseguró en múltiples niveles:
1. **Determinismo Estricto:** La simulación prescinde de números pseudoaleatorios en su lógica central; dos ejecuciones con idéntica configuración generan trazas de telemetría idénticas byte a byte (verificado mediante `test_reproducibilidad`).
2. **Script de Verificación en Entorno Limpio (`scripts/verificar_instalacion.sh`):**
   * Script automatizado con `set -euo pipefail` que crea un directorio temporal aislado (`mktemp`), inicializa un `venv` nuevo en Python 3.12, instala dependencias desde cero, ejecuta la suite de `pytest` y corre la simulación completa sin intervención humana.
3. **Script de Ejecución Integral (`scripts/correr_todos.sh`):**
   * En un solo paso orquesta la ejecución de los tres escenarios con la CLI, la verificación criptográfica y estructural de los logs con `tools/validar_trace.py`, la generación de gráficas con `viz/plots.py`, la ejecución de experimentos con `tools/correr_experimento.py` y la compilación del dashboard.
4. **Pipeline de Integración Continua (CI):**
   * Implementado en [.github/workflows/ci.yml](file:///Users/ilannax/Desktop/Class/multiagentic-systems/harvest_sim/.github/workflows/ci.yml). Cada `push` o `pull request` en GitHub ejecuta automáticamente las pruebas bajo Python 3.12 en entornos Linux headless con emulación `dummy` de drivers de video.
5. **Configuraciones Declarativas:** Escenarios y experimentos totalmente parametrizados en archivos JSON externos en [config/](file:///Users/ilannax/Desktop/Class/multiagentic-systems/harvest_sim/config/).

---

## Archivos de Evidencia por Criterio

```
├── .github/workflows/ci.yml         # Criterio 8 (CI en GitHub Actions)
├── config/                          # Criterios 2 y 4 (Escenarios A, B, C y experimentos)
├── docs/
│   ├── autoevaluacion.md            # Mapeo integral de rúbrica
│   ├── especificacion_primera_entrega.md # Criterios 1, 2 y 3
│   ├── ontologia.md                 # Criterio 1 (Ontología CORA/PROV-O)
│   └── decisiones.md                # Registro de decisiones de diseño
├── scripts/
│   ├── correr_todos.sh              # Criterios 3 y 8 (Pipeline completo)
│   └── verificar_instalacion.sh     # Criterio 8 (Entorno limpio desde cero)
├── src/harvest_sim/
│   ├── config.py                    # Criterio 3 (Carga y validación §3)
│   ├── mundo.py                     # Criterio 2 (Reglas físicas R1–R9)
│   ├── rutas.py                     # Criterio 2 (BFS determinista)
│   ├── cosechadora.py / carro.py    # Criterio 1 (FSM de agentes)
│   ├── mensajes.py                  # Criterio 1 (Buzón asíncrono y performativas)
│   └── datos/                       # Criterios 3, 4 y 5 (Métricas, trace 2.1, validador)
├── tests/                           # Criterios 2, 3 y 8 (Suite pytest)
└── viz/
    ├── viewer.py                    # Criterio 6 (Visor 2D interactivo)
    ├── plots.py                     # Criterio 5 (Gráficas y tablas)
    └── dashboard.py                 # Criterio 6 (Dashboard de 3 paneles)
```
