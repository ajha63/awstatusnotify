"""Caso de uso principal: orquesta fetch -> parse -> evaluar -> notificar.

Depende de interfaces/protocolos, no de implementaciones concretas,
para facilitar el testing y la migración futura de adapters.
"""

from __future__ import annotations

import logging
from typing import Protocol

from src.domain.incident import Incident
from src.domain.rules import should_notify

logger = logging.getLogger(__name__)


class FeedFetcher(Protocol):
    """Puerto de entrada: fuente de incidentes."""

    def fetch_incidents(self) -> list[Incident]: ...


class DedupStore(Protocol):
    """Puerto de salida: almacén de deduplicación."""

    def is_seen(self, incident_id: str) -> bool: ...
    def mark_seen(self, incident_id: str) -> None: ...


class Notifier(Protocol):
    """Puerto de salida: canal de notificación."""

    def notify(self, incident: Incident) -> None: ...


def process_feed(
    fetcher: FeedFetcher,
    dedup: DedupStore,
    notifier: Notifier,
    critical_services: list[str],
    watched_regions: list[str],
) -> int:
    """Ejecuta el ciclo completo de chequeo y notificación.

    Returns:
        Número de notificaciones enviadas en esta ejecución.
    """
    incidents = fetcher.fetch_incidents()
    logger.info("Evaluando %d incidentes del feed", len(incidents))

    notified = 0
    for incident in incidents:
        if dedup.is_seen(incident.incident_id):
            logger.debug("Incidente ya visto, omitiendo: %s", incident.incident_id)
            continue

        if should_notify(incident, critical_services, watched_regions):
            notifier.notify(incident)
            dedup.mark_seen(incident.incident_id)
            notified += 1
        else:
            logger.debug(
                "Incidente no relevante para notificar: %s (%s / %s)",
                incident.incident_id,
                incident.service,
                incident.region,
            )

    logger.info("Ciclo completado: %d notificaciones enviadas", notified)
    return notified
