from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from app.domain.exceptions import (
    FechaInvalidaError,
    LecturaFueraDeCicloError,
    RangoInvalidoError,
)
from app.domain.models import ClasificacionLectura, EstadoLote, Lectura, Lote

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ResultadoLectura:
    lectura: Lectura
    clasificacion: ClasificacionLectura


class LoteProcessor:
    
    def validar_lote(self, lote: Lote) -> None:
        """Valida fechas, rangos y pertenencia de lecturas al ciclo."""
        if lote.fin <= lote.inicio:
            raise FechaInvalidaError(lote.lote_id, str(lote.inicio), str(lote.fin))

        if lote.temperatura_minima > lote.temperatura_maxima:
            raise RangoInvalidoError(
                "temperatura", lote.temperatura_minima, lote.temperatura_maxima
            )
        if lote.presion_minima > lote.presion_maxima:
            raise RangoInvalidoError("presion", lote.presion_minima, lote.presion_maxima)

        for lectura in lote.lecturas:
            if not (lote.inicio <= lectura.fecha_hora <= lote.fin):
                raise LecturaFueraDeCicloError(lote.lote_id, str(lectura.fecha_hora))

    def clasificar_lectura(self, lote: Lote, lectura: Lectura) -> ClasificacionLectura:
        """Clasifica una lectura comparándola contra los rangos del lote."""
        temperatura_fuera_de_rango = not (
            lote.temperatura_minima <= lectura.temperatura <= lote.temperatura_maxima
        )
        presion_fuera_de_rango = not (
            lote.presion_minima <= lectura.presion <= lote.presion_maxima
        )

        if temperatura_fuera_de_rango and presion_fuera_de_rango:
            return ClasificacionLectura.ALERTA_MULTIPLE
        if temperatura_fuera_de_rango:
            return ClasificacionLectura.ALERTA_TEMPERATURA
        if presion_fuera_de_rango:
            return ClasificacionLectura.ALERTA_PRESION
        return ClasificacionLectura.NORMAL

    def _determinar_estado(self, numero_alertas: int) -> EstadoLote:
        """Determina el estado del lote según la cantidad de alertas."""
        if numero_alertas == 0:
            return EstadoLote.APROBADO
        if numero_alertas <= 2:
            return EstadoLote.OBSERVADO
        return EstadoLote.RECHAZADO

    def procesar_lote(self, lote: Lote) -> dict[str, Any]:
        """Valida, clasifica y genera el resumen de un lote."""
        logger.info("Procesando lote %s (autoclave %s)", lote.lote_id, lote.autoclave)
        self.validar_lote(lote)

        resultados = [
            ResultadoLectura(lectura=lectura, clasificacion=self.clasificar_lectura(lote, lectura))
            for lectura in lote.lecturas
        ]

        total_lecturas = len(resultados)
        alertas = [r for r in resultados if r.clasificacion != ClasificacionLectura.NORMAL]
        numero_alertas = len(alertas)

        if numero_alertas:
            logger.warning(
                "Lote %s: %d alerta(s) detectada(s) de %d lectura(s)",
                lote.lote_id,
                numero_alertas,
                total_lecturas,
            )

        temperaturas = [r.lectura.temperatura for r in resultados]
        presiones = [r.lectura.presion for r in resultados]

        # Evita división por cero si el lote no tiene lecturas: se
        # documenta explícitamente en vez de dejar que Python lance
        # ZeroDivisionError, que sería un error poco descriptivo.
        porcentaje_conformes = (
            round((total_lecturas - numero_alertas) / total_lecturas * 100, 2)
            if total_lecturas
            else 0.0
        )

        estado = self._determinar_estado(numero_alertas)
        logger.info("Lote %s finalizado con estado %s", lote.lote_id, estado.value)

        return {
            "lote_id": lote.lote_id,
            "producto": lote.producto,
            "autoclave": lote.autoclave,
            "inicio": lote.inicio.isoformat(),
            "fin": lote.fin.isoformat(),
            "resumen": {
                "total_lecturas": total_lecturas,
                "temperatura_promedio": round(sum(temperaturas) / total_lecturas, 2)
                if total_lecturas
                else None,
                "temperatura_minima_registrada": min(temperaturas) if temperaturas else None,
                "temperatura_maxima_registrada": max(temperaturas) if temperaturas else None,
                "presion_promedio": round(sum(presiones) / total_lecturas, 2)
                if total_lecturas
                else None,
                "presion_minima_registrada": min(presiones) if presiones else None,
                "presion_maxima_registrada": max(presiones) if presiones else None,
                "numero_alertas": numero_alertas,
                "porcentaje_conformes": porcentaje_conformes,
                "estado": estado.value,
            },
            "detalle_alertas": [
                {
                    "fecha_hora": r.lectura.fecha_hora.isoformat(),
                    "temperatura": r.lectura.temperatura,
                    "presion": r.lectura.presion,
                    "clasificacion": r.clasificacion.value,
                }
                for r in alertas
            ],
        }

    def procesar_lotes(self, lotes: list[Lote]) -> dict[str, Any]:
        """Procesa la lista de lotes ordenados por inicio, manejando errores individuales."""
        lotes_ordenados = sorted(lotes, key=lambda l: l.inicio)

        reportes_lotes: list[dict[str, Any]] = []
        errores: list[str] = []

        for lote in lotes_ordenados:
            try:
                reportes_lotes.append(self.procesar_lote(lote))
            except Exception as exc:  # noqa: BLE001 - se captura para no abortar el batch
                logger.error("Error procesando el lote %s: %s", lote.lote_id, exc)
                errores.append(f"{lote.lote_id}: {exc}")

        return {"lotes": reportes_lotes, "errores": errores}
