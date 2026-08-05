from __future__ import annotations


class ValidationError(Exception):
    """Excepción base para todos los errores de validación del dominio."""


class CampoObligatorioError(ValidationError):
    """Se lanza cuando un campo requerido llega vacío, None o ausente."""

    def __init__(self, campo: str, contexto: str = "") -> None:
        mensaje = f"El campo obligatorio '{campo}' está vacío o ausente"
        if contexto:
            mensaje += f" ({contexto})"
        super().__init__(mensaje)
        self.campo = campo


class RangoInvalidoError(ValidationError):
    """Se lanza cuando un rango mínimo es mayor que su máximo
    (temperatura_minima > temperatura_maxima, o lo mismo con presión).
    """

    def __init__(self, nombre_rango: str, minimo: float, maximo: float) -> None:
        super().__init__(
            f"Rango inválido para '{nombre_rango}': mínimo ({minimo}) "
            f"es mayor que máximo ({maximo})"
        )
        self.nombre_rango = nombre_rango


class FechaInvalidaError(ValidationError):
    """Se lanza cuando la fecha de fin no es posterior a la de inicio."""

    def __init__(self, lote_id: str, inicio: str, fin: str) -> None:
        super().__init__(
            f"En el lote '{lote_id}': la fecha de fin ({fin}) no es posterior "
            f"a la fecha de inicio ({inicio})"
        )
        self.lote_id = lote_id


class LecturaFueraDeCicloError(ValidationError):
    """Se lanza cuando una lectura tiene fecha_hora fuera del intervalo
    [inicio, fin] del ciclo de esterilización al que pertenece.
    """

    def __init__(self, lote_id: str, fecha_hora: str) -> None:
        super().__init__(
            f"Lote '{lote_id}': la lectura con fecha_hora {fecha_hora} "
            f"está fuera del intervalo del ciclo"
        )
        self.lote_id = lote_id


class ArchivoEntradaError(ValidationError):
    """Se lanza cuando el archivo JSON de entrada no existe, no es JSON
    válido, o no tiene la estructura mínima esperada (clave 'lotes').
    """
