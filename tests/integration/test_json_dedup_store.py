"""Tests de integración del adapter JsonDedupStore."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.adapters.json_dedup_store import JsonDedupStore


@pytest.fixture
def store_path(tmp_path: Path) -> Path:
    return tmp_path / "seen_incidents.json"


def test_new_incident_not_seen(store_path: Path) -> None:
    store = JsonDedupStore(store_path)
    assert store.is_seen("abc123") is False


def test_mark_seen_persists(store_path: Path) -> None:
    store = JsonDedupStore(store_path)
    store.mark_seen("abc123")

    # Carga una nueva instancia para verificar persistencia
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
