"""Regresión contra la línea base de la primera entrega (v0.1-entrega1).  [Dueño: Ilan]

`tests/fixtures/metricas_v0_1.json` guarda las métricas escalares de A, B y C calculadas con el código
de la etiqueta `v0.1-entrega1` (no con el código actual). Con la configuración por defecto, las tres
corridas deben dar exactamente esas métricas: así la comparación de estrategias contra la línea base es
justa. **Esta prueba no se desactiva ni se regenera con el código nuevo**: si falla, alguien cambió la
línea base.
"""

import json
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
ESPERADAS = json.loads((RAIZ / "tests" / "fixtures" / "metricas_v0_1.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("nombre", sorted(ESPERADAS))
def test_regresion_linea_base(nombre):
    from harvest_sim.config import cargar_config
    from harvest_sim.simulacion import ejecutar

    metricas = ejecutar(cargar_config(RAIZ / "config" / f"{nombre}.json"))["metricas"]
    distintas = {clave: (valor, metricas.get(clave)) for clave, valor in ESPERADAS[nombre].items()
                 if metricas.get(clave) != pytest.approx(valor)}
    assert not distintas, f"{nombre}: métricas distintas de v0.1 (esperada, actual): {distintas}"
