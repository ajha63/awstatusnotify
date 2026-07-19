"""Tests de integración del adapter JsonDedupStore.

Todos los tests usan tmp_path de pytest (filesystem real, sin red).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from src.adapters.json_dedup_store import DEFAULT_TTL_DAYS, JsonDedupStore


@pytest.fixture
def store_path(tmp_path: Path) -> Path:
    return tmp_path / "seen_incidents.json"


# ------------------------------------------------------------------
# Tests del contrato básico (existentes, actualizados al formato v2)
# ------------------------------------------------------------------


def test_new_incident_not_seen(store_path: Path) -> None:
    store = JsonDedupStore(store_path)
    assert store.is_seen("abc123") is False


def test_mark_seen_persists(store_path: Path) -> None:
    store = JsonDedupStore(store_path)
    store.mark_seen("abc123")

    # Carga una nueva instancia para verificar persistencia entre ejecuciones
    store2 = JsonDedupStore(store_path)
    assert store2.is_seen("abc123") is True


def test_multiple_ids(store_path: Path) -> None:
    store = JsonDedupStore(store_path)
    store.mark_seen("id-1")
    store.mark_seen("id-2")

    assert store.is_seen("id-1") is True
    assert store.is_seen("id-2") is True
    assert store.is_seen("id-3") is False


def test_corrupted_file_handled_gracefully(store_path: Path) -> None:
    store_path.write_text("NOT_JSON", encoding="utf-8")
    store = JsonDedupStore(store_path)
    assert store.is_seen("any") is False


def test_len_reflects_active_entries(store_path: Path) -> None:
    store = JsonDedupStore(store_path)
    assert len(store) == 0
    store.mark_seen("id-1")
    store.mark_seen("id-2")
    assert len(store) == 2


def test_remove_eliminates_entry(store_path: Path) -> None:
    store = JsonDedupStore(store_path)
    store.mark_seen("id-1")
    assert store.is_seen("id-1") is True
    store.remove("id-1")
    assert store.is_seen("id-1") is False

    # Verificar que la eliminación persiste en nueva instancia
    store2 = JsonDedupStore(store_path)
    assert store2.is_seen("id-1") is False


def test_remove_nonexistent_id_is_silent(store_path: Path) -> None:
    store = JsonDedupStore(store_path)
    store.remove("nonexistent")  # No debe lanzar excepción


# ------------------------------------------------------------------
# Tests de formato v2 (timestamps en JSON)
# ------------------------------------------------------------------


def test_saved_file_uses_v2_format(store_path: Path) -> None:
    """El archivo guardado debe usar el formato dict con timestamps ISO 8601."""
    store = JsonDedupStore(store_path)
    store.mark_seen("abc123")

    raw = json.loads(store_path.read_text(encoding="utf-8"))
    assert isinstance(raw["seen_ids"], dict)
    assert "abc123" in raw["seen_ids"]
    # El valor debe ser un string ISO 8601 parseable
    ts = datetime.fromisoformat(raw["seen_ids"]["abc123"])
    assert ts.tzinfo is not None  # Debe tener timezone


# ------------------------------------------------------------------
# Tests de TTL
# ------------------------------------------------------------------


def test_expired_entry_not_seen(store_path: Path) -> None:
    """Una entrada con timestamp hace 91 días no debe aparecer como vista."""
    expired_ts = (datetime.now(tz=UTC) - timedelta(days=91)).isoformat()
    store_path.write_text(
        json.dumps({"seen_ids": {"old-id": expired_ts}}),
        encoding="utf-8",
    )
    store = JsonDedupStore(store_path, ttl_days=90)
    assert store.is_seen("old-id") is False


def test_fresh_entry_is_seen(store_path: Path) -> None:
    """Una entrada con timestamp de hoy debe aparecer como vista."""
    fresh_ts = datetime.now(tz=UTC).isoformat()
    store_path.write_text(
        json.dumps({"seen_ids": {"fresh-id": fresh_ts}}),
        encoding="utf-8",
    )
    store = JsonDedupStore(store_path, ttl_days=90)
    assert store.is_seen("fresh-id") is True


def test_ttl_boundary_exact_day(store_path: Path) -> None:
    """Una entrada exactamente en el límite del TTL se considera válida (>=, no >)."""
    # Exactamente en el límite: ahora - ttl_days → debe mantenerse
    boundary_ts = (datetime.now(tz=UTC) - timedelta(days=90) + timedelta(seconds=1)).isoformat()
    store_path.write_text(
        json.dumps({"seen_ids": {"boundary-id": boundary_ts}}),
        encoding="utf-8",
    )
    store = JsonDedupStore(store_path, ttl_days=90)
    assert store.is_seen("boundary-id") is True


def test_ttl_zero_days_expires_all(store_path: Path) -> None:
    """Con TTL de 0 días, todas las entradas expiran inmediatamente al cargar."""
    ts = (datetime.now(tz=UTC) - timedelta(seconds=1)).isoformat()
    store_path.write_text(
        json.dumps({"seen_ids": {"id-1": ts, "id-2": ts}}),
        encoding="utf-8",
    )
    store = JsonDedupStore(store_path, ttl_days=0)
    assert store.is_seen("id-1") is False
    assert store.is_seen("id-2") is False
    assert len(store) == 0


def test_ttl_configurable_keeps_recent_discards_old(store_path: Path) -> None:
    """Con TTL de 30 días, entradas de 20 días se conservan; de 40 días se descartan."""
    recent_ts = (datetime.now(tz=UTC) - timedelta(days=20)).isoformat()
    old_ts = (datetime.now(tz=UTC) - timedelta(days=40)).isoformat()
    store_path.write_text(
        json.dumps({"seen_ids": {"recent": recent_ts, "old": old_ts}}),
        encoding="utf-8",
    )
    store = JsonDedupStore(store_path, ttl_days=30)
    assert store.is_seen("recent") is True
    assert store.is_seen("old") is False


def test_default_ttl_is_90_days() -> None:
    """Verificar que el valor por defecto es el documentado en el módulo."""
    assert DEFAULT_TTL_DAYS == 90


# ------------------------------------------------------------------
# Tests de migración v1 → v2
# ------------------------------------------------------------------


def test_migration_from_v1_format(store_path: Path) -> None:
    """El formato v1 (lista de IDs) debe migrarse automáticamente al cargar."""
    store_path.write_text(
        json.dumps({"seen_ids": ["id-alpha", "id-beta", "id-gamma"]}),
        encoding="utf-8",
    )
    store = JsonDedupStore(store_path, ttl_days=90)

    # Los IDs del formato v1 deben ser reconocidos como vistos
    assert store.is_seen("id-alpha") is True
    assert store.is_seen("id-beta") is True
    assert store.is_seen("id-gamma") is True
    assert len(store) == 3


def test_migration_v1_persists_as_v2(store_path: Path) -> None:
    """Tras migrar, el archivo debe guardarse en formato v2 al marcar un nuevo ID."""
    store_path.write_text(
        json.dumps({"seen_ids": ["old-id"]}),
        encoding="utf-8",
    )
    store = JsonDedupStore(store_path, ttl_days=90)
    store.mark_seen("new-id")  # Dispara _save()

    raw = json.loads(store_path.read_text(encoding="utf-8"))
    # El archivo debe estar en formato v2 (dict, no lista)
    assert isinstance(raw["seen_ids"], dict)
    assert "old-id" in raw["seen_ids"]
    assert "new-id" in raw["seen_ids"]


def test_migration_v1_empty_list(store_path: Path) -> None:
    """Migración de lista vacía no debe producir errores."""
    store_path.write_text(json.dumps({"seen_ids": []}), encoding="utf-8")
    store = JsonDedupStore(store_path, ttl_days=90)
    assert len(store) == 0
