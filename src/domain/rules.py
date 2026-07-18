"""Reglas de negocio del dominio.

Determina si un incidente es relevante para notificar.
No depende de ninguna librería externa ni SDK de AWS.
"""

from __future__ import annotations

from src.domain.incident import Incident


def is_massive_impact(incident: Incident, critical_services: list[str]) -> bool:
    """Retorna True si el incidente tiene impacto masivo.

    Un incidente es masivo si:
    - Afecta múltiples regiones simultáneamente (más de una), o
    - Afecta múltiples servicios simultáneamente (más de uno), o
    - Afecta un servicio de la lista de servicios críticos.
    """
    if len(incident.affected_regions) > 1:
        return True
    if len(incident.affected_services) > 1:
        return True
    return incident.service in critical_services


def is_watched_region(incident: Incident, watched_regions: list[str]) -> bool:
    """Retorna True si el incidente ocurre en una región vigilada."""
    return incident.region in watched_regions


def should_notify(
    incident: Incident,
    critical_services: list[str],
    watched_regions: list[str],
) -> bool:
    """Retorna True si el incidente debe generar una notificación.

    Combina is_massive_impact e is_watched_region: notifica si cualquiera
    de las dos condiciones se cumple.
    """
    return is_massive_impact(incident, critical_services) or is_watched_region(
        incident, watched_regions
    )
