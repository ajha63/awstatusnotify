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


class IncidentSeverity(str, Enum):
    """Severidad inferida del prefijo del título en el feed RSS.

    Mapeo basado en análisis real del feed (ver feed-analysis.md):
      Service disruption   → CRITICAL
      Service degradation  → HIGH
      Increased error rate → HIGH
      Service impact       → MEDIUM
      Performance issue    → LOW
      Informational message→ INFO
      Operating normally   → RESOLVED
    """

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"
    RESOLVED = "resolved"


class IncidentType(str, Enum):
    """Tipo de incidente según el prefijo del título RSS."""

    DISRUPTION = "disruption"  # "Service disruption:"
    DEGRADATION = "degradation"  # "Service degradation:"
    ERROR_RATE = "error_rate"  # "Increased error rate:"
    IMPACT = "impact"  # "Service impact:"
    PERFORMANCE = "performance"  # "Performance issue:"
    INFORMATIONAL = "informational"  # "Informational message:"
    OPERATIONAL = "operational"  # "Service is operating normally:"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Incident:
    """Representa un incidente reportado en el AWS Service Health Dashboard.

    incident_id: sha256(<slug>:<incident_name>)[:16] — estable por incidente
                 lógico, no por update. Así la deduplicación evita múltiples
                 notificaciones de un mismo incidente aunque AWS publique
                 varios updates.
    service_slug: slug del feed RSS (ej. "ec2-us-east-1", "multipleservices-me-central-1")
    """

    incident_id: str
    service: str  # nombre legible (ej. "EC2", "Multiple services")
    service_slug: str  # slug del feed (ej. "ec2-us-east-1")
    region: str  # región AWS o "global"
    status: IncidentStatus
    severity: IncidentSeverity
    incident_type: IncidentType
    title: str  # nombre del incidente sin prefijo de tipo
    raw_title: str  # título completo tal como viene del feed
    detected_at: datetime
    affected_services: list[str] = field(default_factory=list)
    affected_regions: list[str] = field(default_factory=list)
    affected_azs: list[str] = field(default_factory=list)
    has_rca: bool = False

    def __post_init__(self) -> None:
        if not self.incident_id:
            raise ValueError("incident_id no puede estar vacío")
        if not self.service:
            raise ValueError("service no puede estar vacío")

    @property
    def is_multi_region(self) -> bool:
        """True si el incidente afecta más de una región."""
        return len(self.affected_regions) > 1

    @property
    def is_multi_service(self) -> bool:
        """True si el incidente afecta múltiples servicios (slug multipleservices-*)."""
        return self.service_slug.startswith("multipleservices")
