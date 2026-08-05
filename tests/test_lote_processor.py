"""
Pruebas automatizadas exigidas para la prueba técnica de Grupo Puertomar.

Contiene exactamente los seis escenarios especificados en el punto 5.3 del requerimiento:
1. Caso correcto
2. Fecha inválida
3. Rango inválido
4. Lectura fuera del ciclo
5. Alerta múltiple
6. Cálculo de estado
"""

from __future__ import annotations

from datetime import datetime

import pytest

from app.application.lote_processor import LoteProcessor
from app.domain.exceptions import (
    FechaInvalidaError,
    LecturaFueraDeCicloError,
    RangoInvalidoError,
)
from app.domain.models import ClasificacionLectura, EstadoLote, Lectura, Lote


def _lote_base(lecturas: list[Lectura] | None = None, **overrides) -> Lote:
    """Construye un Lote de referencia para las pruebas."""
    valores = {
        "lote_id": "AT-2026-0001",
        "producto": "Atun en aceite 170 g",
        "autoclave": "AUT-03",
        "inicio": datetime.fromisoformat("2026-08-01T08:00:00-05:00"),
        "fin": datetime.fromisoformat("2026-08-01T09:15:00-05:00"),
        "temperatura_minima": 116.0,
        "temperatura_maxima": 123.0,
        "presion_minima": 1.20,
        "presion_maxima": 1.80,
        "lecturas": lecturas or [],
    }
    valores.update(overrides)
    return Lote(**valores)


@pytest.fixture
def procesador() -> LoteProcessor:
    return LoteProcessor()


# 1. Caso correcto
def test_caso_correcto(procesador: LoteProcessor) -> None:
    """Caso correcto: lote válido se procesa sin errores produciendo resumen conforme."""
    lecturas = [
        Lectura(datetime.fromisoformat("2026-08-01T08:10:00-05:00"), 117.2, 1.35),
        Lectura(datetime.fromisoformat("2026-08-01T08:30:00-05:00"), 119.0, 1.55),
    ]
    lote = _lote_base(lecturas=lecturas)

    reporte = procesador.procesar_lote(lote)

    assert reporte["lote_id"] == "AT-2026-0001"
    assert reporte["resumen"]["total_lecturas"] == 2
    assert reporte["resumen"]["numero_alertas"] == 0
    assert reporte["resumen"]["estado"] == EstadoLote.APROBADO.value
    assert reporte["resumen"]["porcentaje_conformes"] == 100.0


# 2. Fecha inválida
def test_fecha_invalida(procesador: LoteProcessor) -> None:
    """Fecha inválida: fecha fin anterior a fecha inicio lanza excepción."""
    lote = _lote_base(
        inicio=datetime.fromisoformat("2026-08-01T09:00:00-05:00"),
        fin=datetime.fromisoformat("2026-08-01T08:00:00-05:00"),
    )

    with pytest.raises(FechaInvalidaError):
        procesador.validar_lote(lote)


# 3. Rango inválido
def test_rango_invalido(procesador: LoteProcessor) -> None:
    """Rango inválido: temperatura mínima mayor que máxima lanza excepción."""
    lote = _lote_base(temperatura_minima=130.0, temperatura_maxima=120.0)

    with pytest.raises(RangoInvalidoError):
        procesador.validar_lote(lote)


# 4. Lectura fuera del ciclo
def test_lectura_fuera_de_ciclo(procesador: LoteProcessor) -> None:
    """Lectura fuera del ciclo: lectura anterior al inicio lanza excepción."""
    lecturas = [Lectura(datetime.fromisoformat("2026-08-01T07:00:00-05:00"), 118.0, 1.40)]
    lote = _lote_base(lecturas=lecturas)

    with pytest.raises(LecturaFueraDeCicloError):
        procesador.validar_lote(lote)


# 5. Alerta múltiple
def test_alerta_multiple(procesador: LoteProcessor) -> None:
    """Alerta múltiple: lectura con temperatura y presión fuera de rango a la vez."""
    lote = _lote_base()
    lectura_critica = Lectura(
        datetime.fromisoformat("2026-08-01T08:10:00-05:00"), 130.0, 2.50
    )

    clasificacion = procesador.clasificar_lectura(lote, lectura_critica)

    assert clasificacion == ClasificacionLectura.ALERTA_MULTIPLE


# 6. Cálculo de estado
def test_calculo_de_estado(procesador: LoteProcessor) -> None:
    """Cálculo de estado: asignación correcta según alertas (0->APROBADO, 1-2->OBSERVADO, 3+->RECHAZADO)."""
    # 0 alertas -> APROBADO
    lote_aprobado = _lote_base(
        lecturas=[Lectura(datetime.fromisoformat("2026-08-01T08:10:00-05:00"), 117.0, 1.40)]
    )
    assert procesador.procesar_lote(lote_aprobado)["resumen"]["estado"] == EstadoLote.APROBADO.value

    # 2 alertas -> OBSERVADO
    lote_observado = _lote_base(
        lecturas=[
            Lectura(datetime.fromisoformat("2026-08-01T08:10:00-05:00"), 130.0, 1.40),
            Lectura(datetime.fromisoformat("2026-08-01T08:20:00-05:00"), 130.0, 1.40),
        ]
    )
    assert procesador.procesar_lote(lote_observado)["resumen"]["estado"] == EstadoLote.OBSERVADO.value

    # 3+ alertas -> RECHAZADO
    lote_rechazado = _lote_base(
        lecturas=[
            Lectura(datetime.fromisoformat("2026-08-01T08:10:00-05:00"), 130.0, 1.40),
            Lectura(datetime.fromisoformat("2026-08-01T08:20:00-05:00"), 130.0, 1.40),
            Lectura(datetime.fromisoformat("2026-08-01T08:30:00-05:00"), 130.0, 1.40),
        ]
    )
    assert procesador.procesar_lote(lote_rechazado)["resumen"]["estado"] == EstadoLote.RECHAZADO.value
