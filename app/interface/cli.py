from __future__ import annotations

import argparse
import logging
import sys

from app.application.lote_processor import LoteProcessor
from app.domain.exceptions import ValidationError
from app.infrastructure.json_repository import cargar_lotes_desde_json, guardar_reporte_json


def _configurar_logging() -> None:
    """Configura logging básico a stdout (punto 5.3: 'registro básico
    de eventos mediante el módulo logging')."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada. Devuelve un código de salida (0 éxito, 1 error)
    en vez de dejar que las excepciones se propaguen sin control, para
    cumplir el punto 5.2.8 ("no finalizar abruptamente, mostrar
    mensajes comprensibles").
    """
    _configurar_logging()
    logger = logging.getLogger("puertomar.cli")

    parser = argparse.ArgumentParser(
        description="Procesa lecturas de ciclos de esterilización de Grupo Puertomar."
    )
    parser.add_argument("entrada", help="Ruta al archivo JSON de entrada")
    parser.add_argument(
        "-o",
        "--salida",
        default="data/reporte_salida.json",
        help="Ruta del archivo JSON de salida (por defecto: data/reporte_salida.json)",
    )
    args = parser.parse_args(argv)

    try:
        lotes = cargar_lotes_desde_json(args.entrada)
        procesador = LoteProcessor()
        reporte = procesador.procesar_lotes(lotes)
        guardar_reporte_json(reporte, args.salida)
    except ValidationError as exc:
        # Errores esperados de negocio/datos: mensaje claro, sin traceback.
        logger.error("Error de validación: %s", exc)
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # noqa: BLE001 - último resguardo, no debe "explotar" la consola
        logger.exception("Error inesperado: %s", exc)
        print(f"ERROR inesperado: {exc}", file=sys.stderr)
        return 1

    print(f"Procesamiento completo. Reporte generado en: {args.salida}")
    if reporte["errores"]:
        print(f"Atención: {len(reporte['errores'])} lote(s) con errores (ver logs).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
