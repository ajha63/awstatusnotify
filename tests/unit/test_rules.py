"""Tests unitarios de las reglas de negocio.

Sin dependencias externas, sin mocks de AWS.
"""

from __future__ import annotations

from datetime import UTC, datetime

from src.domain.incident import (
    Incident,
    IncidentSeverity,
    IncidentStatus,
    IncidentType,
)
from src.domain.rules import is_massive_impact, is_watched_region, should_notify

CRITICAL_SERVICES = ["ec2", "rds", "lambda", "s3"]
WATCHED_REGIONS = ["us-east-1", "us-east-2", "eu-west-1"]


def make_incident(**kwargs: object) -> Incident:
    defaults: dict[str, object] = {
        "incident_id": "test001",
        "service": "EC2",
        "service_slug": "ec2-us-east-1",
        "region": "us-east-1",
        "status": IncidentStatus.OPEN,
        "severity": IncidentSeverity.MEDIUM,
        "incident_type": IncidentType.IMPACT,
        "title": "EC2 instance connectivity issues",
        "raw_title": "Service impact: EC2 instance connectivity issues",
        "detected_at": datetime(2024, 1, 1, tzinfo=UTC),
        "affected_services": [],
        "affected_regions": [],
        "affected_azs": [],
        "has_rca": False,
    }
    defaults.update(kwargs)
    return Incident(**defaults)  # type: ignore[arg-type]


class TestIsMassiveImpact:
    def test_critical_severity_is_massive(self) -> None:
        incident = make_incident(severity=IncidentSeverity.CRITICAL)
        assert is_massive_impact(incident, CRITICAL_SERVICES) is True

    def test_high_severity_is_massive(self) -> None:
        incident = make_incident(severity=IncidentSeverity.HIGH)
        assert is_massive_impact(incident, CRITICAL_SERVICES) is True

    def test_medium_non_critical_service_not_massive(self) -> None:
        incident = make_incident(
            service="cloudtrail",
            service_slug="cloudtrail-us-east-1",
            severity=IncidentSeverity.MEDIUM,
            affected_services=[],
            affected_regions=["us-east-1"],
        )
        assert is_massive_impact(incident, CRITICAL_SERVICES) is False

    def test_multi_region_is_massive(self) -> None:
        incident = make_incident(
            severity=IncidentSeverity.MEDIUM,
            affected_regions=["us-east-1", "eu-west-1"],
        )
        assert is_massive_impact(incident, CRITICAL_SERVICES) is True

    def test_multipleservices_slug_is_massive(self) -> None:
        incident = make_incident(
            service="Multiple services",
            service_slug="multipleservices-me-central-1",
            severity=IncidentSeverity.MEDIUM,
        )
        assert is_massive_impact(incident, CRITICAL_SERVICES) is True

    def test_critical_service_in_list_is_massive(self) -> None:
        incident = make_incident(
            service="s3",
            service_slug="s3",
            region="global",
            severity=IncidentSeverity.MEDIUM,
        )
        assert is_massive_impact(incident, CRITICAL_SERVICES) is True


class TestIsWatchedRegion:
    def test_watched_region_returns_true(self) -> None:
        incident = make_incident(region="us-east-1")
        assert is_watched_region(incident, WATCHED_REGIONS) is True

    def test_unwatched_region_returns_false(self) -> None:
        incident = make_incident(region="ap-southeast-1")
        assert is_watched_region(incident, WATCHED_REGIONS) is False

    def test_global_region_always_watched(self) -> None:
        incident = make_incident(region="global")
        assert is_watched_region(incident, WATCHED_REGIONS) is True


class TestShouldNotify:
    def test_notify_when_critical_severity(self) -> None:
        incident = make_incident(
            severity=IncidentSeverity.CRITICAL,
            region="ap-southeast-1",
        )
        assert should_notify(incident, CRITICAL_SERVICES, WATCHED_REGIONS) is True

    def test_notify_when_watched_region(self) -> None:
        incident = make_incident(
            service="cloudtrail",
            service_slug="cloudtrail-us-east-2",
            region="us-east-2",
            severity=IncidentSeverity.MEDIUM,
        )
        assert should_notify(incident, CRITICAL_SERVICES, WATCHED_REGIONS) is True

    def test_no_notify_when_neither(self) -> None:
        incident = make_incident(
            service="cloudtrail",
            service_slug="cloudtrail-ap-southeast-1",
            region="ap-southeast-1",
            severity=IncidentSeverity.MEDIUM,
            affected_services=[],
            affected_regions=["ap-southeast-1"],
        )
        assert should_notify(incident, CRITICAL_SERVICES, WATCHED_REGIONS) is False

    def test_no_notify_when_resolved(self) -> None:
        incident = make_incident(
            severity=IncidentSeverity.CRITICAL,
            region="us-east-1",
            status=IncidentStatus.RESOLVED,
        )
        assert should_notify(incident, CRITICAL_SERVICES, WATCHED_REGIONS) is False

    def test_notify_global_service(self) -> None:
        incident = make_incident(
            service="Billing Console",
            service_slug="billingconsole",
            region="global",
            severity=IncidentSeverity.MEDIUM,
        )
        assert should_notify(incident, CRITICAL_SERVICES, WATCHED_REGIONS) is True
