from __future__ import annotations

from enum import Enum


class ClasificacionLectura(str, Enum):
    NORMAL = "NORMAL"
    ALERTA_TEMPERATURA = "ALERTA_TEMPERATURA"
    ALERTA_PRESION = "ALERTA_PRESION"
    ALERTA_MULTIPLE = "ALERTA_MULTIPLE"


class EstadoLote(str, Enum):
    APROBADO = "APROBADO"
    OBSERVADO = "OBSERVADO"
    RECHAZADO = "RECHAZADO"
