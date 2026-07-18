"""Entidad de dominio: Incident.

Representa un incidente del AWS Service Health Dashboard.
No depende de ninguna librería externa ni SDK de AWS.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class IncidentStatus(str, Enum):
    OPEN = "open"
    RESOLVED = "resolved"


@dataclass(frozen=True)
class Incident:
    """Representa un incidente reportado en el AWS Service Health Dashboard."""

    incident_id: str
    service: str
    region: str
    status: IncidentStatus
    title: str
    detected_at: datetime
    affected_services: list[str] = field(default_factory=list)
    affected_regions: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.incident_id:
            raise ValueError("incident_id no puede estar vacío")
        if not self.service:
            raise ValueError("service no puede estar vacío")
