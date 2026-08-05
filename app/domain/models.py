from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from app.domain.enums import ClasificacionLectura, EstadoLote

@dataclass(frozen=True)
class Lectura:
    fecha_hora: datetime
    temperatura: float
    presion: float


@dataclass
class Lote:
    lote_id: str
    producto: str
    autoclave: str
    inicio: datetime
    fin: datetime
    temperatura_minima: float
    temperatura_maxima: float
    presion_minima: float
    presion_maxima: float
    lecturas: list[Lectura] = field(default_factory=list)
