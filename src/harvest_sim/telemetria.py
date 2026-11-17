"""Fachada de compatibilidad: la lógica de Datos vive en el paquete `harvest_sim.datos`.  [Joel]

`from harvest_sim.telemetria import TraceBuilder` sigue funcionando para quien ya lo usa.
"""

from harvest_sim.datos import *  # noqa: F401,F403
from harvest_sim.datos import __all__  # noqa: F401
