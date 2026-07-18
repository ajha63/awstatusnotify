"""Adapter: lectura y parseo del feed RSS del AWS Service Health Dashboard.

Fuente: https://health.aws.amazon.com/public/currentevents
Feed público, no requiere plan de soporte Business/Enterprise.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime
from typing import Any

import feedparser  # type: ignore[import-untyped]

from src.domain.incident import Incident, IncidentStatus

logger = logging.getLogger(__name__)

AWS_HEALTH_FEED_URL = "https://health.aws.amazon.com/public/currentevents"


def _parse_status(entry: Any) -> IncidentStatus:
    """Infiere el status del incidente a partir del título o tags del entry."""
    title: str = getattr(entry, "title", "").lower()
    if "resolved" in title or "closed" in title:
        return IncidentStatus.RESOLVED
    return IncidentStatus.OPEN


def _parse_region(entry: Any) -> str:
    """Extrae la región del entry. Retorna 'global' si no se identifica."""
    # El feed de AWS no siempre expone la región directamente;
    # se intenta inferir del título o de los tags.
    title: str = getattr(entry, "title", "")
    # Patrón simple: busca tokens que coincidan con nombres de región AWS
    # (e.g. "us-east-1", "eu-west-2"). Se refinará según datos reales.
    import re

    match = re.search(r"[a-z]{2}-[a-z]+-\d", title)
    return match.group(0) if match else "global"


def _stable_id(entry: Any) -> str:
    """Genera un ID estable para el incidente.

    Usa el link del entry si está disponible; de lo contrario hace hash
    del título + fecha para garantizar unicidad.
    """
    link: str = getattr(entry, "link", "")
    if link:
        return hashlib.sha256(link.encode()).hexdigest()[:16]
    raw = f"{getattr(entry, 'title', '')}{getattr(entry, 'published', '')}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def fetch_incidents(feed_url: str = AWS_HEALTH_FEED_URL) -> list[Incident]:
    """Descarga el feed RSS y retorna una lista de Incident.

    Raises:
        RuntimeError: si el feed no puede ser descargado o parseado.
    """
    logger.info("Descargando feed de AWS Service Health: %s", feed_url)
    parsed = feedparser.parse(feed_url)

    if parsed.get("bozo") and not parsed.get("entries"):
        raise RuntimeError(f"No se pudo parsear el feed de AWS Service Health: {feed_url}")

    incidents: list[Incident] = []
    for entry in parsed.entries:
        try:
            published_struct = getattr(entry, "published_parsed", None)
            if published_struct:
                detected_at = datetime(*published_struct[:6], tzinfo=UTC)
            else:
                detected_at = datetime.now(tz=UTC)

            incident = Incident(
                incident_id=_stable_id(entry),
                service=getattr(entry, "tags", [{}])[0].get("term", "unknown")
                if getattr(entry, "tags", None)
                else "unknown",
                region=_parse_region(entry),
                status=_parse_status(entry),
                title=getattr(entry, "title", "Sin título"),
                detected_at=detected_at,
            )
            incidents.append(incident)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Error al parsear entrada del feed: %s — %s", entry, exc)

    logger.info("Feed parseado: %d incidentes encontrados", len(incidents))
    return incidents
