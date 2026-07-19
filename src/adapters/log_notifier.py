"""Adapter: notificador que escribe al archivo de log.

En la fase local reemplaza al notificador SNS.
Reemplazable por sns_notifier.py en la migración a AWS.
"""

from __future__ import annotations

import logging

from src.domain.incident import Incident

logger = logging.getLogger(__name__)


class LogNotifier:
    """Emite notificaciones de incidentes escribiendo al log configurado."""

    def notify(self, incident: Incident) -> None:
        """Registra el incidente como una notificación en el log."""
        logger.warning(
            "NOTIFICACIÓN | id=%s | type=%s | severity=%s | status=%s"
            " | service=%s | region=%s | rca=%s | title=%s | detected_at=%s",
            incident.incident_id,
            incident.incident_type.value,
            incident.severity.value,
            incident.status.value,
            incident.service,
            incident.region,
            incident.has_rca,
            incident.title,
            incident.detected_at.isoformat(),
        )
