"""Adapter: lectura y parseo del feed RSS del AWS Service Health Dashboard.

Fuente real: https://status.aws.amazon.com/rss/<service-slug>.rss
El feed de índice con todos los slugs activos está en:
  https://status.aws.amazon.com/

Cada item del feed representa un UPDATE de un incidente, no el incidente
en sí. Varios items pueden pertenecer al mismo incidente lógico.

El incident_id se calcula como sha256(<slug>:<incident_name>)[:16] para
que sea estable por incidente lógico y permita deduplicación correcta.

SSL en macOS con Python 3.12+: feedparser puede fallar con SSL si no hay
CA bundle. Se pasa el XML descargado vía subprocess/curl como fallback.
"""

from __future__ import annotations

import hashlib
import logging
import re
import subprocess
from datetime import UTC, datetime
from xml.etree import ElementTree as ET

from src.domain.incident import (
    Incident,
    IncidentSeverity,
    IncidentStatus,
    IncidentType,
)

logger = logging.getLogger(__name__)

# URL base de los feeds RSS de AWS Service Health Dashboard
AWS_RSS_BASE = "https://status.aws.amazon.com/rss"

# Mapeo de prefijo de título → (tipo, severidad)
_TITLE_PREFIX_MAP: list[tuple[str, IncidentType, IncidentSeverity]] = [
    ("Service disruption", IncidentType.DISRUPTION, IncidentSeverity.CRITICAL),
    ("Service degradation", IncidentType.DEGRADATION, IncidentSeverity.HIGH),
    ("Increased error rate", IncidentType.ERROR_RATE, IncidentSeverity.HIGH),
    ("Increased Error Rate", IncidentType.ERROR_RATE, IncidentSeverity.HIGH),
    ("Service impact", IncidentType.IMPACT, IncidentSeverity.MEDIUM),
    ("Performance issue", IncidentType.PERFORMANCE, IncidentSeverity.LOW),
    ("Informational message", IncidentType.INFORMATIONAL, IncidentSeverity.INFO),
    ("Service is operating normally", IncidentType.OPERATIONAL, IncidentSeverity.RESOLVED),
]

# Regex de región AWS (cubre todos los patrones de región actuales)
_REGION_RE = re.compile(
    r"\b("
    r"us-(?:east|west)-\d|"
    r"eu-(?:west|central|north|south)-\d|"
    r"ap-(?:southeast|northeast|south|east)-\d|"
    r"sa-east-\d|"
    r"ca-(?:central|west)-\d|"
    r"me-(?:central|south)-\d|"
    r"af-south-\d|"
    r"il-central-\d"
    r")\b",
    re.IGNORECASE,
)

# Regex de AZ (ej. mec1-az2, use1-az3)
_AZ_RE = re.compile(r"\b([a-z]{2,4}\d-az\d)\b", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Clasificación de título
# ---------------------------------------------------------------------------


def _classify_title(raw_title: str) -> tuple[IncidentType, IncidentSeverity, bool]:
    """Retorna (tipo, severidad, is_resolved) a partir del título completo."""
    is_resolved = bool(re.search(r"\[RESOLVED\]|operating normally", raw_title, re.IGNORECASE))

    for prefix, itype, isev in _TITLE_PREFIX_MAP:
        if raw_title.startswith(prefix):
            return itype, isev, is_resolved

    # Fallback: si no coincide ningún prefijo conocido
    sev = IncidentSeverity.RESOLVED if is_resolved else IncidentSeverity.MEDIUM
    return IncidentType.UNKNOWN, sev, is_resolved


def _incident_name_from_title(raw_title: str) -> str:
    """Extrae el nombre del incidente quitando el prefijo de tipo y [RESOLVED].

    "Service disruption: Increased Error Rates" → "Increased Error Rates"
    "[RESOLVED] Inaccurate Estimated Billing Data" → "Inaccurate Estimated Billing Data"
    """
    name = re.sub(r"^[^:]+:\s*", "", raw_title)  # quitar "Prefijo: "
    name = re.sub(r"^\[RESOLVED\]\s*", "", name)  # quitar "[RESOLVED] "
    return name.strip()


# ---------------------------------------------------------------------------
# Extracción de región y AZs
# ---------------------------------------------------------------------------


def _region_from_slug(slug: str) -> str:
    """Extrae la región del slug del feed.

    "ec2-us-east-1"                  → "us-east-1"
    "multipleservices-me-central-1"  → "me-central-1"
    "billingconsole"                 → "global"
    """
    m = _REGION_RE.search(slug)
    return m.group(1).lower() if m else "global"


def _service_name_from_slug(slug: str) -> str:
    """Extrae un nombre legible del servicio a partir del slug.

    "ec2-us-east-1"                 → "EC2"
    "multipleservices-me-central-1" → "Multiple services"
    "billingconsole"                → "Billing Console"
    """
    # Quitar sufijo de región
    name = _REGION_RE.sub("", slug).rstrip("-")
    if name == "multipleservices":
        return "Multiple services"
    # CamelCase aproximado: "billingconsole" → "Billingconsole" (legible)
    return name.replace("-", " ").title()


def _extract_regions(text: str) -> list[str]:
    """Extrae todas las regiones AWS mencionadas en el texto."""
    return [m.lower() for m in _REGION_RE.findall(text)]


def _extract_azs(text: str) -> list[str]:
    """Extrae todas las AZs mencionadas en el texto."""
    return [m.lower() for m in _AZ_RE.findall(text)]


def _has_rca(description: str) -> bool:
    """Retorna True si el update menciona identificación de causa raíz."""
    return bool(
        re.search(
            r"identified the root cause|root cause|retrospective",
            description,
            re.IGNORECASE,
        )
    )


# ---------------------------------------------------------------------------
# Generación de incident_id estable
# ---------------------------------------------------------------------------


def _incident_id(slug: str, incident_name: str) -> str:
    """ID estable por incidente lógico: sha256(<slug>:<incident_name>)[:16].

    Estable entre runs: el mismo incidente siempre produce el mismo ID,
    aunque AWS publique múltiples updates con guids distintos.
    """
    raw = f"{slug}:{incident_name}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Descarga del XML (con fallback a curl por SSL en macOS/Python 3.14)
# ---------------------------------------------------------------------------


def _fetch_xml(url: str) -> str:
    """Descarga el XML del feed. Usa curl para evitar problemas de SSL en macOS."""
    result = subprocess.run(  # noqa: S603
        ["curl", "-sL", "--max-time", "15", url],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise RuntimeError(f"No se pudo descargar el feed RSS ({url}): {result.stderr.strip()}")
    return result.stdout


# ---------------------------------------------------------------------------
# Parseo del XML
# ---------------------------------------------------------------------------


def _parse_items(xml_text: str) -> tuple[str, list[dict[str, str]]]:
    """Parsea el XML del feed y retorna (feed_title, items).

    Cada item es un dict con keys: title, pubDate, guid, description.
    """
    root = ET.fromstring(xml_text)
    channel = root.find("channel")
    if channel is None:
        raise RuntimeError("XML del feed no contiene elemento <channel>")

    feed_title = channel.findtext("title") or ""
    items: list[dict[str, str]] = []
    for item in channel.findall("item"):
        entry = {child.tag: (child.text or "") for child in item}
        items.append(entry)

    return feed_title, items


# ---------------------------------------------------------------------------
# Conversión item → Incident
# ---------------------------------------------------------------------------


def _item_to_incident(item: dict[str, str], slug: str) -> Incident | None:
    """Convierte un item RSS en una entidad Incident.

    Retorna None si el item no puede parsearse correctamente.
    """
    raw_title = item.get("title", "").strip()
    if not raw_title:
        return None

    itype, isev, resolved = _classify_title(raw_title)
    incident_name = _incident_name_from_title(raw_title)
    region = _region_from_slug(slug)
    service = _service_name_from_slug(slug)
    description = item.get("description", "")

    # Regiones y AZs adicionales mencionadas en el description
    regions_in_desc = _extract_regions(description)
    azs_in_desc = _extract_azs(description)

    # Si hay más de una región en el description, sobreescribir la del slug
    # con la lista completa (para que is_multi_region funcione)
    if region != "global":
        affected_regions = list(dict.fromkeys([region] + regions_in_desc))
    else:
        affected_regions = regions_in_desc

    # pubDate → datetime UTC
    pub_raw = item.get("pubDate", "")
    try:
        from email.utils import parsedate_to_datetime

        detected_at = parsedate_to_datetime(pub_raw).astimezone(UTC)
    except Exception:  # noqa: BLE001
        detected_at = datetime.now(tz=UTC)

    return Incident(
        incident_id=_incident_id(slug, incident_name),
        service=service,
        service_slug=slug,
        region=region,
        status=IncidentStatus.RESOLVED if resolved else IncidentStatus.OPEN,
        severity=isev,
        incident_type=itype,
        title=incident_name,
        raw_title=raw_title,
        detected_at=detected_at,
        affected_regions=affected_regions,
        affected_azs=azs_in_desc,
        has_rca=_has_rca(description),
    )


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------


def feed_url_for_slug(slug: str) -> str:
    """Construye la URL del feed RSS para un slug dado."""
    return f"{AWS_RSS_BASE}/{slug}.rss"


def fetch_incidents_from_slug(slug: str) -> list[Incident]:
    """Descarga el feed RSS de un slug y retorna la lista de incidentes únicos.

    Agrupa los items por incidente lógico (mismo slug + incident_name) y
    retorna solo el item más reciente de cada grupo, que refleja el estado
    actual del incidente.

    Raises:
        RuntimeError: si el feed no puede descargarse o parsearse.
    """
    url = feed_url_for_slug(slug)
    logger.info("Descargando feed: %s", url)

    xml = _fetch_xml(url)
    _, items = _parse_items(xml)
    logger.info("Feed %s: %d items descargados", slug, len(items))

    # Agrupar por incident_id (incidente lógico), quedarse con el más reciente
    latest: dict[str, Incident] = {}
    for item in items:
        incident = _item_to_incident(item, slug)
        if incident is None:
            continue
        existing = latest.get(incident.incident_id)
        if existing is None or incident.detected_at > existing.detected_at:
            latest[incident.incident_id] = incident

    result = list(latest.values())
    logger.info("Feed %s: %d incidentes únicos identificados", slug, len(result))
    return result


def fetch_incidents(slugs: list[str]) -> list[Incident]:
    """Descarga y parsea los feeds RSS de la lista de slugs proporcionada.

    Retorna todos los incidentes activos (no resueltos) de todos los feeds.
    Los errores en un feed individual se loguean pero no detienen el procesamiento.
    """
    all_incidents: list[Incident] = []
    for slug in slugs:
        try:
            incidents = fetch_incidents_from_slug(slug)
            all_incidents.extend(incidents)
        except RuntimeError as exc:
            logger.error("Error procesando feed '%s': %s", slug, exc)

    logger.info("Total incidentes cargados de %d feeds: %d", len(slugs), len(all_incidents))
    return all_incidents
