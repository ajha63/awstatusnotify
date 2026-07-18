"""Adapter: deduplicación de incidentes usando un archivo JSON local.

Almacena los incident_id ya notificados para evitar envíos duplicados.
Reemplazable por dynamo_dedup_store.py en la migración a AWS.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_STORE_PATH = Path("data/seen_incidents.json")


class JsonDedupStore:
    """Gestiona la persistencia de incidentes ya notificados en un archivo JSON."""

    def __init__(self, store_path: Path = DEFAULT_STORE_PATH) -> None:
        self._path = store_path
        self._seen: set[str] = self._load()

    def _load(self) -> set[str]:
        """Carga el archivo JSON existente. Retorna set vacío si no existe."""
        if not self._path.exists():
            logger.debug("Archivo de deduplicación no encontrado, iniciando vacío: %s", self._path)
            return set()
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            return set(data.get("seen_ids", []))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("No se pudo leer el store de deduplicación: %s", exc)
            return set()

    def _save(self) -> None:
        """Persiste el estado actual al archivo JSON."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps({"seen_ids": sorted(self._seen)}, indent=2),
            encoding="utf-8",
        )

    def is_seen(self, incident_id: str) -> bool:
        """Retorna True si el incidente ya fue notificado."""
        return incident_id in self._seen

    def mark_seen(self, incident_id: str) -> None:
        """Registra el incidente como notificado y persiste el cambio."""
        self._seen.add(incident_id)
        self._save()
        logger.debug("Incidente marcado como visto: %s", incident_id)
