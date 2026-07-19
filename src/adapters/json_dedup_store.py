"""Adapter: deduplicación de incidentes usando un archivo JSON local.

Almacena los incident_id ya notificados para evitar envíos duplicados.
Reemplazable por dynamo_dedup_store.py en la migración a AWS.

Formato del archivo (v2, con TTL):
    {
      "seen_ids": {
        "a3f8c1d2e4b56789": "2026-07-18T12:00:00+00:00",
        "b7e2f4a1c3d58920": "2026-06-01T08:30:00+00:00"
      }
    }

Formato antiguo (v1, lista plana) — se migra automáticamente al cargar:
    {
      "seen_ids": ["a3f8c1d2e4b56789", "b7e2f4a1c3d58920"]
    }
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_STORE_PATH = Path("data/seen_incidents.json")
DEFAULT_TTL_DAYS = 90


class JsonDedupStore:
    """Gestiona la persistencia de incidentes ya notificados en un archivo JSON.

    Los IDs se almacenan junto con el timestamp en que fueron marcados (UTC ISO 8601).
    Al cargar, las entradas más antiguas que `ttl_days` se descartan automáticamente.
    """

    def __init__(
        self,
        store_path: Path = DEFAULT_STORE_PATH,
        ttl_days: int = DEFAULT_TTL_DAYS,
    ) -> None:
        self._path = store_path
        self._ttl_days = ttl_days
        # dict[incident_id → datetime UTC de cuándo fue marcado]
        self._seen: dict[str, datetime] = self._load()

    # ------------------------------------------------------------------
    # Carga y persistencia
    # ------------------------------------------------------------------

    def _load(self) -> dict[str, datetime]:
        """Carga el archivo JSON y filtra las entradas expiradas.

        Soporta dos formatos:
        - v1 (legacy): seen_ids es una lista de strings.
        - v2 (actual): seen_ids es un dict {id: iso8601_timestamp}.

        Las entradas del formato v1 se migran asignando datetime.now(UTC)
        como timestamp de marcado (conservador: se tratan como recién vistas).
        """
        if not self._path.exists():
            logger.debug("Archivo de deduplicación no encontrado, iniciando vacío: %s", self._path)
            return {}

        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            raw = data.get("seen_ids", {})
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("No se pudo leer el store de deduplicación: %s", exc)
            return {}

        # Migración v1 → v2: seen_ids era una lista de strings
        if isinstance(raw, list):
            logger.info(
                "Migrando store de deduplicación de formato v1 (lista) a v2 (dict con TTL): "
                "%d entradas",
                len(raw),
            )
            now_str = datetime.now(tz=UTC).isoformat()
            raw = {incident_id: now_str for incident_id in raw}

        # Parsear timestamps y filtrar expirados
        cutoff = datetime.now(tz=UTC) - timedelta(days=self._ttl_days)
        seen: dict[str, datetime] = {}
        expired = 0

        for incident_id, ts_str in raw.items():
            try:
                seen_at = datetime.fromisoformat(ts_str)
                if seen_at >= cutoff:
                    seen[incident_id] = seen_at
                else:
                    expired += 1
            except (ValueError, TypeError):
                # Timestamp malformado → descartar la entrada
                logger.debug("Timestamp inválido para %s, descartando entrada", incident_id)

        if expired:
            logger.info(
                "TTL: %d entradas expiradas eliminadas del store (ttl_days=%d)",
                expired,
                self._ttl_days,
            )

        return seen

    def _save(self) -> None:
        """Persiste el estado actual al archivo JSON (formato v2)."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # Serializar como dict ordenado por ID para diffs legibles
        payload = {
            "seen_ids": {
                incident_id: seen_at.isoformat()
                for incident_id, seen_at in sorted(self._seen.items())
            }
        }
        self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    # ------------------------------------------------------------------
    # Contrato público (DedupStore Protocol)
    # ------------------------------------------------------------------

    def is_seen(self, incident_id: str) -> bool:
        """Retorna True si el incidente ya fue notificado y su TTL no expiró."""
        return incident_id in self._seen

    def mark_seen(self, incident_id: str) -> None:
        """Registra el incidente como notificado con el timestamp actual y persiste."""
        self._seen[incident_id] = datetime.now(tz=UTC)
        self._save()
        logger.debug("Incidente marcado como visto: %s", incident_id)

    def remove(self, incident_id: str) -> None:
        """Elimina un incidente del store (usado al notificar resoluciones).

        Si el ID no existe, la operación es silenciosa (idempotente).
        """
        if incident_id in self._seen:
            del self._seen[incident_id]
            self._save()
            logger.debug("Incidente eliminado del store: %s", incident_id)

    # ------------------------------------------------------------------
    # Utilidades de inspección
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        """Número de entradas activas en el store."""
        return len(self._seen)
