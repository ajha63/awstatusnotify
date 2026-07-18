"""Entry point del script local.

Cablea los adapters concretos con el caso de uso y ejecuta el ciclo.
Uso: python -m src.handler
"""

from __future__ import annotations

import json
import logging
import logging.config
from pathlib import Path

from src.adapters.health_feed import fetch_incidents
from src.adapters.json_dedup_store import JsonDedupStore
from src.adapters.log_notifier import LogNotifier
from src.application.process_feed import process_feed

CONFIG_PATH = Path("config.json")
LOG_DIR = Path("logs")
LOG_FILE = LOG_DIR / "notifier.log"


def _setup_logging() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s %(levelname)-8s %(name)s — %(message)s",
                    "datefmt": "%Y-%m-%dT%H:%M:%S",
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                },
                "file": {
                    "class": "logging.FileHandler",
                    "filename": str(LOG_FILE),
                    "formatter": "default",
                    "encoding": "utf-8",
                },
            },
            "root": {"level": "INFO", "handlers": ["console", "file"]},
        }
    )


def _load_config() -> dict[str, list[str]]:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"Archivo de configuración no encontrado: {CONFIG_PATH}. "
            "Copia config.json.example a config.json y ajusta los valores."
        )
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


class _FeedFetcherAdapter:
    """Adapta la función fetch_incidents al protocolo FeedFetcher."""

    def fetch_incidents(self) -> list:  # type: ignore[type-arg]
        return fetch_incidents()


def main() -> None:
    _setup_logging()
    logger = logging.getLogger(__name__)

    config = _load_config()
    critical_services: list[str] = config.get("critical_services", [])
    watched_regions: list[str] = config.get("watched_regions", [])

    logger.info(
        "Iniciando chequeo | regiones vigiladas=%s | servicios críticos=%s",
        watched_regions,
        critical_services,
    )

    notified = process_feed(
        fetcher=_FeedFetcherAdapter(),
        dedup=JsonDedupStore(),
        notifier=LogNotifier(),
        critical_services=critical_services,
        watched_regions=watched_regions,
    )

    logger.info("Fin del ciclo | notificaciones enviadas=%d", notified)


if __name__ == "__main__":
    main()
