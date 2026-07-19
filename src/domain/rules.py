"""Reglas de negocio del dominio.

Determina si un incidente es relevante para notificar.
No depende de ninguna librería externa ni SDK de AWS.
"""

from __future__ import annotations

from src.domain.incident import Incident, IncidentSeverity, IncidentStatus

# Severidades que siempre activan notificación independientemente de región.
ALWAYS_NOTIFY_SEVERITIES: frozenset[IncidentSeverity] = frozenset(
    [IncidentSeverity.CRITICAL, IncidentSeverity.HIGH]
)


def is_massive_impact(incident: Incident, critical_services: list[str]) -> bool:
    """Retorna True si el incidente tiene impacto masivo.

    Un incidente es masivo si:
    - Su severidad es CRITICAL o HIGH (disruption, degradation, error_rate), o
    - Afecta múltiples regiones simultáneamente, o
    - Su slug es multipleservices-* (múltiples servicios en una región), o
    - Afecta un servicio de la lista de servicios críticos.
    """
    if incident.severity in ALWAYS_NOTIFY_SEVERITIES:
        return True
    if incident.is_multi_region:
        return True
    if incident.is_multi_service:
        return True
    return incident.service in critical_services


def is_watched_region(incident: Incident, watched_regions: list[str]) -> bool:
    """Retorna True si el incidente ocurre en una región vigilada o es global."""
    if incident.region == "global":
        # Los servicios globales (billing, iam, route53) afectan todas las regiones.
        return True
    return incident.region in watched_regions


def is_resolved(incident: Incident) -> bool:
    """Retorna True si el incidente ya está resuelto."""
    return incident.status == IncidentStatus.RESOLVED


def should_notify(
    incident: Incident,
    critical_services: list[str],
    watched_regions: list[str],
) -> bool:
    """Retorna True si el incidente debe generar una notificación.

    No notifica incidentes ya resueltos (el estado RESOLVED llega como
    update final del mismo incidente; si ya notificamos al abrirse, no
    repetimos al cerrarse — eso es responsabilidad del dedup store).

    Notifica si:
    - El incidente no está resuelto, Y
    - Tiene impacto masivo O afecta una región vigilada.
    """
    if is_resolved(incident):
        return False
    return is_massive_impact(incident, critical_services) or is_watched_region(
        incident, watched_regions
    )
