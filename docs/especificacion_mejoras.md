# Especificación de las mejoras (M1–M12)

> Plan y orden: `docs/plan_terreno.md` §4b. Reglas para todas:
> - Python sigue siendo la única fuente de verdad.
> - Cada mejora queda **desactivada por defecto**, así que A–F siguen pasando `test_regresion`.
> - Una rama y un PR por mejora, con sus pruebas.
> - G (El Pueblito) es el caso principal.

## M1. Despacho aprendido (Q-learning y SARSA)

**Pregunta:** ¿puede un agente aprender cuándo pedir el carro mejor que el umbral fijo (`umbral_aviso` = 0.7 en la estrategia anticipada)? Responde la pregunta 3 de la retro.

### Cómo se activa

- `politica.aviso`:
  - `"umbral"` (por defecto) es la regla fija de siempre;
  - `"qlearning"` o `"sarsa"` usan una tabla aprendida.
- Requiere `asignacion = "subasta"`, porque usa la llamada `SOLICITUD_SERVICIO`.
- `politica.qtabla`: la ruta de la tabla, relativa a `config/`. Si es `null`, se usa `config/aprendizaje/qtabla_<aviso>_<escenario>.json`. Si la tabla no existe, la simulación falla con un mensaje que dice cómo entrenarla.
- Estrategias `qlearning` y `sarsa` (`ESTRATEGIAS_APRENDIDAS` en `datos/experimentos.py`): son la estrategia **anticipada** (subasta, sin atender desde la bodega ni encadenar) con el aviso aprendido. Por eso la comparación pareada contra `anticipada` aísla lo que aporta el aprendizaje.
  - No están en `ESTRATEGIAS` porque necesitan una tabla por escenario.
  - La CLI y los experimentos sí las aceptan.

### Formulación (rúbrica: estados, acciones, recompensas, cliff)

| Elemento | Definición (`src/harvest_sim/aprendizaje.py`) |
|---|---|
| Momento de decidir | Cuando la tolva de una cosechadora **sin servicio en curso** (ni llamada abierta, ni carro contratado, ni reintento pendiente) entra a un **tramo nuevo**: a lo más una decisión por tramo y ciclo. En las demás celdas sigue cosechando. |
| Por qué por tramo | Se probó primero decidir en cada celda. Pedir una celda más tarde cambia el ocio en décimas de tick, esa diferencia se pierde en el ruido de la actualización, y la política voraz terminaba pidiendo tarde. Por tramo, aplazar un paso cuesta varios ticks de ocio y se aprende. Además, cada tramo se visita una sola vez por ciclo, lo que reduce el aliasing. |
| Respaldo del umbral | En la práctica, la regla fija se evalúa al entrar al tramo, así que con `umbral_aviso = 0.7` el respaldo pide al entrar al tramo 4 (80 %). |
| Estado | (tramo de la tolva 0–4, carros libres 0/1/2+, tramo de distancia al carro más cercano 0–3, otra cosechadora ya pidió 0/1). El tramo 5 es «llena» y solo aparece en el cliff. |
| Carro libre | En `EN_BASE` o `REGRESANDO_A_BASE` |
| Tramo de distancia | Manhattan al carro más cercano entre (ancho + alto): < 0.1, < 0.25, < 0.5, ≥ 0.5. Así la misma tabla tiene sentido en campos de tamaños distintos. |
| Acciones | 0 = seguir cosechando, 1 = pedir carro |
| Recompensa | −1 por cada tick que la cosechadora pasa en `LLENA_ESPERANDO` y −`costo_solicitud` (10) por cada llamada |
| Cliff | La tolva se llena sin carro en camino: −`castigo_cliff` (100) y la llamada se hace a la fuerza, como en la línea base |
| Transiciones | Semi-MDP: la recompensa se acumula entre una decisión y la siguiente de la misma cosechadora. Al final de la corrida se cierra la última transición sin valor futuro. |
| Q-learning | Q(s,a) ← Q(s,a) + α·(r + γ·max Q(s',·) − Q(s,a)) |
| SARSA | Igual, con Q(s',a') de la acción que de verdad se tomó (on-policy) |
| Hiperparámetros | α = 0.1, **γ = 0.999**, ε inicial = 0.2, que baja en línea recta hasta 0.01 |
| Por qué γ tan alto | El problema es episódico (cada corrida termina), así que un γ cercano a 1 es válido. En la primera versión, con una decisión por celda, γ = 0.95 hacía que el ocio de pedir tarde (unas 50 decisiones después) pesara 0.95⁵⁰ ≈ 0.08. «Seguir» siempre parecía más barato porque solo aplazaba el costo. |
| Evaluación | Sin exploración. En un estado nunca visitado o con empate se usa la regla del umbral, así que lo peor que puede pasar es portarse como anticipada. |

Las dos cosechadoras comparten la tabla. La exploración usa su propio `random.Random(semilla)`, así que con la misma tabla y la misma seed el trace es idéntico (prueba `test_entrenar_evaluar_y_reproducir`).

### Entrenamiento y evaluación

```bash
python tools/entrenar_despacho.py config/escenario_d.json --algoritmo qlearning --episodios 500 --epsilon 0.2
python tools/entrenar_despacho.py config/escenario_g.json --algoritmo sarsa --episodios 60 --epsilon 0.2
python tools/correr_experimento.py config/experimentos/m1_despacho.json --procesos 8
python tools/correr_experimento.py config/experimentos/m1_despacho_incertidumbre.json --procesos 8
```

- **Entrenamiento:**
  - Usa las seeds 1000 y siguientes; la evaluación usa las seeds 0 a 19, que nunca se ven al entrenar.
  - Las tablas se versionan en `config/aprendizaje/`.
  - La curva queda en `runs/aprendizaje/<algoritmo>_<escenario>/curva.csv`.
- **Experimento `m1_despacho.json`:** D y G × {subasta, anticipada, qlearning, sarsa} × 20 seeds, pareado contra `anticipada`.
- **Experimento `m1_despacho_incertidumbre.json`:** lo mismo en D con incertidumbre. Las seeds sí varían, así que el IC 95 % es real; la tabla es la de D sin incertidumbre, de modo que esto también prueba la generalización.

Resultados: `docs/resultados_mejoras.md` §M1.

### En el log y en Unity

Para que el visor y Unity muestren el aprendizaje sin decidir nada, el trace registra cada decisión. Todo esto aparece **solo** con `politica.aviso` aprendido; las corridas con las 4 estrategias de siempre no cambian.

- **Evento `DECISION_DESPACHO`** (categoría «mundo», como `RESTRICCION`; desde el trace 2.2):

| Campo | Contenido |
|---|---|
| `agente` | La cosechadora que decide |
| `estado` | `{tramo: 0–5, carros_libres: 0–2, distancia: 0–3, otra_pidio: bool}` |
| `q` | `{seguir, pedir}`: los valores de la tabla en ese estado. Falta si la tabla no lo conoce. |
| `accion` | `seguir` o `pedir` |
| `origen` | `tabla` (la tabla prefirió esa acción), `umbral` (estado nuevo o empate: decidió la regla fija), `forzada` (la tolva se llenó sin carro: el cliff) o `exploracion` (ε, solo al entrenar) |

- Cada `pedir` sale en el mismo tick que el `SOLICITUD_SERVICIO` de esa cosechadora.
- **`config.aprendizaje`:** qué tabla decidió (`algoritmo`, `tabla` relativa a `config/`, `sha256`, `episodios`, `estados`), o `{algoritmo, entrenando: true, epsilon}` al entrenar.
- **Métricas:** `decisiones_despacho`, `pedidos_tabla`, `pedidos_respaldo` y `cliffs_despacho`.
- **Servidor:** `/api/escenarios` lista las 6 estrategias y, por escenario, las que puede correr. Las aprendidas solo aparecen en los escenarios con tabla (hoy D y G).
- **`tools/exportar_traces_unity.py`:** acepta `qlearning` y `sarsa`.
- **Tamaño:** en G con SARSA son 41 decisiones por corrida (≈5 por ciclo); el trace pesa 0.96 MB.
