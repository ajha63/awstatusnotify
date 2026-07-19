"""Tests unitarios del parseo del feed RSS (sin red, sin curl).

Valida las funciones puras de clasificación, extracción y generación de IDs.
"""

from __future__ import annotations

from src.adapters.health_feed import (
    _classify_title,
    _extract_azs,
    _extract_regions,
    _has_rca,
    _incident_id,
    _incident_name_from_title,
    _region_from_slug,
    _service_name_from_slug,
    feed_url_for_slug,
)
from src.domain.incident import IncidentSeverity, IncidentType


class TestClassifyTitle:
    def test_disruption(self) -> None:
        itype, sev, resolved = _classify_title("Service disruption: Increased Error Rates")
        assert itype == IncidentType.DISRUPTION
        assert sev == IncidentSeverity.CRITICAL
        assert resolved is False

    def test_resolved_tag(self) -> None:
        _, _, resolved = _classify_title(
            "Service is operating normally: [RESOLVED] Inaccurate Estimated Billing Data"
        )
        assert resolved is True

    def test_resolved_bracket(self) -> None:
        _, _, resolved = _classify_title("[RESOLVED] Inaccurate Estimated Billing Data")
        assert resolved is True

    def test_impact_medium(self) -> None:
        itype, sev, _ = _classify_title("Service impact: Something went wrong")
        assert itype == IncidentType.IMPACT
        assert sev == IncidentSeverity.MEDIUM

    def test_error_rate_high(self) -> None:
        _, sev, _ = _classify_title("Increased error rate: Lambda throttles")
        assert sev == IncidentSeverity.HIGH

    def test_operational_resolved_severity(self) -> None:
        itype, sev, resolved = _classify_title("Service is operating normally: EC2 recovered")
        assert itype == IncidentType.OPERATIONAL
        assert sev == IncidentSeverity.RESOLVED
        assert resolved is True


class TestIncidentNameFromTitle:
    def test_strips_prefix(self) -> None:
        assert (
            _incident_name_from_title("Service disruption: Increased Error Rates")
            == "Increased Error Rates"
        )

    def test_strips_resolved_bracket(self) -> None:
        assert (
            _incident_name_from_title("[RESOLVED] Inaccurate Estimated Billing Data")
            == "Inaccurate Estimated Billing Data"
        )

    def test_strips_operating_normally_prefix(self) -> None:
        # Quita "Service is operating normally: " y luego "[RESOLVED] "
        assert (
            _incident_name_from_title(
                "Service is operating normally: [RESOLVED] Inaccurate Estimated Billing Data"
            )
            == "Inaccurate Estimated Billing Data"
        )


class TestRegionFromSlug:
    def test_ec2_us_east(self) -> None:
        assert _region_from_slug("ec2-us-east-1") == "us-east-1"

    def test_multipleservices_me(self) -> None:
        assert _region_from_slug("multipleservices-me-central-1") == "me-central-1"

    def test_global_service(self) -> None:
        assert _region_from_slug("billingconsole") == "global"

    def test_s3_global(self) -> None:
        assert _region_from_slug("s3") == "global"


class TestServiceNameFromSlug:
    def test_multipleservices(self) -> None:
        assert _service_name_from_slug("multipleservices-me-central-1") == "Multiple services"

    def test_ec2(self) -> None:
        assert _service_name_from_slug("ec2-us-east-1") == "Ec2"

    def test_billingconsole(self) -> None:
        assert _service_name_from_slug("billingconsole") == "Billingconsole"


class TestExtractRegions:
    def test_finds_region_in_text(self) -> None:
        regions = _extract_regions(
            "The ME-CENTRAL-1 Region (mec1-az2 and mec1-az3) remain impaired."
        )
        assert "me-central-1" in regions

    def test_multi_region(self) -> None:
        regions = _extract_regions("Affecting US-EAST-1 and EU-WEST-1 simultaneously.")
        assert "us-east-1" in regions
        assert "eu-west-1" in regions

    def test_no_region(self) -> None:
        assert _extract_regions("No region mentioned here.") == []


class TestExtractAzs:
    def test_finds_az(self) -> None:
        azs = _extract_azs("Availability Zones mec1-az2 and mec1-az3 are impaired.")
        assert "mec1-az2" in azs
        assert "mec1-az3" in azs

    def test_no_az(self) -> None:
        assert _extract_azs("No AZ mentioned.") == []


class TestHasRca:
    def test_root_cause_phrase(self) -> None:
        assert _has_rca("We identified the root cause as a configuration change.") is True

    def test_retrospective_phrase(self) -> None:
        assert _has_rca("We are conducting a thorough retrospective.") is True

    def test_no_rca(self) -> None:
        assert _has_rca("We are investigating the issue.") is False


class TestIncidentId:
    def test_stable_across_calls(self) -> None:
        id1 = _incident_id("ec2-us-east-1", "Connectivity Issues")
        id2 = _incident_id("ec2-us-east-1", "Connectivity Issues")
        assert id1 == id2

    def test_different_slugs_produce_different_ids(self) -> None:
        id1 = _incident_id("ec2-us-east-1", "Connectivity Issues")
        id2 = _incident_id("ec2-us-west-2", "Connectivity Issues")
        assert id1 != id2

    def test_length_16(self) -> None:
        assert len(_incident_id("billingconsole", "Inaccurate Billing Data")) == 16


class TestFeedUrlForSlug:
    def test_url_format(self) -> None:
        assert feed_url_for_slug("ec2-us-east-1") == (
            "https://status.aws.amazon.com/rss/ec2-us-east-1.rss"
        )
