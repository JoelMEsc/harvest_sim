# Ontología del curso: cómo se usa en el diseño y en el log

Una **ontología** es un vocabulario compartido: qué conceptos existen en un dominio, cómo se llaman y cómo se relacionan, para que personas, programas y agentes se refieran a lo mismo con el mismo nombre. El documento del curso pide usarla como andamio de diseño: nombrar agentes, tareas, celdas del mapa, restricciones y registros con el vocabulario del curso, y relacionarlo con los estándares IEEE 1872, 1872.2 y 1873.

En el proyecto aparece en tres lugares: los nombres del diseño, las etiquetas del `trace.json` (formato 2.1) y el acto comunicativo de cada mensaje. Los valores viven en `src/harvest_sim/datos/formato.py` y el validador exige que estén.

## Correspondencias

| Clase del curso | Qué es en nuestro modelo | Dónde aparece | Estándar relacionado |
|---|---|---|---|
| `AutonomousAgriculturalRobot` | La cosechadora y el carro: agentes autónomos con percepción, estado interno y acciones | `agentes[].clase` en el trace; clases `Cosechadora` y `Carro` | IEEE 1872 (ontología central de robótica, CORA: robot, agente) e IEEE 1872.2 (robots autónomos) |
| `SemanticMapCell` | Una celda del grid con significado: campo (se cosecha), fila de servicio, bodega, base de un agente u obstáculo | `mundo.clase_celdas` en el trace; `mundo.bodega`, `mundo.bases`, `mundo.obstaculos`; `datos/campo.py` | IEEE 1873 (representación de mapas para la navegación de robots) |
| `SafetyConstraint` | Las reglas físicas R1–R9 (dentro del mapa, un paso por tick, nunca la misma celda, no intercambiarse, transferir solo entre vecinos, respetar capacidades, conservar el grano, cosechar una vez, no entrar a la bodega) | Especificación §2; pruebas de mundo, rutas e integración | Restricciones de seguridad de la robótica; IEEE 7007 (ética en sistemas robóticos) |
| `AccountabilityRecord` | El `trace.json`: registro verificable de todo lo que pasó (versión del esquema, checksum por tick, reproducible byte a byte) | `meta.clase` en el trace | Rendición de cuentas y trazabilidad (IEEE 7007) |
| Acto comunicativo (KQML / FIPA-ACL) | `LLENA` es una **petición** (`request`: la cosechadora pide que el carro venga); `TRANSFERENCIA_TERMINADA` es un **aviso** (`inform`: la cosechadora informa un hecho) | `performativa` en los eventos `MENSAJE_ENVIADO` | Comunicación entre agentes vista en clase |

Un mensaje del trace se lee como un mensaje KQML: `(request :sender cosechadora_1 :receiver carro_1 :content (LLENA x=3 y=1 carga=4))`. La `performativa` es el tipo de acto, `de` y `a` son emisor y receptor, `tipo_mensaje` y `payload` son el contenido, y el vocabulario es esta ontología.

## Segunda entrega: subasta, seguridad y sostenibilidad en el log

| Concepto | En el log (trace 2.2) | Relación con la ontología |
|---|---|---|
| Protocolo Contract Net | Mensajes `SOLICITUD_SERVICIO` (`cfp`), `PROPUESTA` (`propose`), `RECHAZO` (`refuse`), `ACEPTACION` (`accept-proposal`), `RECHAZO_PROPUESTA` (`reject-proposal`) y `TRANSFERENCIA_TERMINADA` (`inform`) | Actos comunicativos de FIPA-ACL entre *AutonomousAgriculturalRobot*: la cosechadora administra el servicio y los carros ofertan |
| Restricción de seguridad aplicada | Evento `RESTRICCION` con su `regla` (`R3_celda_ocupada`, `R4_intercambio`, `R9_bodega`, `R10_obstaculo`, `combustible_reserva`) | Cada *SafetyConstraint* que cambió una decisión queda en el *AccountabilityRecord*: la supervisión puede auditar qué regla actuó, cuándo y sobre qué agente (IEEE 7007) |
| Sostenibilidad | Campo `combustible` de cada agente y evento `RECARGA` | Consumo y recargas medidos y reportados (métricas `combustible_usado`, `combustible_comprado`, `recargas`), como pide la rúbrica de ética y sostenibilidad |
| Celda con rendimiento | `mundo.rendimiento` y `CELDA_COSECHADA.cantidad` | Atributo de la *SemanticMapCell* de campo |

## Tareas y relaciones

- **Tareas** del robot: cosechar (cosechadora), transportar y descargar (carro), transferir (las dos). Cada estado de las máquinas de estados (§5 de la especificación) corresponde a una tarea o a una espera.
- **Relaciones:** un robot *ocupa* una celda (`pose`); una cosechadora *cosecha* una celda de campo (`CELDA_COSECHADA`); un carro *deposita* en la bodega (`DEPOSITO`); un robot *pide* o *informa* a otro (`MENSAJE_ENVIADO`); una restricción *limita* las acciones de los robots.

> Nota: la tabla relaciona nuestros conceptos con las áreas de cada estándar. Para citar definiciones exactas en el reporte, verifíquenlas en los documentos de IEEE.
