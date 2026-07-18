"""Tests unitarios de las reglas de dominio.

Sin dependencias externas, sin mocks de AWS.
"""

from __future__ import annotations

from datetime import UTC, datetime

from src.domain.incident import Incident, IncidentStatus
from src.domain.rules import is_massive_impact, is_watched_region, should_notify

CRITICAL_SERVICES = ["ec2", "rds", "lambda", "s3"]
WATCHED_REGIONS = ["us-east-1", "us-east-2", "eu-west-1"]


def make_incident(**kwargs: object) -> Incident:
    defaults: dict[str, object] = {
        "incident_id": "test-001",
        "service": "ec2",
        "region": "us-east-1",
        "status": IncidentStatus.OPEN,
        "title": "EC2 instance connectivity issues",
        "detected_at": datetime(2024, 1, 1, tzinfo=UTC),
        "affected_services": [],
        "affected_regions": [],
    }
    defaults.update(kwargs)
    return Incident(**defaults)  # type: ignore[arg-type]


class TestIsMassiveImpact:
    def test_critical_service_is_massive(self) -> None:
        incident = make_incident(service="ec2")
        assert is_massive_impact(incident, CRITICAL_SERVICES) is True

    def test_non_critical_service_not_massive(self) -> None:
        incident = make_incident(service="cloudtrail", affected_services=[], affected_regions=[])
        assert is_massive_impact(incident, CRITICAL_SERVICES) is False

    def test_multiple_affected_regions_is_massive(self) -> None:
        incident = make_incident(
            service="cloudtrail",
            affected_regions=["us-east-1", "eu-west-1"],
        )
        assert is_massive_impact(incident, CRITICAL_SERVICES) is True

    def test_multiple_affected_services_is_massive(self) -> None:
        incident = make_incident(
            service="cloudtrail",
            affected_services=["cloudtrail", "cloudwatch"],
        )
        assert is_massive_impact(incident, CRITICAL_SERVICES) is True


class TestIsWatchedRegion:
    def test_watched_region_returns_true(self) -> None:
        incident = make_incident(region="us-east-1")
        assert is_watched_region(incident, WATCHED_REGIONS) is True

    def test_unwatched_region_returns_false(self) -> None:
        incident = make_incident(region="ap-southeast-1")
        assert is_watched_region(incident, WATCHED_REGIONS) is False


class TestShouldNotify:
    def test_notify_when_critical_service(self) -> None:
        incident = make_incident(service="s3", region="ap-southeast-1")
        assert should_notify(incident, CRITICAL_SERVICES, WATCHED_REGIONS) is True

    def test_notify_when_watched_region(self) -> None:
        incident = make_incident(service="cloudtrail", region="us-east-2")
        assert should_notify(incident, CRITICAL_SERVICES, WATCHED_REGIONS) is True

    def test_no_notify_when_neither(self) -> None:
        incident = make_incident(
            service="cloudtrail",
            region="ap-southeast-1",
            affected_services=[],
            affected_regions=[],
        )
        assert should_notify(incident, CRITICAL_SERVICES, WATCHED_REGIONS) is False
