"""
Modelos Pydantic (DTOs) para request/response bodies de la API FastAPI.

Se mantienen separados de los modelos de dominio (app.domain.models)
para no mezclar las responsabilidades: los modelos de dominio son la
fuente de verdad del negocio; estos son solo los Data Transfer Objects (DTOs)
en la capa HTTP.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Estructura estándar de response (envelope)
# Todos los endpoints devuelven ApiResponse[T]
# ---------------------------------------------------------------------------

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """Envelope estándar para todas las respuestas de la API Puertomar."""

    error: str | None = None
    status_code: int
    data: T | None = None
    message: str

    @classmethod
    def ok(cls, data: Any, message: str = "OK", status_code: int = 200) -> "ApiResponse":
        """Respuesta exitosa."""
        return cls(error=None, status_code=status_code, data=data, message=message)

    @classmethod
    def created(cls, data: Any, message: str = "Created") -> "ApiResponse":
        """Respuesta de creación exitosa (201)."""
        return cls(error=None, status_code=201, data=data, message=message)

    @classmethod
    def fail(cls, error: str, status_code: int, message: str) -> "ApiResponse":
        """Respuesta de error."""
        return cls(error=error, status_code=status_code, data=None, message=message)


# ---------------------------------------------------------------------------
# Ejemplo pre-cargado en Swagger UI para POST /lotes/procesar
# ---------------------------------------------------------------------------
_EJEMPLO_PROCESAR = {
    "lotes": [
        {
            "lote_id": "AT-2026-0001",
            "producto": "Atun en aceite 170 g",
            "autoclave": "AUT-03",
            "inicio": "2026-08-01T08:00:00-05:00",
            "fin": "2026-08-01T09:15:00-05:00",
            "temperatura_minima": 116.0,
            "temperatura_maxima": 123.0,
            "presion_minima": 1.20,
            "presion_maxima": 1.80,
            "lecturas": [
                {"fecha_hora": "2026-08-01T08:10:00-05:00", "temperatura": 117.2, "presion": 1.35},
                {"fecha_hora": "2026-08-01T08:20:00-05:00", "temperatura": 124.1, "presion": 1.62},
                {"fecha_hora": "2026-08-01T08:30:00-05:00", "temperatura": 119.0, "presion": 1.55},
                {"fecha_hora": "2026-08-01T08:45:00-05:00", "temperatura": 120.5, "presion": 1.40},
            ],
        },
        {
            "lote_id": "SA-2026-0002",
            "producto": "Sardina en salsa de tomate 425 g",
            "autoclave": "AUT-01",
            "inicio": "2026-08-01T10:00:00-05:00",
            "fin": "2026-08-01T11:20:00-05:00",
            "temperatura_minima": 115.0,
            "temperatura_maxima": 121.0,
            "presion_minima": 1.10,
            "presion_maxima": 1.70,
            "lecturas": [
                {"fecha_hora": "2026-08-01T10:10:00-05:00", "temperatura": 125.0, "presion": 1.90},
                {"fecha_hora": "2026-08-01T10:25:00-05:00", "temperatura": 122.5, "presion": 1.45},
                {"fecha_hora": "2026-08-01T10:40:00-05:00", "temperatura": 118.0, "presion": 1.95},
                {"fecha_hora": "2026-08-01T11:00:00-05:00", "temperatura": 117.5, "presion": 1.30},
            ],
        },
        {
            "lote_id": "AT-2026-0003",
            "producto": "Atun en agua 170 g",
            "autoclave": "AUT-02",
            "inicio": "2026-08-01T07:00:00-05:00",
            "fin": "2026-08-01T08:10:00-05:00",
            "temperatura_minima": 116.0,
            "temperatura_maxima": 123.0,
            "presion_minima": 1.20,
            "presion_maxima": 1.80,
            "lecturas": [
                {"fecha_hora": "2026-08-01T07:10:00-05:00", "temperatura": 118.0, "presion": 1.40},
                {"fecha_hora": "2026-08-01T07:30:00-05:00", "temperatura": 119.5, "presion": 1.50},
                {"fecha_hora": "2026-08-01T07:50:00-05:00", "temperatura": 120.0, "presion": 1.45},
            ],
        },
    ]
}


# ---------------------------------------------------------------------------
# Request DTOs
# ---------------------------------------------------------------------------

class LecturaInput(BaseModel):
    fecha_hora: str
    temperatura: float
    presion: float


class LoteInput(BaseModel):
    lote_id: str
    producto: str
    autoclave: str
    inicio: str
    fin: str
    temperatura_minima: float
    temperatura_maxima: float
    presion_minima: float
    presion_maxima: float
    lecturas: list[LecturaInput] = []


class ProcesarLotesRequest(BaseModel):
    """Request DTO para POST /lotes/procesar."""

    lotes: list[LoteInput]

    model_config = {
        "json_schema_extra": {
            "example": _EJEMPLO_PROCESAR
        }
    }


# ---------------------------------------------------------------------------
# Response DTOs
# ---------------------------------------------------------------------------

class ResumenLoteResponse(BaseModel):
    total_lecturas: int
    temperatura_promedio: float | None
    temperatura_minima_registrada: float | None
    temperatura_maxima_registrada: float | None
    presion_promedio: float | None
    presion_minima_registrada: float | None
    presion_maxima_registrada: float | None
    numero_alertas: int
    porcentaje_conformes: float
    estado: str


class AlertaDetalle(BaseModel):
    fecha_hora: str
    temperatura: float
    presion: float
    clasificacion: str


class LoteReporteResponse(BaseModel):
    lote_id: str
    producto: str
    autoclave: str
    inicio: str
    fin: str
    resumen: ResumenLoteResponse
    detalle_alertas: list[AlertaDetalle]


class ProcesarLotesPayload(BaseModel):
    lotes: list[LoteReporteResponse]
    errores: list[str]


class LoteListItem(BaseModel):
    lote_id: str
    producto: str
    autoclave: str
    inicio: datetime
    fin: datetime
    temperatura_minima: float
    temperatura_maxima: float
    presion_minima: float
    presion_maxima: float
    creado_en: datetime

    model_config = {"from_attributes": True}


class LecturaDetalle(BaseModel):
    lectura_id: int
    fecha_hora: datetime
    temperatura: float
    presion: float
    clasificacion: str

    model_config = {"from_attributes": True}


class LoteDetalleResponse(BaseModel):
    lote_id: str
    producto: str
    autoclave: str
    inicio: datetime
    fin: datetime
    temperatura_minima: float
    temperatura_maxima: float
    presion_minima: float
    presion_maxima: float
    creado_en: datetime
    lecturas: list[LecturaDetalle]

    model_config = {"from_attributes": True}


class AlertaResumenItem(BaseModel):
    lote_id: str
    autoclave: str
    cantidad_alertas: int
    mayor_desviacion_temperatura: float


class HealthPayload(BaseModel):
    db: str
    version: str
